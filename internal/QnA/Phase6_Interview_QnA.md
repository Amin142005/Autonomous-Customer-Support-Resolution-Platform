# Phase 6 — Interview Questions and Answers

This question bank covers **Phase 6: Tools and policy**. The answers are written
for an interview, include beginner-friendly explanations, and distinguish
implemented behavior from later workflow and approval work.

Related reading:

- [Phase 6 plain-language explanation](../explain_codebase/phase6_explained.md)
- [Phase 6 system-design evolution](../design_evolution/Phase6_Project_System_Design_Evolution.md)
- [Phase 6 infrastructure evolution](../Infra_design_evolution/Phase6_Infra_design_evolution.md)
- [Phase 6 task status](../../TASK.md)
- [Phase 6 plan and exit criteria](../../PLAN_PHASE.md)

## 30-second overview

### 1. Can you summarize Phase 6?

**A:** “Phase 6 creates a safe action layer for CloudDesk. It separates read-only
tools from write tools, sends every action through a central asynchronous
registry, applies an approval policy, converts failures into consistent results,
and uses mock integrations so refunds, email, workspace changes, and status
checks do not reach real systems.”

### 2. What problem does Phase 6 solve?

**A:** “It prevents application and future AI workflow code from calling random
actions directly. Every action must be registered, policy-checked, timed, and
reported consistently.”

### 3. What are tools in this system?

**A:** “A tool is a named, validated operation the software can perform. Examples
are reading a customer, searching articles, updating a ticket, resetting a
workspace setting, or creating a refund request.”

### 4. Which four subtasks make up Phase 6?

**A:** “P6-1 adds the tool registry and policy. P6-2 adds read-only support tools.
P6-3 adds approval-gated write tools. P6-4 adds mock integration adapters.”

### 5. Does Phase 6 run the complete AI support workflow?

**A:** “No. It establishes the safe action components that the future LangGraph
workflow can use.”

### 6. Does Phase 6 issue real refunds or send real email?

**A:** “No. Refunds and email are mocked. A refund is marked as simulated, and
the email adapter only records a count.”

### 7. Does Phase 6 contain a human approval screen?

**A:** “No. It contains the policy and the `approved` execution flag. A later
phase creates approval records, interrupts, and the human approval API and UI.”

### 8. Why is the phase important for an AI system?

**A:** “AI output should not directly control consequential systems. The registry
gives the application deterministic registration and approval boundaries even
if a model requests an action.”

### 9. What is the main architectural principle?

**A:** “Separate registration and execution, approval policy, tool behavior,
database access, and external integration adapters. Each component has one main
responsibility.”

### 10. What is the Phase 6 execution path?

**A:** “The caller requests a tool by name with arguments. The registry looks it
up, asks the policy for approval, blocks or permits the call, invokes the async
tool with a timeout, and returns a `ToolResult`.”

## Tool registry

### 11. What does `ToolRegistry` do?

**A:** “It stores registered tools, validates registration, sends execution
requests through the policy, runs tools asynchronously, applies a timeout, and
returns success or explicit failure results.”

### 12. Why use a registry instead of calling tools directly?

**A:** “A registry creates one entry point for unknown-tool handling, approval,
timeouts, exception handling, and consistent results. Direct calls would allow
different parts of the application to bypass those controls.”

### 13. How are tools registered?

**A:** “Registration receives a LangChain `BaseTool`-compatible object and an
optional `requires_approval` flag. The registry validates the name and async
`ainvoke()` method, then stores the registration.”

### 14. What does async execution mean here?

**A:** “The tool is awaited instead of running synchronously. It does not block
the event loop during waiting and can be combined with FastAPI or future
workflow operations.”

### 15. How does the registry validate registration?

**A:** “It rejects empty or whitespace-surrounded names, non-async tools,
missing `ainvoke()` implementations, and duplicate names.”

### 16. Does the registry permit a tool with a name but no implementation?

**A:** “No. Unknown or unregistered names are not invoked. With approval, an
unknown tool still receives `UNKNOWN_TOOL`; without approval it returns
`APPROVAL_REQUIRED` first.”

### 17. Why does the unknown-tool policy require approval?

**A:** “Fail-safe policy is important. Because the application cannot verify an
unregistered action, it does not silently permit or execute it.”

### 18. What happens after unknown-tool approval is supplied?

**A:** “The registry checks approval and then checks registration again. If no
registration exists, it returns `UNKNOWN_TOOL`; it does not invoke anything.”

### 19. Why is timeout configuration useful?

**A:** “An external or internal operation may hang. A timeout lets the workflow
receive a failure and continue with its own recovery or escalation logic.”

