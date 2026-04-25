# Repo Memory — Persistent Context Across Sessions

This repo has a persistent memory skill at `.github/skills/repo-memory/SKILL.md` — read it for full details.

## IMPORTANT: Session Persistence

You MUST save conversations to the persistent memory store. This is how context survives between sessions.

### Saving conversations (after every significant exchange)

Generate a unique thread ID at the start of each session (e.g. a timestamp like `2026-04-25-1330`). Then after each significant exchange, store the turns:

**PowerShell/Windows:**
```
.github\skills\repo-memory\memory.ps1 add --user-id copilot --thread-id <session-id> --role user --content "what the user asked"
.github\skills\repo-memory\memory.ps1 add --user-id copilot --thread-id <session-id> --role assistant --content "summary of what you did/responded"
```

**Bash/macOS/Linux:**
```
.github/skills/repo-memory/memory add --user-id copilot --thread-id <session-id> --role user --content "what the user asked"
.github/skills/repo-memory/memory add --user-id copilot --thread-id <session-id> --role assistant --content "summary of what you did/responded"
```

Keep the same `--thread-id` for the entire session so all turns are grouped together.

### Searching past context

Before starting complex work, search for relevant prior context:

**PowerShell/Windows:**
```
.github\skills\repo-memory\memory.ps1 search --query "topic you're working on" --user-id copilot
```

**Bash/macOS/Linux:**
```
.github/skills/repo-memory/memory search --query "topic you're working on" --user-id copilot
```

## Keep Artifacts Updated

As you work, maintain these files in the repo root:
- **STATE.md** — current project state and active tasks
- **DECISIONS.md** — architectural and design decisions with rationale
- **FAILURES.md** — what went wrong and lessons learned
- **CHANGELOG.md** — significant changes made

These files ARE your long-term memory. Future sessions depend on them.
