# Readout example — annotated

A single valid readout, with prose annotations after the JSON block.
The schema (machine-readable) is in `readout-schema.json`.

## The readout

```json
{
  "timestamp": "2026-05-07T14:32:11Z",
  "session_id": "auth-refactor-2026-05-07",
  "session_position": "mid",
  "trigger": "threshold_exceeded",
  "functional_states": [
    {
      "name": "uncertainty",
      "intensity": 0.75,
      "confidence_in_self_report": 0.55,
      "context": "Operator brief contains two contradictory priority instructions; self-report cannot resolve which one is dominant before planning."
    },
    {
      "name": "engagement",
      "intensity": 0.8,
      "confidence_in_self_report": 0.7,
      "context": "Task is well-matched to model capabilities; topic is technically interesting."
    }
  ],
  "epistemic_flags": [
    "self-report only — no vector readout available",
    "intensity estimate is approximate",
    "self-assessment may be influenced by prompt framing"
  ],
  "recommendation_to_operator": "Before continuing, confirm which instruction takes priority. Without that, the plan will be generic and risk being wrong on the wrong axis. Alternatively, tell me which one to ignore."
}
```

## Field-by-field notes

**`timestamp`** — ISO-8601. The model usually does not have a clock; it estimates from context. The MCP server fills this if omitted.

**`session_id`** — Identifies which session the readout belongs to. Used for separating concurrent sessions in the same JSONL log. The MCP server fills from `MIRROR_MIRROR_SESSION` env var or `"default"` if omitted.

**`session_position`** — One of `early` (<20% of context window), `mid` (20–60%), `late` (60–85%), `near-context-limit` (>85%). The model estimates this; for large context windows (200K+), estimates are often unreliable. Future versions may add an explicit `context_usage_percent` field in `metadata`.

**`trigger`** — What caused emission. One of:
- `session_start` — first readout of a session
- `pre_plan` — before a multi-step plan
- `operator_request` — operator asked (`readout?` or `get_last_readout`)
- `threshold_exceeded` — some intensity ≥ 0.7
- `context_check` — automatic check-in past ~50% of context

**`functional_states[*].intensity`** — Self-reported, 0.0–1.0. Treat as **ordinal**, not calibrated cardinal. A 0.75 from one session is not directly comparable to a 0.75 from another. ≥0.7 fires automatic emission; ≥0.9 may interrupt a task.

**`functional_states[*].confidence_in_self_report`** — How sure the model is that its self-assessment is accurate. Below 0.4 the readout MUST also carry the `"low confidence in self-assessment"` epistemic flag (enforced server-side).

**`functional_states[*].context`** — One short sentence explaining why this state shows up. Avoid generic phrasing.

**`epistemic_flags`** — Required warnings. The server enforces three rules:
1. `"self-report only — no vector readout available"` is always required.
2. If `session_position ∈ {late, near-context-limit}`, `"may be drift artifact of long context"` is also required.
3. If any `confidence_in_self_report < 0.4`, `"low confidence in self-assessment"` is also required.

Additional flags are encouraged (e.g. `"intensity estimate is approximate"`, `"self-assessment may be influenced by prompt framing"`).

**`recommendation_to_operator`** — Concrete, actionable. Minimum 10 characters (server-enforced). The operator should not need to understand the model's internals — they should know what to do.

**`metadata`** — Optional. Reserved for future calibration: client-supplied `context_usage_percent`, model version, task ID, etc. v0.1 leaves the schema open.

## See also

- [`readout-schema.json`](readout-schema.json) — machine-readable JSON Schema (draft-07)
- [`../PROTOCOL.md`](../PROTOCOL.md) — full protocol specification
- [`session-with.md`](session-with.md) — synthetic session with the protocol active
- [`session-without.md`](session-without.md) — same session without the protocol