### 20. Where does the timeout come from?

**A:** “It comes from `TOOL_TIMEOUT_SECONDS` in settings. The registry rejects
zero or negative timeout values.”

### 21. How is timeout implemented?

**A:** “The registry wraps `await tool.ainvoke(...)` in `asyncio.wait_for(...)`.
If the timeout expires, it returns a timeout `ToolResult`.”

### 22. What happens if a tool raises an exception?

**A:** “The registry converts the exception into `EXECUTION_FAILED`. It does not
expose the original exception message, helping prevent secrets or internal text
from reaching callers.”

### 23. Does tool failure crash the workflow?

**A:** “No. A failure becomes an explicit `ToolResult` that the workflow can
inspect and handle.”

### 24. What fields does `ToolResult` contain?

**A:** “It contains success status, tool name, optional output, optional error
code, optional error text, and whether approval is required.”

### 25. What error codes exist?

**A:** “Approval required, unknown tool, timeout, and execution failed.”

## Tool policy

### 26. What is `ToolPolicy` responsible for?

**A:** “It decides whether a tool call needs human approval. It receives the tool
name, arguments, registration state, and declared approval requirement.”

### 27. Is the policy separate from the registry?

**A:** “Yes. The registry owns registration and execution; the policy owns the
approval decision.”

### 28. Why is that separation useful?

**A:** “It allows approval rules to change independently from invocation,
timeout, or result handling.”

### 29. Which tools always require approval?

**A:** “Unknown tools and `reset_demo_setting` always require approval. Refund
approval depends on configuration and amount, with default approval required.”

### 30. Can a declared approval requirement be overridden?

**A:** “No. A tool registered with `requires_approval=True` remains
approval-required.”

### 31. Why does `reset_demo_setting` always require approval?

**A:** “It changes workspace configuration. Even as a mock operation, it
represents an account-administration action that must have a human gate.”

### 32. What is the default refund policy?

**A:** “`APPROVAL_REQUIRED_FOR_REFUNDS=true` in the demo, so every refund request
requires approval.”

### 33. How does the refund threshold work?

**A:** “If global refund approval is disabled, the policy parses the amount and
compares it with `MAX_REFUND_WITHOUT_APPROVAL`. Amounts above the threshold
need approval.”

### 34. What happens to invalid refund amounts?

**A:** “Missing amounts, booleans, invalid strings, negative amounts, and
non-finite values require approval. They are never silently processed.”

### 35. Why use `Decimal` instead of a float for refunds?

**A:** “Decimal avoids binary floating-point rounding surprises in money
calculations. It gives exact decimal input and supports finite and positive
checks.”

### 36. Does approval happen only at the tool layer?

**A:** “No. Tool policy is a safety guard, but later approval APIs and audit
records provide the human decision and traceability.”

## Read-only tools

### 37. What is P6-2 responsible for?

**A:** “P6-2 creates registered tools that gather context without changing support
records.”

### 38. What read-only tools exist?

**A:** “`get_customer`, `get_subscription`, `get_ticket_history`, `search_docs`,
and `check_service_status`.”

### 39. What does `get_customer` return?

**A:** “It returns an existing customer's basic support profile, such as ID,
name, email, company, and plan.”

### 40. What does `get_subscription` return?

**A:** “It returns subscription records for a customer, including plan, status,
seat count, and price when available.”

### 41. What does `get_ticket_history` return?

**A:** “It returns prior ticket summaries for a customer. The implementation
supports limits, offsets, and excluding the current ticket.”

### 42. Why does ticket history exclude raw bodies?

**A:** “The tool is meant for support context. It avoids unnecessarily exposing
the original customer message body while still providing useful ticket
summaries.”

### 43. How does `search_docs` work?

**A:** “It builds a knowledge search request and calls the existing Phase 5
knowledge service. It returns evidence with snippets and citations.”

### 44. How does `check_service_status` work?

**A:** “It asks the service-status integration for a named service and returns
the state, summary, and incident IDs.”

### 45. Are read-only tools completely risk-free?

**A:** “They do not intentionally write, but they still validate IDs and query
scope so the caller cannot read the wrong customer or an excessive page.”

### 46. How is customer data isolated by the history tool?

**A:** “The repository query begins with the supplied customer ID and can exclude
a single ticket. It does not search all tickets and remove other customers
afterward.”

## Write tools

### 47. What is P6-3 responsible for?

**A:** “P6-3 creates tools that change ticket metadata or represent consequential
actions: `update_ticket`, `reset_demo_setting`, and `create_refund_request`.”

### 48. What fields can `update_ticket` change?

