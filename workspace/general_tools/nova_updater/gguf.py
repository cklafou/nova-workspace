# @nova: Reads GGUF file headers (architecture, name, adapter and base-model keys) without loading tensors, so installed files can be identified fast.
"""Minimal GGUF metadata reader (spec v2/v3).

Reads the key/value header only and stops before the tokenizer's huge arrays, so a 24 GB model
is identified in milliseconds. Arrays are summarised unless they are tiny.
"""
from __future__ import annotations

import struct

MAGIC = b"GGUF"
_SCALARS = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f", 7: "<?", 10: "<Q", 11: "<q", 12: "<d"}
STRING, ARRAY = 8, 9
MAX_STRING = 1 << 20
MAX_KEYS = 4096


class GGUFError(Exception):
    pass


def _read(handle, n: int) -> bytes:
    data = handle.read(n)
    if len(data) != n:
        raise GGUFError("file ended inside the header")
    return data


def _string(handle) -> str:
    (length,) = struct.unpack("<Q", _read(handle, 8))
    if length > MAX_STRING:
        raise GGUFError("implausible string length in header")
    return _read(handle, length).decode("utf-8", "replace")


def _skip_string(handle) -> None:
    (length,) = struct.unpack("<Q", _read(handle, 8))
    handle.seek(length, 1)


def _value(handle, kind: int, keep_arrays: int):
    if kind in _SCALARS:
        fmt = _SCALARS[kind]
        return struct.unpack(fmt, _read(handle, struct.calcsize(fmt)))[0]
    if kind == STRING:
        return _string(handle)
    if kind == ARRAY:
        (item_kind,) = struct.unpack("<I", _read(handle, 4))
        (count,) = struct.unpack("<Q", _read(handle, 8))
        if count <= keep_arrays:
            return [_value(handle, item_kind, keep_arrays) for _ in range(count)]
        if item_kind in _SCALARS:
            handle.seek(struct.calcsize(_SCALARS[item_kind]) * count, 1)
        elif item_kind == STRING:
            for _ in range(count):
                _skip_string(handle)
        else:
            for _ in range(count):
                _value(handle, item_kind, 0)
        return {"array_of": item_kind, "length": count}
    raise GGUFError(f"unknown value type {kind}")


def read_metadata(path, stop_prefixes=("tokenizer.ggml.tokens", "tokenizer.ggml.merges"),
                  keep_arrays: int = 16) -> dict:
    """Return header metadata. `_tensor_count`, `_version` describe the file itself."""
    with open(path, "rb") as handle:
        if _read(handle, 4) != MAGIC:
            raise GGUFError("not a GGUF file")
        (version,) = struct.unpack("<I", _read(handle, 4))
        if version < 2:
            raise GGUFError(f"GGUF v{version} is too old to read")
        tensor_count, kv_count = struct.unpack("<QQ", _read(handle, 16))
        if kv_count > MAX_KEYS:
            raise GGUFError("implausible key count")
        meta = {"_version": version, "_tensor_count": tensor_count, "_kv_count": kv_count}
        for _ in range(kv_count):
            key = _string(handle)
            (kind,) = struct.unpack("<I", _read(handle, 4))
            if any(key.startswith(prefix) for prefix in stop_prefixes):
                meta["_truncated_at"] = key
                break
            meta[key] = _value(handle, kind, keep_arrays)
        return meta


def classify(meta: dict) -> str:
    """'lora', 'projector' or 'model'."""
    general_type = str(meta.get("general.type", "")).lower()
    if general_type == "adapter" or "adapter.type" in meta:
        return "lora"
    if general_type in ("mmproj", "clip") or meta.get("general.architecture") == "clip":
        return "projector"
    return "model"


def base_model(meta: dict) -> dict | None:
    """The base a LoRA was trained against, when the converter recorded it."""
    if not meta.get("general.base_model.count"):
        return None
    return {"name": meta.get("general.base_model.0.name"), "organization": meta.get("general.base_model.0.organization"),
            "repo_url": meta.get("general.base_model.0.repo_url"), "version": meta.get("general.base_model.0.version")}


def write_minimal(path, kv: dict, version: int = 3) -> None:
    """Write a tiny GGUF with only metadata (tests and fixtures). Strings and ints supported."""
    def string(text: str) -> bytes:
        raw = text.encode("utf-8")
        return struct.pack("<Q", len(raw)) + raw

    body = bytearray()
    for key, value in kv.items():
        body += string(key)
        if isinstance(value, bool):
            body += struct.pack("<I", 7) + struct.pack("<?", value)
        elif isinstance(value, int):
            body += struct.pack("<I", 4) + struct.pack("<I", value)
        elif isinstance(value, float):
            body += struct.pack("<I", 6) + struct.pack("<f", value)
        elif isinstance(value, list):
            body += struct.pack("<I", ARRAY) + struct.pack("<I", STRING) + struct.pack("<Q", len(value))
            for item in value:
                body += string(str(item))
        else:
            body += struct.pack("<I", STRING) + string(str(value))
    with open(path, "wb") as handle:
        handle.write(MAGIC + struct.pack("<I", version) + struct.pack("<QQ", 0, len(kv)) + bytes(body))
