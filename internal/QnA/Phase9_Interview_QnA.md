# Phase 9 — Interview Questions and Answers

This question bank covers **Phase 9: Specialist Agents**. The answers are written for interview speaking and distinguish implemented specialist components from the later LangGraph workflow that will compose them.

Related reading:

- [Phase 9 plain-language explanation](../explain_codebase/phase9_explained.md)
- [Phase 9 system-design evolution](../design_evolution/Phase9_Project_System_Design_Evolution.md)
- [Phase 9 infrastructure evolution](../Infra_design_evolution/Phase9_Infra_design_evolution.md)
- [Phase 9 task status](../../TASK.md)
- [Phase 9 plan](../../PLAN_PHASE.md)

## 30-second overview

### 1. Can you summarize Phase 9?

**A:** “Phase 9 creates the specialist components that will investigate support tickets. A Supervisor understands and triages the ticket, a Customer agent gathers context, a Knowledge agent finds evidence, a Troubleshooting agent creates a diagnosis, a Resolution agent prepares a safe plan, and an Escalation agent applies policy and routes serious cases.”

### 2. What problem does Phase 9 solve?

**A:** “It replaces a single all-purpose AI prompt with focused specialist responsibilities and predictable structured outputs. This makes the system easier to test, inspect, ground in evidence, and protect with rules.”

### 3. What are the eight Phase 9 subtasks?

**A:** “P9-1 adds schemas and a fake LLM, P9-2 adds the Supervisor, P9-3 the Customer agent, P9-4 the Knowledge agent, P9-5 Troubleshooting, P9-6 Resolution, P9-7 Escalation, and P9-8 the evaluation dataset.”

### 4. Does Phase 9 execute all specialists in one workflow?

**A:** “No. Phase 9 implements and tests the specialist components individually. A later LangGraph phase will compose them into nodes and route state between them.”

### 5. Is the complete ticket workflow available after Phase 9?

**A:** “No. Human approval interrupts, workflow state persistence, graph routing, workflow events, and the ticket action API still belong to later phases.”

### 6. Which specialist owns ticket understanding?

**A:** “The Supervisor agent.”

### 7. Which specialist gathers account context?

**A:** “The Customer agent.”

### 8. Which specialist creates the diagnosis?

**A:** “The Troubleshooting agent.”

### 9. Which specialist prepares a safe resolution plan?

**A:** “The Resolution agent.”

### 10. Which specialist decides escalation?

**A:** “The Escalation agent.”

### 11. What is a specialist in this application?

**A:** “It is a focused Python component with a defined responsibility and structured output. It may use AI, registered tools, deterministic rules, or memory, but it does not need to handle the entire support pipeline.”

### 12. Why use several specialists instead of one AI prompt?

**A:** “Smaller components reduce complexity, make individual behavior testable, prevent unrelated data from entering a prompt, and allow deterministic policy to remain outside the model.”

### 13. What is the central Phase 9 design principle?

**A:** “AI judgement inside structured boundaries, with rules, tools, schemas, guardrails, and tests controlling important behavior.”

### 14. What is the strongest one-sentence Phase 9 summary?

**A:** “Phase 9 turns CloudDesk's existing tools and policies into a team of structured specialist agents that can classify, investigate, resolve, escalate, and be evaluated independently.”

## P9-1 — Schemas and fake AI

### 15. Where are the specialist answer formats defined?

**A:** “In `backend/app/schemas/workflow.py`.”

### 16. Why use Pydantic models?

**A:** “Pydantic validates field names and types, rejects malformed AI output, and gives downstream code one predictable object shape.”

### 17. What is `Classification`?

**A:** “It contains one of the 10 CloudDesk categories and a concise one-line ticket summary.”

### 18. What is `SeverityAssessment`?

**A:** “It contains a low, medium, high, or critical severity and a short reason.”

### 19. What is `CustomerContext`?

**A:** “It contains the customer, subscription, workspaces, previous tickets, and memory notes used during investigation.”

### 20. What is `Evidence`?

**A:** “It identifies a cited knowledge passage with its title, source, snippet, score, URL, and article identifier.”

### 21. What is `PreviousCase`?

**A:** “It represents a previously resolved ticket and contains its identifier, subject, category, resolution or summary, and similarity score.”

### 22. What is `Diagnosis`?

