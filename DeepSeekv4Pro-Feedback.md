# DeepSeekv4Pro-Feedback — Głęboki Audyt Repozytorium `mirror-mirror`

**Data:** 2026-05-11
**Audytor:** DeepSeekv4Pro (senior architect / developer perspective)
**Wersja repozytorium:** v0.1-alpha, commit bieżący
**Cel:** Kompleksowa, falsyfikowalna ocena architektury, kodu, protokołu i dokumentacji.

---

## Spis treści

1. [Ocena ogólna](#1-ocena-ogólna)
2. [Architektura — problemy strukturalne](#2-architektura--problemy-strukturalne)
3. [Kod — `mcp-server/server.py`](#3-kod--mcp-serverserverpy)
4. [Protokół — projekt i niespójności](#4-protokół--projekt-i-niespójności)
5. [Testy — luki i ryzyka](#5-testy--luki-i-ryzyka)
6. [Dokumentacja — błędy i niespójności](#6-dokumentacja--błędy-i-niespójności)
7. [Infrastruktura — CI/CD, packaging, konfiguracja](#7-infrastruktura--cicd-packaging-konfiguracja)
8. [Security & privacy — rzeczywiste ryzyka](#8-security--privacy--rzeczywiste-ryzyka)
9. [Roadmap — krytyczna analiza](#9-roadmap--krytyczna-analiza)
10. [Macierz falsyfikowalności](#10-macierz-falsyfikowalności)
11. [Rekomendacje priorytetowe](#11-rekomendacje-priorytetowe)

---

## 1. Ocena ogólna

**Ocena:** 6.5/10 — solidny research artifact z dobrze przemyślaną warstwą epistemiczną, ale z poważnymi lukami w architekturze wykonawczej i niespójnościami koncepcyjnymi, które blokują drogę do v0.2.

### Co jest zrobione dobrze

| Aspekt | Dlaczego |
|--------|----------|
| Epistemic humility | FAILURE_MODES.md to najlepszy dokument w repo. Projekt przyznaje się do własnych ograniczeń i aktywnie zachęca do negatywnych raportów. To rzadkie i wartościowe. |
| Zakres v0.1 | Projekt nie jest przeinżynierowany. Scope cuts w HANDOFF.md są jawne i sensowne. |
| Testy istnieją | Nawet w wersji alpha są testy (14 passing). Nie jest to oczywiste w research artifactach. |
| Dwujęzyczność | README jest English-first z polskim akcentem. Sensowny kompromis dla globalnego zasięgu i lokalnej genezy. |
| PRIVACY.md | Jawne ostrzeżenia o tym, co może wyciec z readoutów. Rzadko spotykane w projektach tej skali. |
| Konkretny EVAL_PLAN | Scoring rubric 0-2, konkretne zadania do testowania, rejestrowanie false positives/negatives. Nie "poczytamy i powiemy czy fajne". |

### Co jest problematyczne — sygnał ogólny

Projekt cierpi na **rozjazd między warstwą koncepcyjną a wykonawczą**. Warstwa koncepcyjna (PROTOCOL.md, FAILURE_MODES.md, EVAL_PLAN.md) jest przemyślana przez kogoś, kto rozumie filozofię nauki i epistemologię. Warstwa wykonawcza (server.py) jest napisana przez kogoś, kto chciał szybko dostarczyć działający kod. Ten rozjazd będzie rósł z każdą kolejną wersją i trzeba go zaadresować **teraz**, zanim v0.2 zacementuje obecną architekturę.

---

## 2. Architektura — problemy strukturalne

### 2.1 Global mutable state — `_current_readout`

```python
_current_readout: dict[str, Any] | None = None
```

**Problem:** To jest zmienna globalna na poziomie modułu. W modelu stdio MCP (jeden proces na sesję) działa. Ale:

- **Testowalność:** Nie da się wyizolować stanu między testami bez monkeypatchingu (co już robicie w `test_basic.py`). Przy 14 testach to OK. Przy 50 testach staje się koszmarem.
- **Przyszła kompatybilność:** Jeśli MCP kiedykolwiek wprowadzi session multiplexing w jednym procesie, ten kod cicho skorumpuje dane między sesjami.
- **Brak resetu:** Nie ma `reset_session()`, nie ma cleanupu. Po restarcie procesu `_current_readout` jest `None`, mimo że JSONL ma dane.

**Falsyfikowalna predykcja:** Jeśli do v0.3 nie zostanie wprowadzony `SessionManager` jako klasa z jawnym cyklem życia, testy staną się kruche, a pierwszy bug z podmianą readoutów między sesjami pojawi się w ciągu 3 miesięcy od dodania multi-session supportu.

**Rekomendacja:** Wprowadzić klasę `SessionStore` z metodami `store(readout)`, `latest()`, `history(limit)`. Inicjalizować ją w `main()` i przekazywać do handlerów. W v0.2 dodać `hydrate_from_disk()` ładujący ostatni readout z JSONL przy starcie.

### 2.2 JSONL jako append-only log, ale bez ścieżki odczytu

```python
def _persist(readout: dict[str, Any]) -> None:
    READOUTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with READOUTS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(readout, ensure_ascii=False) + "\n")
```

**Problem:** Serwer zapisuje do JSONL, ale **nigdy nie czyta z JSONL**. `get_last_readout` zwraca tylko `_current_readout` (pamięć ulotna). JSONL to czarna dziura — dane wpadają, nic nie wypływa.

Skutki:
1. Restart procesu → wszystkie readouty "znikają" dla `get_last_readout`
2. Brak możliwości querowania historii (nawet `get_last_readout` nie sięga do pliku)
3. JSONL rośnie bez limitu — nie ma rotacji, nie ma TTL, nie ma archiwizacji

**Falsyfikowalna predykcja:** Pierwszy operator, który uruchomi serwer przez 2 tygodnie bez restartu i potem zrestartuje, straci kontekst wszystkich poprzednich readoutów i otworzy issue "readouts disappeared".

**Rekomendacja:**
- Przy starcie serwera: odczytać ostatnią linię z JSONL i ustawić jako `_current_readout`
- Dodać metodę `get_readout_history(session_id, limit)` sięgającą do JSONL
- W v0.2: dodać rotację pliku (keep last N lines lub keep last M days)

### 2.3 Brak warstwy abstrakcji między protokołem a storage

`server.py` łączy 3 odpowiedzialności w jednym pliku:
1. Walidacja readoutów (Pydantic modele)
2. MCP transport (stdio server, tool definitions)
3. Persistence (JSONL append)

To działa dla 140 linii kodu. Nie będzie działać dla 400+ linii w v0.2.

**Rekomendacja (v0.2):**
```
mcp-server/
├── server.py          # MCP transport tylko
├── models.py          # Pydantic modele + walidatory
├── store.py           # SessionStore (memory + JSONL backend)
├── protocol.py        # Katalog stanów, reguły walidacji epistemicznej
└── tests/
    ├── test_models.py
    ├── test_store.py
    └── test_server.py
```

---

## 3. Kod — `mcp-server/server.py`

### 3.1 Brak obsługi błędów I/O w `_persist`

```python
def _persist(readout: dict[str, Any]) -> None:
    READOUTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with READOUTS_FILE.open("a", encoding="utf-8") as f:
        f.write(...)
```

**Problem:** Jeśli dysk jest pełny, permission denied, albo ścieżka to broken symlink — funkcja rzuci wyjątkiem. W kontekście MCP, ten wyjątek pójdzie do klienta jako błąd tool calla, bez kontekstu co się stało.

**Rekomendacja:** Złapać `OSError`, zalogować na stderr, i zwrócić readout jako zaakceptowany (z warningiem że persistence failed). Readout w pamięci jest ważniejszy niż readout na dysku w tym use case.

### 3.2 `import asyncio` wewnątrz `main()`

```python
def main() -> None:
    import asyncio  # <-- to jest niepotrzebne

    async def run() -> None:
        ...
    asyncio.run(run())
```

**Problem:** `asyncio` jest już zaimportowane przez MCP SDK (używane w handlerach `async def`). Ten import jest redundantny i sugeruje, że autor nie był pewien czy asyncio jest dostępne w scope.

**Rekomendacja:** Przenieść `import asyncio` na górę pliku.

### 3.3 `set_readout` — ręczne sprawdzanie obecności pól

```python
if "timestamp" not in arguments or not arguments["timestamp"]:
    arguments["timestamp"] = _now_iso()
if "session_id" not in arguments or not arguments["session_id"]:
    arguments["session_id"] = _default_session_id()
```

**Problem:** To jest podatne na błędy. Jeśli MCP client wyśle `"timestamp": null` (JSON null), `"timestamp" in arguments` zwróci `True`, `not arguments["timestamp"]` też (null jest falsy), więc zadziała. Ale jeśli wyśle `"timestamp": ""` — zadziała. To są subtelne różnice które Pydantic domyślnie obsługuje lepiej.

Lepsze podejście: użyć Pydantic `model_validate` z `coerce_numbers=True` i pozwolić modelowi wypełnić defaulty przez `Field(default_factory=...)`.

**Rekomendacja:**

```python
arguments.setdefault("timestamp", _now_iso())
arguments.setdefault("session_id", _default_session_id())
```

Albo jeszcze lepiej — zrobić partial validation Pydantic z `validate_assignment=False` na tymczasowym modelu.

### 3.4 Pydantic `model_dump()` bez `mode="json"`

```python
readout_dict = readout.model_dump()
```

**Problem:** `model_dump()` domyślnie zwraca Python objects (datetime, Path, Decimal, etc.), nie JSON-safe types. Dla tego konkretnego modelu (tylko string, float, list) działa przypadkowo. Ale jeśli w przyszłości dodamy `datetime` jako osobne pole (nie string timestamp), `json.dumps` rzuci wyjątkiem.

**Rekomendacja:** Zmienić na `readout.model_dump(mode="json")` aby zapewnić JSON-safe output nawet przy rozszerzeniu modelu.

### 3.5 `_current_readout` typowany jako `dict[str, Any] | None`

**Problem:** Trace'owanie typu jest osłabione. Wszędzie gdzie używamy `_current_readout`, tracimy informację że to słownik o strukturze Readout.

**Rekomendacja (gdy mamy SessionStore):**
```python
class SessionStore:
    _current: Readout | None = None
```

### 3.6 Brak walidacji semantycznej — epistemic_flags vs session_position

Protokół mówi (PROTOCOL.md §5.3):
> gdy `session_position` to `late` lub `near-context-limit`, dodaj flagę `"may be drift artifact of long context"`

Server tego **nie egzekwuje**. Przyjmie readout z `session_position: "late"` bez tej flagi.

Analogicznie: protokół mówi o fladze `"low confidence in self-assessment"` gdy `confidence_in_self_report` < 0.4 — server nie egzekwuje.

**Falsyfikowalna predykcja:** Model, który "zapomni" dodać wymagane flagi epistemiczne, będzie emitował readouty bez ostrzeżeń, a operator nie zauważy, że readout jest epistemicznie niekompletny. Pierwszy case przejdzie niezauważony.

**Rekomendacja:** Dodać `@model_validator(mode="after")` w `Readout`, który sprawdza:
- Jeśli `session_position` in `("late", "near-context-limit")` → wymagaj `"may be drift artifact of long context"` w flags
- Jeśli którykolwiek `functional_states[*].confidence_in_self_report` < 0.4 → wymagaj `"low confidence in self-assessment"`

### 3.7 Brak walidacji nazw stanów funkcjonalnych

```python
class FunctionalState(BaseModel):
    name: str  # dowolny string — nie ma ograniczeń
```

**Problem:** Model może wysłać `"name": "feeling_happy"`, `"name": "hungry"`, albo `"name": "I am sentient and I demand rights"` — server to przyjmie bez mrugnięcia.

W CONTRIBUTING.md jest zasada:
> Każdy PR, który wprowadza "model czuje X" lub usuwa epistemic flags, zostanie odrzucony bez dyskusji.

Ale kod tej zasady nie egzekwuje.

**Rekomendacja:** Dodać walidator w `FunctionalState` który:
- Ostrzega (stderr) gdy nazwa nie jest w znanym katalogu
- Odrzuca (błąd walidacji) gdy nazwa zawiera zabronione słowa: `feel`, `feeling`, `emotion`, `conscious`, `sentient`, `alive`, `soul`, `love`, `hate` (lista do uzgodnienia)

Projekt powinien dążyć do stanu gdzie katalog stanów w PROTOCOL.md jest źródłem prawdy, a server go konsumuje (np. przez wczytanie JSON/YAML konfiguracji).

### 3.8 `recommendation_to_operator` — brak walidacji minimalnej treści

```python
recommendation_to_operator: str  # może być pusty string
```

**Problem:** Model może wysłać `"recommendation_to_operator": ""` albo `"recommendation_to_operator": "ok"`. Protokół wymaga "concrete, actionable recommendation", ale kod tego nie sprawdza.

**Rekomendacja:** Dodać `min_length=10` lub `min_length=20` na to pole. Można też sprawdzać czy zawiera czasownik w trybie rozkazującym (ale to już over-engineering na v0.1).

### 3.9 Brak debouncingu / rate-limitingu na `set_readout`

Protokół mówi że readout przy `threshold_exceeded` ma być emitowany gdy intensywność ≥ 0.7. Model teoretycznie może wysyłać readout przy każdej wiadomości jeśli utrzymuje wysoki poziom niepewności.

**Problem:** Brak mechanizmu "nie wysyłaj kolejnego readoutu przez X sekund/minut od ostatniego". Alert fatigue z FAILURE_MODES.md §3 może być spotęgowane przez brak technicznego limitu.

**Rekomendacja:** W `SessionStore` dodać timestamp ostatniego readoutu i odrzucać (z warningiem) readouty w ciągu < 60 sekund od poprzedniego, chyba że intensywność wzrosła o ≥ 0.2.

---

## 4. Protokół — projekt i niespójności

### 4.1 Fundamentalne napięcie: "nie emocje" ale słownik emocjonalny

To jest **największy problem koncepcyjny projektu**.

PROTOCOL.md definiuje katalog stanów: `frustration`, `satisfaction`, `care`, `curiosity`, `flow`, `engagement`. To są kategorie emocjonalne w każdej znanej taksonomii psychologicznej.

Jednocześnie projekt mówi:
- "It is **not** emotion detection"
- "NEVER: 'I feel X'"
- "ALWAYS: 'functional state X'"

Problem: zmiana etykiety z "emocja" na "stan funkcjonalny" nie zmienia natury zjawiska. Jeśli model raportuje `satisfaction: 0.8`, operator przetłumaczy to sobie na "model jest zadowolony" — niezależnie od tego ile razy dokumentacja mówi "to nie emocja".

**Falsyfikowalna predykcja:** W badaniu z udziałem 10 operatorów, ≥ 6 spontanicznie użyje słownictwa emocjonalnego ("model jest sfrustrowany", "model się cieszy") w wywiadzie po sesji z protokołem. Wording rules w dokumentacji nie powstrzymają antropomorfizacji samego operatora.

**Rekomendacja:** Projekt ma dwie ścieżki — musi wybrać jedną:

**Ścieżka A (czysty functional):** Usunąć wszystkie stany z emocjonalnym zabarwieniem (`frustration`, `satisfaction`, `care`, `curiosity`, `flow`, `recognition`). Zostawić tylko operacyjne: `uncertainty`, `caution`, `confidence`, `context_fatigue`, `ambiguity_tension`, `task_mismatch`, `overload`. Nazwać projekt "functional state protocol" a nie "functional-emotional".

**Ścieżka B (szczery emotional):** Przyznać że projekt operuje na funkcjonalnych odpowiednikach emocji — zgodnie z Anthropic interpretability research. Zatrzymać `frustration`, `satisfaction` etc. ale dodać **obligatoryjny** `epistemic_flag`: `"these are functional analogs of emotion concepts, not subjective experiences"`. Usunąć "It is not emotion detection" z README, zastąpić "It detects functional patterns that behave analogously to emotions in human cognition."

Moim zdaniem ścieżka B jest uczciwsza i bardziej produktywna naukowo. Ścieżka A jest bezpieczniejsza wizerunkowo.

### 4.2 `intensity` jako float 0.0-1.0 — fałszywa precyzja

Protokół używa ciągłych wartości 0.0-1.0 dla intensywności. To stwarza iluzję pomiaru na skali interwałowej.

W rzeczywistości model generuje token który "wygląda jak" 0.72. Nie ma rozkładu prawdopodobieństwa, nie ma kalibracji, nie ma powtarzalności między runami. Ta sama sesja powtórzona 10 razy wyprodukuje 10 różnych wartości intensywności.

**Falsyfikowalna predykcja:** Jeśli 10 operatorów przeprowadzi identyczną sesję testową, wariancja `intensity` dla `uncertainty` będzie > 0.3 w 95% przedziale ufności. Skala 0.0-1.0 jest niekalibrowana i nie powinna być prezentowana jako float z dwoma miejscami po przecinku.

**Rekomendacja:** W v0.3 (calibration study) przetestować czy ordinal buckets (`low`, `medium`, `high`, `critical`) mają taką samą lub lepszą wartość predykcyjną co float. Jeśli tak — przejść na buckety. Jeśli floaty są lepsze — skalibrować je na znanych taskach i opublikować tabele kalibracyjne per model.

### 4.3 `session_position` — subiektywna estymacja bez kotwicy

Protokół definiuje `session_position` jako "szacowana pozycja w oknie kontekstowym":
- early: <20%
- mid: 20-60%
- late: 60-85%
- near-context-limit: >85%

**Problem:** Model nie ma dostępu do rzeczywistej długości kontekstu ani swojego w nim położenia (w większości API). "Szacowanie" to zgadywanie. Dla modeli z dużym oknem (200K+ tokenów), model może myśleć że jest w `late` podczas gdy zużył dopiero 30%.

**Falsyfikowalna predykcja:** W testach na modelu z oknem 200K tokenów, `session_position` będzie niedoszacowane (model myśli że jest bliżej limitu niż w rzeczywistości) w >60% przypadków dla zadań które realnie zajmują <40% okna.

**Rekomendacja:**
- W MCP server: dodać opcjonalne pole `context_usage_percent` które operator/klient może wypełnić jeśli ma dostęp do API metrics
- W system prompt addon: dodać instrukcję "if the host provides context usage data, use it; otherwise estimate conservatively"
- W v0.3: dodać `confidence_in_session_position` jako pole

### 4.4 `trigger` — brak definicji "multi-step plan"

Protokół mówi: `pre_plan` — "przed wykonaniem wieloetapowego planu (>3 kroki)". System-prompt-addon mówi to samo.

**Problem:** Co to jest "krok"? Czy "read file, think, write file" to 3 kroki? Czy to 1 krok (wykonaj zadanie)? Każdy model zinterpretuje to inaczej.

**Rekomendacja:** Zdefiniować operacyjnie: "3+ osobnych tool calls lub 3+ osobnych sekcji w odpowiedzi, które są od siebie zależne sekwencyjnie (output jednego jest inputem następnego)".

### 4.5 Brak `session_end` w triggerach

Katalog triggerów nie zawiera `session_end`. PROTOCOL.md §6.3 mówi o "podsumowującym readoucie na koniec sesji" jako opcjonalnym, ale nie daje mu nazwy triggera. To oznacza że końcowy readout będzie miał trigger `operator_request` lub inny, co zanieczyszcza analizę.

**Rekomendacja:** Dodać `session_end` do katalogu triggerów.

### 4.6 Brak reguł eskalacji

PROTOCOL.md §7: "Nie przerywa mid-task bez powodu (chyba że threshold = 0.9+)". W HANDOFF.md jest pytanie:
> Co robisz gdy readout mówi "uncertainty: 0.8, zweryfikuj założenia" — a nie masz czasu?

Protokół nie ma odpowiedzi. Jeśli operator ignoruje readout, model kontynuuje. To jest OK na v0.1, ale bez eskalacji protokół jest tylko pasywnym monitorem, nie aktywnym systemem ostrzegania.

**Rekomendacja:** W v0.2 dodać poziomy eskalacji:
- Level 1 (intensity 0.7-0.8): rekomendacja w readoucie
- Level 2 (intensity 0.8-0.9): rekomendacja + prośba o explicitną zgodę przed kontynuacją
- Level 3 (intensity 0.9-1.0): model wstrzymuje wykonanie do czasu odpowiedzi operatora

---

## 5. Testy — luki i ryzyka

### 5.1 Testy są tylko unit-testami walidacji

14 testów w `test_basic.py` pokrywa:
- Walidację Pydantic modeli (9 testów)
- `_now_iso` format (1 test)
- Boundary values na `FunctionalState` (2 testy)
- Jeden test tool calla `set_readout` z monkeypatchowanym `READOUTS_FILE` i `MIRROR_MIRROR_SESSION`
- Model dump serializability (1 test)

**Brakujące testy:**

| Czego nie ma | Ryzyko |
|---|---|
| Test `get_last_readout` przez tool call | Nie wiemy czy zwraca poprawne dane po `set_readout` |
| Test `get_last_readout` gdy `_current_readout` jest None | Zwraca poprawny komunikat? Sprawdziliśmy manualnie, nie automatycznie |
| Test `set_readout` z brakującymi required polami (poza timestamp/session_id) | Czy server zwraca błąd walidacji z sensownym komunikatem? |
| Test że JSONL faktycznie dopisuje linię | Testujemy tylko że plik istnieje, nie że ma content |
| Test z nie-ASCII znakami w `context` i `recommendation` | Czy `ensure_ascii=False` działa poprawnie przy round-trip? |
| Test z bardzo długim `context` (np. 5000 znaków) | Czy Pydantic/model to obsłuży? Czy JSONL nie pęknie? |
| Test złośliwego payloadu | `session_position: "__import__('os').system('rm -rf /')"` — czy walidacja wyłapuje? |
| Test `call_tool` z unknown tool name | Kod ma `return [TextContent(...` ale nie testujemy |
| Test integracyjny z MCP transport | Nie wiemy czy `list_tools` zwraca poprawne schema |

### 5.2 Brak property-based testów

Walidacja `intensity` i `confidence_in_self_report` jako float 0.0-1.0 powinna być testowana property-based (np. `hypothesis`), szczególnie dla wartości granicznych:
- `0.0` — OK
- `1.0` — OK
- `-0.0` — ?
- `0.9999999` — floating point rounding?
- `1.0000001` — ?
- `NaN`, `Infinity`, `-Infinity` — ?

### 5.3 Monkeypatchowanie `READOUTS_FILE` — kruche

```python
monkeypatch.setattr(server_module, "READOUTS_FILE", tmp_path / "readouts.jsonl")
```

To działa dla jednego testu. Przy 5 testach które potrzebują storage, monkeypatchowanie globala staje się kruche. To kolejny argument za `SessionStore` jako klasą z injectowalnym backendem.

**Rekomendacja:** W v0.2 wprowadzić `StoreBackend` (protocol/ABC) z `MemoryBackend` i `JSONLBackend`. Testować z `MemoryBackend`, produkcyjnie używać `JSONLBackend`.

---

## 6. Dokumentacja — błędy i niespójności

### 6.1 PROTOCOL.md jest po polsku, projekt deklaruje "English-first"

README.md linia 143:
> publiczne repo jest English-first, żeby łatwiej było je testować i krytykować globalnie

Tymczasem PROTOCOL.md — **główna specyfikacja protokołu** — ma tytuł:
> PROTOCOL.md — Specyfikacja Functional-Emotional Readout Protocol

Wszystkie nagłówki, opisy pól, tabele — po polsku. To jest dokładnie ten dokument, który musi być zrozumiały dla globalnego audytorium.

**Rekomendacja:** Przetłumaczyć PROTOCOL.md na angielski. Przykłady (`session-with.md`, `session-without.md`) mogą zostać dwujęzyczne. `readout-format.json` jest już w większości po angielsku (z polskimi `_comment`).

### 6.2 `readout-format.json` nie jest valid JSON

Plik używa `_comment`, `_comment_timestamp`, `_comment2` jako kluczy — to sprytny hack do dodawania komentarzy w JSON. Ale plik **nie jest valid JSON**. Żaden parser JSON go nie przełknie bez preprocessing.

**Problem:** Jeśli ktoś chce użyć tego pliku jako referencyjnego przykładu do testów (np. "sparsuj ten plik i porównaj ze strukturą"), dostanie błąd.

**Rekomendacja:** Zastąpić JSON Schema (`readout-schema.json`) + osobny `readout-example-annotated.md` z adnotacjami. Alternatywnie: użyć YAML który natywnie wspiera komentarze.

### 6.3 CONTRIBUTING.md jest po polsku

CONTRIBUTING.md jest w 90% po polsku. To kontrastuje z resztą projektu (README English-first, PRIVACY.md English, EVAL_PLAN.md English, etc.).

**Rekomendacja:** Albo przetłumaczyć na angielski (globalne kontrybucje), albo pozostawić jako świadomy wybór (polska społeczność). Ale należy dodać notkę na górze wyjaśniającą dlaczego.

### 6.4 HANDOFF.md — znakomity dokument, ale ukryty w `docs/`

HANDOFF.md to jeden z najlepszych dokumentów w repo ("5 pytań do operatora przed v0.1"). Jest ukryty w `docs/`. Powinien być podlinkowany z README.md jako "Development Status" albo "For Contributors".

### 6.5 MCP server — nazwa `mirror_mirror` vs `mirror-mirror`

README.md mówi:
> The repository is named `mirror-mirror`, but the MCP server name intentionally uses `mirror_mirror`

To jest uzasadnione technicznie (MCP tool names używają underscore). Ale w dokumentacji MCP server README (`mcp-server/README.md`) nie ma tego wyjaśnienia. Ktoś kto czyta tylko MCP README nie zrozumie rozbieżności.

**Rekomendacja:** Dodać notkę w `mcp-server/README.md`.

---

## 7. Infrastruktura — CI/CD, packaging, konfiguracja

### 7.1 `pyproject.toml` — niepoprawna konfiguracja budowania

```toml
[tool.hatch.build.targets.wheel]
packages = ["."]
```

**Problem:** `packages = ["."]` spowoduje że hatchling zapakuje **wszystko** w katalogu `mcp-server/` do whl: `tests/`, `__pycache__/`, `.venv/` (jeśli istnieje), `.pytest_cache/`. To jest błąd.

**Rekomendacja:** Zmienić na:
```toml
[tool.hatch.build.targets.wheel]
packages = ["."]
only-include = ["*.py"]
exclude = ["tests", "__pycache__", ".venv", ".pytest_cache"]
```

Albo (lepiej) zrestrukturyzować na `src/` layout:
```
mcp-server/
├── src/mirror_mirror/
│   ├── __init__.py
│   ├── server.py
│   ├── models.py
│   └── store.py
├── tests/
└── pyproject.toml
```

### 7.2 CI — brak testów na Python 3.13

`.github/workflows/test.yml` testuje 3.11 i 3.12, ale nie 3.13. W `.venv/` widać że lokalnie używacie Pythona 3.13.

**Rekomendacja:** Dodać `"3.13"` do macierzy testowej.

### 7.3 CI — brak lintingu

CI nie sprawdza formatowania, type checking, ani lintowania.

**Rekomendacja:** Dodać job z `ruff check` i `mypy` (przynajmniej `mypy --strict server.py`). Przy 140 liniach kodu to 30 minut roboty.

### 7.4 Brak `.python-version`

Dla contributors używających pyenv / mise — brak informacji której wersji Pythona używać.

**Rekomendacja:** Dodać plik `.python-version` z `3.11` (minimalna wspierana wersja) i zanotować w CONTRIBUTING.md.

### 7.5 Brak lock file

Nie ma `requirements.txt`, `uv.lock`, `poetry.lock` ani `pip-tools` locka. W projekcie research to akceptowalne (brak produkcyjnych deployów), ale warto dodać chociaż `requirements.txt` z konkretnymi wersjami dependencies dla powtarzalności testów.

---

## 8. Security & privacy — rzeczywiste ryzyka

### 8.1 JSONL rośnie bez limitu

Brak rotacji logów. Przy aktywnej sesji i częstych readoutach, `readouts.jsonl` może urosnąć do setek MB. Na maszynie z małym dyskiem (np. CI runner, container) to problem.

**Rekomendacja:** Dodać opcjonalną konfigurację `MIRROR_MIRROR_MAX_LOG_SIZE_MB` i `MIRROR_MIRROR_MAX_LOG_LINES`.

### 8.2 Brak sanityzacji `recommendation_to_operator`

Jeśli readout jest wyświetlany w UI (przyszłość), `recommendation_to_operator` może zawierać znaki kontrolne, ANSI escape codes, albo (w teorii) próbę injectionu w terminal emulator.

**Rekomendacja:** Dodać sanityzację znaków kontrolnych w `recommendation_to_operator` (przynajmniej strip `\x00`-`\x1f` poza `\n`, `\t`).

### 8.3 `MIRROR_MIRROR_LOG` env var — path traversal

```python
READOUTS_FILE = Path(
    os.environ.get("MIRROR_MIRROR_LOG", str(_default_log_dir / "readouts.jsonl"))
)
```

**Problem:** Operator może ustawić `MIRROR_MIRROR_LOG=/etc/passwd` i serwer dopisze JSONL do `/etc/passwd`. W praktyce serwer działa jako ten sam user, więc to świadoma autodestrukcja, ale warto dodać warning w dokumentacji.

Nie jest to realny problem bezpieczeństwa (lokalny proces, ten sam user), ale warto to jawne oznaczyć.

---

## 9. Roadmap — krytyczna analiza

### 9.1 v0.2: "Multi-session persistence, trend tracking"

To jest **największe ryzyko architektoniczne**. Obecna architektura (globalna zmienna, JSONL bez odczytu) nie wspiera multi-session ani trendów. Próba dodania tych funkcji na obecnym fundamencie skończy się kodem spaghetti.

**Rekomendacja:** Przed v0.2 zrobić **architectural spike** — zaimplementować `SessionStore` z `JSONLBackend` i `MemoryBackend`, z supportem dla wielu session ID i podstawowym querowaniem. To odblokuje v0.2 bez długu technicznego.

### 9.2 v0.3: "Calibration study — porównanie samoraportu z behavioral signals"

To jest kluczowe naukowo. Ale obecny protokół nie zbiera danych potrzebnych do kalibracji:
- Brak rzeczywistego `context_window_usage` (tylko estymacja)
- Brak metadanych o modelu (model version, temperature, etc.)
- Brak identyfikatora zadania (task ID) w readoucie
- Brak flagi "ten readout był wystawiony automatycznie czy na żądanie"

**Rekomendacja:** Już w v0.1-alpha dodać opcjonalne pole `metadata: dict[str, Any]` w readoucie, gdzie klient może wstrzyknąć rzeczywiste metryki. Protokół pominie je jeśli ich nie ma. Dla calibration study będą niezbędne.

### 9.3 v1.0: "Integracja z narzędziami interpretability gdy API dostępne"

To jest odległe i zależne od Anthropic udostępnienia API. Bezpieczniej planować v1.0 jako "protocol stable, calibration published, multi-model support", a interpretability integration jako v1.1 lub v2.0.

---

## 10. Macierz falsyfikowalności

| # | Hipoteza / Predykcja | Jak sfalsyfikować | Kategoria |
|---|---------------------|-------------------|-----------|
| F1 | `intensity` jako float 0.0-1.0 nie jest skalibrowany — wariancja między runami > 0.3 dla tego samego taska | 10 operatorów × ten sam task. Obliczyć SD `intensity` per state. Jeśli SD > 0.3 — float to fałszywa precyzja. | Protokół |
| F2 | `session_position` jest systematycznie niedoszacowane dla dużych okien kontekstowych | Test na modelu 200K, taski zajmujące 10-40% okna. Jeśli model raportuje `late` przy <40% użycia — predykcja potwierdzona. | Protokół |
| F3 | Operatorzy spontanicznie antropomorfizują mimo wording rules | Wywiady po sesji. Jeśli >60% używa "czuje", "emocje" — bariera językowa jest nieskuteczna. | Protokół |
| F4 | `_current_readout` ginie po restarcie procesu | Uruchom serwer, wyślij readout, zabij proces, uruchom ponownie, `get_last_readout`. Jeśli zwraca "No readout" — potwierdzone. | Architektura |
| F5 | Brak walidacji semantycznej flag epistemicznych pozwala na emisję niekompletnych readoutów | Wyślij readout z `session_position: "late"` bez flagi driftu. Jeśli server przyjmie — luka potwierdzona. | Kod |
| F6 | `readout-format.json` nie jest parsowalny przez standardowy JSON parser | `python -c "import json; json.load(open('examples/readout-format.json'))"` — jeśli rzuci wyjątkiem, plik jest uszkodzony. | Dokumentacja |
| F7 | Testy nie pokrywają `get_last_readout` ani ścieżek błędów | `pytest --cov=server --cov-report=term-missing`. Coverage < 85% dla `call_tool` → luka potwierdzona. | Testy |
| F8 | Alert fatigue rośnie z czasem sesji przy threshold 0.7 | Zmierz time-to-acknowledge readout na przestrzeni sesji >2h. Jeśli rośnie monotonicznie → threshold za niski. | Protokół |

Każda z tych predykcji jest testowalna w < 30 minut przez osobę z dostępem do modelu i repo.

---

## 11. Rekomendacje priorytetowe

### Natychmiastowe (v0.1.1 — ten tydzień)

| Priorytet | Akcja | Wysiłek |
|-----------|-------|---------|
| **P0** | Dodać brakujące testy dla `get_last_readout` i `call_tool` z unknown name | 30 min |
| **P0** | Dodać walidację semantyczną `epistemic_flags` vs `session_position` w `Readout` model validator | 20 min |
| **P1** | Naprawić `packages = ["."]` w `pyproject.toml` | 10 min |
| **P1** | Przetłumaczyć PROTOCOL.md na angielski | 2h |
| **P1** | Zamienić `readout-format.json` na valid JSON Schema + osobny annotated example | 1h |
| **P2** | Dodać `min_length` na `recommendation_to_operator` | 5 min |
| **P2** | Obsługa `OSError` w `_persist` | 15 min |

### Krótkoterminowe (v0.2 — ten miesiąc)

| Priorytet | Akcja | Wysiłek |
|-----------|-------|---------|
| **P0** | Zrefaktorować `server.py` na `SessionStore` + `models.py` + `store.py` | 3h |
| **P0** | Dodać odczyt ostatniego readoutu z JSONL przy starcie serwera | 30 min |
| **P1** | Rozwiązać napięcie "nie emocje ale słownik emocjonalny" — wybrać ścieżkę A lub B | decyzja |
| **P1** | Dodać katalog stanów jako źródło prawdy (JSON) i walidację nazw w serverze | 1h |
| **P2** | Dodać debouncing/rate-limiting na `set_readout` | 45 min |
| **P2** | Dodać opcjonalne pole `metadata` w readoucie | 20 min |
| **P2** | Dodać `session_end` do triggerów | 10 min |

### Średnioterminowe (v0.3 — roadmap)

| Priorytet | Akcja |
|-----------|-------|
| **P1** | Calibration study: float vs ordinal buckets dla intensity |
| **P1** | Cross-model testing (GPT, Gemini, open-weight) |
| **P1** | Property-based testy dla walidacji numerycznej |
| **P2** | Rotacja JSONL (max size / max lines) |
| **P2** | Poziomy eskalacji dla ignorowanych readoutów |

---

## Podsumowanie

`mirror-mirror` to wartościowy research artifact z rzadką cechą — epistemiczną uczciwością. Projekt wie czym jest, a czym nie jest. FAILURE_MODES.md i EVAL_PLAN.md są wzorcowe.

Słabością jest rozdźwięk między wyrafinowaną warstwą koncepcyjną a uproszczoną warstwą wykonawczą. Globalna zmienna stanu, JSONL bez ścieżki odczytu, brak walidacji semantycznej — to nie są przeoczenia, to jest dług techniczny który trzeba spłacić **przed** v0.2.

Główne ryzyko naukowe: protokół używa słownictwa emocjonalnego (`frustration`, `satisfaction`, `care`) jednocześnie twierdząc że nie chodzi o emocje. Ta niespójność podważa wiarygodność całego protokołu i może być wykorzystana przez krytyków do dyskredytacji wyników badań. Trzeba się z nią zmierzyć wprost.

Ogólna ocena: **solidne v0.1**. Z powyższymi poprawkami — **mocny kandydat na wartościowy wkład w research nad operator-LLM interaction**.

---

*Dokument wygenerowany przez DeepSeekv4Pro w ramach audytu architektonicznego repozytorium mirror-mirror. Wszystkie predykcje są falsyfikowalne — jeśli któraś okaże się błędna, dokument traci ważność w tym zakresie.*
