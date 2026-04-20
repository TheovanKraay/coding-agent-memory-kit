"""Tests for session_store module."""

from repo_memory import SessionMemoryStore, TurnRole


def test_add_and_get_turns():
    store = SessionMemoryStore(session_id="s1", agent_id="agent-1")
    store.add_turn("user", "Hello")
    store.add_turn("agent", "Hi there")
    assert len(store) == 2
    assert store.get_all()[0].content == "Hello"
    assert store.get_all()[1].role == TurnRole.agent


def test_get_recent():
    store = SessionMemoryStore()
    for i in range(20):
        store.add_turn("user", f"msg-{i}")
    recent = store.get_recent(5)
    assert len(recent) == 5
    assert recent[0].content == "msg-15"


def test_get_by_type():
    store = SessionMemoryStore()
    store.add_turn("user", "u1")
    store.add_turn("agent", "a1")
    store.add_turn("tool", "t1")
    store.add_turn("user", "u2")
    assert len(store.get_by_type("user")) == 2
    assert len(store.get_by_type("tool")) == 1


def test_clear():
    store = SessionMemoryStore()
    store.add_turn("user", "hi")
    store.clear()
    assert len(store) == 0


def test_agent_id_default():
    store = SessionMemoryStore(agent_id="default-agent")
    turn = store.add_turn("agent", "response")
    assert turn.agent_id == "default-agent"


def test_agent_id_override():
    store = SessionMemoryStore(agent_id="default")
    turn = store.add_turn("agent", "response", agent_id="override")
    assert turn.agent_id == "override"
