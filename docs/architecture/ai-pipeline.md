# AI Pipeline Architecture — Presales Hub

## End-to-End AI Request Flow

```mermaid
flowchart TB
    subgraph Input
        User[Presales Lead] -->|RFP document\nor query| Copilot
    end

    subgraph Copilot["AI Copilot Layer"]
        Copilot[/copilot/assist] --> RAG
        RAG[Memory / RAG Engine\n/memory/search] -->|top-k chunks\nscore ≥ 0.6| Prompt
        Prompt[Prompt Builder\ncontext injection\nrole instructions] --> CB
    end

    subgraph Provider["Provider Layer (Circuit Breaker)"]
        CB{Circuit\nBreaker} -->|CLOSED| ANT[Anthropic Claude\nclaude-sonnet-4-5]
        CB -->|fallback| OAI[OpenAI GPT-4o]
        CB -->|fallback| GRQ[Groq LLaMA]
        CB -->|OPEN| ERR[503 Degraded\nGraceful fallback message]
    end

    subgraph Safety["Safety & Evaluation"]
        ANT --> Eval[Evaluation Layer\nsafety_flags check\ngrounding score ≥ 0.7]
        OAI --> Eval
        Eval -->|pass| Response
        Eval -->|flag| Review[Human Review Queue]
    end

    subgraph Output
        Response[Structured Response\nresult + grounding_metadata\nevaluation_score + safety_flags]
        Response --> FE[Frontend\nConfidenceBar\nGroundingCitations\nReasoningTrace]
    end
```

## Agent Orchestration

```mermaid
flowchart LR
    subgraph Trigger
        API[Hub API\n/api/agents/run] --> AT[AgentTask\ncreated in DB]
    end

    subgraph Temporal["Temporal Workflow"]
        AT -->|schedule| WT[Workflow\nstart_agent_workflow]
        WT --> A1[rfp_analyzer\nActivity]
        WT --> A2[sme_recommender\nActivity]
        WT --> A3[proposal_drafter\nActivity]
        WT --> A4[risk_assessor\nActivity]
    end

    subgraph Control
        A1 -->|awaiting_approval| Gate{Approval\nGate}
        Gate -->|approved| A3
        Gate -->|rejected| Reject[Task failed]
    end

    subgraph Result
        A3 --> Persist[(PostgreSQL\nAgentTask.output)]
        Persist --> WS[WebSocket Broadcast\nagent.completed event]
        WS --> FE[Agent Monitor UI]
    end
```

## RAG / Memory Pipeline

```mermaid
flowchart LR
    Doc[Source Document\nRFP · Proposal · Policy] -->|chunk 512 tokens| Embed
    Embed[Embedding Model\ntext-embedding-3-small] -->|vectors| VS[(Vector Store\nPostgreSQL pgvector)]

    Query[Copilot Query] --> QEmbed[Query Embedding]
    QEmbed -->|cosine similarity| VS
    VS -->|top-k results| Filter[Score Filter\n≥ 0.6 threshold]
    Filter -->|grounding sources| Prompt[Prompt Context Window]
```

## AI Governance & Quotas

```mermaid
flowchart LR
    Request[AI Request] --> QC{Quota Check\nTenantQuota}
    QC -->|within limit| Process[Process Request]
    QC -->|exceeded| Block[429 Quota Exceeded]
    Process --> Log[UsageRecord\ntokens · cost · model]
    Log --> Agg[Daily Aggregation\n/api/ai/usage/history]
    Agg --> Gov[AI Governance Dashboard\ntoken trends · cost · efficiency]
```
