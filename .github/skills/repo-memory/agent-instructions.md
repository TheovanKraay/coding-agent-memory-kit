# Repo Memory — Persistent Context Across Sessions

This repo has a persistent memory skill at `.github/skills/repo-memory/SKILL.md` — read it for full details.

## Quick Start

**At session start** — load previous context:
- **Bash/macOS/Linux:** `.github/skills/repo-memory/memory session-import`
- **PowerShell/Windows:** `.github\skills\repo-memory\memory.ps1 session-import`

**At session end** — save this session's context:
- **Bash/macOS/Linux:** `.github/skills/repo-memory/memory session-export`
- **PowerShell/Windows:** `.github\skills\repo-memory\memory.ps1 session-export`

**Search past context:**
- **Bash/macOS/Linux:** `.github/skills/repo-memory/memory search --query "..." --user-id <agent-id>`
- **PowerShell/Windows:** `.github\skills\repo-memory\memory.ps1 search --query "..." --user-id <agent-id>`

## Keep Artifacts Updated

As you work, maintain these files in the repo root:
- **STATE.md** — current project state and active tasks
- **DECISIONS.md** — architectural and design decisions with rationale
- **FAILURES.md** — what went wrong and lessons learned
- **CHANGELOG.md** — significant changes made

These files ARE your long-term memory. Future sessions depend on them.
