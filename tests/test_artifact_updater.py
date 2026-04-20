"""Tests for artifact_updater module."""

import tempfile
from pathlib import Path

from repo_memory import (
    LongTermMemoryManager,
    MemoryArtifactUpdater,
    SessionMemoryStore,
)


def _setup(tmp: Path):
    for name in ("STATE.md", "DECISIONS.md", "FAILURES.md", "CHANGELOG.md"):
        src = Path(__file__).resolve().parent.parent / name
        if src.exists():
            (tmp / name).write_text(src.read_text())
        else:
            (tmp / name).write_text(f"# {name}\n")
    mgr = LongTermMemoryManager(tmp)
    return MemoryArtifactUpdater(mgr)


def test_update_from_session_with_decision():
    with tempfile.TemporaryDirectory() as tmp:
        updater = _setup(Path(tmp))
        store = SessionMemoryStore()
        store.add_turn("agent", "Decided to use Rust", metadata={
            "decision": {
                "title": "Use Rust",
                "context": "Performance needed",
                "decision": "Rust",
                "rationale": "Fast",
            }
        })
        result = updater.update_from_session(store, version="0.3.0")
        assert result["decisions"] == 1
        assert result["changelog"] == 1


def test_update_from_session_with_state_and_failure():
    with tempfile.TemporaryDirectory() as tmp:
        updater = _setup(Path(tmp))
        store = SessionMemoryStore()
        store.add_turn("agent", "Started work", metadata={
            "state_change": {
                "item": "API redesign",
                "description": "Refactoring endpoints",
                "status": "in_progress",
            }
        })
        store.add_turn("agent", "Hit a bug", metadata={
            "failure": {
                "title": "Import error",
                "what_happened": "Module not found",
                "root_cause": "Missing dep",
            }
        })
        result = updater.update_from_session(store)
        assert result["state_changes"] == 1
        assert result["failures"] == 1
        assert result["changelog"] == 0  # no version provided


def test_extract_decisions_empty():
    store = SessionMemoryStore()
    store.add_turn("user", "hello")
    assert MemoryArtifactUpdater.extract_decisions(store.get_all()) == []
