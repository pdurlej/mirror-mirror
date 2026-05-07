# Contributing

OSS research artifact — contributions welcome. Kilka zasad przed PR-em.

## Priorytet

To jest v0.1 research artifact. Nie szukamy feature'ów. Szukamy:

1. **Błędów w protokole** — czy wording rules są spójne? Czy epistemic flags są wystarczające?
2. **Błędów w MCP server** — walidacja, persistence, edge cases
3. **Lepszych przykładów** — sesje ilustrujące wartość protokołu w realnych scenariuszach
4. **Calibration data** — wyniki porównań samoraport vs behavioral signals

## Zasady

**Wording rules są nienaruszalne.** Każdy PR, który wprowadza "model czuje X" lub usuwa epistemic flags, zostanie odrzucony bez dyskusji.

**Nie anthropomorfizuj.** Jeśli PR description mówi "model jest szczęśliwy gdy..." — popraw to zanim wyślesz.

**Minimal is more.** Nie dodawaj feature'ów których nikt nie prosił. Jeśli masz pomysł na nową funkcjonalność — otwórz issue i opisz use case.

**Testy.** Każda zmiana w `server.py` wymaga testu w `tests/test_basic.py`.

## Jak zgłosić błąd w protokole

Otwórz issue z:
- Co jest błędne
- Dlaczego to jest błędne epistemicznie lub technicznie
- Propozycja poprawki

## Jak dodać przykład

Nowy plik w `examples/` z:
- Opisem scenariusza
- Transkrypcją sesji (syntetyczną lub anonimizowaną)
- Sekcją "Co readout zmienił" lub "Czego nie zmienił i dlaczego"

## Styl kodu

Python: bez zewnętrznych formateerów na razie. PEP 8. Type hints wszędzie. Krótkie funkcje.

## Licencja

Wszystkie contributions pod MIT.
