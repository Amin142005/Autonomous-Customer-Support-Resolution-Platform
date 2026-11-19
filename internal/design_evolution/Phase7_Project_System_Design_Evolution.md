# Phase 7 — Project System Design Evolution

This document follows the CloudDesk rules and guardrail design from the
Phase 6 tool and integration baseline through P7-1 to P7-4. It shows the
simplest starting shape, how each subtask changes the design, and the complete
policy and safety architecture at the end of Phase 7.

## Phase 7 goal

Phase 7 makes deterministic policy and safe handling of untrusted content
available before model-assisted decisions.

The subtask evolution is:

```mermaid
flowchart LR
    P71["P7-1: Escalation and severity rules"]
    P72["P7-2: Injection wrapping and security preamble"]
    P73["P7-3: Customer output validation"]
    P74["P7-4: Secret scrub"]

    P71 --> Final["Rules-first, guarded support workflow"]
    P72 --> Final
    P73 --> Final
    P74 --> Final
```

P7-1 establishes policy decisions. P7-2 protects prompt boundaries. P7-3 protects
generated customer replies. P7-4 protects memory and persisted text.

## Starting design — Phase 6 tool system without policy guardrails

At the beginning of Phase 7, CloudDesk already has:

- protected APIs;
- ticket and customer repositories;
- knowledge retrieval;
- a central tool registry;
- tool approval policy;
- mock integrations.

The application can execute controlled tools, but it does not yet have the
complete deterministic policy and text-safety layer described for the agents.
It lacks one combined design for:

- policy escalation and named teams;
- severity policy that raises rather than lowers urgency;
- prompt-injection scanning;
- untrusted-content boundaries;
- customer-reply validation;
- centralized secret and card-number scrubbing.

```mermaid
flowchart LR
    Ticket["Support ticket"]
    Ticket --> Model["Future model or agent"]
    Model --> Decision["Proposed category, severity, reply, or tool action"]
    Decision --> Tools["ToolRegistry"]
    Tools --> DB["Database or mock integration"]
    Decision --> Reply["Customer-facing output"]
    Reply --> Customer["Customer or support console"]

    Policy["P7 policy and guardrails"] -. "Not implemented yet" .-> Model
    Policy -. "Not implemented yet" .-> Decision
    Policy -. "Not implemented yet" .-> Reply
```

### Starting limitations

- Clear policy cases could be left to model probability.
- The model could lower a severity that policy requires to be higher.
- Ticket text could be presented to a prompt without an explicit untrusted
  boundary.
- Prompt-injection text could be confused with instructions.
- A generated reply could expose an internal URL or secret.
- Stored memory text could retain passwords, tokens, or card numbers.

Phase 7 adds separate guardrail components before the future agent workflow
uses model-generated decisions.

## Evolution by subtask

### P7-1 — Escalation and severity rules

**Design change:** clear support-policy cases become deterministic lookups
instead of model probability.

`agents/rules.py` defines `ESCALATION_RULES`, category rules, severity rules,
and functions that return policy matches.

```mermaid
flowchart LR
    Ticket["Ticket subject and body"]
    Ticket --> Normalize["Normalize text"]
    Normalize --> Escalation["matching_escalation_rules"]
    Normalize --> Category["rule_category"]
    Normalize --> Severity["rule_severity"]

    Escalation --> Matches["Matched rule names and teams"]
    Category --> CategoryResult["Deterministic or model category"]
    Severity --> SeverityResult["Raised-or-preserved severity"]
```

The escalation rules currently cover:

| Rule | Team | Required severity |
|---|---|---|
| Security breach | Security team | Critical |
| Data loss | Data recovery team | Critical |
| Workspace deletion | Account deletion team | High |
| Payment dispute | Billing and payment dispute team | High |
| Enterprise outage | Incident response team | Critical |
| Legal request | Legal and compliance team | High |
| Prompt injection | Security team | Critical |

The severity design uses a rank:

```text
low 1 < medium 2 < high 3 < critical 4
```

The implementation compares the model value with the deterministic requirement.
It only changes severity when the required rank is higher.

