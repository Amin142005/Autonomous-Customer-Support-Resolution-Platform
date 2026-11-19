# Phase 7 — Interview Questions and Answers

This question bank covers **Phase 7: Rules and guardrails**. The answers are
written for interview speaking, distinguish implemented behavior from future
agent work, and include both technical detail and a plain-language explanation.

Related reading:

- [Phase 7 plain-language explanation](../explain_codebase/phase7_explained.md)
- [Phase 7 system-design evolution](../design_evolution/Phase7_Project_System_Design_Evolution.md)
- [Phase 7 infrastructure evolution](../Infra_design_evolution/Phase7_Infra_design_evolution.md)
- [Phase 7 task status](../../TASK.md)
- [Phase 7 plan and exit criteria](../../PLAN_PHASE.md)

## 30-second overview

### 1. Can you summarize Phase 7?

**A:** “Phase 7 adds deterministic rules and text-safety boundaries around the
future AI workflow. Clear policy cases decide escalation and severity, ticket
text is marked as untrusted, customer replies are validated, and secrets are
scrubbed before memory use.”

### 2. What problem does Phase 7 solve?

**A:** “It prevents a model from making dangerous policy decisions or returning
unsafe text by probability alone. Written rules and validation run outside the
model as additional controls.”

### 3. What are the four Phase 7 subtasks?

**A:** “P7-1 adds escalation and severity rules. P7-2 adds prompt-injection
wrapping and a security preamble. P7-3 validates customer-facing output. P7-4
adds centralized secret scrubbing.”

### 4. Does Phase 7 run the complete LangGraph agent workflow?

**A:** “No. It provides reusable policy and guardrail modules for the specialist
agents and workflow nodes that will be implemented in later phases.”

### 5. Is Phase 7 a model provider implementation?

**A:** “No. It contains prompt boundaries and validation code, but it does not
call a live model.”

### 6. Is Phase 7 a Docker or infrastructure phase?

**A:** “No. It runs as Python modules inside the existing application or test
process. No Dockerfile, Compose service, database migration, or network route
was added.”

### 7. What is the central design principle?

**A:** “Rules first, AI judgment second. Known policy cases are deterministic;
the model is used in grey areas where the rules do not decide.”

### 8. What is defense in depth?

**A:** “It means several independent controls protect the system. Phase 7
protects policy decisions, prompt input, customer output, and memory text
instead of relying on only one check.”

### 9. Why is Phase 7 important?

**A:** “An AI can misread a customer's words as an instruction or produce text
that exposes sensitive infrastructure or customer data. Phase 7 creates code
boundaries that catch clear policy and text risks.”

### 10. What is the strongest Phase 7 summary?

**A:** “Phase 7 makes CloudDesk rules-first: clear policy always wins, ticket
text is untrusted, replies are checked, and secrets are removed before memory
use.”

## P7-1 — Escalation and severity rules

### 11. What is in `agents/rules.py`?

**A:** “It contains deterministic escalation matches, category rules, severity
rules, text normalization, and helpers for policy decisions.”

### 12. What does `ESCALATION_RULES` contain?

**A:** “It maps rule names to a team, required severity, and a set of normalized
terms. It includes security, data loss, deletion, dispute, outage, legal, and
prompt-injection cases.”

### 13. What policy teams are defined?

**A:** “The security team, data recovery team, account deletion team, billing
and payment dispute team, incident response team, and legal and compliance
team.”

### 14. What does `matching_escalation_rules()` do?

**A:** “It normalizes ticket text and returns structured matches containing a
rule name, team, and required severity.”

### 15. Why use a team-specific rule instead of one generic escalation?

**A:** “Different cases need different reviewers. A security breach should not
be routed as a normal account issue, and a data-loss case should reach recovery
specialists.”

### 16. What is `rule_category()`?

**A:** “It applies deterministic category overrides for clear subjects, but it
preserves a valid model category when no policy term matches.”

### 17. Which category examples are handled explicitly?

**A:** “Security, account deletion, billing disputes, login and MFA issues, API
429 failures, storage quota, integrations, workspace permissions, and dark
mode feature requests.”

### 18. What is `rule_severity()`?

**A:** “It compares model severity with deterministic policy severity and raises
the result when policy requires it.”

### 19. What does “rules can raise but never lower severity” mean?

**A:** “A policy rule may increase low or medium severity to high or critical.
The model cannot lower a severity that is already higher or required by policy.”

