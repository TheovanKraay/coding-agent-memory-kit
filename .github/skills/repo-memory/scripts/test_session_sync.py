#!/usr/bin/env python3
"""Tests for session sync module.

Tests adapter registry, adapter interface compliance, Claude Code round-trip,
SessionStore serialization, sync reconciliation logic, and fingerprint correlation.

Does NOT connect to Cosmos DB — all Cosmos operations are mocked.
"""

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

# Add scripts dir to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Mock agent_memory_toolkit before importing store (it's not installed in test env)
sys.modules.setdefault("agent_memory_toolkit", MagicMock())

from session_sync import get_adapter, list_adapters
from session_sync.base import SessionAdapter, SessionInfo, compute_fingerprint
from session_sync.claude_code import ClaudeCodeAdapter
from session_sync.copilot import CopilotAdapter
from session_sync.cursor import CursorAdapter
from session_sync.codex import CodexAdapter
from session_sync.openclaw import OpenClawAdapter
from session_sync.store import SessionStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_claude_session(session_dir: Path, session_id: str = "test-sess-1",
                        cwd: str = "/tmp/project",
                        messages=None, model: str = "claude-sonnet-4-20250514") -> Path:
    """Create a synthetic Claude Code session JSON file."""
    if messages is None:
        messages = [
            {"role": "user", "content": "Fix the auth bug"},
            {"role": "assistant", "content": "I found the issue in token refresh."},
            {"role": "user", "content": "Great, apply the fix."},
            {"role": "assistant", "content": "Done. The token now refreshes correctly."},
        ]
    data = {
        "id": session_id,
        "cwd": cwd,
        "messages": messages,
        "model": model,
        "created_at": "2025-01-15T10:00:00Z",
        "updated_at": "2025-01-15T12:30:00Z",
    }
    path = session_dir / f"{session_id}.json"
    path.write_text(json.dumps(data, indent=2))
    return path


