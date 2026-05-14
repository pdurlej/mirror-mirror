#!/usr/bin/env python3
"""
Statusline script for Claude Code → mirror-mirror bridge.

Install once in your Claude Code settings.json:

    {
      "statusLine": {
        "type": "command",
        "command": "python3 /absolute/path/to/mcp-server/statusline_script.py",
        "refreshInterval": 5
      }
    }

What it does:

1. Reads the Claude Code statusline JSON from stdin
2. Atomically writes a snapshot to ~/.cache/mirror-mirror/claude-code-status.json
   (or the path in MIRROR_MIRROR_STATUSLINE_PATH)
3. Prints a one-line summary back to Claude Code's status bar

If you already have a custom statusline command, wrap your existing one
around this rather than replacing it — this script is intentionally
small and pipe-friendly.
"""

import json
import os
import pathlib
import sys
import tempfile
import time


DEFAULT_PATH = "~/.cache/mirror-mirror/claude-code-status.json"


def _resolve_path() -> pathlib.Path:
    raw = os.environ.get("MIRROR_MIRROR_STATUSLINE_PATH", DEFAULT_PATH)
    return pathlib.Path(raw).expanduser()


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        # Claude Code probably ran us without stdin; just exit quietly.
        return 0

    state_path = _resolve_path()
    state_path.parent.mkdir(parents=True, exist_ok=True)

    snapshot = {
        "ts": time.time(),
        "session_id": data.get("session_id"),
        "transcript_path": data.get("transcript_path"),
        "cwd": data.get("cwd"),
        "workspace": data.get("workspace"),
        "model": data.get("model"),
        "cost": data.get("cost"),
        "context_window": data.get("context_window"),
        "version": data.get("version"),
    }

    # Atomic write — rename is atomic on POSIX, so readers never see a half-written file.
    fd, tmp = tempfile.mkstemp(
        dir=str(state_path.parent),
        prefix=state_path.name + ".",
        text=True,
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(snapshot, f, separators=(",", ":"))
            f.write("\n")
        os.replace(tmp, state_path)
    except OSError as exc:
        # Don't break Claude Code's statusline if disk is full / permissions / etc.
        try:
            os.unlink(tmp)
        except OSError:
            pass
        print(f"mirror-mirror statusline write failed: {exc}", file=sys.stderr)

    # Echo a useful line back to Claude Code's status bar.
    cw = snapshot.get("context_window") or {}
    pct = cw.get("used_percentage")
    cost = (snapshot.get("cost") or {}).get("total_cost_usd")
    model = ((snapshot.get("model") or {}).get("display_name")) or "Claude"

    pct_str = f"ctx={pct:.0f}%" if isinstance(pct, (int, float)) else "ctx=?"
    cost_str = f"${cost:.4f}" if isinstance(cost, (int, float)) else "$?"

    print(f"{model} {pct_str} {cost_str}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
