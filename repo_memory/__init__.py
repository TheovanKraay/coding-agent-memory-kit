"""coding-agent-memory-kit: cross-agent memory-as-artifact system."""

from .artifact_updater import MemoryArtifactUpdater
from .cosmos_sync import CosmosSessionSync
from .long_term_memory import LongTermMemoryManager
from .models import (
    ChangelogEntry,
    Decision,
    FailureRecord,
    SessionTurn,
    StateEntry,
    TurnRole,
)
from .session_store import SessionMemoryStore
from .transcript_adapter import AgentTranscriptAdapter

__all__ = [
    "LongTermMemoryManager",
    "SessionMemoryStore",
    "CosmosSessionSync",
    "AgentTranscriptAdapter",
    "MemoryArtifactUpdater",
    "SessionTurn",
    "Decision",
    "StateEntry",
    "FailureRecord",
    "ChangelogEntry",
    "TurnRole",
]
