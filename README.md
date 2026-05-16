# mirror-mirror

Structured self-reports for long-running LLM operator workflows.

`mirror-mirror` is a small research artifact for making AI-agent sessions easier to supervise. It gives the model a strict protocol for reporting functional states such as uncertainty, caution, overload, or context fatigue, plus a concrete recommendation to the operator.

It is **not** emotion detection. It is **not** a consciousness claim. It is **not** interpretability instrumentation. It is an operator signal: useful when it predicts trouble, disposable when it does not.

> The readout is the bassist, not the lead vocalist. It should keep the session honest without taking over the room.

## Why this exists

AI agents can look calm while drifting. They can produce confident prose while silently relying on bad assumptions, running out of context, or overfitting to the operator's tone.

`mirror-mirror` tests whether a lightweight, structured self-report can give operators earlier warning than post-hoc output review. The goal is not to make models more human. The goal is to make long sessions less opaque.

## What it does

- Adds a copy-paste system prompt protocol for functional-state readouts.
- Defines a JSON format with mandatory epistemic warnings.
- Provides a minimal local MCP server for storing and retrieving the latest readout.
- Includes synthetic examples showing a session with and without the protocol.
- Documents failure modes up front, including overtrust, alert fatigue, and anthropomorphization.

## What it does not claim

- That models feel emotions or have subjective experience.
- That text self-reports reliably expose internal model state.
- That Anthropic's interpretability findings transfer directly to prompt-level self-report.
- That this should replace tests, review, or operator judgment.
- That one protocol will work across all model families.

## Quick start

### Option 1: system prompt add-on

Copy the block in [`system-prompt-addon.md`](system-prompt-addon.md) into your agent's system prompt.

Then ask:

```text
readout?
```

The model should answer with a `[READOUT]` JSON block using the protocol in [`PROTOCOL.md`](PROTOCOL.md).

### Option 2: local MCP server

```bash
cd mcp-server
python3 -m pip install -e .
python3 server.py
```

The server exposes two tools:

- `set_readout` — the model stores a functional-state readout.
- `get_last_readout` — the operator retrieves the most recent readout.

See [`mcp-server/README.md`](mcp-server/README.md) for Claude Code configuration.

### Option 3: manual experiment

Run the same task twice:

1. without the protocol,
2. with the protocol active.

Compare when the model asks clarifying questions, flags assumptions, or warns about context risk. The point is not whether the JSON looks plausible. The point is whether it changes operator decisions.

## Readout format

```json
{
  "timestamp": "2026-05-07T14:32:00Z",
  "session_id": "architecture-review-001",
  "session_position": "mid",
  "trigger": "pre_plan",
  "functional_states": [
    {
      "name": "uncertainty",
      "intensity": 0.72,
      "confidence_in_self_report": 0.58,
      "context": "The brief contains two competing priorities and no acceptance criteria."
    }
  ],
  "epistemic_flags": [
    "self-report only — no vector readout available",
    "intensity estimate is approximate"
  ],
  "recommendation_to_operator": "Confirm which priority wins before continuing; otherwise the plan will optimize for the wrong constraint."
}
```

Every readout must include:

- at least one functional state,
- an intensity estimate,
- confidence in the self-report,
- mandatory epistemic flags,
- a concrete recommendation to the operator.

## Good first experiments

- **Long architecture planning:** does the readout surface uncertainty before a bad plan hardens?
- **Multi-agent handoff:** does it help the next agent understand what the previous agent was unsure about?
- **Context-limit check-in:** does it warn before late-session drift becomes visible in the answer?
- **Uncertainty escalation:** does `uncertainty >= 0.7` cause a useful operator intervention or just noise?

Use [`EVAL_PLAN.md`](EVAL_PLAN.md) to evaluate these without fooling yourself.

## Share what breaks

The useful version of this project will come from negative evidence, not flattering demos.

If you test it, the most helpful reports are:

- a readout that looked plausible but did not predict a real problem,
- a readout that changed the operator's decision in a useful way,
- a case where the protocol increased noise, overtrust, or anthropomorphism,
- model-family differences between Claude, GPT, Gemini, or open-weight models.

Open an issue with synthetic or anonymized notes. See [`PRIVACY.md`](PRIVACY.md) before sharing logs.

## Design decisions and their grounding

Every threshold, default, and behavior in mirror-mirror is one of three things: **research-backed**, **operations convention**, or **fail-safe heuristic**. We do not pretend convention is research, and we name heuristics as heuristics. The full grading lives in [`docs/RESEARCH.md`](docs/RESEARCH.md) with citations.

Short version:

- **Pulse activity trigger** (8 / 24 tool calls) — research-backed. Reflexion 2023's 30-action bound, Voyager's 4-failed-rounds policy, SELF-REFINE's diminishing-returns-after-3 finding.
- **Pulse context-window trigger** (15% / 25% of advertised) — research-backed. BABILong 2024 (effective context 10–20%), NoLiMa 2025 (GPT-4.1's effective length ~1.6% of 1M advertised), Liu 2023 "Lost in the Middle", Chroma Context Rot 2025.
- **Pulse quota trigger** (70% / 90%) — **ops convention**. AWS recommended alarms, SRE Book. Not empirically validated for LLM users.
- **Pulse time trigger** (30 / 60 min) — **fail-safe heuristic only**. No literature supports wall-clock periodicity for agent self-monitoring. Kept as a safety net for idle sessions; the reason string in the pulse output flags it as such.
- **Severity bands** (none / soft / hard) — convention from monitoring industry, not research-validated for agents.

The grading exists so any future Claude session reading this repo, any operator deciding whether to deploy this in earnest, and any reviewer asking "why these numbers?" can find the answer without trusting our intuition.

## Project map

```text
mirror-mirror/
├── README.md
├── PROTOCOL.md
├── system-prompt-addon.md
├── FAILURE_MODES.md
├── EVAL_PLAN.md
├── PRIVACY.md
├── RESEARCH_NOTES.md
├── docs/
│   ├── HANDOFF.md
│   └── RESEARCH.md          # ← every threshold's literature backing
├── examples/
│   ├── readout-schema.json
│   ├── readout-example.md
│   ├── session-with.md
│   └── session-without.md
└── mcp-server/
    ├── server.py
    ├── clock.py
    ├── usage.py
    ├── pulse.py
    ├── statusline.py
    ├── statusline_script.py    # ← install into Claude Code statusLine
    ├── hook_pulse_injector.py  # ← install into Claude Code UserPromptSubmit hook
    ├── pyproject.toml
    └── tests/
```

## Polish note

Ten projekt wyrósł z polskojęzycznych eksperymentów z agentami i operator workflows, ale publiczne repo jest English-first, żeby łatwiej było je testować i krytykować globalnie.

Krótko po polsku: `mirror-mirror` to protokół samoraportu modelu. Nie mówi, że model czuje. Mówi: “model zachowuje się tak, jakby operował pod niepewnością / przeciążeniem / ostrożnością; operatorze, sprawdź X”.

## References

- Anthropic Interpretability Team (2026). [Emotion concepts and their function in a large language model](https://www.anthropic.com/research/emotion-concepts-function).
- Sofroniew et al. (2026). [Emotion Concepts and their Function in a Large Language Model](https://transformer-circuits.pub/2026/emotions/index.html).
- Reeves, B. & Nass, C. (1996). *The Media Equation.*
- Edmondson, A. (1999). Psychological Safety and Learning Behavior in Work Teams. *Administrative Science Quarterly*.

See [`RESEARCH_NOTES.md`](RESEARCH_NOTES.md) for the longer motivation and caveats.

## Status

`v0.1-alpha`: usable for local experiments, not production infrastructure.

## License

MIT. See [`LICENSE`](LICENSE).
