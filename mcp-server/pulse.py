"""
Pulse — passive event-driven trigger for emitting a fresh readout.

The pulse module aggregates four signals into a single decision:

1. Activity     — MCP tool calls since the last readout
2. Context     — context_window.used_percentage from Claude Code statusline
3. Quota       — codexbar 5h / weekly window utilisation
4. Time        — wall-clock seconds since the last readout (fallback)

Each signal has a soft and a hard threshold. The aggregate severity is
the maximum severity across the four — if any one signal is hard, the
pulse is hard. If any is soft (and none is hard), the pulse is soft.
Otherwise none.

Output is a dict ready to be embedded in any tool response as a
`_pulse` field, so the model sees it on every interaction with a
mirror-mirror tool.

See docs/RESEARCH.md for the literature grounding behind every default.
Bottom line:

- Activity (8 / 24) and context (15% / 25%) are research-backed
  (Reflexion 2023; BABILong 2024; NoLiMa 2025; Liu 2023; Chroma 2025).
- Quota (70% / 90%) is operations convention (AWS recommended alarms),
  not empirically validated for LLM users.
- Time (30 / 60 min) is a pure heuristic; no literature supports
  wall-clock periodicity for agent reflection. Kept as a safety net
  for idle sessions.

Environment
-----------
MIRROR_MIRROR_PULSE                       — "off" disables. Default: on.
MIRROR_MIRROR_PULSE_TOOLCALL_SOFT         — default 8
MIRROR_MIRROR_PULSE_TOOLCALL_HARD         — default 24
MIRROR_MIRROR_PULSE_CONTEXT_PCT_SOFT      — default 15.0
MIRROR_MIRROR_PULSE_CONTEXT_PCT_HARD      — default 25.0
MIRROR_MIRROR_PULSE_QUOTA_SOFT            — default 70.0
MIRROR_MIRROR_PULSE_QUOTA_HARD            — default 90.0
MIRROR_MIRROR_PULSE_TIME_SOFT_MIN         — default 30
MIRROR_MIRROR_PULSE_TIME_HARD_MIN         — default 60
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Literal

import statusline as statusline_module


Severity = Literal["none", "soft", "hard"]


# Module-level activity counter. Incremented on every mirror-mirror tool
# call from server.call_tool; reset whenever a readout is persisted.
_activity_since_last_readout: int = 0


def increment_activity() -> int:
    """Called by server.call_tool on every tool invocation. Returns the
    new count for convenience (mostly for tests / logging)."""
    global _activity_since_last_readout
    _activity_since_last_readout += 1
    return _activity_since_last_readout


def reset_activity() -> None:
    """Called whenever a new readout is persisted."""
    global _activity_since_last_readout
    _activity_since_last_readout = 0


def get_activity_count() -> int:
    return _activity_since_last_readout


def is_enabled() -> bool:
    return os.environ.get("MIRROR_MIRROR_PULSE", "on").strip().lower() != "off"


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _max_severity(*levels: Severity) -> Severity:
    if "hard" in levels:
        return "hard"
    if "soft" in levels:
        return "soft"
    return "none"


def _activity_severity(count: int) -> tuple[Severity, str | None]:
    soft = _env_int("MIRROR_MIRROR_PULSE_TOOLCALL_SOFT", 8)
    hard = _env_int("MIRROR_MIRROR_PULSE_TOOLCALL_HARD", 24)
    if count >= hard:
        return "hard", (
            f"{count} mirror-mirror tool calls since last readout "
            f"(hard threshold: {hard}; Reflexion 2023 reports 30 actions "
            f"as 'inefficient planning' bound)"
        )
    if count >= soft:
        return "soft", (
            f"{count} mirror-mirror tool calls since last readout "
            f"(soft threshold: {soft}; early warning at 1/4 of Reflexion's "
            f"30-action bound)"
        )
    return "none", None


def _context_severity(pct: float | None) -> tuple[Severity, str | None]:
    if pct is None:
        return "none", None
    soft = _env_float("MIRROR_MIRROR_PULSE_CONTEXT_PCT_SOFT", 15.0)
    hard = _env_float("MIRROR_MIRROR_PULSE_CONTEXT_PCT_HARD", 25.0)
    if pct >= hard:
        return "hard", (
            f"context window at {pct:.1f}% used (hard threshold: {hard}%; "
            f"BABILong 2024: effective context typically 10-20%; "
            f"NoLiMa 2025: effective length << advertised window)"
        )
    if pct >= soft:
        return "soft", (
            f"context window at {pct:.1f}% used (soft threshold: {soft}%; "
            f"early warning before BABILong's documented degradation zone)"
        )
    return "none", None


def _quota_severity(usage_summary: dict[str, Any] | None) -> tuple[Severity, str | None]:
    if not usage_summary:
        return "none", None
    soft = _env_float("MIRROR_MIRROR_PULSE_QUOTA_SOFT", 70.0)
    hard = _env_float("MIRROR_MIRROR_PULSE_QUOTA_HARD", 90.0)
    pcts: list[tuple[str, float]] = []
    for key in ("window_5h_pct", "window_weekly_pct"):
        v = usage_summary.get(key)
        if isinstance(v, (int, float)):
            pcts.append((key, float(v)))
    if not pcts:
        return "none", None
    label, peak = max(pcts, key=lambda kv: kv[1])
    if peak >= hard:
        return "hard", (
            f"peak quota window {label}={peak:.0f}% "
            f"(hard threshold: {hard}%; ops convention, not empirically "
            f"validated for LLM users)"
        )
    if peak >= soft:
        return "soft", (
            f"peak quota window {label}={peak:.0f}% "
            f"(soft threshold: {soft}%; ops convention, AWS recommended alarms)"
        )
    return "none", None


def _time_severity(last_readout_ts: str | None) -> tuple[Severity, str | None]:
    if not last_readout_ts:
        return "none", None
    try:
        if last_readout_ts.endswith("Z"):
            last_readout_ts = last_readout_ts[:-1] + "+00:00"
        last_dt = datetime.fromisoformat(last_readout_ts)
    except (ValueError, TypeError):
        return "none", None
    elapsed_s = (datetime.now(timezone.utc) - last_dt).total_seconds()
    elapsed_min = elapsed_s / 60.0

    soft_min = _env_int("MIRROR_MIRROR_PULSE_TIME_SOFT_MIN", 30)
    hard_min = _env_int("MIRROR_MIRROR_PULSE_TIME_HARD_MIN", 60)
    if elapsed_min >= hard_min:
        return "hard", (
            f"{elapsed_min:.0f} minutes since last readout "
            f"(hard threshold: {hard_min}m; fail-safe heuristic, "
            f"no research basis for wall-clock periodicity)"
        )
    if elapsed_min >= soft_min:
        return "soft", (
            f"{elapsed_min:.0f} minutes since last readout "
            f"(soft threshold: {soft_min}m; fail-safe heuristic)"
        )
    return "none", None


def _last_readout_timestamp_from_disk(readouts_file_path: Any) -> str | None:
    """Cheap reader: just need the last timestamp, not the whole record."""
    import json
    from pathlib import Path

    path = Path(readouts_file_path) if not isinstance(readouts_file_path, Path) else readouts_file_path
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            last_line: str | None = None
            for line in f:
                if line.strip():
                    last_line = line
        if last_line is None:
            return None
        return json.loads(last_line).get("timestamp")
    except (OSError, json.JSONDecodeError):
        return None


def assess(
    *,
    readouts_file: Any,
    usage_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute the current pulse state. Returns a dict with `due` (bool),
    `severity` ("none"|"soft"|"hard"), `reasons` (list of strings), and
    `signals` (per-signal breakdown for debugging / calibration analysis).

    Always safe to call. If pulse is disabled via env var, returns a
    minimal `{"due": false, "severity": "none", "reasons": [], "enabled": false}`.
    """
    if not is_enabled():
        return {"due": False, "severity": "none", "reasons": [], "enabled": False}

    activity_count = get_activity_count()
    statusline_snap = statusline_module.read_snapshot()
    context_pct = statusline_module.context_window_pct(statusline_snap)
    last_ts = _last_readout_timestamp_from_disk(readouts_file)

    activity = _activity_severity(activity_count)
    context = _context_severity(context_pct)
    quota = _quota_severity(usage_summary)
    time_sig = _time_severity(last_ts)

    severity = _max_severity(activity[0], context[0], quota[0], time_sig[0])
    reasons = [r for _, r in (activity, context, quota, time_sig) if r]

    return {
        "due": severity != "none",
        "severity": severity,
        "reasons": reasons,
        "enabled": True,
        "signals": {
            "activity": {"severity": activity[0], "count": activity_count},
            "context": {
                "severity": context[0],
                "context_window_pct": context_pct,
                "from_statusline": statusline_snap is not None,
            },
            "quota": {"severity": quota[0]},
            "time": {
                "severity": time_sig[0],
                "last_readout_timestamp": last_ts,
            },
        },
    }
