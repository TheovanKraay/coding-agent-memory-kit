# coding-agent-memory-kit

A drop-in GitHub Skill that gives any coding agent persistent, searchable memory across sessions. Powered by [AgentMemoryToolkit](https://github.com/TheovanKraay/AgentMemoryToolkit) — this repo is a thin CLI wrapper and markdown convention layer on top of it.

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
