#!/usr/bin/env python3
"""
memory_init.py — First-time setup for repo memory.

- Creates Cosmos DB database and container (if COSMOS_DB_ENDPOINT is set)
- Creates markdown template files in the repo root (if they don't exist)
- Validates Entra ID auth (if Cosmos DB is configured)
"""

import os
import subprocess
import sys
from pathlib import Path


TEMPLATES = {
    "AGENTS.md": """# Agents

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
""",
    "STATE.md": """# Project State

## In Progress

-

## Blocked

-

## Done

-

## Session References

| Session ID | Agent | Date | Cosmos DB Thread |
|------------|-------|------|-----------------|
""",
    "DECISIONS.md": """# Decisions

Architecture Decision Records for this project.

## Session References

| Session ID | Agent | Date | Cosmos DB Thread |
|------------|-------|------|-----------------|
""",
    "CHANGELOG.md": """# Changelog

## Session References

| Session ID | Agent | Date | Cosmos DB Thread |
|------------|-------|------|-----------------|
""",
    "FAILURES.md": """# Failures & Lessons Learned

## Session References

| Session ID | Agent | Date | Cosmos DB Thread |
|------------|-------|------|-----------------|
""",
}


def find_repo_root():
    """Walk up from this script to find the repo root (where .git lives)."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    # Fallback: assume 4 levels up from scripts/
    return Path(__file__).resolve().parent.parent.parent.parent.parent


def create_templates(repo_root: Path):
    """Create markdown template files if they don't exist."""
    created = []
    for filename, content in TEMPLATES.items():
        filepath = repo_root / filename
        if not filepath.exists():
            filepath.write_text(content)
            created.append(filename)
            print(f"  Created {filename}")
        else:
            print(f"  {filename} already exists, skipping.")
    return created


def init_cosmos():
    """Initialize Cosmos DB via memory_sync.py init."""
    script_dir = Path(__file__).resolve().parent
    sync_script = script_dir / "memory_sync.py"

    result = subprocess.run(
        [sys.executable, str(sync_script), "init"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"  Cosmos DB init failed: {result.stderr.strip()}", file=sys.stderr)
        return False

    for line in result.stdout.strip().split("\n"):
        print(f"  {line}")
    return True


def main():
    repo_root = find_repo_root()
    print(f"Repo root: {repo_root}\n")

    # Step 1: Create markdown templates
    print("Creating memory files...")
    create_templates(repo_root)
    print()

    # Step 2: Initialize Cosmos DB (if configured)
    endpoint = os.environ.get("COSMOS_DB_ENDPOINT")
    if endpoint:
        print(f"Cosmos DB endpoint: {endpoint}")
        print("Initializing Cosmos DB...")
        if init_cosmos():
            print("\nSetup complete. Cosmos DB is ready.")
        else:
            print("\nSetup partially complete. Cosmos DB initialization failed.", file=sys.stderr)
            print("Memory files are ready. Fix Cosmos DB config and re-run.", file=sys.stderr)
            sys.exit(1)
    else:
        print("COSMOS_DB_ENDPOINT not set — skipping Cosmos DB setup.")
        print("Memory files are ready. Set COSMOS_DB_ENDPOINT later to enable sync.")

    print("\nDone.")


if __name__ == "__main__":
    main()
