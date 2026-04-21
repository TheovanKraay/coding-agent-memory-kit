# coding-agent-memory-kit

A **drop-in agent skill** that gives any coding agent (Codex, Copilot, Claude, Cursor, etc.) persistent memory across sessions. Install it in your repo, point it at Azure Cosmos DB, and forget about it. The agent handles the rest.

## Quick Start

1. **Copy the skill** into your repo:
   ```bash
   cp -r .github/skills/repo-memory/ your-repo/.github/skills/repo-memory/
   ```

2. **Create an Azure Cosmos DB NoSQL account** (just the account — the skill auto-creates the database and containers).

3. **Authenticate with Entra ID:**
   ```bash
   az login
   ```

4. **Set your endpoint:**
   ```bash
   export COSMOS_DB_ENDPOINT="https://your-account.documents.azure.com:443/"
   ```

5. **Run setup:**
   ```bash
   bash .github/skills/repo-memory/setup.sh
   ```

That's it. Your agent reads `.github/skills/repo-memory/SKILL.md` and knows what to do.

## How It Works

```
┌─────────────────────────────────────────────────┐
│  Your Repo                                      │
│                                                 │
│  DECISIONS.md  STATE.md  CHANGELOG.md  ...      │  ← Human-readable, git-tracked
│       │            │          │                  │
│       └────────────┼──────────┘                  │
│                    │                             │
│         ## Session References                    │  ← Pointers to Cosmos DB (never chat content)
│                    │                             │
│  .github/skills/repo-memory/                    │
│    SKILL.md        scripts/                     │  ← Agent reads SKILL.md, calls scripts
│                      memory_sync.py             │
└────────────────────┼────────────────────────────┘
                     │
              ┌──────▼──────┐
              │  Cosmos DB  │  ← Session transcripts (searchable, cross-agent)
              │  (NoSQL)    │
              └─────────────┘
```

- **Markdown files** = long-term memory (decisions, state, failures). Git-tracked, human-readable.
- **Cosmos DB** = session transcripts. Searchable, shared across agents. Never stored in the repo.
- **Session References** = the bridge. Markdown files point to Cosmos DB sessions, never contain chat content.

## Files Created in Your Repo Root

| File | Purpose |
|------|---------|
| `AGENTS.md` | Who works on this repo — humans and AI agents |
| `STATE.md` | Current project state: in progress, blocked, done |
| `DECISIONS.md` | Architecture Decision Records |
| `CHANGELOG.md` | What changed, when, by whom |
| `FAILURES.md` | What went wrong, lessons learned |

## Configuration

| Environment Variable | Required | Default | Description |
|---------------------|----------|---------|-------------|
| `COSMOS_DB_ENDPOINT` | Yes | — | Your Cosmos DB account endpoint |
| `COSMOS_DB_DATABASE` | No | `agent_memory` | Database name |

Auth is always **Entra ID** (`DefaultAzureCredential`). No connection strings, no keys in env vars.

## Agent Details

See [SKILL.md](.github/skills/repo-memory/SKILL.md) for the full agent instructions.

## License

MIT