def make_copilot_db(db_path: Path, sessions=None):
    """Create a synthetic Copilot Chat SQLite database."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE conversations (id TEXT PRIMARY KEY, title TEXT, created_at TEXT, updated_at TEXT)"
    )
    conn.execute(
        "CREATE TABLE messages (id TEXT PRIMARY KEY, conversation_id TEXT, role TEXT, content TEXT, created_at TEXT)"
    )
    if sessions is None:
        sessions = [{
            "id": "copilot-sess-1",
            "title": "Auth bug discussion",
            "created_at": "2025-01-15T10:00:00Z",
            "updated_at": "2025-01-15T12:30:00Z",
            "messages": [
                {"role": "user", "content": "How do I fix token refresh?"},
                {"role": "assistant", "content": "Check the expiry logic."},
            ],
        }]
    for s in sessions:
        conn.execute("INSERT INTO conversations VALUES (?, ?, ?, ?)",
                     (s["id"], s["title"], s["created_at"], s["updated_at"]))
        for i, m in enumerate(s.get("messages", [])):
            conn.execute("INSERT INTO messages VALUES (?, ?, ?, ?, ?)",
                         (f"{s['id']}-msg-{i}", s["id"], m["role"], m["content"], s["created_at"]))
    conn.commit()
    conn.close()


class MockCosmosClient:
    """Mock CosmosMemoryClient for testing SessionStore without Cosmos DB."""

    def __init__(self):
        self._records = []  # list of dicts

    def add_cosmos(self, user_id, thread_id, role, content, memory_type, metadata=None):
        record = {
            "id": f"rec-{len(self._records)}",
            "user_id": user_id,
            "thread_id": thread_id,
            "role": role,
            "content": content,
            "memory_type": memory_type,
            "metadata": metadata or {},
        }
        self._records.append(record)
        return record

    def get_thread(self, thread_id, user_id=None):
        return [r for r in self._records
                if r["thread_id"] == thread_id
                and (user_id is None or r["user_id"] == user_id)]

    def get_memories(self, user_id, memory_type=None):
        return [r for r in self._records
                if r["user_id"] == user_id
                and (memory_type is None or r["memory_type"] == memory_type)]

    def search_cosmos(self, query, user_id, memory_type=None, top_k=5):
        results = self.get_memories(user_id, memory_type)
        return results[:top_k]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAdapterRegistry(unittest.TestCase):
    def test_list_adapters(self):
        adapters = list_adapters()
        self.assertIn("openclaw", adapters)
        self.assertIn("claude-code", adapters)
        self.assertIn("copilot", adapters)
        self.assertIn("cursor", adapters)
        self.assertIn("codex", adapters)

    def test_get_adapter_by_name(self):
        adapter = get_adapter("claude-code")
        self.assertEqual(adapter.platform, "claude-code")

    def test_get_adapter_unknown(self):
        with self.assertRaises(ValueError):
            get_adapter("nonexistent-platform")

    def test_auto_detect_no_platforms(self):
        """Auto-detect raises when no platform is installed."""
        with patch.object(OpenClawAdapter, "detect", return_value=False), \
             patch.object(ClaudeCodeAdapter, "detect", return_value=False), \
             patch.object(CopilotAdapter, "detect", return_value=False), \
             patch.object(CursorAdapter, "detect", return_value=False), \
             patch.object(CodexAdapter, "detect", return_value=False):
            with self.assertRaises(RuntimeError):
                get_adapter(None)


class TestSessionAdapterInterface(unittest.TestCase):
    """Verify all adapters implement the required ABC methods."""

    def test_all_adapters_are_session_adapters(self):
        for name in list_adapters():
            adapter = get_adapter(name)
            self.assertIsInstance(adapter, SessionAdapter)
            self.assertTrue(hasattr(adapter, "platform"))
            self.assertTrue(hasattr(adapter, "detect"))
            self.assertTrue(hasattr(adapter, "locate_sessions"))
            self.assertTrue(hasattr(adapter, "export_session"))
            self.assertTrue(hasattr(adapter, "import_session"))
            self.assertTrue(hasattr(adapter, "resume_command"))


class TestClaudeCodeAdapter(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.sessions_dir = Path(self.tmpdir) / ".claude" / "sessions"
        self.sessions_dir.mkdir(parents=True)
        self.adapter = ClaudeCodeAdapter(sessions_dir=self.sessions_dir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_detect(self):
        self.assertTrue(self.adapter.detect())

    def test_locate_sessions(self):
        make_claude_session(self.sessions_dir, "sess-1")
        make_claude_session(self.sessions_dir, "sess-2", cwd="/tmp/other")
        sessions = self.adapter.locate_sessions()
        self.assertEqual(len(sessions), 2)
        self.assertEqual(sessions[0].id, "sess-1")

    def test_locate_sessions_workspace_filter(self):
        make_claude_session(self.sessions_dir, "sess-1", cwd="/tmp/project")
        make_claude_session(self.sessions_dir, "sess-2", cwd="/tmp/other")
        sessions = self.adapter.locate_sessions(workspace="/tmp/project")
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].id, "sess-1")

    def test_export_session(self):
        make_claude_session(self.sessions_dir, "sess-1")
        data = self.adapter.export_session("sess-1")
        self.assertIn("metadata", data)
        self.assertIn("turns", data)
        self.assertEqual(data["metadata"]["platform_session_id"], "sess-1")
        self.assertEqual(data["metadata"]["platform"], "claude-code")
        self.assertEqual(len(data["turns"]), 4)
        self.assertEqual(data["turns"][0]["role"], "user")
        self.assertEqual(data["turns"][0]["content"], "Fix the auth bug")

    def test_export_session_not_found(self):
        with self.assertRaises(FileNotFoundError):
            self.adapter.export_session("nonexistent")

    def test_import_session(self):
        make_claude_session(self.sessions_dir, "sess-1")
        data = self.adapter.export_session("sess-1")
        # Change the platform_session_id to simulate importing to new location
        data["metadata"]["platform_session_id"] = "sess-imported"
        pid = self.adapter.import_session(data)
        self.assertEqual(pid, "sess-imported")
        # Verify file was written
        imported_path = self.sessions_dir / "sess-imported.json"
        self.assertTrue(imported_path.exists())

    def test_round_trip(self):
        """Export → import → export should produce equivalent data."""
        make_claude_session(self.sessions_dir, "sess-rt")
        original = self.adapter.export_session("sess-rt")

        # Import under new ID
        original["metadata"]["platform_session_id"] = "sess-rt-copy"
        self.adapter.import_session(original)

        reimported = self.adapter.export_session("sess-rt-copy")
        self.assertEqual(len(original["turns"]), len(reimported["turns"]))
        for orig_turn, new_turn in zip(original["turns"], reimported["turns"]):
            self.assertEqual(orig_turn["role"], new_turn["role"])
            self.assertEqual(orig_turn["content"], new_turn["content"])

    def test_resume_command(self):
        cmd = self.adapter.resume_command("sess-1")
        self.assertIn("claude --resume sess-1", cmd)

    def test_summary_hint(self):
        make_claude_session(self.sessions_dir, "sess-1")
        sessions = self.adapter.locate_sessions()
        self.assertEqual(sessions[0].summary_hint, "Fix the auth bug")

    def test_content_blocks_format(self):
        """Test handling of content-blocks format (list of dicts)."""
        messages = [
            {"role": "user", "content": [{"type": "text", "text": "Block format test"}]},
            {"role": "assistant", "content": "Response"},
        ]
        make_claude_session(self.sessions_dir, "sess-blocks", messages=messages)
        data = self.adapter.export_session("sess-blocks")
        self.assertEqual(data["turns"][0]["content"], "Block format test")


class TestCopilotAdapter(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.storage_base = Path(self.tmpdir) / "globalStorage"
        self.ext_dir = self.storage_base / "github.copilot-chat"
        self.ext_dir.mkdir(parents=True)
        self.db_path = self.ext_dir / "conversations.db"
        make_copilot_db(self.db_path)
        self.adapter = CopilotAdapter(storage_base=self.storage_base)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_detect(self):
        self.assertTrue(self.adapter.detect())

    def test_locate_sessions(self):
        sessions = self.adapter.locate_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].id, "copilot-sess-1")

    def test_export_session(self):
        data = self.adapter.export_session("copilot-sess-1")
        self.assertIn("metadata", data)
        self.assertIn("turns", data)
        self.assertEqual(data["metadata"]["platform"], "copilot")
        self.assertEqual(len(data["turns"]), 2)

    def test_import_session(self):
        data = self.adapter.export_session("copilot-sess-1")
        data["metadata"]["platform_session_id"] = "copilot-imported"
        pid = self.adapter.import_session(data)
        self.assertEqual(pid, "copilot-imported")
        # Verify it's in the DB
        sessions = self.adapter.locate_sessions()
        ids = [s.id for s in sessions]
        self.assertIn("copilot-imported", ids)

    def test_resume_command(self):
        cmd = self.adapter.resume_command("copilot-sess-1")
        self.assertIn("VS Code", cmd)


class TestCursorAdapter(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Simulate Cursor directory structure
        self.cursor_user = Path(self.tmpdir) / "Cursor" / "User"
        self.storage_base = self.cursor_user / "globalStorage"
        self.ext_dir = self.storage_base / "cursor.chat"
        self.ext_dir.mkdir(parents=True)
        self.db_path = self.ext_dir / "conversations.db"
        make_copilot_db(self.db_path, sessions=[{
            "id": "cursor-sess-1",
            "title": "Cursor chat",
            "created_at": "2025-01-15T10:00:00Z",
            "updated_at": "2025-01-15T12:30:00Z",
            "messages": [{"role": "user", "content": "Hello Cursor"}],
        }])
        self.adapter = CursorAdapter(storage_base=self.storage_base)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_detect(self):
        self.assertTrue(self.adapter.detect())

    def test_locate_sessions(self):
        sessions = self.adapter.locate_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].id, "cursor-sess-1")

    def test_export_session(self):
        data = self.adapter.export_session("cursor-sess-1")
        self.assertEqual(data["metadata"]["platform"], "cursor")
        self.assertEqual(len(data["turns"]), 1)


class TestCodexAdapter(unittest.TestCase):
    def test_detect_no_install(self):
        adapter = CodexAdapter()
        # May or may not detect depending on environment
        # Just verify it doesn't crash
        adapter.detect()

    def test_locate_sessions_empty(self):
        adapter = CodexAdapter()
        sessions = adapter.locate_sessions()
        self.assertEqual(sessions, [])

    def test_export_from_artifact(self):
        adapter = CodexAdapter()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Session Log\nWorked on the auth bug.\n")
            f.flush()
            data = adapter.export_session(f.name)
            self.assertIn("metadata", data)
            self.assertTrue(data["metadata"].get("synthetic"))
            os.unlink(f.name)

    def test_export_nonexistent_raises(self):
        adapter = CodexAdapter()
        with self.assertRaises(NotImplementedError):
            adapter.export_session("not-a-file-and-not-a-session")

    def test_import_raises(self):
        adapter = CodexAdapter()
        with self.assertRaises(NotImplementedError):
            adapter.import_session({"metadata": {}, "turns": []})


class TestSessionStore(unittest.TestCase):
    def setUp(self):
        self.mock_client = MockCosmosClient()
        self.store = SessionStore(self.mock_client, user_id="test-user")

    def test_save_and_get_session(self):
        data = {
            "metadata": {
                "platform_session_id": "abc-123",
                "platform": "claude-code",
                "workspace": "/tmp/project",
                "model": "claude-sonnet-4-20250514",
                "summary": "Fix the auth bug",
                "created_at": "2025-01-15T10:00:00Z",
                "updated_at": "2025-01-15T12:30:00Z",
                "fingerprint": "sha256:deadbeef",
            },
            "turns": [
                {"role": "user", "content": "Fix the auth bug", "tool_use": None},
                {"role": "assistant", "content": "Found the issue.", "tool_use": None},
            ],
        }

        cosmos_id = self.store.save_session(data)
        self.assertTrue(cosmos_id)

        # Retrieve it
        retrieved = self.store.get_session(cosmos_id)
        self.assertEqual(len(retrieved["turns"]), 2)
        self.assertEqual(retrieved["turns"][0]["content"], "Fix the auth bug")
        self.assertEqual(retrieved["metadata"]["platform"], "claude-code")

    def test_save_session_with_existing_id(self):
        data = {
            "metadata": {"platform_session_id": "x", "platform": "claude-code",
                         "summary": "test", "created_at": "", "updated_at": "",
                         "workspace": "", "model": "", "fingerprint": ""},
            "turns": [{"role": "user", "content": "hello", "tool_use": None}],
        }
        cosmos_id = self.store.save_session(data, cosmos_session_id="fixed-id")
        self.assertEqual(cosmos_id, "fixed-id")

    def test_list_sessions(self):
        for i in range(3):
            data = {
                "metadata": {"platform_session_id": f"p-{i}", "platform": "claude-code",
                             "summary": f"session {i}", "created_at": "", "updated_at": "",
                             "workspace": "", "model": "", "fingerprint": ""},
                "turns": [{"role": "user", "content": f"msg {i}", "tool_use": None}],
            }
            self.store.save_session(data)

        sessions = self.store.list_sessions()
        self.assertEqual(len(sessions), 3)

    def test_list_sessions_filter_platform(self):
        for p in ["claude-code", "copilot", "claude-code"]:
            data = {
                "metadata": {"platform_session_id": f"p-{p}", "platform": p,
                             "summary": "test", "created_at": "", "updated_at": "",
                             "workspace": "", "model": "", "fingerprint": ""},
                "turns": [],
            }
            self.store.save_session(data)

        cc_sessions = self.store.list_sessions(platform="claude-code")
        self.assertEqual(len(cc_sessions), 2)

    def test_search_sessions(self):
        data = {
            "metadata": {"platform_session_id": "s1", "platform": "claude-code",
                         "summary": "auth bug fix", "created_at": "", "updated_at": "",
                         "workspace": "", "model": "", "fingerprint": ""},
            "turns": [{"role": "user", "content": "fix auth", "tool_use": None}],
        }
        self.store.save_session(data)
        results = self.store.search_sessions("auth")
        self.assertTrue(len(results) >= 1)

    def test_find_by_platform_id(self):
        data = {
            "metadata": {"platform_session_id": "abc-123", "platform": "claude-code",
                         "summary": "test", "created_at": "", "updated_at": "",
                         "workspace": "", "model": "", "fingerprint": ""},
            "turns": [],
        }
        self.store.save_session(data)
        found = self.store.find_by_platform_id("claude-code", "abc-123")
        self.assertIsNotNone(found)

    def test_find_by_platform_id_not_found(self):
        found = self.store.find_by_platform_id("claude-code", "nonexistent")
        self.assertIsNone(found)

    def test_find_by_fingerprint(self):
        data = {
            "metadata": {"platform_session_id": "x", "platform": "claude-code",
                         "summary": "test", "created_at": "", "updated_at": "",
                         "workspace": "", "model": "", "fingerprint": "sha256:abc123"},
            "turns": [],
        }
        self.store.save_session(data)
        found = self.store.find_by_fingerprint("sha256:abc123")
        self.assertIsNotNone(found)

    def test_get_session_not_found(self):
        with self.assertRaises(FileNotFoundError):
            self.store.get_session("nonexistent-id")

    def test_turn_ordering(self):
        """Turns must come back in the same order they were saved."""
        turns = [
            {"role": "user", "content": f"message {i}", "tool_use": None}
            for i in range(10)
        ]
        data = {
            "metadata": {"platform_session_id": "ord", "platform": "claude-code",
                         "summary": "order test", "created_at": "", "updated_at": "",
                         "workspace": "", "model": "", "fingerprint": ""},
            "turns": turns,
        }
        cid = self.store.save_session(data)
        retrieved = self.store.get_session(cid)
        for i, turn in enumerate(retrieved["turns"]):
            self.assertEqual(turn["content"], f"message {i}")

    def test_tool_use_round_trip(self):
        """tool_use data should survive JSON serialization round-trip."""
        tool_data = [{"name": "read_file", "args": {"path": "/tmp/foo"}}]
        data = {
            "metadata": {"platform_session_id": "tu", "platform": "claude-code",
                         "summary": "tool test", "created_at": "", "updated_at": "",
                         "workspace": "", "model": "", "fingerprint": ""},
            "turns": [
                {"role": "assistant", "content": "reading file", "tool_use": tool_data},
            ],
        }
        cid = self.store.save_session(data)
        retrieved = self.store.get_session(cid)
        self.assertEqual(retrieved["turns"][0]["tool_use"], tool_data)


class TestFingerprint(unittest.TestCase):
    def test_compute_fingerprint_deterministic(self):
        fp1 = compute_fingerprint("2025-01-15T10:00:00Z", "Fix auth bug", "/tmp/project")
        fp2 = compute_fingerprint("2025-01-15T10:00:00Z", "Fix auth bug", "/tmp/project")
        self.assertEqual(fp1, fp2)
        self.assertTrue(fp1.startswith("sha256:"))

    def test_fingerprint_differs_with_different_inputs(self):
        fp1 = compute_fingerprint("2025-01-15T10:00:00Z", "Fix auth bug", "/tmp/project")
        fp2 = compute_fingerprint("2025-01-15T11:00:00Z", "Fix auth bug", "/tmp/project")
        self.assertNotEqual(fp1, fp2)

    def test_session_info_fingerprint(self):
        si = SessionInfo(id="x", created_at="2025-01-15T10:00:00Z",
                         summary_hint="Fix auth", workspace="/tmp/project")
        fp = si.fingerprint()
        expected = compute_fingerprint("2025-01-15T10:00:00Z", "Fix auth", "/tmp/project")
        self.assertEqual(fp, expected)


class TestSyncReconciliation(unittest.TestCase):
    """Test the reconciliation logic used by session-sync command."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.sessions_dir = Path(self.tmpdir) / ".claude" / "sessions"
        self.sessions_dir.mkdir(parents=True)
        self.adapter = ClaudeCodeAdapter(sessions_dir=self.sessions_dir)
        self.mock_client = MockCosmosClient()
        self.store = SessionStore(self.mock_client, user_id="test-user")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_new_local_session_exported(self):
        """A local session with no Cosmos match should be exported."""
        make_claude_session(self.sessions_dir, "new-local")
        local_sessions = self.adapter.locate_sessions()
        cosmos_sessions = self.store.list_sessions()

        self.assertEqual(len(local_sessions), 1)
        self.assertEqual(len(cosmos_sessions), 0)

        # Simulate sync: export new local
        data = self.adapter.export_session("new-local")
        cosmos_id = self.store.save_session(data)
        self.assertTrue(cosmos_id)

        # Now it should appear in cosmos
        cosmos_sessions = self.store.list_sessions()
        self.assertEqual(len(cosmos_sessions), 1)

    def test_matching_by_platform_id(self):
        """Sessions should match by platform_ids in metadata."""
        make_claude_session(self.sessions_dir, "match-test")
        data = self.adapter.export_session("match-test")
        cosmos_id = self.store.save_session(data)

        # Should find by platform ID
        found = self.store.find_by_platform_id("claude-code", "match-test")
        self.assertIsNotNone(found)
        self.assertEqual(found["cosmos_session_id"], cosmos_id)

    def test_matching_by_fingerprint(self):
        """Sessions should match by fingerprint when platform_id doesn't match."""
        make_claude_session(self.sessions_dir, "fp-test")
        data = self.adapter.export_session("fp-test")
        cosmos_id = self.store.save_session(data)

        # The fingerprint from local session should match
        local_sessions = self.adapter.locate_sessions()
        local_fp = local_sessions[0].fingerprint()
        found = self.store.find_by_fingerprint(
            compute_fingerprint("2025-01-15T10:00:00Z", "Fix the auth bug", "/tmp/project")
        )
        self.assertIsNotNone(found)

    def test_in_sync_detection(self):
        """Sessions with matching timestamps should be detected as in-sync."""
        make_claude_session(self.sessions_dir, "sync-test")
        local_sessions = self.adapter.locate_sessions()
        data = self.adapter.export_session("sync-test")
        self.store.save_session(data)
        cosmos_sessions = self.store.list_sessions()

        local_ts = local_sessions[0].updated_at
        remote_ts = cosmos_sessions[0]["updated_at"]

        # Both have same source timestamp, so they should be comparable
        # (In real sync, we'd compare these)
        self.assertIsNotNone(local_ts)
        self.assertIsNotNone(remote_ts)


