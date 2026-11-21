# Phase 10 — Project System Design Evolution

This document follows the CloudDesk support-workflow design from the isolated specialist components available at the start of Phase 10 through P10-1 to P10-6. It shows the simple starting shape, the design introduced by each subtask, and the complete Phase 10 architecture.

## Phase 10 goal

Before Phase 10, CloudDesk already had specialist agents that could understand tickets, gather customer context, retrieve knowledge, diagnose problems, propose resolutions, and evaluate escalation. Those specialists existed as individual components, but they were not yet arranged into one dependable workflow.

Phase 10 gives the application:

- one shared workflow state;
- a checkpointer for resumable progress;
- named graph nodes for each stage;
- deterministic routing for policy, approval, and low-risk cases;
- workflow run and status APIs;
- persisted node, tool, model, and completion events;
- an events API for support operators.

The subtask evolution is:

```mermaid
flowchart LR
    P101["P10-1: Shared state and checkpointer"]
    P102["P10-2: Supervisor nodes"]
    P103["P10-3: Investigation nodes"]
    P104["P10-4: Resolution and risk nodes"]
    P105["P10-5: Graph wiring and run API"]
    P106["P10-6: Workflow tracer and events API"]

    P101 --> P102
    P102 --> P103
    P103 --> P104
    P104 --> P105
    P105 --> P106
```

The result is not just a collection of AI components. It is a controlled support-workflow system with a visible route, persistent state, and an audit trail.

## Starting design — specialist components without one workflow

At the beginning of Phase 10, CloudDesk already has the specialist components from earlier phases:

- Supervisor logic for classification and severity;
- Customer context tools;
- Knowledge search and similar-case retrieval;
- Troubleshooting diagnosis;
- Resolution planning;
- Escalation policy logic;
- workflow state and checkpointer foundations;
- workflow database models and repositories.

The missing design element is coordination.

```mermaid
flowchart LR
    Ticket[Support ticket] --> Supervisor[Supervisor agent]
    Ticket --> Customer[Customer agent]
    Ticket --> Knowledge[Knowledge agent]
    Ticket --> Diagnose[Troubleshooting agent]
    Ticket --> Resolution[Resolution agent]
    Ticket --> Escalation[Escalation agent]

    Supervisor --> Separate1[Individual result]
    Customer --> Separate2[Individual result]
    Knowledge --> Separate3[Individual result]
    Diagnose --> Separate4[Individual result]
    Resolution --> Separate5[Individual result]
    Escalation --> Separate6[Individual result]

    Separate1 -. "No common journey" .-> Missing[Missing orchestration and trace]
    Separate2 -.-> Missing
    Separate3 -.-> Missing
    Separate4 -.-> Missing
    Separate5 -.-> Missing
    Separate6 -.-> Missing
```

### Starting limitations

- The system knows the specialist operations but does not have one authoritative path between them.
- Completed stages are not guaranteed to be recorded together.
- A service needs a way to save progress after every node.
- There is no complete HTTP start/status lifecycle for a workflow.
- Operators cannot yet follow one chronological activity trail for a run.
- Approval and later execution behavior need a graph route that can pause and resume.

Phase 10 adds a coordinator around these specialists. LangGraph is that coordinator.

## Design principle — shared state and named stages

The workflow is designed as a sequence of named stages with a shared case file.

```mermaid
flowchart LR
    Start[Ticket received] --> State[Create shared workflow state]
    State --> Node1[Run named node]
    Node1 --> Update[Add partial result to state]
    Update --> Save[Save state and event]
    Save --> Next{More stages?}
    Next -->|Yes| Node1
    Next -->|No| Complete[Complete or pause workflow]
```

The shared state includes:

- ticket identifiers and ticket data;
- classification and severity;
- injection detection;
- customer context;
- knowledge evidence and previous cases;
- diagnosis;
- resolution plan;
- escalation decision;
- risk and approval fields;
- current node;
- completed nodes;
- errors;
- total token usage.

The graph uses partial updates rather than replacing the entire case. This allows completed nodes and errors to accumulate, and token usage to increase as each model call occurs.

