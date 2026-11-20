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

TROUBLESHOOTING_PROMPT = (
    "Diagnose the support issue using only the ticket, cited evidence, customer "
    "context, and service status provided. Produce probable causes, hypotheses, "
    "numbered troubleshooting steps, root-cause assessment, and confidence. "
    "Do not invent incidents or claim an account-specific fact without evidence."
)

RESOLUTION_PROMPT = (
    "Create a concise support resolution plan using only the diagnosis and cited "
    "evidence provided. Produce a summary, customer-facing reply, internal notes, "
    "and grounded troubleshooting steps. Do not invent internal URLs, secrets, "
    "other customer data, or action arguments."
)

__all__ = [
    "SECURITY_PREAMBLE",
    "SUPERVISOR_CLASSIFICATION_PROMPT",
    "SUPERVISOR_SEVERITY_PROMPT",
    "SUPERVISOR_TICKET_SUMMARY_PROMPT",
    "TROUBLESHOOTING_PROMPT",
    "RESOLUTION_PROMPT",
]
