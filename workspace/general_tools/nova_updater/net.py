# Last updated: 2026-10-05 18:23:37
# @nova: Minimal HTTPS client for public model catalogs: JSON and text GETs with timeouts, and resumable download streams.
"""Standard-library HTTP for the updater. No third-party dependencies.

Every call has a timeout. Errors become NetError with a short, credential-free message.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "NovaUpdater/1.0 (Project Nova model updater)"
MAX_JSON = 32 * 1024 * 1024


class NetError(Exception):
    """A network or HTTP failure, safe to show the user, with optional HTTP status."""
    def __init__(self, message, *, status_code=None):
        super().__init__(message)
        self.status_code = status_code


def build_url(url: str, params=None) -> str:
    if not params:
        return url
    items = params.items() if isinstance(params, dict) else params
    query = urllib.parse.urlencode([(k, v) for k, v in items if v is not None and v != ""], doseq=True)
    return url + ("&" if "?" in url else "?") + query if query else url


def _request(url: str, headers=None, method: str = "GET", data: bytes | None = None):
    merged = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    merged.update(headers or {})
    return urllib.request.Request(url, headers=merged, method=method, data=data)


def get_bytes(url: str, params=None, headers=None, timeout: float = 10.0, limit: int = MAX_JSON) -> bytes:
    full = build_url(url, params)
    try:
        with urllib.request.urlopen(_request(full, headers), timeout=timeout) as response:
            body = response.read(limit + 1)
    except urllib.error.HTTPError as error:
        raise NetError(f"{urllib.parse.urlsplit(full).netloc} answered HTTP {error.code}", status_code=error.code) from None
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        reason = getattr(error, "reason", error)
        raise NetError(f"Could not reach {urllib.parse.urlsplit(full).netloc}: {reason}") from None
    if len(body) > limit:
        raise NetError("Response was larger than expected; refusing to read it.")
    return body


def get_json(url: str, params=None, headers=None, timeout: float = 10.0):
    body = get_bytes(url, params, headers, timeout)
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeError, ValueError):
        raise NetError("The catalog returned something that is not JSON.") from None


def get_text(url: str, params=None, headers=None, timeout: float = 10.0) -> str:
    return get_bytes(url, params, {"Accept": "text/html,*/*", **(headers or {})}, timeout).decode("utf-8", "replace")


def send_json(url: str, method: str, body=None, headers=None, timeout: float = 20.0):
    data = None if body is None else json.dumps(body).encode("utf-8")
    merged = {"Content-Type": "application/json", **(headers or {})}
    try:
        with urllib.request.urlopen(_request(url, merged, method, data), timeout=timeout) as response:
            raw = response.read(MAX_JSON + 1)
    except urllib.error.HTTPError as error:
        raise NetError(f"{urllib.parse.urlsplit(url).netloc} answered HTTP {error.code} to {method}", status_code=error.code) from None
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise NetError(f"Could not reach {urllib.parse.urlsplit(url).netloc}: {getattr(error, 'reason', error)}") from None
    if not raw.strip():
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError):
        raise NetError("The service returned something that is not JSON.") from None


def open_stream(url: str, start: int = 0, headers=None, timeout: float = 30.0):
    """Open a download, resuming at byte `start`. Returns (response, resumed: bool)."""
    merged = {"Accept": "*/*", **(headers or {})}
    if start > 0:
        merged["Range"] = f"bytes={start}-"
    try:
        response = urllib.request.urlopen(_request(url, merged), timeout=timeout)
    except urllib.error.HTTPError as error:
        if error.code == 416 and start > 0:
            raise NetError("The server says the partial file is already complete or too long.") from None
        raise NetError(f"Download refused: HTTP {error.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise NetError(f"Download could not start: {getattr(error, 'reason', error)}") from None
    resumed = start > 0 and getattr(response, "status", 200) == 206
    return response, resumed
