# coding-agent-memory-kit

A cross-agent memory-as-artifact system that combines **repo-native markdown files** for persistent project knowledge with **Azure Cosmos DB** for real-time session memory.

## Architecture

```
┌─────────────────────────────────────────────┐
│              Agent Session                   │
│  ┌──────────────┐    ┌───────────────────┐  │
│  │ SessionStore  │───▶│ CosmosSessionSync │  │
│  │ (in-memory)   │    │ (Cosmos DB)       │  │
│  └──────┬───────┘    └───────────────────┘  │
│         │                                    │
│         ▼                                    │
│  ┌──────────────────┐                        │
│  │ ArtifactUpdater   │──▶ DECISIONS.md       │
│  │ (end of session)  │──▶ STATE.md           │
│  │                   │──▶ FAILURES.md        │
│  │                   │──▶ CHANGELOG.md       │
│  └──────────────────┘                        │
└─────────────────────────────────────────────┘
```

**Two-layer memory:**
- **Layer 1 (Repo):** Markdown files checked into git — the source of truth. Human-readable, diffable, portable.
- **Layer 2 (Cosmos DB):** Session turns, vector search, cross-agent sharing. Working memory that gets promoted to repo artifacts.

## Installation

```bash
pip install -e .
```

Requires [AgentMemoryToolkit](https://github.com/theovankraay/AgentMemoryToolkit) for Cosmos DB features.

## Quick Start

```python
from repo_memory import (
    LongTermMemoryManager,
    SessionMemoryStore,
    MemoryArtifactUpdater,
    AgentTranscriptAdapter,
)

# Manage repo markdown directly
memory = LongTermMemoryManager(".")
memory.update_state(StateEntry(item="Auth module", description="Implementing OAuth", agent_id="agent-1"))
memory.log_decision(Decision(title="Use OAuth2", context="Need auth", decision="OAuth2", rationale="Industry standard"))

# Track session turns
store = SessionMemoryStore(session_id="sess-1", agent_id="agent-1")
store.add_turn("user", "Build the login page")
store.add_turn("agent", "Created login.html with OAuth flow")

# Convert from OpenAI/Anthropic formats
turns = AgentTranscriptAdapter.from_openai(openai_messages)

# Promote session findings to repo
updater = MemoryArtifactUpdater(memory)
updater.update_from_session(store, version="0.2.0")
```

## With Cosmos DB

```python
from agent_memory_toolkit import CosmosMemoryClient
from repo_memory import CosmosSessionSync, SessionMemoryStore

client = CosmosMemoryClient(
    cosmos_endpoint="https://your-account.documents.azure.com",
    cosmos_database="agent-memory",
    cosmos_container="memories",
)

sync = CosmosSessionSync(client, user_id="project-1")
store = SessionMemoryStore(agent_id="agent-1")

# Rehydrate from previous session
sync.rehydrate_session(store)

# ... do work, add turns ...

# Persist to Cosmos
sync.sync_to_cosmos(store)

# Semantic search
results = sync.search_memories("authentication flow")
```

## Memory Files

| File | Purpose |
|------|---------|
| `AGENTS.md` | Registered agents and roles |
| `STATE.md` | Work items: in progress, blocked, done |
| `DECISIONS.md` | Architecture Decision Records with rationale |
| `CHANGELOG.md` | Chronological change log |
| `FAILURES.md` | Failures, root causes, and lessons |

## Modules

| Module | Class | Purpose |
|--------|-------|---------|
| `long_term_memory` | `LongTermMemoryManager` | Read/write repo markdown files |
| `session_store` | `SessionMemoryStore` | In-memory session turn tracking |
| `cosmos_sync` | `CosmosSessionSync` | Sync sessions to/from Cosmos DB |
| `transcript_adapter` | `AgentTranscriptAdapter` | Convert OpenAI/Anthropic/raw formats |
| `artifact_updater` | `MemoryArtifactUpdater` | Promote session data to repo artifacts |
| `models` | Various | Pydantic models for all data types |

## Documentation

- [Architecture](docs/architecture.md) — Detailed system design
- [Quick Start](docs/quickstart.md) — Getting started guide
- [Extending](docs/extending.md) — How to add custom memory types

## Testing

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT
