# Phase 10 — Infrastructure, Component Wiring, and Routing Evolution

This document explains how the Phase 10 workflow components are loaded, connected, routed, stored, and exposed inside the CloudDesk application. It begins with the Phase 9 baseline and follows P10-1 through P10-6.

## What exists in Phase 10

Phase 10 adds workflow orchestration and observability to the existing FastAPI application. It does not add Docker images or Compose containers. CloudDesk is still running as a Python application process with an optional frontend process outside the current container implementation.

| Component              | Infrastructure role at the end of Phase 10                                     |
| ---------------------- | ------------------------------------------------------------------------------ |
| FastAPI                | Receives HTTP requests and starts or reads workflow runs                       |
| Ticket API routes      | Provides run, status, and events endpoints                                     |
| `WorkflowService`      | Creates runs, starts graphs in background tasks, saves state, and reads status |
| LangGraph `StateGraph` | Coordinates named workflow nodes and conditional routing                       |
| `SupportState`         | Carries the ticket and specialist findings through the graph                   |
| Checkpointer           | Preserves resumable workflow state in memory or SQLite                         |
| SQLAlchemy             | Persists workflow runs and events                                              |
| SQLite or PostgreSQL   | Stores the workflow database and event history                                 |
| `WorkflowTracer`       | Writes safe node, tool, model, error, and completion events                    |
| BackgroundTasks        | Starts workflow execution after the API returns 202                            |
| Docker / Compose       | Not implemented yet; no container network is active in Phase 10                |

## Subtask evolution

```mermaid
flowchart LR
    P101["P10-1<br/>State and checkpointer"]
    P102["P10-2<br/>Supervisor nodes"]
    P103["P10-3<br/>Investigation nodes"]
    P104["P10-4<br/>Resolution and risk nodes"]
    P105["P10-5<br/>Graph and run API"]
    P106["P10-6<br/>Tracer and events API"]

    P101 --> Runtime["Workflow runtime state"]
    P102 --> Runtime
    P103 --> Runtime
    P104 --> Runtime
    P105 --> Runtime
    P106 --> Observability["Workflow observability"]
    Runtime --> Observability
```

## Starting point — Phase 9 application process

At the start of Phase 10, CloudDesk has specialist Python classes but no complete workflow path. The application already has FastAPI routing, SQLAlchemy session management, tickets, repositories, tools, guardrails, memory facades, knowledge retrieval, and mock integrations.

```mermaid
flowchart LR
    Agent["Support agent"] --> API["FastAPI backend process"]
    API --> Routes["Ticket and customer routes"]

    Routes --> Specialist1["Supervisor specialist"]
    Routes --> Specialist2["Customer specialist"]
    Routes --> Specialist3["Knowledge specialist"]
    Routes --> Specialist4["Troubleshooting specialist"]
    Routes --> Specialist5["Resolution specialist"]
    Routes --> Specialist6["Escalation specialist"]

    Specialist1 -. "No shared orchestration" .-> Missing["No complete workflow run or event timeline"]
    Specialist2 -.-> Missing
    Specialist3 -.-> Missing
    Specialist4 -.-> Missing
    Specialist5 -.-> Missing
    Specialist6 -.-> Missing

    API --> SQL[("SQL database")]
```

### Starting limitations

- A caller would need to decide when to execute each specialist.
- Specialist outputs are not carried by one complete named workflow state.
- A paused or interrupted workflow has no public graph lifecycle through P10-5.
- Workflow runs and node events are not yet the center of routing.
- Operators cannot inspect one chronological workflow timeline.

Phase 10 introduces LangGraph as the in-process coordinator and HTTP routes as the external control boundary.

## Component map at the end of Phase 10

```mermaid
flowchart TB
    Agent["Support agent"]
    Viewer["Viewer or support operator"]

    subgraph FastAPIProcess["FastAPI application process"]
        Middleware["Request ID, CORS, rate limit, audit"]
        TicketAPI["Ticket run, workflow, and events routes"]
        TicketService["TicketService"]
        WorkflowService["WorkflowService"]
        Graph["Compiled LangGraph StateGraph"]
        Nodes["Named workflow nodes"]
        Specialists["Specialist agents"]
        Tools["ToolRegistry and tools"]
        Tracer["WorkflowTracer"]

        Middleware --> TicketAPI
        TicketAPI --> TicketService
        TicketAPI --> WorkflowService
        WorkflowService --> Graph
        Graph --> Nodes
        Nodes --> Specialists
        Specialists --> Tools
        Graph --> Tracer
    end

    subgraph Persistence["Persistence inside or outside the process"]
        SQL[("SQLite or PostgreSQL")]
        Checkpoint[("In-memory or SQLite checkpointer")]
        Memory[("Redis or Fakeredis memory")]
        Knowledge[("In-memory or Qdrant knowledge store")]
    end

    Agent --> Middleware
    Viewer --> Middleware

    WorkflowService --> SQL
    TicketService --> SQL
    Tracer --> SQL
    Graph --> Checkpoint
    Tools --> SQL
    Tools --> Memory
    Specialists --> Knowledge
```

