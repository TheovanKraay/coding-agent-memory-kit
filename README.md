# Memory as an Artifact

> Give your AI coding agents durable, cross-platform memory. Install into any repo — agent sessions automatically sync to Azure Cosmos DB, searchable and resumable across machines and platforms.

---

## Prerequisites

You need two Azure services set up before using this kit:

### 1. Azure Cosmos DB (NoSQL API)

Stores all memories, session turns, facts, and summaries.

- Create a Cosmos DB account with the **NoSQL API**
- Enable **vector search** on the account (required for semantic search)
- Authentication uses `DefaultAzureCredential` — run `az login` or configure a service principal
- The CLI auto-creates the container on first `init` (with vector indexes, fulltext indexes, and hierarchical partition key)
- **Important:** With Entra ID (DefaultAzureCredential) auth, you must create the database beforehand — Entra ID doesn't have permission to create databases. Create it via the Azure Portal or CLI:
  ```bash
  az cosmosdb sql database create --account-name <account> --resource-group <rg> --name agent_memory
  ```

### 2. Azure AI Foundry (formerly Azure OpenAI)

Generates vector embeddings for semantic and hybrid search. **Required for any search functionality.**

- Create an [Azure AI Foundry](https://ai.azure.com/) resource (this is the rebranded Azure OpenAI Service)
- Deploy an embedding model — the default is `text-embedding-3-large` but any embedding model works
- The endpoint looks like: `https://your-resource.cognitiveservices.azure.com/` or `https://your-resource.openai.azure.com/`
- Authentication uses `DefaultAzureCredential` (same `az login` as Cosmos DB)

> **Without AI Foundry**, you can store and retrieve memories by ID/thread, but **vector search and hybrid search will not work**. If search is important to you (it probably is), this is effectively required.

### 3. Azure Durable Functions (optional)

Powers async pipelines for thread summarization, fact extraction, and user profile generation. These are convenience features — the core memory and session sync functionality works without them.

---


## Quick Start

**1. Set up Azure** (see [Prerequisites](#prerequisites) above):

**Bash / macOS / Linux / WSL:**
```bash
az login
export COSMOS_DB_ENDPOINT="https://your-account.documents.azure.com:443/"
export AI_FOUNDRY_ENDPOINT="https://your-foundry.cognitiveservices.azure.com/"
```

**PowerShell (Windows):**
```powershell
az login
$env:COSMOS_DB_ENDPOINT = "https://your-account.documents.azure.com:443/"
$env:AI_FOUNDRY_ENDPOINT = "https://your-foundry.cognitiveservices.azure.com/"
```

**2. Install** — from the root of any repo:

**Bash / macOS / Linux / WSL:**
```bash
curl -sL https://raw.githubusercontent.com/TheovanKraay/coding-agent-memory-kit/main/install.sh | bash
```

**PowerShell (Windows):**
```powershell
irm https://raw.githubusercontent.com/TheovanKraay/coding-agent-memory-kit/main/install.ps1 | iex
```

**That's it.** The installer handles everything: Python, dependencies, skill files, Cosmos DB setup.

### What happens next

Once installed, your coding agent sessions are automatically synced:

- **Session export** — when an agent session ends, its full conversation history is stored in Cosmos DB as individual turn documents, vector-indexed and searchable
- **Session import** — when a new agent starts (same machine or different), it checks Cosmos DB for previous sessions on this repo and can resume where the last agent left off
- **Cross-platform** — a session started in Claude Code on your laptop can be resumed in Cursor on your desktop, or picked up by an OpenClaw agent on a VPS
- **Semantic search** — any agent can search across all past sessions: *"what did we decide about authentication?"*

The skill instructs agents how to do this automatically via [SKILL.md](.github/skills/repo-memory/SKILL.md). You don't need to run commands manually — the agent reads the skill and handles session sync on its own.

### What gets stored

| In your repo (git-tracked) | In Cosmos DB (cloud-synced) |
|---|---|
| `STATE.md` — current project state | Full session transcripts (per-turn documents) |
| `DECISIONS.md` — architectural decisions | Vector embeddings for semantic search |
| `FAILURES.md` — what went wrong | Session metadata (platform, machine, workspace) |
| `CHANGELOG.md` — what changed | Extracted facts and thread summaries |
| `AGENTS.md` — who works on this repo | Cross-session user profiles |

The repo artifacts are human-readable summaries. Cosmos DB holds the full conversation history — the [conversation-as-artifact](docs/session-sync-architecture.md#conversations-as-code-artifacts) that is now the primary record of how and why code was written.

> **Flags:** Pass `--yes` to skip prompts (for CI). Pass `--skip-cosmos` to install files only.

---


## CLI Reference

For advanced use or manual operations, the skill includes a CLI:

```bash
# Sync all local agent sessions to/from Cosmos DB
.github/skills/repo-memory/memory session-sync

# List sessions (local, cosmos, or both)
.github/skills/repo-memory/memory session-list --source both

# Search across all past sessions
.github/skills/repo-memory/memory search --query "auth decision" --user-id agent-1 --hybrid

# Store a memory manually
.github/skills/repo-memory/memory add \
  --user-id agent-1 --thread-id sess-001 --role agent \
  --content "Decided to use retry logic"

# Test which platform adapters work on this machine
.github/skills/repo-memory/memory session-test
```

See [SKILL.md](.github/skills/repo-memory/SKILL.md) for the full command reference.


## Configuration Reference

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `COSMOS_DB_ENDPOINT` | **Yes** | — | Cosmos DB account URI |
| `AI_FOUNDRY_ENDPOINT` | **Yes**\* | — | Azure AI Foundry endpoint for embeddings |
| `COSMOS_DB_DATABASE` | No | `agent_memory` | Database name |
| `COSMOS_DB_CONTAINER` | No | `memories` | Container name |
| `EMBEDDING_MODEL` | No | `text-embedding-3-large` | Embedding model deployed in AI Foundry |
| `ADF_ENDPOINT` | No | — | Azure Durable Functions endpoint (for summaries/facts) |
| `ADF_KEY` | No | — | Durable Functions key |

\* Required for vector/hybrid search. Without it, only ID-based retrieval works.


---

## Concepts

### The Principle

Today, every AI memory system stores memories *outside* the project — in vector databases, proprietary formats, or opaque cloud services. That memory is invisible to humans, locked to a single tool, and lost when you switch agents or machines.

**Memory as an Artifact** inverts this. Project memory is treated the same way we treat code, documentation, and configuration:

- It lives **in the repo**
- It's **version-controlled** (full git history of how decisions evolved)
- It's **human-readable** (structured markdown, not opaque embeddings)
- It's **reviewable** (shows up in PRs, can be edited, discussed, approved)
- It's **portable** (`git clone` and any agent, on any platform, has full context)
- It's **shareable** (teammates get project memory the same way they get code)

Raw session transcripts don't belong in the repo — they're noisy and large. Instead, the repo stores **structured distillations** (decisions, state, failures, lessons) and **pointers** to searchable session history in the cloud.

### The Conversation Is the Code

In agentic development, the conversation with the agent **is** the development process. The dialogue — the reasoning, the architectural debates, the "try this approach, no go back" — is as valuable as the code it produces. The code is reproducible from the conversation, but the conversation is not reproducible from the code.

Traditional version control tracks *what changed* (diffs). This system also captures *why and how* — the full reasoning chain that led to every design choice. An agent session that produces a feature is as important as the feature's pull request.

Platforms like GitHub Copilot's memory or Cursor's context treat agent interactions as ephemeral. **Memory as an Artifact** treats every conversation as source material — durable, searchable, portable across machines, and syncable across platforms via [Session Sync](docs/session-sync-architecture.md).

### The Artifact Files

| File | Purpose | Why it matters |
|------|---------|----------------|
| **`DECISIONS.md`** | Architectural Decision Records — what was decided, by whom, why | Agents stop re-debating settled questions. New team members understand rationale. |
| **`STATE.md`** | Living project state — in progress, blocked, done | Any agent reads this on startup and knows exactly where things stand. |
| **`FAILURES.md`** | What went wrong and lessons learned | Agents stop repeating the same mistakes. Institutional knowledge survives. |
| **`CHANGELOG.md`** | What changed, when, by whom (human or agent) | Audit trail that travels with the code. |
| **`AGENTS.md`** | Who works on this repo — humans and AI agents | Context for multi-agent and multi-developer collaboration. |

These aren't log files. They're **living project artifacts** with defined structure and semantics, designed to be read by agents at session start and updated as work progresses.

---

### The Problem This Solves

AI coding agents have no lasting memory. Every session starts from scratch.

1. **Session amnesia.** You explain the same context over and over. The agent re-discovers things you already told it. Previous sessions might as well not have happened.

2. **No portability.** Move your project from Claude Code to Codex, or from your laptop to a teammate's machine, and all agent context is lost. Chat history doesn't travel with the code.

3. **No shared project memory.** When a teammate (human or AI) picks up your work, they start from zero. There's no structured record of what was tried, what was decided, or what went wrong.

Existing memory solutions store memories in external databases (Milvus, ChromaDB, PostgreSQL, proprietary formats). That memory is opaque, not version-controlled, not human-readable, and not portable. Platform-specific tools like Claude Tandem add structured memory files, but they're locked to a single agent and have no cloud-backed session search.

---

### How It Works

**coding-agent-memory-kit** implements Memory as an Artifact with two layers:

### Layer 1: Long-Term Memory → Repo Artifacts

The markdown files above, committed to your repo. Any agent that can read files has instant project context. No API calls, no database, no setup required for this layer.

### Layer 2: Short-Term Memory → Azure Cosmos DB

Full session transcripts, semantic search, fact extraction, thread summaries, and cross-session user profiles — powered by [AgentMemoryToolkit](https://github.com/TheovanKraay/AgentMemoryToolkit) and Azure Cosmos DB.

The repo stores **pointers** to Cosmos DB sessions (session ID, date, agent, thread reference) — never raw chat content. This gives you:

- **Semantic search** across all past sessions ("what did we decide about authentication?")
- **Hybrid search** (vector + full-text) for precise recall
- **Fact extraction** — discrete, searchable assertions pulled from conversations
- **Thread summaries** — compressed recaps of long sessions
- **User profiles** — cross-session context that builds over time

### Where This Fits

| | Generic AI Memory (Mem0, MemSearch, Memvid, Hindsight) | Platform-Specific (Claude Tandem) | **Memory as an Artifact** |
|---|---|---|---|
| **Memory location** | External DB — opaque, invisible | Local files — platform-locked | Repo artifacts (git-tracked) + cloud for sessions |
| **Human-readable** | No | Partially | Yes — structured markdown with project semantics |
| **Version-controlled** | No | Partially (gitignored files) | Fully — committed, reviewable in PRs |
| **Portable across agents** | No — tied to the memory runtime | No — Claude Code only | Yes — any agent that reads markdown |
| **Portable across developers** | No — requires memory service access | No — single-developer | Yes — `git clone` gives full project context |
| **Searchable session history** | Vector search over flat memory | No cloud search | Vector + hybrid search via Cosmos DB |
| **Derived memory** | Hindsight has "reflect" | No | Summaries, facts, profiles via Durable Functions |
| **Designed for** | Generic AI chat recall | Claude Code gaps | Coding projects — decisions, state, failures, architecture |

### The Lifecycle

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

---

### Architecture

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

## Documentation

- **[SKILL.md](.github/skills/repo-memory/SKILL.md)** — Full agent instructions and CLI reference
- **[Architecture](docs/architecture.md)** — Design rationale and layers
- **[Quick Start Guide](docs/quickstart.md)** — Step-by-step setup


## License

MIT

