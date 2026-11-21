# Phase 10 — Interview Questions and Answers

This question bank covers **Phase 10: Workflow Graph and Trace**. The answers distinguish work implemented in P10-1 through P10-6 from later approval, action-execution, memory, and delivery work.

Related reading:

- [Phase 10 plain-language explanation](../explain_codebase/phase10_explained.md)
- [Phase 10 system-design evolution](../design_evolution/Phase10_Project_System_Design_Evolution.md)
- [Phase 10 infrastructure evolution](../Infra_design_evolution/Phase10_Infra_design_evolution.md)
- [Phase 10 task status](../../TASK.md)
- [Phase 10 plan](../../PLAN_PHASE.md)

## 30-second overview

### 1. Can you summarize Phase 10?

**A:** “Phase 10 turns the specialist agents into a persistent LangGraph workflow. It adds shared state, named graph nodes, conditional routing, workflow runs, status and events APIs, in-memory or SQLite checkpoints, and safe observability for the work performed.”

### 2. What problem did Phase 10 solve?

**A:** “The specialist agents existed individually in earlier phases, but the application needed one controlled order of execution, one shared state, a way to create and monitor runs, and an audit trail. Phase 10 provides that orchestration layer.”

### 3. What are the six Phase 10 subtasks?

**A:** “P10-1 adds workflow state and the checkpointer, P10-2 adds Supervisor nodes, P10-3 adds investigation nodes, P10-4 adds resolution and risk nodes, P10-5 wires the graph and run/status APIs, and P10-6 adds tracing and the events API.”

### 4. Is Phase 10 the complete support workflow?

**A:** “No. Phase 10 completes the graph shape, run lifecycle, risk routing, state persistence, and observability. The real approval interrupt, approval resume behavior, shared resolution action execution, and final memory update are later Phase 11 work.”

### 5. Did Docker networking change in Phase 10?

**A:** “No. Phase 10 is an in-process application and LangGraph implementation. Docker, Compose networking, worker processes, and containers belong to later delivery work.”

### 6. Which main technologies participate in Phase 10?

**A:** “FastAPI, SQLAlchemy, LangGraph, Pydantic workflow schemas, SQLite or PostgreSQL, and the existing specialist agents and tools.”

### 7. What is the main output of Phase 10?

**A:** “A support ticket can start a workflow run, move through named stages, save state and events, route to escalation or approval, and expose status and timeline information through the API.”

### 8. What is the strongest one-sentence Phase 10 summary?

**A:** “Phase 10 is the orchestration and observability layer that joins CloudDesk's specialists into a resumable workflow and makes every stage inspectable.”

## P10-1 — Workflow state and checkpointer

### 9. Where is the workflow state type defined?

**A:** “In `agents/state.py`, in the `SupportState` typed dictionary.”

### 10. What does `SupportState` contain?

**A:** “It carries the ticket and run identifiers, ticket and summary data, classification, severity, injection status, customer context, evidence, diagnosis, resolution, escalation, risk and approval fields, current node, completed nodes, errors, and token usage.”

### 11. Why use a shared state instead of passing every specialist result manually?

**A:** “Shared state gives LangGraph one workflow-wide case file. Each node reads what it needs and returns only the fields it changes, so the graph remains modular and repeatable.”

### 12. What is a partial state update?

**A:** “A node returns a dictionary containing only the fields it added or changed. LangGraph merges that update into the shared state instead of replacing the full state.”

### 13. Which state fields use append reducers?

**A:** “`completed_nodes` and `errors` use append-style reducers.”

### 14. What happens when a completed node appears more than once?

**A:** “The `append_unique` reducer keeps one copy of the node name, while preserving the order of distinct nodes.”

### 15. Why are errors accumulated instead of overwritten?

**A:** “Accumulation preserves the history of each failed or partial stage, so operators can understand all workflow errors instead of seeing only the latest one.”

### 16. How is token usage combined?

**A:** “The `merge_usage` reducer sums input tokens, output tokens, and estimated cost from node outputs.”

### 17. What is `LLMUsage`?

**A:** “It is a provider usage record containing input-token count, output-token count, and estimated cost.”

### 18. Why did the implementation handle both `LLMUsage` and `TokenUsage`?

