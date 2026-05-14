# MCP Server

Minimal stdio MCP server for the `mirror-mirror` readout protocol.

The server does not ask the model to introspect. It only stores and returns readouts that the model emits through the protocol.

## Requirements

- Python 3.11+
- MCP SDK >= 1.0.0

## Install

```bash
cd mcp-server
python3 -m pip install -e .
```

For tests:

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest -q
```

## Run directly

```bash
python3 server.py
```

The server uses stdio, so it normally runs under an MCP client rather than as a standalone terminal app.

## Configure Claude Code

Prefer Claude Code's `claude mcp add-json` flow instead of hand-editing old MCP config paths.

User-scoped example:

```bash
claude mcp add-json --scope user mirror_mirror \
  '{"type":"stdio","command":"python3","args":["/absolute/path/to/mirror-mirror/mcp-server/server.py"],"env":{"MIRROR_MIRROR_SESSION":"claude-code"}}'
```

Project-scoped example:

```bash
claude mcp add-json --scope project mirror_mirror \
  '{"type":"stdio","command":"python3","args":["/absolute/path/to/mirror-mirror/mcp-server/server.py"],"env":{"MIRROR_MIRROR_SESSION":"project-session"}}'
```

The repository is named `mirror-mirror`, but the MCP server name intentionally uses
`mirror_mirror` so Claude exposes stable tool names such as
`mcp__mirror_mirror__set_readout`.

Then verify:

```bash
claude mcp list
claude mcp get mirror_mirror
```

## Environment

- `MIRROR_MIRROR_LOG` — absolute path to the JSONL log. Defaults to `~/.mirror-mirror/readouts.jsonl`.
- `MIRROR_MIRROR_SESSION` — default session identifier when a readout omits `session_id`. Defaults to `default`.
- `MIRROR_MIRROR_PULSE` — set to `off` to disable the passive pulse. Default: on.
- `MIRROR_MIRROR_PULSE_TOOLCALL_SOFT` / `_HARD` — activity thresholds (default 8 / 24).
- `MIRROR_MIRROR_PULSE_CONTEXT_PCT_SOFT` / `_HARD` — context-window % thresholds (default 15.0 / 25.0).
- `MIRROR_MIRROR_PULSE_QUOTA_SOFT` / `_HARD` — codexbar window % thresholds (default 70.0 / 90.0).
- `MIRROR_MIRROR_PULSE_TIME_SOFT_MIN` / `_HARD_MIN` — fail-safe time thresholds (default 30 / 60).
- `MIRROR_MIRROR_STATUSLINE_PATH` — statusline state file (default `~/.cache/mirror-mirror/claude-code-status.json`).
- `MIRROR_MIRROR_STATUSLINE_MAX_AGE_S` — max snapshot age before treating as stale (default 30).
- `MIRROR_MIRROR_CLOCK` — set to `off` to disable wall-clock auto-enrichment of `set_readout`. Default: on. The `get_session_clock` tool itself is unaffected.
- `MIRROR_MIRROR_TIMEZONE` — IANA timezone (e.g. `Europe/Warsaw`) for the `local` block in clock snapshots. Default: omit `local`.
- `MIRROR_MIRROR_USAGE` — set to `off` to disable the codexbar usage integration. Default: on.
- `MIRROR_MIRROR_USAGE_PROVIDER` — codexbar `--provider` argument. Default: `claude`.
- `MIRROR_MIRROR_USAGE_CMD` — override the entire usage command (useful for tests). Default: `codexbar usage --json`. If `--provider` is not present, it is appended.
- `MIRROR_MIRROR_USAGE_TIMEOUT` — seconds before the subprocess is killed. Default: `4.0`.

## Tools

### `set_readout`

Store a readout emitted by the model.

Required fields:

- `session_position`
- `trigger`
- `functional_states`
- `epistemic_flags`
- `recommendation_to_operator`

Optional fields:

- `timestamp` — server fills current UTC time when omitted.
- `session_id` — server fills `MIRROR_MIRROR_SESSION` or `default` when omitted.
- `metadata` — free-form object reserved for future calibration (e.g. `context_usage_percent`, `model`, `task_id`). Schema unconstrained at v0.1.

The server enforces three conditional rules from `PROTOCOL.md` §5.3:

- `session_position ∈ {late, near-context-limit}` requires the `"may be drift artifact of long context"` flag.
- Any `confidence_in_self_report < 0.4` requires the `"low confidence in self-assessment"` flag.
- `recommendation_to_operator` must be at least 10 non-whitespace characters.

Readouts that fail these rules are rejected with a validation error.

### `get_last_readout`

Return the most recent cached readout. This does not trigger a fresh self-assessment. Ask the model `readout?` first if you need a new readout.

### `pulse_check`

Explicit pull of the **passive pulse** — a trigger that aggregates four signals (activity / context pressure / quota / time) into a single `due: bool, severity: "none"|"soft"|"hard"` decision. The same payload is auto-injected as `_pulse` on every response of `get_session_clock`, `get_session_usage`, and `get_last_readout`.

Thresholds and their literature backing are documented in [`docs/RESEARCH.md`](../docs/RESEARCH.md). Activity (8/24) and context (15%/25%) are research-backed; quota (70%/90%) is operations convention; time (30/60 min) is fail-safe heuristic only. Every reason string the pulse emits flags its own evidentiary status.

### Statusline integration (required for context-pressure trigger)

Without statusline configuration the pulse loses access to `context_window.used_percentage`, the most research-supported signal. Setup is one-time:

1. Find your Claude Code `settings.json` (`~/.claude/settings.json` for user-level, `.claude/settings.json` for project-level).
2. Add or merge:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 /absolute/path/to/mcp-server/statusline_script.py",
    "refreshInterval": 5
  }
}
```

