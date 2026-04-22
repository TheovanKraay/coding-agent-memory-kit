# Quick Start

## 1. Prerequisites

- **Azure Cosmos DB** (NoSQL API) with vector search enabled
- **Python 3.10+**
- **Azure CLI** logged in: `az login`

## 2. Clone the repo

```bash
git clone https://github.com/TheovanKraay/coding-agent-memory-kit.git
cd coding-agent-memory-kit
```

## 3. Set environment variables

```bash
export COSMOS_DB_ENDPOINT="https://your-account.documents.azure.com:443/"

# Optional — for embeddings and search
export AI_FOUNDRY_ENDPOINT="https://your-foundry.cognitiveservices.azure.com/"

# Optional — for Durable Functions pipelines (summarise, extract facts)
export ADF_ENDPOINT="https://your-functions.azurewebsites.net"
export ADF_KEY="your-function-key"
```

## 4. Install and initialise

```bash
bash .github/skills/repo-memory/setup.sh
```

This installs `agent-memory-toolkit` (which brings in `azure-cosmos`, `openai`, `pydantic`, etc.) and creates the Cosmos DB database + container with vector indexes.

## 5. Verify

```bash
python .github/skills/repo-memory/scripts/memory_cli.py add \
  --user-id test-agent --thread-id test-001 --role agent \
  --content "Setup verified successfully"

python .github/skills/repo-memory/scripts/memory_cli.py get-thread \
  --thread-id test-001 --user-id test-agent
```

## 6. Point your agent at the skill

Add `.github/skills/repo-memory/SKILL.md` to your agent's context. It contains full lifecycle instructions (session start → during → end) and CLI reference.

## Next Steps

- Read [SKILL.md](../.github/skills/repo-memory/SKILL.md) for the full agent workflow
- Read [Architecture](architecture.md) for design rationale