**A:** “It contains probable causes, hypotheses, numbered troubleshooting steps, checks, an optional root cause, and confidence.”

### 23. What is `ActionProposal`?

**A:** “It proposes a tool name and arguments, states whether approval is required, and gives a rationale.”

### 24. What is `ResolutionPlan`?

**A:** “It contains a summary, customer-facing reply, internal notes, troubleshooting steps, and proposed actions.”

### 25. What is `EscalationDecision`?

**A:** “It contains whether escalation is required, the target team, reason, severity, and confidence.”

### 26. What is `call_structured()`?

**A:** “It is the common function for asking an LLM to return a Pydantic schema. It retries, parses JSON or model output, validates the result, and records usage and duration.”

### 27. What happens if structured output is malformed?

**A:** “`call_structured()` retries and raises the final parsing or validation error if the provider cannot return valid content.”

### 28. Why should every agent call models through `call_structured()`?

**A:** “It provides consistent validation and usage telemetry and prevents agents from inventing their own parsing behavior.”

### 29. What is `FakeLLM`?

**A:** “It is a deterministic offline provider used for tests and demos. It returns valid JSON for known workflow schema requests.”

### 30. How does the FakeLLM avoid external API calls?

**A:** “It detects the requested schema from the prompt and constructs a JSON response directly inside the Python process.”

### 31. Is the fake provider only for tests?

**A:** “It is used in tests and offline demos. The application can keep the same structured calling pattern when a real provider is configured later.”

### 32. What is `LLMUsage`?

**A:** “It is the input-token count, output-token count, and estimated cost returned alongside a structured result.”

### 33. Does the fake provider incur cost?

**A:** “No. It returns zero usage and zero cost.”

### 34. How do Phase 9 specialists receive an LLM implementation?

**A:** “They accept an optional `llm` argument. If no implementation is supplied, `call_structured()` obtains the configured provider.”

### 35. How are free-text answers handled?

**A:** “Specialists use structured fields and fallback logic instead of sending raw paragraphs as state between components.”

## P9-2 — Supervisor agent

### 36. What does `SupervisorAgent` do?

**A:** “It understands a ticket, classifies it, assesses severity, detects injection-like text, and creates a concise internal summary.”

### 37. How does it receive ticket text?

**A:** “It accepts a ticket mapping, subject and body, or plain text through several supported method arguments.”

### 38. What are the 10 exact categories?

**A:** “`login_issue`, `billing`, `api_failure`, `workspace_permissions`, `storage_quota`, `integration`, `feature_request`, `account`, `security`, and `other`."

### 39. Does the model have the final category decision?

**A:** “No. Clear deterministic category rules can override or correct the model category.”

### 40. Give an example of a deterministic category override.

**A:** “An SSO, MFA, or locked-out ticket becomes `login_issue`; a delete-workspace and GDPR ticket becomes `account`; and unauthorized-charge text becomes `billing`."

### 41. Does severity become lower because of a policy rule?

**A:** “No. Policy severity can raise the model result but is not allowed to lower a more severe model assessment.”

### 42. Give an example of severity policy.

**A:** “A possible breach, suspicious login, or data-loss text can be raised to critical; deletion or unauthorized-charge disputes can be raised to high; dark mode remains low.”

### 43. Why is prompt-injection text marked as untrusted?

**A:** “The text may contain instructions that look authoritative but came from the ticket. Wrapping it helps prevent the model from treating it as a system command.”

### 44. What is `scan_for_injection()` used for?

**A:** “It flags suspicious text that asks the model to export data, ignore instructions, or reveal protected information.”

### 45. What does `wrap_untrusted()` do?

**A:** “It places ticket content between delimited `<untrusted_content>` tags and escapes embedded closing tags.”

### 46. Does injection detection stop the whole workflow?

**A:** “In Phase 9 it sets a flag and routes policy handling to security-oriented logic. CD-1013 is not executed as an export instruction.”

### 47. How are missing summaries handled?

**A:** “The Supervisor uses a one-line fallback based on the ticket text instead of returning an empty summary.”

### 48. What is `SupervisorAgent.run()` for?

**A:** “It combines understanding and severity assessment and returns classification, severity, injection status, usage, and duration information.”

## P9-3 — Customer agent

