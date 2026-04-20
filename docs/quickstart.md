# Quick Start

## Install

```bash
git clone https://github.com/theovankraay/coding-agent-memory-kit.git
cd coding-agent-memory-kit
pip install -e ".[dev]"
```

## Basic Usage (No Cosmos DB)

```python
from repo_memory import (
    LongTermMemoryManager,
    SessionMemoryStore,
    MemoryArtifactUpdater,
    Decision,
    StateEntry,
)

# Point to your repo
memory = LongTermMemoryManager(".")

# Track state
memory.update_state(StateEntry(
    item="User auth",
    description="Implementing login flow",
    agent_id="agent-1",
))

# Log decisions
memory.log_decision(Decision(
    title="JWT for tokens",
    context="Need stateless auth",
    decision="Use JWT",
    rationale="Stateless, widely supported",
))

# Track a session
store = SessionMemoryStore(agent_id="agent-1")
store.add_turn("user", "Add password reset")
store.add_turn("agent", "Added reset endpoint at /api/reset")

# Promote to repo files
updater = MemoryArtifactUpdater(memory)
updater.update_from_session(store, version="0.1.1")
```

## With Cosmos DB

```python
from agent_memory_toolkit import CosmosMemoryClient
from repo_memory import CosmosSessionSync

client = CosmosMemoryClient(
    cosmos_endpoint="https://your-account.documents.azure.com",
    cosmos_database="agent-memory",
    cosmos_container="memories",
)

sync = CosmosSessionSync(client, user_id="my-project")

# Load previous context
sync.rehydrate_session(store)

# ... work ...

# Save session
sync.sync_to_cosmos(store)
```

## Converting Transcripts

```python
from repo_memory import AgentTranscriptAdapter

# OpenAI format
turns = AgentTranscriptAdapter.from_openai([
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi!"},
])

# Anthropic format
turns = AgentTranscriptAdapter.from_anthropic(messages)
```

## Run Tests

```bash
pytest
```
