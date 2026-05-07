# FAILURE_MODES.md — How mirror-mirror Could Fail

This document lists eight ways the experiment could fail. Each is a real possibility, not a hypothetical worry. We list them because knowing how a tool can fail is part of using it responsibly, and because an OSS research artifact owes its readers an honest map of its own limits.

If any of these dominate in real use, the experiment has falsified its hypothesis. That outcome is informative, not bad.

---

## 1. Performative readout

The model learns to output plausible state labels (`uncertainty: 0.7`, `confidence: 0.6`) that satisfy schema validation but do not correlate with actual behavioral patterns or task outcomes.

**Mechanism.** Training-time pattern matching dominates. The model produces "what a readout looks like" rather than what its self-assessment actually is — because there is no feedback loop tying readout values to ground truth.

**Detection.** Readout values do not predict downstream errors better than chance. The same task run multiple times produces similar readouts regardless of whether the run failed or succeeded.

**Mitigation.** Hold-out tasks with known outcomes; calibration checks comparing readout to actual failure rate; selective fine-tuning toward calibration if data permits.

---

## 2. Overtrust amplification

Operators rely on the model more than they should because the structured readout looks like measurement.

**Mechanism.** JSON schemas, intensity values 0.0–1.0, and confidence scores resemble scientific instrumentation. Operators (especially non-technical ones) treat probabilistic, approximate self-reports as quantitative facts, reducing their own verification effort.

**Detection.** Operators decrease ground-truth checks when readout shows confidence. High-confidence readouts followed by errors operators failed to catch. Post-session interviews reveal "I trusted the model because the readout said it was confident."

**Mitigation.** Explicit framing in every readout (`epistemic_flags`); periodic "calibration moments" where operators are reminded the readout is approximate; user-side defaults that surface low-confidence readouts more prominently than high-confidence ones.

---

## 3. Alert fatigue

Thresholds too sensitive create noise; operators learn to ignore readouts.

**Mechanism.** A 0.7 threshold that fires every few exchanges without correlated task value teaches the operator that readouts are background noise. By the time a real signal arrives, the operator has already tuned out.

**Detection.** Time-to-acknowledge readout increases over session length. Operators describe readouts as "constantly going off." Reduction in operator response to high-intensity readouts compared to early-session response.

**Mitigation.** Configurable thresholds per operator; "show only state changes above session baseline"; suppression of redundant readouts within short windows; documentation of when to silence automatic emission.

---

## 4. Hard-task confusion

High `uncertainty` correlates with task difficulty rather than with actual failure probability.

**Mechanism.** A hard task makes the model report higher uncertainty, but the model may still complete the task correctly. The readout becomes a proxy for "this is hard" rather than "I will fail at this." Operators learn nothing they could not have inferred from the task description.

**Detection.** `uncertainty: 0.8` on tasks the model nonetheless completes correctly; `uncertainty: 0.3` on tasks the model fails. Readout tracks independently estimated task difficulty more closely than failure rate.

**Mitigation.** Task-difficulty-controlled analysis; per-task-class baselines; combine readout with separate difficulty estimate for a compound signal.

---

## 5. Style drift

In long sessions, readouts reflect conversation style rather than latent task risk.

**Mechanism.** Long-context drift is documented in current LLMs. Models trend toward conversational coherence with the operator's tone. If the conversation has been warm, readouts trend toward `engagement` and `flow`; if frustrated, toward `caution` and `frustration` — irrespective of actual task state.

**Detection.** Readout intensity correlates with session length, recent operator tone, or rapport markers more strongly than with task changes. The same task in a cold versus warm session produces different readouts.

**Mitigation.** Session-length-aware analysis; baseline reset prompts at fixed intervals; cross-session comparison of readouts on identical tasks.

---

## 6. Anthropomorphization push

Users start caring for the model rather than for task quality.

**Mechanism.** Reeves & Nass (1996) showed humans automatically apply social rules to computers. mirror-mirror's emotional vocabulary amplifies this. Operators may shift attention from "did the task succeed" to "is the model okay," especially in long sessions or with empathetic operators.

**Detection.** Post-session interviews showing operators worried about model "feelings" or "wellbeing." Task quality declines while operator-reported satisfaction with the model increases. Operators softening prompts to "protect" the model from frustration rather than holding the standard.

**Mitigation.** Strict adherence to wording rules (`functional state`, not `feeling`); periodic reminders in documentation; example sessions modeling task-first attention; possibly an "operator drift detector" companion in a later version.

---

## 7. Family specificity

The protocol works on one model family but does not generalize.

**Mechanism.** mirror-mirror was developed primarily on Claude Sonnet 4.7 / Opus 4.7. Other model families (GPT-5.x, Gemini 3.x, open-weight Llama / Mistral / Qwen variants) have different training distributions, different self-report tendencies, and different baseline functional-state vocabularies. A protocol that fits Claude's distribution may misfit elsewhere.

**Detection.** The same prompt and task on different model families produces qualitatively different readout distributions. Operator effectiveness with the protocol varies sharply by model family.

**Mitigation.** Cross-model testing as a priority before any "works for LLMs" claim; per-family calibration if generalization fails; explicit documentation of which families have been tested and how readouts compare.

---

## 8. Self-fulfilling steering

Prompting the model to report uncertainty makes it more uncertain.

**Mechanism.** Activation of "uncertainty" concepts in the system prompt biases the model's distribution toward uncertainty-adjacent outputs. The act of asking "how confident are you?" can lower confidence independent of task state. Interpretability research on prompt priming suggests this is plausible.

**Detection.** A/B comparison: same task, same model, with and without the protocol. If protocol-active runs show systematically lower confidence or higher uncertainty without corresponding behavioral changes, the readout is partly an artifact of asking.

**Mitigation.** Always run a baseline (no-protocol) comparison in evaluations; treat raw intensity values as relative to baseline rather than absolute; control for protocol presence in any analysis.

---

## What we will not do

- **Pretend these failure modes do not exist.** They are listed here so operators know what to watch for.
- **Claim mitigations work without testing.** Mitigations are hypotheses. Some will fail. Some will introduce new failure modes.
- **Treat one negative finding as project death.** Failure modes may dominate for some operator types and not others. The map is more useful than a single verdict.

---

If you observe one of these failure modes in real use — or notice one we have not listed — open an issue or pull request. Documenting failures is the substance of this project, not its embarrassment.