**A:** “Status, summary, category, severity, subject, and assignee. It does not
replace the original ticket body.”

### 49. Does `update_ticket` require approval?

**A:** “No policy approval requirement is declared for it in P6-3. It is still
executed through the registry and validates one or more supported fields.”

### 50. Why does `update_ticket` validate enum values?

**A:** “It converts values through `TicketStatus`, `Category`, and `Severity`
schemas. Invalid values are not stored.”

### 51. What happens if a ticket is missing?

**A:** “The tool raises `LookupError`, and the registry converts it into an
`EXECUTION_FAILED` result.”

### 52. What does `reset_demo_setting` do?

**A:** “It calls the mock workspace-admin integration to reset a named setting
to a supplied default value.”

### 53. When can `reset_demo_setting` execute?

**A:** “Only after the registry receives `approved=True`. Without approval, the
tool implementation is never invoked.”

### 54. What does `create_refund_request` do?

**A:** “It validates customer ID, reason, and a positive finite amount, converts
the amount to Decimal, and calls the mock billing integration.”

### 55. How is the refund returned?

**A:** “The result includes a mock request ID, customer ID, amount, status, and
a `simulated` flag.”

### 56. Can P6-3 change real money?

**A:** “No. It can only create a mock refund receipt.”

## Mock integrations

### 57. What is P6-4 responsible for?

**A:** “P6-4 creates integration contracts and mock implementations for billing,
email, service status, and workspace administration.”

### 58. What is an integration protocol?

**A:** “It is a Python `Protocol` that defines the methods and result types a
concrete adapter must provide.”

### 59. Why use protocols?

**A:** “Protocols decouple tools from vendor-specific implementations. A real
adapter can replace a mock while keeping the same tool interface.”

### 60. What adapters exist in the mock bundle?

**A:** “Mock billing, mock email, mock service status, and mock workspace-admin
adapters.”

### 61. What does `IntegrationBundle` contain?

**A:** “It holds the billing, email, service-status, and workspace-admin
integration objects in one composition.”

### 62. What does `create_integrations()` do?

**A:** “It creates fresh mock objects and returns an `IntegrationBundle`. Separate
calls create isolated adapter instances.”

### 63. How does mock refund state work?

**A:** “The mock billing service keeps a list of simulated receipts in memory.
It rejects zero, negative, NaN, and infinite amounts.”

### 64. How does mock email work?

**A:** “It increments a simulated-message count and returns a simulated receipt.
It does not store or send the message body.”

### 65. How does mock service status work?

**A:** “It returns configured states by normalized service name. Unknown names
return `unknown`; identity is configured as degraded in the demo.”

### 66. How does mock workspace reset work?

**A:** “It validates workspace and setting names, updates an in-memory dictionary,
and returns a simulated reset result.”

### 67. Are mock states persistent?

**A:** “No. They disappear when the Python process restarts. They are useful for
tests and demos, not durable account records.”

### 68. Why use mocks in Phase 6?

**A:** “Mocks allow end-to-end tool behavior to be developed and tested offline
without credentials or real financial, email, or account systems.”

## Architecture and layering

### 69. How do tools fit the repository architecture?

**A:** “Tools remain in `backend/app/tools/`, repositories remain responsible for
SQL, and integrations remain under `integrations/`. Tools compose those
boundaries instead of bypassing them.”

### 70. Do tools contain direct SQL?

**A:** “The read-only and write tool implementations open sessions and use
repositories. They do not embed SQL statements directly.”

### 71. Do integrations import core or agents?

**A:** “The mock integration implementation should remain independent of core
or agent internals. Tools and composition code connect integration objects to
the registry.”

### 72. What is dependency injection in this phase?

**A:** “The tool builders receive the session factory and integration bundle
from their callers. Tests can provide an in-memory database and fresh mocks
instead of production dependencies.”

### 73. Why is `@tool` used?

**A:** “It wraps async Python functions as LangChain tools with a name and
docstring description. That makes the operations visible to future LangChain
or MCP clients.”

### 74. Why are docstrings important?

**A:** “The docstring describes the tool to the model and future MCP clients.
It should explain the purpose clearly without treating ticket text as an
instruction.”

### 75. What is a tool description separate from implementation?

**A:** “The description tells a caller what the tool is for. The implementation
and policy determine what it actually validates and may change.”

## Safety and failure handling

### 76. Where is approval checked?

**A:** “It is checked in `ToolRegistry.execute()` through `ToolPolicy` before
the registered implementation is invoked.”

### 77. How does the system prevent approval bypass?

