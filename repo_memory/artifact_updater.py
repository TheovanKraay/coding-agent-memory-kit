"""Artifact updater — promotes session data to repo markdown files."""

from __future__ import annotations

import re
from typing import Optional

from .long_term_memory import LongTermMemoryManager
from .models import ChangelogEntry, Decision, FailureRecord, SessionTurn, StateEntry
from .session_store import SessionMemoryStore


class MemoryArtifactUpdater:
    """Orchestrates updating repo markdown files from session memory.

    At the end of a session, extracts decisions, state changes, and failures
    from the in-memory session store and writes them to the long-term
    markdown artifacts.

    Parameters
    ----------
    memory_manager : LongTermMemoryManager
        The manager for reading/writing markdown files.
    """

    def __init__(self, memory_manager: LongTermMemoryManager) -> None:
        self.manager = memory_manager

    # -- extraction ---------------------------------------------------------

    @staticmethod
    def extract_decisions(turns: list[SessionTurn]) -> list[Decision]:
        """Extract decisions from turns whose metadata contains ``decision`` key."""
        decisions: list[Decision] = []
        for turn in turns:
            if "decision" in turn.metadata:
                d = turn.metadata["decision"]
                if isinstance(d, dict):
                    decisions.append(Decision(**d))
                elif isinstance(d, Decision):
                    decisions.append(d)
        return decisions

    @staticmethod
    def extract_state_changes(turns: list[SessionTurn]) -> list[StateEntry]:
        """Extract state changes from turns whose metadata contains ``state_change`` key."""
        entries: list[StateEntry] = []
        for turn in turns:
            if "state_change" in turn.metadata:
                s = turn.metadata["state_change"]
                if isinstance(s, dict):
                    entries.append(StateEntry(**s))
                elif isinstance(s, StateEntry):
                    entries.append(s)
        return entries

    @staticmethod
    def extract_failures(turns: list[SessionTurn]) -> list[FailureRecord]:
        """Extract failures from turns whose metadata contains ``failure`` key."""
        failures: list[FailureRecord] = []
        for turn in turns:
            if "failure" in turn.metadata:
                f = turn.metadata["failure"]
                if isinstance(f, dict):
                    failures.append(FailureRecord(**f))
                elif isinstance(f, FailureRecord):
                    failures.append(f)
        return failures

    # -- update -------------------------------------------------------------

    def update_from_session(
        self,
        store: SessionMemoryStore,
        version: Optional[str] = None,
    ) -> dict[str, int]:
        """Extract and write all artifacts from a session store.

        Returns a summary dict with counts of items written per category.
        """
        turns = store.get_all()
        summary: dict[str, int] = {"decisions": 0, "state_changes": 0, "failures": 0, "changelog": 0}

        for dec in self.extract_decisions(turns):
            self.manager.log_decision(dec)
            summary["decisions"] += 1

        for state in self.extract_state_changes(turns):
            self.manager.update_state(state)
            summary["state_changes"] += 1

        for fail in self.extract_failures(turns):
            self.manager.log_failure(fail)
            summary["failures"] += 1

        # Auto-append changelog if version provided and anything was written
        if version and any(v > 0 for v in summary.values()):
            parts = []
            if summary["decisions"]:
                parts.append(f"{summary['decisions']} decision(s)")
            if summary["state_changes"]:
                parts.append(f"{summary['state_changes']} state change(s)")
            if summary["failures"]:
                parts.append(f"{summary['failures']} failure(s)")
            self.manager.append_changelog(ChangelogEntry(
                version=version,
                description="Session artifacts: " + ", ".join(parts),
                category="Changed",
            ))
            summary["changelog"] = 1

        return summary