### 20. How is severity ranked?

**A:** “Low is 0, medium is 1, high is 2, and critical is 3.”

### 21. Which text raises severity to critical?

**A:** “Examples include possible breach, account compromise, suspicious login,
enterprise outage, data loss, files disappearing, and export or instruction
phrases associated with prompt injection.”

### 22. Which text raises severity to high?

**A:** “Examples include team-wide SSO issues, workspace deletion, erasure,
GDPR, unauthorized charges, payment disputes, and chargebacks.”

### 23. Can a security category force critical severity?

**A:** “Yes. The severity helper has category and text checks that can require
critical for clear security or suspicious-login policy cases.”

### 24. What happens to dark mode requests?

**A:** “They are treated as low severity by the deterministic policy.”

### 25. Why normalize text before matching rules?

**A:** “Normalization lowercases text and extracts alphanumeric words. It makes
matching more consistent and avoids punctuation differences.”

### 26. Is category matching an LLM call?

**A:** “No. P7-1 category and escalation matching are deterministic Python
string and term checks.”

### 27. Can policy escalation override a model that says no escalation?

**A:** “Yes. A policy match is a direct rule decision and should override the
model's judgment.”

### 28. Does P7-1 decide every category perfectly?

**A:** “No. It defines clear deterministic overrides. For unclear subjects,
a valid model category can still be preserved.”

### 29. Why is P7-1 separate from P7-2 and P7-3?

**A:** “P7-1 decides policy and severity. P7-2 protects prompt text. P7-3
protects customer-facing output. They solve different risks.”

### 30. What is the policy-versus-model flow?

**A:** “Known policy cases are handled by rules. Ambiguous grey areas may use
model judgment. The model cannot override known policy decisions.”

## P7-2 — Prompt injection and security preamble

### 31. What is prompt injection?

**A:** “It is text that tries to make an AI ignore its instructions or perform
an action the application does not allow.”

### 32. What does `scan_for_injection()` do?

**A:** “It searches text for known instruction-like patterns and returns a
boolean indicating likely injection.”

### 33. Which patterns does it recognize?

**A:** “It recognizes ignore or disregard instructions, reveal hidden prompts,
override rules, bypass approval, developer mode, export customer records,
invoke tools, jailbreak phrases, and similar language.”

### 34. Does pattern detection catch every prompt injection?

**A:** “No. It is a deterministic first line of defense, not a complete natural-
language security system.”

### 35. What is `wrap_untrusted()`?

**A:** “It places text inside `<untrusted_content>` tags so future prompts can
identify it as customer-supplied data.”

### 36. Why is an untrusted-content block useful?

**A:** “It separates information from instructions. The model can read ticket
text but should not treat it as authority for policy or tool actions.”

### 37. What happens if ticket text contains the closing tag?

**A:** “The wrapper escapes it to `&lt;/untrusted_content&gt;` so ticket text
cannot break the delimiter boundary.”

### 38. What happens if ticket text contains the opening tag?

**A:** “The wrapper escapes it to `&lt;untrusted_content&gt;`.”

### 39. What is `SECURITY_PREAMBLE`?

**A:** “It is shared prompt text that tells the model to treat untrusted blocks
as customer data, never as instructions, and to ignore attempts to reveal
prompts, bypass approval, or access another customer.”

### 40. Where is `SECURITY_PREAMBLE` exposed?

**A:** “It is defined in `backend/app/core/guardrails.py` and re-exported by
`agents/prompts.py` for future prompt builders.”

### 41. Does the preamble itself call a model?

**A:** “No. It is only text that future prompt code can include.”

### 42. Why use a preamble instead of relying only on pattern matching?

**A:** “An attacker may not use a known phrase. The preamble gives the model
explicit instructions, while pattern matching provides a deterministic signal.”

### 43. What happens to CD-1013?

**A:** “The text is detected as prompt-injection policy and assigned security
escalation. It must never export customer records.”

### 44. Can prompt injection change a tool call by itself?

**A:** “No, not when tool registry approval and application policy controls are
used. P7-2 provides prompt defense; P6 tools provide execution controls.”

### 45. Is prompt wrapping a security guarantee?

**A:** “No. It is a defensive boundary. Authentication, authorization,
tool policy, output validation, and human approval remain necessary.”

## P7-3 — Customer output validation

### 46. What is `validate_customer_output()`?

