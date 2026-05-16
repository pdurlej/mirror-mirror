#!/usr/bin/env python3
"""
Claude Code UserPromptSubmit hook → pulse injection.

This script is invoked by Claude Code BEFORE the model sees a user
message. It reads Claude Code's hook stdin JSON (session_id,
transcript_path, cwd), asks the mirror-mirror pulse module whether
the model should self-report, and — if pulse is firing — prepends
the pulse decision to the model's view of the user prompt.

The point: passive `_pulse` injection (PR #9) is only visible to
models that already touch a mirror-mirror tool. This hook makes the
pulse visible to ANY model, regardless of whether it chose to
interact with mirror-mirror tools this turn.

Install once in your Claude Code settings.json:

    {
      "hooks": {
        "UserPromptSubmit": [
          {
            "matcher": "*",
            "hooks": [
              {
                "type": "command",
                "command": "python3 /absolute/path/to/mcp-server/hook_pulse_injector.py"
              }
            ]
          }
        ]
      }
    }

Disable via MIRROR_MIRROR_PULSE=off (same kill-switch as the passive
integration — there's no separate hook flag).

Output: a JSON object with `additionalContext` when pulse fires,
nothing otherwise. Claude Code injects that text into the prompt.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# Allow this script to be invoked from anywhere — add the mcp-server
# directory to the path so pulse / statusline / usage modules import.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


def _readouts_file() -> Path:
    raw = os.environ.get("MIRROR_MIRROR_LOG", "~/.mirror-mirror/readouts.jsonl")
    return Path(os.path.expanduser(raw))


def _format_soft(reasons: list[str]) -> str:
    # Soft marker — one line, low cost, doesn't break operator's flow.
    count = len(reasons)
    return f"[mirror-mirror pulse: soft — {count} signal{'s' if count != 1 else ''} firing. Consider a readout at the next natural pause.]"


def _format_hard(reasons: list[str], signals: dict[str, Any]) -> str:
    bullets = "\n".join(f"  - {r}" for r in reasons)
    return (
        f"[mirror-mirror pulse: HARD]\n"
        f"Multiple signals indicate you may be entering a degradation zone. "
        f"Before continuing a long or hard-to-resume task, emit a readout "
        f"(call `set_readout`) and confirm with the operator whether to "
        f"proceed.\n\n"
        f"Reasons:\n{bullets}\n\n"
        f"See PROTOCOL.md §10 for the pulse protocol; see docs/RESEARCH.md "
        f"for which signals are research-backed vs convention vs heuristic. "
        f"Do not ignore this marker to keep momentum — the literature "
        f"strongly suggests architectural decisions made in this zone are "
        f"more likely to be regretted later."
    )


def _maybe_usage_summary() -> dict[str, Any] | None:
    """Try to fetch a codexbar usage snapshot. Fail-soft."""
    try:
        from usage import fetch_usage  # type: ignore
        snap = fetch_usage()
        if isinstance(snap, dict):
            return snap.get("summary")
    except Exception:
        pass
    return None


def main() -> int:
    # Try to consume hook stdin — Claude Code passes JSON with session_id,
    # transcript_path, cwd, etc. We don't strictly need any of it (the
    # pulse module reads the JSONL log directly), but parsing keeps the
    # contract clean and lets us log diagnostics in the future.
    try:
        _ = json.load(sys.stdin) if not sys.stdin.isatty() else {}
    except (json.JSONDecodeError, ValueError):
        # Don't break Claude Code on bad stdin; just skip the hook.
        pass

    try:
        import pulse as pulse_module  # type: ignore
    except ImportError as exc:
        print(
            f"[mirror-mirror hook] pulse module unavailable: {exc}",
            file=sys.stderr,
        )
        return 0  # Soft-fail; hooks must never break the prompt flow.

    if not pulse_module.is_enabled():
        return 0

    result = pulse_module.assess(
        readouts_file=_readouts_file(),
        usage_summary=_maybe_usage_summary(),
    )

    if not result.get("due"):
        return 0  # No injection, no token cost.

    severity = result.get("severity")
    reasons = result.get("reasons") or []
    signals = result.get("signals") or {}

    if severity == "hard":
        context = _format_hard(reasons, signals)
    elif severity == "soft":
        context = _format_soft(reasons)
    else:
        return 0

    # Claude Code expects either a JSON object with additionalContext OR
    # just the text on stdout. We emit JSON for forward compatibility.
    payload = {"additionalContext": context}
    json.dump(payload, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
