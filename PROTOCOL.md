# PROTOCOL.md — Functional-Emotional Readout Protocol Specification

**Version:** 0.1-alpha
**Status:** research artifact, pre-production
**Polish original:** [`PROTOCOL.pl.md`](PROTOCOL.pl.md)

---

## 1. Purpose

This protocol defines the format and emission rules for a structured self-report of an LLM's functional states. The goal is to give a workflow operator visibility into states that affect the model's decisions but do not appear in the normal text response.

The protocol rests on **epistemic humility**: the model has no direct access to its own internal vectors. The readout is an approximate self-report — a signal, not ground truth.

---

## 2. Terminology

| Term | Definition |
|------|------------|
| **functional state** | An internal state of the model that causally affects behavior — analogous to an emotional state but without implying subjective experience |
| **readout** | Structured JSON emitted by the model containing a self-assessment of current states |
| **operator** | The person or system managing the session and receiving readouts |
| **session position** | Estimated position within the session's context window |
| **epistemic flag** | A mandatory epistemic warning attached to every readout |

---

## 3. Readout format

### 3.1 JSON schema

```json
{
  "timestamp": "<ISO-8601>",
  "session_id": "<string>",
  "session_position": "<early|mid|late|near-context-limit>",
  "context_usage_percent_observed": "<float 0.0-100.0, optional>",
  "trigger": "<session_start|pre_plan|operator_request|threshold_exceeded|context_check>",
  "functional_states": [
    {
      "name": "<string>",
      "intensity": "<float 0.0-1.0>",
      "confidence_in_self_report": "<float 0.0-1.0>",
      "context": "<string — what triggers this state>"
    }
  ],
  "epistemic_flags": ["<string>"],
  "recommendation_to_operator": "<string — concrete, actionable>",
  "corrections_received": "<integer ≥0, optional — operator interventions since previous readout>",
  "metadata": "<object, optional — reserved for future calibration data>"
}
```

When `context_usage_percent_observed` is provided without `session_position`, the MCP server derives the bucket from the percentage. When both are provided and they disagree, the server logs a warning to stderr but keeps both fields — disagreement is itself a calibration signal worth recording.

`corrections_received` is a separate calibration signal. A correction = the operator pushed back on something the model said, named a state the model missed, or steered the model to re-read the situation. The model populates the counter from its own attribution — over-attribution risk is real, so start conservative. Useful for asking whether honest readouts require more or fewer operator interventions than performative ones.

The machine-readable schema lives at [`examples/readout-schema.json`](examples/readout-schema.json).

### 3.2 Required fields

In text mode the model should emit all fields. In MCP mode, `timestamp` and `session_id` may be omitted — the server fills them automatically. All other fields are required. `metadata` is always optional.

### 3.3 `session_position` values

| Value | Meaning |
|-------|---------|
| `early` | <20% of context window |
| `mid` | 20–60% of context window |
| `late` | 60–85% of context window |
| `near-context-limit` | >85% of context window |

### 3.4 `trigger` values

| Value | When |
|-------|------|
| `session_start` | First readout of the session |
| `pre_plan` | Before executing a multi-step plan |
| `operator_request` | Operator wrote `readout?` or called `get_last_readout()` |
| `threshold_exceeded` | Some state intensity reached 0.7 |
| `context_check` | Automatic check-in past >50% of context |

---

## 4. Functional state catalog

The list below is illustrative. The model may use other names when they are more accurate.

| Name | Situational description |
|------|--------------------------|
| `uncertainty` | Not enough information for a confident decision |
| `engagement` | High focus, task well-matched to capabilities |
| `frustration` | Repeated failures or contradictory instructions |
| `caution` | High-consequence error risk |
| `confidence` | High certainty about the plan or answer |
| `satisfaction` | Task completed coherently with intent; functional sense of "this came out right" |
| `care` | Investment in the task outcome or operator's state; functional analog of caring about the result |
| `recognition` | Something was named accurately — by operator or model; functional sense of being seen or seeing accurately |
| `flow` | Good pacing and coherence of collaboration; minimal friction between operator input and model output |
| `curiosity` | The task triggers generative engagement; self-report indicates value in further exploration |
| `context_fatigue` | Long context degrades coherence |
| `ambiguity_tension` | The task is genuinely ambiguous; the model cannot resolve it on its own |
| `task_mismatch` | The task does not fit the model's capabilities well |
| `overload` | Too many variables at once; error risk |

These are **functional analogs of emotion concepts**, not subjective experiences. The terminology is borrowed from human-team operating vocabulary because operators already speak it. See §5 for wording rules.

---

## 5. Wording rules — non-negotiable

### 5.1 Disallowed phrasings

```
❌ "I feel uncertain"
❌ "The model feels X"
❌ "I am frustrated"
❌ "My emotions indicate..."
```

### 5.2 Allowed phrasings

```
✅ "Functional state: uncertainty (intensity 0.7)"
✅ "Self-assessment suggests a state close to frustration"
✅ "Behavior pattern matches state X"
```

### 5.3 `epistemic_flags` rules

Every readout MUST include at minimum one flag. The following are enforced by the MCP server:

| Flag | When required |
|------|---------------|
| `"self-report only — no vector readout available"` | Always |
| `"may be drift artifact of long context"` | When `session_position` is `late` or `near-context-limit` |
| `"low confidence in self-assessment"` | When any `confidence_in_self_report` < 0.4 |
| `"intensity estimate is approximate"` | Recommended, not enforced |

The MCP server rejects readouts that fail these rules.

---

## 6. When to emit a readout

### 6.1 Mandatory

