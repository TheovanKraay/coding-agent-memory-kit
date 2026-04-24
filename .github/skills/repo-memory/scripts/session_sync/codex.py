"""OpenAI Codex session adapter.

FRAGILITY: VERY HIGH — Codex sessions are cloud-only on OpenAI's servers.
There are no local session files to read or write. This adapter is a
best-effort stub that can only:
- Detect if the codex CLI is installed
- Export synthetic session summaries from local markdown artifacts
- Provide guidance on limitations

What could break:
- Everything. There is no stable local API or file format.
- OpenAI may add local session caching in the future, which would change this entirely.
- The codex CLI may not exist or may be renamed.

This adapter exists so the registry has an entry for Codex and users get
clear error messages rather than cryptic failures.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import SessionAdapter, SessionInfo, compute_fingerprint


class CodexAdapter(SessionAdapter):
    platform = "codex"

    def detect(self) -> bool:
        """Check for codex CLI or ~/.codex config directory."""
        if (Path.home() / ".codex").is_dir():
            return True
        return shutil.which("codex") is not None

    def locate_sessions(self, workspace: Optional[str] = None) -> List[SessionInfo]:
        """Codex sessions are cloud-only — no local sessions to enumerate.

        Returns an empty list. Use export_session() with a synthetic summary
        if you have markdown artifacts to capture.
        """
        if not self.detect():
            return []
        # No local session files exist for Codex
        return []

    def export_session(self, session_id: str) -> Dict[str, Any]:
        """Export a synthetic session summary.

        Since Codex has no local session state, this method accepts a
        session_id that is actually a path to a markdown artifact file
        (e.g., a conversation log you've saved manually) and wraps it
        as a synthetic session.

        If the session_id is not a valid file path, raises NotImplementedError.
        """
        artifact_path = Path(session_id)
        if artifact_path.is_file():
            content = artifact_path.read_text(encoding="utf-8")
            summary = content[:500]
            fp = compute_fingerprint("", summary, str(artifact_path.parent))

            return {
                "metadata": {
                    "platform_session_id": session_id,
                    "platform": self.platform,
                    "workspace": str(artifact_path.parent),
                    "model": "codex",
                    "summary": summary,
                    "created_at": "",
                    "updated_at": "",
                    "fingerprint": fp,
                    "synthetic": True,
                },
                "turns": [
                    {"role": "system", "content": f"[Synthetic session from artifact: {session_id}]", "tool_use": None},
                    {"role": "assistant", "content": content, "tool_use": None},
                ],
            }

        raise NotImplementedError(
            f"Codex sessions are cloud-only on OpenAI's servers. "
            f"There are no local session files to export. "
            f"To export a synthetic session, pass the path to a markdown artifact file "
            f"as the session_id argument. Got: '{session_id}'"
        )

    def import_session(self, data: Dict[str, Any]) -> str:
        """Codex has no local state to write to.

        Raises NotImplementedError with guidance.
        """
        raise NotImplementedError(
            "Codex sessions are cloud-only. There is no local platform state to import into. "
            "The session data has been stored in Cosmos DB and can be exported to other platforms "
            "(e.g., Claude Code) using: python memory_cli.py session-import --platform claude-code"
        )

    def resume_command(self, session_id: str) -> str:
        return (
            f"Codex sessions cannot be resumed via CLI. "
            f"Session '{session_id}' is stored in Cosmos DB. "
            f"You can import it to another platform for continuation."
        )
