"""Tests for models module."""

from repo_memory.models import SessionTurn, Decision, StateEntry, FailureRecord, ChangelogEntry, TurnRole


def test_session_turn_defaults():
    t = SessionTurn(role=TurnRole.user, content="hi")
    assert t.role == TurnRole.user
    assert t.timestamp is not None
    assert t.metadata == {}


def test_decision_defaults():
    d = Decision(title="T", context="C", decision="D", rationale="R")
    assert d.status == "accepted"


def test_state_entry_defaults():
    s = StateEntry(item="X", description="Y")
    assert s.status == "in_progress"


def test_failure_record():
    f = FailureRecord(title="F", what_happened="W", root_cause="R")
    assert f.resolution == ""


def test_changelog_entry():
    c = ChangelogEntry(version="1.0", description="init")
    assert c.category == "Added"