### Networking boundary

At this stage, CloudDesk is not deployed as a Docker network. The main process boundary is:

```text
Browser or API client
  → FastAPI process on the configured port
  → in-process LangGraph graph
  → SQLAlchemy database session
  → optional Redis, knowledge store, checkpointer, and mock integrations
```

This is a process-level architecture. Docker service names and container ports belong to a later Compose or deployment design.

## P10-1 — State and checkpointer wiring

P10-1 introduces `SupportState` and `create_checkpointer()`.

### Component wiring

```mermaid
flowchart LR
    Graph["LangGraph StateGraph"] --> State["SupportState"]
    State --> Reducers["Append and merge reducers"]

    Reducers --> Completed["completed_nodes"]
    Reducers --> Errors["errors"]
    Reducers --> Usage["Aggregated token_usage"]

    State --> Checkpointer["create_checkpointer()"]

    Checkpointer --> MemoryCP["InMemorySaver<br/>CHECKPOINT_DB_PATH=:memory:"]
    Checkpointer --> SQLiteCP["AsyncSqliteSaver<br/>file-backed SQLite"]
```

The state is the shared working memory for the graph. The checkpointer is the resumable execution memory for the graph.

### State persistence versus checkpoint persistence

```mermaid
flowchart TD
    NodeUpdate["Node returns partial state"]
    NodeUpdate --> LangGraphCheckpoint["LangGraph checkpointer"]
    NodeUpdate --> WorkflowSnapshot["JSON-safe workflow run snapshot"]

    LangGraphCheckpoint --> Resume["Resume a known thread"]
    WorkflowSnapshot --> SQL[("workflow_runs.state")]

    SQL --> StatusAPI["GET workflow status"]
```

Runtime objects such as `ToolRegistry`, AI providers, and memory service objects are not copied into these persisted structures. They are execution dependencies that are kept outside the database snapshot.

### Infrastructure choice

- Tests and local one-off runs can use `:memory:` checkpointer storage.
- A file-backed SQLite checkpointer preserves state across process restarts.
- The application database may use SQLite or PostgreSQL independently of checkpoint storage.

## P10-2 — Supervisor node wiring

P10-2 adds the first graph stages:

```text
understand_ticket
  → classify_severity
  → ticket_summary
```

### Process routing

```mermaid
flowchart LR
    InitialState["Initial SupportState"] --> Understand["understand_ticket"]
    Understand --> Supervisor1["SupervisorAgent.understand"]
    Supervisor1 --> LLM1["call_structured and fake or real provider"]
    LLM1 --> Understand

    Understand --> Severity["classify_severity"]
    Severity --> Supervisor2["SupervisorAgent.assess_severity"]
    Supervisor2 --> Severity

    Severity --> Summary["ticket_summary"]
    Summary --> StateUpdate["Partial workflow state"]
    StateUpdate --> Checkpoint["Checkpointer"]
```

The nodes run inside the LangGraph graph, not as separate network services. They share Python memory and call existing specialist components.

### Subtask routing boundary

```mermaid
sequenceDiagram
    participant Graph as LangGraph
    participant Node as Supervisor graph node
    participant Agent as SupervisorAgent
    participant LLM as AI provider

    Graph->>Node: Pass SupportState
    Node->>Agent: Understand or assess ticket
    Agent->>LLM: call_structured()
    LLM-->>Agent: Validated Pydantic result
    Agent-->>Node: Classification or severity
    Node-->>Graph: Partial state update
```

No additional HTTP calls or containers are required for this stage.

## P10-3 — Investigation node wiring

P10-3 adds three graph stages:

```text
customer_context
  → knowledge_retrieval
  → troubleshooting
```

### Component wiring

