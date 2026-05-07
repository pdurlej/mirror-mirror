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
3. **Na żądanie** — `readout?` lub `get_readout()`
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

### License

MIT. See `LICENSE`.
