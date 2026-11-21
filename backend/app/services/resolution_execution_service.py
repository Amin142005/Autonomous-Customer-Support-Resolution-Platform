from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from agents.tracer import WorkflowTracer
from backend.app.models.entities import ResolutionAction
from backend.app.repositories.workflow import ResolutionActionRepository
from backend.app.tools.result import ToolResult


class ResolutionExecutionService:
    """Execute deterministic resolution proposals only through ToolRegistry."""

    def __init__(
        self,
        session: AsyncSession | None,
        registry: Any,
    ) -> None:
        self.session = session
        self.registry = registry
        self.actions = (
            ResolutionActionRepository(session)
            if session is not None
            else None
        )

    async def execute(
        self,
        *,
        ticket_id: str,
        workflow_id: str,
        proposals: list[Any] | list[Mapping[str, Any]],
        approval_status: str | None,
        approval_decided_by: str | None = None,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        approved = str(approval_status or "").casefold() in {
            "approved",
            "approve",
            "true",
            "yes",
        }

        tracer = (
            WorkflowTracer(
                self.session,
                ticket_id=ticket_id,
                workflow_id=workflow_id,
            )
            if self.session is not None
            else None
        )

        for proposal in proposals:
            if isinstance(proposal, Mapping):
                tool_name = str(proposal.get("tool", "")).strip()
                arguments = (
                    dict(proposal.get("arguments", {}))
                    if isinstance(proposal.get("arguments"), Mapping)
                    else {}
                )
                requires_approval = bool(proposal.get("approval_required", False))
                rationale = str(proposal.get("rationale", ""))
            else:
                tool_name = str(getattr(proposal, "tool", "")).strip()
                arguments = getattr(proposal, "arguments", {})
                if not isinstance(arguments, Mapping):
                    arguments = {}
                arguments = dict(arguments)
                requires_approval = bool(getattr(proposal, "approval_required", False))
                rationale = str(getattr(proposal, "rationale", ""))

            if not tool_name:
                continue

            if requires_approval and not approved:
                status = "approval_required"
                output: object | None = None
                result = None
                error = "Approval required before tool execution"
            else:
                try:
                    result = await self.registry.execute(
                        tool_name,
                        arguments,
                        approved=approved if requires_approval else False,
                    )
                except Exception as exc:  # noqa: BLE001
                    result = None
                    status = "failed"
                    output = None
                    error = type(exc).__name__
                else:
                    if isinstance(result, ToolResult):
                        if result.ok:
                            status = "completed"
                            output = result.output
                            error = None
                        else:
                            status = "failed"
                            output = None
                            error = result.error or result.error_code
                    else:
                        status = "completed"
                        output = result
                        error = None

            record = {
                "tool": tool_name,
                "arguments": arguments,
                "approval_required": requires_approval,
                "rationale": rationale,
                "status": status,
                "output": output,
                "error": error,
            }
            results.append(record)

            if tracer is not None:
                await tracer.record(
                    "tool_called",
                    node_name="execute_resolution",
                    payload={
                        "tool": tool_name,
                        "status": status,
                        "requires_approval": requires_approval,
                    },
                )

            if self.actions is not None:
                await self.actions.create(
                    ticket_id=ticket_id,
                    workflow_id=workflow_id,
                    tool_name=tool_name,
                    args=arguments,
                    status=status,
                    result=(
                        dict(output)
                        if isinstance(output, Mapping)
                        else (output if isinstance(output, (str, int, float, bool)) else None)
                    ),
                    approved_by=(
                        approval_decided_by
                        if requires_approval and approved
                        else None
                    ),
                )

        if self.session is not None:
            await self.session.flush()

        return results


__all__ = ["ResolutionExecutionService"]