```mermaid
flowchart TD
    Graph["LangGraph workflow"] --> Customer["customer_context node"]
    Graph --> Knowledge["knowledge_retrieval node"]
    Graph --> Troubleshoot["troubleshooting node"]

    Customer --> CustomerAgent["CustomerAgent"]
    CustomerAgent --> Registry1["ToolRegistry"]
    Registry1 --> CustomerTools["Customer, subscription, history tools"]
    CustomerTools --> SQL1[("SQL data")]
    CustomerAgent --> Memory["Memory service"]
    Memory --> CustomerMemory[("Customer memory")]

    Knowledge --> KnowledgeAgent["KnowledgeAgent"]
    KnowledgeAgent --> Registry2["ToolRegistry"]
    Registry2 --> Search["search_docs tool"]
    Search --> RAG["KnowledgeService and retriever"]
    RAG --> Vector[("In-memory or Qdrant store")]

    Troubleshoot --> DiagnoseAgent["TroubleshootingAgent"]
    DiagnoseAgent --> Registry3["ToolRegistry"]
    Registry3 --> Status["check_service_status tool"]
    Status --> Mock["Mock service status integration"]
```

### Routing sequence

```mermaid
sequenceDiagram
    participant Graph as LangGraph
    participant Customer as Customer node
    participant Knowledge as Knowledge node
    participant Troubleshoot as Troubleshooting node
    participant Tools as ToolRegistry

    Graph->>Customer: Customer ID and ticket
    Customer->>Tools: Read-only customer tools
    Tools-->>Customer: Customer context
    Customer-->>Graph: Customer partial state

    Graph->>Knowledge: Ticket query and category
    Knowledge->>Tools: search_docs
    Tools-->>Knowledge: Evidence
    Knowledge-->>Graph: Evidence and previous cases

    Graph->>Troubleshoot: Ticket, evidence, customer context
    Troubleshoot->>Tools: check_service_status
    Tools-->>Troubleshoot: Service status
    Troubleshoot-->>Graph: Diagnosis and usage
```

If a tool fails or is unavailable, the node returns partial state and an error record. The graph can continue to later stages instead of losing the entire workflow.

## P10-4 — Resolution and risk node wiring

P10-4 adds:

```text
resolution_planning
  → risk_check
```

### Resolution component route

```mermaid
flowchart LR
    Ticket["Ticket"] --> ResolutionNode["resolution_planning"]
    Diagnosis["Diagnosis"] --> ResolutionNode
    Evidence["Evidence"] --> ResolutionNode
    Context["Customer context"] --> ResolutionNode

    ResolutionNode --> ResolutionAgent["ResolutionAgent"]
    ResolutionAgent --> LLM["call_structured(ResolutionPlan)"]
    ResolutionAgent --> Ground["Ground reply in diagnosis"]
    ResolutionAgent --> Validate["Validate customer output"]
    ResolutionAgent --> Actions["Plan deterministic actions"]

    Actions --> Plan["ResolutionPlan"]
    Ground --> Plan
    Validate --> Plan
```

### Risk routing

```mermaid
flowchart TD
    RiskInput["Risk node inputs"]

    RiskInput --> Policy["Policy-rule match"]
    RiskInput --> Approval["Approval-required action"]
    RiskInput --> Critical["Critical severity"]
    RiskInput --> Injection["Prompt injection"]
    RiskInput --> Output["Invalid customer output"]

    Policy --> High["High risk"]
    Approval --> High
    Critical --> High
    Injection --> High
    Output --> High

    High --> Route1["Escalation or approval route"]
    RiskInput --> Ordinary["No high-risk condition"]
    Ordinary --> Low["Low or medium risk"]
    Low --> Route2["Low-risk execution route"]
```

There is no real money or account action in P10-4. The resolution node creates an approval-required action proposal. Actual execution belongs to the later shared tool phase.

## P10-5 — Graph wiring and run API

P10-5 is the main infrastructure step in Phase 10.

### Final process route

```mermaid
sequenceDiagram
    participant Agent as Support agent
    participant API as FastAPI ticket route
    participant Service as WorkflowService
    participant Graph as LangGraph
    participant CP as Checkpointer
    participant DB as SQL database

    Agent->>API: POST /tickets/{id}/run
    API->>Service: create_run(ticket_id)
    Service->>DB: Create WorkflowRun
    Service->>DB: Set ticket in_progress
    Service-->>API: workflow_id
    API-->>Agent: 202 Accepted

    API->>Service: Add background start task
    Service->>Graph: Start with initial state
    Graph->>CP: Save state after node updates
    Graph-->>Service: Streamed workflow values
    Service->>DB: Save JSON-safe run state
```

