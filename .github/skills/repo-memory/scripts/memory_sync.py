#!/usr/bin/env python3
"""
memory_sync.py — CLI for syncing agent session data to/from Azure Cosmos DB.

Usage:
    python memory_sync.py init
    python memory_sync.py sync --session-id ID --turns-file PATH
    python memory_sync.py rehydrate [--limit N]
    python memory_sync.py search --query "..."
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone

try:
    from azure.identity import DefaultAzureCredential
    from azure.cosmos import CosmosClient, PartitionKey, exceptions
except ImportError:
    print("ERROR: Missing dependencies. Run: pip install -r .github/skills/repo-memory/requirements.txt", file=sys.stderr)
    sys.exit(1)


def get_config():
    endpoint = os.environ.get("COSMOS_DB_ENDPOINT")
    if not endpoint:
        print("ERROR: COSMOS_DB_ENDPOINT environment variable is not set.", file=sys.stderr)
        sys.exit(1)
    database_name = os.environ.get("COSMOS_DB_DATABASE", "agent_memory")
    return endpoint, database_name


def get_client():
    endpoint, _ = get_config()
    credential = DefaultAzureCredential()
    return CosmosClient(endpoint, credential=credential)


def get_container(client, database_name, container_name="sessions"):
    database = client.get_database_client(database_name)
    return database.get_container_client(container_name)


def cmd_init(_args):
    """Create Cosmos DB database and container if they don't exist."""
    endpoint, database_name = get_config()
    client = get_client()

    # Create database
    try:
        database = client.create_database_if_not_exists(id=database_name)
        print(f"Database '{database_name}' ready.")
    except exceptions.CosmosHttpResponseError as e:
        print(f"ERROR creating database: {e.message}", file=sys.stderr)
        sys.exit(1)

    # Create container with partition key on session_id
    try:
        container = database.create_container_if_not_exists(
            id="sessions",
            partition_key=PartitionKey(path="/session_id"),
            default_ttl=-1,  # No expiry
        )
        print(f"Container 'sessions' ready.")
    except exceptions.CosmosHttpResponseError as e:
        print(f"ERROR creating container: {e.message}", file=sys.stderr)
        sys.exit(1)

    print("Cosmos DB initialization complete.")


def cmd_sync(args):
    """Upload session turns to Cosmos DB."""
    if not args.session_id:
        print("ERROR: --session-id is required.", file=sys.stderr)
        sys.exit(1)
    if not args.turns_file:
        print("ERROR: --turns-file is required.", file=sys.stderr)
        sys.exit(1)

    try:
        with open(args.turns_file, "r") as f:
            turns = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"ERROR reading turns file: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(turns, list):
        print("ERROR: turns file must contain a JSON array.", file=sys.stderr)
        sys.exit(1)

    _, database_name = get_config()
    client = get_client()
    container = get_container(client, database_name)

    # Upsert a document per session with all turns
    doc = {
        "id": args.session_id,
        "session_id": args.session_id,
        "turns": turns,
        "turn_count": len(turns),
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "agent": args.agent or "unknown",
    }

    try:
        container.upsert_item(doc)
        print(f"Synced {len(turns)} turns for session {args.session_id}")
        print(f"thread_id: {args.session_id}")
    except exceptions.CosmosHttpResponseError as e:
        print(f"ERROR syncing: {e.message}", file=sys.stderr)
        sys.exit(1)


def cmd_rehydrate(args):
    """Get recent session context from Cosmos DB."""
    _, database_name = get_config()
    client = get_client()
    container = get_container(client, database_name)

    limit = args.limit or 20

    query = f"SELECT TOP {limit} * FROM c ORDER BY c.last_updated DESC"

    try:
        items = list(container.query_items(query=query, enable_cross_partition_query=True))
    except exceptions.CosmosHttpResponseError as e:
        print(f"ERROR querying: {e.message}", file=sys.stderr)
        sys.exit(1)

    if not items:
        print("No previous sessions found.")
        return

    print(f"Found {len(items)} recent session(s):\n")
    for item in items:
        print(f"--- Session: {item.get('session_id', 'unknown')} | Agent: {item.get('agent', 'unknown')} | Updated: {item.get('last_updated', 'unknown')} ---")
        turns = item.get("turns", [])
        # Print last few turns as summary
        for turn in turns[-5:]:
            role = turn.get("role", "?")
            content = turn.get("content", "")
            # Truncate long content
            if len(content) > 200:
                content = content[:200] + "..."
            print(f"  [{role}]: {content}")
        print()


def cmd_search(args):
    """Search across sessions. Basic keyword search (semantic search requires vector indexing)."""
    if not args.query:
        print("ERROR: --query is required.", file=sys.stderr)
        sys.exit(1)

    _, database_name = get_config()
    client = get_client()
    container = get_container(client, database_name)

    # Basic CONTAINS search across turn content
    # For true semantic search, you'd need vector indexing + embeddings
    query_text = args.query.replace("'", "''")
    query = f"SELECT * FROM c WHERE CONTAINS(LOWER(ToString(c.turns)), LOWER('{query_text}'))"

    try:
        items = list(container.query_items(query=query, enable_cross_partition_query=True))
    except exceptions.CosmosHttpResponseError as e:
        print(f"ERROR searching: {e.message}", file=sys.stderr)
        sys.exit(1)

    if not items:
        print(f"No results for: {args.query}")
        return

    print(f"Found {len(items)} session(s) matching '{args.query}':\n")
    for item in items:
        print(f"--- Session: {item.get('session_id', 'unknown')} | Agent: {item.get('agent', 'unknown')} ---")
        turns = item.get("turns", [])
        for turn in turns:
            content = turn.get("content", "")
            if args.query.lower() in content.lower():
                role = turn.get("role", "?")
                if len(content) > 300:
                    content = content[:300] + "..."
                print(f"  [{role}]: {content}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Agent memory sync for Cosmos DB")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    subparsers.add_parser("init", help="Initialize Cosmos DB database and container")

    # sync
    sync_parser = subparsers.add_parser("sync", help="Sync session turns to Cosmos DB")
    sync_parser.add_argument("--session-id", required=True, help="Session identifier")
    sync_parser.add_argument("--turns-file", required=True, help="Path to JSON file with turns")
    sync_parser.add_argument("--agent", default=None, help="Agent name")

    # rehydrate
    rehydrate_parser = subparsers.add_parser("rehydrate", help="Get recent session context")
    rehydrate_parser.add_argument("--limit", type=int, default=20, help="Max sessions to retrieve")

    # search
    search_parser = subparsers.add_parser("search", help="Search across sessions")
    search_parser.add_argument("--query", required=True, help="Search query")

    args = parser.parse_args()

    commands = {
        "init": cmd_init,
        "sync": cmd_sync,
        "rehydrate": cmd_rehydrate,
        "search": cmd_search,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
