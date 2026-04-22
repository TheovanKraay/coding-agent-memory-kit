# coding-agent-memory-kit

A drop-in GitHub Skill that gives any coding agent persistent, searchable memory across sessions. Powered by [AgentMemoryToolkit](https://github.com/TheovanKraay/AgentMemoryToolkit) — this repo is a thin CLI wrapper and markdown convention layer on top of it.

## Why This Exists

As a developer working with AI coding agents, you've probably hit these walls:

**Your chat history is trapped.** Every conversation with Copilot, Codex, Claude Code, or Cursor lives in that tool's silo. Switch agents, switch machines, or start a new session — and all that context is gone. The agent doesn't remember what you decided yesterday, what failed last week, or why you chose one approach over another.

**Your team can't share agent context.** When a teammate picks up your work, they start from zero. The agent has no idea what's already been tried, what architectural decisions were made, or what gotchas were discovered. That hard-won context evaporates.

**Chat history isn't project memory.** Raw transcripts are noisy and unsearchable. What you actually need are the *decisions*, the *current state*, the *failures and lessons learned* — distilled, structured, and living alongside the code.

### Memory as Artifact

This project takes a different approach from generic AI memory systems (which store memories in external databases, invisible to humans). Here, **memory is an artifact** — committed to your repo, version-controlled, human-readable, and portable:

- **`DECISIONS.md`** — Architectural Decision Records. Why choices were made, by whom (human or agent), with full rationale. Survives across agents, sessions, and team members.
- **`STATE.md`** — Living project state. What's in progress, what's blocked, what's done. Any agent reads this on startup and knows where things stand.
- **`FAILURES.md`** — What went wrong and lessons learned. Agents stop repeating the same mistakes.
- **`CHANGELOG.md`** — What changed, when, and who did it (human or agent).
- **`AGENTS.md`** — Who works on this repo and in what capacity.

These files show up in PRs. They're reviewable. They travel with `git clone`. They work with *any* agent that can read markdown — no vendor lock-in.

For the short-term session layer (full conversation history, semantic search, fact extraction), we use Azure Cosmos DB via [AgentMemoryToolkit](https://github.com/TheovanKraay/AgentMemoryToolkit). The repo stores *pointers* to sessions — never raw chat content.

### What makes this different

| | Generic AI Memory (Mem0, MemSearch, etc.) | coding-agent-memory-kit |
|---|---|---|
| **Where memory lives** | External DB (Milvus, ChromaDB, PostgreSQL) | In the repo (markdown) + Cosmos DB for sessions |
| **Human-readable** | No — opaque vector stores | Yes — markdown files you can read, edit, review |
| **Version-controlled** | No | Yes — full git history of how project memory evolved |
| **Portable** | Locked to the memory system | `git clone` and you have everything |
| **Shareable** | Requires access to the memory service | Push/pull — teammates get full context |
| **Agent-agnostic** | Usually tied to specific platforms | Any agent that reads markdown |
| **Designed for** | Chat personalization, generic recall | Coding projects — decisions, state, failures, architecture |

### The workflow

1. You install the skill in your repo
2. Any coding agent reads the markdown files on session start → instant project context
3. During work, the agent updates the artifacts and syncs session transcripts to Cosmos DB
4. On session end, facts and summaries are extracted and stored
5. Next session (same agent, different agent, teammate's agent) — everything is there
6. Your project memory grows with the code, not trapped in chat windows

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
