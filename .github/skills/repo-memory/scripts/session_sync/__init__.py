"""Session sync adapter registry.

Provides auto-detection and manual selection of platform adapters.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .base import SessionAdapter, SessionInfo  # noqa: F401
from .openclaw import OpenClawAdapter
from .claude_code import ClaudeCodeAdapter
from .copilot import CopilotAdapter
from .cursor import CursorAdapter
from .codex import CodexAdapter

# Canonical adapter instances keyed by platform name.
# OpenClaw is first in detection order — if running inside OpenClaw, prefer it.
_ADAPTERS: Dict[str, SessionAdapter] = {
    "openclaw": OpenClawAdapter(),
    "claude-code": ClaudeCodeAdapter(),
    "copilot": CopilotAdapter(),
    "cursor": CursorAdapter(),
    "codex": CodexAdapter(),
}


def list_adapters() -> List[str]:
    """Return all registered adapter platform names."""
    return list(_ADAPTERS.keys())


def get_adapter(platform: Optional[str] = None) -> SessionAdapter:
    """Return an adapter by name, or auto-detect the first available platform.

    Args:
        platform: Explicit platform name (e.g. "claude-code"). If None,
                  tries each adapter's detect() and returns the first hit.

    Raises:
        ValueError: If the platform name is unknown.
        RuntimeError: If auto-detect finds no installed platform.
    """
    if platform is not None:
        if platform not in _ADAPTERS:
            raise ValueError(
                f"Unknown platform '{platform}'. Available: {list_adapters()}"
            )
        return _ADAPTERS[platform]

    # Auto-detect: try each adapter in priority order
    for adapter in _ADAPTERS.values():
        try:
            if adapter.detect():
                return adapter
        except Exception:
            continue

    raise RuntimeError(
        "No supported coding agent platform detected on this machine. "
        f"Checked: {list_adapters()}"
    )
