"""OpenClaw session adapter.

FRAGILITY: LOW — OpenClaw stores sessions as JSONL files in a well-known
location with an index file. We control the format.

What could break:
- OpenClaw changes its agents directory from ~/.openclaw/agents/
- The JSONL schema changes (line types renamed, fields restructured)
- The sessions.json index format changes
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import SessionAdapter, SessionInfo, compute_fingerprint


def _extract_text(content: Any) -> str:
    """Extract plain text from OpenClaw message content blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts) if parts else ""
    return ""


# Line types to skip during export (not conversation content)
_SKIP_TYPES = frozenset({
    "session",
    "model_change",
    "thinking_level_change",
    "compaction",
})

# Custom types to skip (matched via type or customType)
_SKIP_CUSTOM_TYPES = frozenset({
    "custom:model-snapshot",
    "custom:openclaw:bootstrap-context:full",
})


class OpenClawAdapter(SessionAdapter):
    platform = "openclaw"

    def __init__(self, agents_dir: Optional[Path] = None):
        self._agents_dir = agents_dir or Path.home() / ".openclaw" / "agents"

    def detect(self) -> bool:
        return self._agents_dir.is_dir()

    def locate_sessions(self, workspace: Optional[str] = None) -> List[SessionInfo]:
        self._require_detected()
        sessions: List[SessionInfo] = []

        for agent_dir in self._iter_agent_dirs():
            agent_id = agent_dir.name
            sessions_dir = agent_dir / "sessions"
            index = self._read_sessions_index(agent_dir)

            for key, entry in index.items():
                session_file = Path(entry.get("sessionFile", ""))
                if not session_file.exists():
                    continue
                # Skip checkpoint files
                if ".checkpoint." in session_file.name:
                    continue

                # Parse first few lines to get header info
                header = self._read_session_header(session_file)
                if header is None:
                    continue

                cwd = header.get("cwd", "")
                if workspace and cwd and not cwd.startswith(workspace):
                    continue

                session_id = header.get("sessionId", session_file.stem)
                created_at = header.get("timestamp")
                updated_at = entry.get("updatedAt")
                if updated_at and isinstance(updated_at, (int, float)):
                    updated_at = datetime.fromtimestamp(
                        updated_at / 1000, tz=timezone.utc
                    ).isoformat()

                # Get first user message as summary hint
                summary_hint = self._get_first_user_message(session_file)

                sessions.append(SessionInfo(
                    id=session_id,
                    created_at=created_at,
                    updated_at=updated_at,
                    workspace=cwd,
                    summary_hint=summary_hint,
                    path=str(session_file),
                ))

        return sessions

    def export_session(self, session_id: str) -> Dict[str, Any]:
        self._require_detected()
        session_file = self._find_session_file(session_id)
        if session_file is None:
            raise FileNotFoundError(
                f"OpenClaw session '{session_id}' not found under {self._agents_dir}"
            )

        lines = self._read_jsonl(session_file)
        header = {}
        turns = []
        yield_points = []
        first_user_msg = ""
        turn_index = 0

        for line in lines:
            line_type = line.get("type", "")
            custom_type = line.get("customType", "")

            # Skip non-conversation lines
            if line_type in _SKIP_TYPES:
                if line_type == "session":
                    header = line
                continue
            if line_type in _SKIP_CUSTOM_TYPES or custom_type in _SKIP_CUSTOM_TYPES:
                continue

            # Track yield points as metadata
            if line_type == "custom_message:openclaw.sessions_yield":
                yield_points.append({
                    "timestamp": line.get("timestamp"),
                    "id": line.get("id"),
                })
                continue

            # Extract message turns
            if line_type == "message":
                msg = line.get("message", {})
                role = msg.get("role", "")
                content_raw = msg.get("content", "")
                content_text = _extract_text(content_raw)

                # Detect tool_use blocks
                tool_use = None
                if isinstance(content_raw, list):
                    tool_blocks = [
                        b for b in content_raw
                        if isinstance(b, dict) and b.get("type") in ("tool_use", "tool_result")
                    ]
                    if tool_blocks:
                        tool_use = tool_blocks

                if role == "user" and not first_user_msg:
                    # Skip tool_result-only messages for summary
                    if isinstance(content_raw, list):
                        has_text = any(
                            isinstance(b, dict) and b.get("type") == "text"
                            for b in content_raw
                        )
                        if has_text:
                            first_user_msg = content_text[:500]
                    else:
                        first_user_msg = content_text[:500]

                turns.append({
                    "role": role,
                    "content": content_text,
                    "tool_use": tool_use,
                    "timestamp": line.get("timestamp"),
                    "turn_index": turn_index,
                })
                turn_index += 1

        # Find agent_id and origin from sessions.json
        agent_id, origin = self._find_session_metadata(session_id)
        created_at = header.get("timestamp", "")
        workspace_path = header.get("cwd", "")
        fp = compute_fingerprint(created_at, first_user_msg, workspace_path)

        metadata: Dict[str, Any] = {
            "platform_session_id": session_id,
            "platform": self.platform,
            "workspace": workspace_path,
            "model": header.get("model", ""),
            "summary": first_user_msg,
            "created_at": created_at,
            "updated_at": turns[-1]["timestamp"] if turns else created_at,
            "fingerprint": fp,
        }
        if agent_id:
            metadata["agent_id"] = agent_id
        if origin:
            metadata["origin"] = origin
        if yield_points:
            metadata["yield_points"] = yield_points

        return {"metadata": metadata, "turns": turns}

    def import_session(self, data: Dict[str, Any]) -> str:
        self._require_detected()
        meta = data.get("metadata", {})
        turns = data.get("turns", [])

        session_id = str(uuid.uuid4())
        cwd = meta.get("workspace", "")
        model = meta.get("model", "")

        # Determine target agent directory
        agent_id = meta.get("agent_id")
        agent_dir = self._resolve_agent_dir(agent_id)
        sessions_dir = agent_dir / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)

        # Build JSONL lines
        jsonl_lines = []
        now = datetime.now(timezone.utc).isoformat()

        # Line 1: session header
        header_id = uuid.uuid4().hex[:8]
        jsonl_lines.append({
            "type": "session",
            "id": header_id,
            "parentId": None,
            "timestamp": meta.get("created_at", now),
            "sessionId": session_id,
            "version": 3,
            "cwd": cwd,
            "model": model,
        })

        # Message lines with proper id/parentId chain
        prev_id = header_id
        for turn in turns:
            line_id = uuid.uuid4().hex[:8]
            content = turn.get("content", "")
            role = turn.get("role", "user")

            # Reconstruct content blocks
            content_blocks = [{"type": "text", "text": content}] if content else []

            # Re-add tool_use blocks if present
            if turn.get("tool_use"):
                for block in turn["tool_use"]:
                    if isinstance(block, dict):
                        content_blocks.append(block)

            jsonl_lines.append({
                "type": "message",
                "id": line_id,
                "parentId": prev_id,
                "timestamp": turn.get("timestamp", now),
                "message": {
                    "role": role,
                    "content": content_blocks,
                },
            })
            prev_id = line_id

        # Write JSONL file
        session_file = sessions_dir / f"{session_id}.jsonl"
        with open(session_file, "w", encoding="utf-8") as f:
            for line in jsonl_lines:
                f.write(json.dumps(line, separators=(",", ":")) + "\n")

        # Update sessions.json index
        self._update_sessions_index(agent_dir, session_id, str(session_file), meta)

        return session_id

    def resume_command(self, session_id: str) -> str:
        return (
            f"OpenClaw manages session resume internally. "
            f"Session '{session_id}' will appear in the agent's session list."
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _iter_agent_dirs(self) -> List[Path]:
        """List all agent directories."""
        if not self._agents_dir.is_dir():
            return []
        return [d for d in sorted(self._agents_dir.iterdir()) if d.is_dir()]

    def _read_sessions_index(self, agent_dir: Path) -> Dict[str, Any]:
        """Read sessions.json for an agent."""
        index_path = agent_dir / "sessions.json"
        if not index_path.exists():
            return {}
        try:
            return json.loads(index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _read_session_header(self, session_file: Path) -> Optional[Dict[str, Any]]:
        """Read the first line (session header) from a JSONL file."""
        try:
            with open(session_file, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
                if first_line:
                    data = json.loads(first_line)
                    if data.get("type") == "session":
                        return data
        except (json.JSONDecodeError, OSError):
            pass
        return None

    def _get_first_user_message(self, session_file: Path) -> str:
        """Scan JSONL for the first user message text."""
        try:
            with open(session_file, "r", encoding="utf-8") as f:
                for raw_line in f:
                    raw_line = raw_line.strip()
                    if not raw_line:
                        continue
                    try:
                        line = json.loads(raw_line)
                    except json.JSONDecodeError:
                        continue
                    if line.get("type") != "message":
                        continue
                    msg = line.get("message", {})
                    if msg.get("role") != "user":
                        continue
                    content = msg.get("content", "")
                    text = _extract_text(content)
                    if text:
                        return text[:200]
        except OSError:
            pass
        return ""

    def _read_jsonl(self, path: Path) -> List[Dict[str, Any]]:
        """Read all lines from a JSONL file."""
        lines = []
        with open(path, "r", encoding="utf-8") as f:
            for raw_line in f:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    lines.append(json.loads(raw_line))
                except json.JSONDecodeError:
                    continue
        return lines

    def _find_session_file(self, session_id: str) -> Optional[Path]:
        """Find a session JSONL file by session ID across all agents."""
        for agent_dir in self._iter_agent_dirs():
            # Check sessions.json index first
            index = self._read_sessions_index(agent_dir)
            for key, entry in index.items():
                if entry.get("sessionId") == session_id:
                    p = Path(entry.get("sessionFile", ""))
                    if p.exists():
                        return p

            # Fallback: scan JSONL files
            sessions_dir = agent_dir / "sessions"
            if not sessions_dir.is_dir():
                continue
            for jsonl_file in sessions_dir.glob("*.jsonl"):
                if ".checkpoint." in jsonl_file.name:
                    continue
                if jsonl_file.stem == session_id:
                    return jsonl_file
                header = self._read_session_header(jsonl_file)
                if header and header.get("sessionId") == session_id:
                    return jsonl_file
        return None

    def _find_session_metadata(self, session_id: str) -> tuple:
        """Find agent_id and origin for a session from sessions.json."""
        for agent_dir in self._iter_agent_dirs():
            index = self._read_sessions_index(agent_dir)
            for key, entry in index.items():
                if entry.get("sessionId") == session_id:
                    return agent_dir.name, entry.get("origin")
        return None, None

    def _resolve_agent_dir(self, agent_id: Optional[str] = None) -> Path:
        """Get the target agent directory for import."""
        if agent_id:
            d = self._agents_dir / agent_id
            d.mkdir(parents=True, exist_ok=True)
            return d
        # Default to first existing agent
        dirs = self._iter_agent_dirs()
        if dirs:
            return dirs[0]
        # Create a default
        d = self._agents_dir / "main"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _update_sessions_index(
        self, agent_dir: Path, session_id: str, session_file: str, meta: Dict[str, Any]
    ) -> None:
        """Atomically update sessions.json with a new session entry."""
        index = self._read_sessions_index(agent_dir)
        origin = meta.get("origin", {
            "provider": "session-sync",
            "surface": "imported",
        })
        key = f"imported:{session_id}"
        index[key] = {
            "sessionId": session_id,
            "sessionFile": session_file,
            "origin": origin,
            "updatedAt": int(datetime.now(timezone.utc).timestamp() * 1000),
        }
        index_path = agent_dir / "sessions.json"
        index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