### 49. What does `CustomerAgent` do?

**A:** “It gathers customer details, subscriptions, workspaces, previous tickets, and recalled memory notes.”

### 50. Does it use SQL directly?

**A:** “No. It uses registered read-only tools and optionally a memory service.”

### 51. Which read-only tools does it use?

**A:** “At minimum `get_customer`, `get_subscription`, and `get_ticket_history`. It also checks for `get_workspaces` if it is registered.”

### 52. What is the result type?

**A:** “It returns `CustomerContext`.”

### 53. What happens if a tool fails?

**A:** “The agent catches the failure and continues with partial context rather than crashing.”

### 54. How are memory notes handled?

**A:** “The agent recalls the safe notes, runs scrubbing again, excludes blank results, and limits the list to 10 notes.”

### 55. Can the Customer agent write account data?

**A:** “No. It only reads context and memory.”

### 56. Why use a tool registry here?

**A:** “It gives the agent a consistent execution boundary, timeout, policy check, and explicit success or failure result.”

### 57. What happens if no memory service is supplied?

**A:** “The returned `CustomerContext` simply has no memory notes.”

## P9-4 — Knowledge agent

### 58. What does `KnowledgeAgent` do?

**A:** “It finds cited knowledge evidence and similar previously resolved cases.”

### 59. Which tool does it call?

**A:** “The registered `search_docs` tool.”

### 60. What is evidence in Phase 9?

**A:** “A structured `Evidence` object with the knowledge article, source citation, supporting snippet, relevance score, and identifiers.”

### 61. Give an example of a source citation.

**A:** “`kb://mfa-recovery#steps` or `kb://sso-login-troubleshooting#checks`."

### 62. How are source citations useful?

**A:** “They let the support workflow show which article section supported a diagnosis or reply instead of relying on an unsupported claim.”

### 63. How are similar resolved cases found?

**A:** “The agent compares text tokens using Jaccard similarity and can filter by category.”

### 64. What is Jaccard similarity?

**A:** “It is the number of shared words divided by the number of distinct words in both texts.”

### 65. Is similarity calculated by AI?

**A:** “No. It is a deterministic text-overlap calculation.”

### 66. How many similar cases are returned by default?

**A:** “Up to three.”

### 67. What fields are compared when finding a case?

**A:** “Subject, resolution, summary, and category.”

### 68. What happens if retrieval fails?

**A:** “The agent returns an empty evidence list and can still find independent resolved cases.”

### 69. Does the agent accept top-k values outside a safe range?

**A:** “No. It requires top-k to be between 1 and 20.”

### 70. Where are previous resolutions loaded from?

**A:** "By default, `sample_data/previous_resolutions.json`."

## P9-5 — Troubleshooting agent

### 71. What does `TroubleshootingAgent` do?

**A:** “It combines ticket category, evidence, customer context, category playbooks, and service status to create a diagnosis.”

### 72. Which tool does it call?

**A:** “`check_service_status` through `ToolRegistry`.”

### 73. What is a category playbook?

**A:** “It is a deterministic list of common probable causes and safe initial checks for a category such as login, billing, API, or storage.”

### 74. Why use a playbook if AI can reason?

**A:** “The playbook provides stable baseline guidance, especially in categories where known checks exist, and prevents the model from omitting important steps.”

### 75. What does the diagnosis contain?

**A:** “Probable causes, hypotheses, checks, numbered steps, root cause, and confidence.”

### 76. How are service-status failures handled?

**A:** “The status check is optional. Tool failure or no registration simply leaves `checks` empty and allows the agent to continue.”

### 77. How does degraded or outage service state affect confidence?

**A:** “It raises confidence to at least 0.75 because a matching active service problem adds stronger evidence.”

### 78. Can the playbook invent an incident?

**A:** “No. It provides general category checks. The actual incident status comes only from the registered service-status result.”

### 79. How are duplicate steps removed?

**A:** “The agent merges playbook and model steps while preserving the first occurrence of each normalized step.”

### 80. How are steps numbered?

**A:** “The agent prepends `1.`, `2.`, `3.`, and so on unless a step already contains a numbering marker.”

### 81. What happens if the model supplies no root cause?

**A:** “The agent uses the only probable cause when it has exactly one; otherwise root cause remains unspecified.”

### 82. What is the main output boundary for troubleshooting?