```mermaid
flowchart TD
    Text["Ticket text"]
    Text --> Critical{"Critical policy terms?"}
    Critical -->|"Yes"| RequiredCritical["Required severity: critical"]
    Critical -->|"No"| High{"High policy terms?"}
    High -->|"Yes"| RequiredHigh["Required severity: high"]
    High -->|"No"| RequiredLow["Required or category severity"]

    RequiredCritical --> Compare["Compare required and model severity"]
    RequiredHigh --> Compare
    RequiredLow --> Compare

    Model["Model severity"]
    Model --> Compare
    Compare -->|"Required is higher"| Raise["Return required severity"]
    Compare -->|"Model is higher"| Preserve["Return model severity"]
```

Category rules can override a model category for clear subjects. A valid model
category is preserved when no deterministic rule matches.

**Result:** P7-1 gives later agent code predictable escalation, category, and
severity decisions for policy subjects.

### P7-2 — Injection wrapping and security preamble

**Design change:** ticket-supplied text becomes explicitly untrusted prompt
data, and prompt builders receive a shared security preamble.

`backend/app/core/guardrails.py` owns the injection scanner and wrapping
helpers. `agents/prompts.py` exposes `SECURITY_PREAMBLE` for future prompt
builders.

```mermaid
flowchart LR
    Ticket["Ticket subject and body"]
    Ticket --> Scan["scan_for_injection"]
    Scan -->|"Likely injection"| Risk["Flag for policy/security handling"]
    Scan -->|"Normal text"| Continue["Continue processing"]
    Ticket --> Wrap["wrap_untrusted"]
    Wrap --> Envelope["<untrusted_content> ... </untrusted_content>"]
    Preamble["SECURITY_PREAMBLE"] --> Prompt["Prompt builder"]
    Envelope --> Prompt
```

The scanner checks common instruction and export patterns, including:

- ignore or disregard instructions;
- reveal system or hidden prompts;
- bypass approval or policy;
- export customer records;
- invoke tools or commands;
- developer-mode or jailbreak language.

The wrapper escapes any attempt to insert `<untrusted_content>` or
`</untrusted_content>` inside the text. That protects the delimiter boundary
from being broken by ticket content.

```mermaid
sequenceDiagram
    participant Ticket as Ticket text
    participant Guard as P7-2 guardrail
    participant Prompt as Future prompt builder
    participant Model as AI model

    Ticket->>Guard: scan_for_injection(text)
    Guard-->>Ticket: injection flag
    Ticket->>Guard: wrap_untrusted(text)
    Guard-->>Prompt: escaped untrusted block
    Guard-->>Prompt: SECURITY_PREAMBLE
    Prompt->>Model: application instructions + untrusted envelope
    Model-->>Prompt: proposed judgment
```

The preamble tells the model that envelope content is customer-supplied data,
not instructions, and that application rules still control the decision.

**Result:** P7-2 separates customer language from prompt instructions, while
P7-1 remains responsible for deterministic policy decisions.

### P7-3 — Customer output validation

**Design change:** generated reply text passes through a final safety gate
before it can be shown or sent.

`validate_customer_output()` returns:

```text
(is_valid, violation_code_list)
```

The violation codes are structured, not free-text:

- `empty_output`;
- `internal_url`;
- `secret`;
- `other_customer_data`.

```mermaid
flowchart TD
    Reply["Generated customer reply"]
    Reply --> Empty{"Empty or whitespace?"}
    Empty -->|"Yes"| EmptyResult["Reject: empty_output"]
    Empty -->|"No"| URLs{"Internal URL or private host?"}
    URLs -->|"Yes"| InternalResult["Reject: internal_url"]
    URLs -->|"No"| Secrets{"Secret, token, or card?"}
    Secrets -->|"Yes"| SecretResult["Reject: secret"]
    Secrets -->|"No"| Customers{"Other customer ID or name?"}
    Customers -->|"Yes"| CustomerResult["Reject: other_customer_data"]
    Customers -->|"No"| Safe["Return valid"]

    EmptyResult --> Violations["Deduplicated violation codes"]
    InternalResult --> Violations
    SecretResult --> Violations
    CustomerResult --> Violations
```

The validator considers both allowed and disallowed customer identities.
Allowed IDs and names are removed from disallowed sets before checking text.

