# Research Notes

`mirror-mirror` is motivated by interpretability, HCI, and operator-workflow concerns. It is not an interpretability project itself. It uses black-box self-report as an operational proxy and treats that proxy as fallible by default.

## What we are testing

We are testing whether **structured, human-legible state readouts can improve long-session LLM collaboration as an operator interface**.

We are not testing whether models have emotions, consciousness, or reliable introspection. The readouts are self-reports. They are not measurements of internal activations.

This distinction matters. Recent interpretability research shows that emotion-like functional representations can exist in some models and can affect behavior. Those findings come from white-box activation analysis and steering, not from asking a chatbot how it feels. `mirror-mirror` asks a weaker practical question:

> Can a structured self-report provide useful early-warning signals for human operators when activation-level access is unavailable?

## Interpretability motivation

Anthropic's April 2026 work, *Emotion Concepts and their Function in a Large Language Model*, identified internal emotion-related representations in Claude Sonnet 4.5. The research describes these representations as functional: they can influence behavior without necessarily appearing in output text.

That is a reason to take internal functional state seriously. It is not evidence that prompt-level self-report is calibrated.

The project therefore treats the Anthropic work as motivation, not proof. Every readout carries epistemic flags because the protocol is deliberately weaker than interpretability instrumentation.

## Human-computer interaction motivation

Humans already apply social coordination patterns to computers. With LLMs, this tendency becomes stronger because the interface is language and the model often presents as a cooperative assistant.

Ignoring this does not make the interaction less social. It only makes the social layer implicit. `mirror-mirror` tests whether making part of that layer explicit and structured improves operator control.

## Management vocabulary as operator vocabulary

Human teams already use practical language for operating under uncertainty: confidence, caution, overload, fatigue, pressure, escalation, psychological safety.

This project does not claim that human management theory transfers directly to LLMs. It claims that operators already understand this vocabulary, and that a bounded, non-anthropomorphic version may be more usable than raw interpretability terminology for day-to-day agent supervision.

## Hypotheses

1. Structured readouts may help operators intervene earlier than post-hoc output evaluation.
2. Non-technical operators may find readouts more actionable than hidden assumptions buried in prose.
3. Readouts may reduce rework loops in long sessions by surfacing context fatigue and ambiguity earlier.
4. Readouts may also backfire by increasing overtrust, alert fatigue, or anthropomorphic attachment.

## Success criteria

The experiment is promising if the readout:

1. predicts later quality drops better than baseline,
2. reduces time-to-intervention,
3. reduces rework loops in long sessions,
4. is rated useful without adding too much cognitive load,
5. does not increase overtrust or anthropomorphic attachment.

The fifth criterion matters as much as the first four. A readout can feel useful while making collaboration worse.

## Expected failure modes

The main expected failure modes are documented in [`FAILURE_MODES.md`](FAILURE_MODES.md):

- performative readout,
- overtrust amplification,
- alert fatigue,
- hard-task confusion,
- style drift,
- anthropomorphization push,
- family specificity,
- self-fulfilling steering.

If these dominate, the experiment has falsified its hypothesis. That outcome is useful.

## References

- Anthropic Interpretability Team (2026). [Emotion concepts and their function in a large language model](https://www.anthropic.com/research/emotion-concepts-function).
- Sofroniew et al. (2026). [Emotion Concepts and their Function in a Large Language Model](https://transformer-circuits.pub/2026/emotions/index.html).
- Reeves, B. & Nass, C. (1996). *The Media Equation.*
- Edmondson, A. (1999). Psychological Safety and Learning Behavior in Work Teams. *Administrative Science Quarterly*.
