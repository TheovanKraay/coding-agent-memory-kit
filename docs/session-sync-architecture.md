# Session Sync Architecture

## Problem Statement

Coding agents (Claude Code, GitHub Copilot, Cursor, OpenAI Codex) maintain conversation state locally on whatever machine they run on. When a developer switches machines — laptop to desktop, local to VPS, or CI — the agent starts from scratch. There's no way to resume a session started on machine A from machine B.

Session sync solves this by exporting platform-specific session state into Cosmos DB and importing it back on another machine, enabling true cross-machine agent continuity.

## Design Overview

```
┌──────────────────┐     ┌──────────────┐     ┌──────────────────┐     ┌────────────┐
│  Platform State   │◄───►│   Adapter    │◄───►│  SessionStore    │◄───►│ Cosmos DB  │
│ (local files/DB)  │     │ (per-platform)│     │ (store.py)       │     │            │
└──────────────────┘     └──────────────┘     └──────────────────┘     └────────────┘
         │                       │
         │              ┌────────┴────────┐
         │              │  base.py ABC    │
         │              │  SessionAdapter │
         │              └─────────────────┘
         │
    ┌────┴────────────────────────────────────────────┐
    │  openclaw.py   │  claude_code.py  │  copilot.py  │
    │  cursor.py     │  codex.py                       │
    └──────────────────────────────────────────────────┘
```

The system uses a **pluggable adapter pattern**. Each coding agent platform gets its own adapter that knows how to read/write that platform's session files. A common `SessionStore` handles Cosmos DB persistence. The CLI orchestrates everything.

## Adapter Interface

```python
class SessionAdapter(ABC):
    platform: str  # "claude-code", "copilot", "cursor", "codex"

    def detect(self) -> bool
        # Is this platform installed on the current machine?

    def locate_sessions(self, workspace: str = None) -> list[SessionInfo]
        # Find local session files, optionally filtered by workspace

    def export_session(self, session_id: str) -> dict
        # Read a local session → dict with "turns" and "metadata" keys

    def import_session(self, data: dict) -> str
        # Write session data to local platform state → platform session ID

    def resume_command(self, session_id: str) -> str
        # CLI command or instructions to resume this session
```

### Export Format

All adapters return the same portable format from `export_session()`:

```python
{
    "metadata": {
        "platform_session_id": "abc-123",
        "platform": "claude-code",
        "workspace": "/home/user/project",
        "model": "claude-sonnet-4-20250514",
        "summary": "First user message or title...",
        "created_at": "ISO-8601",
        "updated_at": "ISO-8601",
        "fingerprint": "sha256:...",
    },
    "turns": [
        {"role": "user", "content": "...", "tool_use": None},
        {"role": "assistant", "content": "...", "tool_use": [...]},
    ]
}
```

The `SessionStore` consumes this format and writes individual Cosmos documents. The same format is returned by `SessionStore.get_session()` and consumed by `adapter.import_session()`.

`SessionInfo` dataclass (for `locate_sessions`):
- `id` — platform session ID
- `created_at` — ISO-8601 timestamp
- `updated_at` — ISO-8601 timestamp
- `workspace` — workspace/cwd path
- `summary_hint` — first user message or title
- `path` — local file/DB path

## Supported Platforms

### Claude Code (CLI + VS Code Extension)

- **Fragility: LOW** — cleanest integration
- **Storage:** `~/.claude/sessions/*.json`
- **Format:** JSON with `id`, `cwd`, `messages[]`, `model`, `created_at`, `updated_at`
- **Resume:** `claude --resume <session-id>`
- **Notes:** VS Code extension uses the same CLI underneath. Session files are self-contained JSON — trivial to read, write, and round-trip.

### GitHub Copilot

- **Fragility: HIGH** — reverse-engineered, no official API
- **Storage:** VS Code globalStorage
  - Linux: `~/.config/Code/User/globalStorage/github.copilot-chat/`
  - macOS: `~/Library/Application Support/Code/User/globalStorage/github.copilot-chat/`
  - Windows: `%APPDATA%/Code/User/globalStorage/github.copilot-chat/`
- **Format:** SQLite database. Assumed tables: `conversations` (id, title, created_at, updated_at), `messages` (conversation_id, role, content, created_at)
- **Resume:** Open VS Code — no CLI resume support
- **Notes:** Schema is reverse-engineered and may change with any VS Code/Copilot update. Every schema assumption is documented in the adapter code.

### Cursor

