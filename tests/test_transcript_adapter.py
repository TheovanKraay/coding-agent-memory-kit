"""Tests for transcript_adapter module."""

from repo_memory import AgentTranscriptAdapter, TurnRole


def test_from_openai():
    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello!"},
        {"role": "tool", "content": "result", "name": "search"},
    ]
    turns = AgentTranscriptAdapter.from_openai(messages)
    assert len(turns) == 4
    assert turns[0].role == TurnRole.system
    assert turns[2].role == TurnRole.agent  # assistant -> agent
    assert turns[3].tool_name == "search"


def test_from_anthropic():
    messages = [
        {"role": "user", "content": "What's up?"},
        {"role": "assistant", "content": [{"type": "text", "text": "Not much!"}]},
    ]
    turns = AgentTranscriptAdapter.from_anthropic(messages)
    assert len(turns) == 2
    assert turns[1].role == TurnRole.agent
    assert turns[1].content == "Not much!"


def test_from_raw_text():
    turns = AgentTranscriptAdapter.from_raw_text("Hello world")
    assert len(turns) == 1
    assert turns[0].content == "Hello world"


def test_to_memory_dicts():
    turns = AgentTranscriptAdapter.from_openai([
        {"role": "user", "content": "test"},
    ])
    dicts = AgentTranscriptAdapter.to_memory_dicts(turns, user_id="u1", thread_id="t1")
    assert len(dicts) == 1
    assert dicts[0]["user_id"] == "u1"
    assert dicts[0]["role"] == "user"


def test_openai_multimodal():
    messages = [
        {"role": "user", "content": [
            {"type": "text", "text": "Look at this"},
            {"type": "image_url", "image_url": {"url": "http://example.com/img.png"}},
        ]},
    ]
    turns = AgentTranscriptAdapter.from_openai(messages)
    assert turns[0].content == "Look at this"
