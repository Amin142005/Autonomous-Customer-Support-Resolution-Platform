import asyncio
from collections.abc import Mapping

import pytest

from backend.app.core.config import Settings
from backend.app.tools.policy import ToolPolicy
from backend.app.tools.registry import ToolRegistry
from backend.app.tools.result import ToolErrorCode


class FakeTool:
    def __init__(self, name, output=None, error=None, wait_seconds=0):
        self.name = name
        self.output = output
        self.error = error
        self.wait_seconds = wait_seconds
        self.calls = 0

    async def ainvoke(self, input: Mapping[str, object]) -> object:
        self.calls += 1
        if self.wait_seconds:
            await asyncio.sleep(self.wait_seconds)
        if self.error is not None:
            raise self.error
        return {"args": dict(input), "value": self.output}


def make_registry(*, timeout_seconds=1, **settings_values):
    settings = Settings(_env_file=None, **settings_values)
    return ToolRegistry(
        ToolPolicy(settings),
        timeout_seconds=timeout_seconds,
    )


async def test_registered_tool_executes_through_async_invoke():
    registry = make_registry()
    tool = FakeTool("get_customer", output={"id": "customer-1"})
    registry.register(tool)

    result = await registry.execute(
        "get_customer",
        {"customer_id": "customer-1"},
    )

    assert result.ok
    assert result.output == {
        "args": {"customer_id": "customer-1"},
        "value": {"id": "customer-1"},
    }
    assert tool.calls == 1


async def test_tool_requires_approval_before_any_side_effect():
    registry = make_registry()
    tool = FakeTool("reset_demo_setting")
    registry.register(tool)

    result = await registry.execute("reset_demo_setting", {"workspace_id": "w1"})

    assert not result.ok
    assert result.error_code == ToolErrorCode.APPROVAL_REQUIRED
    assert result.requires_approval
    assert tool.calls == 0


async def test_approved_tool_runs_through_the_same_registry_path():
    registry = make_registry()
    tool = FakeTool("reset_demo_setting", output="reset")
    registry.register(tool)

    result = await registry.execute(
        "reset_demo_setting",
        {"workspace_id": "w1"},
        approved=True,
    )

    assert result.ok
    assert result.output["value"] == "reset"
    assert tool.calls == 1


async def test_unknown_tool_requires_approval_and_is_never_invoked():
    registry = make_registry()

    approval = await registry.execute("not_registered", {})
    after_approval = await registry.execute(
        "not_registered",
        {},
        approved=True,
    )

    assert approval.error_code == ToolErrorCode.APPROVAL_REQUIRED
    assert approval.requires_approval
    assert after_approval.error_code == ToolErrorCode.UNKNOWN_TOOL
    assert after_approval.requires_approval


async def test_registered_tool_can_declare_approval_requirement():
    registry = make_registry()
    tool = FakeTool("custom_write")
    registry.register(tool, requires_approval=True)

    result = await registry.execute("custom_write", {})

    assert result.error_code == ToolErrorCode.APPROVAL_REQUIRED
    assert tool.calls == 0


async def test_refund_requires_approval_with_default_policy():
    registry = make_registry()
    tool = FakeTool("create_refund_request")
    registry.register(tool)

    result = await registry.execute(
        "create_refund_request",
        {"amount": 1},
    )

    assert result.error_code == ToolErrorCode.APPROVAL_REQUIRED
    assert tool.calls == 0


async def test_refund_below_configured_threshold_runs_without_approval():
    registry = make_registry(
        approval_required_for_refunds=False,
        max_refund_without_approval=25,
    )
    tool = FakeTool("create_refund_request", output="requested")
    registry.register(tool)

    result = await registry.execute(
        "create_refund_request",
        {"amount": 25},
    )

    assert result.ok
    assert tool.calls == 1


async def test_timeout_returns_explicit_failure_without_raising():
    registry = make_registry(timeout_seconds=0.01)
    tool = FakeTool("slow_tool", wait_seconds=0.1)
    registry.register(tool)

    result = await registry.execute("slow_tool", {})

    assert not result.ok
    assert result.error_code == ToolErrorCode.TIMEOUT
    assert "0.01 seconds" in result.error


async def test_tool_exception_returns_failure_without_exposing_exception_text():
    registry = make_registry()
    tool = FakeTool("failing_tool", error=ValueError("api_key=secret-value"))
    registry.register(tool)

    result = await registry.execute("failing_tool", {})

    assert not result.ok
    assert result.error_code == ToolErrorCode.EXECUTION_FAILED
    assert result.error == "Tool execution failed (ValueError)"
    assert "secret-value" not in result.error


def test_duplicate_registration_is_rejected():
    registry = make_registry()
    registry.register(FakeTool("get_customer"))

    with pytest.raises(ValueError, match="already registered"):
        registry.register(FakeTool("get_customer"))


def test_non_async_tool_is_rejected():
    class SyncTool:
        name = "sync_tool"

        def ainvoke(self, input):
            return input

    registry = make_registry()

    with pytest.raises(TypeError, match="async ainvoke"):
        registry.register(SyncTool())


def test_non_positive_timeout_is_rejected():
    with pytest.raises(ValueError, match="greater than zero"):
        make_registry(timeout_seconds=0)
