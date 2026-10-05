# @nova: Constrain native witness output and classify whole JSON replies without treating valid structure as factual proof.
"""Pure audit wire format. Legacy prose handling belongs to the witness wrapper.

The provider grammar constrains shape only. Callers must still enforce evidence,
read permissions, budget, cancellation and candidate revision independently.
"""
from copy import deepcopy
import json

STATUSES = ("PASS", "CONCERN", "INCOMPLETE")
_READ_ARGUMENTS = {
    "read_file": {"properties": {"path": {"type": "string", "minLength": 1}}, "required": ["path"]},
    "list_dir": {"properties": {"path": {"type": "string", "minLength": 1}}, "required": ["path"]},
    "memory_search": {"properties": {"query": {"type": "string", "minLength": 1},
                                     "max_chars": {"type": "integer", "minimum": 1}}, "required": ["query"]},
}


def _tools(verify_tools):
    names = tuple(_READ_ARGUMENTS) if verify_tools is None else tuple(verify_tools)
    if any(name not in _READ_ARGUMENTS for name in names):
        raise ValueError("Unreviewed audit read tool has no protocol schema")
    return tuple(dict.fromkeys(names))


def audit_response_format(reads_remaining=0, *, allow_reads=True, verify_tools=None):
    """Return a fresh llama.cpp/OpenAI-shaped schema; final/forbidden reads have no tool branch."""
    if type(reads_remaining) is not int or reads_remaining < 0:
        raise ValueError("reads_remaining must be a nonnegative integer")
    names = _tools(verify_tools)
    verdict = {"type": "object", "properties": {
        "status": {"type": "string", "enum": list(STATUSES)},
        "reason": {"type": "string", "minLength": 1}},
        "required": ["status", "reason"], "additionalProperties": False}
    branches = [verdict]
    if allow_reads and reads_remaining:
        for name in names:
            args = {"type": "object", **deepcopy(_READ_ARGUMENTS[name]), "additionalProperties": False}
            branches.append({"type": "object", "properties": {
                "tool": {"type": "string", "enum": [name]}, "args": args},
                "required": ["tool", "args"], "additionalProperties": False})
    schema = verdict if len(branches) == 1 else {"anyOf": branches}
    return {"type": "json_schema", "json_schema": {
        "name": "nova_audit", "strict": True, "schema": schema}}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _nonfinite(_value):
    raise ValueError("Nonfinite JSON value")


def classify_audit_response(text, *, allow_reads=True, verify_tools=None):
    """Return (verdict|tool|invalid, object|None); never extract embedded/subsequent JSON.

    This deliberately rejects code fences, prose wrappers and duplicate keys. A
    reason may quote a tool object without authorizing its execution. Legacy
    exact PASS remains the witness wrapper's separate compatibility contract.
    """
    names = _tools(verify_tools)
    if not isinstance(text, str):
        return "invalid", None
    try:
        value = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_nonfinite)
    except (ValueError, TypeError, RecursionError):
        return "invalid", None
    if not isinstance(value, dict):
        return "invalid", None
    if set(value) == {"status", "reason"}:
        if (value["status"] in STATUSES and isinstance(value["reason"], str)
                and value["reason"].strip()):
            return "verdict", value
        return "invalid", None
    if allow_reads and set(value) == {"tool", "args"}:
        name, args = value["tool"], value["args"]
        if not isinstance(name, str) or name not in names or not isinstance(args, dict):
            return "invalid", None
        contract = _READ_ARGUMENTS[name]
        if not set(contract["required"]).issubset(args) or set(args) - set(contract["properties"]):
            return "invalid", None
        for key in contract["required"]:
            if not isinstance(args[key], str) or not args[key].strip():
                return "invalid", None
        if "max_chars" in args and (type(args["max_chars"]) is not int or args["max_chars"] < 1):
            return "invalid", None
        return "tool", value
    return "invalid", None