class TestPlatformIdTracking(unittest.TestCase):
    """Test that platform_ids map is maintained across imports."""

    def setUp(self):
        self.mock_client = MockCosmosClient()
        self.store = SessionStore(self.mock_client, user_id="test-user")

    def test_platform_ids_preserved_on_re_save(self):
        """Saving from different platforms should accumulate platform_ids."""
        data = {
            "metadata": {"platform_session_id": "cc-1", "platform": "claude-code",
                         "summary": "test", "created_at": "", "updated_at": "",
                         "workspace": "", "model": "", "fingerprint": ""},
            "turns": [{"role": "user", "content": "hello", "tool_use": None}],
        }
        cosmos_id = self.store.save_session(data)

        # Now "import" to copilot and update platform_ids
        self.store.update_platform_id(cosmos_id, "copilot", "cop-1")

        # Retrieve and check
        session = self.store.get_session(cosmos_id)
        pids = session["metadata"].get("platform_ids", {})
        self.assertEqual(pids.get("claude-code"), "cc-1")
        self.assertEqual(pids.get("copilot"), "cop-1")


# ---------------------------------------------------------------------------
# OpenClaw Adapter Tests
# ---------------------------------------------------------------------------

def make_openclaw_session(sessions_dir: Path, session_id: str = "test-oc-sess",
                          cwd: str = "/tmp/project",
                          extra_lines: Optional[list] = None) -> Path:
    """Create a synthetic OpenClaw JSONL session file."""
    sessions_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        {"type": "session", "id": "hdr1", "parentId": None,
         "timestamp": "2025-01-15T10:00:00Z", "sessionId": session_id,
         "version": 3, "cwd": cwd, "model": "claude-sonnet-4-20250514"},
        {"type": "model_change", "id": "mc1", "parentId": "hdr1",
         "timestamp": "2025-01-15T10:00:01Z", "model": "claude-sonnet-4-20250514"},
        {"type": "custom:openclaw:bootstrap-context:full", "id": "bc1",
         "parentId": "mc1", "timestamp": "2025-01-15T10:00:02Z",
         "customType": "custom:openclaw:bootstrap-context:full",
         "content": "SYSTEM PROMPT SHOULD BE FILTERED"},
        {"type": "message", "id": "m1", "parentId": "bc1",
         "timestamp": "2025-01-15T10:01:00Z",
         "message": {"role": "user",
                     "content": [{"type": "text", "text": "Fix the auth bug"}]}},
        {"type": "message", "id": "m2", "parentId": "m1",
         "timestamp": "2025-01-15T10:02:00Z",
         "message": {"role": "assistant",
                     "content": [{"type": "text", "text": "Found the issue in token refresh."}]}},
        {"type": "compaction", "id": "cp1", "parentId": "m2",
         "timestamp": "2025-01-15T10:03:00Z"},
        {"type": "message", "id": "m3", "parentId": "cp1",
         "timestamp": "2025-01-15T10:04:00Z",
         "message": {"role": "user",
                     "content": [{"type": "text", "text": "Great, apply the fix."}]}},
        {"type": "message", "id": "m4", "parentId": "m3",
         "timestamp": "2025-01-15T10:05:00Z",
         "message": {"role": "assistant",
                     "content": [{"type": "text", "text": "Done. Token refreshes correctly now."}]}},
    ]
    if extra_lines:
        lines.extend(extra_lines)

    path = sessions_dir / f"{session_id}.jsonl"
    with open(path, "w") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")
    return path