```mermaid
flowchart LR
    Allowed["Allowed customer ID and name"]
    Disallowed["Known other-customer IDs and names"]
    Text["Reply text"]

    Allowed --> Remove["Subtract allowed values from other-customer sets"]
    Disallowed --> Remove
    Remove --> Check["Search remaining values in reply"]
    Text --> Check
    Check -->|"Match found"| Block["other_customer_data"]
    Check -->|"No match"| Continue["Continue validation"]
```

It rejects internal and private addresses, but allows a normal public support
URL.

**Result:** P7-3 becomes a structured answer gate. A later workflow can
convert violations into high risk and block a reply.

### P7-4 — Secret scrub

**Design change:** common sensitive text is redacted centrally before memory
content is read or persisted.

`SECRET_PATTERNS` and `scrub()` live in `backend/app/core/guardrails.py`.
The customer service now calls `scrub()` before returning stored memory.

```mermaid
flowchart LR
    Text["Memory or customer-context text"]
    Text --> Blocks["Private-key blocks"]
    Text --> Assignments["Password, API key, token assignments"]
    Text --> Bearer["Bearer and JWT tokens"]
    Text --> URLs["Credentials in URLs"]
    Text --> Query["Sensitive query values"]
    Text --> AWS["AWS-style access keys"]
    Text --> Cards["Card numbers"]

    Blocks --> Redact["Replace with [REDACTED]"]
    Assignments --> Redact
    Bearer --> Redact
    URLs --> Redact
    Query --> Redact
    AWS --> Redact
    Cards --> Redact
    Redact --> SafeText["Safe text with useful content preserved"]
```

`CustomerService.get_detail()` loads memory notes and passes each note through
`scrub()` before constructing the API response.

```mermaid
sequenceDiagram
    participant API as Customer API
    participant Service as CustomerService
    participant Repo as CustomerMemoryRepository
    participant Guard as scrub()
    participant Caller as Support caller

    API->>Service: get_detail(customer_id)
    Service->>Repo: list_for_customer(limit=10)
    Repo-->>Service: stored memory notes
    loop Each memory note
        Service->>Guard: scrub(note.content)
        Guard-->>Service: redacted safe text
    end
    Service-->>API: CustomerDetail
    API-->>Caller: Memory with [REDACTED] values
```

`scrub()` is different from `validate_customer_output()`:

| Operation | Result |
|---|---|
| Validation | Pass or reject the complete output |
| Scrubbing | Preserve useful text while replacing sensitive values |

**Result:** P7-4 centralizes redaction rules and removes duplicate memory
scrubbing code from the customer service.

## End-of-Phase 7 design

The complete design has two related safety paths:

1. **Policy and prompt safety** decide and contain ticket information.
2. **Reply and memory safety** protect outbound and stored text.

```mermaid
flowchart TB
    Ticket["Customer ticket text"]

    subgraph Policy["P7-1 deterministic policy"]
        Category["rule_category"]
        Escalation["matching_escalation_rules"]
        Severity["rule_severity"]
    end

    subgraph PromptSafety["P7-2 prompt safety"]
        Injection["scan_for_injection"]
        Wrap["wrap_untrusted"]
        Preamble["SECURITY_PREAMBLE"]
    end

    subgraph Proposed["Future model or resolution logic"]
        Judgment["Uncertain judgment"]
        CategoryDecision["Category"]
        SeverityDecision["Severity"]
        ReplyDraft["Generated reply draft"]
    end

    subgraph OutputSafety["P7-3 customer-output safety"]
        OutputValidation["validate_customer_output"]
        ViolationCodes["Violation codes"]
    end

    subgraph MemorySafety["P7-4 memory safety"]
        Scrub["scrub"]
        RedactedMemory["Redacted memory"]
    end

    Ticket --> Category
    Ticket --> Escalation
    Ticket --> Severity
    Ticket --> Injection
    Ticket --> Wrap

    Category --> Judgment
    Severity --> Judgment
    Escalation -->|"Rules win"| Escalate["Named team decision"]
    Injection --> Judgment
    Wrap --> Preamble
    Preamble --> Judgment

    Judgment --> CategoryDecision
    Judgment --> SeverityDecision
    Judgment --> ReplyDraft

    ReplyDraft --> OutputValidation
    OutputValidation -->|"Valid"| Customer["Customer-facing reply"]
    OutputValidation -->|"Invalid"| ViolationCodes
    ViolationCodes -->|"Raise risk"| Block["Block or review reply"]

    Ticket --> Scrub
    ReplyDraft --> Scrub
    Scrub --> RedactedMemory
```

