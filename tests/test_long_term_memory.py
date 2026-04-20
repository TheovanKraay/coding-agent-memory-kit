"""Tests for long_term_memory module."""

import tempfile
from pathlib import Path

from repo_memory import LongTermMemoryManager, Decision, StateEntry, FailureRecord, ChangelogEntry


def _setup_repo(tmp: Path) -> LongTermMemoryManager:
    """Create a temp repo with template files."""
    for name in ("STATE.md", "DECISIONS.md", "FAILURES.md", "CHANGELOG.md"):
        src = Path(__file__).resolve().parent.parent / name
        if src.exists():
            (tmp / name).write_text(src.read_text())
        else:
            (tmp / name).write_text(f"# {name}\n")
    return LongTermMemoryManager(tmp)


def test_update_state():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = _setup_repo(Path(tmp))
        mgr.update_state(StateEntry(item="Feature X", description="Building it", agent_id="bot"))
        content = mgr.get_state()
        assert "Feature X" in content
        assert "Building it" in content


def test_log_decision():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = _setup_repo(Path(tmp))
        mgr.log_decision(Decision(
            title="Use Python",
            context="Need a language",
            decision="Python",
            rationale="Ecosystem",
        ))
        content = mgr.get_decisions()
        assert "Use Python" in content
        assert "DEC-005" in content  # after the 4 already in template


def test_log_failure():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = _setup_repo(Path(tmp))
        mgr.log_failure(FailureRecord(
            title="Deploy failed",
            what_happened="Timeout",
            root_cause="Network",
            resolution="Retry",
            lesson="Add retries",
        ))
        content = mgr.get_failures()
        assert "Deploy failed" in content
        assert "FAIL-001" in content
        assert "No failures recorded" not in content


def test_append_changelog():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = _setup_repo(Path(tmp))
        mgr.append_changelog(ChangelogEntry(version="0.2.0", description="New feature", category="Added"))
        content = mgr.get_changelog()
        assert "0.2.0" in content
        assert "New feature" in content
