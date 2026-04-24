"""Claude Code session adapter.

FRAGILITY: LOW — Claude Code stores sessions as plain JSON files in a
well-known location. The file format is straightforward and the CLI has
native --resume support. This is the most reliable adapter.

What could break:
- Claude Code changes its session directory from ~/.claude/sessions/
- The JSON schema changes (fields renamed, nested differently)
- Session IDs stop being the filename stem
"""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import SessionAdapter, SessionInfo, compute_fingerprint


def _extract_text(content: Any) -> str:
    """Extract plain text from Claude message content (str or content-blocks)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                return block.get("text", "")
            if isinstance(block, str):
                return block
    return ""


class ClaudeCodeAdapter(SessionAdapter):
    platform = "claude-code"

    def __init__(self, sessions_dir: Optional[Path] = None):
        self._sessions_dir = sessions_dir or Path.home() / ".claude" / "sessions"

    def detect(self) -> bool:
        if self._sessions_dir.parent.is_dir():
            return True
        return shutil.which("claude") is not None

    def locate_sessions(self, workspace: Optional[str] = None) -> List[SessionInfo]:
        self._require_detected()
        sessions: List[SessionInfo] = []
        if not self._sessions_dir.is_dir():
            return sessions

        for path in sorted(self._sessions_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            cwd = data.get("cwd", "")
            if workspace and cwd and not cwd.startswith(workspace):
                continue

            summary_hint = ""
            for msg in data.get("messages", []):
                if msg.get("role") == "user":
                    summary_hint = _extract_text(msg.get("content", ""))[:200]
                    break

            sessions.append(SessionInfo(
                id=data.get("id", path.stem),
                created_at=data.get("created_at"),
                updated_at=data.get("updated_at"),
                workspace=cwd,
                summary_hint=summary_hint,
                path=str(path),
            ))

        return sessions

    def export_session(self, session_id: str) -> Dict[str, Any]:
        self._require_detected()
        path = self._sessions_dir / f"{session_id}.json"
        if not path.exists():
            path = self._find_session_file(session_id)
            if path is None:
                raise FileNotFoundError(
                    f"Claude Code session '{session_id}' not found in {self._sessions_dir}"
                )

        data = json.loads(path.read_text(encoding="utf-8"))

        # Build turns list
        turns = []
        first_user_msg = ""
        for msg in data.get("messages", []):
            role = msg.get("role", "")
            content_raw = msg.get("content", "")
            content_text = _extract_text(content_raw)
            tool_use = msg.get("tool_use") or msg.get("tool_calls")

            if role == "user" and not first_user_msg:
                first_user_msg = content_text[:500]

            turns.append({
                "role": role,
                "content": content_text,
                "tool_use": tool_use,
            })

        created_at = data.get("created_at", "")
        workspace = data.get("cwd", "")
        fp = compute_fingerprint(created_at, first_user_msg, workspace)

        return {
            "metadata": {
                "platform_session_id": data.get("id", session_id),
                "platform": self.platform,
                "workspace": workspace,
                "model": data.get("model", ""),
                "summary": first_user_msg,
                "created_at": created_at,
                "updated_at": data.get("updated_at", ""),
                "fingerprint": fp,
            },
            "turns": turns,
            "_raw": data,  # Full original JSON for lossless round-trip
        }

    def import_session(self, data: Dict[str, Any]) -> str:
        self._require_detected()
        self._sessions_dir.mkdir(parents=True, exist_ok=True)

        meta = data.get("metadata", {})
        session_id = meta.get("platform_session_id") or str(uuid.uuid4())

        # Prefer raw original if available for lossless round-trip
        if "_raw" in data and isinstance(data["_raw"], dict):
            session_data = data["_raw"].copy()
        else:
            # Reconstruct Claude Code JSON from portable format
            messages = []
            for turn in data.get("turns", []):
                msg: Dict[str, Any] = {
                    "role": turn["role"],
                    "content": turn["content"],
                }
                if turn.get("tool_use"):
                    msg["tool_use"] = turn["tool_use"]
                messages.append(msg)

            session_data = {
                "id": session_id,
                "cwd": meta.get("workspace", ""),
                "messages": messages,
                "model": meta.get("model", "claude-sonnet-4-20250514"),
                "created_at": meta.get("created_at", ""),
                "updated_at": meta.get("updated_at", ""),
            }

        session_data["id"] = session_id

        path = self._sessions_dir / f"{session_id}.json"
        path.write_text(json.dumps(session_data, indent=2), encoding="utf-8")
        return session_id

    def resume_command(self, session_id: str) -> str:
        return f"claude --resume {session_id}"

    def _find_session_file(self, session_id: str) -> Optional[Path]:
        """Search session files by their internal 'id' field."""
        if not self._sessions_dir.is_dir():
            return None
        for path in self._sessions_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("id") == session_id:
                    return path
            except (json.JSONDecodeError, OSError):
                continue
        return None