3. The script atomic-writes Claude Code's session JSON to `~/.cache/mirror-mirror/claude-code-status.json` every 5 seconds. The mirror-mirror MCP server reads from there.

If you already have a custom statusline command, wrap it or alternate via shell rather than replacing — `statusline_script.py` is designed to be small and pipe-friendly.

### `get_session_clock`

Return current wall-clock state: UTC time, weekday, optional local-timezone block, and time elapsed since the last persisted readout. Models do not have a native clock; this is the counter to confabulation like "I think it's Monday" in long sessions.

Returns `{now_utc, weekday, weekday_index, [local], last_readout_timestamp, time_since_last_readout_seconds, time_since_last_readout_human}`. Elapsed-time fields are null when no prior readout exists.

The tool always responds — `MIRROR_MIRROR_CLOCK=off` only disables the implicit attachment on `set_readout`, not the explicit pull path.

### `get_session_usage`

Return current rate-limit / quota status from the [codexbar](https://github.com/codexbar/codexbar) CLI. Useful before kicking off a long task — the model can check whether enough of its 5-hour or weekly window is left to finish.

The returned payload always has:

- `available: bool` — whether codexbar was reached at all
- `ok: bool` — whether codexbar returned a real reading vs. an error envelope
- `summary` — best-effort `{window_5h_pct, window_weekly_pct}` extraction
- `raw` — the unmodified codexbar JSON, for consumers that want to do their own parsing
- `error` — non-null only when codexbar returned an error envelope

Returns `{"available": false, "reason": "..."}` if codexbar is missing or disabled. The session is never blocked by usage telemetry.

## Auto-enrichment on `set_readout`

Two best-effort enrichments run server-side before pydantic validation:

**Wall-clock snapshot** (when `MIRROR_MIRROR_CLOCK` is on, default). Attaches `metadata.clock_snapshot` with `now_utc`, `weekday`, elapsed time since last readout, and an optional `local` block when `MIRROR_MIRROR_TIMEZONE` is set. Local, free, no failure modes.

**codexbar usage snapshot** (when `MIRROR_MIRROR_USAGE` is on, default). Attaches `metadata.usage_snapshot` with the codexbar reading (or `ok: false` when codexbar errored). Adds an extra epistemic flag when peak window usage is ≥70% (`"quota pressure may affect session continuity (peak window usage ~X%)"`) or ≥90% (`"... critical"`).

If both are off and the model passes no `metadata`, the readout is persisted with `metadata: null` — same contract as v0.1.

## Persistence

Readouts are appended to JSONL. One readout is one line.

The default log path is:

```text
~/.mirror-mirror/readouts.jsonl
```

On startup the server reads the last line of this file and uses it as the cached readout, so a process restart does not silently lose the most recent state. If the JSONL is missing, empty, or corrupt, the server starts with an empty cache and logs a warning to stderr.

Disk-level errors during `_persist` (full disk, permission denied) are caught and logged to stderr; the in-memory readout remains the source of truth for the current session and the `set_readout` call still succeeds.

Treat this file as private session data. See [`../PRIVACY.md`](../PRIVACY.md).

## Known limits

- One active in-memory readout.
- No authentication; local use only.
- No multi-session query interface (the JSONL is a flat log).
- No claim that readouts are calibrated.
