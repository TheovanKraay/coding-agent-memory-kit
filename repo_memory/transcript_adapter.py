"""Transcript adapter — converts between agent formats and memory records."""

from __future__ import annotations

from typing import Any

from .models import SessionTurn, TurnRole


class AgentTranscriptAdapter:
    """Converts between common agent transcript formats and SessionTurns.

    Supports OpenAI chat messages, Anthropic messages, and raw text.
    """

    # -- from formats -------------------------------------------------------

    @staticmethod
    def from_openai(messages: list[dict[str, Any]]) -> list[SessionTurn]:
        """Convert OpenAI-format messages to SessionTurns.

        Expected format: ``[{"role": "user"|"assistant"|"system"|"tool", "content": "..."}]``
        """
        role_map = {"assistant": "agent", "function": "tool"}
        turns: list[SessionTurn] = []
        for msg in messages:
            raw_role = msg.get("role", "user")
            role = role_map.get(raw_role, raw_role)
            content = msg.get("content") or ""
            if isinstance(content, list):
                # multimodal: extract text parts
                content = " ".join(
                    p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"
                )
            turns.append(SessionTurn(
                role=TurnRole(role),
                content=content,
                tool_name=msg.get("name") or msg.get("tool_call_id"),
                metadata={k: v for k, v in msg.items() if k not in ("role", "content", "name", "tool_call_id")},
            ))
        return turns

    @staticmethod
    def from_anthropic(messages: list[dict[str, Any]]) -> list[SessionTurn]:
        """Convert Anthropic-format messages to SessionTurns.

        Expected format: ``[{"role": "user"|"assistant", "content": "..." | [...]}]``
        """
        turns: list[SessionTurn] = []
        for msg in messages:
            raw_role = msg.get("role", "user")
            role = "agent" if raw_role == "assistant" else raw_role
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text"
                )
            turns.append(SessionTurn(
                role=TurnRole(role),
                content=content,
            ))
        return turns

    @staticmethod
    def from_raw_text(text: str, role: str = "user") -> list[SessionTurn]:
        """Wrap raw text as a single SessionTurn."""
        return [SessionTurn(role=TurnRole(role), content=text)]

    # -- to memory records --------------------------------------------------

    @staticmethod
    def to_memory_dicts(turns: list[SessionTurn], user_id: str, thread_id: str) -> list[dict[str, Any]]:
        """Convert SessionTurns to dicts compatible with AgentMemoryToolkit's MemoryRecord.

        Returns dicts with fields matching ``MemoryRecord`` constructor kwargs.
        """
        records: list[dict[str, Any]] = []
        for turn in turns:
            records.append({
                "user_id": user_id,
                "thread_id": thread_id,
                "role": turn.role.value,
                "content": turn.content,
                "memory_type": "turn",
                "metadata": {
                    "agent_id": turn.agent_id or "",
                    "tool_name": turn.tool_name or "",
                    **turn.metadata,
                },
            })
        return records
