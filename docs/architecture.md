# Architecture

## Overview

The coding-agent-memory-kit implements a **two-layer memory architecture** for multi-agent systems.

```
┌─────────────────────────────────────────────────────────┐
│                    Agent Runtime                         │
│                                                         │
│  ┌─────────────────┐     ┌────────────────────────┐    │
│  │ SessionMemory    │     │ TranscriptAdapter       │    │
│  │ Store            │◀────│ (OpenAI/Anthropic/raw)  │    │
│  │ (in-memory)      │     └────────────────────────┘    │
│  └────────┬─────────┘                                   │
│           │                                             │
│     ┌─────┴──────┐                                      │
│     ▼            ▼                                      │
│  ┌──────────┐ ┌──────────────┐                          │
│  │ Cosmos   │ │ Artifact     │                          │
│  │ Sync     │ │ Updater      │                          │
│  └────┬─────┘ └──────┬───────┘                          │
│       │              │                                  │
└───────┼──────────────┼──────────────────────────────────┘
        │              │
        ▼              ▼
  ┌──────────┐   ┌──────────────┐
  │ Cosmos DB│   │ Repo Files   │
  │ (working │   │ (source of   │
  │  memory) │   │  truth)      │
  └──────────┘   └──────────────┘
```

## Layer 1: Long-Term Repo Memory

Markdown files in the repository root serve as the persistent, version-controlled source of truth:

- **AGENTS.md** — Agent registry
- **STATE.md** — Current project state
- **DECISIONS.md** — Architecture Decision Records
- **CHANGELOG.md** — Change history
- **FAILURES.md** — Failure log with lessons

These files are managed by `LongTermMemoryManager`, which provides structured read/write operations while keeping the files human-readable.

### Why Markdown?

1. **Portable** — No runtime dependencies, works everywhere
2. **Human-readable** — Agents and humans can both read/edit
3. **Git-trackable** — Full history via version control, meaningful diffs
4. **IDE-native** — Every editor renders markdown

## Layer 2: Session Memory (Cosmos DB)

During active sessions, agents use `SessionMemoryStore` for fast in-memory turn tracking, with `CosmosSessionSync` providing persistence and cross-agent sharing via Azure Cosmos DB.

### Why Cosmos DB?

1. **Vector search** — Find semantically similar memories
2. **Hierarchical partition keys** — Efficient queries by user/thread
3. **Change feed** — Trigger processing pipelines (summaries, fact extraction)
4. **Cross-agent** — Multiple agents share the same memory space

## Data Flow

1. **Session start**: `CosmosSessionSync.rehydrate_session()` loads previous context
2. **During session**: `SessionMemoryStore.add_turn()` tracks all interactions
3. **Session end**:
   - `CosmosSessionSync.sync_to_cosmos()` persists to Cosmos DB
   - `MemoryArtifactUpdater.update_from_session()` promotes decisions/state/failures to repo markdown

## Integration with AgentMemoryToolkit

The `CosmosSessionSync` class wraps `agent_memory_toolkit.CosmosMemoryClient`, providing a session-focused API. This avoids reinventing Cosmos DB integration while keeping the memory-kit's API clean and focused.

Authentication uses `DefaultAzureCredential` (Entra ID / RBAC) — no connection strings or keys in code.
