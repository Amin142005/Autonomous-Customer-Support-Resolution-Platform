from backend.app.core.config import Settings
from backend.app.tools.policy import ToolPolicy


def test_unknown_tool_requires_approval():
    policy = ToolPolicy(Settings(_env_file=None))

    assert policy.requires_approval(
        "unregistered_action",
        {},
        registered=False,
    )


def test_declared_approval_requirement_cannot_be_overridden_by_policy():
    policy = ToolPolicy(Settings(_env_file=None))

    assert policy.requires_approval(
        "custom_write",
        {},
        registered=True,
        declared_requires_approval=True,
    )


def test_reset_demo_setting_always_requires_approval():
    policy = ToolPolicy(Settings(_env_file=None))

    assert policy.requires_approval(
        "reset_demo_setting",
        {},
        registered=True,
    )


def test_refunds_require_approval_by_default():
    policy = ToolPolicy(Settings(_env_file=None))

    assert policy.requires_approval(
        "create_refund_request",
        {"amount": 1},
        registered=True,
    )


def test_refund_threshold_applies_when_global_approval_is_disabled():
    policy = ToolPolicy(
        Settings(
            _env_file=None,
            approval_required_for_refunds=False,
            max_refund_without_approval=25,
        )
    )

    assert not policy.requires_approval(
        "create_refund_request",
        {"amount": "25"},
        registered=True,
    )
    assert policy.requires_approval(
        "create_refund_request",
        {"amount": "25.01"},
        registered=True,
    )


def test_missing_or_invalid_refund_amount_requires_approval():
    policy = ToolPolicy(
        Settings(
            _env_file=None,
            approval_required_for_refunds=False,
            max_refund_without_approval=25,
        )
    )

    for args in ({}, {"amount": "invalid"}, {"amount": True}, {"amount": -1}):
        assert policy.requires_approval(
            "create_refund_request",
            args,
            registered=True,
        )


def test_registered_read_tool_does_not_require_approval():
    policy = ToolPolicy(Settings(_env_file=None))

    assert not policy.requires_approval(
        "get_customer",
        {},
        registered=True,
    )
