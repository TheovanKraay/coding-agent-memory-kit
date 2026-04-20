"""Long-term memory manager — reads and writes repo markdown artifacts."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .models import ChangelogEntry, Decision, FailureRecord, StateEntry


class LongTermMemoryManager:
    """Manages the markdown-based long-term memory files in a repo.

    Parameters
    ----------
    repo_root : str | Path
        Path to the repository root containing AGENTS.md, STATE.md, etc.
    """

    def __init__(self, repo_root: str | Path) -> None:
        self.root = Path(repo_root)

    # -- helpers ------------------------------------------------------------

    def _read(self, filename: str) -> str:
        path = self.root / filename
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def _write(self, filename: str, content: str) -> None:
        path = self.root / filename
        path.write_text(content, encoding="utf-8")

    def _append_section(self, filename: str, section: str, entry: str) -> None:
        """Append *entry* text under the first occurrence of *section* heading."""
        content = self._read(filename)
        marker = f"## {section}"
        if marker in content:
            idx = content.index(marker) + len(marker)
            # find end of heading line
            nl = content.find("\n", idx)
            if nl == -1:
                nl = len(content)
            content = content[: nl + 1] + entry + "\n" + content[nl + 1 :]
        else:
            content += f"\n{marker}\n{entry}\n"
        self._write(filename, content)

    # -- STATE.md -----------------------------------------------------------

    def get_state(self) -> str:
        """Return raw STATE.md content."""
        return self._read("STATE.md")

    def update_state(self, entry: StateEntry) -> None:
        """Add or move a state entry under the appropriate section."""
        section_map = {
            "in_progress": "In Progress",
            "blocked": "Blocked",
            "done": "Done",
        }
        section = section_map.get(entry.status, "In Progress")
        date_str = entry.since.strftime("%Y-%m-%d")
        line = f"- **{entry.item}** — {entry.description} (agent: {entry.agent_id or 'unknown'}, since: {date_str})"
        self._append_section("STATE.md", section, line)

    # -- DECISIONS.md -------------------------------------------------------

    def get_decisions(self) -> str:
        return self._read("DECISIONS.md")

    def log_decision(self, decision: Decision) -> None:
        """Append a decision entry."""
        # find next DEC number
        content = self._read("DECISIONS.md")
        nums = [int(m) for m in re.findall(r"DEC-(\d+)", content)]
        next_num = max(nums, default=0) + 1
        date_str = decision.date.strftime("%Y-%m-%d")
        block = (
            f"\n## DEC-{next_num:03d}: {decision.title}\n"
            f"- **Date:** {date_str}\n"
            f"- **Status:** {decision.status}\n"
            f"- **Context:** {decision.context}\n"
            f"- **Decision:** {decision.decision}\n"
            f"- **Rationale:** {decision.rationale}\n"
        )
        if decision.consequences:
            block += f"- **Consequences:** {decision.consequences}\n"
        self._write("DECISIONS.md", content + block)

    # -- FAILURES.md --------------------------------------------------------

    def get_failures(self) -> str:
        return self._read("FAILURES.md")

    def log_failure(self, failure: FailureRecord) -> None:
        content = self._read("FAILURES.md")
        # Remove placeholder
        content = content.replace("*No failures recorded yet.*", "")
        nums = [int(m) for m in re.findall(r"FAIL-(\d+)", content)]
        next_num = max(nums, default=0) + 1
        date_str = failure.date.strftime("%Y-%m-%d")
        block = (
            f"\n## FAIL-{next_num:03d}: {failure.title}\n"
            f"- **Date:** {date_str}\n"
            f"- **Agent:** {failure.agent_id or 'unknown'}\n"
            f"- **What happened:** {failure.what_happened}\n"
            f"- **Root cause:** {failure.root_cause}\n"
        )
        if failure.resolution:
            block += f"- **Resolution:** {failure.resolution}\n"
        if failure.lesson:
            block += f"- **Lesson:** {failure.lesson}\n"
        self._write("FAILURES.md", content + block)

    # -- CHANGELOG.md -------------------------------------------------------

    def get_changelog(self) -> str:
        return self._read("CHANGELOG.md")

    def append_changelog(self, entry: ChangelogEntry) -> None:
        content = self._read("CHANGELOG.md")
        date_str = entry.date.strftime("%Y-%m-%d")
        block = f"\n## [{entry.version}] - {date_str}\n### {entry.category}\n- {entry.description}\n"
        self._write("CHANGELOG.md", content + block)