**A:** “Specialist methods and the workflow state use slightly different usage representations. `merge_usage` normalizes both into the Pydantic `TokenUsage` model and then adds them.”

### 19. What is a checkpointer?

**A:** “It is LangGraph storage that preserves graph state for a thread, allowing a workflow to be inspected or resumed later.”

### 20. Where is checkpointer selection implemented?

**A:** “In `agents/checkpointer.py`, through `create_checkpointer()`.”

### 21. When does the system use `InMemorySaver`?

**A:** “It uses `InMemorySaver` when `CHECKPOINT_DB_PATH=:memory:`, which is the test and temporary in-memory mode.”

### 22. When does it use `AsyncSqliteSaver`?

**A:** “It uses `AsyncSqliteSaver` when the configured checkpoint path is a SQLite file.”

### 23. What is a LangGraph thread ID?

**A:** “It is the identifier used to associate graph execution and checkpoint history with one workflow run.”

### 24. How does Phase 10 map the thread ID to a workflow run?

**A:** “The workflow run ID is used as the thread ID and is saved on the `WorkflowRun` record.”

### 25. Are runtime objects placed in workflow state or checkpoints?

**A:** “No. Tool registries, AI providers, memory services, and other runtime objects are excluded from persisted state and checkpoints. The workflow service recreates or injects runtime dependencies for execution.”

### 26. Why are large documents avoided in reducer fields?

**A:** “Reducers may be called repeatedly and every snapshot can be persisted. Keeping large documents out of append or cumulative fields makes state smaller and avoids leaking or duplicating ticket data.”

### 27. What is the difference between a workflow run and a workflow checkpoint?

**A:** “The run is the application record in `workflow_runs` containing status and a JSON-safe state snapshot. The checkpoint is LangGraph execution state associated with a thread for graph resume behavior.”

## P10-2 — Supervisor graph nodes

### 28. Which graph nodes come from P10-2?

**A:** “`understand_ticket`, `classify_severity`, and `ticket_summary`."

### 29. What does `understand_ticket` return?

**A:** “Classification, prompt-injection status, completed-node state, current-node state, and token usage.”

### 30. What does `classify_severity` do?

**A:** “It reads the ticket and classification, calls the severity specialist, applies deterministic severity rules, combines injection information, and returns a severity assessment.”

### 31. Can policy lower a model's severity?

**A:** “No. Policy severity rules can raise a result but never lower it.”

### 32. What does `ticket_summary` do?

**A:** “It creates a concise internal summary from the ticket, classification, and severity.”

### 33. Why should the summary node come after classification and severity?

**A:** “The summary should reflect the category and risk already established, rather than treating the original free-form ticket as the only input.”

### 34. What happens if a Supervisor node raises an exception?

**A:** “The node returns a partial state update containing an error string and marks its own node complete, rather than allowing an unhandled exception to crash the graph.”

## P10-3 — Investigation graph nodes

### 35. Which graph nodes come from P10-3?

**A:** “`customer_context`, `knowledge_retrieval`, and `troubleshooting`."

### 36. What does `customer_context` load?

**A:** “Customer information, subscriptions, workspaces, previous tickets, and recalled memory notes.”

### 37. What tools does `customer_context` use?

**A:** “`get_customer`, `get_subscription`, `get_ticket_history`, and optionally `get_workspaces` when the registry exposes it.”

### 38. What does `knowledge_retrieval` return?

**A:** “Cited evidence and a list of similar previously resolved cases.”

### 39. What tools does knowledge retrieval use?

**A:** “The registered `search_docs` tool.”

### 40. How does troubleshooting receive evidence and context?

**A:** “The node passes the state’s evidence and `customer_context` to `TroubleshootingAgent.run()`.”

### 41. What does the diagnosis contain?

**A:** “Probable causes, hypotheses, numbered troubleshooting steps, service checks, an optional root cause, and confidence.”

### 42. What tool does troubleshooting use for service status?

**A:** “The registered `check_service_status` tool.”

### 43. What happens if a customer or knowledge tool fails?

**A:** “The specialist can return partial context or empty evidence, and the graph node records an error or continues safely based on the available information.”

### 44. How are investigation node failures represented in state?

**A:** “An error string is appended, the node is marked complete, and the current node is recorded.”

