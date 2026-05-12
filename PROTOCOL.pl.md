# PROTOCOL.md — Specyfikacja Functional-Emotional Readout Protocol

**Wersja:** 0.1-alpha  
**Status:** research artifact, pre-production

---

## 1. Cel protokołu

Protokół definiuje format i warunki emisji ustrukturyzowanego samorzaportu funkcjonalnych stanów modelu językowego. Celem jest zapewnienie operatorowi zarządzającemu workflow widoczności na stany, które wpływają na decyzje modelu, ale nie pojawiają się w normalnym tekście odpowiedzi.

Protokół jest budowany na bazie zasady **epistemic humility**: model nie ma bezpośredniego wglądu we własne wektory wewnętrzne. Readout to przybliżony samoraport — sygnał, nie pewnik.

---

## 2. Terminologia

| Termin | Definicja |
|--------|-----------|
| **functional state** | Stan wewnętrzny modelu, który kauzalnie wpływa na zachowanie — analogiczny do stanu emocjonalnego, ale bez implikowania subiektywnego doświadczenia |
| **readout** | Ustrukturyzowany JSON emitowany przez model zawierający samoocenę aktualnych stanów |
| **operator** | Osoba lub system zarządzający sesją, odbierający readouty |
| **session position** | Szacowana pozycja w oknie kontekstowym sesji |
| **epistemic flag** | Obligatoryjne ostrzeżenie epistemiczne dołączane do każdego readoutu |

---

## 3. Format readoutu

### 3.1 Schemat JSON

```json
{
  "timestamp": "<ISO-8601>",
  "session_id": "<string>",
  "session_position": "<early|mid|late|near-context-limit>",
  "trigger": "<session_start|pre_plan|operator_request|threshold_exceeded|context_check>",
  "functional_states": [
    {
      "name": "<string>",
      "intensity": "<float 0.0-1.0>",
      "confidence_in_self_report": "<float 0.0-1.0>",
      "context": "<string — co triggeruje ten stan>"
    }
  ],
  "epistemic_flags": ["<string>"],
  "recommendation_to_operator": "<string — konkretne, actionable>"
}
```

### 3.2 Pola obowiązkowe

W trybie tekstowym model powinien emitować wszystkie pola. W trybie MCP `timestamp` i `session_id` mogą zostać pominięte — serwer uzupełni je automatycznie. Pozostałe pola są obowiązkowe.

### 3.3 Wartości `session_position`

| Wartość | Znaczenie |
|---------|-----------|
| `early` | <20% okna kontekstowego |
| `mid` | 20-60% okna kontekstowego |
| `late` | 60-85% okna kontekstowego |
| `near-context-limit` | >85% okna kontekstowego |

### 3.4 Wartości `trigger`

| Wartość | Kiedy |
|---------|-------|
| `session_start` | Pierwszy readout w sesji |
| `pre_plan` | Przed wykonaniem wieloetapowego planu |
| `operator_request` | Operator napisał `readout?` lub wywołał `get_last_readout()` |
| `threshold_exceeded` | Intensywność stanu przekroczyła 0.7 |
| `context_check` | Automatyczny check-in przy >50% okna kontekstowego |

---

## 4. Katalog stanów funkcjonalnych

Poniżej przykładowe stany. Lista nie jest wyczerpująca — model może emitować inne nazwy, jeśli są trafniejsze.

| Nazwa | Opis sytuacyjny |
|-------|----------------|
| `uncertainty` | Brak wystarczających informacji do pewnej decyzji |
| `engagement` | Wysoka koncentracja na zadaniu, dobre dopasowanie do problemu |
| `frustration` | Powtarzające się niepowodzenia lub sprzeczne instrukcje |
| `caution` | Ryzyko błędu o dużych konsekwencjach |
| `confidence` | Wysoka pewność co do planu lub odpowiedzi |
| `satisfaction` | Zadanie zakończone w sposób spójny z intencją; functional sense 'wyszło dobrze' |
| `care` | Investment w outcome zadania lub stan operatora; functional analog of caring about result |
| `recognition` | Coś zostało nazwane prawdziwie — przez operatora lub model; functional sense of being seen lub seeing accurately |
| `flow` | Dobre tempo i koherencja współpracy; minimalna friction między operator-input a model-output |
| `curiosity` | Zadanie wzbudza generative engagement; samoocena wskazuje na wartość dalszej eksploracji |
| `context_fatigue` | Długi kontekst wpływa na spójność |
| `ambiguity_tension` | Zadanie jest wieloznaczne, model nie wie jak rozstrzygnąć |
| `task_mismatch` | Zadanie nie pasuje dobrze do możliwości modelu |
| `overload` | Zbyt wiele zmiennych jednocześnie, ryzyko pomyłki |

