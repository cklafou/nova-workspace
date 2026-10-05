# Last updated: 2026-10-05 21:33:05
# @nova: Parses model repository and GGUF file names (Qwen first) into version, size, variant and quant so releases can be compared.
"""Model-name parsing for update checks. Pure functions, no I/O.

    Qwen/Qwen3.8-27B                    -> family Qwen, version (3, 8), 27B, dense chat model
    Qwen/Qwen3-30B-A3B-Instruct-2507    -> MoE (A3B), revision 2507
    Qwen/Qwen3.6-27B-FP8                -> quantized variant (not a drop-in base)
    Qwen3.6-27B-UD-Q6_K_XL.gguf         -> model Qwen3.6-27B, quant UD-Q6_K_XL
"""
from __future__ import annotations

from dataclasses import dataclass
import re

QUANT_TOKENS = {"fp8", "fp16", "bf16", "fp4", "gptq", "awq", "int4", "int8", "gguf", "mlx", "bnb",
                "4bit", "8bit", "exl2", "exl3", "nf4", "w4a16", "w8a8", "onnx", "mxfp4", "nvfp4"}
NAME_RE = re.compile(r"^(?:(?P<org>[^/\s]+)/)?(?P<family>[A-Za-z][A-Za-z]*?)(?P<ver>\d+(?:\.\d+)*)?-(?P<rest>.+)$")
SIZE_RE = re.compile(r"^(?P<size>\d+(?:\.\d+)?)B$", re.I)
ACTIVE_RE = re.compile(r"^A(?P<active>\d+(?:\.\d+)?)B$", re.I)
REVISION_RE = re.compile(r"^\d{4}$")
QUANT_RE = re.compile(r"(?:^|-)(?P<quant>(?:UD-)?(?:I?Q\d(?:_[A-Z0-9]+)*|BF16|F16|F32|MXFP4(?:_MOE)?))$", re.I)
SPLIT_RE = re.compile(r"-(?P<part>\d{5})-of-(?P<total>\d{5})$")


@dataclass(frozen=True)
class ModelName:
    repo: str
    org: str
    family: str
    version: tuple
    size_b: float | None
    active_b: float | None
    variant: tuple
    revision: str

    @property
    def moe(self) -> bool:
        return self.active_b is not None

    @property
    def quantized(self) -> bool:
        return any(token in QUANT_TOKENS for token in self.variant)

    @property
    def base_only(self) -> bool:
        return "base" in self.variant

    @property
    def dense_chat(self) -> bool:
        return not self.moe and not self.quantized and not self.base_only and self.size_b is not None

    @property
    def label(self) -> str:
        return self.repo.split("/")[-1]

    @property
    def version_text(self) -> str:
        return ".".join(str(v) for v in self.version)

    @property
    def slug(self) -> str:
        """Folder name under models/, matching today's `models/qwen3.6/`."""
        return (self.family + self.version_text).lower() or self.label.lower()

    def to_dict(self) -> dict:
        return {"repo": self.repo, "org": self.org, "family": self.family, "version": self.version_text,
                "size_b": self.size_b, "active_b": self.active_b, "variant": list(self.variant),
                "revision": self.revision, "moe": self.moe, "quantized": self.quantized,
                "base_only": self.base_only, "dense_chat": self.dense_chat, "slug": self.slug}


def parse(repo: str) -> ModelName | None:
    """Parse `org/Name` (or bare `Name`); None if it does not look like `Family<ver>-<size>B...`."""
    text = (repo or "").strip()
    match = NAME_RE.match(text)
    if not match:
        return None
    tokens = match.group("rest").split("-")
    size_b = active_b = None
    variant, revision = [], ""
    for token in tokens:
        size = SIZE_RE.match(token)
        active = ACTIVE_RE.match(token)
        if size and size_b is None:
            size_b = float(size.group("size"))
        elif active and active_b is None:
            active_b = float(active.group("active"))
        elif REVISION_RE.match(token) and not revision:
            revision = token
        elif token:
            variant.append(token.lower())
    if size_b is None:
        return None
    version = tuple(int(part) for part in match.group("ver").split(".")) if match.group("ver") else ()
    return ModelName(repo=text, org=match.group("org") or "", family=match.group("family"),
                     version=version, size_b=size_b, active_b=active_b, variant=tuple(variant),
                     revision=revision)


def _key(name: ModelName) -> tuple:
    padded = tuple(name.version) + (0,) * (4 - len(name.version))
    return padded, name.revision


def is_newer(candidate: ModelName, current: ModelName) -> bool:
    """Same family, and a higher version (or the same version with a later revision tag)."""
    if candidate.family.lower() != current.family.lower():
        return False
    return _key(candidate) > _key(current)


def parse_gguf_filename(filename: str) -> dict:
    """Split a GGUF file name into model name, quant label and split part."""
    stem = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if stem.lower().endswith(".gguf"):
        stem = stem[:-5]
    info = {"file": filename, "mmproj": "mmproj" in stem.lower(), "quant": None, "part": None,
            "parts": None, "model": None}
    split = SPLIT_RE.search(stem)
    if split:
        info["part"], info["parts"] = int(split.group("part")), int(split.group("total"))
        stem = stem[: split.start()]
    quant = QUANT_RE.search(stem)
    if quant:
        info["quant"] = quant.group("quant")
        stem = stem[: quant.start()]
    parsed = parse(stem) if not info["mmproj"] else None
    info["model"] = parsed.to_dict() if parsed else None
    info["stem"] = stem
    return info


def same_quant(a: str | None, b: str | None) -> bool:
    return bool(a and b and a.lower() == b.lower())
