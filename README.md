# coding-agent-memory-kit

A drop-in GitHub Skill that gives any coding agent persistent, searchable memory across sessions. Powered by [AgentMemoryToolkit](https://github.com/TheovanKraay/AgentMemoryToolkit) — this repo is a thin CLI wrapper and markdown convention layer on top of it.

## The Problem

AI coding agents are powerful — but they have no lasting memory.

Every session with Copilot, Codex, Claude Code, or Cursor starts from scratch. The agent doesn't know what you decided last week, what approaches failed, what the current project state is, or why the architecture looks the way it does. That context lives in chat windows that are siloed per tool, per session, per machine.

This creates three concrete problems for developers:

1. **Session amnesia.** You explain the same context over and over. The agent re-discovers things you already told it. Previous sessions might as well not have happened.

2. **No portability.** Move your project from Claude Code to Codex, or from your laptop to a teammate's machine, and all agent context is lost. Chat history doesn't travel with the code.

3. **No shared project memory.** When a teammate (human or AI) picks up your work, they start from zero. There's no structured record of what was tried, what was decided, or what went wrong.

Existing memory solutions don't solve this. Tools like MemSearch, MemPalace, Memvid, and Hindsight store memories in external databases (Milvus, ChromaDB, PostgreSQL, proprietary formats). That memory is opaque, not version-controlled, not human-readable, and not portable. Some tools like Claude Tandem add structured memory files, but they're locked to a single agent platform and have no cloud-backed session search.

## What This Is

**coding-agent-memory-kit** is a memory system designed specifically for coding projects, built on a simple idea: **project memory should be an artifact** — committed to your repo, version-controlled alongside your code, readable by any human or agent, and portable everywhere your code goes.

It has two layers:

### Layer 1: Long-Term Memory (Repo Artifacts)

Structured markdown files committed to your repo:

- **`DECISIONS.md`** — Architectural Decision Records. Why choices were made, by whom (human or agent), with full rationale.
- **`STATE.md`** — Living project state. What's in progress, what's blocked, what's done.
- **`FAILURES.md`** — What went wrong and lessons learned. Agents stop repeating the same mistakes.
- **`CHANGELOG.md`** — What changed, when, and who did it.
- **`AGENTS.md`** — Who works on this repo and in what capacity.

These files are the long-term memory. They show up in PRs. They survive across agents, sessions, machines, and team members. Any agent that can read markdown picks up the full project context on session start — no vendor lock-in.

### Layer 2: Short-Term Memory (Azure Cosmos DB)

Full session transcripts, semantic search, fact extraction, thread summaries, and cross-session user profiles — powered by [AgentMemoryToolkit](https://github.com/TheovanKraay/AgentMemoryToolkit) and Azure Cosmos DB.

The repo stores **pointers** to Cosmos DB sessions (session ID, date, agent, thread reference) — never raw chat content. This gives you:

- **Semantic search** across all past sessions ("what did we decide about authentication?")
- **Hybrid search** (vector + full-text) for precise recall
- **Fact extraction** — discrete, searchable assertions pulled from conversations
- **Thread summaries** — compressed recaps of long sessions
- **User profiles** — cross-session context that builds over time

### What's Different Here

The landscape of AI memory tools is growing fast. Here's where this fits:

| | Generic AI Memory (Mem0, MemSearch, Memvid, Hindsight) | Platform-Specific (Claude Tandem) | **coding-agent-memory-kit** |
|---|---|---|---|
| **Memory location** | External DB — opaque, invisible | Local files — but platform-locked | Repo artifacts (git-tracked) + Cosmos DB for sessions |
| **Human-readable** | No | Partially (MEMORY.md, progress.md) | Yes — structured markdown with project semantics |
| **Version-controlled** | No | Partially (gitignored progress files) | Fully — artifacts are committed, show up in PRs |
| **Portable across agents** | No — tied to the memory system's runtime | No — Claude Code only | Yes — any agent that reads markdown |
| **Portable across developers** | No — requires access to the memory service | No — single-developer, single-machine | Yes — `git clone` gives full project context |
| **Searchable session history** | Vector search over flat memory | No cloud search | Vector + hybrid search via Cosmos DB |
| **Derived memory** (summaries, facts, profiles) | Hindsight has "reflect"; others don't | No | Thread summaries, fact extraction, user profiles via Durable Functions |
| **Designed for** | Generic AI chat recall | Claude Code workflow gaps | Coding projects — decisions, state, failures, architecture |

The core differentiator is the combination: **structured project-specific artifacts in git** (not flat memory logs) **+ cloud-backed semantic search** (not just local files) **+ full agent and developer portability** (not locked to any platform).

### The Workflow

```
 Developer installs skill in repo
              │
              ▼
 ┌─── Session Start ───────────────────────────────────┐
 │  Agent reads STATE.md, DECISIONS.md, FAILURES.md    │
 │  Agent searches Cosmos DB for relevant past context  │
 │  → Instant project awareness, zero re-explanation    │
 └─────────────────────────────────────────────────────┘
              │
              ▼
 ┌─── During Session ──────────────────────────────────┐
 │  Agent updates markdown artifacts as it works        │
 │  Session turns sync to Cosmos DB                     │
 └─────────────────────────────────────────────────────┘
              │
              ▼
 ┌─── Session End ─────────────────────────────────────┐
 │  Facts extracted, thread summarized                  │
 │  Markdown artifacts committed to repo                │
 │  Session pointer added to artifact files             │
 └─────────────────────────────────────────────────────┘
              │
              ▼
   Next session — same agent, different agent,
   teammate's agent — everything is there.
   Project memory grows with the code.
```

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌────────────────────┐     ┌──────────────┐
│  Repo Markdown  │◄───►│  memory_cli  │◄───►│ AgentMemoryToolkit │◄───►│  Cosmos DB   │
│  (STATE.md etc) │     │  (this CLI)  │     │ CosmosMemoryClient │     │ + AI Foundry │
└─────────────────┘     └──────────────┘     └────────────────────┘     └──────────────┘
```

- **Repo Markdown** — human-readable, git-tracked files (STATE.md, DECISIONS.md, etc.)
- **memory_cli.py** — single CLI wrapping `CosmosMemoryClient` from the toolkit
- **AgentMemoryToolkit** — handles Cosmos DB CRUD, vector/hybrid search, embeddings, Durable Functions pipelines
- **Cosmos DB + AI Foundry** — scalable vector-indexed storage and embedding generation

## Quick Start

1. **Prerequisites:** Azure Cosmos DB (NoSQL API, vector search enabled), `az login` completed

2. **Set environment variables:**
   ```bash
   export COSMOS_DB_ENDPOINT="https://your-account.documents.azure.com:443/"
   export AI_FOUNDRY_ENDPOINT="https://your-foundry.cognitiveservices.azure.com/"  # optional
   ```

3. **Install & initialise:**
   ```bash
   bash .github/skills/repo-memory/setup.sh
   ```

4. **Store a memory:**
   ```bash
   python .github/skills/repo-memory/scripts/memory_cli.py add \
     --user-id agent-1 --thread-id sess-001 --role agent \
     --content "Decided to use retry logic"
   ```

5. **Search memories:**
   ```bash
   python .github/skills/repo-memory/scripts/memory_cli.py search \
     --query "retry logic" --user-id agent-1 --hybrid
   ```

## Configuration

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `COSMOS_DB_ENDPOINT` | Yes | — | Cosmos DB account URI |
| `COSMOS_DB_DATABASE` | No | `agent_memory` | Database name |
| `COSMOS_DB_CONTAINER` | No | `memories` | Container name |
| `AI_FOUNDRY_ENDPOINT` | No | — | Azure AI Foundry for embeddings |
| `EMBEDDING_MODEL` | No | `text-embedding-3-large` | Embedding model name |
| `ADF_ENDPOINT` | No | — | Azure Durable Functions endpoint |
| `ADF_KEY` | No | — | Durable Functions key |

## Documentation

- **[SKILL.md](.github/skills/repo-memory/SKILL.md)** — Full agent instructions and CLI reference
- **[Architecture](docs/architecture.md)** — Design rationale and layers
- **[Quick Start Guide](docs/quickstart.md)** — Step-by-step setup

## License

MIT