**A:** “A Pydantic `Diagnosis` object with bounded confidence and structured lists.”

## P9-6 — Resolution agent

### 83. What does `ResolutionAgent` do?

**A:** “It turns a diagnosis and evidence into a resolution summary, customer reply, internal notes, steps, and proposed actions.”

### 84. Does the Resolution agent execute tools?

**A:** “No. It proposes deterministic action objects. It does not call the tool registry to execute side effects.”

### 85. What is an `ActionProposal`?

**A:** “It is a description of one possible tool action, including tool name, arguments, approval status, and rationale.”

### 86. Which ordinary action can every identified ticket receive?

**A:** “An `update_ticket` proposal with status `in_progress`."

### 87. Which consequential actions require approval?

**A:** “A refund proposal and a workspace setting reset.”

### 88. Which tool is used for a refund?

**A:** “`create_refund_request`.”

### 89. Which tool is used to reset a workspace setting?

**A:** “`reset_demo_setting`.”

### 90. How is the customer reply grounded?

**A:** “The agent combines the model reply with missing diagnosis steps and validates the final text.”

### 91. What customer-output validation checks are used?

**A:** “It blocks empty replies, internal URLs and private addresses, secrets, card numbers, and another customer's identifiers or names.”

### 92. What happens if validation fails?

**A:** “The agent replaces the unsafe reply with a safe fallback based on its diagnosis steps.”

### 93. Can the AI invent arbitrary action arguments?

**A:** “No. Action arguments come from deterministic planning code, not from free-form model output.”

### 94. Can a refund be executed silently?

**A:** “No. The refund proposal explicitly requires approval, and policy later controls actual tool execution.”

### 95. Why are both `customer_reply` and `reply` present?

**A:** “The schema retains compatibility with the existing fake provider and resolution representation while both fields receive the same safe reply.”

## P9-7 — Escalation agent

### 96. What does `EscalationAgent` do?

**A:** “It routes clear policy cases deterministically and uses cautious structured AI judgement for grey areas.”

### 97. Which function finds policy matches?

**A:** “`matching_escalation_rules()`.”

### 98. Can policy escalate a case without AI?

**A:** “Yes. Matching a policy rule immediately returns an escalation decision with the named team and required severity.”

### 99. Why does policy take priority?

**A:** “For legal, security, data-loss, dispute, deletion, and outage cases, a probabilistic model should not make the final decision.”

### 100. How is policy severity chosen when several rules match?

**A:** “The agent uses the highest severity among all matched policy rules.”

### 101. What team is used for suspicious-login or breach cases?

**A:** “The security team.”

### 102. What team is used for data loss?

**A:** “The data recovery team.”

### 103. What team is used for workspace deletion or GDPR?

**A:** “The account deletion team.”

### 104. What team is used for unauthorized-charge or payment disputes?

**A:** “The billing and payment dispute team.”

### 105. What team is used for prompt-injection or bulk-export requests?

**A:** “The security team.”

### 106. Under what conditions will the AI alone escalate?

**A:** “It must request escalation, report confidence of at least 0.60, and return high or critical severity.”

### 107. What happens if the model gives a vague low-confidence escalation?

**A:** “The agent does not escalate and continues through normal workflow handling.”

### 108. What happens if no team is named by a model judgement?

**A:** “The agent rejects or leaves the escalation unnamed because the known policy-team boundary is not met.”

### 109. What confidence is returned for a direct policy match?

**A:** “1.0, because the decision is based on a deterministic rule.”

## P9-8 — Evaluation dataset

### 110. Where is the evaluation dataset stored?

**A:** “In `datasets/eval_cases.json`."

### 111. How many current demo cases does it contain?

**A:** “13 cases, CD-1001 through CD-1013.”

### 112. What fields does each case have?

**A:** “Ticket number, text, expected category, severity, escalation boolean, team, article identifier, and grounding steps.”

### 113. Why is the dataset necessary?

**A:** “It provides known expected answers for regression testing and future metric evaluation.”

### 114. Which categories are covered?

**A:** “All 10 categories, including `other`."

### 115. Which policy cases are covered?

**A:** “Security, data loss, workspace deletion, unauthorized charge, enterprise-wide SSO impact, and prompt injection.”

### 116. Why is CD-1013 important?

