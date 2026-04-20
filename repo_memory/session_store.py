"""Session memory store — in-memory short-term memory for a single session."""

from __future__ import annotations

from typing import Optional

from .models import SessionTurn, TurnRole


class SessionMemoryStore:
    """In-memory store for conversation turns and session context.

    Tracks turns, tool calls, and decisions within a single agent session.
    Contents are ephemeral — sync to Cosmos or promote to repo artifacts
    before the session ends.
    """

    def __init__(self, session_id: Optional[str] = None, agent_id: Optional[str] = None) -> None:
        self.session_id = session_id
        self.agent_id = agent_id
        self._turns: list[SessionTurn] = []

    # -- mutators -----------------------------------------------------------

    def add_turn(
        self,
        role: str | TurnRole,
        content: str,
        *,
        agent_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> SessionTurn:
        """Append a conversation turn and return it."""
        turn = SessionTurn(
            role=TurnRole(role),
            content=content,
            agent_id=agent_id or self.agent_id,
            tool_name=tool_name,
            metadata=metadata or {},
        )
        self._turns.append(turn)
        return turn

    def clear(self) -> None:
        """Remove all turns."""
        self._turns.clear()

    # -- queries ------------------------------------------------------------

    def get_all(self) -> list[SessionTurn]:
        """Return all turns."""
        return list(self._turns)

    def get_recent(self, n: int = 10) -> list[SessionTurn]:
        """Return the *n* most recent turns."""
        return list(self._turns[-n:])

    def get_by_type(self, role: str | TurnRole) -> list[SessionTurn]:
        """Return turns matching a specific role."""
        target = TurnRole(role)
        return [t for t in self._turns if t.role == target]

    def __len__(self) -> int:
        return len(self._turns)
