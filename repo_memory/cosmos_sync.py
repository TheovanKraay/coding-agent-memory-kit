"""Cosmos DB session sync — wraps AgentMemoryToolkit for session persistence."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from .models import SessionTurn
from .session_store import SessionMemoryStore


class CosmosSessionSync:
    """Syncs local session memory to/from Cosmos DB via AgentMemoryToolkit.

    Parameters
    ----------
    cosmos_client : CosmosMemoryClient
        An initialized ``agent_memory_toolkit.CosmosMemoryClient``.
    user_id : str
        The user/project identifier for partition key.
    thread_id : str, optional
        Thread identifier. Auto-generated if not provided.
    """

    def __init__(
        self,
        cosmos_client: Any,  # CosmosMemoryClient — Any to avoid hard import
        user_id: str,
        thread_id: Optional[str] = None,
    ) -> None:
        self.client = cosmos_client
        self.user_id = user_id
        self.thread_id = thread_id or str(uuid.uuid4())

    def sync_to_cosmos(self, store: SessionMemoryStore) -> list[str]:
        """Persist all turns from *store* to Cosmos DB. Returns created IDs."""
        ids: list[str] = []
        for turn in store.get_all():
            record_id = self.client.add_memory(
                user_id=self.user_id,
                thread_id=self.thread_id,
                role=turn.role.value,
                content=turn.content,
                memory_type="turn",
                metadata={
                    "agent_id": turn.agent_id or "",
                    "tool_name": turn.tool_name or "",
                    **turn.metadata,
                },
            )
            ids.append(record_id)
        return ids

    def rehydrate_session(self, store: SessionMemoryStore, limit: int = 50) -> int:
        """Load previous turns from Cosmos into *store*. Returns count loaded."""
        records = self.client.get_memories(
            user_id=self.user_id,
            thread_id=self.thread_id,
            limit=limit,
        )
        count = 0
        for rec in records:
            role = rec.get("role", "system") if isinstance(rec, dict) else getattr(rec, "role", "system")
            content = rec.get("content", "") if isinstance(rec, dict) else getattr(rec, "content", "")
            metadata = rec.get("metadata", {}) if isinstance(rec, dict) else getattr(rec, "metadata", {})
            store.add_turn(
                role=role,
                content=content,
                agent_id=metadata.get("agent_id"),
                tool_name=metadata.get("tool_name"),
            )
            count += 1
        return count

    def search_memories(self, query: str, limit: int = 10) -> list[Any]:
        """Semantic search across memories for this user."""
        return self.client.search_memories(
            user_id=self.user_id,
            query=query,
            limit=limit,
        )
