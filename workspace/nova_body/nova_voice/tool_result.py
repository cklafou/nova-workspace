# @nova: Preserve explicit tool outcomes, operation identity and execution environment alongside their text view.
# Last updated: 2026-10-04 14:28:11
"""Explicit tool outcomes, with a string-compatible view for older faculties."""
from __future__ import annotations

import uuid


class ToolResult(str):
    """Text is presentation; status is evidence. Never infer success from output text.

    Legacy tools remain usable, but an untyped return has unknown status until its
    adapter supplies an outcome. This also avoids treating a file containing ERROR
    as a failed read. The str base preserves authored tools' existing contracts.
    """

    def __new__(cls, text="", *, status="succeeded", exit_code=None, stdout="",
                stderr="", operation_id=None, duration_ms=0, artifacts=(), environment=None):
        if status not in {"succeeded", "failed", "refused", "timed_out", "cancelled", "unknown"}:
            raise ValueError(f"Invalid tool status: {status}")
        obj = super().__new__(cls, str(text))
        obj.status, obj.exit_code = status, exit_code
        obj.stdout, obj.stderr = stdout, stderr
        obj.operation_id = operation_id or uuid.uuid4().hex
        obj.duration_ms = duration_ms
        obj.artifacts = list(artifacts)
        obj.environment = dict(environment or {})
        obj.run_id = None
        return obj

    @property
    def ok(self):
        return None if self.status == "unknown" else self.status == "succeeded"

    def to_dict(self, limit=12000):
        return {
            "schema_version": 1, "operation_id": self.operation_id,
            "run_id": self.run_id,
            "status": self.status, "ok": self.ok, "exit_code": self.exit_code,
            "stdout": self.stdout[:limit], "stderr": self.stderr[:limit],
            "output_truncated": len(self.stdout) > limit or len(self.stderr) > limit,
            "timed_out": self.status == "timed_out", "cancelled": self.status == "cancelled",
            "duration_ms": round(self.duration_ms, 1), "artifacts": self.artifacts,
            "environment": dict(self.environment),
        }


def normalize_result(value):
    if isinstance(value, ToolResult):
        return value
    # Only a compatibility failure hint; no untyped output is proof of success.
    text = str(value)
    status = "unknown"
    if text.startswith(("ERROR", "[error]", "EXCEPTION:")):
        status = "failed"
    elif text.startswith(("REFUSED", "HELD")):
        status = "refused"
    return ToolResult(text, status=status)


def tool_event(tool, args, result, is_error=False, duration_ms=0):
    result = normalize_result(result)
    if is_error and result.ok is not False:
        result = ToolResult(str(result), status="failed", operation_id=result.operation_id)
    result.duration_ms = duration_ms
    return {"type": "tool_executed", "tool": tool, "input": args,
            "result": str(result)[:12000], "error": result.ok is False,
            "duration_ms": round(duration_ms), "outcome": result.to_dict()}
