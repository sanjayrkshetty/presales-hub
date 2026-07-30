# Data Flow — Presales Hub

## Real-time event bus

```mermaid
flowchart LR
    subgraph Backend
        API[Hub API] -->|publish| RD[(Redis Pub/Sub)]
        API -->|on failure| DLQ[(Dead Letter Queue<br/>PostgreSQL)]
        DLQ -->|retry backoff<br/>1→5→15→60→240 min| RD
        RD -->|subscribe| BR[Broadcaster]
        BR -->|fan-out| WS1[WebSocket /ws/activity]
        BR -->|fan-out| WS2[WebSocket /ws/sla-alerts]
        BR -->|fan-out| WS3[WebSocket /ws/events]
    end

    subgraph Frontend
        WS1 --> RST[Realtime Store<br/>Zustand]
        WS2 --> RST
        WS3 --> RST
        RST -->|event log| AF[Activity Feed]
        RST -->|SLA events| SLA[SLA Timer]
        RST -->|invalidate| RQ[React Query Cache]
    end
```

## Proposal lifecycle (Temporal)

```mermaid
stateDiagram-v2
    [*] --> intake: New RFP received
    intake --> discovery: SME assigned
    discovery --> technical_review: Discovery complete
    technical_review --> commercial_review: Tech approved
    commercial_review --> legal_review: Commercial cleared
    legal_review --> awaiting_approval: Legal signed off
    awaiting_approval --> submitted: All approvals granted
    submitted --> [*]: Won / Lost

    intake --> [*]: Declined
    awaiting_approval --> [*]: Rejected
```

Durable stage transitions and approvals run on Temporal. **Draft text** is produced by the LangGraph draft graph (see [`ai-pipeline.md`](./ai-pipeline.md)), not by Temporal-as-writer.

## AI draft request flow (war-room Generate)

```mermaid
sequenceDiagram
    participant FE as War room / Copilot
    participant API as Hub API
    participant G as LangGraph draft
    participant VS as pgvector MiniLM
    participant GR as Groq scrubbed-only

    FE->>API: POST generate-docx / draft-section
    Note over API: TimeoutAPIRoute 180s for generate-docx
    API->>G: run_draft_graph
    G->>G: load → scrub
    G->>VS: retrieve + graph_expand
    VS-->>G: scrubbed chunks
    alt GROQ_API_KEY present
        G->>GR: draft on scrubbed context
        GR-->>G: markdown sections
        G->>G: validate grounding
        alt hard gate fail
            G->>G: one repair then template_fallback
        end
    else no Groq / fallback mode
        G->>G: template from retrieved chunks
    end
    G-->>API: emit section_map + meta
    API-->>FE: editable draft / .docx
```

## Database schema (core)

```mermaid
erDiagram
    Tenant ||--o{ Opportunity : owns
    Opportunity ||--o| Proposal : has
    Proposal ||--o{ Approval : requires
    Proposal ||--o{ ActivityFeed : logs
    Stakeholder }|--o{ Approval : decides
    Stakeholder }|--o{ Opportunity : engages

    UsageRecord }|--|| Tenant : tracks
    TenantQuota }|--|| Tenant : limits
    DeadLetterEvent {
        uuid id
        str channel
        text payload
        str error
        int retry_count
        datetime next_retry_at
        bool resolved
    }
```

Vectors live in the same Postgres DB (`memory_chunks.embedding vector(384)` + `embedding_json`); see [`ai-pipeline.md`](./ai-pipeline.md) and [`docs/CORPUS.md`](../CORPUS.md).