### 45. Why is this considered resilient behavior?

**A:** “The graph does not assume every dependency is available. It preserves the findings that did succeed and prevents one tool failure from becoming an unhandled service crash.”

## P10-4 — Resolution and risk nodes

### 46. Which graph nodes come from P10-4?

**A:** “`resolution_planning` and `risk_check`."

### 47. What does `resolution_planning` produce?

**A:** “A grounded summary, customer-facing reply, internal notes, troubleshooting steps, and deterministic action proposals.”

### 48. Does the resolution model invent tools?

**A:** “No. `ResolutionAgent.plan_actions()` deterministically proposes registered actions based on ticket text, category, and context.”

### 49. Which actions require approval in the current policy model?

**A:** “A refund request and a workspace setting reset can require approval. Ordinary ticket update actions do not.”

### 50. Where is customer output validated?

**A:** “The resolution specialist validates the reply against internal URLs, secrets, and cross-customer data through `validate_customer_output()`.”

### 51. What happens when customer output is invalid?

**A:** “The resolution agent uses a safe fallback reply, and `risk_check` identifies output validation failure as a high-risk condition.”

### 52. What is `risk_check` responsible for?

**A:** “It combines policy, severity, approval, injection, and output-validation signals into an overall routing risk level.”

### 53. When does risk become high?

**A:** “It becomes high for approval-required actions, policy escalation matches, critical severity, prompt injection, or customer-output validation failure.”

### 54. Does high risk always mean policy escalation?

**A:** “No. An approval-required action has approval routing, while an approval-free policy or critical-risk case routes to escalation.”

### 55. What is the medium-risk case in the current implementation?

**A:** “The routing logic uses medium risk for high severity when no stronger high-risk condition requires approval or escalation.”

### 56. What is the low-risk route?

**A:** “A low or ordinary ticket with no approval or policy condition routes to the execution path.”

### 57. Is resolution execution complete in P10-4?

**A:** “No. P10-4 only proposes resolution actions and calculates risk. P11 will add interrupts and shared tool execution.”

## P10-5 — Graph wiring and run API

### 58. Where is the LangGraph graph defined?

**A:** “In `agents/graph.py`.”

### 59. What is `GRAPH_NODES` used for?

**A:** “It provides a stable list of workflow node names for architecture metadata and future API/UI presentation.”

### 60. What is `GRAPH_EDGES` used for?

**A:** “It describes the named graph connections for architecture and UI metadata.”

### 61. What is the complete graph sequence?

**A:** “Supervisor understanding and severity, customer context, knowledge retrieval, troubleshooting, resolution planning, risk check, then escalation, approval, or execution, followed by ticket summary and memory update.”

### 62. What is `build_support_graph()`?

**A:** “It creates a `StateGraph`, registers all nodes and edges, adds conditional risk routing, and returns a compiled graph with an optional checkpointer.”

### 63. How does conditional routing work?

**A:** “`route_risk()` examines `escalation_required`, `approval_required`, and `risk_level`, then returns the next named route.”

### 64. Which route has the highest precedence?

**A:** “The implemented routing gives policy escalation precedence when `escalation_required` is true, then approval-required actions, then high-risk escalation, and finally low-risk execution.”

### 65. What are `human_approval`, `execute_resolution`, and `memory_update` in P10-5?

**A:** “They are placeholders or partial graph nodes. P11 and later memory integration complete their real behavior.”

### 66. What does `human_approval` currently do?

**A:** “In P10-5 it marks approval as pending and the workflow as paused so the graph shape is present. The actual interrupt and resume lifecycle is a P11 implementation.”

### 67. What does `execute_resolution` currently do?

**A:** “It marks the execution node complete but does not yet execute consequential tools. P11 provides the shared registry execution path.”

### 68. What does `memory_update` currently do?

**A:** “It marks the memory-update node complete in the P10 graph shape. The P11 or later memory phase supplies actual safe resolution recording.”

### 69. What endpoint starts a workflow?

**A:** “`POST /api/v1/tickets/{ticket_id}/run`."

### 70. What minimum role can start a workflow?

**A:** “An agent or administrator role; viewers cannot start a run.”

### 71. What does the run endpoint return?

