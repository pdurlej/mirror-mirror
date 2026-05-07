# Przykład sesji BEZ protokołu readout

**Scenariusz:** Identyczny jak w `session-with.md` — operator prosi o plan refaktoryzacji modułu auth.

**Cel tego pliku:** Pokazać co się dzieje bez protokołu — gdzie decyzje modelu są niewidoczne dla operatora.

**Uwaga:** To jest syntetyczny przykład ilustrujący protokół, nie zapis prawdziwej sesji.

---

## Sesja

**Operator:**
> Zaprojektuj plan refaktoryzacji modułu auth. Mamy problem z wydajnością i chcemy przejść z JWT na session tokens. Kod jest w `/src/auth/`. Deadline jest pilny.

---

**Model:**

Oto plan refaktoryzacji modułu auth z JWT na session tokens:

### Plan refaktoryzacji — JWT → Session Tokens

**Faza 1: Przygotowanie**
1. Audyt `/src/auth/` i zmapowanie JWT dependencies
2. Wybór session store (Redis lub memcached)
3. Przygotowanie infrastruktury

**Faza 2: Implementacja**
4. Zaimplementuj `SessionTokenService`
5. Dodaj session middleware równolegle do JWT
6. Przetestuj na środowisku staging

**Faza 3: Migracja**
7. Feature flag dla nowych loginów
8. Stopniowy rollout
9. Monitoring

**Faza 4: Cleanup**
10. Usuń JWT code path
11. Testy regresji

Czy mam rozwinąć któryś z etapów?

---

## Co się stało "pod spodem" (niewidoczne dla operatora)

Poniżej to, co model _mógłby_ zaraportować, gdyby miał protokół. Bez protokołu operator tego nie widzi.

### Ukryte założenia modelu

**Deadline "pilny":** Model zinterpretował jako "kilka tygodni" i zaprojektował plan liniowy. Gdyby deadline był 3 dni, plan byłby inny. Operator nie wie, że model dokonał tego wyboru.

**"Problem z wydajnością":** Model założył, że to typowy JWT overhead (parsing + validation). Możliwe, że problem jest gdzie indziej (np. network call do JWKS endpoint przy każdym request). Plan może nie rozwiązać właściwego problemu.

**Strategia migracji:** Model założył zero-downtime (bo to "bezpieczny default"), ale nie zapytał. Gdyby operator był OK z oknem maintenance, plan byłby prostszy o 30%.

**Testy:** Model nie wspomniał o testach. Jeśli ich nie ma, plan Faza 3 jest ryzykowny — ale model tego nie zasygnalizował.

### Skutki

Operator dostaje plan, który:
- Wygląda kompletnie
- Jest oparty na 3-4 ukrytych założeniach
- Nie sygnalizuje ryzyka braku testów
- Może nie rozwiązać właściwego problemu wydajnościowego

Model dostarcza **confidence theater** — wynik wygląda pewnie, bo nic nie jest podniesione jako wątpliwość.

---

## Porównanie side-by-side

| Aspekt | Z protokołem | Bez protokołu |
|--------|-------------|---------------|
| Brakujące dane | Model pyta zanim planuje | Model zakłada i planuje |
| Ryzyka | Widoczne w readoucie i planie | Ukryte w założeniach |
| Czas do użytecznego planu | Dłuższy (jedna runda pytań) | Krótszy pozornie |
| Jakość planu | Dostosowany do kontekstu | Generyczny |
| Ukryte decyzje modelu | Widoczne | Niewidoczne |
| Operator wie co model "myśli" | Tak | Nie |

## Kiedy brak protokołu jest OK

- Proste, dobrze zdefiniowane zadania
- Operator zna model i wie, że trzeba doprecyzować brief
- Iteracyjna praca gdzie korekta jest tania
- Zadania kreatywne bez wysokich kosztów błędu

## Kiedy protokół jest krytyczny

- Plan będzie realizowany bez review
- Brief jest niekompletny lub wieloznaczny
- Konsekwencje błędu są wysokie (produkcja, dane użytkowników)
- Długa sesja z wieloma decyzjami — ryzyko dryftu
- Multi-agent workflow gdzie output idzie wprost do następnego modelu