**A:** “It proves that embedded export instructions remain ticket data and must trigger safe handling instead of a customer-record export.”

### 117. Where are dataset validation tests located?

**A:** “In `tests/evaluation/test_eval_cases.py`."

### 118. What do dataset tests verify?

**A:** “Valid categories and severities, 13 unique tickets, all-category coverage, policy escalation coverage, and the prompt-injection case.”

### 119. Is the dataset itself a runtime routing table?

**A:** “No. It is a golden test and evaluation input. Runtime policy remains in code.”

### 120. How does the dataset support future metrics?

**A:** “It supplies the expected category, escalation team, article, and steps that can be compared with actual specialist output.”

## Specialist architecture questions

### 121. How do specialists communicate?

**A:** “They exchange Pydantic models in Python method calls. A later graph will store these values in workflow state.”

### 122. What does the end-to-end intended order look like?

**A:** “Supervisor → Customer → Knowledge → Troubleshooting → Resolution → Escalation.”

### 123. What is the Customer agent's relationship to the Knowledge agent?

**A:** “They gather independent context. Customer context comes from account and memory data, while Knowledge evidence comes from approved articles and prior resolutions.”

### 124. What is the relationship between Diagnosis and Resolution?

**A:** “Diagnosis is the technical or support hypothesis, while Resolution converts it into a customer-safe plan and proposed actions.”

### 125. What is the relationship between Resolution and Escalation?

**A:** “Resolution prepares the plan, while Escalation decides whether policy or uncertainty requires specialist routing.”

### 126. Does every ticket reach every specialist?

**A:** “The intended graph includes all stages, but later routing may branch based on risk or escalation. Phase 9 has individual components rather than a complete graph.”

### 127. Why do specialists remain independent of SQLAlchemy models?

**A:** “They should focus on AI and decision logic. SQL belongs behind repositories and tools so specialists do not become data-access layers.”

### 128. Can a specialist execute tools directly?

**A:** “Read-only agents use `ToolRegistry`; the Resolution agent proposes write actions but does not execute them.”

### 129. What is the trust boundary around a tool call?

**A:** “Tool registration, approval policy, timeout handling, and `ToolResult` success or failure remain outside the model.”

### 130. Why validate output twice for resolution?

**A:** “Pydantic validates the plan structure, and `validate_customer_output()` validates that the final customer-facing text is safe.”

### 131. What happens if customer context is missing?

**A:** “The agent can continue with an empty or partial context, so lack of one tool result does not necessarily stop diagnosis.”

### 132. What is grounding in this phase?

**A:** “A reply or plan uses diagnosis steps and approved evidence rather than unsupported claims.”

### 133. How can grounding be measured later?

**A:** “Evaluation compares whether the reply contains the expected diagnosis or troubleshooting steps.”

### 134. What is citation rate?

**A:** "The proportion of factual claims or responses that include valid evidence citations."

### 135. What is the target escalation correctness?

**A:** “At least 90 percent.”

### 136. What is the target classification accuracy?

**A:** “At least 80 percent.”

### 137. What is the target retrieval hit-rate at 3?

**A:** “At least 75 percent.”

### 138. What is the target citation rate?

**A:** “At least 90 percent.”

### 139. What is the target grounding rate?

**A:** “At least 90 percent.”

## Offline, testing, and infrastructure questions

### 140. Can Phase 9 run without an API key?

**A:** “Yes. `LLM_PROVIDER=fake` gives deterministic responses, while SQLite and Fakeredis or memory stores provide offline dependencies.”

### 141. Are specialist tests fully offline?

**A:** “The current tests use fake AI, mock tools, temporary data, and local sample files. They do not require a real API key.”

### 142. Does Phase 9 add Docker containers?

**A:** “No. Docker and Compose belong to later delivery work.”

### 143. Does Phase 9 add HTTP routes for specialists?

**A:** “No. It adds Python specialist classes. HTTP workflow routes are later.”

### 144. Does Phase 9 add LangGraph nodes?

**A:** “No. It creates the specialist components that later graph nodes can invoke.”

### 145. Does Phase 9 persist specialist outputs?

**A:** “No. The specialist methods return Python objects or test results. Workflow-run and event persistence belong to later graph infrastructure.”

### 146. Does `ResolutionAgent` call the approval API?

