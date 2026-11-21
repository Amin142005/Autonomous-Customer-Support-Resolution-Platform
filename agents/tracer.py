from __future__ import annotations

import time
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator, Mapping
from enum import Enum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import WorkflowEvent


class WorkflowTracer:
    """Persist workflow telemetry without allowing telemetry failures to stop runs."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        ticket_id: str,
        workflow_id: str,
    ) -> None:
        self.session = session
        self.ticket_id = ticket_id
        self.workflow_id = workflow_id

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, Mapping):
            return {
                str(key): WorkflowTracer._json_safe(item)
                for key, item in value.items()
                if key not in {"prompt", "messages", "raw", "secrets"}
            }
        if isinstance(value, (list, tuple)):
            return [WorkflowTracer._json_safe(item) for item in value]
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        if hasattr(value, "model_dump"):
            try:
                dumped = value.model_dump(mode="json")
                return WorkflowTracer._json_safe(dumped)
            except Exception:
                return str(value)
        if hasattr(value, "as_dict"):
            try:
                dumped = value.as_dict()
                return WorkflowTracer._json_safe(dumped)
            except Exception:
                return str(value)
        if hasattr(value, "input_tokens"):
            return {
                "input_tokens": int(getattr(value, "input_tokens", 0) or 0),
                "output_tokens": int(getattr(value, "output_tokens", 0) or 0),
                "cost": float(getattr(value, "cost", 0.0) or 0.0),
            }
        return str(value)

    async def record(
        self,
        event_type: str,
        *,
        node_name: str | None = None,
        payload: Mapping[str, Any] | None = None,
        duration_ms: int | None = None,
        token_usage: Mapping[str, Any] | Any | None = None,
    ) -> WorkflowEvent | None:
        try:
            usage_payload = (
                self._json_safe(token_usage)
                if token_usage is not None
                else None
            )
            if usage_payload is not None and not isinstance(usage_payload, dict):
                usage_payload = None

            event = WorkflowEvent(
                ticket_id=self.ticket_id,
                workflow_id=self.workflow_id,
                event_type=event_type,
                node_name=node_name,
                payload=(
                    dict(self._json_safe(payload))
                    if isinstance(payload, Mapping)
                    else None
                ),
                duration_ms=max(0, int(duration_ms)) if duration_ms is not None else None,
                token_usage=usage_payload,
            )
            self.session.add(event)
            await self.session.flush()
            return event
        except Exception:
            return None

    async def node_started(self, node_name: str) -> WorkflowEvent | None:
        return await self.record("node_started", node_name=node_name)

    async def node_completed(
        self,
        node_name: str,
        *,
        duration_ms: int,
        payload: Mapping[str, Any] | None = None,
    ) -> WorkflowEvent | None:
        return await self.record(
            "node_completed",
            node_name=node_name,
            payload=payload,
            duration_ms=duration_ms,
        )

    async def tool_called(
        self,
        tool_name: str,
        *,
        node_name: str,
        duration_ms: int = 0,
    ) -> WorkflowEvent | None:
        return await self.record(
            "tool_called",
            node_name=node_name,
            payload={"tool": tool_name, "status": "observed"},
            duration_ms=duration_ms,
        )

    async def llm_called(
        self,
        *,
        node_name: str,
        usage: Any,
        duration_ms: int = 0,
    ) -> WorkflowEvent | None:
        return await self.record(
            "llm_called",
            node_name=node_name,
            payload={"status": "completed"},
            duration_ms=duration_ms,
            token_usage=usage,
        )

    async def error(
        self,
        node_name: str,
        payload: Mapping[str, Any],
    ) -> WorkflowEvent | None:
        return await self.record("error", node_name=node_name, payload=payload)

    async def workflow_completed(self) -> WorkflowEvent | None:
        return await self.record("workflow_completed", payload={"status": "completed"})

    @asynccontextmanager
    async def node(self, node_name: str) -> AsyncIterator[None]:
        started = time.monotonic()
        await self.node_started(node_name)
        try:
            yield
        except Exception as exc:
            await self.error(node_name, {"error": type(exc).__name__})
            raise
        else:
            duration_ms = int((time.monotonic() - started) * 1000)
            await self.node_completed(node_name, duration_ms=duration_ms)


__all__ = ["WorkflowTracer"]
