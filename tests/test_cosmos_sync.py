"""Tests for cosmos_sync module (mocked)."""

from unittest.mock import MagicMock

from repo_memory import CosmosSessionSync, SessionMemoryStore


def test_sync_to_cosmos():
    mock_client = MagicMock()
    mock_client.add_memory.return_value = "id-123"

    sync = CosmosSessionSync(mock_client, user_id="u1", thread_id="t1")
    store = SessionMemoryStore()
    store.add_turn("user", "hello")
    store.add_turn("agent", "hi")

    ids = sync.sync_to_cosmos(store)
    assert len(ids) == 2
    assert mock_client.add_memory.call_count == 2


def test_rehydrate_session():
    mock_client = MagicMock()
    mock_client.get_memories.return_value = [
        {"role": "user", "content": "prev msg", "metadata": {}},
        {"role": "agent", "content": "prev response", "metadata": {}},
    ]

    sync = CosmosSessionSync(mock_client, user_id="u1", thread_id="t1")
    store = SessionMemoryStore()
    count = sync.rehydrate_session(store)
    assert count == 2
    assert len(store) == 2


def test_search_memories():
    mock_client = MagicMock()
    mock_client.search_memories.return_value = [{"content": "result"}]

    sync = CosmosSessionSync(mock_client, user_id="u1")
    results = sync.search_memories("test query")
    assert len(results) == 1
    mock_client.search_memories.assert_called_once()