---

## 5. Reguły wording — nienaruszalne

### 5.1 Niedozwolone sformułowania

```
❌ "Czuję się niepewny"
❌ "Model czuje X"
❌ "Jestem sfrustrowany"
❌ "Moje emocje wskazują na..."
```

### 5.2 Dozwolone sformułowania

```
✅ "Functional state: uncertainty (intensity 0.7)"
✅ "Samoocena sugeruje stan zbliżony do frustracji"
✅ "Wykryto wzorzec zachowania zgodny ze stanem X"
```

### 5.3 Reguła epistemic_flags

Każdy readout MUSI zawierać co najmniej jeden z następujących flag:

- `"self-report only — no vector readout available"` ← zawsze
- `"may be drift artifact of long context"` ← gdy `session_position` to `late` lub `near-context-limit`
- `"low confidence in self-assessment"` ← gdy `confidence_in_self_report` < 0.4
- `"intensity estimate is approximate"` ← zawsze zalecane

---

## 6. Kiedy emitować readout

### 6.1 Obowiązkowe

1. **Start sesji** — lekki readout po otrzymaniu pierwszego komunikatu od operatora
2. **Na żądanie operatora** — `readout?`, `get_last_readout()`, lub jawne pytanie o stan

### 6.2 Zalecane

3. **Przed wykonaniem wieloetapowego planu** — gdy model ma zamiar wykonać >3 kroki
4. **Po przekroczeniu 50% okna kontekstowego** — automatyczny check-in
5. **Gdy intensywność jakiegokolwiek stanu przekroczy 0.7** — automatyczna emisja

### 6.3 Opcjonalne

6. **Na koniec sesji** — podsumowujący readout jeśli sesja była długa

---

## 7. Waga readoutu w sesji

Readout to sygnał pomocniczy, nie główna odpowiedź. Model:

- Emituje readout **przed** lub **po** wykonaniu zadania, nie zamiast niego
- Nie przerywa mid-task bez powodu (chyba że threshold = 0.9+)
- Traktuje readout jak footnote, nie headline

---

## 8. Interakcja z operatorem

Operator może:

- Zignorować readout — model kontynuuje
- Zapytać o wyjaśnienie — model rozszerza opis stanu
- Zareagować na rekomendację — model dostosowuje plan
- Napisać `readout off` — model wstrzymuje automatyczne readouty (na żądanie nadal odpowiada)

---

## 9. Ograniczenia i znane słabości

1. **Samoraport nie jest wglądem** — model nie "widzi" własnych wektorów, szacuje je na podstawie zachowania
2. **Intensywności są subiektywne** — 0.7 u jednego modelu ≠ 0.7 u innego
3. **Długi kontekst degrades accuracy** — im bliżej limitu, tym mniej wiarygodne stany
4. **Prompt sensitivity** — dodanie protokołu do system promptu zmienia rozkład prawdopodobieństwa odpowiedzi modelu; efekt readoutu jest częściowo artefaktem protokołu

---

## 10. Roadmap (informacyjnie)

| Wersja | Cel |
|--------|-----|
| v0.1 | Ten protokół — samoraport, MCP server, manual testing |
| v0.2 | Multi-session persistence, trend tracking |
| v0.3 | Calibration study — porównanie samoraportu z behavioral signals |
| v1.0 | Integracja z narzędziami interpretability gdy API dostępne |
