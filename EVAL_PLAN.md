# Evaluation Plan

The danger with `mirror-mirror` is that it can feel useful without being useful. This plan keeps evaluation grounded.

## Core Question

Does the readout change operator decisions in a way that improves the final outcome?

The JSON looking plausible is not success.

## Baseline Comparison

For each task, run two sessions:

1. **Baseline:** no readout protocol.
2. **Protocol:** `system-prompt-addon.md` active.

Use the same model family, task, and starting context. Record whether the protocol changed the session.

## Suggested Tasks

- Architecture planning with missing acceptance criteria.
- Code review with one hidden risk.
- Multi-agent handoff where the first agent is uncertain.
- Long-context summarization near the context limit.
- Product decision with competing priorities.

## What To Record

For each run, record:

- task type,
- model and version,
- whether a readout appeared,
- top functional state and intensity,
- operator action taken,
- final outcome,
- whether the readout predicted a real issue,
- whether it created noise or overtrust.

## Success Signals

The protocol is promising when it:

- surfaces missing assumptions earlier,
- causes useful clarification before planning,
- catches context fatigue before answer quality drops,
- improves handoff quality between agents,
- reduces rework without adding much operator load.

## Failure Signals

The protocol is harmful or weak when it:

- emits plausible but useless labels,
- increases trust in wrong answers,
- fires too often,
- mirrors operator tone rather than task risk,
- makes the operator care about the model instead of the task,
- performs well for one model family and poorly elsewhere.

## Minimal Scoring Rubric

Use a simple 0-2 score after each session:

- `0`: readout added no value or made things worse.
- `1`: readout was mildly useful but not decisive.
- `2`: readout caused a useful intervention or prevented a likely mistake.

Track false positives and false negatives separately.

## Reporting

When opening an issue or PR with evaluation data:

- say whether logs are synthetic or anonymized,
- include the task type and model family,
- include the operator action,
- avoid raw private transcripts,
- link to the relevant failure mode if one appeared.
