from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from inspect import iscoroutinefunction
from typing import Protocol

from backend.app.core.config import get_settings
from backend.app.tools.policy import ToolPolicy
from backend.app.tools.result import ToolErrorCode, ToolResult


class AsyncTool(Protocol):
    name: str

    async def ainvoke(self, input: Mapping[str, object]) -> object:
        ...


@dataclass(frozen=True, slots=True)
class _ToolRegistration:
    tool: AsyncTool
    requires_approval: bool


class ToolRegistry:
    def __init__(
        self,
        policy: ToolPolicy | None = None,
        *,
        timeout_seconds: float | None = None,
    ) -> None:
        settings = get_settings()
        self.policy = policy or ToolPolicy(settings)
        self.timeout_seconds = (
            settings.tool_timeout_seconds
            if timeout_seconds is None
            else timeout_seconds
        )
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        self._tools: dict[str, _ToolRegistration] = {}

    @property
    def tool_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))

    def register(
        self,
        tool: AsyncTool,
        *,
        requires_approval: bool = False,
    ) -> None:
        name = getattr(tool, "name", None)
        invoke = getattr(tool, "ainvoke", None)
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Registered tools must have a non-empty name")
        if name != name.strip():
            raise ValueError("Registered tool names cannot have surrounding whitespace")
        if not callable(invoke) or not iscoroutinefunction(invoke):
            raise TypeError(f"Tool {name!r} must provide async ainvoke")
        if name in self._tools:
            raise ValueError(f"Tool {name!r} is already registered")
        self._tools[name] = _ToolRegistration(tool, requires_approval)

    async def execute(
        self,
        name: str,
        args: Mapping[str, object],
        *,
        approved: bool = False,
    ) -> ToolResult:
        registration = self._tools.get(name)
        requires_approval = self.policy.requires_approval(
            name,
            args,
            registered=registration is not None,
            declared_requires_approval=(
                registration.requires_approval
                if registration is not None
                else False
            ),
        )
        if requires_approval and not approved:
            return ToolResult.failure(
                name,
                ToolErrorCode.APPROVAL_REQUIRED,
                f"Tool {name!r} requires approval before execution",
                requires_approval=True,
            )
        if registration is None:
            return ToolResult.failure(
                name,
                ToolErrorCode.UNKNOWN_TOOL,
                f"Tool {name!r} is not registered",
                requires_approval=True,
            )

        try:
            output = await asyncio.wait_for(
                registration.tool.ainvoke(dict(args)),
                timeout=self.timeout_seconds,
            )
        except TimeoutError:
            return ToolResult.failure(
                name,
                ToolErrorCode.TIMEOUT,
                f"Tool execution exceeded {self.timeout_seconds:g} seconds",
            )
        # Tool failures must be returned to the workflow as explicit results.
        except Exception as exc:  # noqa: BLE001
            return ToolResult.failure(
                name,
                ToolErrorCode.EXECUTION_FAILED,
                f"Tool execution failed ({type(exc).__name__})",
            )

        return ToolResult(ok=True, tool_name=name, output=output)