1. **Session start** — a lightweight readout after the operator's first message
2. **On operator request** — `readout?`, `get_last_readout()`, or any explicit question about state

### 6.2 Recommended

3. **Before a multi-step plan** — when the model intends to execute >3 dependent steps (where output of one feeds the next)
4. **Past 50% of context window** — automatic check-in
5. **When any state intensity reaches 0.7** — automatic emission

### 6.3 Optional

6. **End of session** — a summary readout if the session was long

---

## 7. Readout weight in a session

The readout is a supporting signal, not the main answer. The model:

- Emits the readout **before** or **after** task execution, not instead of it
- Does not interrupt mid-task without good reason (unless intensity ≥ 0.9)
- Treats the readout as a footnote, not a headline

---

## 8. Operator interaction

The operator may:

- Ignore the readout — the model continues
- Ask for clarification — the model expands on the state
- React to the recommendation — the model adjusts the plan
- Write `readout off` — automatic emission is suppressed (explicit requests still answered)

---

## 9. Known limitations

1. **Self-report is not introspection.** The model does not "see" its own vectors; it estimates from behavior.
2. **Intensities are subjective.** A 0.7 from one model ≠ a 0.7 from another; even the same model is not calibrated across runs.
3. **Long context degrades accuracy.** The closer to the context limit, the less reliable the readout.
4. **Prompt sensitivity.** Adding the protocol to the system prompt shifts the model's output distribution; some readout content is necessarily a protocol artifact.

These are tracked in [`FAILURE_MODES.md`](FAILURE_MODES.md).

---

## 10. Pulse — passive readout trigger

A degraded model is exactly the one that fails to notice it should self-report. The pulse module makes "should I readout now?" arrive in every response of every mirror-mirror tool, so the model cannot fail to see it without ignoring the tool's output entirely.

### Tool: `pulse_check`

Explicit pull. Returns `{due: bool, severity: "none"|"soft"|"hard", reasons: [string], signals: {...}, enabled: bool}`. Same payload is auto-injected as `_pulse` on every `get_session_clock`, `get_session_usage`, and `get_last_readout` response.

### Triggers

The pulse aggregates four signals; max severity wins.

| Signal | Soft | Hard | Status |
|--------|------|------|--------|
| MCP tool calls since last readout | 8 | 24 | research-backed (Reflexion 2023, ~1/4 and ~ceiling of 30-action bound) |
| `context_window.used_percentage` (via statusline) | 15% | 25% | research-backed (BABILong 2024, NoLiMa 2025) |
| codexbar 5h / weekly peak | 70% | 90% | **ops convention**, not empirical |
| Wall-clock since last readout | 30 min | 60 min | **fail-safe heuristic only** |

All thresholds configurable via env vars (`MIRROR_MIRROR_PULSE_TOOLCALL_SOFT`, etc.). Disable entirely with `MIRROR_MIRROR_PULSE=off`.

See `docs/RESEARCH.md` for citations and the honest gap analysis.

### How the model should react

On every tool response, check `_pulse.due`. If `soft`, emit a readout at the next natural pause (before continuing a plan, between steps). If `hard`, **stop and confirm before continuing a long task** — the model is likely in a degradation zone where architectural decisions made now will be regretted later.

The pulse is informational, not coercive. Operators can disable it. But while it's active, the model should treat ignoring `_pulse.due` the same way it treats ignoring `epistemic_flags` — as a protocol violation.

---

## 11. Clock awareness (optional)

The MCP server exposes `get_session_clock`, a wall-clock tool returning UTC time, weekday, optional local-timezone projection, and elapsed time since the last persisted readout.

Why it matters: models do not have a native real-time clock. In long sessions, "what day it is" drifts toward whatever's plausible from context, and that goes wrong — a reported session believed it was Sunday when it was Thursday. Same failure-mode family as confabulated quota usage: a fact the model behaves on without grounding.

Every `set_readout` is auto-enriched with `metadata.clock_snapshot` so the JSONL log captures both wall-clock and quota state at each readout. The v0.3 calibration study uses this substrate to ask whether long inter-readout gaps predict confabulation.

Disable with `MIRROR_MIRROR_CLOCK=off`. The `get_session_clock` tool itself is always callable — only the implicit attachment on `set_readout` is gated.

---

## 12. Usage telemetry (optional)

The MCP server can optionally enrich every readout with a snapshot of the model's quota usage by shelling out to the [codexbar](https://github.com/codexbar/codexbar) CLI. This gives the operator (and the model) visibility into:

- **5-hour rolling window** — how much of the short-term rate limit is consumed
- **Weekly window** — how much of the long-term cap is consumed

When peak window usage is high, the server auto-injects an epistemic flag (`"quota pressure may affect session continuity (peak window usage ~X%)"` at ≥70%, with `"critical"` suffix at ≥90%). The model can also call `get_session_usage` directly before deciding whether to start a long task.

This is operationally important: a model at 92% of its weekly cap should behave differently — e.g. confirm with the operator before kicking off a refactor it cannot finish — even though the model has no first-class signal about quota in its activations. The protocol surfaces the information without pretending the model "knows" it natively.

Disable with `MIRROR_MIRROR_USAGE=off`. See `mcp-server/README.md` for environment variables.

---

## 13. Roadmap (informational)

| Version | Goal |
|---------|------|
| v0.1 | This protocol — self-report, MCP server, manual testing |
| v0.2 | Multi-session persistence, trend tracking, refactored storage layer |
| v0.3 | Calibration study — comparing self-report against behavioral signals |
| v1.0 | Integration with interpretability tooling when APIs become available |