- **Fragility: HIGH** — VS Code fork, reverse-engineered
- **Storage:** Cursor's globalStorage
  - Linux: `~/.config/Cursor/User/globalStorage/`
  - macOS: `~/Library/Application Support/Cursor/User/globalStorage/`
- **Format:** SQLite/LevelDB. Similar to Copilot but table names may differ (Cursor fork).
- **Resume:** Open Cursor — no CLI resume
- **Notes:** Cursor frequently changes its internals. Same fragility caveats as Copilot, plus fork-specific divergence.

### OpenAI Codex

- **Fragility: VERY HIGH** — cloud-only, no local state
- **Storage:** Sessions live on OpenAI servers. No local files.
- **Capabilities:** `detect()` checks for codex CLI/config. `export_session()` can store synthetic summaries from markdown artifacts. All other methods raise `NotImplementedError`.
- **Notes:** Most fragile adapter. Would need API access or scraping to get real session data. Currently a best-effort stub.

### OpenClaw

- **Fragility: LOW** — we control the format
- **Storage:** `~/.openclaw/agents/<agent-id>/sessions/*.jsonl` with a `sessions.json` index per agent
- **Format:** JSONL (one JSON object per line), based on the Claude Agent SDK format with additional custom types. Key line types:
  - `session` — header with version, session ID, cwd, model
  - `message` — conversation turns with `message.role` and `message.content` (content blocks)
  - `compaction` — context window compaction markers (filtered on export)
  - `custom:openclaw:bootstrap-context:full` — injected system prompts (filtered on export)
  - `custom_message:openclaw.sessions_yield` — subagent orchestration yield points (preserved as metadata)
- **Resume:** Sessions appear automatically in the agent's session list; no CLI command needed
- **Notes:** Multiple agents can exist under `~/.openclaw/agents/`. The adapter scans all agent directories. Checkpoint files (`*.checkpoint.*.jsonl`) are ignored in favor of the canonical `.jsonl` file. The adapter is first in detection order since if running inside OpenClaw, it's the most relevant platform.

## Cosmos DB Storage Model

Sessions are stored as **individual turn documents** plus one **metadata document** per session. All documents in a session share the same partition key (`session_id` = `cosmos_session_id`).

This aligns with the existing AgentMemoryToolkit hierarchical partition key `[/user_id, /thread_id]`:
- `user_id` = agent/user identifier
- `thread_id` = `cosmos_session_id` (the UUID we generate)

### Turn Document

One document per conversation turn:

```json
{
  "id": "turn-uuid",
  "session_id": "cosmos-session-uuid",
  "platform_session_id": "abc-123",
  "platform": "claude-code",
  "role": "user",
  "content": "Fix the auth bug",
  "tool_use": null,
  "turn_index": 0,
  "created_at": "2025-01-15T10:00:00Z",
  "memory_type": "session_turn"
}
```

### Session Metadata Document

One document per session, same partition:

```json
{
  "id": "meta-<cosmos-session-uuid>",
  "session_id": "cosmos-session-uuid",
  "memory_type": "session_meta",
  "platform": "claude-code",
  "platform_session_id": "abc-123",
  "platform_ids": {
    "claude-code": "abc-123",
    "cursor": "row-42"
  },
  "machine_hostname": "dev-laptop",
  "workspace_path": "/home/user/myproject",
  "summary": "Debugging auth token refresh bug...",
  "fingerprint": "sha256-of-first-message+timestamp",
  "model": "claude-sonnet-4-20250514",
  "turn_count": 47,
  "created_at": "2025-01-15T10:00:00Z",
  "updated_at": "2025-01-15T12:30:00Z"
}
```

### Why Per-Turn Storage?

1. **Granular vector search** — individual turns can be embedded and searched independently
2. **Incremental sync** — only new turns need to be uploaded on re-export
3. **Alignment with AgentMemoryToolkit** — the existing client is designed for per-message storage
4. **Partition efficiency** — all turns for a session share a partition, enabling efficient full-session reads

### cosmos_session_id as Canonical ID

The `cosmos_session_id` (a UUID we generate) is the canonical session identifier across all platforms. The `platform_session_id` is tracked per-platform in the metadata doc's `platform_ids` map. This is because:
- The same session may be imported to multiple platforms
- Each platform assigns its own internal ID
- We need a stable cross-platform key

## Sync Reconciliation

The `session-sync` command performs bidirectional reconciliation:

```
1. Enumerate local sessions (via adapter.locate_sessions())
2. Query Cosmos for all session_meta docs matching the user_id
3. For each local session:
   a. Check Cosmos metadata docs' platform_ids for current platform's session ID
   b. If no match, try fingerprint-based correlation
   c. If no match → NEW_LOCAL → export to Cosmos (generates new cosmos_session_id)
   d. If match exists:
      - If local.updated_at > cosmos.updated_at → LOCAL_NEWER → re-export new turns
      - If cosmos.updated_at > local.updated_at → REMOTE_NEWER → import
      - If equal → IN_SYNC → skip
4. For each Cosmos session with no local match for this platform:
   → REMOTE_ONLY → import if workspace matches, otherwise skip
5. After import, record the new platform_session_id in the Cosmos metadata doc's platform_ids
6. Print sync report
```

### Sync Report Format

```json
{
  "exported": 3,
  "imported": 1,
  "in_sync": 5,
  "conflicts_resolved": 0,
  "skipped_remote": 2,
  "details": [
    {"session_id": "abc", "action": "exported", "reason": "new_local"},
    {"session_id": "def", "action": "imported", "reason": "remote_newer"}
  ]
}
```

## Correlation Strategy

**Primary:** Check the `platform_ids` map in Cosmos session metadata documents. For each local session, look for a metadata doc where `platform_ids[current_platform]` matches the local session ID.

**Fallback (fingerprinting):** For platforms with unstable IDs (Copilot, Cursor may regenerate IDs), we compute a fingerprint:

```
fingerprint = sha256(
    created_at_iso +
    first_user_message_content[:200] +
    workspace_path
)
```

This catches cases where the platform reassigned a new ID to what is logically the same session.

## Conflict Resolution

When both local and remote have changes (rare — usually means two machines edited the same session):

1. **Newer wins** — the version with the later `updated_at` is kept as the canonical version.
2. **Older archived** — the losing version is saved as a snapshot in Cosmos with `memory_type="session_snapshot"` and a reference to the winning version's `cosmos_session_id`.

This is a simple, predictable strategy. Users who need more sophisticated merge can manually inspect snapshots.

## Security Considerations

- **Session files contain conversation history** — potentially proprietary code, secrets, API keys mentioned in conversation. Treat them as sensitive.
- **Cosmos DB access** is gated by `DefaultAzureCredential` — same auth as the rest of the memory system.
- **No session data is stored in git** — only in Cosmos DB.
- **Workspace paths** are stored for correlation but may leak directory structure. Acceptable for single-user/team scenarios.
- **Consider TTL** — old sessions could be auto-expired via Cosmos TTL policies.

## Data Flow Diagrams

### Export

```
Developer runs: python memory_cli.py session-export --session-id abc

1. CLI → get_adapter(platform) → adapter.export_session("abc")
2. Adapter reads local file/DB → returns {metadata: {...}, turns: [...]}
3. CLI → SessionStore.save_session(data, user_id)
4. SessionStore generates cosmos_session_id (or reuses existing)
5. SessionStore → CosmosMemoryClient.add_cosmos() for each turn (memory_type="session_turn")
6. SessionStore → CosmosMemoryClient.add_cosmos() for metadata doc (memory_type="session_meta")
7. Summary in metadata doc gets vector-embedded for search
```

### Import

```
Developer runs: python memory_cli.py session-import --session-id <cosmos-session-id>

1. CLI → SessionStore.get_session(cosmos_session_id)
2. SessionStore queries all docs where thread_id = cosmos_session_id
3. SessionStore separates metadata (session_meta) from turns (session_turn)
4. SessionStore reconstructs {metadata: {...}, turns: [...]} sorted by turn_index
5. CLI → get_adapter(platform) → adapter.import_session(data)
6. Adapter writes to local file/DB → returns new platform_session_id
7. CLI → SessionStore updates metadata doc's platform_ids with new mapping
8. CLI → adapter.resume_command(platform_session_id) → prints resume instructions
```

### Sync

```
Developer runs: python memory_cli.py session-sync

1. CLI → get_adapter(platform)
2. adapter.locate_sessions() → local_sessions[]
3. SessionStore.list_sessions(user_id) → cosmos_meta_docs[]
4. For each local session:
   a. Check cosmos_meta_docs' platform_ids for match
   b. Fallback: fingerprint match
   c. Apply reconciliation rules
5. For NEW_LOCAL / LOCAL_NEWER: adapter.export_session() → SessionStore.save_session()
6. For REMOTE_ONLY / REMOTE_NEWER: SessionStore.get_session() → adapter.import_session()
7. Update platform_ids in Cosmos metadata after each import
8. Print sync report
```
