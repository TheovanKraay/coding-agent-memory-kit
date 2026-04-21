# Repo Memory Skill

> Drop-in persistent memory for coding agents. Markdown files for long-term context, Cosmos DB for session transcripts.

## You are an agent reading this skill. Follow these instructions.

This skill gives you persistent memory across sessions. You maintain markdown files in the repo root and optionally sync session transcripts to Azure Cosmos DB.

---

## Session Lifecycle

### On Session Start

1. **Check for memory files** in the repo root:
   - `DECISIONS.md`, `STATE.md`, `CHANGELOG.md`, `FAILURES.md`, `AGENTS.md`
   - If any are missing, create them by running:
     ```bash
     python .github/skills/repo-memory/scripts/memory_init.py
     ```

2. **Read the memory files.** They contain the project's accumulated context — decisions made, current state, past failures, and who's worked on what. Use this to orient yourself.

3. **Check if Cosmos DB is configured** by looking for the `COSMOS_DB_ENDPOINT` environment variable.
   - If set, rehydrate recent session context:
     ```bash
     python .github/skills/repo-memory/scripts/memory_sync.py rehydrate --limit 20
     ```
   - This prints recent session summaries from past agents. Use them to understand what happened recently.
   - If `COSMOS_DB_ENDPOINT` is not set, skip this step. The markdown files alone provide sufficient context.

4. **Generate a session ID** for this session. Use the format: `sess-<8 random hex chars>` (e.g., `sess-a1b2c3d4`).

### During the Session

As you work, **update the markdown files in real time:**

- **DECISIONS.md** — When you make or discover an architectural/design decision, add an entry:
  ```markdown
  ### [Short Title]
  - **Date:** YYYY-MM-DD
  - **Context:** Why this decision came up
  - **Decision:** What was decided
  - **Consequences:** What follows from this
  ```

- **STATE.md** — Update the project state as things change:
  - Move items between `## In Progress`, `## Blocked`, `## Done`
  - Add new items as they emerge

- **CHANGELOG.md** — Log what you changed:
  ```markdown
  ### YYYY-MM-DD — [Agent Name]
  - What changed and why
  ```

- **FAILURES.md** — When something goes wrong, document it:
  ```markdown
  ### [What Failed]
  - **Date:** YYYY-MM-DD
  - **What happened:** Description
  - **Root cause:** Why it failed
  - **Lesson:** What to do differently
  ```

- **AGENTS.md** — If you're a new agent working on this repo, add yourself to the agents list.

**If Cosmos DB is configured**, periodically sync your session turns. Write your recent turns to a JSON file and sync:

```bash
# Write turns to a temp file (array of {role, content, timestamp} objects)
cat > /tmp/session_turns.json << 'EOF'
[
  {"role": "user", "content": "...", "timestamp": "2024-01-15T10:30:00Z"},
  {"role": "assistant", "content": "...", "timestamp": "2024-01-15T10:30:15Z"}
]
EOF

python .github/skills/repo-memory/scripts/memory_sync.py sync \
  --session-id sess-a1b2c3d4 \
  --turns-file /tmp/session_turns.json
```

Do this every 10-15 turns or when you've made significant progress. It's not critical — if you miss a sync, the markdown files still capture the important decisions.

### On Session End

1. **Final sync to Cosmos DB** (if configured):
   ```bash
   python .github/skills/repo-memory/scripts/memory_sync.py sync \
     --session-id sess-a1b2c3d4 \
     --turns-file /tmp/session_turns.json
   ```

2. **Add a session reference** to each markdown file you modified. Append a row to the `## Session References` table at the bottom:
   ```
   | sess-a1b2c3d4 | codex | 2024-01-15 | thread_id: <from sync output> |
   ```

3. **Commit the markdown changes:**
   ```bash
   git add DECISIONS.md STATE.md CHANGELOG.md FAILURES.md AGENTS.md
   git commit -m "memory: update from session sess-a1b2c3d4"
   ```

---

## Searching Past Context

If you need to find something specific from past sessions:

```bash
python .github/skills/repo-memory/scripts/memory_sync.py search \
  --query "what was decided about authentication"
```

This performs a semantic search across all stored session transcripts in Cosmos DB and returns relevant excerpts.

---

## Key Principles

1. **Markdown files ARE the memory.** They're human-readable, git-tracked, and the source of truth for project decisions and state. Always keep them updated.

2. **Cosmos DB is optional but powerful.** It stores full session transcripts for search and cross-agent access. The repo never contains chat history — only pointers in the Session References tables.

3. **You don't need to understand the scripts.** Just call them as documented above. They handle Cosmos DB interactions, auth, indexing, and search.

4. **Auth is Entra ID.** The scripts use `DefaultAzureCredential`. The developer has already authenticated via `az login` or managed identity. Never ask for or store connection strings or keys.

5. **Be a good citizen.** Other agents (and humans) read these markdown files. Write clearly. Be concise. Future you will thank past you.

---

## Script Reference

All scripts are in `.github/skills/repo-memory/scripts/`.

| Command | What it does |
|---------|-------------|
| `python scripts/memory_init.py` | First-time setup: creates Cosmos DB database/container, creates markdown templates |
| `python scripts/memory_sync.py init` | Create/verify Cosmos DB resources |
| `python scripts/memory_sync.py sync --session-id ID --turns-file PATH` | Upload session turns to Cosmos DB |
| `python scripts/memory_sync.py rehydrate --limit N` | Get recent session context (default: 20 turns) |
| `python scripts/memory_sync.py search --query "..."` | Semantic search across all sessions |

---

## File Templates

If you need to recreate any memory file, use these templates:

<details>
<summary>AGENTS.md</summary>

```markdown
# Agents

Who works on this repo — humans and AI agents.

## Humans

| Name | Role | Notes |
|------|------|-------|
| | | |

## AI Agents

| Agent | Platform | First Session | Notes |
|-------|----------|--------------|-------|
| | | | |

## Session References

| Session ID | Agent | Date | Cosmos DB Thread |
|------------|-------|------|-----------------|
```

</details>

<details>
<summary>STATE.md</summary>

```markdown
# Project State

## In Progress

-

## Blocked

-

## Done

-

## Session References

| Session ID | Agent | Date | Cosmos DB Thread |
|------------|-------|------|-----------------|
```

</details>

<details>
<summary>DECISIONS.md</summary>

```markdown
# Decisions

Architecture Decision Records for this project.

## Session References

| Session ID | Agent | Date | Cosmos DB Thread |
|------------|-------|------|-----------------|
```

</details>

<details>
<summary>CHANGELOG.md</summary>

```markdown
# Changelog

## Session References

| Session ID | Agent | Date | Cosmos DB Thread |
|------------|-------|------|-----------------|
```

</details>

<details>
<summary>FAILURES.md</summary>

```markdown
# Failures & Lessons Learned

## Session References

| Session ID | Agent | Date | Cosmos DB Thread |
|------------|-------|------|-----------------|
```

</details>
