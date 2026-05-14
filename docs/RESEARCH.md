# Research grounding for mirror-mirror design decisions

This document lists every design decision in mirror-mirror that involves a chosen number, threshold, or behavior, and grades each by what the literature actually supports vs what is convention vs what is pure heuristic. It exists so operators, contributors, and future Claude sessions reading this repo can distinguish between "we picked this because a study said so" and "we picked this because it felt right and we'll learn later".

If you find a published source we missed or a default we should revise, open an issue.

---

## Summary of evidentiary status

| Decision | Status | Default |
|----------|--------|---------|
| Pulse activity trigger | **Research-backed (inference)** | soft=8 / hard=24 tool calls since last readout |
| Pulse context-window trigger | **Research-backed** | soft=15% / hard=25% used |
| Pulse quota trigger | **Operations convention** | soft=70% / hard=90% peak window |
| Pulse time trigger | **Fail-safe heuristic only** | soft=30min / hard=60min |
| Epistemic flag conditional rules | **Project policy** | 3 enforced flags (drift, low-conf, mandatory) |
| `context_usage_percent_observed` numeric field | **Research-motivated** | optional; field reports requested it |
| `corrections_received` counter | **Calibration substrate** | optional; v0.3 study uses it |
| `recent_failures` counter | **Research-backed (inference)** | optional; Reflexion-aligned |

---

## A. Long-context degradation — basis for context-pressure trigger

### What we shipped

