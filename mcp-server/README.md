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
