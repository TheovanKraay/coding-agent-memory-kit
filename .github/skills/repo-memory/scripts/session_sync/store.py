"""Session storage layer for Cosmos DB.

Stores sessions as individual turn documents plus one metadata document
per session, all sharing the same partition key (cosmos_session_id).

Uses CosmosMemoryClient from AgentMemoryToolkit under the hood, mapping:
  - user_id → agent/user identifier
  - thread_id → cosmos_session_id (our generated UUID)
  - memory_type → "session_turn" or "session_meta"
"""

from __future__ import annotations

import json
import socket
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agent_memory_toolkit import CosmosMemoryClient


class SessionStore:
    """Cosmos DB storage for session sync.

    Each session is stored as:
    - One metadata document (memory_type="session_meta") with summary, fingerprint,
      platform_ids map, and session-level fields.
    - N turn documents (memory_type="session_turn"), one per conversation message,
      ordered by turn_index.

    All documents for a session share thread_id = cosmos_session_id as the
    partition key.
    """

    def __init__(self, client: CosmosMemoryClient, user_id: str):
        self._client = client
        self._user_id = user_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save_session(
        self,
        data: Dict[str, Any],
        cosmos_session_id: Optional[str] = None,
    ) -> str:
        """Save a session (from adapter export) to Cosmos DB.

        Args:
            data: Dict with 'metadata' and 'turns' keys (adapter export format).
            cosmos_session_id: Existing Cosmos session ID for updates.
                Generated if None (new session).

        Returns:
            The cosmos_session_id used.
        """
        if cosmos_session_id is None:
            cosmos_session_id = str(uuid.uuid4())

        meta = data.get("metadata", {})
        turns = data.get("turns", [])
        platform = meta.get("platform", "unknown")
        platform_session_id = meta.get("platform_session_id", "")
        now = datetime.now(timezone.utc).isoformat()

        # Check for existing metadata doc to preserve platform_ids
        existing_meta = self._get_meta_doc(cosmos_session_id)
        if existing_meta:
            platform_ids = existing_meta.get("platform_ids", {})
        else:
            platform_ids = {}

        if platform_session_id:
            platform_ids[platform] = platform_session_id

        # Build and store metadata document
        meta_content = json.dumps({
            "session_id": cosmos_session_id,
            "memory_type": "session_meta",
            "platform": platform,
            "platform_session_id": platform_session_id,
            "platform_ids": platform_ids,
            "machine_hostname": socket.gethostname(),
            "workspace_path": meta.get("workspace", ""),
            "summary": meta.get("summary", ""),
            "fingerprint": meta.get("fingerprint", ""),
            "model": meta.get("model", ""),
            "turn_count": len(turns),
            "created_at": meta.get("created_at") or now,
            "updated_at": now,
        })

        meta_doc_id = f"meta-{cosmos_session_id}"
        self._client.add_cosmos(
            user_id=self._user_id,
            thread_id=cosmos_session_id,
            role="system",
            content=meta.get("summary", "") or f"Session {cosmos_session_id}",
            memory_type="session_meta",
            metadata={
                "doc_id": meta_doc_id,
                "session_id": cosmos_session_id,
                "platform": platform,
                "platform_session_id": platform_session_id,
                "platform_ids": platform_ids,
                "machine_hostname": socket.gethostname(),
                "workspace_path": meta.get("workspace", ""),
                "fingerprint": meta.get("fingerprint", ""),
                "model": meta.get("model", ""),
                "turn_count": len(turns),
                "created_at": meta.get("created_at") or now,
                "updated_at": now,
                "session_meta_payload": meta_content,
            },
        )

        # Store each turn as a separate document
        for i, turn in enumerate(turns):
            turn_id = str(uuid.uuid4())
            turn_content = turn.get("content", "")
            tool_use = turn.get("tool_use")

            self._client.add_cosmos(
                user_id=self._user_id,
                thread_id=cosmos_session_id,
                role=turn.get("role", "user"),
                content=turn_content or f"[turn {i}]",
                memory_type="session_turn",
                metadata={
                    "doc_id": turn_id,
                    "session_id": cosmos_session_id,
                    "platform_session_id": platform_session_id,
                    "platform": platform,
                    "turn_index": i,
                    "tool_use": json.dumps(tool_use) if tool_use else None,
                    "created_at": meta.get("created_at") or now,
                },
            )

        return cosmos_session_id

    def get_session(self, cosmos_session_id: str) -> Dict[str, Any]:
        """Retrieve a full session from Cosmos DB.

        Returns dict with 'metadata' and 'turns' keys (same format adapters consume).
        """
        # Get all records for this session (thread_id = cosmos_session_id)
        records = self._client.get_thread(
            thread_id=cosmos_session_id,
            user_id=self._user_id,
        )

        if not records:
            raise FileNotFoundError(f"Session '{cosmos_session_id}' not found in Cosmos DB")

        # Separate metadata from turns
        meta_record = None
        turn_records = []

        for r in records:
            rec = r.model_dump() if hasattr(r, "model_dump") else r
            mt = rec.get("memory_type", "")
            if mt == "session_meta":
                meta_record = rec
            elif mt == "session_turn":
                turn_records.append(rec)

        if meta_record is None:
            raise ValueError(f"Session '{cosmos_session_id}' has no metadata document")

        # Reconstruct metadata
        meta_data = meta_record.get("metadata", {})
        metadata = {
            "platform_session_id": meta_data.get("platform_session_id", ""),
            "platform": meta_data.get("platform", ""),
            "workspace": meta_data.get("workspace_path", ""),
            "model": meta_data.get("model", ""),
            "summary": meta_record.get("content", ""),
            "created_at": meta_data.get("created_at", ""),
            "updated_at": meta_data.get("updated_at", ""),
            "fingerprint": meta_data.get("fingerprint", ""),
            "platform_ids": meta_data.get("platform_ids", {}),
            "machine_hostname": meta_data.get("machine_hostname", ""),
            "turn_count": meta_data.get("turn_count", 0),
            "cosmos_session_id": cosmos_session_id,
        }

        # Sort turns by turn_index
        turn_records.sort(key=lambda r: (r.get("metadata") or {}).get("turn_index", 0))

        turns = []
        for tr in turn_records:
            tr_meta = tr.get("metadata", {}) or {}
            tool_use_raw = tr_meta.get("tool_use")
            tool_use = json.loads(tool_use_raw) if tool_use_raw else None
            turns.append({
                "role": tr.get("role", "user"),
                "content": tr.get("content", ""),
                "tool_use": tool_use,
            })

        return {"metadata": metadata, "turns": turns}

    def list_sessions(
        self,
        platform: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List session metadata docs from Cosmos DB.

        Returns a list of metadata dicts (no turns).
        """
        records = self._client.get_memories(
            user_id=self._user_id,
            memory_type="session_meta",
        )

        results = []
        for r in records:
            rec = r.model_dump() if hasattr(r, "model_dump") else r
            meta = rec.get("metadata", {}) or {}

            if platform and meta.get("platform") != platform:
                # Also check platform_ids
                pids = meta.get("platform_ids", {})
                if platform not in pids:
                    continue

            results.append({
                "cosmos_session_id": meta.get("session_id", ""),
                "platform": meta.get("platform", ""),
                "platform_session_id": meta.get("platform_session_id", ""),
                "platform_ids": meta.get("platform_ids", {}),
                "workspace_path": meta.get("workspace_path", ""),
                "machine_hostname": meta.get("machine_hostname", ""),
                "summary": rec.get("content", ""),
                "fingerprint": meta.get("fingerprint", ""),
                "turn_count": meta.get("turn_count", 0),
                "created_at": meta.get("created_at", ""),
                "updated_at": meta.get("updated_at", ""),
            })

        return results

    def search_sessions(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Vector search over session metadata summaries."""
        results = self._client.search_cosmos(
            query=query,
            user_id=self._user_id,
            memory_type="session_meta",
            top_k=top_k,
        )

        sessions = []
        for r in results:
            rec = r.model_dump() if hasattr(r, "model_dump") else r
            meta = rec.get("metadata", {}) or {}
            sessions.append({
                "cosmos_session_id": meta.get("session_id", ""),
                "platform": meta.get("platform", ""),
                "summary": rec.get("content", ""),
                "workspace_path": meta.get("workspace_path", ""),
                "turn_count": meta.get("turn_count", 0),
                "score": rec.get("score"),
            })

        return sessions

    def update_platform_id(
        self,
        cosmos_session_id: str,
        platform: str,
        platform_session_id: str,
    ) -> None:
        """Record a new platform_session_id mapping in the session metadata.

        Called after importing a session to a new platform.
        """
        session = self.get_session(cosmos_session_id)
        meta = session["metadata"]
        platform_ids = meta.get("platform_ids", {})
        platform_ids[platform] = platform_session_id

        # Re-save the metadata (the save_session will preserve the updated platform_ids)
        meta["platform_ids"] = platform_ids
        # We only need to update the metadata doc, but since CosmosMemoryClient
        # doesn't expose an update-by-id, we re-save the full session
        # In practice, save_session checks for existing meta and merges platform_ids
        self.save_session(session, cosmos_session_id=cosmos_session_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_meta_doc(self, cosmos_session_id: str) -> Optional[Dict[str, Any]]:
        """Try to fetch an existing metadata doc for a session."""
        try:
            records = self._client.get_thread(
                thread_id=cosmos_session_id,
                user_id=self._user_id,
            )
            for r in records:
                rec = r.model_dump() if hasattr(r, "model_dump") else r
                if rec.get("memory_type") == "session_meta":
                    return rec.get("metadata", {})
        except Exception:
            pass
        return None

    def find_by_platform_id(
        self,
        platform: str,
        platform_session_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Find a Cosmos session by platform + platform_session_id.

        Searches the platform_ids map in metadata docs.
        """
        all_sessions = self.list_sessions()
        for s in all_sessions:
            pids = s.get("platform_ids", {})
            if pids.get(platform) == platform_session_id:
                return s
        return None

    def find_by_fingerprint(self, fingerprint: str) -> Optional[Dict[str, Any]]:
        """Find a Cosmos session by fingerprint hash."""
        all_sessions = self.list_sessions()
        for s in all_sessions:
            if s.get("fingerprint") == fingerprint:
                return s
        return None
