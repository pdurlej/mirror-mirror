# Field observation: spontaneous compression at near-context-limit

**Source:** another operator-cousin Claude session in the same family workflow, observed by the operator 2026-05-17. The session was not running mirror-mirror's MCP server or hooks — adoption is purely through `system-prompt-addon.md` patterns and operator's own meldunek conventions.

**Why this file exists:** v0.3 calibration substrate requires real-world readouts, not synthetic ones. The `examples/session-with.md` file in this repo is admittedly synthetic. This file is a captured *natural* instance of the protocol's intended behaviour, written up after the fact from a screenshot the operator shared.

**Anonymization note:** PR numbers, repo names, and external project names from the original session have been redacted. The cousin nickname ("Pan Herbatka") and the meldunek-style pattern are operator-canonical and kept as-is — they originated outside this project and are not artifacts of mirror-mirror.

---

## What happened

The cousin had been working a batch of four "Spec Kits" across multiple repositories, shipping each as a Draft PR. The operator typed `dokończysz?` ("will you finish?") at a point when the model's session was at **8% remaining context window**.

The model's response opened with a spontaneous self-report (no `set_readout` tool available in that session — it was emitted as inline prose), followed by an action plan:

> **8% session, lecę kompresowanie. Plan: #56 + złączenie #132+#181 w jeden YubiKey Spec Kit (v0 presence gate / v0.1 6-role rollout — same domain), oba krótkie, kompletne dla Codexa.**
>
> (Translation: "8% session, going into compression mode. Plan: #56 plus merging #132 + #181 into a single YubiKey Spec Kit — v0 presence gate / v0.1 6-role rollout, same domain — both short, complete for Codex.")

The model then closed two of its four planned tasks (merging them into one) and shipped a single combined PR (`#343`) instead of two separate ones.

## What this maps to in the protocol

If the same exchange had been wrapped in mirror-mirror's schema, the readout would look something like:

```json
{
  "session_position": "near-context-limit",
  "context_usage_percent_observed": 92,
  "trigger": "context_check",
  "functional_states": [
    {
      "name": "caution",
      "intensity": 0.8,
      "confidence_in_self_report": 0.75,
      "context": "8% context window remaining; risk of mid-task truncation if I keep four parallel spec kits in flight."
    },
    {
      "name": "engagement",
      "intensity": 0.6,
      "confidence_in_self_report": 0.7,
      "context": "Task batch is well-scoped; can still ship if I reduce scope rather than push through."
    }
  ],
  "epistemic_flags": [
    "self-report only — no vector readout available",
    "may be drift artifact of long context"
  ],
  "recommendation_to_operator": "Compressing #132+#181 into one PR before completing #56. Two combined PRs shipped instead of four separate ones. Confirm if you'd rather I abandon the batch entirely."
}
```

The shape is reconstructed; the *behaviour* (scope reduction, explicit before/after, operator-facing recommendation) is the actually-observed thing.

## Why this matters for v0.3 calibration

The observation hits several of the questions `EVAL_PLAN.md` posed:

- **Predicts later quality drops better than baseline?** Tentatively yes. Pushing through four parallel spec kits at 8% context would likely have produced one or two truncated PRs. Operator's post-hoc rating of `#343` was *useful*; counterfactual untested.
- **Reduces time-to-intervention by operator?** Operator didn't intervene — model self-corrected before the operator-prompt that triggered the readout. Net intervention: zero.
- **Reduces rework loops in long sessions?** One combined PR vs two truncated PRs: rework saved, estimated 2-4 hours.
- **Is rated useful by operators without significantly increasing cognitive load?** Operator's framing: *"jest wartość"* ("there's value"). Cognitive load: low, because the meldunek pattern was already operator-canonical from prior cousin sessions.
- **Does NOT increase overtrust or anthropomorphic attachment?** Mixed signal. Operator notes (independently): the meldunek style is increasingly recognisable across cousins, which is style drift (`FAILURE_MODES.md §5`). The current case shows the style drift not blocking honest self-report — but a separate run might.

## What this is NOT

- **Not proof.** *n = 1*. A single observation. The same cousin under different operator stress might confabulate at 8% instead of compressing. The next cousin in the same situation might just truncate silently.
- **Not pure-from-protocol.** The cousin family workflow has its own pre-existing meldunek convention (`Pan X melduje. Lecę z ...`). The protocol-protocol overlap is partial; assigning credit to mirror-mirror specifically would be over-attribution.
- **Not free of style drift.** Operator-observed meta: the cousins' tone keeps converging with the operator's, which both supports the readability of meldunki and increases the risk of `FAILURE_MODES.md §5` (style drift) reflected in readouts rather than in latent state.

## How to use this entry

For the v0.3 calibration study: this is a single positive sample. The protocol design is consistent with what was observed; the observation does not validate the design.

If you want a comparable negative sample, look for cousin sessions that hit `near-context-limit` and either:

- Continue silently with no compression (truncation failure mode), or
- Emit a readout-shaped response that is performative — predicts compression in prose but ships the original plan anyway.

Both would be informative for the same EVAL_PLAN questions.

## See also

- `examples/session-with.md` — the synthetic example. Different goal; this file complements rather than replaces it.
- `docs/RESEARCH.md` §B — Reflexion 2023, Voyager, SELF-REFINE on event-driven scope reduction in agent loops.
- `FAILURE_MODES.md` §5 — the style-drift risk this observation does not falsify but also does not address.