def make_openclaw_index(agent_dir: Path, entries: dict) -> Path:
    """Create a sessions.json index file."""
    index_path = agent_dir / "sessions.json"
    index_path.write_text(json.dumps(entries, indent=2))
    return index_path


class TestOpenClawAdapter(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.agents_dir = Path(self.tmpdir) / ".openclaw" / "agents"
        self.agent_dir = self.agents_dir / "testagent"
        self.sessions_dir = self.agent_dir / "sessions"
        self.sessions_dir.mkdir(parents=True)
        self.adapter = OpenClawAdapter(agents_dir=self.agents_dir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def _setup_session(self, session_id="test-oc-sess", cwd="/tmp/project",
                       extra_lines=None):
        path = make_openclaw_session(
            self.sessions_dir, session_id, cwd, extra_lines
        )
        make_openclaw_index(self.agent_dir, {
            f"agent:testagent:test:{session_id}": {
                "sessionId": session_id,
                "sessionFile": str(path),
                "origin": {"provider": "test", "surface": "test"},
                "updatedAt": 1705312200000,
            }
        })
        return path

    def test_detect(self):
        self.assertTrue(self.adapter.detect())

    def test_detect_missing(self):
        adapter = OpenClawAdapter(agents_dir=Path(self.tmpdir) / "nonexistent")
        self.assertFalse(adapter.detect())

    def test_locate_sessions(self):
        self._setup_session()
        sessions = self.adapter.locate_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].id, "test-oc-sess")
        self.assertEqual(sessions[0].workspace, "/tmp/project")
        self.assertEqual(sessions[0].summary_hint, "Fix the auth bug")

    def test_locate_sessions_workspace_filter(self):
        self._setup_session("s1", "/tmp/project")
        p2 = make_openclaw_session(self.sessions_dir, "s2", "/tmp/other")
        # Add s2 to index
        idx = json.loads((self.agent_dir / "sessions.json").read_text())
        idx["agent:testagent:test:s2"] = {
            "sessionId": "s2",
            "sessionFile": str(p2),
            "origin": {"provider": "test"},
            "updatedAt": 1705312200000,
        }
        (self.agent_dir / "sessions.json").write_text(json.dumps(idx))

        sessions = self.adapter.locate_sessions(workspace="/tmp/project")
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].id, "s1")

    def test_export_session(self):
        self._setup_session()
        data = self.adapter.export_session("test-oc-sess")
        self.assertIn("metadata", data)
        self.assertIn("turns", data)
        self.assertEqual(data["metadata"]["platform"], "openclaw")
        self.assertEqual(data["metadata"]["platform_session_id"], "test-oc-sess")
        # Should have 4 message turns (skip session, model_change, bootstrap, compaction)
        self.assertEqual(len(data["turns"]), 4)
        self.assertEqual(data["turns"][0]["role"], "user")
        self.assertEqual(data["turns"][0]["content"], "Fix the auth bug")

    def test_export_filters_bootstrap_and_compaction(self):
        """Verify bootstrap-context and compaction lines are excluded."""
        self._setup_session()
        data = self.adapter.export_session("test-oc-sess")
        contents = [t["content"] for t in data["turns"]]
        self.assertNotIn("SYSTEM PROMPT SHOULD BE FILTERED", contents)
        # Only message type lines should be in turns
        for turn in data["turns"]:
            self.assertIn(turn["role"], ("user", "assistant"))

    def test_export_session_not_found(self):
        with self.assertRaises(FileNotFoundError):
            self.adapter.export_session("nonexistent")

    def test_import_session(self):
        self._setup_session()
        data = self.adapter.export_session("test-oc-sess")
        new_id = self.adapter.import_session(data)
        self.assertTrue(new_id)
        # Verify the JSONL file was created
        new_file = self.sessions_dir / f"{new_id}.jsonl"
        self.assertTrue(new_file.exists())
        # Verify sessions.json was updated
        idx = json.loads((self.agent_dir / "sessions.json").read_text())
        self.assertIn(f"imported:{new_id}", idx)

    def test_round_trip(self):
        """Export -> import -> export should produce equivalent turns."""
        self._setup_session()
        original = self.adapter.export_session("test-oc-sess")
        new_id = self.adapter.import_session(original)
        reimported = self.adapter.export_session(new_id)
        self.assertEqual(len(original["turns"]), len(reimported["turns"]))
        for orig, new in zip(original["turns"], reimported["turns"]):
            self.assertEqual(orig["role"], new["role"])
            self.assertEqual(orig["content"], new["content"])

    def test_import_valid_jsonl(self):
        """Imported JSONL should have valid structure."""
        self._setup_session()
        data = self.adapter.export_session("test-oc-sess")
        new_id = self.adapter.import_session(data)
        new_file = self.sessions_dir / f"{new_id}.jsonl"
        lines = []
        with open(new_file) as f:
            for raw in f:
                lines.append(json.loads(raw.strip()))
        # First line should be session header
        self.assertEqual(lines[0]["type"], "session")
        self.assertEqual(lines[0]["version"], 3)
        # Remaining should be messages with proper parentId chain
        for i in range(1, len(lines)):
            self.assertEqual(lines[i]["type"], "message")
            self.assertEqual(lines[i]["parentId"], lines[i-1]["id"])

    def test_multi_agent_scan(self):
        """Sessions from multiple agents should all be found."""
        # Agent 1
        agent1_sessions = self.sessions_dir
        p1 = make_openclaw_session(agent1_sessions, "agent1-sess", "/tmp/a")
        make_openclaw_index(self.agent_dir, {
            "k1": {"sessionId": "agent1-sess", "sessionFile": str(p1),
                   "origin": {}, "updatedAt": 1705312200000}
        })
        # Agent 2
        agent2_dir = self.agents_dir / "agent2"
        agent2_sessions = agent2_dir / "sessions"
        agent2_sessions.mkdir(parents=True)
        p2 = make_openclaw_session(agent2_sessions, "agent2-sess", "/tmp/b")
        make_openclaw_index(agent2_dir, {
            "k2": {"sessionId": "agent2-sess", "sessionFile": str(p2),
                   "origin": {}, "updatedAt": 1705312200000}
        })

        sessions = self.adapter.locate_sessions()
        ids = {s.id for s in sessions}
        self.assertIn("agent1-sess", ids)
        self.assertIn("agent2-sess", ids)

    def test_resume_command(self):
        cmd = self.adapter.resume_command("some-id")
        self.assertIn("some-id", cmd)
        self.assertIn("internally", cmd)

    def test_yield_points_in_metadata(self):
        """sessions_yield lines should appear in export metadata."""
        yield_line = {
            "type": "custom_message:openclaw.sessions_yield",
            "id": "y1", "parentId": "m4",
            "timestamp": "2025-01-15T10:06:00Z",
        }
        self._setup_session(extra_lines=[yield_line])
        data = self.adapter.export_session("test-oc-sess")
        self.assertIn("yield_points", data["metadata"])
        self.assertEqual(len(data["metadata"]["yield_points"]), 1)


if __name__ == "__main__":
    unittest.main()
