# Phase 6 — CloudDesk Tools, Policy, and Mock Integrations

## A plain-language presentation

> **Use this as a speaking script.** It explains Phase 6 for an audience that may
> not have a software background.

Phases 1 through 5 gave CloudDesk a working application foundation, stored
support records, login rules, support APIs, and a knowledge-search system.
Phase 6 gives the application a safe and organized set of actions it is allowed
to perform.

In an airline, not every employee can open every door or change every system.
In the same way, CloudDesk separates “the system can look at information” from
“the system can change something.” Phase 6 establishes the rules, approval gates,
and mock services needed for that separation.

The short version is:

```text
The workflow requests an action
  → the action is checked against the tool registry
  → the policy decides whether approval is required
  → the action is stopped, approved, timed out, or completed
  → the result is returned clearly
  → no real external system is changed by the demo
```

Phase 6 prepares safe actions for later AI workflow phases. It does not yet run
a complete automated support workflow.

## The problem Phase 6 solves

Imagine that CloudDesk's future AI agent believes it can help by changing a
ticket, resetting a workspace setting, or creating a refund request.

If those actions are called directly, several problems could occur:

- the system might not know whether the action is allowed;
- a consequential action might happen without a human approving it;
- an unknown or misspelled action might try to run;
- an external service might delay forever;
- an error might expose secrets or stop the whole workflow.

Phase 6 creates one controlled doorway for every action. The AI and other
application components must use that doorway instead of calling the action
directly.

This is similar to having a building's reception desk approve access rather than
giving every visitor a master key.

## The main idea: tools

A **tool** is a clearly named operation that the software can perform.

The current Phase 6 tools are divided into three groups:

| Tool | What it does | Ordinary permission |
|---|---|---|
| `get_customer` | Reads a basic customer profile | No approval |
| `get_subscription` | Reads a customer's subscriptions | No approval |
| `get_ticket_history` | Reads previous ticket summaries | No approval |
| `search_docs` | Searches support articles and returns citations | No approval |
| `check_service_status` | Reads a mocked service status | No approval |
| `update_ticket` | Changes supported ticket details | No approval in the tool policy |
| `reset_demo_setting` | Resets a workspace setting | Human approval |
| `create_refund_request` | Creates a simulated refund request | Approval according to policy |

Read-only tools do not change CloudDesk records. Write tools are designed to
change records or interact with an external-style integration, so they receive
stricter policy checks.

Every tool has a short description, a named set of inputs, and an asynchronous
implementation. “Asynchronous” means the system can wait for an action without
blocking every other operation while it waits.

## The four Phase 6 pieces

### 1. P6-1 — A central tool registry and approval policy

P6-1 creates the **ToolRegistry**, which acts as an action directory and security
desk.

Before an action can run, the registry asks:

1. Is this tool registered?
2. Does the policy require approval?
3. Has approval been given?
4. Is the implementation still running within the allowed time?

Only a registered tool can execute. A tool that is not registered is rejected.
This prevents an accidentally named action or an unknown action from bypassing
CloudDesk's controls.

The policy is separate from the registry:

- the registry manages registration and execution;
- the policy decides whether an action needs approval.

The approval decision follows these rules:

- unknown tools always require approval;
- `reset_demo_setting` always requires approval;
- refunds require approval by default;
- refunds can follow a configured threshold if global refund approval is
  disabled;
- invalid or missing refund amounts require approval;
- ordinary read tools do not require approval;
- a tool that is explicitly declared as requiring approval cannot bypass that
  declaration.

This separation means the approval rules can change without rewriting how tools
are invoked or executed.

### 2. P6-2 — Read-only support tools

P6-2 creates tools for gathering context without changing anything.

`get_customer` returns a basic profile. `get_subscription` returns subscription
records. `get_ticket_history` returns prior ticket summaries but excludes the
original ticket body.

`search_docs` searches the knowledge system created in Phase 5 and returns cited
evidence. `check_service_status` asks the mock service-status integration for
information about identity, storage, API, billing, collaboration, or another
configured service.