`context_window.used_percentage` (read from Claude Code's statusline) drives a pulse at **15% soft / 25% hard** of advertised window. We also accept a self-reported `context_usage_percent_observed` field on `set_readout`.

### What the literature supports

**Liu et al. 2023, "Lost in the Middle: How Language Models Use Long Contexts."** Positional bias in long inputs: models use info from the start and end of prompts but degrade in the middle, "especially notable" with prompts of more than 20 documents.

**BABILong 2024** (Kuratov et al.). Reasoning over facts dispersed in long text. Headline finding: **popular LLMs effectively use only 10–20% of advertised context.** Performance "declines sharply" as reasoning complexity grows.

**NoLiMa 2025** (Modarressi et al.). Estimates *effective context length* at the 0.85 normalized-score threshold:

- GPT-4o: **~16K of 128K** → 12.5%
- Llama 3.3 70B: **~8K of 128K** → 6.25%
- Llama 3.1 70B / 405B: **~4K of 128K** → 3.1%
- GPT-4.1: **~16K of 1M** → **1.6%**

Score drops below 65% at 128K for GPT-4.1.

**Chroma 2025, Context Rot report.** 18 models tested. LongMemEval comparison of ~300-token focused prompts vs ~113K-token prompts shows consistent quality drop across all families when irrelevant context is added. The classical needle-in-a-haystack benchmark with literal matching "typically performs well" and **overstates real long-context robustness.**

### Why our defaults

If "effective context" is 10–20% of advertised, the soft pulse trigger should fire well before that boundary, not after it. 15% / 25% places the soft trigger inside the effective zone for most current models and the hard trigger right at the documented degradation boundary for the more permissive ones.

### Gaps

There is no single peer-reviewed threshold "quality drops by X% at Y% context utilization" that holds across models and task classes. The best numbers are benchmark-specific. Some of the strongest 2025 findings (NoLiMa, Context Rot) come from preprints and technical reports, not long-stabilized production benchmarks.

---

## B. Self-monitoring intervals — basis for pulse architecture

### What we shipped

Pulse is **event-driven primarily, time-driven only as fallback.** The primary signals are activity (tool count), context pressure, and quota. The wall-clock timer is a safety net for idle sessions.

### What the literature supports

**ReAct (Yao et al. 2023).** "Thoughts only need to appear sparsely in the most relevant positions." Decisions and reasoning are interleaved per-step with model judgment about when to reason; no fixed interval.

**Reflexion (Shinn et al. 2023).** Triggers self-reflection on **>3 repeated identical actions** with identical results, OR **>30 actions in the current environment**. Memory limited to 3 reflections. Trigger is counter-based and state-based, not wall-clock.

**Voyager (Wang et al. 2023).** Iterative code refinement until self-verification passes, OR aborts the task after **4 rounds of failed generation**. Counter-based again.

**SELF-REFINE (Madaan et al. 2023).** Up to ~3 refinement cycles is the productive zone; marginal improvement decreases per iteration. The paper explicitly notes diminishing returns from over-frequent reflection.

**ReflAct 2025 (Liu et al.).** Adding reflective iterations or memory components to ReAct gives "limited benefits" and can "deteriorate performance" in dynamic environments. **More reflection ≠ better.**

### Why our defaults

Activity soft=8 is 1/4 of Reflexion's 30-action inefficient-planning bound — an early warning. Hard=24 leaves one buffer before that bound. These are inferences from agent-paper triggers, not direct citations. The closest direct number from literature is **30** (Reflexion), which we use as a ceiling.

Time-based 30/60 min thresholds get NO support in the literature. Agent papers reliably go event-driven. We kept the timer as a fallback for the case where a model is idle (no tool calls) but the session is still alive — pure product heuristic, flagged as such in the code comments and the reason strings.

### Gaps

We could not find a paper that empirically optimizes wall-clock periodicity for operator sessions. Anyone wanting research-grounded numbers there would need to run a study.

---

## C. Alert fatigue — basis for quota threshold framing

### What we shipped

Quota soft=70% / hard=90% for codexbar 5h and weekly windows.

### What the literature supports — and doesn't

**Google SRE Book.** Monitoring should have "good signal and very low noise." Avoid "false positives and pager burnout." A single 20-minute interrupt can realistically cost "several hours of genuinely productive work."

**AHRQ alarm fatigue review.** In healthcare, alarm overload caused 59,000+ alarms in 12 days at one center; false-alarm rates of **72–99%** lead to desensitization and ignored real alarms.

**Nagrecha & Baldwin 2022** (causal study). Participants exposed to **80% false alarms** acted on significantly more false alarms than those exposed to **40%**. Earlier exposure to high false-alarm rates degraded response to subsequent real alarms.

**Vectra State of Threat Detection.** Average 4,484 alerts/day; **67% ignored**, **83%** of analysts say alerts are false positives not worth their time. **51%** of SOC teams "overwhelmed" (Trend Micro survey via ACM 2023).

**AWS Recommended Alarms.** CPU **70–80%** as warning threshold, filesystem **90–95%**. Explicitly called *typical*, depends on workload — engineering convention.

### Why our defaults

70/90 mirrors the AWS warning/critical pair and is widely recognizable by anyone in ops. **It is NOT empirically validated for LLM users.** The reason string in the pulse module flags it explicitly: *"ops convention, not empirically validated for LLM users"*.

### Gaps

There is no peer-reviewed empirical study (that we found) of how Claude Pro/Max-style sliding-window utilization affects user behavior at specific percentages — no mid-task abandonment data, no scope-reduction curves, no productivity-vs-utilization function. This is a clean gap in the literature.

---

## D. Rate-limit user behavior — clean gap

### What we shipped

Pulse uses codexbar quota readings as a secondary signal. We do not pretend to know how operators behave at 70%, 80%, or 90% of their Pro/Max windows.

### What the literature supports

**Mechanics**: well-documented. Anthropic exposes 5-hour and 7-day windows; OpenAI exposes message-count limits per plan. Both products show progress UI as users approach a limit. Anthropic's March 2026 promo doubled the 5h limit off-peak; May 2026 launch doubled Claude Code's 5h limit and removed peak-hours reduction — strong signal that the company itself treats utilization as a UX-relevant variable.

### Gaps

No peer-reviewed work on user behavior change at rate-limit thresholds. Whole subfield missing.

---

## E. Severity bands (soft / hard)

### What we shipped

Two-level severity: `soft` is informational ("a readout would be appropriate"), `hard` is structural ("pause and confirm before continuing a long task").

### Why

Single-level "should readout?" loses information — operators on long architectural tasks need to distinguish "minor flag, can finish my thought" from "I'm in degraded zone, do not start a refactor now." Three-level (none / soft / hard) maps cleanly onto monitoring industry warning/critical conventions, doesn't proliferate (4 levels are harder to remember and easier to dismiss).

### What the literature supports

**Severity bands themselves are convention, not research.** AWS, PagerDuty, and SRE handbooks all use warning/critical pairs. No paper we found specifically validates 2 vs 3 vs 5 levels for agent self-monitoring.

---

## F. Project-policy decisions

These are decisions where the *direction* is supported by something — usually a failure mode in `FAILURE_MODES.md` — but the *specifics* are policy, not science.

- **Epistemic flag enforcement.** Three rules enforced server-side (mandatory flag, drift flag when position is late/near-context-limit, low-confidence flag when any state has confidence <0.4). The rules trade strict validation for forcing-function honesty.
- **Recommendation minimum length 10 chars.** Pure policy — anti-pattern guard against `"ok"`. Not research.
- **`session_id` defaulting to env var or `"default"`.** Operational convenience.
- **`metadata` as free-form dict.** Calibration substrate, intentionally unconstrained at v0.1.

---

## What we DON'T claim

- That readouts are calibrated (they're approximate self-reports)
- That intensity 0.7 means the same thing across models or sessions
- That mirror-mirror is the right tool for any specific operator workflow without testing
- That the design will survive v0.3 calibration without major revision

If any of the failure modes in `FAILURE_MODES.md` dominate in real use, the experiment is falsified. That outcome is informative, not bad.

---

## Bibliography

1. Liu, N., et al. (2023). *Lost in the Middle: How Language Models Use Long Contexts.* arXiv:2307.03172.
2. Kuratov, Y., et al. (2024). *BABILong: Testing the Limits of LLMs with Long Context Reasoning.* arXiv:2406.10149.
3. Modarressi, A., et al. (2025). *NoLiMa: Long-Context Evaluation Beyond Literal Matching.* arXiv:2502.05167.
4. Chroma Research. (2025). *Context Rot: A Report on Long-Context Performance.* trychroma.com.
5. Yao, S., et al. (2023). *ReAct: Synergizing Reasoning and Acting in Language Models.* ICLR 2023.
6. Shinn, N., et al. (2023). *Reflexion: Language Agents with Verbal Reinforcement Learning.* NeurIPS 2023.
7. Wang, G., et al. (2023). *Voyager: An Open-Ended Embodied Agent with Large Language Models.* arXiv:2305.16291.
8. Madaan, A., et al. (2023). *SELF-REFINE: Iterative Refinement with Self-Feedback.* NeurIPS 2023.
9. Liu, J., et al. (2025). *ReflAct: World-Grounded Decision Making in LLM Agents via Goal-State Reflection.* ACL 2025 (preprint).
10. Beyer, B., et al. *Site Reliability Engineering.* O'Reilly, Google.
11. AHRQ. *Alarm Fatigue: A Patient Safety Concern.* (Review.)
12. Nagrecha, S., & Baldwin, M. (2022). *Causal Effects of Cybersecurity Alert Fatigue.* (HCI study.)
13. AWS. *Recommended Alarms for CloudWatch.* (Documentation.)
14. Reeves, B., & Nass, C. (1996). *The Media Equation.* Cambridge University Press.
15. Edmondson, A. (1999). *Psychological Safety and Learning Behavior in Work Teams.* Administrative Science Quarterly 44(2).
16. Anthropic Interpretability Team. (2026). *Emotion Concepts and their Function in a Large Language Model.*

The full GPT-5 Pro DeepSearch report that surveyed and rated these sources (~40 minutes of research, May 2026) is preserved in the project's research notes.
