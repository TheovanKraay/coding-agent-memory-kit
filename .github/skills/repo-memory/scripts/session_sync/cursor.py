"""Cursor session adapter.

FRAGILITY: HIGH — Cursor is a VS Code fork with its own globalStorage layout.
This adapter reverse-engineers its chat session storage, which uses SQLite
similar to (but not necessarily identical to) GitHub Copilot Chat.

What could break:
- Cursor changes its globalStorage directory structure
- Cursor switches from SQLite to LevelDB or another backend
- Table names or column schemas diverge from assumptions
- Cursor's extension ID or chat storage extension changes
- Cursor merges, renames, or restructures the chat feature entirely

Schema assumptions (as of early 2025):
- Storage base: ~/.config/Cursor/User/globalStorage/ (Linux), ~/Library/Application Support/Cursor/User/globalStorage/ (macOS)
- Chat extension dir: one of "cursor.chat", "cursorai.cursor", or similar
- Database file: conversations.db, chat.db, or any .db in the extension dir
- Table 'conversations': columns (id TEXT, title TEXT, created_at TEXT, updated_at TEXT)
- Table 'messages': columns (id TEXT, conversation_id TEXT, role TEXT, content TEXT, created_at TEXT)
"""

from __future__ import annotations

import platform
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import SessionAdapter, SessionInfo, compute_fingerprint

_DB_CANDIDATES = ["conversations.db", "chat.db", "cursor-chat.db"]

# Cursor has changed extension IDs across versions — check all known ones
_EXTENSION_DIRS = ["cursor.chat", "cursorai.cursor", "cursor-chat"]


def _get_cursor_storage_base() -> Path:
    system = platform.system()
    if system == "Linux":
        return Path.home() / ".config" / "Cursor" / "User" / "globalStorage"
    elif system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Cursor" / "User" / "globalStorage"
    elif system == "Windows":
        return Path.home() / "AppData" / "Roaming" / "Cursor" / "User" / "globalStorage"
    return Path.home() / ".config" / "Cursor" / "User" / "globalStorage"


def _find_cursor_db(base: Path) -> Optional[Path]:
    """Search for Cursor's chat SQLite database.

    Cursor's internal structure is not documented, so we try multiple
    known extension directory names and database filenames.
    """
    # First try known extension dirs
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

    # Fallback: scan all subdirs in globalStorage for any matching .db
    if base.is_dir():
        for subdir in base.iterdir():
            if not subdir.is_dir():
                continue
            for db_name in _DB_CANDIDATES:
                db_path = subdir / db_name
                if db_path.is_file():
                    return db_path

    return None


class CursorAdapter(SessionAdapter):
    platform = "cursor"

    def __init__(self, storage_base: Optional[Path] = None):
        self._storage_base = storage_base or _get_cursor_storage_base()

    def detect(self) -> bool:
        """Check if Cursor's globalStorage directory exists."""
        # Check for the Cursor config directory (parent of globalStorage)
        cursor_config = self._storage_base.parent.parent  # .../Cursor/User/
        if cursor_config.is_dir():
            return True
        return False

    def _get_db(self) -> Path:
        db = _find_cursor_db(self._storage_base)
        if db is None:
            raise FileNotFoundError(
                f"Cursor chat database not found in {self._storage_base}. "
                f"Searched extension dirs: {_EXTENSION_DIRS}, "
                f"db candidates: {_DB_CANDIDATES}. "
                f"Cursor may use a different storage backend or directory layout."
            )
        return db

    def locate_sessions(self, workspace: Optional[str] = None) -> List[SessionInfo]:
        self._require_detected()
        db_path = self._get_db()
        sessions: List[SessionInfo] = []

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            # ASSUMPTION: same table schema as Copilot (Cursor is a VS Code fork)
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
                f"Failed to query Cursor chat DB. Schema may have changed. "
                f"Expected table 'conversations' with (id, title, created_at, updated_at). "
                f"Error: {e}"
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
            row = conn.execute(
                "SELECT id, title, created_at, updated_at FROM conversations WHERE id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                raise FileNotFoundError(f"Cursor session '{session_id}' not found in DB")

            msgs_cursor = conn.execute(
                "SELECT role, content, created_at FROM messages "
                "WHERE conversation_id = ? ORDER BY created_at ASC",
                (session_id,),
            )
            messages = list(msgs_cursor)
        except sqlite3.OperationalError as e:
            raise RuntimeError(f"Failed to export Cursor session. DB schema may have changed. Error: {e}")
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
            raise RuntimeError(f"Failed to import into Cursor chat DB. Schema may have changed. Error: {e}")
        finally:
            conn.close()

        return session_id

    def resume_command(self, session_id: str) -> str:
        return (
            f"Open Cursor and navigate to the AI chat panel. "
            f"The imported session '{session_id}' should appear in chat history. "
            f"There is no CLI command to directly resume a Cursor chat session."
        )
