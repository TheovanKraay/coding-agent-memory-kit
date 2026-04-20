# Extending the Memory System

## Custom Memory Types

Add new markdown artifacts by extending `LongTermMemoryManager`:

```python
from repo_memory import LongTermMemoryManager

class ExtendedMemory(LongTermMemoryManager):
    def log_experiment(self, name: str, result: str, notes: str) -> None:
        content = self._read("EXPERIMENTS.md")
        block = f"\n## {name}\n- **Result:** {result}\n- **Notes:** {notes}\n"
        self._write("EXPERIMENTS.md", content + block)
```

## Custom Session Metadata

Use the `metadata` dict on `add_turn()` to attach structured data:

```python
store.add_turn("agent", "Ran benchmark", metadata={
    "benchmark": {"name": "latency", "p99": 42, "unit": "ms"},
    "state_change": {"item": "Perf testing", "description": "Complete", "status": "done"},
})
```

The `MemoryArtifactUpdater` recognizes these metadata keys:
- `decision` — promotes to DECISIONS.md
- `state_change` — promotes to STATE.md
- `failure` — promotes to FAILURES.md

Add your own by subclassing `MemoryArtifactUpdater`:

```python
from repo_memory import MemoryArtifactUpdater

class CustomUpdater(MemoryArtifactUpdater):
    def update_from_session(self, store, version=None):
        summary = super().update_from_session(store, version)
        # Extract custom metadata
        for turn in store.get_all():
            if "benchmark" in turn.metadata:
                # Write to EXPERIMENTS.md or wherever
                pass
        return summary
```

## Custom Transcript Formats

Extend `AgentTranscriptAdapter` for your agent framework:

```python
from repo_memory import AgentTranscriptAdapter, SessionTurn, TurnRole

class MyAdapter(AgentTranscriptAdapter):
    @staticmethod
    def from_langchain(messages) -> list[SessionTurn]:
        return [
            SessionTurn(
                role=TurnRole.agent if msg.type == "ai" else TurnRole.user,
                content=msg.content,
            )
            for msg in messages
        ]
```

## Custom Cosmos DB Behavior

Subclass `CosmosSessionSync` to customize sync logic:

```python
from repo_memory import CosmosSessionSync

class FilteredSync(CosmosSessionSync):
    def sync_to_cosmos(self, store):
        # Only sync agent and user turns, skip tool calls
        original_turns = store.get_all()
        filtered = [t for t in original_turns if t.role.value in ("user", "agent")]
        # ... custom sync logic
```