### Graph route

```mermaid
flowchart TD
    START["START"] --> Understand["understand_ticket"]
    Understand --> Severity["classify_severity"]
    Severity --> Customer["customer_context"]
    Customer --> Knowledge["knowledge_retrieval"]
    Knowledge --> Diagnose["troubleshooting"]
    Diagnose --> Resolution["resolution_planning"]
    Resolution --> Risk["risk_check"]

    Risk -->|Policy escalation| Escalate["escalation"]
    Risk -->|Approval required| Approval["human_approval placeholder"]
    Risk -->|Ordinary case| Execute["execute_resolution placeholder"]

    Escalate --> Summary["ticket_summary"]
    Approval --> Execute
    Execute --> Summary
    Summary --> Memory["memory_update placeholder"]
    Memory --> END["END"]
```

### Status routing

```mermaid
flowchart LR
    AgentViewer["Agent or viewer"] --> StatusAPI["GET /tickets/{id}/workflow"]
    StatusAPI --> Service["WorkflowService.get_status"]
    Service --> RunRepo["WorkflowRunRepository"]
    RunRepo --> DB[("Workflow run table")]
    DB --> Service
    Service --> SafeState["Safe workflow state response"]
    SafeState --> AgentViewer
```

Starting a second run while a workflow is paused is blocked with HTTP 409. The same conflict rule protects approval and resume behavior from duplicate starts.

### Background execution

The API has two responsibilities:

1. create the workflow record immediately;
2. schedule graph execution in FastAPI `BackgroundTasks`.

```mermaid
flowchart LR
    Request["Incoming run request"] --> Response["202 response"]
    Request --> Schedule["Schedule start_workflow"]
    Schedule --> Worker["In-process background task"]
    Worker --> Graph["LangGraph execution"]
```

In Phase 10, background work is still in-process. There is no separate worker service or message queue.

## P10-6 — Workflow tracer and events API

P10-6 adds `WorkflowTracer` and `GET /tickets/{ticket_id}/events`.

### Wiring

```mermaid
flowchart LR
    Graph["LangGraph stream"] --> Service["WorkflowService"]
    Service --> State["Latest workflow state"]
    Service --> Tracer["WorkflowTracer"]

    Tracer --> Started["node_started"]
    Tracer --> Completed["node_completed"]
    Tracer --> Tool["tool_called"]
    Tracer --> LLM["llm_called"]
    Tracer --> Error["error"]
    Tracer --> Finished["workflow_completed"]

    Started --> EventTable[("workflow_events")]
    Completed --> EventTable
    Tool --> EventTable
    LLM --> EventTable
    Error --> EventTable
    Finished --> EventTable

    EventTable --> EventsAPI["GET ticket events"]
```

### Event sequence

```mermaid
sequenceDiagram
    participant Graph as LangGraph
    participant Service as WorkflowService
    participant Tracer as WorkflowTracer
    participant DB as Workflow event table

    Graph-->>Service: Node state update
    Service->>Tracer: node_started or node_completed
    Tracer->>DB: Persist safe event

    Graph-->>Service: Tool or node context
    Service->>Tracer: tool_called
    Tracer->>DB: Persist tool name and node

    Graph-->>Service: Aggregated token usage
    Service->>Tracer: llm_called
    Tracer->>DB: Persist usage and timing

    Graph-->>Service: Workflow finished
    Service->>Tracer: workflow_completed
    Tracer->>DB: Persist final event
```

The tracer is intentionally fail-safe. If telemetry cannot be written, it does not stop the main graph workflow.

### Events API routing

```mermaid
flowchart LR
    Viewer["Viewer, agent, or admin"] --> Request["GET /tickets/{id}/events"]
    Request --> Middleware["Auth and viewer-role check"]
    Middleware --> TicketCheck["Verify ticket exists"]
    TicketCheck --> LatestRun["Find latest workflow run"]
    LatestRun --> EventRepo["WorkflowEventRepository"]
    EventRepo --> SQL[("workflow_events")]
    SQL --> Response["Chronological event items"]
```

The events response is reader-safe:

- event type;
- node name;
- payload;
- duration;
- token usage;
- timestamp.

It does not expose raw prompts or hidden chain-of-thought.

## Complete Phase 10 infrastructure flow

