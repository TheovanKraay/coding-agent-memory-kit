# Repo Memory Skill

Persistent cross-session memory for coding agents. Uses [AgentMemoryToolkit](https://github.com/TheovanKraay/AgentMemoryToolkit) as the engine — this skill is a thin CLI wrapper plus markdown conventions.

## Prerequisites

1. **Azure Cosmos DB account** (NoSQL API) with vector search enabled
2. **`az login`** completed (uses `DefaultAzureCredential`)
3. **Environment variables** set:

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `COSMOS_DB_ENDPOINT` | Yes | — | Cosmos DB account URI |
| `COSMOS_DB_DATABASE` | No | `agent_memory` | Database name |
| `COSMOS_DB_CONTAINER` | No | `memories` | Container name |
| `AI_FOUNDRY_ENDPOINT` | No | — | Azure AI Foundry (embeddings) |
| `EMBEDDING_MODEL` | No | `text-embedding-3-large` | Embedding model |
| `ADF_ENDPOINT` | No | — | Azure Durable Functions endpoint |
| `ADF_KEY` | No | — | Durable Functions key |

4. **Install dependencies** (one-time):
   ```bash
   bash .github/skills/repo-memory/setup.sh
   ```

## CLI Reference

All commands go through a single script:

```bash
CLI=".github/skills/repo-memory/scripts/memory_cli.py"
```

### init — Set up store & templates

```bash
python $CLI init
```

Creates the Cosmos DB database/container (with vector + fulltext indexes, hierarchical partition key) and copies markdown templates (`STATE.md`, `DECISIONS.md`, `AGENTS.md`, `CHANGELOG.md`, `FAILURES.md`) to the repo root if they don't exist.

### add — Store a single memory

```bash
python $CLI add \
  --user-id <agent-id> \
  --thread-id <session-id> \
  --role agent \
  --content "Decided to use retry logic for transient failures" \
  --memory-type turn \
  --agent-id <agent-id>
```

Roles: `user`, `agent`, `tool`, `system`
Memory types: `turn`, `summary`, `fact`, `user_summary`

### sync — Bulk upload turns

Write turns to a JSON file, then sync:

```bash
cat > /tmp/turns.json << 'EOF'
[
  {"user_id": "agent-1", "thread_id": "sess-001", "role": "user", "content": "Fix the auth bug"},
  {"user_id": "agent-1", "thread_id": "sess-001", "role": "agent", "content": "Found root cause in token refresh"}
]
EOF
python $CLI sync --turns-file /tmp/turns.json
```

### get-thread — Retrieve thread history

```bash
python $CLI get-thread --thread-id sess-001 --user-id agent-1 --recent-k 20
```

### get-memories — Filtered retrieval

```bash
python $CLI get-memories --user-id agent-1 --memory-type fact --recent-k 10
```

### search — Vector / hybrid search

```bash
# Semantic search
python $CLI search --query "auth decision" --user-id agent-1 --memory-type fact --top-k 5

# Hybrid search (vector + full-text via RRF)
python $CLI search --query "auth decision" --user-id agent-1 --hybrid
```

### get-user-summary — Cross-thread profile

```bash
python $CLI get-user-summary --user-id agent-1
```

### summarize-thread — Generate summary (Durable Functions)

```bash
python $CLI summarize-thread --user-id agent-1 --thread-id sess-001 --recent-k 50
```

### extract-facts — Extract facts (Durable Functions)

```bash
python $CLI extract-facts --user-id agent-1 --thread-id sess-001 --recent-k 50
```

### summarize-user — Generate user summary (Durable Functions)

```bash
python $CLI summarize-user --user-id agent-1 --thread-ids sess-001,sess-002,sess-003
```

---

## Session Lifecycle

### On Session Start

1. **Initialise:**
   ```bash
   python $CLI init
   ```
2. **Read context:** Open `STATE.md` and `DECISIONS.md` for project state.
3. **Rehydrate from Cosmos (optional):**
   ```bash
   python $CLI get-user-summary --user-id <agent-id>
   python $CLI search --query "<current task description>" --user-id <agent-id> --memory-type fact --top-k 10
   ```

### During Session

- **Log decisions** → append to `DECISIONS.md`
- **Log state changes** → update `STATE.md`
- **Log failures** → append to `FAILURES.md`
- **Store turns** individually or batch via `sync`

### On Session End

1. **Generate thread summary:**
   ```bash
   python $CLI summarize-thread --user-id <agent-id> --thread-id <session-id>
   ```
2. **Extract facts:**
   ```bash
   python $CLI extract-facts --user-id <agent-id> --thread-id <session-id>
   ```
3. **Update user summary:**
   ```bash
   python $CLI summarize-user --user-id <agent-id>
   ```
4. **Update markdown files** — add a row to the `## Session References` table in each changed file:
   ```markdown
   | 2024-12-20 | sess-001 | agent-1 | Fixed auth token refresh bug |
   ```
5. **Commit markdown changes:**
   ```bash
   git add STATE.md DECISIONS.md CHANGELOG.md FAILURES.md AGENTS.md
   git commit -m "session sess-001: <summary>"
   ```

### Searching Previous Sessions

```bash
# Semantic search across all facts
python $CLI search --query "what was the auth decision" --user-id <agent-id> --memory-type fact

# Hybrid search
python $CLI search --query "retry logic" --user-id <agent-id> --hybrid

# Full thread replay
python $CLI get-thread --thread-id sess-001
```

## Markdown Files

Each markdown file in the repo root serves as human-readable, git-tracked memory. Chat content is **never** stored in these files — only summaries, decisions, and references to Cosmos DB threads.

Every file ends with a `## Session References` table linking to thread IDs stored in Cosmos DB.

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌────────────────────┐     ┌──────────────┐
│  Repo Markdown  │◄───►│  memory_cli  │◄───►│ AgentMemoryToolkit │◄───►│  Cosmos DB   │
│  (STATE.md etc) │     │  (this CLI)  │     │ CosmosMemoryClient │     │ + AI Foundry │
└─────────────────┘     └──────────────┘     └────────────────────┘     └──────────────┘
```

Markdown = portable, human-readable, git-tracked.
Cosmos DB = searchable, scalable, vector-indexed.
The CLI bridges both worlds.