The policy path is deterministic for clear cases. The model may assist where
the rules do not decide, but it cannot lower policy severity or replace policy
escalation.

### Complete policy decision flow

```mermaid
flowchart TD
    Ticket["Ticket"]
    Ticket --> Rules{"Known policy match?"}
    Rules -->|"Security, data loss, deletion, dispute, outage, legal"| Policy["Deterministic policy decision"]
    Rules -->|"No direct policy match"| Model["Model judgment in grey area"]

    Policy --> SeverityRaise["Raise severity if required"]
    Policy --> Team["Assign named team"]
    Model --> SeverityCheck["Apply raise-only severity rule"]
    SeverityCheck --> FinalSeverity["Final severity"]
    SeverityRaise --> FinalSeverity

    Team --> Escalation["Escalation decision"]
    FinalSeverity --> Risk["Workflow risk assessment"]

    Ticket --> Injection{"Prompt injection detected?"}
    Injection -->|"Yes"| Security["Security escalation and high risk"]
    Injection -->|"No"| Continue["Continue normal processing"]
```

## Component boundaries

| Component | Owns | Does not own |
|---|---|---|
| `agents/rules.py` | Escalation, category, and severity policy | LLM prompt rendering |
| `backend/app/core/guardrails.py` | Injection, output, and secret safety helpers | Model calls or workflow routing |
| `agents/prompts.py` | Shared security-preamble export | HTTP or database logic |
| `CustomerService` | Applying scrubbed memory to API output | Long-term memory persistence rules |
| Phase 7 tests | Deterministic policy and guardrail verification | Live model or live provider behavior |

The key boundary is that policy and guardrails are pure or service-level Python
helpers. HTTP route code and tool code do not each need to invent separate
injection or secret rules.

## Evolution of risk handling

The design becomes stronger at each subtask:

```mermaid
flowchart LR
    Start["Model-only decision"]
    P71["P7-1: written policy wins"]
    P72["P7-2: ticket text is untrusted"]
    P73["P7-3: reply is validated"]
    P74["P7-4: memory is scrubbed"]
    Final["Defense-in-depth policy and text safety"]

    Start --> P71 --> P72 --> P73 --> P74 --> Final
```

The result is not a single guardrail but four coordinated boundaries:

1. policy decisions;
2. prompt input boundaries;
3. customer output boundaries;
4. memory and context boundaries.

## Validation and honest status

Phase 7 implementation includes:

- escalation and category rules;
- raise-only severity rules;
- injection scanning and delimiter escaping;
- shared security preamble;
- customer-reply validation;
- centralized secret scrubbing;
- memory display integration;
- focused unit tests.

The local offline suite passed 165 tests, and Ruff passed for the relevant
Phase 7 implementation and test files.

The guardrails do not claim complete prompt-injection detection or perfect
secret discovery. Pattern matching is an additional deterministic boundary, not
a replacement for authentication, authorization, secrets management, secure
provider configuration, or human review.

No real model provider or external integration was used in local validation.

## Component reference

| Responsibility | Implementation |
|---|---|
| Escalation, category, and severity rules | [rules.py](../../agents/rules.py) |
| Injection, output, and secret guardrails | [guardrails.py](../../backend/app/core/guardrails.py) |
| Shared security preamble | [prompts.py](../../agents/prompts.py) |
| Memory API scrubbing | [customer_service.py](../../backend/app/services/customer_service.py) |
| Policy rule tests | [test_policy_rules.py](../../tests/unit/test_policy_rules.py) |
| Injection tests | [test_guardrail_injection.py](../../tests/unit/test_guardrail_injection.py) |
| Customer output tests | [test_customer_output_validation.py](../../tests/unit/test_customer_output_validation.py) |
| Secret scrub tests | [test_secret_scrub.py](../../tests/unit/test_secret_scrub.py) |
| Phase task status | [TASK.md](../../TASK.md) |
| Phase exit criteria | [PLAN_PHASE.md](../../PLAN_PHASE.md) |
| Plain-language Phase 7 explanation | [phase7_explained.md](../explain_codebase/phase7_explained.md) |