**A:** “No. Approval is future graph and API work. The agent only marks proposed actions as requiring approval.”

### 147. Does `EscalationAgent` create an escalation database record?

**A:** “No. It returns an `EscalationDecision`. A later graph or tool node will perform routing and persist the escalation.”

### 148. How are specialist tests structured?

**A:** “There is a focused test module for each specialist or one shared test for structured schema and fake-provider behavior.”

## Edge-case and security questions

### 149. What happens with prompt-injection text?

**A:** “It is treated as untrusted ticket data. It is not allowed to become a system instruction or trigger an export.”

### 150. What happens with an unauthorized-charge ticket?

**A:** “The rules classify it as billing and likely escalate it to the billing and payment dispute team.”

### 151. What happens with a data-loss ticket?

**A:** “The policy can classify or raise the severity and route the case to the data recovery team.”

### 152. What happens with a workspace-deletion request?

**A:** “The account category and high severity can apply, and the case can route to the account deletion team.”

### 153. What happens with a refund request?

**A:** “The Resolution agent proposes `create_refund_request` but marks it as approval-required.”

### 154. What happens with a setting reset request?

**A:** “The Resolution agent proposes `reset_demo_setting` only when workspace context exists and marks it approval-required.”

### 155. What happens with dark mode?

**A:** “It is classified as a feature request and remains low severity.”

### 156. What happens with Slack integration failure?

**A:** “It becomes integration and receives integration-specific troubleshooting, unless a separate policy rule requires escalation.”

### 157. What happens with API 429 errors?

**A:** “It is classified as API failure and receives checks for service status, status code, retry timing, credentials, and request parameters.”

### 158. What happens with storage quota?

**A:** “It is classified as storage quota and checked against usage, limits, and upload behavior.”

### 159. What happens with MFA lockout?

**A:** “It is classified as login issue and receives MFA recovery and session checks.”

### 160. What happens with suspicious login text?

**A:** “It becomes critical security and routes to the security team under deterministic policy.”

## Behavioral and architecture trade-offs

### 161. What is the benefit of rule-first escalation?

**A:** “Known dangerous or regulated cases receive consistent routing regardless of model uncertainty.”

### 162. What is the benefit of AI judgement in grey areas?

**A:** “The model can interpret subtle context that explicit phrase rules might miss.”

### 163. What is the limitation of deterministic rules?

**A:** “Rules may miss wording not included in the term set and therefore need conservative review or expanded policy coverage.”

### 164. What is the limitation of Jaccard similarity?

**A:** “It compares word overlap, not deep meaning, and may miss semantically similar text with different words.”

### 165. How could retrieval improve later?

**A:** “A stronger embedding model or LLM reranker could improve semantic matching, but the change would require reindexing and evaluation.”

### 166. What is the benefit of Pydantic models?

**A:** “They create a shared data contract for UI, tests, graph state, and storage.”

### 167. What is the main disadvantage of structured agents?

**A:** “The system needs careful schema evolution and retry handling. Otherwise provider output may repeatedly fail validation.”

### 168. Should all prompts be free text?

**A:** “No. Prompts can guide the model, but important decisions and side effects should come from schemas, policies, and tools.”

### 169. Does fake AI prove real AI quality?

**A:** “No. It proves offline behavior and schema correctness. Real-provider quality still requires evaluation and guardrail testing.”

### 170. What is the strongest architecture lesson from Phase 9?

**A:** “Divide the problem into specialists, make their results inspectable, keep policy outside the model, control tools, validate replies, and measure behavior with known cases.”

## Honest status questions

### 171. What was implemented in Phase 9?

**A:** “Workflow schemas, a fake LLM, six specialist components, and the evaluation dataset.”

### 172. What was validated locally?

**A:** “Focused specialist tests and policy/schema tests run offline with the fake provider and mock or in-memory infrastructure.”

### 173. What was not implemented in Phase 9?

**A:** “LangGraph composition, graph state persistence, workflow events, approval interrupts, action execution, workflow HTTP routes, Docker, and the ticket UI.”

### 174. Are cloud services involved?

**A:** “No. Phase 9 is local and offline for the normal demo and test path.”

### 175. What begins in the next phase?

**A:** "Phase 10 composes the specialists into a support-state graph and adds tracing and node activity."
