"""Pydantic models for the cross-agent memory system."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TurnRole(str, Enum):
    user = "user"
    agent = "agent"
    tool = "tool"
    system = "system"


class SessionTurn(BaseModel):
    """A single conversation turn within a session."""

    role: TurnRole
    content: str
    agent_id: Optional[str] = None
    tool_name: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=_utc_now)


class Decision(BaseModel):
    """An architectural or design decision."""

    title: str
    context: str
    decision: str
    rationale: str
    consequences: str = ""
    status: str = "accepted"
    date: datetime = Field(default_factory=_utc_now)
    agent_id: Optional[str] = None


class StateEntry(BaseModel):
    """A project state item."""

    item: str
    description: str
    status: str = "in_progress"  # in_progress | blocked | done
    agent_id: Optional[str] = None
    since: datetime = Field(default_factory=_utc_now)


class FailureRecord(BaseModel):
    """A failure event with lessons learned."""

    title: str
    what_happened: str
    root_cause: str
    resolution: str = ""
    lesson: str = ""
    agent_id: Optional[str] = None
    date: datetime = Field(default_factory=_utc_now)


class ChangelogEntry(BaseModel):
    """A changelog entry."""

    version: str
    description: str
    category: str = "Added"  # Added | Changed | Fixed | Removed
    date: datetime = Field(default_factory=_utc_now)
