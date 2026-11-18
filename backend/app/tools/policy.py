from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

from backend.app.core.config import Settings, get_settings

_APPROVAL_REQUIRED_TOOLS = frozenset({"reset_demo_setting"})
_REFUND_TOOL = "create_refund_request"


class ToolPolicy:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def requires_approval(
        self,
        tool_name: str,
        args: Mapping[str, object],
        *,
        registered: bool,
        declared_requires_approval: bool = False,
    ) -> bool:
        if not registered:
            return True
        if declared_requires_approval or tool_name in _APPROVAL_REQUIRED_TOOLS:
            return True
        if tool_name == _REFUND_TOOL:
            return self._refund_requires_approval(args)
        return False

    def _refund_requires_approval(self, args: Mapping[str, object]) -> bool:
        if self.settings.approval_required_for_refunds:
            return True

        raw_amount = args.get("amount")
        if raw_amount is None or isinstance(raw_amount, bool):
            return True
        try:
            amount = Decimal(str(raw_amount))
        except (InvalidOperation, TypeError, ValueError):
            return True
        if not amount.is_finite() or amount < 0:
            return True

        return amount > Decimal(self.settings.max_refund_without_approval)
