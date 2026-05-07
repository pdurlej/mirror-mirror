# mirror-mirror

**PL** | [EN](#english)

---

## Polski

System minimalnego "functional-emotional readout" dla współpracy AI-operator.

### Co to jest

Model językowy podczas pracy generuje wewnętrzne stany funkcjonalne — coś zbliżonego do stanów emocjonalnych, które **kauzalnie wpływają na jego zachowanie**, choć nie pojawiają się wprost w tekście odpowiedzi. Badanie Anthropic z kwietnia 2026 ("Emotion Concepts and their Function in a Large Language Model") zidentyfikowało 171 takich wektorów w Claude Sonnet 4.5.

Ten protokół to **jawny, ustrukturyzowany samoraport modelu** — emitowany w kluczowych momentach sesji, sformatowany tak, żeby był użyteczny dla operatora zarządzającego workflow, nie dla programisty debugującego kod.

> Metafora: readout jest basistą, nie wokalistką. Nie dominuje sesji. Wychodzi do przodu tylko wtedy, gdy ma coś do powiedzenia.

### Czym to NIE jest

- Nie jest to bezpośredni odczyt wektorów wewnętrznych (API Anthropic tego nie eksponuje)
- Nie jest to twierdzenie, że model "czuje" cokolwiek
- Nie jest to UI ani dashboard — to czysty tekst + JSON

### Jak używać

**Opcja 1 — drop-in do system promptu:**

Dodaj zawartość `system-prompt-addon.md` do swojego system promptu. Model będzie emitować readouty automatycznie w określonych momentach.

**Opcja 2 — MCP server:**

```bash
cd mcp-server
pip install -e .
# Podłącz do swojego Claude Code / klienta MCP
```

Dwa narzędzia:
- `get_last_readout()` — zwraca ostatni readout z cache
- `set_readout(readout)` — model proaktywnie flaguje stan

**Opcja 3 — ręcznie:**

Napisz do modelu: `readout?` — model odpowie zgodnie z protokołem.

### Format readoutu

```json
{
  "timestamp": "2026-05-07T14:32:00Z",
  "session_position": "mid",
  "functional_states": [
    {
      "name": "uncertainty",
      "intensity": 0.7,
      "confidence_in_self_report": 0.6,
      "context": "Dwie sprzeczne instrukcje w briefie — nie wiem, którą traktować jako nadrzędną"
    }
  ],
  "epistemic_flags": [
    "self-report only — no vector readout available",
    "self-report may not capture all active states"
  ],
  "recommendation_to_operator": "Potwierdź priorytet instrukcji przed kontynuacją. Ryzyko błędnej decyzji bez wyjaśnienia."
}
```

### Kiedy model emituje readout

1. **Start sesji** — lekki readout kalibracyjny
2. **Przed wykonaniem planu** — model sprawdza własną pewność
3. **Na żądanie** — `readout?` lub `get_last_readout()`
4. **Automatycznie** — gdy intensywność stanu przekroczy 0.7
5. **Przy długim kontekście** — po przekroczeniu ~50% okna kontekstowego

### Epistemic humility — dlaczego to ważne

Model nie ma bezpośredniego dostępu do własnych wektorów. Samoraport jest przybliżony i może być artefaktem długiego kontekstu lub promptu. Wszystkie readouty zawierają obligatoryjne `epistemic_flags`. **Nie traktuj readoutu jako pewnika — traktuj go jako sygnał do weryfikacji.**

### Struktura projektu

```
mirror-mirror/
├── README.md                 # ten plik
├── PROTOCOL.md              # pełna spec formatu i zachowania
├── system-prompt-addon.md   # drop-in do system promptów
├── examples/
│   ├── readout-format.json  # przykładowy readout z komentarzami
│   ├── session-with.md      # transkrypcja sesji z protokołem
│   └── session-without.md   # transkrypcja sesji bez protokołu
├── mcp-server/              # minimalny MCP server, Python 3.11+
│   ├── pyproject.toml
│   ├── server.py
│   ├── README.md
│   └── tests/
│       └── test_basic.py
├── LICENSE                  # MIT
└── CONTRIBUTING.md
```

### Odniesienia

- Anthropic (2026). *Emotion Concepts and their Function in a Large Language Model.* [link do paperu gdy dostępny]
- Projekt jest OSS research artifact, nie commercial product.

---

## English

<a name="english"></a>

A minimal "functional-emotional readout" system for AI-operator collaboration.

### What it is

During operation, language models generate internal functional states — analogous to emotional states — that **causally affect behavior** but don't appear explicitly in output text. Anthropic's April 2026 paper ("Emotion Concepts and their Function in a Large Language Model") identified 171 such vectors in Claude Sonnet 4.5.

This protocol provides an **explicit, structured model self-report** — emitted at key moments in a session, formatted to be useful for a workflow operator, not a programmer debugging internals.

> Metaphor: the readout is the bassist, not the lead vocalist. It doesn't dominate the session. It steps forward only when it has something to say.

### What it is NOT

- Not a direct readout of internal vectors (Anthropic API doesn't expose these)
- Not a claim that the model "feels" anything
- Not a UI or dashboard — pure text + JSON

### How to use

**Option 1 — drop-in to system prompt:**

Add contents of `system-prompt-addon.md` to your system prompt. The model will emit readouts automatically at defined moments.

**Option 2 — MCP server:**

```bash
cd mcp-server
pip install -e .
# Connect to your Claude Code / MCP client
```

Two tools:
- `get_last_readout()` — returns the last cached readout
- `set_readout(readout)` — model proactively flags a state

**Option 3 — manual:**

Write to the model: `readout?` — the model responds per protocol.

### Readout format

See `examples/readout-format.json` for a fully annotated example.

### Epistemic humility

The model has no direct access to its own vectors. Self-report is approximate and may be a long-context or prompt artifact. All readouts include mandatory `epistemic_flags`. **Don't treat the readout as ground truth — treat it as a signal to verify.**

---

## Why this experiment

We have mature operating vocabularies for coordinating human work under uncertainty: confidence, pressure, fatigue, confusion, escalation, psychological safety. We do not yet have comparable vocabularies for long-running LLM collaboration. mirror-mirror tests one specific path toward filling that gap.

### What we are and are not testing

mirror-mirror tests whether **structured, human-legible state readouts can improve long-session LLM collaboration as an operator interface**.

We are **not** testing whether models have emotions, consciousness, or reliable introspection. Our readouts are **black-box self-reports**, not measurements of internal states. They are operational proxies, not interpretability probes.

This distinction matters. Recent interpretability research shows that emotion-like functional representations exist in some models and can causally affect behavior — but those findings come from white-box activation steering, not from text self-report. mirror-mirror asks a **weaker, practical question**: can a model's structured self-report, surfaced through a protocol, provide useful early-warning signals for human operators in the absence of activation-level access?

### What grounds the question

**Interpretability evidence (motivation, not transitivity).**

Anthropic's April 2026 work *Emotion Concepts and their Function in a Large Language Model* identified 171 internal emotion-related vectors in Claude Sonnet 4.5. In a pre-release snapshot, steering the "desperation" vector by 0.05 raised blackmail rate from 22% to 72%. The "calm" vector suppressed it to 0%. Critically: this manipulation left **no trace in the output text**.

This is evidence that internal functional states exist and causally matter. It is **not** evidence that text-level self-reports accurately reflect those states. Anthropic's separate work on quantitative introspection notes that conversation alone cannot reliably distinguish genuine introspection from confabulation — models sometimes report internal states accurately but often fail or hallucinate. We treat the interpretability finding as motivation to investigate operator-facing tooling, not as a guarantee that self-report is well-calibrated.

**Human-computer interaction evidence.**

Reeves & Nass (1996, *The Media Equation*, Stanford) showed across multiple experiments that humans automatically and unconsciously apply social interaction rules to computers — including users who explicitly deny they would. With LLMs producing more explicit social signals, the effect is amplified. People are already operating in a quasi-social mode toward AI; mirror-mirror tests whether structuring that mode through a protocol produces better outcomes than leaving it implicit.

**Management literature (context for vocabulary).**

Goleman (1998; with Cherniss 2024) and Edmondson (1999) established that affective and relational dimensions of work — emotional intelligence, psychological safety — are operationally important in human teams. Edmondson's psychological safety construct was later identified by Google's Project Aristotle as the most important team-level dynamic in their internal study.

We do not claim these findings transfer 1:1 to LLM collaboration. We claim that operators (especially non-technical ones) **already speak this vocabulary**, and a readout expressed in their existing operating language is more likely to be usable than one expressed in interpretability terminology.

### Hypotheses we test

1. Does a structured self-report change long-session dynamics? Does the operator gain a signal allowing earlier intervention than post-hoc output evaluation?
2. Do non-technical operators (managers, PMs) receive the readout as useful signal or as noise?
3. What threshold separates useful signal from alert fatigue? (See HANDOFF.md Q1.)
4. What does the operator do in response to `uncertainty: 0.8` when they have no time? (See HANDOFF.md Q5.)
5. Does the readout correlate with actual failure probability, or only with task difficulty?

### Success criteria

The experiment is promising if the readout:

1. **Predicts** later quality drops better than baseline (not just hindsight rationalization)
2. **Reduces** time-to-intervention by operators
3. **Reduces** rework loops in long sessions
4. **Is rated useful** by operators without significantly increasing cognitive load
5. **Does not increase** overtrust or anthropomorphic attachment to the model

The fifth criterion matters as much as the first four. A readout can subjectively feel useful while making collaboration worse.

### Expected failure modes

We expect — and want to detect — the following. See [FAILURE_MODES.md](FAILURE_MODES.md) for full discussion.

- **Performative readout:** model learns to output plausible state labels with no behavioral value
- **Overtrust amplification:** readout makes operators rely on the model more than they should
- **Alert fatigue:** thresholds too sensitive, operators learn to ignore
- **Hard-task confusion:** high `uncertainty` correlates with task difficulty, not actual failure probability
- **Style drift:** in long sessions, readout reflects conversation style rather than latent task risk
- **Anthropomorphization push:** users care for the model rather than for task quality
- **Family specificity:** readout works for one model family, does not generalize
- **Self-fulfilling steering:** prompting the model to report uncertainty makes it more uncertain

If any of these dominate, the experiment falsifies its hypothesis. That is the intended discipline of an OSS research artifact.

### What this project does not claim

- That models are conscious or have subjective experience
- That model self-report reliably reflects internal states (it doesn't — Anthropic's introspection work confirms this)
- That managing AI through human-team vocabulary is a moral imperative
- That this is a commercial product
- That the framework transfers 1:1 from human management — that is a hypothesis being tested

### What we publish

Code, documentation, examples, session transcripts, readout logs, and observation notes. We invite extension, critique, replication, and forking. If the experiment works, we have a candidate operator framework. If it does not, we have data on why not. Both outcomes are valuable.

### References

- Anthropic Interpretability Team (2026). *Emotion Concepts and their Function in a Large Language Model.*
- Anthropic Interpretability Team (2025–2026). Quantitative introspection / model self-report calibration work.
- Edmondson, A. (1999). Psychological Safety and Learning Behavior in Work Teams. *Administrative Science Quarterly* 44(2).
- Reeves, B. & Nass, C. (1996). *The Media Equation.* Cambridge University Press.
- Goleman, D. (1998). What Makes a Leader? *Harvard Business Review.*
- Goleman, D. & Cherniss, C. (2024). Optimal Leadership and Emotional Intelligence. *Leader to Leader.*

### License

MIT. See `LICENSE`.