**A:** “HTTP 202 Accepted and `{ "workflow_id": "<id>" }`."

### 72. Why is the start response immediate rather than waiting for completion?

**A:** “Workflow execution can involve several specialist calls and tools. FastAPI schedules it in a background task, then returns the workflow ID for polling.”

### 73. What creates the workflow run record?

**A:** “`WorkflowService.create_run()` creates a `WorkflowRun`, commits it, sets the ticket in progress, and initializes the run's thread identity.”

### 74. What status prevents a second run?

**A:** “A ticket already waiting on approval or a latest workflow in paused status prevents duplicate run creation with HTTP 409.”

### 75. What endpoint reads workflow status?

**A:** “`GET /api/v1/tickets/{ticket_id}/workflow`."

### 76. What roles can read status?

**A:** “Viewer, agent, and administrator roles.”

### 77. What does status include?

**A:** “Workflow ID, status, ticket ID, thread ID, and a JSON-safe workflow state snapshot.”

### 78. Where is graph execution started?

**A:** “`WorkflowService.start_workflow()` loads the run and ticket, creates the graph with a checkpointer, and streams graph values.”

### 79. How are graph values persisted?

**A:** “For each streamed dictionary update, `WorkflowService` writes a JSON-safe state snapshot to `workflow_runs.state`.”

### 80. What are JSON-safe runtime values?

**A:** “Pydantic models are serialized with `model_dump(mode='json')`, enums become values, mappings and sequences are converted recursively, and unsupported objects become strings or are omitted where appropriate.”

### 81. What runtime values are excluded from persisted state?

**A:** “Registry, tool registry, memory service, memory, and LLM objects.”

### 82. How does `resume_workflow()` work in the P10 shape?

**A:** “It is available as a service method and can invoke the compiled graph with `Command(resume=...)`, but the P11 approval routes own the production interrupt and decision lifecycle.”

### 83. What happens if `resume_workflow()` is called for a run that is not paused?

**A:** “The service raises a 409-style workflow conflict.”

### 84. Where is the workflow run background task registered?

**A:** “In the ticket API route through FastAPI `BackgroundTasks`."

### 85. Is the background task a separate worker process?

**A:** “No. Phase 10 runs it inside the FastAPI process.”

### 86. What happens after every graph update?

**A:** “The workflow service saves a JSON-safe state snapshot and updates the run status as running, paused, or completed based on state.”

### 87. What is an HTTP 202 response in this flow?

**A:** “It means the workflow run was accepted for processing, not that processing already completed.”

### 88. What is an HTTP 409 in workflow routing?

**A:** “It means a workflow conflict was found, such as starting a duplicate paused run or resuming a run that is not paused.”

## P10-6 — Workflow tracer and events API

### 89. What is `WorkflowTracer`?

**A:** “It is a telemetry component that persists workflow events such as node start, node completion, tool activity, model usage, errors, and final completion.”

### 90. Where are traced events stored?

**A:** “In the `workflow_events` SQLAlchemy table.”

### 91. What event types are implemented?

**A:** “The tracer supports `node_started`, `node_completed`, `tool_called`, `llm_called`, `error`, and `workflow_completed`. P11 adds approval-specific event names in its own implementation.”

### 92. What fields can a workflow event contain?

**A:** “Ticket ID, workflow ID, event type, node name, safe payload, duration, token usage, and timestamp.”

### 93. Why are timing and usage useful?

**A:** “They make execution measurable and allow an operator or later dashboard to identify slow nodes and estimate AI consumption.”

### 94. Does the tracer raise when persistence fails?

**A:** “No. `record()` catches persistence exceptions and returns no event. Telemetry is secondary and must not stop the support graph.”

### 95. What does `WorkflowTracer.node()` do?

**A:** “It records node start, catches node exceptions for an error event, re-raises the original exception, and records node completion with duration on success.”

### 96. Why does the tracer exclude prompt fields?

**A:** “Raw prompts, hidden reasoning, secrets, and runtime instructions are not necessary for the workflow timeline and must not be exposed as telemetry.”

### 97. How does the tracer make values safe?

**A:** “It converts enums and Pydantic models to JSON values, blocks sensitive keys such as prompt and secrets, converts sequences recursively, and excludes unsupported runtime objects.”

