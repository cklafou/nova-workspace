# Last updated: 2026-10-06 03:19:20
# @nova: Searches public model repositories (Hugging Face, ModelScope, Ollama) and lists a model's downloadable files with sizes and hashes.
"""Model repositories the updater can search.

Each source returns `Hit` rows with the same fields so the widget can show and filter them
uniformly. Hugging Face and ModelScope can also list files (size + sha256) for installing;
the Ollama library is search-and-link only, because Nova runs llama.cpp GGUF files directly.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
import urllib.parse

from . import naming, net

PERMISSIVE = ("apache-2.0", "mit")


@dataclass
class Hit:
    source: str
    id: str
    title: str = ""
    author: str = ""
    created: str = ""
    modified: str = ""
    downloads: int | None = None
    likes: int | None = None
    license: str = ""
    gated: bool = False
    pipeline: str = ""
    params: int | None = None
    tags: list = field(default_factory=list)
    url: str = ""
    installable: bool = True
    formats: list = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        parsed = naming.parse(self.id)
        data["name"] = parsed.to_dict() if parsed else None
        data["params_b"] = round(self.params / 1e9, 2) if self.params else (parsed.size_b if parsed else None)
        return data


@dataclass
class FileInfo:
    path: str
    size: int | None = None
    sha256: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _license_from_tags(tags) -> str:
    for tag in tags or []:
        if isinstance(tag, str) and tag.startswith("license:"):
            return tag.split(":", 1)[1]
    return ""


def _formats(tags, model_id: str) -> list:
    lowered = {str(t).lower() for t in tags or []}
    found = []
    if "gguf" in lowered or model_id.lower().endswith("-gguf"):
        found.append("gguf")
    if "safetensors" in lowered or "library:safetensors" in lowered:
        found.append("safetensors")
    return found


class HuggingFace:
    name = "huggingface"
    title = "Hugging Face"
    installable = True
    API = "https://huggingface.co/api"
    EXPAND = ("createdAt", "lastModified", "safetensors", "pipeline_tag", "cardData", "gated",
              "downloads", "likes", "tags")

    def __init__(self, get_json=None, token: str | None = None):
        self._get = get_json or net.get_json
        self._headers = {"Authorization": "Bearer " + token} if token else None

    def search(self, q: str = "", author: str | None = None, sort: str = "createdAt", limit: int = 50,
               gguf: bool = False, pipeline: str | None = None, timeout: float = 10.0) -> list:
        params = []
        if q:
            params.append(("search", q))
        if author:
            params.append(("author", author))
        params += [("sort", sort if sort in ("createdAt", "lastModified", "downloads", "likes", "trendingScore") else "createdAt"),
                   ("direction", "-1"), ("limit", str(max(1, min(int(limit), 200))))]
        if gguf:
            params.append(("filter", "gguf"))
        if pipeline:
            params.append(("pipeline_tag", pipeline))
        params += [("expand[]", e) for e in self.EXPAND]
        rows = self._get(self.API + "/models", params, self._headers, timeout)
        return [self._hit(row) for row in rows if isinstance(row, dict) and row.get("id")]

    def _hit(self, row: dict) -> Hit:
        tags = row.get("tags") or []
        card = row.get("cardData") or {}
        lic = card.get("license") if isinstance(card, dict) else ""
        if isinstance(lic, list):
            lic = lic[0] if lic else ""
        safetensors = row.get("safetensors") or {}
        return Hit(source=self.name, id=row["id"], title=row["id"].split("/")[-1],
                   author=row["id"].split("/")[0] if "/" in row["id"] else "",
                   created=row.get("createdAt") or "", modified=row.get("lastModified") or "",
                   downloads=row.get("downloads"), likes=row.get("likes"),
                   license=(lic or _license_from_tags(tags) or "").lower(), gated=bool(row.get("gated")),
                   pipeline=row.get("pipeline_tag") or "", params=safetensors.get("total"),
                   tags=[t for t in tags if isinstance(t, str)][:40],
                   url=f"https://huggingface.co/{row['id']}", installable=True,
                   formats=_formats(tags, row["id"]))

    def files(self, repo: str, timeout: float = 15.0) -> list:
        data = self._get(f"{self.API}/models/{urllib.parse.quote(repo, safe='/')}", [("blobs", "true")],
                         self._headers, timeout)
        out = []
        for sibling in data.get("siblings") or []:
            lfs = sibling.get("lfs") or {}
            out.append(FileInfo(path=sibling.get("rfilename", ""), size=sibling.get("size") or lfs.get("size"),
                                sha256=lfs.get("sha256")))
        return [f for f in out if f.path]

    def config(self, repo: str, timeout: float = 15.0) -> dict:
        return self._get(self.download_url(repo, "config.json"), None, self._headers, timeout)

    def download_url(self, repo: str, path: str, revision: str = "main") -> str:
        return (f"https://huggingface.co/{urllib.parse.quote(repo, safe='/')}/resolve/"
                f"{urllib.parse.quote(revision, safe='')}/{urllib.parse.quote(path, safe='/')}")

    def auth_headers(self) -> dict:
        return dict(self._headers or {})


class ModelScope:
    name = "modelscope"
    title = "ModelScope"
    installable = True
    SEARCH = "https://www.modelscope.cn/openapi/v1/models"
    API = "https://modelscope.cn/api/v1/models"

    def __init__(self, get_json=None):
        self._get = get_json or net.get_json

    def search(self, q: str = "", author: str | None = None, sort: str = "createdAt", limit: int = 50,
               gguf: bool = False, pipeline: str | None = None, timeout: float = 10.0) -> list:
        term = " ".join(x for x in (q, "GGUF" if gguf and "gguf" not in q.lower() else "") if x).strip()
        params = [("search", term or author or "Qwen"), ("page_size", str(max(1, min(int(limit), 100))))]
        data = self._get(self.SEARCH, params, None, timeout)
        rows = ((data or {}).get("data") or {}).get("models") or []
        hits = []
        for row in rows:
            if not isinstance(row, dict) or not row.get("id"):
                continue
            if author and not row["id"].lower().startswith(author.lower() + "/"):
                continue
            tags = row.get("tags") or []
            tasks = row.get("tasks") or []
            hits.append(Hit(source=self.name, id=row["id"], title=row.get("display_name") or row["id"],
                            author=row["id"].split("/")[0], created=row.get("created_at") or "",
                            modified=row.get("last_modified") or "", downloads=row.get("downloads"),
                            likes=row.get("likes"), license=(row.get("license") or _license_from_tags(tags)).lower(),
                            gated=bool(row.get("gated")), pipeline=tasks[0] if tasks else "",
                            params=row.get("params"), tags=[t for t in tags if isinstance(t, str)][:40],
                            url=f"https://modelscope.cn/models/{row['id']}", installable=True,
                            formats=_formats(tags, row["id"])))
        if pipeline:
            hits = [h for h in hits if h.pipeline == pipeline]
        return hits

    def files(self, repo: str, timeout: float = 15.0) -> list:
        data = self._get(f"{self.API}/{urllib.parse.quote(repo, safe='/')}/repo/files",
                         [("Revision", "master"), ("Recursive", "true")], None, timeout)
        rows = ((data or {}).get("Data") or {}).get("Files") or []
        return [FileInfo(path=r.get("Path", ""), size=r.get("Size"), sha256=r.get("Sha256"))
                for r in rows if isinstance(r, dict) and r.get("Type", "blob") == "blob" and r.get("Path")]

    def config(self, repo: str, timeout: float = 15.0) -> dict:
        return self._get(self.download_url(repo, "config.json"), None, None, timeout)

    def download_url(self, repo: str, path: str, revision: str = "master") -> str:
        return (f"https://modelscope.cn/models/{urllib.parse.quote(repo, safe='/')}/resolve/"
                f"{urllib.parse.quote(revision, safe='')}/{urllib.parse.quote(path, safe='/')}")

    def auth_headers(self) -> dict:
        return {}


class Ollama:
    """Search-and-link only: Ollama stores models in its own blob store, not as llama.cpp files."""
    name = "ollama"
    title = "Ollama library"
    installable = False
    SEARCH = "https://ollama.com/search"
    LINK_RE = re.compile(r'href="/library/([A-Za-z0-9._:-]+)"')

    def __init__(self, get_text=None):
        self._get_text = get_text or net.get_text

    def search(self, q: str = "", limit: int = 50, timeout: float = 10.0, **_ignored) -> list:
        html = self._get_text(self.SEARCH, [("q", q or "qwen")], None, timeout)
        seen, hits = set(), []
        for name in self.LINK_RE.findall(html):
            if name in seen:
                continue
            seen.add(name)
            hits.append(Hit(source=self.name, id=name, title=name, url=f"https://ollama.com/library/{name}",
                            installable=False))
            if len(hits) >= limit:
                break
        return hits

    def files(self, repo: str, timeout: float = 15.0) -> list:
        raise net.NetError("Ollama models install through Ollama itself; open the link instead.")


SOURCES = {"huggingface": HuggingFace, "modelscope": ModelScope, "ollama": Ollama}


def source(name: str, **kwargs):
    try:
        return SOURCES[name](**kwargs)
    except KeyError:
        raise ValueError(f"Unknown repository '{name}'. Choose one of: {', '.join(SOURCES)}") from None


def describe_sources() -> list:
    return [{"name": k, "title": v.title, "installable": v.installable} for k, v in SOURCES.items()]


def filter_hits(hits, min_b=None, max_b=None, dense_only=False, licenses=None, include_quantized=True,
                pipelines=None, formats=None, family=None, newer_than=None) -> list:
    """Advanced filters shared by the widget search and the startup check."""
    out = []
    for hit in hits:
        parsed = naming.parse(hit.id)
        size = (hit.params / 1e9) if hit.params else (parsed.size_b if parsed else None)
        name_size = parsed.size_b if parsed else None
        if min_b is not None and (name_size if name_size is not None else size or 0) < float(min_b):
            continue
        if max_b is not None and (name_size if name_size is not None else size or 1e9) > float(max_b):
            continue
        if dense_only and (not parsed or parsed.moe):
            continue
        if not include_quantized and parsed and parsed.quantized:
            continue
        if licenses and (hit.license or "").lower() not in {l.lower() for l in licenses}:
            continue
        if pipelines and hit.pipeline and hit.pipeline not in pipelines:
            continue
        if formats and not set(formats) & set(hit.formats):
            continue
        if family and (not parsed or parsed.family.lower() != family.lower()):
            continue
        if newer_than is not None and (not parsed or not naming.is_newer(parsed, newer_than)):
            continue
        out.append(hit)
    return out


SORT_KEYS = {
    "created": lambda h: h.created or "",
    "modified": lambda h: h.modified or "",
    "downloads": lambda h: h.downloads or 0,
    "likes": lambda h: h.likes or 0,
    "params": lambda h: h.params or 0,
}


def sort_hits(hits, key: str = "created", descending: bool = True) -> list:
    return sorted(hits, key=SORT_KEYS.get(key, SORT_KEYS["created"]), reverse=descending)
