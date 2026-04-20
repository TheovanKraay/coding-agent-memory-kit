# Repo Memory Skill

## Description
Cross-agent memory-as-artifact system. Manages long-term project memory via markdown files and short-term session memory via Cosmos DB.

## When to Use
- At **session start**: rehydrate previous context from Cosmos DB
- **During a session**: log turns, decisions, state changes, and failures
- At **session end**: promote important session data to repo markdown artifacts

## Quick Start

```python
from repo_memory import (
    LongTermMemoryManager,
    SessionMemoryStore,
    MemoryArtifactUpdater,
)

# 1. Initialize
memory = LongTermMemoryManager("/path/to/repo")
store = SessionMemoryStore(session_id="s1", agent_id="my-agent")

# 2. Log turns during your session
store.add_turn("user", "Build the API endpoint")
store.add_turn("agent", "Done. Created /api/v1/users")

# 3. Log structured events via metadata
store.add_turn("agent", "Chose REST over GraphQL", metadata={
    "decision": {
        "title": "REST over GraphQL",
        "context": "Need simple CRUD API",
        "decision": "Use REST",
        "rationale": "Simpler for our use case",
    }
})

# 4. At session end, promote to repo artifacts
updater = MemoryArtifactUpdater(memory)
updater.update_from_session(store, version="0.2.0")
```

## Memory Files

| File | Purpose |
|------|---------|
| `AGENTS.md` | Registered agents and their roles |
| `STATE.md` | Current project state (in progress / blocked / done) |
| `DECISIONS.md` | Architecture Decision Records |
| `CHANGELOG.md` | What changed and when |
| `FAILURES.md` | What went wrong and lessons learned |

## With Cosmos DB

```python
from repo_memory import CosmosSessionSync
from agent_memory_toolkit import CosmosMemoryClient

client = CosmosMemoryClient(cosmos_endpoint="...", cosmos_database="...", cosmos_container="...")
sync = CosmosSessionSync(client, user_id="project-1")

# Rehydrate previous session
sync.rehydrate_session(store)

# ... do work ...

# Persist session to Cosmos
sync.sync_to_cosmos(store)
```

## Transcript Conversion

```python
from repo_memory import AgentTranscriptAdapter

# From OpenAI format
turns = AgentTranscriptAdapter.from_openai(openai_messages)

# From Anthropic format
turns = AgentTranscriptAdapter.from_anthropic(anthropic_messages)
```

## Key Principle
**Repo markdown = source of truth.** Cosmos DB = working memory.
Promote important session findings to repo artifacts before session ends.
