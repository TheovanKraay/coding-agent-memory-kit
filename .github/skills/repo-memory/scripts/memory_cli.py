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

from agent_memory_toolkit import CosmosMemoryClient


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
