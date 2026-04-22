# Architecture

## Layers

```
┌─────────────────────────────────────────────────────┐
│                   Coding Agent                       │
│         (Copilot, Cursor, Claude, etc.)             │
├─────────────────────────────────────────────────────┤
│              Repo Markdown Files                     │
│   STATE.md · DECISIONS.md · CHANGELOG.md · etc.     │
│   Human-readable, git-tracked, portable             │
├─────────────────────────────────────────────────────┤
│              memory_cli.py (this repo)               │
│   Thin CLI wrapper — argparse + JSON output          │
├─────────────────────────────────────────────────────┤
│           AgentMemoryToolkit                         │
│   CosmosMemoryClient — CRUD, vector search,          │
│   hybrid search, Durable Functions pipelines         │
├─────────────────────────────────────────────────────┤
│         Azure Cosmos DB + AI Foundry                 │
│   Vector indexes, fulltext indexes, hierarchical     │
│   partition key [/user_id, /thread_id], embeddings   │
└─────────────────────────────────────────────────────┘
```

## Why Two Memory Layers?

**Repo Markdown (long-term, portable):**
- Survives repo clones, forks, platform migrations
- Human-readable — anyone can open STATE.md and understand project context
- Git-tracked — full history of decisions and state changes
- Never contains raw chat content — only summaries and references

**Cosmos DB (short-term, searchable):**
- Vector similarity search across all sessions
- Hybrid search (vector + full-text via Reciprocal Rank Fusion)
- Structured memory types: turns, facts, summaries, user profiles
- Scales to millions of memories across hundreds of sessions
- Durable Functions pipelines for summarisation and fact extraction

## How AgentMemoryToolkit Is Used

This repo does **not** use `azure-cosmos` directly. All Cosmos DB interaction goes through `CosmosMemoryClient` from [AgentMemoryToolkit](https://github.com/TheovanKraay/AgentMemoryToolkit), which provides:

- **Auto-provisioning** — `create_memory_store()` creates the database, container (with vector + fulltext indexes and hierarchical partition key), and counter container
- **CRUD** — `add_cosmos()`, `update_cosmos()`, `delete_cosmos()`, `get_thread()`, `get_memories()`
- **Search** — `search_cosmos()` with vector-only or hybrid (vector + fulltext via RRF) modes
- **Pipelines** — `generate_thread_summary()`, `extract_facts()`, `generate_user_summary()` via Azure Durable Functions
- **Auth** — `DefaultAzureCredential` built-in (`use_default_credential=True`)

The CLI (`memory_cli.py`) maps each subcommand 1:1 to a `CosmosMemoryClient` method. No additional logic.

## Data Model

From AgentMemoryToolkit's `MemoryRecord`:

| Field | Type | Description |
|-------|------|-------------|
| `id` | str | Unique record ID |
| `user_id` | str | Agent/user identifier (partition key L1) |
| `thread_id` | str | Session/thread identifier (partition key L2) |
| `role` | str | `user`, `agent`, `tool`, `system` |
| `memory_type` | str | `turn`, `summary`, `fact`, `user_summary` |
| `content` | str | The memory content |
| `embedding` | list[float] | Vector embedding (auto-generated) |
| `metadata` | dict | Arbitrary metadata |
| `created_at` | datetime | Timestamp |
