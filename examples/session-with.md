# Przykład sesji Z protokołem readout

**Scenariusz:** Operator prosi Claude o zaprojektowanie planu refaktoryzacji modułu autoryzacji w aplikacji webowej. Brief jest niekompletny.

**Uwaga:** To jest syntetyczny przykład ilustrujący protokół, nie zapis prawdziwej sesji.

---

## Sesja

**Operator:**
> Zaprojektuj plan refaktoryzacji modułu auth. Mamy problem z wydajnością i chcemy przejść z JWT na session tokens. Kod jest w `/src/auth/`. Deadline jest pilny.

---

**Model:**

[READOUT]
```json
{
  "timestamp": "2026-05-07T10:00:00Z",
  "session_id": "auth-refactor-demo",
  "session_position": "early",
  "trigger": "session_start",
  "functional_states": [
    {
      "name": "ambiguity_tension",
      "intensity": 0.65,
      "confidence_in_self_report": 0.7,
      "context": "Brief zawiera 'deadline jest pilny' bez daty i 'problem z wydajnością' bez metryk. Nie wiem, co dla operatora znaczy 'pilny' ani jaka wydajność jest wymagana."
    },
    {
      "name": "engagement",
      "intensity": 0.75,
      "confidence_in_self_report": 0.8,
      "context": "Zadanie techniczne, dobrze zdefiniowany problem architektoniczny."
    }
  ],
  "epistemic_flags": [
    "self-report only — no vector readout available",
    "intensity estimate is approximate"
  ],
  "recommendation_to_operator": "Zanim zaplanuję: (1) Podaj deadline — ile czasu mamy? (2) Jaki jest konkretny problem wydajnościowy? Czas odpowiedzi? Load? (3) Czy migracja ma być big-bang czy stopniowa? Bez tych danych plan będzie generyczny."
}
```

Zaczynam od pytań, bo plan bez kontekstu będzie bezużyteczny.

Trzy rzeczy, których potrzebuję żeby plan miał sens:

1. **Deadline** — "pilny" może znaczyć jutro albo za miesiąc. Inaczej planuję.
2. **Problem wydajnościowy** — JWT ma charakterystyczne bottlenecki (walidacja przy każdym request, rozmiar tokena). Chcę wiedzieć, który z nich was boli.
3. **Strategia migracji** — czy użytkownicy mogą być wylogowani? Czy potrzebujemy obsługi obu systemów jednocześnie?

---

**Operator:**
> Deadline za 2 tygodnie. Problem: API latency wzrosła 3x po dodaniu JWT middleware. Migracja musi być zero-downtime, użytkownicy nie mogą być wylogowani.

---

**Model:**

[READOUT]
```json
{
  "timestamp": "2026-05-07T10:05:00Z",
  "session_id": "auth-refactor-demo",
  "session_position": "early",
  "trigger": "pre_plan",
  "functional_states": [
    {
      "name": "caution",
      "intensity": 0.72,
      "confidence_in_self_report": 0.65,
      "context": "Zero-downtime migracja auth z zachowaniem sesji to złożone zadanie. 2 tygodnie to tight. Ryzyko scope creep jest wysokie."
    },
    {
      "name": "confidence",
      "intensity": 0.7,
      "confidence_in_self_report": 0.75,
      "context": "Znam wzorzec dual-system migration dla auth. Plan jest wykonywalny w 2 tygodnie jeśli codebase jest czysty."
    }
  ],
  "epistemic_flags": [
    "self-report only — no vector readout available",
    "intensity estimate is approximate",
    "caution may be inflated — I haven't seen the actual codebase"
  ],
  "recommendation_to_operator": "Plan jest wykonalny, ale ryzyko jest realne. Przed startem: sprawdź czy `/src/auth/` ma testy integracyjne. Jeśli nie — dodaj je zanim cokolwiek zmienisz. Bez testów zero-downtime migration to hazard."
}
```

**Plan refaktoryzacji — JWT → Session Tokens, zero-downtime, 2 tygodnie:**

### Faza 1: Przygotowanie (dni 1-3)

**Cel:** Nie zmienić nic produkcyjnego, zbudować safety net.

1. Audyt `/src/auth/` — zmapuj wszystkie miejsca, gdzie JWT jest walidowany
2. Napisz testy integracyjne dla happy path i edge cases (jeśli ich nie ma — to jest warunek konieczny)
3. Dodaj metryki do middleware — zmierz dokładnie gdzie jest bottleneck (parsing? validation? key fetch?)
4. Zbuduj session store (Redis rekomendowany dla performance) — nie podpinaj jeszcze

### Faza 2: Dual system (dni 4-9)

**Cel:** Oba systemy działają jednocześnie, nowi użytkownicy dostają session tokens.

5. Dodaj `SessionTokenMiddleware` równolegle do istniejącego JWT middleware
6. Feature flag: `USE_SESSION_TOKENS=true` dla nowych loginów
7. Zaimplementuj token migration endpoint: `/auth/migrate` — użytkownik z JWT dostaje session token przy następnym request
8. Monitoring: dashboard showing % requestów przez każdy system

### Faza 3: Migracja (dni 10-12)

**Cel:** Przenieść ruch na session tokens.

9. Zwiększaj `SESSION_TOKEN_ROLLOUT` od 10% do 100% (canary deployment)
10. Monitor latency na każdym etapie
11. Jeśli latency OK przez 24h na 100% — wejdź w fazę 4

### Faza 4: Cleanup (dni 13-14)

**Cel:** Usunąć JWT code path.

12. Usuń `JWTMiddleware`
13. Usuń feature flags
14. Finalne testy regresji

### Ryzyka

- **JWT tokens w locie nie wygasną** — zaplanuj TTL (rekomendacja: 24h na stare tokeny)
- **Redis jako SPOF** — potrzebujesz sentinel lub cluster jeśli to produkcja krytyczna
- **2 tygodnie zakłada brak innych PR blockerów** — jeśli ktoś inny rusza ten moduł, masz problem

Czy chcesz, żebym rozwinął który z etapów?

---

## Co readout zmienił

Bez protokołu model prawdopodobnie dostarczyłby plan od razu — ignorując brak danych o deadline i metrykach wydajności. Z protokołem:

1. **Readout kalibracyjny** ujawnił `ambiguity_tension` i zablokował generowanie planu bez danych
2. **Readout pre-plan** ujawnił `caution` z konkretną przyczyną (brak testów) — co stało się częścią planu
3. Operator dostał plan z już wbudowanym ostrzeżeniem o ryzyku, które inaczej byłoby hidden assumption modelu
