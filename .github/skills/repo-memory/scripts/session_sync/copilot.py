"""GitHub Copilot Chat session adapter.

FRAGILITY: HIGH — This adapter reverse-engineers Copilot Chat's local storage.
There is NO official API. The SQLite schema is inferred from observation and
may change with any VS Code or Copilot Chat extension update.

What could break:
- Copilot Chat extension changes its globalStorage path
- SQLite database schema changes (table names, column names, data format)
- Copilot Chat moves to a different storage backend (IndexedDB, LevelDB, etc.)
- Conversation data format inside the DB changes
- Extension ID changes from "github.copilot-chat"

Schema assumptions (as of early 2025):
- Database file: conversations.db or chat.db in the globalStorage directory
- Table 'conversations': columns (id TEXT, title TEXT, created_at TEXT, updated_at TEXT)
- Table 'messages': columns (id TEXT, conversation_id TEXT, role TEXT, content TEXT, created_at TEXT)
- All timestamps are ISO-8601 strings
"""

from __future__ import annotations

import platform
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import SessionAdapter, SessionInfo, compute_fingerprint

_DB_CANDIDATES = ["conversations.db", "chat.db", "copilot-chat.db"]
_EXTENSION_DIRS = ["github.copilot-chat"]


def _get_global_storage_base() -> Path:
    system = platform.system()
    if system == "Linux":
        return Path.home() / ".config" / "Code" / "User" / "globalStorage"
    elif system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Code" / "User" / "globalStorage"
    elif system == "Windows":
        return Path.home() / "AppData" / "Roaming" / "Code" / "User" / "globalStorage"
    return Path.home() / ".config" / "Code" / "User" / "globalStorage"


def _find_copilot_db(base: Path) -> Optional[Path]:
    for ext_dir in _EXTENSION_DIRS:
        ext_path = base / ext_dir
        if not ext_path.is_dir():
            continue
        for db_name in _DB_CANDIDATES:
            db_path = ext_path / db_name
            if db_path.is_file():
                return db_path
        for db_path in ext_path.glob("*.db"):
            return db_path
    return None


class CopilotAdapter(SessionAdapter):
    platform = "copilot"

    def __init__(self, storage_base: Optional[Path] = None):
        self._storage_base = storage_base or _get_global_storage_base()

    def detect(self) -> bool:
        for ext_dir in _EXTENSION_DIRS:
            if (self._storage_base / ext_dir).is_dir():
                return True
        return False

    def _get_db(self) -> Path:
        db = _find_copilot_db(self._storage_base)
        if db is None:
            raise FileNotFoundError(
                f"Copilot Chat database not found in {self._storage_base}. "
                f"Searched: {_EXTENSION_DIRS}, db candidates: {_DB_CANDIDATES}"
            )
        return db

    def locate_sessions(self, workspace: Optional[str] = None) -> List[SessionInfo]:
        self._require_detected()
        db_path = self._get_db()
        sessions: List[SessionInfo] = []

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            # ASSUMPTION: table 'conversations' with these columns
            cursor = conn.execute(
                "SELECT id, title, created_at, updated_at FROM conversations ORDER BY updated_at DESC"
            )
            for row in cursor:
                sessions.append(SessionInfo(
                    id=row["id"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    workspace=None,
                    summary_hint=row["title"] or "",
                    path=str(db_path),
                ))
        except sqlite3.OperationalError as e:
            raise RuntimeError(
                f"Failed to query Copilot Chat DB. Schema may have changed. "
                f"Expected table 'conversations' with (id, title, created_at, updated_at). Error: {e}"
            )
        finally:
            conn.close()

        return sessions

    def export_session(self, session_id: str) -> Dict[str, Any]:
        self._require_detected()
        db_path = self._get_db()
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        try:
            # ASSUMPTION: 'conversations' table schema
            row = conn.execute(
                "SELECT id, title, created_at, updated_at FROM conversations WHERE id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                raise FileNotFoundError(f"Copilot session '{session_id}' not found in DB")

            # ASSUMPTION: 'messages' table with conversation_id foreign key
            msgs_cursor = conn.execute(
                "SELECT role, content, created_at FROM messages "
                "WHERE conversation_id = ? ORDER BY created_at ASC",
                (session_id,),
            )
            messages = list(msgs_cursor)
        except sqlite3.OperationalError as e:
            raise RuntimeError(f"Failed to export Copilot session. DB schema may have changed. Error: {e}")
        finally:
            conn.close()

        turns = [
            {"role": m["role"], "content": m["content"] or "", "tool_use": None}
            for m in messages
        ]

        first_user_msg = ""
        for t in turns:
            if t["role"] in ("user", "human"):
                first_user_msg = t["content"][:500]
                break

        summary = row["title"] or first_user_msg
        created_at = row["created_at"] or ""
        fp = compute_fingerprint(created_at, first_user_msg, "")

        return {
            "metadata": {
                "platform_session_id": row["id"],
                "platform": self.platform,
                "workspace": "",
                "model": "",
                "summary": summary,
                "created_at": created_at,
                "updated_at": row["updated_at"] or "",
                "fingerprint": fp,
                "title": row["title"] or "",
            },
            "turns": turns,
        }

    def import_session(self, data: Dict[str, Any]) -> str:
        self._require_detected()
        db_path = self._get_db()
        meta = data.get("metadata", {})
        session_id = meta.get("platform_session_id") or str(uuid.uuid4())

        conn = sqlite3.connect(str(db_path))
        try:
            # ASSUMPTION: these table schemas exist and accept INSERTs
            conn.execute(
                "INSERT OR REPLACE INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (session_id, meta.get("title", meta.get("summary", "")),
                 meta.get("created_at", ""), meta.get("updated_at", "")),
            )
            for turn in data.get("turns", []):
                msg_id = str(uuid.uuid4())
                conn.execute(
                    "INSERT INTO messages (id, conversation_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
                    (msg_id, session_id, turn.get("role", ""), turn.get("content", ""), ""),
                )
            conn.commit()
        except sqlite3.OperationalError as e:
            conn.rollback()
            raise RuntimeError(f"Failed to import into Copilot Chat DB. Schema may have changed. Error: {e}")
        finally:
            conn.close()

        return session_id

    def resume_command(self, session_id: str) -> str:
        return (
            f"Open VS Code and navigate to the Copilot Chat panel. "
            f"The imported session '{session_id}' should appear in chat history. "
            f"There is no CLI command to directly resume a Copilot Chat session."
        )