```mermaid
classDiagram
    class SupportState {
        ticket_id
        ticket_number
        customer_id
        thread_id
        workflow_id
        ticket
        ticket_summary
        classification
        severity
        injection_detected
        customer_context
        evidence
        previous_cases
        diagnosis
        resolution
        escalation
        risk_level
        escalation_required
        approval_required
        approval_status
        paused
        current_node
        completed_nodes
        errors
        token_usage
    }

    class WorkflowRun {
        workflow ID
        ticket ID
        status
        thread ID
        saved state
    }

    class WorkflowEvent {
        event type
        node name
        payload
        duration
        token usage
        timestamp
    }

    SupportState --> WorkflowRun : serialized into run state
    WorkflowRun --> WorkflowEvent : emits node and model activity
```

## P10-1 — Workflow state and checkpointer

P10-1 establishes persistence conventions before all nodes are connected.

### Design change

The workflow moves from a one-time Python function call to a stateful process with a resumable history.

```mermaid
flowchart LR
    StateFile[SupportState case file] --> NodeA[Workflow node]
    NodeA --> Partial[Partial state update]
    Partial --> Reducer{Reducer type}

    Reducer --> Completed[Append completed node]
    Reducer --> Errors[Append errors]
    Reducer --> Usage[Add token usage]
    Reducer --> Normal[Update or replace normal field]

    Completed --> Checkpoint[Checkpointer saves state]
    Errors --> Checkpoint
    Usage --> Checkpoint
    Normal --> Checkpoint
```

The checkpointer is not the database workflow record. It has a different job:

- the workflow database run records the application status;
- the checkpointer preserves LangGraph execution state and thread identity;
- the workflow service saves a JSON-safe snapshot in the run record.

```mermaid
sequenceDiagram
    participant Node as Graph node
    participant State as SupportState
    participant CP as Checkpointer
    participant DB as Workflow run record

    Node->>State: Return partial update
    State->>CP: Save graph state for this thread
    State->>DB: Save JSON-safe workflow snapshot
    CP-->>Node: State available for continuation
```

### P10-1 result

The system can remember state, append a complete activity history, add model usage across nodes, and resume a known workflow thread later.

## P10-2 — Supervisor graph nodes

P10-2 turns the supervisor into the beginning of the workflow graph.

### Design change

Ticket understanding becomes the first named stage, followed by severity classification and an internal summary.

```mermaid
flowchart LR
    Start[Workflow start] --> Understand[understand_ticket]
    Understand --> Classify[classify_severity]
    Classify --> Summary[ticket_summary]
    Summary --> Investigate[Continue to customer context]
```

Each node returns a small partial update:

```mermaid
sequenceDiagram
    participant Graph as LangGraph
    participant Understand as Understand node
    participant Severity as Severity node
    participant TicketSummary as Summary node

    Graph->>Understand: Read ticket and state
    Understand-->>Graph: Classification, injection flag, usage
    Graph->>Severity: Read classification and original ticket
    Severity-->>Graph: Severity assessment and final injection flag
    Graph->>TicketSummary: Read ticket, classification, and severity
    TicketSummary-->>Graph: Internal ticket summary
```

The same policy approach is preserved: clear rule conditions can raise severity or detect suspicious instructions, while AI judgement provides a result for less certain cases.

### P10-2 result

Every workflow now begins with a structured understanding stage and a known completed-node trail.

## P10-3 — Investigation graph nodes

P10-3 adds customer context, knowledge evidence, and diagnosis to the graph.

### Design change

The workflow becomes a research pipeline rather than a single prompt.

```mermaid
flowchart TD
    Ticket[Ticket and classification] --> Customer[customer_context]
    Ticket --> Knowledge[knowledge_retrieval]

    Customer --> Context[Customer, subscriptions, workspaces, history, memory]
    Knowledge --> Evidence[Approved evidence and similar cases]

    Context --> Troubleshoot[troubleshooting]
    Evidence --> Troubleshoot
    Ticket --> Troubleshoot

    Troubleshoot --> Diagnosis[Probable causes, checks, numbered steps]
```

The node sequence is:

```mermaid
sequenceDiagram
    participant Graph as LangGraph
    participant Customer as Customer node
    participant Knowledge as Knowledge node
    participant Diagnose as Troubleshooting node

    Graph->>Customer: Customer ID and ticket context
    Customer-->>Graph: Customer context or partial error
    Graph->>Knowledge: Query, category, and retrieval mode
    Knowledge-->>Graph: Evidence and similar cases
    Graph->>Diagnose: Ticket, evidence, and customer context
    Diagnose-->>Graph: Diagnosis and model usage
```

Tool failures do not stop this stage. A missing customer record or search result produces partial state and an error, allowing the graph to continue when possible.

### P10-3 result

Before a resolution is prepared, the graph can gather account context, approved knowledge, and likely causes through separate registered-tool paths.

## P10-4 — Resolution and risk nodes

P10-4 prepares a proposed answer and decides how safely the workflow should continue.

### Design change

Resolution planning is separated from risk routing.

```mermaid
flowchart LR
    Diagnosis[Diagnosis and evidence] --> Resolution[resolution_planning]
    Resolution --> Plan[Reply, notes, steps, and actions]
    Plan --> Risk[risk_check]

    Risk --> High{High-risk conditions?}
    High -->|Approval action| Approval[Human approval route]
    High -->|Policy or critical risk| Escalate[Escalation route]
    High -->|Ordinary low-risk case| Execute[Low-risk execution route]
```

The risk node checks:

- consequential actions;
- policy-rule matches;
- critical severity;
- prompt-injection detection;
- invalid customer-facing output.

```mermaid
sequenceDiagram
    participant Graph as LangGraph
    participant Resolution as Resolution node
    participant Risk as Risk node

    Graph->>Resolution: Ticket, diagnosis, evidence, context, severity
    Resolution-->>Graph: Customer reply and deterministic action proposals
    Graph->>Risk: Resolution, approval flags, policy and severity

    alt Approval-required action
        Risk-->>Graph: High risk and approval_required
    else Policy or critical risk
        Risk-->>Graph: High risk and escalation_required
    else Ordinary case
        Risk-->>Graph: Low or medium risk
    end
```

A billing refund or setting reset remains approval-gated. Policy decisions such as a security breach or data-loss situation take precedence over an ordinary model opinion.

### P10-4 result

The graph produces both a resolution plan and a risk decision. The next stage does not need to guess whether action is safe.

## P10-5 — Graph wiring and run API

P10-5 joins every node into a compiled LangGraph workflow and exposes HTTP start/status operations.

### Design change

The application moves from callable specialist nodes to a persistent workflow service with background execution.

```mermaid
flowchart TD
    Agent[Support agent] --> RunAPI[POST ticket run]
    RunAPI --> CreateRun[Create WorkflowRun record]
    CreateRun --> Initial[Build initial SupportState]
    Initial --> Background[Background workflow task]
    Background --> Graph[Compiled LangGraph]

    Graph --> GraphState[Save state after updates]
    GraphState --> Status[GET ticket workflow]
    Status --> Console[Support operator or polling client]
```

The complete graph shape is:

```mermaid
flowchart TD
    START[START] --> Understand[understand_ticket]
    Understand --> Severity[classify_severity]
    Severity --> Customer[customer_context]
    Customer --> Knowledge[knowledge_retrieval]
    Knowledge --> Diagnose[troubleshooting]
    Diagnose --> Resolution[resolution_planning]
    Resolution --> Risk[risk_check]

    Risk -->|Policy escalation| Escalation[escalation]
    Risk -->|Approval required| Approval[human_approval]
    Risk -->|Low risk| Execute[execute_resolution]

    Escalation --> Summary[ticket_summary]
    Approval --> Execute
    Execute --> Summary
    Summary --> Memory[memory_update]
    Memory --> END[END]
```

The run API request sequence is:

```mermaid
sequenceDiagram
    participant Agent as Support agent
    participant API as Ticket API
    participant Service as Workflow service
    participant Run as WorkflowRun table
    participant Graph as LangGraph

    Agent->>API: POST /tickets/{id}/run
    API->>Service: Create workflow run
    Service->>Run: Create running record and ticket status
    Run-->>Service: Workflow ID and thread ID
    Service-->>API: 202 workflow ID
    API-->>Agent: Immediate response

    API->>Service: Run graph in background
    Service->>Graph: Stream graph updates
    Graph-->>Service: Updated state after nodes
    Service->>Run: Save JSON-safe state snapshots
```