```mermaid
flowchart TB
    Browser["Browser or API client"] --> Middleware["Request ID, CORS, rate limit, audit"]

    Middleware --> RunAPI["POST /tickets/{id}/run"]
    Middleware --> StatusAPI["GET /tickets/{id}/workflow"]
    Middleware --> EventsAPI["GET /tickets/{id}/events"]

    RunAPI --> TicketRepo["Ticket repository"]
    RunAPI --> WorkflowService["WorkflowService"]

    WorkflowService --> RunTable[("workflow_runs")]
    WorkflowService --> InitialState["Initial JSON-safe state"]
    InitialState --> Graph["LangGraph StateGraph"]

    subgraph GraphRuntime["In-process graph runtime"]
        Supervisor["Supervisor nodes"]
        Investigation["Customer, knowledge, troubleshooting nodes"]
        Resolution["Resolution and risk nodes"]
        Routing["Escalation, approval, or execution route"]
        Summary["Ticket summary and memory placeholders"]

        Supervisor --> Investigation
        Investigation --> Resolution
        Resolution --> Routing
        Routing --> Summary
    end

    Graph --> GraphRuntime
    GraphRuntime --> CP[("Checkpointer")]
    GraphRuntime --> Tracer["WorkflowTracer"]

    Tracer --> EventTable[("workflow_events")]
    GraphRuntime --> StateSave["JSON-safe state snapshot"]
    StateSave --> RunTable

    StatusAPI --> RunTable
    EventsAPI --> EventTable
```

## Docker and container-network status

Docker networking is not yet active in the repository at this phase.

Phase 10 components still run in the local or test Python process:

- FastAPI routes;
- LangGraph nodes;
- specialist agents;
- tool registry;
- workflow service;
- tracer;
- in-process background task.

Persistence may point to:

- local SQLite;
- PostgreSQL;
- Redis or Fakeredis;
- in-memory or Qdrant vector storage.

The future container design will need service DNS names and port wiring, for example:

```mermaid
flowchart LR
    Browser["Browser"] --> Frontend["frontend:3000"]
    Frontend --> Backend["backend:8000"]

    Backend --> DB["PostgreSQL or Supabase"]
    Backend --> Redis["redis:6379"]
    Backend --> Qdrant["qdrant:6333"]
    Backend --> LLM["External AI provider"]
```

That is a planned end-state network only. It is not a claim that Compose containers or Dockerfiles are already implemented in Phase 10.

## Request and routing summary

| Request or operation | Entry point                                  | Internal routing                                           | Storage                        |
| -------------------- | -------------------------------------------- | ---------------------------------------------------------- | ------------------------------ |
| Start workflow       | `POST /tickets/{id}/run`                     | `WorkflowService.create_run` → background `start_workflow` | `workflow_runs`, ticket status |
| Execute graph        | In-process background task                   | LangGraph nodes and conditional routing                    | Checkpointer and run state     |
| Read progress        | `GET /tickets/{id}/workflow`                 | Workflow repository lookup                                 | `workflow_runs.state`          |
| Read events          | `GET /tickets/{id}/events`                   | Workflow and event repositories                            | `workflow_events`              |
| Resume workflow      | Service method in later approval integration | LangGraph `Command(resume=...)`                            | Checkpointer and run status    |
| Store telemetry      | Stream and node updates                      | `WorkflowTracer`                                           | `workflow_events`              |

## Honest limitations after Phase 10

- No Docker network, container DNS, or Compose dependency wiring is implemented in Phase 10.
- Workflow background tasks run inside the FastAPI process.
- `human_approval`, `execute_resolution`, and `memory_update` placeholders are not complete P11 behavior.
- P10-6 traces workflow stream state and node context. It does not yet guarantee a complete argument/result trace for every low-level registry call.
- External Redis and Qdrant are supported as application choices, but no container topology is required for the offline demo.
- Live AI API calls require provider configuration, credentials, and later deployment settings.

## Interview summary

Phase 10 turns the CloudDesk backend into an orchestrated workflow application.

FastAPI receives a request and creates a workflow run. `WorkflowService` starts a LangGraph graph as an in-process background task. The graph moves named nodes through understanding, investigation, resolution planning, and risk routing. A checkpointer preserves resumable graph state, while SQL tables persist run snapshots and event history.

The service is the infrastructure bridge between HTTP, LangGraph, database repositories, and observability. At the end of Phase 10, the system can start a workflow, report status, and return a safe event timeline. Docker networking and the completed approval/action lifecycle are intentionally left to later work.
