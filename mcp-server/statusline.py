"""
Claude Code statusline bridge.

Claude Code's statusline mechanism exposes per-session state — including
`session_id`, `transcript_path`, `cost.total_cost_usd`, and crucially
`context_window.used_percentage` — to a user-supplied shell command that
runs on a refresh interval (default 5s). The command receives the state
as JSON on stdin.

We exploit this to get real telemetry into the MCP server. The user
installs a small Python script (`statusline_script.py` in this
directory) that atomically writes the statusline JSON to a known path.
This module tails that path.

Design notes
------------
- Local-only, single-file state. No daemons.
- Fail-soft: missing file / stale file / corrupt JSON → return None.
  The pulse module treats absence-of-data as absence-of-signal, not as
  a fault.
- The `context_window` numbers come from Claude Code itself and are
  the highest-quality signal we get for context pressure — see
  RESEARCH.md (Domain A: long-context degradation).

Environment
-----------
- MIRROR_MIRROR_STATUSLINE_PATH : override the state file path.
  Default: ~/.cache/mirror-mirror/claude-code-status.json
- MIRROR_MIRROR_STATUSLINE_MAX_AGE_S : ignore the snapshot if older than
  this many seconds (default: 30). A stale snapshot usually means the
  user closed Claude Code or stopped the statusline refresh.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any


DEFAULT_PATH = "~/.cache/mirror-mirror/claude-code-status.json"
DEFAULT_MAX_AGE_S = 30.0


def _resolve_path() -> Path:
    raw = os.environ.get("MIRROR_MIRROR_STATUSLINE_PATH", DEFAULT_PATH)
    return Path(os.path.expanduser(raw))


def _resolve_max_age() -> float:
    raw = os.environ.get("MIRROR_MIRROR_STATUSLINE_MAX_AGE_S")
    if not raw:
        return DEFAULT_MAX_AGE_S
    try:
        return max(0.0, float(raw))
    except ValueError:
        return DEFAULT_MAX_AGE_S


def read_snapshot() -> dict[str, Any] | None:
    """Return the most recent statusline JSON, or None if unavailable.

    Returns None when:
    - the state file does not exist (user hasn't set up the statusline)
    - the snapshot is older than MIRROR_MIRROR_STATUSLINE_MAX_AGE_S
    - the file is unreadable or not valid JSON
    """
    path = _resolve_path()
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"[mirror-mirror] statusline: unreadable {path}: {exc}",
            file=sys.stderr,
        )
        return None

    if not isinstance(data, dict):
        return None

    written_at = data.get("ts")
    if isinstance(written_at, (int, float)):
        age = time.time() - float(written_at)
        if age > _resolve_max_age():
            return None

    return data


def context_window_pct(snapshot: dict[str, Any] | None) -> float | None:
    """Extract context window utilisation percent (0.0-100.0) from a
    statusline snapshot, or None if unavailable.

    Claude Code v2.1.132+ exposes this under context_window.used_percentage.
    Older versions may expose only the raw token totals — we fall back to
    a ratio when both are present.
    """
    if not isinstance(snapshot, dict):
        return None
    cw = snapshot.get("context_window")
    if not isinstance(cw, dict):
        return None

    pct = cw.get("used_percentage")
    if isinstance(pct, (int, float)):
        return float(pct)

    # Older shape: derive from totals if both are exposed.
    input_tokens = cw.get("total_input_tokens")
    limit = cw.get("limit") or cw.get("max_tokens") or cw.get("total")
    if isinstance(input_tokens, (int, float)) and isinstance(limit, (int, float)) and limit > 0:
        return float(input_tokens) / float(limit) * 100.0

    return None


def session_id(snapshot: dict[str, Any] | None) -> str | None:
    if not isinstance(snapshot, dict):
        return None
    sid = snapshot.get("session_id")
    return sid if isinstance(sid, str) else None


def total_cost_usd(snapshot: dict[str, Any] | None) -> float | None:
    if not isinstance(snapshot, dict):
        return None
    cost = snapshot.get("cost")
    if isinstance(cost, dict):
        v = cost.get("total_cost_usd")
        if isinstance(v, (int, float)):
            return float(v)
    return None