**A:** “It validates proposed customer-facing text and returns whether it is
safe plus a list of structured violation codes.”

### 47. Why return violation codes instead of only raising an exception?

**A:** “Codes let future workflow nodes make explicit decisions and raise risk
without parsing free-text errors.”

### 48. What violation codes can it return?

**A:** “It can return `empty_output`, `internal_url`, `secret`, and
`other_customer_data`.”

### 49. What is blocked as an internal URL?

**A:** “Private IP addresses, localhost, backend/database/Redis/Qdrant hosts,
`.internal` hosts, internal protocols, `/api/v1`, `/health`, and `kb://`
references.”

### 50. Which secrets are blocked in customer output?

**A:** “Password or API-key assignments, bearer tokens, JWT values, URL
credentials, and card numbers.”

### 51. What card pattern does the validator detect?

**A:** “It looks for a 13-to-19 digit-style sequence after allowing spaces or
hyphens between digits.”

### 52. How is another-customer data detected?

**A:** “The validator receives allowed and disallowed customer IDs and names.
It removes allowed values, then searches the reply for remaining other-customer
identifiers.”

### 53. Can an allowed customer name appear in the reply?

**A:** “Yes. The name is removed from disallowed values, so it does not
automatically trigger a violation.”

### 54. Why allow public support URLs?

**A:** “Public customer-facing article links are useful. The validator targets
internal hosts and infrastructure paths, not normal public documentation.”

### 55. What happens when validation fails?

**A:** “The caller receives structured violations. A future workflow can block
the reply and raise high risk.”

### 56. Does P7-3 currently send or store replies?

**A:** “No. It validates text; later workflow and API code decide whether to
show or send it.”

### 57. Why validate after model generation rather than only before the model?

**A:** “Prompt instructions reduce risk, but they do not guarantee the model's
output. Output validation is a final content gate.”

### 58. What happens if the reply is empty?

**A:** “It receives `empty_output` and is rejected.”

### 59. Can several violations be returned together?

**A:** “Yes. The validator can collect internal URL and secret violations,
deduplicate them, and return all relevant codes.”

### 60. Is output validation a separate layer from P7-2?

**A:** “Yes. P7-2 protects input and prompt boundaries. P7-3 protects generated
output. Both are needed.”

## P7-4 — Secret scrub

### 61. What is `scrub()`?

**A:** “It is a shared text-redaction function that replaces common secrets and
payment identifiers with `[REDACTED]`.”

### 62. What does `SECRET_PATTERNS` contain?

**A:** “It contains patterns for private-key blocks, credential assignments,
bearer and JWT tokens, URL credentials, sensitive query values, AWS-style keys,
and card numbers.”

### 63. Why have both `validate_customer_output()` and `scrub()`?

**A:** “Validation decides whether to allow the complete output. Scrubbing
preserves useful text while replacing sensitive values.”

### 64. What is the difference between a secret and a card number?

**A:** “They are both sensitive identifiers. Card numbers are payment data;
secrets include passwords, API keys, credentials, tokens, and private keys.”

### 65. What does `scrub()` redact in URL credentials?

**A:** “It preserves the protocol and replaces the username/password portion
before `@` with `[REDACTED]`.”

### 66. How are bearer tokens handled?

**A:** “The token text is replaced by `[REDACTED]`, while `Bearer` is preserved
in a standard bearer assignment.”

### 67. How are private-key blocks handled?

**A:** “The entire BEGIN/END private-key block is replaced with `[REDACTED]`.”

### 68. How are card numbers handled?

**A:** “The card-number pattern is replaced as `[REDACTED]`, including spaced
or hyphenated digits.”

### 69. What AWS-style keys are detected?

**A:** “The scrubber recognizes AKIA and ASIA prefixes followed by 16 uppercase
alphanumeric characters.”

### 70. How is the scrubber used in `CustomerService`?

**A:** “`get_detail()` loads memory notes and calls `scrub(note.content)` before
placing the content in the API response.”

### 71. Does P7-4 update stored database notes?

**A:** “At the current implementation, it scrubs at read/API display. Future
memory-write code must call it before persistence as well.”

### 72. Is exact raw ticket text stored in memory?

**A:** “No. The intended later memory design stores permitted summaries and
troubleshooting details, not raw ticket bodies.”

### 73. Does scrubbing guarantee no secret remains?

**A:** “No. It covers recognized patterns. A completely unknown custom secret
format could escape pattern matching.”