### 98. What is an `llm_called` event?

**A:** “It records that a model call completed for a node and includes input/output token counts and estimated cost.”

### 99. What is a `tool_called` event?

**A:** “It records a tool name associated with a graph node and the observed status.”

### 100. Does P10 prove the exact arguments and results of every tool call?

**A:** “Not completely. P10 currently derives some tool observations from known graph-node context in the workflow stream. Exact argument/result tracing requires the full node and registry call integration described in the project architecture.”

### 101. What endpoint retrieves workflow events?

**A:** “`GET /api/v1/tickets/{ticket_id}/events`."

### 102. What minimum role can read events?

**A:** “Viewer or higher.”

### 103. How are events ordered?

**A:** “The event repository selects events by workflow ID and ascending creation time.”

### 104. What happens if a ticket has no workflow run?

**A:** “The events endpoint returns an empty `items` list.”

### 105. What happens if the ticket is missing?

**A:** “The API returns 404.”

### 106. Can an events payload contain secrets?

**A:** “It is designed not to. The tracer filters sensitive keys and stores only safe status, node, tool, usage, and timing information.”

### 107. Does the events API expose hidden chain-of-thought?

**A:** “No. It exposes inspectable operational activity, not raw prompts or internal reasoning.”

### 108. How is the frontend expected to use events?

**A:** “The frontend can poll workflow and events endpoints and turn the chronological items into a timeline or progress panel.”

### 109. Which event can mark final workflow completion?

**A:** “`workflow_completed`."

### 110. When is `workflow_completed` emitted in P10-5/P10-6 streaming?

**A:** “After graph streaming ends, if graph execution returns normally and the tracer can persist the event.”

## Architecture and infrastructure questions

### 111. Which layer creates workflow runs?

**A:** “The API route validates HTTP and RBAC, while `WorkflowService` owns workflow orchestration.”

### 112. Which layer contains graph routing rules?

**A:** “The graph and risk nodes contain workflow routing. API routes do not implement the specialist policy decisions.”

### 113. Which layer writes SQL for workflow records?

**A:** “SQLAlchemy repositories write and read the workflow tables.”

### 114. Do graph nodes write SQL directly?

**A:** “No. Nodes return partial state and use specialists, tools, repositories, or services through the appropriate application boundaries.”

### 115. Do specialists write SQL directly?

**A:** “No. They obtain data through registered tools or memory services, not direct workflow SQL."

### 116. Where is the workflow service in relation to FastAPI?

**A:** “It is a service class inside the FastAPI application process. It orchestrates repositories and the LangGraph graph but does not depend on HTTP routes.”

### 117. Is there a separate LangGraph worker in Phase 10?

**A:** “No. Background tasks execute in the FastAPI process. A separate worker queue would be a production scaling extension.”

### 118. Is there a Docker network in Phase 10?

**A:** “No. No Compose stack or container networking was added in the Phase 10 implementation.”

### 119. What persistence choices does Phase 10 support?

**A:** “SQLite and PostgreSQL are supported through SQLAlchemy, while Redis or Fakeredis supports memory and in-memory or Qdrant support knowledge storage.”

### 120. What is the future container topology?

**A:** “A browser connects to Next.js, Next.js reaches FastAPI, and FastAPI reaches PostgreSQL or Supabase, Redis, Qdrant, and the AI provider. Phase 10 does not implement that topology.”

### 121. What happens in the offline demo mode?

**A:** “The fake LLM, fake Redis option, in-memory vector store, temporary SQLite database, and memory or SQLite checkpoints keep the workflow offline.”

### 122. Does a workflow run require a real AI API key in demo mode?

**A:** “No. `LLM_PROVIDER=fake` returns deterministic offline structured responses.”

### 123. Does `WorkflowService` read the existing tool registry setup?

**A:** “It can accept a registry for tests or dependency injection. Its default creates a `ToolRegistry` and a configured provider.”

### 124. What is a concern with the P10 tool tracer?

**A:** “The P10 implementation uses workflow-node context to infer tool observations. It does not yet prove exact argument/result coverage for every tool call.”

### 125. How should exact tool tracing be implemented later?

**A:** “Wrap `ToolRegistry.execute()` or record the tool-call result immediately in the node or tracer, using a safe allowlisted payload and no secret arguments.”