These tools are useful to a future support agent because they allow investigation:

```text
What account are we supporting?
  → get_customer

What plan and subscriptions apply?
  → get_subscription

What has happened before?
  → get_ticket_history

What official guidance exists?
  → search_docs

Is a service currently healthy?
  → check_service_status
```

The tools read through repository or integration interfaces. They do not contain
their own direct database connection bypass or live external API call.

### 3. P6-3 — Approval-gated write tools

P6-3 adds tools that can change a ticket or prepare a consequential action.

The `update_ticket` tool can update supported fields such as:

- ticket status;
- support summary;
- category;
- severity;
- subject;
- assignee.

It does not replace the customer's original message body. It validates the
ticket ID and at least one update field, then uses the ticket repository to
save the change.

The `reset_demo_setting` tool resets a workspace setting through the mock
workspace administrator. It always requires approval.

The `create_refund_request` tool prepares a simulated refund. It validates the
customer ID, reason, and positive finite refund amount. In the demo, it creates
a mock receipt but never charges real money.

The write tools are not run automatically by a direct call. Every call goes
through the registry's approval check.

### 4. P6-4 — Mock integrations

P6-4 provides local simulated services for development and testing.

The mock bundle contains four adapters:

- billing;
- email;
- service status;
- workspace administration.

Each adapter follows a common interface, or contract. That means the rest of
the application asks for a billing action or service status without depending
on a real payment, email, or account-management vendor.

For example, a mock refund:

1. receives a customer ID, amount, and reason;
2. validates the amount;
3. creates a simulated receipt;
4. records the request in memory;
5. clearly marks the result as `simulated`.

No real refund is issued. A mock email also records that a simulated message
was sent and does not send a real email.

Mock service statuses are designed for local demonstrations. Identity may be
shown as degraded, while storage or collaboration may be operational. The
team can test incident handling without relying on a live service.

## How an action passes through the system

```text
Future AI workflow or application component
  └─ Names a tool and supplies its inputs
       └─ ToolRegistry receives the request
            ├─ Is the tool unknown?
            │    └─ Return “unknown tool” after approval checks
            │
            ├─ Does policy require approval?
            │    └─ Without approval: stop before running the action
            │
            └─ Is approval present?
                 └─ Run the registered tool through a time limit
                      ├─ Success: return the tool's data
                      ├─ Timeout: return an explicit timeout result
                      └─ Error: return an explicit, sanitized error
```

The important control is that approval is checked before the tool's actual
implementation runs. It is not an approval message written after a side effect
has already happened.

For a reset, for example:

```text
Request reset_demo_setting
  → Registry checks policy
  → Approval is missing
  → No workspace setting is changed
  → A clear approval-required result is returned
```

After approval:

```text
Request the same reset with approved=true
  → Registry checks policy again
  → Registered mock tool is invoked
  → Workspace setting is changed only in the mock integration
  → A simulated success result is returned
```

The same registry path is used whether an action is blocked, approved, or
automatically permitted. That consistency makes testing and auditing easier.

## How refund approval works

Refund approval is intentionally conservative.

By default, `APPROVAL_REQUIRED_FOR_REFUNDS=true`, so every refund request needs
human approval. CloudDesk will not allow the future AI workflow to create a
refund request alone.

The system can also be configured with a maximum amount that can be handled
without approval. If the global approval setting is turned off, the policy can
compare the requested amount to `MAX_REFUND_WITHOUT_APPROVAL`.

For example:

| Refund amount | Global refund approval | Policy result |
|---|---:|---|
| Any amount | Enabled | Approval required |
| $25.00 | Disabled; maximum $25 | No approval required |
| $25.01 | Disabled; maximum $25 | Approval required |
| Missing or invalid | Disabled | Approval required |

The default demonstration setting uses no approved zero-cost refund threshold:
any refund requires approval.

## How errors are handled

