#!/usr/bin/env python3
"""CLI wrapper around AgentMemoryToolkit's CosmosMemoryClient.

Every command delegates to CosmosMemoryClient — this script never
touches azure-cosmos directly.
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# .env file loader (no external dependencies)
# ---------------------------------------------------------------------------

def _load_dotenv():
    """Load variables from .env files into os.environ.

    Search order (first found wins per variable):
      1. .github/skills/repo-memory/.env  (skill-local)
      2. <repo-root>/.env                 (repo-root)

    Existing env vars are NOT overwritten — real environment always wins.
    """
    skill_dir = Path(__file__).resolve().parent.parent  # .github/skills/repo-memory
    repo_root = skill_dir.parent.parent.parent          # repo root

    candidates = [
        skill_dir / ".env",
        repo_root / ".env",
    ]

    loaded = set()
    for env_path in candidates:
        if not env_path.is_file():
            continue
        try:
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip()
                    # Remove surrounding quotes
                    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                        value = value[1:-1]
                    # Don't overwrite existing env vars
                    if key and key not in os.environ and key not in loaded:
                        os.environ[key] = value
                        loaded.add(key)
        except OSError:
            continue

    if loaded:
        print(f"  Loaded {len(loaded)} var(s) from .env: {', '.join(sorted(loaded))}", file=sys.stderr)


_load_dotenv()

from agent_memory_toolkit import CosmosMemoryClient

# Add scripts dir to path for session_sync imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Lazy import to avoid breaking existing commands if session_sync deps missing
def _get_session_deps():
    from session_sync import get_adapter, list_adapters
    from session_sync.store import SessionStore
    return get_adapter, list_adapters, SessionStore


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------

def get_client() -> CosmosMemoryClient:
    return CosmosMemoryClient(
        cosmos_endpoint=os.environ.get("COSMOS_DB_ENDPOINT"),
        cosmos_database=os.environ.get("COSMOS_DB_DATABASE", "agent_memory"),
        cosmos_container=os.environ.get("COSMOS_DB_CONTAINER", "memories"),
        ai_foundry_endpoint=os.environ.get("AI_FOUNDRY_ENDPOINT"),
        embedding_model=os.environ.get("EMBEDDING_MODEL", "text-embedding-3-large"),
        adf_endpoint=os.environ.get("ADF_ENDPOINT"),
        adf_key=os.environ.get("ADF_KEY"),
        use_default_credential=True,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SKILL_DIR = Path(__file__).resolve().parent.parent          # .github/skills/repo-memory
TEMPLATE_DIR = SKILL_DIR / "templates"
REPO_ROOT = SKILL_DIR.parent.parent.parent                  # repo root


def _copy_templates():
    """Copy markdown templates to repo root if they don't already exist."""
    if not TEMPLATE_DIR.is_dir():
        return
    for tmpl in TEMPLATE_DIR.iterdir():
        dest = REPO_ROOT / tmpl.name
        if not dest.exists():
            shutil.copy2(tmpl, dest)
            print(f"  Created {tmpl.name}")


def _json_out(obj):
    """Print an object as JSON to stdout."""
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump()
    elif isinstance(obj, list):
        obj = [x.model_dump() if hasattr(x, "model_dump") else x for x in obj]
    print(json.dumps(obj, indent=2, default=str))


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_init(_args):
    """Initialise memory store and copy markdown templates."""
    client = get_client()                      # auto-calls create_memory_store()
    _copy_templates()
    print("✅ Memory store initialised and templates copied.")


def cmd_add(args):
    client = get_client()
    metadata = {}
    if args.agent_id:
        metadata["agent_id"] = args.agent_id
    record = client.add_cosmos(
        user_id=args.user_id,
        thread_id=args.thread_id,
        role=args.role,
        content=args.content,
        memory_type=args.memory_type,
        metadata=metadata or None,
    )
    _json_out(record)


def cmd_sync(args):
    client = get_client()
    with open(args.turns_file) as f:
        turns = json.load(f)
    for t in turns:
        client.add_local(
            user_id=t["user_id"],
            thread_id=t["thread_id"],
            role=t["role"],
            content=t["content"],
            memory_type=t.get("memory_type", "turn"),
            metadata=t.get("metadata"),
        )
    results = client.push_to_cosmos()
    _json_out(results)


def cmd_get_thread(args):
    client = get_client()
    kwargs = {"thread_id": args.thread_id}
    if args.user_id:
        kwargs["user_id"] = args.user_id
    if args.recent_k:
        kwargs["recent_k"] = args.recent_k
    records = client.get_thread(**kwargs)
    _json_out(records)


def cmd_get_memories(args):
    client = get_client()
    kwargs = {"user_id": args.user_id}
    if args.memory_type:
        kwargs["memory_type"] = args.memory_type
    if args.recent_k:
        kwargs["recent_k"] = args.recent_k
    records = client.get_memories(**kwargs)
    _json_out(records)


def cmd_search(args):
    client = get_client()
    kwargs = {
        "query": args.query,
        "user_id": args.user_id,
    }
    if args.memory_type:
        kwargs["memory_type"] = args.memory_type
    if args.top_k:
        kwargs["top_k"] = args.top_k
    if args.hybrid:
        kwargs["hybrid"] = True
    results = client.search_cosmos(**kwargs)
    _json_out(results)


def cmd_get_user_summary(args):
    client = get_client()
    summary = client.get_user_summary(user_id=args.user_id)
    _json_out(summary)


def cmd_summarize_thread(args):
    client = get_client()
    kwargs = {"user_id": args.user_id, "thread_id": args.thread_id}
    if args.recent_k:
        kwargs["recent_k"] = args.recent_k
    result = client.generate_thread_summary(**kwargs)
    _json_out(result)


def cmd_extract_facts(args):
    client = get_client()
    kwargs = {"user_id": args.user_id, "thread_id": args.thread_id}
    if args.recent_k:
        kwargs["recent_k"] = args.recent_k
    result = client.extract_facts(**kwargs)
    _json_out(result)


def cmd_summarize_user(args):
    client = get_client()
    kwargs = {"user_id": args.user_id}
    if args.thread_ids:
        kwargs["thread_ids"] = args.thread_ids.split(",")
    result = client.generate_user_summary(**kwargs)
    _json_out(result)


# ---------------------------------------------------------------------------
# Session sync commands
# ---------------------------------------------------------------------------

def cmd_session_export(args):
    get_adapter, _, SessionStore = _get_session_deps()
    adapter = get_adapter(args.platform)
    client = get_client()
    store = SessionStore(client, user_id=args.user_id)

    if args.all:
        sessions = adapter.locate_sessions()
        results = []
        for s in sessions:
            data = adapter.export_session(s.id)
            cosmos_id = store.save_session(data)
            results.append({"platform_session_id": s.id, "cosmos_session_id": cosmos_id})
        _json_out({"exported": len(results), "sessions": results})
    else:
        if not args.session_id:
            print(json.dumps({"error": "--session-id or --all required"}), file=sys.stderr)
            sys.exit(1)
        data = adapter.export_session(args.session_id)
        cosmos_id = store.save_session(data)
        _json_out({"platform_session_id": args.session_id, "cosmos_session_id": cosmos_id, "platform": adapter.platform})


def cmd_session_import(args):
    get_adapter, _, SessionStore = _get_session_deps()
    adapter = get_adapter(args.platform)
    client = get_client()
    store = SessionStore(client, user_id=args.user_id)

    session_data = store.get_session(args.session_id)
    platform_session_id = adapter.import_session(session_data)

    # Record the new platform_session_id mapping
    store.update_platform_id(args.session_id, adapter.platform, platform_session_id)

    resume_cmd = adapter.resume_command(platform_session_id)
    _json_out({
        "cosmos_session_id": args.session_id,
        "platform": adapter.platform,
        "platform_session_id": platform_session_id,
        "resume_command": resume_cmd,
    })


def cmd_session_sync(args):
    get_adapter, _, SessionStore = _get_session_deps()
    adapter = get_adapter(args.platform)
    client = get_client()
    store = SessionStore(client, user_id=args.user_id)

    local_sessions = adapter.locate_sessions()
    cosmos_sessions = store.list_sessions(platform=None)  # All platforms for cross-matching

    report = {"exported": 0, "imported": 0, "in_sync": 0, "conflicts_resolved": 0, "skipped_remote": 0, "details": []}

    # Index cosmos sessions by platform_id and fingerprint
    cosmos_by_pid = {}
    cosmos_by_fp = {}
    for cs in cosmos_sessions:
        pids = cs.get("platform_ids", {})
        pid = pids.get(adapter.platform)
        if pid:
            cosmos_by_pid[pid] = cs
        fp = cs.get("fingerprint")
        if fp:
            cosmos_by_fp[fp] = cs

    matched_cosmos_ids = set()

    for ls in local_sessions:
        # Try matching by platform_session_id
        cs = cosmos_by_pid.get(ls.id)
        if cs is None:
            # Fallback: fingerprint
            fp = ls.fingerprint()
            cs = cosmos_by_fp.get(fp)

        if cs is None:
            # New local session → export
            data = adapter.export_session(ls.id)
            cosmos_id = store.save_session(data)
            report["exported"] += 1
            report["details"].append({"session_id": ls.id, "cosmos_session_id": cosmos_id, "action": "exported", "reason": "new_local"})
        else:
            cosmos_id = cs["cosmos_session_id"]
            matched_cosmos_ids.add(cosmos_id)
            local_ts = ls.updated_at or ""
            remote_ts = cs.get("updated_at", "")
            if local_ts > remote_ts:
                data = adapter.export_session(ls.id)
                store.save_session(data, cosmos_session_id=cosmos_id)
                report["exported"] += 1
                report["details"].append({"session_id": ls.id, "cosmos_session_id": cosmos_id, "action": "exported", "reason": "local_newer"})
            elif remote_ts > local_ts:
                session_data = store.get_session(cosmos_id)
                pid = adapter.import_session(session_data)
                store.update_platform_id(cosmos_id, adapter.platform, pid)
                report["imported"] += 1
                report["details"].append({"session_id": ls.id, "cosmos_session_id": cosmos_id, "action": "imported", "reason": "remote_newer"})
            else:
                report["in_sync"] += 1
                report["details"].append({"session_id": ls.id, "cosmos_session_id": cosmos_id, "action": "skipped", "reason": "in_sync"})

    # Remote-only sessions
    for cs in cosmos_sessions:
        cosmos_id = cs["cosmos_session_id"]
        if cosmos_id in matched_cosmos_ids:
            continue
        # Skip if this platform already has a mapping (means we just didn't find local)
        pids = cs.get("platform_ids", {})
        if adapter.platform not in pids:
            # Could import, but skip if no workspace match
            report["skipped_remote"] += 1
            report["details"].append({"cosmos_session_id": cosmos_id, "action": "skipped", "reason": "remote_only_no_platform_match"})
        else:
            report["skipped_remote"] += 1
            report["details"].append({"cosmos_session_id": cosmos_id, "action": "skipped", "reason": "remote_only_local_missing"})

    _json_out(report)


def cmd_session_list(args):
    get_adapter, list_adapters_fn, SessionStore = _get_session_deps()
    client = get_client()
    store = SessionStore(client, user_id=args.user_id)

    result = {}

    if args.source in ("local", "both"):
        try:
            adapter = get_adapter(args.platform)
            local_sessions = adapter.locate_sessions()
            result["local"] = [s.to_dict() for s in local_sessions]
        except Exception as e:
            result["local"] = {"error": str(e)}

    if args.source in ("cosmos", "both"):
        cosmos_sessions = store.list_sessions(platform=args.platform)
        result["cosmos"] = cosmos_sessions

    _json_out(result)