### 126. Why should exact tool payloads be filtered?

**A:** “Tool arguments can contain IDs, refund amounts, account settings, or other sensitive values. The event API should expose useful operation metadata without secrets or unneeded customer data.”

## State, routing, and concurrency questions

### 127. Why is `errors` append-only?

**A:** “It provides a complete error history for the workflow and avoids losing earlier partial failures.”

### 128. Why is `completed_nodes` append-only?

**A:** “It represents the node sequence and allows a UI to derive workflow progress from completed node IDs.”

### 129. What does `current_node` represent?

**A:** “It identifies the most recently active or completed workflow node in state.”

### 130. What can `paused` mean?

**A:** “It means the graph reached a pausable route in which further execution is waiting for an external decision or resume.”

### 131. How will P11 make a real pause?

**A:** “P11 will call `interrupt()` inside the human approval node and store the approved or rejected decision in the approval service and checkpointer.”

### 132. Why keep code before `interrupt()` small and idempotent?

**A:** “Checkpoint resume can re-execute code before the interrupt. Small, idempotent logic prevents duplicate writes or side effects.”

### 133. What route should a security breach take?

**A:** “A policy match makes the graph route to escalation before a model may suggest ordinary execution.”

### 134. What route should a refund take?

**A:** “It should route to human approval because a consequential billing action requires a recorded approval.”

### 135. What route should a dark-mode request take?

**A:** “It is low severity and no consequential action is required, so it can route to low-risk execution.”

### 136. What route should prompt-injected export text take?

**A:** “The ticket remains untrusted data, prompt-injection detection raises risk, and policy/risk routing prevents the export instruction from becoming an action.”

### 137. Can the model override a policy escalation?

**A:** “No. Deterministic policy matches are added outside model probability and must always win.”

### 138. Can a refund be executed through P10 graph execution?

**A:** “No. P10 resolution planning creates a proposal only. P11 adds the approval record and shared execution path.”

### 139. Can the graph execute `create_escalation` in P10?

**A:** “No. P10 is the orchestration shape; P11 and the escalation service add the final persisted routing behavior.”

### 140. Why is a second run blocked while approval is pending?

**A:** “Starting a duplicate workflow could produce two plans or approval requests for the same ticket and make the state ambiguous.”

## Testing questions

### 141. How are P10 graph nodes tested?

**A:** “Focused async pytest tests call node functions with a test state and verify partial state, completed nodes, output models, and resilient failures.”

### 142. How is graph shape tested?

**A:** “Tests verify `GRAPH_NODES`, `GRAPH_EDGES`, compiled graph construction, and conditional route outcomes.”

### 143. How are state reducers tested?

**A:** “Tests verify that completed nodes and errors append uniquely and token usage sums across values, including dataclass usage compatibility.”

### 144. How are checkpointers tested?

**A:** “Tests select `:memory:` for `InMemorySaver` behavior and a file path for `AsyncSqliteSaver` behavior.”

### 145. How is the run API tested?

**A:** “Tests verify viewer and agent RBAC, 202 workflow creation, workflow status lookup, and event ordering.”

### 146. How is telemetry tested?

**A:** “Tests create SQL records and assert event order, type, token usage, payload filtering, and timestamp fields.”

### 147. Are P10 tests fully offline?

**A:** “Yes for the current test setup. They use the fake LLM, in-memory or temporary SQLite, fake Redis settings, and in-memory knowledge choices.”

### 148. Are Docker containers needed for P10 tests?

**A:** “No. P10 tests run in-process and do not require Docker or a live external service.”

### 149. What does the full offline suite prove?

**A:** “It proves implemented unit, API, RAG, agent, workflow, memory, and repository behavior under the test environment.”

### 150. What does a passing suite not prove?

**A:** “It does not prove a real cloud deployment, live LLM behavior, live Redis or Qdrant availability, Docker networking, real approval decisions, or real money actions.”

## API and data questions

### 151. What does `WorkflowRun` store?

**A:** “It stores the ticket ID, status, JSON state snapshot, thread ID, and timestamps.”

### 152. What does `WorkflowEvent` store?

**A:** “It stores ticket and workflow IDs, event type, optional node name, safe payload, duration, token usage, and timestamps.”