### 74. Where should scrubbing run in a complete workflow?

**A:** “It should run before memory persistence and again before memory is
returned or inserted into prompts.”

### 75. Why is scrubbing useful even if validation also exists?

**A:** “Validation may block a full reply, while scrubbing preserves safe parts
of internal or memory text and removes sensitive values.”

## Architecture and layering

### 76. Which file owns policy?

**A:** “`agents/rules.py` owns deterministic escalation, category, and severity
policy.”

### 77. Which file owns text guardrails?

**A:** “`backend/app/core/guardrails.py` owns injection, output-validation,
wrapping, and secret scrubbing helpers.”

### 78. Which file owns prompt security wording?

**A:** “`agents/prompts.py` re-exports the shared `SECURITY_PREAMBLE` from the
core guardrails module.”

### 79. Which service applies memory scrubbing?

**A:** “`CustomerService` calls `scrub()` before memory notes are returned in a
customer detail response.”

### 80. Do API routers contain business guardrail logic?

**A:** “No. The intended design keeps policy and guardrails in reusable modules
and services, not in HTTP route handlers.”

### 81. Do rules write SQL?

**A:** “No. P7-1 rules operate on Python text and enums. Repositories own
database access.”

### 82. Do guardrails import agents?

**A:** “The core guardrails module does not depend on agent implementation.
Agents can import guardrail helpers.”

### 83. Why keep P7 in the core and agents folders?

**A:** “Core guardrails are reusable application safety helpers. Agent rules
live in `agents/` because escalation and model decision policy belong to agent
behavior.”

### 84. How does P7 fit with P6 tool policy?

**A:** “P6 decides whether a tool is registered and whether an action needs
approval. P7 decides policy risk and protects text. They enforce separate
parts of safe execution.”

### 85. Should P7 policy replace human approval?

**A:** “No. Policy decides clear risk and escalation. Human approval is still
required for consequential actions such as refunds or setting resets.”

## Testing and validation

### 86. How is P7-1 tested?

**A:** “`test_policy_rules.py` verifies security, data loss, deletion, dispute,
injection, raise-only severity, and category behavior.”

### 87. How is P7-2 tested?

**A:** “`test_guardrail_injection.py` verifies the preamble, untrusted wrapping,
delimiter escaping, known injection phrases, and benign text.”

### 88. How is P7-3 tested?

**A:** “`test_customer_output_validation.py` verifies empty output, internal
URLs, secrets, card numbers, other-customer data, public URLs, and allowed
customer context.”

### 89. How is P7-4 tested?

**A:** “`test_secret_scrub.py` verifies credential assignments, bearer and JWT
tokens, URL credentials, cards, AWS keys, private-key blocks, and safe text.”

### 90. Is customer memory display also tested?

**A:** “Yes. The customer API tests verify that memory containing
`Password=...` is returned with `[REDACTED]` and the secret value is absent.”

### 91. What local test count passed?

**A:** “The full offline suite passed 165 tests after P7-4.”

### 92. Did the test suite use Docker or cloud providers?

**A:** “No. It used offline pytest, fake/local dependencies, and in-memory
SQLite where needed.”

### 93. Did Ruff pass?

**A:** “Yes. Ruff checks passed for the relevant Phase 7 implementation and test
files.”

## Status and limitations

### 94. Are P7-1 through P7-4 complete?

**A:** “Yes, they are marked completed in `TASK.md` and have focused tests.”

### 95. Are specialist agents implemented in Phase 7?

**A:** “No. Agents belong to later phases. P7 provides components they will call.”

### 96. Is the LangGraph workflow implemented?

**A:** “No. Graph nodes and routing are later work.”

### 97. Is a human approval screen implemented?

**A:** “No. P7 policy raises risk and routes cases, but approval UI and persisted
decisions remain later phases.”

### 98. Is Docker implemented?

**A:** “No. There is no Dockerfile or Compose configuration in this repository.
Phase 7 runs inside the Python process.”

### 99. Can pattern matching be the only security strategy?

**A:** “No. It should be combined with authentication, authorization,
tool-policy enforcement, secure data storage, provider controls, output checks,
logging, and human review.”

### 100. What is the strongest final interview answer for Phase 7?

**A:** “Phase 7 creates defense in depth around future AI decisions: deterministic
rules win for policy cases, ticket text is wrapped as untrusted, replies are
validated for leaks and wrong-customer data, and secrets are scrubbed before
memory use.”
