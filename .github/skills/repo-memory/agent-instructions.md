# Repo Memory — Persistent Context Across Sessions

This repo has a persistent memory skill at `.github/skills/repo-memory/SKILL.md` — read it for full details.

## IMPORTANT: Session Persistence

You MUST sync your conversations to the persistent memory store. This is how context survives between sessions. Use your agent name as `--user-id` (e.g. `copilot`, `claude`, `cursor`).

**At the START of every chat session**, run:
- **Bash/macOS/Linux:** `.github/skills/repo-memory/memory session-import --user-id copilot`
- **PowerShell/Windows:** `.github\skills\repo-memory\memory.ps1 session-import --user-id copilot`

**After every significant exchange** (decisions, code changes, problem solving), run:
- **Bash/macOS/Linux:** `.github/skills/repo-memory/memory session-export --user-id copilot`
- **PowerShell/Windows:** `.github\skills\repo-memory\memory.ps1 session-export --user-id copilot`

**To search past context from previous sessions:**
- **Bash/macOS/Linux:** `.github/skills/repo-memory/memory search --query "..." --user-id copilot`
- **PowerShell/Windows:** `.github\skills\repo-memory\memory.ps1 search --query "..." --user-id copilot`

## Keep Artifacts Updated

As you work, maintain these files in the repo root:
- **STATE.md** — current project state and active tasks
- **DECISIONS.md** — architectural and design decisions with rationale
- **FAILURES.md** — what went wrong and lessons learned
- **CHANGELOG.md** — significant changes made

These files ARE your long-term memory. Future sessions depend on them.