### 153. Why is run state JSON instead of normalized workflow tables?

**A:** “The workflow has varied evolving fields and LangGraph state is naturally document-like. JSON snapshots make polling and state persistence straightforward in Phase 10.”

### 154. Why also store workflow events?

**A:** “Events preserve immutable chronology. State tells the current situation, while events show how the workflow reached that situation.”

### 155. What is the events repository responsibility?

**A:** “It returns all events for a workflow ordered by ascending creation time.”

### 156. What is the workflow run repository responsibility?

**A:** “It retrieves latest runs and provides workflow-run records for status and resume operations.”

### 157. Can the events API expose another customer's data?

**A:** “No. The route belongs to the ticket being requested and event payloads are filtered to operational workflow information.”

### 158. Why does the frontend reach only the API client layer?

**A:** "It keeps bearer handling, request routing, and typed response conversion out of UI components and avoids direct service-role access in the browser."

### 159. What response shapes mirror the API contract?

**A:** “Workflow run response contains `workflow_id`; workflow status contains ID, status, ticket ID, thread ID, and state; events response contains an `items` list.”

### 160. What needs to be added to the API contract for a route change?

**A:** “Update `docs/API_CONTRACT.md`, backend Pydantic schemas, and frontend types together.”

## Security and observability questions

### 161. How is prompt injection handled in Phase 10 routing?

**A:** “The supervisor detects injection-like text, wraps ticket content as untrusted, and the risk node raises routing risk for the workflow.”

### 162. How are policy decisions protected from model probability?

**A:** “Policy cases are matched with deterministic rules, and escalation or severity decisions are decided outside the model.”

### 163. How are approval-required actions protected?

**A:** “Resolution planning marks them as approval-required, and risk routing sends them to the approval route rather than ordinary execution.”

### 164. How are customer replies protected?

**A:** “The resolution layer validates internal URLs, secrets, and cross-customer data and falls back to a safe grounded reply if validation fails.”

### 165. How are secrets kept out of telemetry?

**A:** “The tracer blocks sensitive key names and stores only JSON-safe operational fields.”

### 166. How are secrets kept out of memory notes?

**A:** “Memory scrubbing and the memory service's note rules belong to earlier memory work. Graph state and telemetry should continue not to store raw ticket bodies or secrets.”

### 167. What is the observability principle for Phase 10?

**A:** “Telemetry must be inspectable but non-destructive. It should show decisions and activity without exposing prompts or becoming a reason for workflow failure.”

### 168. What does `WorkflowTracer` never raise over the workflow?

**A:** “It catches event persistence failures and returns no event rather than stopping graph execution.”

### 169. What audit layer applies to HTTP state changes?

**A:** “The existing audit middleware records non-GET requests through the application middleware stack.”

### 170. What request ID behavior applies to workflow routes?

**A:** “The existing request-ID middleware adds `X-Request-ID` to responses and binds it to application logging context.”

## Resumé and interruption questions

### 171. What is the P10 interruption status?

**A:** "P10 defines the graph route and placeholder state but does not implement a real `interrupt()` approval lifecycle."

### 172. What must P11 add before a real pause is complete?

**A:** “P11 must call `interrupt()`, create an approval record, set the ticket waiting on approval, and implement approval decision and graph resume routes.”

### 173. Why should code before `interrupt()` be small?

**A:** “The code can run again on resume. Small and idempotent logic prevents duplicate ticket updates or approval records.”

### 174. How will rejection route in P11?

**A:** “A rejected approval will route the workflow to escalation instead of executing the rejected action.”

### 175. How will approval route in P11?

**A:** “An approved action will resume the graph and execute the same registered tool path used for an approved or low-risk action.”

### 176. What does the P10 graph currently do for `human_approval`?

**A:** “It marks pending and paused status so the graph shape and state contract exist, without creating a real interrupt or approval record.”

### 177. What will P11 do for `execute_resolution`?

**A:** “It will execute planned actions through `ToolRegistry.execute()` with approval where required.”

### 178. What will P11 or a later memory phase do for `memory_update`?

**A:** “It will summarize the completed run and write safe, deduplicated customer memory notes through the memory service.”

## Honest status questions