def cmd_session_test(args):
    get_adapter, list_adapters_fn, _ = _get_session_deps()
    results = {}

    platforms = [args.platform] if args.platform else list_adapters_fn()
    for p in platforms:
        try:
            adapter = get_adapter(p)
        except ValueError as e:
            results[p] = {"status": "error", "message": str(e)}
            continue

        info = {"platform": p}
        info["detected"] = adapter.detect()

        if info["detected"]:
            try:
                sessions = adapter.locate_sessions()
                info["sessions_found"] = len(sessions)
                info["status"] = "ok"
            except Exception as e:
                info["sessions_found"] = 0
                info["status"] = "partial"
                info["locate_error"] = str(e)
        else:
            info["sessions_found"] = 0
            info["status"] = "not_installed"

        results[p] = info

    _json_out(results)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="CLI wrapper for AgentMemoryToolkit's CosmosMemoryClient"
    )
    sub = p.add_subparsers(dest="command", required=True)

    # init
    sub.add_parser("init", help="Initialise Cosmos DB store and copy templates")

    # add
    a = sub.add_parser("add", help="Add a single memory record to Cosmos")
    a.add_argument("--user-id", required=True)
    a.add_argument("--thread-id", required=True)
    a.add_argument("--role", required=True, choices=["user", "agent", "tool", "system"])
    a.add_argument("--content", required=True)
    a.add_argument("--memory-type", default="turn", choices=["turn", "summary", "fact", "user_summary"])
    a.add_argument("--agent-id", default=None)

    # sync
    s = sub.add_parser("sync", help="Bulk-sync turns from a JSON file")
    s.add_argument("--turns-file", required=True)

    # get-thread
    gt = sub.add_parser("get-thread", help="Retrieve thread history")
    gt.add_argument("--thread-id", required=True)
    gt.add_argument("--user-id", default=None)
    gt.add_argument("--recent-k", type=int, default=None)

    # get-memories
    gm = sub.add_parser("get-memories", help="Get memories for a user")
    gm.add_argument("--user-id", required=True)
    gm.add_argument("--memory-type", default=None)
    gm.add_argument("--recent-k", type=int, default=None)

    # search
    sr = sub.add_parser("search", help="Vector / hybrid search")
    sr.add_argument("--query", required=True)
    sr.add_argument("--user-id", required=True)
    sr.add_argument("--memory-type", default=None)
    sr.add_argument("--top-k", type=int, default=None)
    sr.add_argument("--hybrid", action="store_true")

    # get-user-summary
    us = sub.add_parser("get-user-summary", help="Get cross-thread user summary")
    us.add_argument("--user-id", required=True)

    # summarize-thread
    st = sub.add_parser("summarize-thread", help="Generate thread summary via Durable Functions")
    st.add_argument("--user-id", required=True)
    st.add_argument("--thread-id", required=True)
    st.add_argument("--recent-k", type=int, default=None)

    # extract-facts
    ef = sub.add_parser("extract-facts", help="Extract facts via Durable Functions")
    ef.add_argument("--user-id", required=True)
    ef.add_argument("--thread-id", required=True)
    ef.add_argument("--recent-k", type=int, default=None)

    # summarize-user
    su = sub.add_parser("summarize-user", help="Generate user summary via Durable Functions")
    su.add_argument("--user-id", required=True)
    su.add_argument("--thread-ids", default=None, help="Comma-separated thread IDs")

    # session-export
    se = sub.add_parser("session-export", help="Export local session(s) to Cosmos DB")
    se.add_argument("--platform", default=None, help="Platform name (auto-detect if omitted)")
    se.add_argument("--session-id", default=None, help="Platform session ID to export")
    se.add_argument("--all", action="store_true", help="Export all local sessions")
    se.add_argument("--user-id", required=True)

    # session-import
    si = sub.add_parser("session-import", help="Import a session from Cosmos DB to local platform")
    si.add_argument("--session-id", required=True, help="Cosmos session ID")
    si.add_argument("--platform", default=None, help="Target platform (auto-detect if omitted)")
    si.add_argument("--user-id", required=True)

    # session-sync
    ss = sub.add_parser("session-sync", help="Bidirectional sync between local and Cosmos")
    ss.add_argument("--platform", default=None)
    ss.add_argument("--user-id", required=True)

    # session-list
    sl = sub.add_parser("session-list", help="List sessions from local, Cosmos, or both")
    sl.add_argument("--platform", default=None)
    sl.add_argument("--source", default="both", choices=["local", "cosmos", "both"])
    sl.add_argument("--user-id", required=True)

    # session-test
    st2 = sub.add_parser("session-test", help="Test adapter detection and readiness")
    st2.add_argument("--platform", default=None)

    return p


DISPATCH = {
    "init": cmd_init,
    "add": cmd_add,
    "sync": cmd_sync,
    "get-thread": cmd_get_thread,
    "get-memories": cmd_get_memories,
    "search": cmd_search,
    "get-user-summary": cmd_get_user_summary,
    "summarize-thread": cmd_summarize_thread,
    "extract-facts": cmd_extract_facts,
    "summarize-user": cmd_summarize_user,
    "session-export": cmd_session_export,
    "session-import": cmd_session_import,
    "session-sync": cmd_session_sync,
    "session-list": cmd_session_list,
    "session-test": cmd_session_test,
}


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        DISPATCH[args.command](args)
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
