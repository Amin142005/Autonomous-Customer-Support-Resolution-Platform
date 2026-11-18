from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ToolErrorCode(StrEnum):
    APPROVAL_REQUIRED = "approval_required"
    UNKNOWN_TOOL = "unknown_tool"
    TIMEOUT = "timeout"
    EXECUTION_FAILED = "execution_failed"


@dataclass(frozen=True, slots=True)
class ToolResult:
    ok: bool
    tool_name: str
    output: object | None = None
    error_code: ToolErrorCode | None = None
    error: str | None = None
    requires_approval: bool = False

    @classmethod
    def failure(
        cls,
        tool_name: str,
        error_code: ToolErrorCode,
        error: str,
        *,
        requires_approval: bool = False,
    ) -> ToolResult:
        return cls(
            ok=False,
            tool_name=tool_name,
            error_code=error_code,
            error=error,
            requires_approval=requires_approval,
        )