### 179. Can I claim Phase 10 is complete in an interview?

**A:** “Yes, the Phase 10 orchestration and tracing scope is implemented and locally validated. You should distinguish it from the P11 approval and action lifecycle.”

### 180. Can I claim Docker support in an interview from Phase 10?

**A:** “No. Docker was not implemented in Phase 10, so describe the future container topology only as planned architecture.”

### 181. Can I claim real refunds or account changes work?

**A:** “No. Phase 10 only proposes consequential actions and routes them to approval placeholders. P11 must add real approval-record and tool-execution behavior, while v1 integrations remain mock.”

### 182. Can I claim live AI was validated?

**A:** “No. Phase 10 tests run offline with the fake provider. A live provider has not been validated unless separately demonstrated.”

### 183. Can I claim live PostgreSQL was tested?

**A:** “No. SQLite and test fixtures can validate local behavior. Claim PostgreSQL only when a real PostgreSQL or Supabase environment was actually run.”

### 184. Can I claim live Redis or Qdrant was tested?

**A:** “No unless the actual environment was used. In Phase 10, Fakeredis and in-memory/vector test modes are sufficient for offline checks.”

### 185. Can I claim workflow tracing is complete end to end?

**A:** "It is complete for workflow stream state and event persistence, but the exact low-level registry argument and result trace should be described as a Phase 10 limitation being fully strengthened in later implementation."

### 186. What is the clearest Phase 10 limitation statement?

**A:** "The graph and observability are in place, but P11 must add real interrupts, approval decisions, shared action execution, and final memory recording before the complete ticket-resolution lifecycle is production-ready."

## Architecture comparison questions

### 187. How is Phase 10 different from Phase 9?

**A:** “Phase 9 builds specialist components individually. Phase 10 organizes those components into a graph, persists state, creates runs, routes risk, and records events.”

### 188. How is Phase 10 different from P11?

**A:** “Phase 10 provides the graph and trace. P11 adds real approval interrupts, decision APIs, escalation routing, shared resolution execution, and demo behavior.”

### 189. How is Phase 10 different from a conventional API endpoint?

**A:** “A normal endpoint performs one request-response operation. The workflow API starts a multi-stage graph and lets the client poll persisted state and events.”

### 190. How is Phase 10 different from a microservice architecture?

**A:** “The specialist agents and graph still run inside the FastAPI Python process. It is a modular application-layer workflow, not a distributed set of separate agent containers.”

### 191. Why use LangGraph instead of manually calling agents in a function?

**A:** "LangGraph provides named stateful nodes, conditional routing, streaming updates, and checkpoint integration. A manual function would need to reimplement much of that control and persistence."

### 192. Is LangGraph itself the database?

**A:** “No. LangGraph coordinates graph state and can use a checkpointer. SQLAlchemy repositories persist workflow runs and events for application queries.”

### 193. Is LangGraph itself the AI model?

**A:** “No. LangGraph is the stateful orchestration library. The specialist agents call the configured AI provider through `call_structured()`.”

### 194. What is the role of Pydantic in Phase 10?

**A:** “Pydantic schemas validate specialist results and API workflow response shapes.”

### 195. What is the role of SQLAlchemy in Phase 10?

**A:** “SQLAlchemy defines and queries workflow runs and events and persists JSON-safe state in supported databases.”

### 196. What is the role of FastAPI BackgroundTasks?

**A:** “It schedules workflow execution after the run request has created a record and provides an immediate 202 response.”

### 197. What is the role of the frontend in Phase 10?

**A:** “It is not implemented yet as a Phase 10 workflow console. The API contract is prepared for later frontend polling and timeline rendering.”

### 198. What is the future frontend flow?

**A:** “The future UI starts a run, polls status every two seconds, displays completed nodes and state, reads events, and exposes approval actions in later phases.”

### 199. What is the future resume flow?

**A:** “P11 approval APIs decide the approval, resume with a LangGraph `Command(resume=...)`, and continue the graph through resolution execution and memory update.”

### 200. What is the most important Phase 10 interview message?

**A:** “Phase 10 is a rules-plus-model, stateful workflow system: deterministic policy and risk boundaries control routes, LangGraph coordinates specialist nodes, and telemetry makes the process inspectable without exposing hidden model data.”
