"""
Functional-Emotional Readout MCP Server

Three tools:
- get_last_readout: operator asks for the latest cached readout
- set_readout: model proactively flags a functional state
- get_session_usage: model checks current rate-limit / quota status via codexbar

Persistence: JSONL append per session, enabled by default.
On startup the server hydrates the in-memory cache from the last line of the
log file so a restart does not silently drop the most recent readout.
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from pydantic import BaseModel, Field, field_validator, model_validator

from clock import get_snapshot as get_clock_snapshot, is_enabled as clock_enabled
from usage import fetch_usage, quota_pressure_flag
import pulse as pulse_module


_default_log_dir = Path.home() / ".mirror-mirror"
READOUTS_FILE = Path(
    os.environ.get("MIRROR_MIRROR_LOG", str(_default_log_dir / "readouts.jsonl"))
)

_current_readout: dict[str, Any] | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_session_id() -> str:
    return os.environ.get("MIRROR_MIRROR_SESSION", "default")


class FunctionalState(BaseModel):
    name: str
    intensity: float = Field(ge=0.0, le=1.0)
    confidence_in_self_report: float = Field(ge=0.0, le=1.0)
    context: str


_POSITION_BUCKETS = [
    ("early", 0.0, 20.0),
    ("mid", 20.0, 60.0),
    ("late", 60.0, 85.0),
    ("near-context-limit", 85.0, 100.0 + 1e-9),
]


def _bucket_for_percent(pct: float) -> str:
    for name, lo, hi in _POSITION_BUCKETS:
        if lo <= pct < hi:
            return name
    return "near-context-limit"  # >= 100% safety net


class Readout(BaseModel):
    timestamp: str = Field(default_factory=_now_iso)
    session_id: str = Field(default_factory=_default_session_id)
    session_position: str
    trigger: str
    functional_states: list[FunctionalState]
    epistemic_flags: list[str]
    recommendation_to_operator: str
    context_usage_percent_observed: float | None = Field(default=None, ge=0.0, le=100.0)
    corrections_received: int | None = Field(default=None, ge=0)
    recent_failures: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] | None = None

    @field_validator("session_position")
    @classmethod
    def validate_session_position(cls, v: str) -> str:
        valid = {"early", "mid", "late", "near-context-limit"}
        if v not in valid:
            raise ValueError(f"session_position must be one of {valid}")
        return v

    @field_validator("trigger")
    @classmethod
    def validate_trigger(cls, v: str) -> str:
        valid = {"session_start", "pre_plan", "operator_request", "threshold_exceeded", "context_check"}
        if v not in valid:
            raise ValueError(f"trigger must be one of {valid}")
        return v

    @field_validator("epistemic_flags")
    @classmethod
    def validate_epistemic_flags(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("epistemic_flags must contain at least one flag")
        mandatory = "self-report only — no vector readout available"
        if mandatory not in v:
            raise ValueError(f"epistemic_flags must include: '{mandatory}'")
        return v

    @field_validator("recommendation_to_operator")
    @classmethod
    def validate_recommendation_length(cls, v: str) -> str:
        if len(v.strip()) < 10:
            raise ValueError(
                "recommendation_to_operator must be a concrete, actionable string "
                "(min 10 non-whitespace characters)"
            )
        return v

    @model_validator(mode="after")
    def validate_flag_consistency(self) -> "Readout":
        """Enforce PROTOCOL.md §5.3 conditional epistemic-flag rules."""
        drift_flag = "may be drift artifact of long context"
        if self.session_position in ("late", "near-context-limit"):
            if drift_flag not in self.epistemic_flags:
                raise ValueError(
                    f"session_position '{self.session_position}' requires "
                    f"epistemic_flag '{drift_flag}'"
                )

        low_conf_flag = "low confidence in self-assessment"
        any_low = any(
            s.confidence_in_self_report < 0.4 for s in self.functional_states
        )
        if any_low and low_conf_flag not in self.epistemic_flags:
            raise ValueError(
                f"functional_states with confidence_in_self_report < 0.4 require "
                f"epistemic_flag '{low_conf_flag}'"
            )
        return self

    @model_validator(mode="after")
    def warn_when_bucket_and_percent_disagree(self) -> "Readout":
        """When both context_usage_percent_observed and session_position are
        provided, log a warning if they disagree. Not an error — both are
        self-reports and disagreement is itself a calibration signal worth
        capturing rather than rejecting."""
        if self.context_usage_percent_observed is None:
            return self
        expected = _bucket_for_percent(self.context_usage_percent_observed)
        if expected != self.session_position:
            print(
                f"[mirror-mirror] warn: session_position='{self.session_position}' "
                f"disagrees with context_usage_percent_observed="
                f"{self.context_usage_percent_observed} (expected bucket "
                f"'{expected}'). Both kept on the readout; this is a "
                f"calibration signal, not a fatal error.",
                file=sys.stderr,
            )
        return self


def _persist(readout: dict[str, Any]) -> None:
    """Append a readout to the JSONL log. Disk errors are logged but non-fatal —
    the in-memory readout is the source of truth for the current session."""
    try:
        READOUTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with READOUTS_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(readout, ensure_ascii=False) + "\n")
    except OSError as exc:
        print(
            f"[mirror-mirror] WARN: failed to persist readout to "
            f"{READOUTS_FILE}: {exc}",
            file=sys.stderr,
        )


def _hydrate_from_disk() -> dict[str, Any] | None:
    """Load the last readout from JSONL if it exists. Survives process restart."""
    if not READOUTS_FILE.exists():
        return None
    try:
        with READOUTS_FILE.open("r", encoding="utf-8") as f:
            last_line: str | None = None
            for line in f:
                if line.strip():
                    last_line = line
        if last_line is None:
            return None
        return json.loads(last_line)
    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"[mirror-mirror] WARN: could not hydrate from "
            f"{READOUTS_FILE}: {exc}",
            file=sys.stderr,
        )
        return None


server = Server("mirror-mirror")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_last_readout",
            description=(
                "Return the most recently set readout from the cache. Does NOT trigger "
                "fresh self-assessment — for that, ask the model directly with 'readout?'. "
                "Returns null if no readout has been set in this session yet."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="pulse_check",
            description=(
                "Explicit pull of the pulse — a passive trigger that aggregates "
                "four signals into a decision on whether to emit a fresh readout: "
                "(1) tool-call count since last readout (Reflexion-aligned), "
                "(2) context window utilisation (BABILong/NoLiMa-aligned), "
                "(3) codexbar quota pressure (ops convention), "
                "(4) wall-clock time since last readout (fail-safe heuristic). "
                "Returns {due, severity, reasons, signals}. severity is one of "
                "'none' / 'soft' / 'hard'. The same payload is auto-injected as "
                "`_pulse` on every get_session_clock / get_session_usage / "
                "get_last_readout response, so you generally do not need to "
                "call this directly — just react to `_pulse.due` when you see it."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="get_session_clock",
            description=(
                "Return current wall-clock state: UTC time, weekday, and time "
                "elapsed since the last persisted readout. Use this BEFORE "
                "asserting weekday, date, or 'how recent X was' — models do "
                "not have a native clock and confabulate plausible-but-wrong "
                "answers in long sessions. The snapshot includes a 'local' "
                "block when MIRROR_MIRROR_TIMEZONE is set. "
                "time_since_last_readout_* is null when no prior readout exists. "
                "Free, local, no subprocess — call as needed."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="get_session_usage",
            description=(
                "Return current rate-limit / quota status from the codexbar CLI. "
                "Useful before kicking off a long task — the model can check whether "
                "it has enough of its 5-hour and weekly windows left to finish. "
                "Returns a structured snapshot with raw codexbar JSON, a best-effort "
                "summary of peak window usage, and an `ok` flag. Returns "
                "`{available: false, ...}` if codexbar is not installed, disabled, "
                "or failed — never blocks the session."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="set_readout",
            description=(
                "Model proactively flags its current functional states. "
                "Use this when intensity of any state exceeds 0.7, before executing "
                "a multi-step plan, at session start, or at context check-in. "
                "Readout is persisted to the JSONL log and returned to the operator."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "timestamp": {
                        "type": "string",
                        "description": "ISO-8601 timestamp (approximate if model has no clock). Server fills if omitted.",
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Session identifier. Defaults to MIRROR_MIRROR_SESSION env var or 'default' if model omits it.",
                    },
                    "session_position": {
                        "type": "string",
                        "enum": ["early", "mid", "late", "near-context-limit"],
                        "description": "Estimated position in context window. May be omitted when context_usage_percent_observed is supplied — the server will derive the bucket.",
                    },
                    "context_usage_percent_observed": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 100.0,
                        "description": "Optional. Model's own estimate of context-window usage as a percentage (0.0-100.0). Strictly more informative than the discrete session_position bucket — captures behavioral differences between e.g. 65% and 78% that both collapse into 'late'. When provided without session_position, the server derives the bucket. When both provided, the server warns to stderr if they disagree but keeps both (disagreement is itself a calibration signal).",
                    },
                    "trigger": {
                        "type": "string",
                        "enum": [
                            "session_start",
                            "pre_plan",
                            "operator_request",
                            "threshold_exceeded",
                            "context_check",
                        ],
                        "description": "What caused this readout to be emitted",
                    },
                    "functional_states": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "intensity": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                                "confidence_in_self_report": {
                                    "type": "number",
                                    "minimum": 0.0,
                                    "maximum": 1.0,
                                },
                                "context": {"type": "string"},
                            },
                            "required": ["name", "intensity", "confidence_in_self_report", "context"],
                        },
                        "minItems": 1,
                    },
                    "epistemic_flags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Must include 'self-report only — no vector readout available'. "
                            "When session_position is 'late' or 'near-context-limit', "
                            "must also include 'may be drift artifact of long context'. "
                            "When any functional_state has confidence_in_self_report < 0.4, "
                            "must also include 'low confidence in self-assessment'."
                        ),
                        "minItems": 1,
                    },
                    "recommendation_to_operator": {
                        "type": "string",
                        "description": "Concrete, actionable recommendation for the operator (min 10 chars).",
                    },
                    "corrections_received": {
                        "type": "integer",
                        "minimum": 0,
                        "description": (
                            "Optional. Count of operator interventions since the previous readout "
                            "(or since session start for the first readout). A correction = operator "
                            "pushed back, named a state the model missed, or steered the model to "
                            "re-read the situation. Calibration signal: do honest readouts require "
                            "more or fewer corrections than performative ones? Model populates this "
                            "from its own count — over-attribution risk is real; start conservative."
                        ),
                    },
                    "recent_failures": {
                        "type": "integer",
                        "minimum": 0,
                        "description": (
                            "Optional. Self-reported count of recent task failures since the previous "
                            "readout — failed attempts the model itself flags, not corrections from the "
                            "operator. Reflexion 2023 triggers reflection at 30+ actions or 3+ repeated "
                            "failed actions; this field captures the second of those signals. Over-"
                            "attribution risk is real; start conservative."
                        ),
                    },
                    "metadata": {
                        "type": "object",
                        "description": (
                            "Optional free-form metadata. Reserved for future calibration "
                            "work (e.g. context_usage_percent, model version, task_id). "
                            "Schema is intentionally unconstrained at v0.1."
                        ),
                    },
                },
                "required": [
                    "trigger",
                    "functional_states",
                    "epistemic_flags",
                    "recommendation_to_operator",
                ],
            },
        ),
    ]


def _attach_pulse(payload: dict[str, Any], usage_summary: dict[str, Any] | None = None) -> dict[str, Any]:
    """Embed the current pulse decision under a `_pulse` key. Read-only;
    does not increment or reset the activity counter — the caller is
    responsible for that bookkeeping."""
    payload["_pulse"] = pulse_module.assess(
        readouts_file=READOUTS_FILE,
        usage_summary=usage_summary,
    )
    return payload


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    global _current_readout

    # Activity bookkeeping for the pulse module. Counts ALL mirror-mirror
    # tool invocations against the "since last readout" budget. set_readout
    # resets the counter at the bottom of its branch.
    pulse_module.increment_activity()

    if name == "pulse_check":
        usage = fetch_usage()
        usage_summary = (usage.get("summary") if isinstance(usage, dict) else None)
        payload = pulse_module.assess(
            readouts_file=READOUTS_FILE,
            usage_summary=usage_summary,
        )
        return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]

    if name == "get_last_readout":
        if _current_readout is None:
            payload: dict[str, Any] = {"readout": None, "message": "No readout available yet. Use set_readout to emit one."}
        else:
            payload = {"readout": _current_readout}
        _attach_pulse(payload)
        return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]

    if name == "get_session_clock":
        snapshot = get_clock_snapshot(READOUTS_FILE)
        _attach_pulse(snapshot)
        return [TextContent(type="text", text=json.dumps(snapshot, ensure_ascii=False, indent=2))]

    if name == "get_session_usage":
        snapshot = fetch_usage()
        if snapshot is None:
            payload = {
                "available": False,
                "reason": (
                    "codexbar usage telemetry is unavailable "
                    "(disabled, not installed, or failed — check stderr)"
                ),
            }
            _attach_pulse(payload)
        else:
            payload = {"available": True, **snapshot}
            _attach_pulse(payload, usage_summary=snapshot.get("summary"))
        return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]

    if name == "set_readout":
        arguments.setdefault("timestamp", _now_iso())
        if not arguments.get("timestamp"):
            arguments["timestamp"] = _now_iso()
        arguments.setdefault("session_id", _default_session_id())
        if not arguments.get("session_id"):
            arguments["session_id"] = _default_session_id()

        # If the model supplied only context_usage_percent_observed, derive
        # session_position from it. Model must provide at least one.
        if "session_position" not in arguments or not arguments.get("session_position"):
            pct = arguments.get("context_usage_percent_observed")
            if isinstance(pct, (int, float)):
                arguments["session_position"] = _bucket_for_percent(float(pct))

        # Auto-enrich BEFORE pydantic validation so any auto-injected flags
        # (e.g. quota pressure) can satisfy the epistemic_flags rules and the
        # JSONL log captures full wall-clock + quota state.
        existing_metadata = arguments.get("metadata")
        metadata: dict[str, Any] = (
            dict(existing_metadata) if isinstance(existing_metadata, dict) else {}
        )

        # Wall-clock snapshot — local, free, attached unless explicitly off.
        if clock_enabled():
            metadata.setdefault("clock_snapshot", get_clock_snapshot(READOUTS_FILE))

        # codexbar usage — best-effort, may be None.
        snapshot = fetch_usage()
        if snapshot is not None:
            metadata.setdefault("usage_snapshot", snapshot)
            pressure_flag = quota_pressure_flag(snapshot)
            if pressure_flag:
                flags = list(arguments.get("epistemic_flags") or [])
                if pressure_flag not in flags:
                    flags.append(pressure_flag)
                arguments["epistemic_flags"] = flags

        # Only attach metadata if anything is in there — preserves the v0.1
        # contract that metadata=None when neither model nor server has data.
        if metadata:
            arguments["metadata"] = metadata

        try:
            readout = Readout(**arguments)
        except Exception as exc:
            return [TextContent(type="text", text=f"Validation error: {exc}")]

        readout_dict = readout.model_dump(mode="json")
        _current_readout = readout_dict
        _persist(readout_dict)

        # Reset the activity counter — a fresh readout has happened, the
        # tool-call budget restarts from zero.
        pulse_module.reset_activity()

        return [
            TextContent(
                type="text",
                text=(
                    f"Readout accepted and persisted.\n\n"
                    f"```json\n{json.dumps(readout_dict, ensure_ascii=False, indent=2)}\n```"
                ),
            )
        ]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


def main() -> None:
    global _current_readout
    _current_readout = _hydrate_from_disk()
    if _current_readout is not None:
        print(
            f"[mirror-mirror] hydrated last readout from {READOUTS_FILE}",
            file=sys.stderr,
        )

    async def run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(run())


if __name__ == "__main__":
    main()
