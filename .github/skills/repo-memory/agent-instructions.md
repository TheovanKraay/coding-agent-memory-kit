# Repo Memory — Persistent Context Across Sessions

This repo has a persistent memory skill at `.github/skills/repo-memory/SKILL.md` — read it for full details.

## IMPORTANT: Session Persistence

You MUST save conversations to the persistent memory store. This is how context survives between sessions.

When the user says **"export session"**, **"save session"**, or **"save this conversation"**, follow the steps below to store the conversation.

### Saving conversations (after every significant exchange)

Generate a unique thread ID at the start of each session (e.g. a timestamp like `2026-04-25-1330`). Then after each significant exchange, store the turns with **VERBATIM content** — copy the exact text, not a summary:

**PowerShell/Windows:**
```
.github\skills\repo-memory\memory.ps1 add --user-id copilot --thread-id <session-id> --role user --content "<EXACT text the user typed, verbatim>"
.github\skills\repo-memory\memory.ps1 add --user-id copilot --thread-id <session-id> --role assistant --content "<EXACT text of your response, verbatim>"
```

**Bash/macOS/Linux:**
```
.github/skills/repo-memory/memory add --user-id copilot --thread-id <session-id> --role user --content "<EXACT text the user typed, verbatim>"
.github/skills/repo-memory/memory add --user-id copilot --thread-id <session-id> --role assistant --content "<EXACT text of your response, verbatim>"
```

**IMPORTANT:** Store the actual message content, NOT a summary. The content should be the real words spoken, not descriptions like "Asked about X" or "Explained Y".

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

As you work, maintain these files under `.github/memory/`:
- **`.github/memory/STATE.md`** — current project state and active tasks
- **`.github/memory/DECISIONS.md`** — architectural and design decisions with rationale
- **`.github/memory/FAILURES.md`** — what went wrong and lessons learned
- **`.github/memory/CHANGELOG.md`** — significant changes made

These files ARE your long-term memory. Future sessions depend on them.
