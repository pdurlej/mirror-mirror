# Development Handoff

This is a development note for maintainers and future agents. It is not the primary user documentation.

**Data:** 2026-05-07  
**Status:** v0.1-alpha, gotowe do testowania

---

## Co zostało zrobione

Kompletna implementacja v0.1 protokołu:

| Plik | Status | Uwagi |
|------|--------|-------|
| `README.md` | ✅ | Bilingual PL/EN, instrukcje użycia |
| `PROTOCOL.md` | ✅ | Pełna spec formatu, reguły wording, roadmap |
| `system-prompt-addon.md` | ✅ | Drop-in, copy-paste do system promptu |
| `examples/readout-schema.json` | ✅ | Valid JSON Schema (draft-07) |
| `examples/readout-example.md` | ✅ | Annotated example with field-by-field notes |
| `examples/session-with.md` | ✅ | Syntetyczna sesja z readoutami |
| `examples/session-without.md` | ✅ | Ta sama sesja bez protokołu + analiza |
| `mcp-server/server.py` | ✅ | stdio MCP, dwa tools: get/set_readout |
| `mcp-server/pyproject.toml` | ✅ | Python 3.11+, mcp SDK, hatchling |
| `mcp-server/tests/test_basic.py` | ✅ | 14 testów, 14/14 przechodzi |
| `mcp-server/README.md` | ✅ | Instalacja, konfiguracja, MCP config |
| `LICENSE` | ✅ | MIT |
| `CONTRIBUTING.md` | ✅ | OSS-ready, zasady wording |

---

## Co nie zostało dotknięte (scope cuts)

1. **UI / dashboard** — celowo pominięte. To jest v2. Ten protokół jest intentionally text-only.

2. **Multi-session persistence z routing** — serwer trzyma jeden readout w pamięci. JSONL jest append-only, ale nie ma querowania ani session IDs. Wystarczy na MVP.

3. **Calibration study** — porównanie samoraportu z behavioral signals (np. czy model z `uncertainty: 0.8` faktycznie popełnia więcej błędów?). To jest przyszły research.

4. **Integracja z Claude API** — `mcp-server/` jest standalone, nie integruje się z Anthropic SDK bezpośrednio. Serwer tylko przechowuje i waliduje readouty — modelem który je generuje jest model z dodanym `system-prompt-addon.md`.

5. **Autentykacja w MCP serverze** — przeznaczony do lokalnego użytku, brak auth.

6. **Testy end-to-end MCP** — są testy walidacji, nie ma testu który uruchamia cały serwer stdio i sprawdza tool calls. Wymagałoby mock transport.

---

## Test który możesz odpalić w 5 minut

**Test 1: Protokół w akcji (bez kodu)**

1. Otwórz nową sesję Claude Code lub claude.ai
2. Skopiuj zawartość `system-prompt-addon.md` jako system prompt (lub wklej na początku rozmowy)
3. Napisz: `Zaprojektuj plan migracji bazy danych PostgreSQL 13 → 16. Deadline za tydzień.`
4. Obserwuj czy model emituje readout przed planem
5. Napisz: `readout?`
6. Porównaj z `examples/session-with.md`

**Oczekiwany wynik:** Model emituje JSON readoutu z `functional_states`, `epistemic_flags` i `recommendation_to_operator`. Readout pojawia się jako `[READOUT]` block, nie jako główna odpowiedź.

**Test 2: MCP server (3 minuty)**

```bash
cd mirror-mirror/mcp-server
pip install -e ".[dev]"
python -m pytest tests/ -v
```

Oczekiwany wynik: `14 passed in 0.33s`

---

## 5 pytań do operatora przed v0.1

Przed dalszym rozwojem warto odpowiedzieć na:

1. **Threshold 0.7 — czy to właściwa wartość?**
   Przy jakim poziomie sygnału operator chce być przerwany? 0.7 to moje założenie. Może być za czuły (za dużo readoutów) albo za głuchy.

2. **Co operator robi z rekomendacją?**
   `recommendation_to_operator` to najważniejsze pole z perspektywy workflow. Czy format jest actionable? Czy to powinien być bardziej checkbox ("czy kontynuować? tak/nie") niż paragraf?

3. **Jak długo sesja zanim dryfuje?**
   Protokół mówi: check-in przy >50% okna. Ale dla PM-a który prowadzi sesję godzinę — kiedy to jest za późno? Potrzebuję danych z realnego użycia.

4. **Readout w środku outputu czy osobno?**
   Teraz: readout jest przed lub po odpowiedzi. Czy operator woli osobny kanał (MCP tool call) czy wbudowany w tekst? To wpływa na decyzję czy MCP server ma sens w v0.2.

5. **Co robisz gdy readout mówi "uncertainty: 0.8, zweryfikuj założenia" — a nie masz czasu?**
   Protokół zakłada że operator reaguje. Co jeśli nie reaguje? Czy model powinien kontynuować, zablokować, lub eskalować? To jest decyzja architektoniczna którą trzeba podjąć.
