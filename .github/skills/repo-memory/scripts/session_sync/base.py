"""Session adapter base class and common data structures."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional


@dataclass
class SessionInfo:
    """Metadata about a local session file."""

    id: str
    created_at: Optional[str] = None  # ISO-8601
    updated_at: Optional[str] = None  # ISO-8601
    workspace: Optional[str] = None
    summary_hint: Optional[str] = None
    path: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}

    def fingerprint(self) -> str:
        """Compute a correlation fingerprint for matching across machines.

        Uses created_at + first user message hint + workspace to produce a
        stable hash that survives platform ID reassignment.
        """
        data = (self.created_at or "") + (self.summary_hint or "")[:200] + (self.workspace or "")
        return "sha256:" + hashlib.sha256(data.encode("utf-8")).hexdigest()


def compute_fingerprint(created_at: str, first_message: str, workspace: str) -> str:
    """Standalone fingerprint computation matching SessionInfo.fingerprint()."""
    data = (created_at or "") + (first_message or "")[:200] + (workspace or "")
    return "sha256:" + hashlib.sha256(data.encode("utf-8")).hexdigest()


class SessionAdapter(ABC):
    """Abstract base class for platform-specific session adapters.

    Each adapter knows how to detect, read, write, and resume sessions
    for one specific coding agent platform.

    Export format (returned by export_session):
    {
        "metadata": {
            "platform_session_id": str,
            "platform": str,
            "workspace": str,
            "model": str,
            "summary": str,
            "created_at": str,  # ISO-8601
            "updated_at": str,  # ISO-8601
            "fingerprint": str,
        },
        "turns": [
            {"role": str, "content": str, "tool_use": Any|None},
            ...
        ]
    }

    Import format (received by import_session): same dict structure.
    """

    platform: str  # e.g. "claude-code", "copilot", "cursor", "codex"

    @abstractmethod
    def detect(self) -> bool:
        """Return True if this platform is installed on the current machine."""

    @abstractmethod
    def locate_sessions(self, workspace: Optional[str] = None) -> List[SessionInfo]:
        """Find local session files, optionally filtered by workspace path."""

    @abstractmethod
    def export_session(self, session_id: str) -> Dict[str, Any]:
        """Read a local session and return a portable dict with 'metadata' and 'turns' keys."""

    @abstractmethod
    def import_session(self, data: Dict[str, Any]) -> str:
        """Write session data to local platform state.

        Args:
            data: Dict with 'metadata' and 'turns' keys.

        Returns:
            The platform session ID of the imported/created session.
        """

    @abstractmethod
    def resume_command(self, session_id: str) -> str:
        """Return the CLI command or instructions to resume this session."""

    def _require_detected(self):
        """Helper: raise if platform is not detected."""
        if not self.detect():
            raise RuntimeError(
                f"Platform '{self.platform}' is not installed or not detected on this machine. "
                f"Cannot perform session operations."
            )
