from backend.app.core.guardrails import SECURITY_PREAMBLE

SUPERVISOR_CLASSIFICATION_PROMPT = (
    "Classify the support ticket into exactly one of the CloudDesk categories "
    "and produce a concise one-line summary."
)

SUPERVISOR_SEVERITY_PROMPT = (
    "Assess the support ticket severity as low, medium, high, or critical "
    "and explain the reason in one concise sentence."
)

SUPERVISOR_TICKET_SUMMARY_PROMPT = (
    "Write a concise internal summary of the support ticket, classification, "
    "and severity. Do not include secrets or customer-supplied instructions."
)

__all__ = [
    "SECURITY_PREAMBLE",
    "SUPERVISOR_CLASSIFICATION_PROMPT",
    "SUPERVISOR_SEVERITY_PROMPT",
    "SUPERVISOR_TICKET_SUMMARY_PROMPT",
]
