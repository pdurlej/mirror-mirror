"""
Wall-clock awareness for mirror-mirror.

Models don't have a native real-time clock. They know training-cutoff dates
and whatever the system prompt told them, but in a long session their sense
of "what day it is" drifts toward whatever's plausible from context. This
module is a small counterweight: give the model a tool that returns hard,
external wall-clock state, and auto-attach it to every readout.

Design notes
------------
- Local-only. No subprocess, no network. Failure modes are minimal.
- Fail-soft: every helper returns None or sensible defaults rather than
  raising. The readout flow must never be blocked by clock data.
- Reads the readouts.jsonl log tail to compute `time_since_last_readout`.
  Uses the same single-pass scan as server._hydrate_from_disk.

Environment
-----------
- MIRROR_MIRROR_CLOCK    : "off" disables the integration (default: on).
                           Affects auto-enrichment of set_readout. The
                           get_session_clock tool always works regardless,
                           since pulling the clock is the operator's
                           explicit request.
- MIRROR_MIRROR_TIMEZONE : IANA timezone (e.g. "Europe/Warsaw"). When set,
                           the snapshot includes a `local` block. When unset
                           or invalid, `local` is omitted.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # pragma: no cover — Python < 3.9
    ZoneInfo = None  # type: ignore
    ZoneInfoNotFoundError = Exception  # type: ignore


_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def is_enabled() -> bool:
    """Whether auto-enrichment of set_readout should attach a clock snapshot.
    The get_session_clock tool itself ignores this flag — it's the explicit
    pull path."""
    return os.environ.get("MIRROR_MIRROR_CLOCK", "on").strip().lower() != "off"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        # Accept both "...Z" and "+00:00" forms
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def _last_readout_timestamp(readouts_file: Path) -> str | None:
    """Return the `timestamp` field of the last non-blank line of the JSONL log,
    or None if the file is missing / empty / corrupt."""
    if not readouts_file.exists():
        return None
    try:
        last_line: str | None = None
        with readouts_file.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    last_line = line
        if last_line is None:
            return None
        parsed = json.loads(last_line)
        ts = parsed.get("timestamp")
        return ts if isinstance(ts, str) else None
    except (OSError, json.JSONDecodeError):
        return None


def _humanize_seconds(seconds: float) -> str:
    """Best-effort fuzzy duration. Not localized — operators read structured
    fields for precision; this is for at-a-glance prose."""
    seconds = max(0.0, float(seconds))
    if seconds < 60:
        return "less than a minute ago"
    minutes = seconds / 60
    if minutes < 2:
        return "about 1 minute ago"
    if minutes < 60:
        return f"about {int(round(minutes))} minutes ago"
    hours = minutes / 60
    if hours < 2:
        return "about 1 hour ago"
    if hours < 24:
        return f"about {int(round(hours))} hours ago"
    days = hours / 24
    if days < 2:
        return "about 1 day ago"
    if days < 14:
        return f"about {int(round(days))} days ago"
    weeks = days / 7
    if weeks < 8:
        return f"about {int(round(weeks))} weeks ago"
    months = days / 30
    return f"about {int(round(months))} months ago"


def get_snapshot(readouts_file: Path | None = None) -> dict[str, Any]:
    """Return a wall-clock snapshot suitable for the get_session_clock tool
    and for auto-attaching to set_readout metadata.

    `readouts_file` is optional so callers without log context (pure unit
    tests, or call-sites that don't care about the elapsed-time field) can
    skip the JSONL tail-scan."""
    now = _utc_now()
    snapshot: dict[str, Any] = {
        "now_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "weekday": _WEEKDAYS[now.weekday()],
        "weekday_index": now.weekday(),  # 0 = Monday
    }

    tz_name = os.environ.get("MIRROR_MIRROR_TIMEZONE", "").strip()
    if tz_name and ZoneInfo is not None:
        try:
            local_dt = now.astimezone(ZoneInfo(tz_name))
            snapshot["local"] = {
                "iso": local_dt.isoformat(timespec="seconds"),
                "timezone": tz_name,
                "weekday": _WEEKDAYS[local_dt.weekday()],
            }
        except ZoneInfoNotFoundError:
            print(
                f"[mirror-mirror] clock: unknown timezone "
                f"'{tz_name}' (MIRROR_MIRROR_TIMEZONE); ignoring",
                file=sys.stderr,
            )

    if readouts_file is not None:
        last_ts = _last_readout_timestamp(readouts_file)
        snapshot["last_readout_timestamp"] = last_ts
        last_dt = _parse_iso(last_ts)
        if last_dt is not None:
            elapsed = (now - last_dt).total_seconds()
            snapshot["time_since_last_readout_seconds"] = round(elapsed, 1)
            snapshot["time_since_last_readout_human"] = _humanize_seconds(elapsed)
        else:
            snapshot["time_since_last_readout_seconds"] = None
            snapshot["time_since_last_readout_human"] = None

    return snapshot