A second run is blocked when the latest workflow is already waiting or paused. This prevents duplicate executions while a case is unresolved.

Runtime objects such as a tool registry or AI provider are not stored in database state or LangGraph checkpoints. The checkpoint keeps workflow data, while the service recreates runtime dependencies at execution time.

### P10-5 result

An operator can start a workflow, receive a workflow ID immediately, poll status, and preserve a resumable workflow thread.

## P10-6 — Workflow tracer and events API

P10-6 makes the graph visible after and during execution.

### Design change

Workflow state answers “What is the current case situation?” Workflow events answer “What happened, in what order, and how long did it take?”

```mermaid
flowchart LR
    Graph[Graph execution] --> Stream[State stream updates]
    Stream --> State[Latest workflow state]
    Stream --> Tracer[WorkflowTracer]

    Tracer --> NodeStarted[node_started]
    Tracer --> NodeCompleted[node_completed]
    Tracer --> ToolCall[tool_called]
    Tracer --> LLM[llm_called]
    Tracer --> Error[error]
    Tracer --> Complete[workflow_completed]

    NodeStarted --> Events[workflow_events table]
    NodeCompleted --> Events
    ToolCall --> Events
    LLM --> Events
    Error --> Events
    Complete --> Events

    Events --> API[GET ticket events]
    API --> Console[Support console timeline]
```

The event data is intentionally safe:

- no raw prompts;
- no hidden reasoning;
- no secrets;
- no runtime objects;
- no other-customer data;
- timing and token usage only where available.

```mermaid
sequenceDiagram
    participant Service as Workflow service
    participant Graph as LangGraph graph
    participant Tracer as Workflow tracer
    participant DB as Workflow event table
    participant API as Events API
    participant Viewer as Support viewer

    Service->>Graph: Stream workflow values
    Graph-->>Service: Current node and completed nodes
    Service->>Tracer: Record node start or completion
    Tracer->>DB: Save safe event

    Graph-->>Service: Model usage from partial state
    Service->>Tracer: Record LLM usage
    Tracer->>DB: Save usage and duration

    Viewer->>API: GET /tickets/{id}/events
    API->>DB: Read latest workflow events
    DB-->>API: Chronological event list
    API-->>Viewer: Safe timeline
```

The events endpoint is viewer-readable, but workflow run remains agent-controlled.

### P10-6 result

Every run has an inspectable event history. A support team can see the node path and model cost information without receiving hidden prompts or other sensitive execution details.

## End-of-Phase 10 design

The final Phase 10 design connects all CloudDesk specialists in a persistent workflow and exposes the process through status and event APIs.

```mermaid
flowchart TB
    Agent[Support agent] --> RunAPI[POST /tickets/{id}/run]
    Viewer[Support viewer] --> WorkflowAPI[GET /tickets/{id}/workflow]
    Viewer --> EventsAPI[GET /tickets/{id}/events]

    RunAPI --> Service[WorkflowService]
    Service --> RunRecord[(workflow_runs)]

    Service --> State[Initial SupportState]
    State --> Graph[Compiled LangGraph]

    subgraph GraphStages[Phase 10 workflow stages]
        Understand[Understand and classify]
        Context[Customer context]
        Knowledge[Knowledge and cases]
        Diagnose[Troubleshooting]
        Plan[Resolution planning]
        Risk[Risk check]
        Escalation[Escalation]
        Approval[Approval placeholder]
        Execute[Execution placeholder]
        Summary[Ticket summary]
        Memory[Memory placeholder]

        Understand --> Context --> Knowledge --> Diagnose --> Plan --> Risk
        Risk --> Escalation
        Risk --> Approval
        Risk --> Execute
        Escalation --> Summary
        Approval --> Execute
        Execute --> Summary
        Summary --> Memory
    end

    Graph --> GraphStages

    GraphStages --> Checkpoint[(Checkpointer state)]
    GraphStages --> StateUpdate[Safe state snapshot]
    StateUpdate --> RunRecord

    GraphStages --> Tracer[WorkflowTracer]
    Tracer --> Events[(workflow_events)]

    WorkflowAPI --> RunRecord
    EventsAPI --> Events
```

The HTTP request and graph process have a clear division:

```mermaid
flowchart LR
    subgraph HTTPControl[HTTP control layer]
        RunAPI2[Run API]
        StatusAPI[Status API]
        EventsAPI2[Events API]
    end

    subgraph WorkflowCore[Workflow core]
        Service2[WorkflowService]
        Graph2[LangGraph graph]
        Checkpoint2[Checkpointer]
    end

    subgraph DataAndTrace[Data and observability]
        Runs[(workflow_runs)]
        Events[(workflow_events)]
    end

    RunAPI2 --> Service2 --> Graph2
    Graph2 --> Runs
    Graph2 --> Checkpoint2
    Graph2 --> Events
    StatusAPI --> Runs
    EventsAPI2 --> Events
```

## Layer and responsibility boundaries

Phase 10 follows the project layering rules:

| Component         | Responsibility                                                     | Must not do                                      |
| ----------------- | ------------------------------------------------------------------ | ------------------------------------------------ |
| API ticket routes | HTTP validation, RBAC, 202 response, status and events lookup      | Contain specialist policy or graph routing rules |
| Workflow service  | Create runs, start graphs, persist safe snapshots, resume workflow | Talk to HTTP clients directly                    |
| LangGraph nodes   | Perform one stage and return partial state                         | Write SQL directly                               |
| Specialist agents | Use existing tools and structured outputs                          | Bypass guardrails or the tool registry           |
| Checkpointer      | Preserve resumable graph state                                     | Store runtime provider objects or secrets        |
| Workflow tracer   | Persist timing, usage, node, tool and error events                 | Store prompts or hidden reasoning                |
| Repositories      | Read and write workflow data through SQLAlchemy                    | Invoke AI models or execute tools                |

## Phase 10 design decisions

### 1. Rules and policies stay outside the model

Policy escalation, severity raising, approval-required actions, and output validation are deterministic application decisions. The AI supports judgement in grey areas but cannot replace those rules.

### 2. State is append-safe

Completed nodes and errors are not overwritten. Token usage is summed across node calls.

### 3. Runtime objects stay outside persistence

The model provider, tool registry, and memory service are execution dependencies. They are not serialized into workflow JSON or checkpoints.

### 4. The graph is inspectable

Every stage is named and completed-node state is preserved. The events API makes that activity visible to authorized operators.

### 5. Consequential work remains controlled

The Phase 10 graph adds approval and escalation routes, but the final human interrupt and shared action execution lifecycle are completed in Phase 11.

## Honest limitations after Phase 10

Phase 10 is complete in orchestration shape, but not complete in every later action behavior:

- `human_approval` is a graph placeholder until P11 adds the real interrupt and approval record;
- `execute_resolution` is a placeholder until P11 adds shared registry execution;
- `memory_update` is a placeholder until P11 adds final resolution-memory writing;
- P10-6 currently derives some tool observations from workflow node context in the stream. Full low-level tool arguments and results are the next layer to make consistently inspectable;
- offline fake LLM mode is supported; live providers require later environment and credential configuration;
- no real refund, real email, real deletion, or account action is executed in Phase 10.

These are intentional boundaries, not hidden failures. They prevent a workflow from being presented as production-complete before approval and action controls exist.

## Short questions and answers

**What is the main benefit of this design?**

It turns separate specialist functions into one controlled journey with saved state and visible progress.

**Where does the workflow state live?**

LangGraph checkpoints preserve resumable execution state. The workflow run record also stores a JSON-safe application snapshot.

**Why is there an events table as well as workflow state?**

State stores the current case information. Events preserve history: which stage happened, at what time, and which usage or error result occurred.

**Can a workflow pause for approval?**

The routing and checkpointer shape support a paused workflow. The final interrupt implementation and resume decisions are completed in Phase 11.

**Can operators see hidden AI prompts?**

No. The event API exposes safe activity and usage fields, not raw prompts or hidden reasoning.

**Can a consequential action happen automatically?**

No. Consequential actions are routed to approval. The final approval and execution controls are not completed until Phase 11.

**Is this Phase 10 design production-ready?**

It is production-shaped and fully inspectable in the offline environment. It is not yet the complete final product because human approval, shared resolution execution, and memory update behavior belong to the next phase.
