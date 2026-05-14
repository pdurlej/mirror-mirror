"""
codexbar usage integration.

Reads provider rate-limit / quota status (5-hour sliding window, weekly cap)
from the codexbar CLI and exposes it in a stable shape for the readout layer.

Design notes
------------
- Fail-soft by default. If codexbar is missing, returns an error code, fails
  to decode its own config, or just times out — we log to stderr and return
  None. The readout flow is never blocked by usage telemetry.
- Pass through the raw codexbar JSON so future analyses can recompute
  whatever derived shape they want.
- Add a small `summary` dict on top with best-effort percentage extraction.
  The exact codexbar JSON shape varies by provider, so the summary is
  intentionally lossy and tagged with `extracted_from_keys` so consumers
  know which keys were found.

Environment
-----------
- MIRROR_MIRROR_USAGE      : "off" disables the integration (default: on)
- MIRROR_MIRROR_USAGE_CMD  : override the command (default: "codexbar usage --json")
                             Mostly for tests; a JSON-producing stub works.
- MIRROR_MIRROR_USAGE_PROVIDER : codexbar --provider arg (default: "claude")
- MIRROR_MIRROR_USAGE_TIMEOUT  : seconds, default 4.0
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from typing import Any


DEFAULT_CMD = "codexbar usage --json"
DEFAULT_PROVIDER = "claude"
DEFAULT_TIMEOUT_S = 4.0

WARN_THRESHOLD_PCT = 70.0
CRITICAL_THRESHOLD_PCT = 90.0


def is_enabled() -> bool:
    return os.environ.get("MIRROR_MIRROR_USAGE", "on").strip().lower() != "off"


def _resolve_command() -> list[str]:
    raw = os.environ.get("MIRROR_MIRROR_USAGE_CMD", DEFAULT_CMD).strip()
    cmd = shlex.split(raw)

    # Append --provider unless the user already passed one in MIRROR_MIRROR_USAGE_CMD.
    if "--provider" not in cmd:
        provider = os.environ.get("MIRROR_MIRROR_USAGE_PROVIDER", DEFAULT_PROVIDER)
        cmd += ["--provider", provider]

    return cmd


def _resolve_timeout() -> float:
    raw = os.environ.get("MIRROR_MIRROR_USAGE_TIMEOUT")
    if not raw:
        return DEFAULT_TIMEOUT_S
    try:
        return float(raw)
    except ValueError:
        return DEFAULT_TIMEOUT_S


def _summarize(payload: Any) -> dict[str, Any]:
    """Best-effort percentage extraction from a codexbar payload.

    Supports three shapes:

    1) **Real codexbar shape** (the one we actually see in production):
       a list with `[{usage: {primary, secondary, tertiary}}]` where each
       sub-block has `windowMinutes` + `usedPercent`. We classify by
       `windowMinutes`: 300 → 5-hour, 10080 → weekly. When multiple weekly
       windows exist (Claude Max has both a Sonnet-weighted weekly and an
       Opus-weighted weekly), we take the max — peak weekly pressure is
       what matters operationally.

    2) Top-level dict with explicit `window_5h` / `window_weekly` keys
       (synthetic shape, useful for tests and other providers).

    3) `usage.{five_hour_used_pct, weekly_used_pct}` flat shape.

    Anything we can't recognise is left out; the raw payload is always
    preserved elsewhere so consumers can do their own parsing.
    """
    summary: dict[str, Any] = {"extracted_from_keys": []}

    candidates: list[dict[str, Any]] = []
    if isinstance(payload, list):
        candidates.extend(c for c in payload if isinstance(c, dict))
    elif isinstance(payload, dict):
        candidates.append(payload)

    for cand in candidates:
        # Shape 1 — real codexbar
        usage_block = cand.get("usage")
        if isinstance(usage_block, dict):
            weekly_pcts: list[float] = []
            for slot_name in ("primary", "secondary", "tertiary"):
                slot = usage_block.get(slot_name)
                if not isinstance(slot, dict):
                    continue
                pct = slot.get("usedPercent")
                minutes = slot.get("windowMinutes")
                if not isinstance(pct, (int, float)):
                    continue
                pct = float(pct)
                # ~5 hours = 300 minutes; tolerate 270-360 for safety
                if isinstance(minutes, (int, float)) and 270 <= minutes <= 360:
                    if "window_5h_pct" not in summary or pct > summary["window_5h_pct"]:
                        summary["window_5h_pct"] = pct
                        summary["extracted_from_keys"].append(f"usage.{slot_name}.5h")
                # ~1 week = 10080 minutes
                elif isinstance(minutes, (int, float)) and 9000 <= minutes <= 11000:
                    weekly_pcts.append(pct)
                    summary["extracted_from_keys"].append(f"usage.{slot_name}.weekly")
            if weekly_pcts:
                summary["window_weekly_pct"] = max(weekly_pcts)

            # Flat shape inside usage block (Shape 3)
            if "five_hour_used_pct" in usage_block and "window_5h_pct" not in summary:
                summary["window_5h_pct"] = float(usage_block["five_hour_used_pct"])
                summary["extracted_from_keys"].append("usage.five_hour_used_pct")
            if "weekly_used_pct" in usage_block and "window_weekly_pct" not in summary:
                summary["window_weekly_pct"] = float(usage_block["weekly_used_pct"])
                summary["extracted_from_keys"].append("usage.weekly_used_pct")

        # Shape 2 — synthetic test/other-provider top-level keys
        if "window_5h_pct" not in summary:
            for key in ("window_5h", "five_hour", "rolling_5h", "session"):
                v = cand.get(key)
                if isinstance(v, dict):
                    pct = _find_pct(v)
                    if pct is not None:
                        summary["window_5h_pct"] = pct
                        summary["extracted_from_keys"].append(key)
                        break

        if "window_weekly_pct" not in summary:
            for key in ("window_weekly", "weekly", "week"):
                v = cand.get(key)
                if isinstance(v, dict):
                    pct = _find_pct(v)
                    if pct is not None:
                        summary["window_weekly_pct"] = pct
                        summary["extracted_from_keys"].append(key)
                        break

    return summary


def _find_pct(block: dict[str, Any]) -> float | None:
    for key in ("used_pct", "percent_used", "percentage", "pct"):
        if key in block:
            try:
                return float(block[key])
            except (TypeError, ValueError):
                continue
    used = block.get("used")
    limit = block.get("limit") or block.get("total") or block.get("cap")
    if used is not None and limit:
        try:
            return float(used) / float(limit) * 100.0
        except (TypeError, ValueError, ZeroDivisionError):
            return None
    return None


def fetch_usage() -> dict[str, Any] | None:
    """Run codexbar (or the override command), parse JSON, return a structured
    snapshot. Returns None on any failure (and writes a warning to stderr)."""
    if not is_enabled():
        return None

    cmd = _resolve_command()
    timeout = _resolve_timeout()

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        print(
            f"[mirror-mirror] usage: command not found: {cmd[0]} "
            f"(disable with MIRROR_MIRROR_USAGE=off)",
            file=sys.stderr,
        )
        return None
    except subprocess.TimeoutExpired:
        print(
            f"[mirror-mirror] usage: {cmd[0]} timed out after {timeout}s",
            file=sys.stderr,
        )
        return None
    except OSError as exc:
        print(f"[mirror-mirror] usage: subprocess failed: {exc}", file=sys.stderr)
        return None

    if not proc.stdout.strip():
        print(
            f"[mirror-mirror] usage: empty stdout from {cmd[0]} "
            f"(exit={proc.returncode}); stderr={proc.stderr.strip()[:200]}",
            file=sys.stderr,
        )
        return None

    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        print(
            f"[mirror-mirror] usage: could not parse JSON from {cmd[0]}: {exc}",
            file=sys.stderr,
        )
        return None

    # codexbar emits error objects inline; surface them but don't pretend it worked.
    error: dict[str, Any] | None = None
    if isinstance(payload, list):
        for entry in payload:
            if isinstance(entry, dict) and isinstance(entry.get("error"), dict):
                error = entry["error"]
                break

    summary = _summarize(payload)

    return {
        "source": cmd[0],
        "ok": error is None,
        "error": error,
        "summary": summary,
        "raw": payload,
    }


def quota_pressure_flag(snapshot: dict[str, Any] | None) -> str | None:
    """Return an epistemic_flag string when quota pressure is high enough that
    operators should know it may affect session continuity, or None otherwise."""
    if not snapshot or not snapshot.get("ok"):
        return None
    summary = snapshot.get("summary") or {}
    pcts: list[float] = []
    for k in ("window_5h_pct", "window_weekly_pct"):
        v = summary.get(k)
        if isinstance(v, (int, float)):
            pcts.append(float(v))
    if not pcts:
        return None
    peak = max(pcts)
    if peak >= CRITICAL_THRESHOLD_PCT:
        return (
            f"quota pressure may affect session continuity "
            f"(peak window usage ~{peak:.0f}% — critical)"
        )
    if peak >= WARN_THRESHOLD_PCT:
        return (
            f"quota pressure may affect session continuity "
            f"(peak window usage ~{peak:.0f}%)"
        )
    return None