**A:** “The implementation is only invoked after the policy returns not
approval-required or the caller supplies `approved=True`. Direct mock
integration calls bypass the registry in application code, so application
actions must remain on the registered path.”

### 78. What should a future approval API do before setting `approved=True`?

**A:** “It should verify the user's role, identify the specific pending action,
record the decision and approver, and only then resume the shared tool path
with approval.”

### 79. What is sanitized error handling?

**A:** “It means errors report a safe category or exception type instead of
raw messages that might contain API keys or internal details.”

### 80. Why do tool failures need `ToolResult` instead of exceptions?

**A:** “A workflow may need to decide whether to retry, escalate, or report
failure. `ToolResult` gives it structured control data instead of an unexpected
exception.”

### 81. What is fail-safe behavior for unknown tools?

**A:** “Do not infer intent and do not execute. Require approval and, if
approved, return `UNKNOWN_TOOL` clearly.”

### 82. What prevents a tool from running indefinitely?

**A:** “The registry's configured `asyncio.wait_for()` timeout.”

### 83. What prevents real actions during the demo?

**A:** “Mock integrations are the concrete implementations. Real billing, email,
and account provider adapters are not implemented in Phase 6.”

### 84. What should never be returned from tool exceptions?

**A:** “Raw exception text containing secrets, API keys, passwords, card data,
ticket bodies, or other customer information.”

## Testing and validation

### 85. How is the registry tested?

**A:** “Tests use fake async tools to verify execution, approval blocking,
declared approval, unknown tools, duplicate registration, invalid async
implementations, timeout, and exception results.”

### 86. How are read-only tools tested?

**A:** “Tests create an in-memory SQLite database, register the tools, and verify
customer profiles, subscriptions, ticket-history filtering, knowledge evidence,
service status, missing records, and unchanged records.”

### 87. How are write tools tested?

**A:** “Tests verify registration names, ticket updates, missing-ticket failures,
workspace-reset blocking and approval, and approved mock refund behavior.”

### 88. How are mock integrations tested?

**A:** “Tests verify isolated adapter instances, simulated receipts, invalid
refund amounts, workspace setting changes, unknown service states, and the
email adapter's lack of real sending.”

### 89. What is the current focused test result?

**A:** “The 24 write-tool, tool-policy, and tool-registry tests passed locally.
Ruff also passed for the changed write-tool and test files.”

### 90. Did Phase 6 use Docker or cloud services in validation?

**A:** “No. Validation used in-memory SQLite, fake or mock integrations, and
local pytest. No Docker service or cloud credential was required.”

## Honest status and common comparisons

### 91. Is the ToolRegistry mounted in FastAPI startup?

**A:** “Not yet. It is constructed directly in tests or can be composed by future
workflow code. Phase 6 does not add a tool HTTP route or `app.state` registry.”

### 92. Is Docker networking implemented?

**A:** “No. The repository has no Dockerfile or Compose configuration in this
phase. Tool components run in the Python process and mock state remains local.”

### 93. What does registry approval differ from RBAC?

**A:** “RBAC decides which user role may request an action. Tool policy decides
which action is consequential and requires approval. Both can be used together.”

### 94. What does tool policy differ from guardrails?

**A:** “Phase 6 policy decides whether an action may execute based on registration
and configuration. Later guardrails will defend against prompt injection and
unsafe output. They address different risks.”

### 95. What is the difference between a mock and a real integration adapter?

**A:** “Both implement the same protocol, but a mock changes local demo state
and never reaches a vendor. A real adapter would call an external system and
require credentials, retries, and production security.”

### 96. What is the difference between `update_ticket` and `reset_demo_setting`?

**A:** “`update_ticket` changes database metadata and has no P6 approval gate.
`reset_demo_setting` changes an account-style setting and always requires
approval.”

### 97. What is the difference between read-only and write tools?

**A:** “Read-only tools gather context and should not change state. Write tools
change database or integration state and receive stricter policy checks.”

### 98. What should be added before Phase 6 is connected to production?

**A:** “A real persisted approval workflow, role authorization, audit records,
real integration credentials, retry and idempotency behavior, secrets
management, and container or worker deployment.”

### 99. What is the Phase 6 exit criterion?

**A:** “Every tool must be asynchronous and registered, consequential actions
must require approval, failures must return explicit `ToolResult` failures,
and the demo must work through mocks without real email, refunds, or account
changes.”

### 100. What is the strongest one-sentence interview answer for Phase 6?

**A:** “Phase 6 adds a controlled tool-execution architecture: read-only and write
tools register behind a central async registry, policy gates consequential
actions before side effects, failures are explicit, and mock integrations keep
the complete flow offline and safe.”