Each tool call returns a `ToolResult`, which is a small, consistent description
of success or failure.

Possible results include:

| Result | Plain-language meaning |
|---|---|
| Success | The registered tool completed |
| Approval required | A person must approve before anything changes |
| Unknown tool | The requested action is not registered |
| Timeout | The tool took too long |
| Execution failed | The tool found an error or integration failure |

A tool failure becomes a result that the workflow can inspect. It does not crash
the workflow merely because a mock integration or external-style action failed.

If an implementation throws an exception, the registry reports a general failure
type such as `Execution failed (LookupError)`. It does not expose exception text
from inside the system. This protects information such as API keys or internal
messages from leaking into a result.

## Where the components fit

```text
Future support workflow
  └─ Tool request
       └─ ToolRegistry
            ├─ ToolPolicy
            │    └─ Approval or threshold decision
            │
            ├─ Registered read-only tools
            │    ├─ Database repositories
            │    ├─ Knowledge service
            │    └─ Service-status mock
            │
            └─ Registered write tools
                 ├─ Ticket repository
                 └─ Mock integrations
                      ├─ Billing
                      ├─ Workspace administration
                      ├─ Email
                      └─ Service status
```

The responsibilities are deliberately separated:

- the **registry** controls execution;
- the **policy** controls approval;
- **read-only tools** gather context;
- **write tools** perform supported changes;
- **repositories** handle database operations;
- **integration protocols** define external actions;
- **mock integrations** provide safe demonstration behavior;
- **ToolResult** makes success and failure predictable.

## Safety and boundaries

- All tool execution goes through the registry.
- Unknown tools require approval and are not invoked automatically.
- Refunds and workspace resets are approval-gated.
- Ticket updates do not alter the original message body.
- Mock refunds and account-setting changes are not real operations.
- A tool call has a configurable timeout.
- Tool exceptions are converted into explicit, sanitized results.
- Read-only tools do not change support records.
- The mock email adapter does not send real email.
- No real money, real account settings, or real email are used in Phase 6.

## What Phase 6 does not do

Phase 6 does not yet:

- provide a human approval screen;
- record the approval in the ticket approval workflow;
- resume a paused AI graph after approval;
- send a real refund or real email;
- connect to a live billing or workspace system;
- decide which tool a customer issue needs;
- run an automated agent workflow.

Those responsibilities belong to later workflow and approval phases.

## Validation and honest status

The Phase 6 implementation includes:

- a central async tool registry;
- policy-based approval checks;
- five read-only support tools;
- ticket update and mock write tools;
- a simulated refund action;
- a simulated workspace-setting reset;
- billing, email, status, and workspace mock integrations;
- explicit success, approval, timeout, unknown-tool, and execution-failure results.

The focused implementation checks include 24 passing tool-policy, tool-registry,
and write-tool tests. The tests confirm that approval is checked before a side
effect, that approved tools execute through the same registry path, that
unknown tools cannot run, and that timeout and exception cases return explicit
results.

Mock behavior is validated locally. No real billing, email, or account provider
was used.

## Short answers for likely questions

**What is the purpose of a tool?**  
It gives the system a clearly named and controlled action with validated inputs.

**Why not let the AI call an action directly?**  
Direct calls could bypass approval, create inconsistent errors, or change
customer data without a recorded safeguard.

**Why is a registry important?**  
It provides one place to register tools, check policy, enforce timeouts, and
return consistent results.

**Why do refunds need approval?**  
A refund is consequential: it affects billing or customer value, so Phase 6
requires a human decision instead of allowing the AI to act independently.

**What happens if a tool is not registered?**  
The system returns an unknown-tool result and does not execute any implementation.

**What happens if a tool takes too long?**  
The registry stops waiting after the configured timeout and returns a timeout
result.

**How are demo integrations kept safe?**  
They are mock implementations that return simulated receipts or modify only
their own in-memory demo state.

**Does Phase 6 send an actual refund or email?**  
No. Refund and email operations are mocked and explicitly marked as simulated.
