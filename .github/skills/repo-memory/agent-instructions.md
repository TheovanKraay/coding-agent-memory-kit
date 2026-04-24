# Repo Memory — Persistent Context Across Sessions

This repo has a persistent memory skill at `.github/skills/repo-memory/SKILL.md` — read it for full details.

## IMPORTANT: Session Persistence

You MUST sync your conversations to the persistent memory store. This is how context survives between sessions.

**At the START of every chat session**, run:
- **Bash/macOS/Linux:** `.github/skills/repo-memory/memory session-import`
- **PowerShell/Windows:** `.github\skills\repo-memory\memory.ps1 session-import`

**After every significant exchange** (decisions, code changes, problem solving), run:
- **Bash/macOS/Linux:** `.github/skills/repo-memory/memory session-export`
- **PowerShell/Windows:** `.github\skills\repo-memory\memory.ps1 session-export`

**To search past context from previous sessions:**
- **Bash/macOS/Linux:** `.github/skills/repo-memory/memory search --query "..." --user-id <agent-id>`
- **PowerShell/Windows:** `.github\skills\repo-memory\memory.ps1 search --query "..." --user-id <agent-id>`

## Keep Artifacts Updated

As you work, maintain these files in the repo root:
- **STATE.md** — current project state and active tasks
- **DECISIONS.md** — architectural and design decisions with rationale
- **FAILURES.md** — what went wrong and lessons learned
- **CHANGELOG.md** — significant changes made

These files ARE your long-term memory. Future sessions depend on them.
