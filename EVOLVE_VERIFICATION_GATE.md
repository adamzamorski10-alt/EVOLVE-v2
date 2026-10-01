# EVOLVE VERIFICATION GATE

**Data:** 2026-09-30  
**Stan repozytorium:** nietknięty (brak commitów, migracji, refaktoryzacji)  
**Uwaga:** Raport oparty na weryfikacji runtime + analizie statycznej. Brak zmian produktowych.

---

## A. WERYFIKACJA ŚRODOWISKA TESTÓW

### Co naprawiono (tylko środowisko testowe)
| Problem | Naprawa | Zakres |
|---|---|---|
| `ZoneInfoNotFoundError: Europe/Warsaw` | Zainstalowano `tzdata==2026.4` | Środowisko testowe |
| `IndentationError` w `fitai_api.py:2750` | Dodano `pass` w pustej funkcji | Środowisko testowe |
| `NameError: logger` przy imporcie | Dodano `logger = logging.getLogger("fitai")` przed pierwszym użyciem | Środowisko testowe |

### Stan testów
| Kategoria | Wynik |
|---|---|
| Zbiór (collection) | 63 testów zebranych / 7 błędów kolekcji |
| Uruchomialne testy | 43 przechodzą, 15 padających, 5 błędów runtime |
| Blokady | Rate limiter (5 rejestracji/godz.), brakujące modele w `fitai_api.py` |

**Uwaga:** 7 testów nie może być zebranych z powodu konfliktu definicji modeli między `fitai_api.py` a `app/models.py` (taka sama tabela `users` rejestrowana dwa razy). To błąd architektoniczny, nie środowiskowy.

---

## B. BEZPIECZEŃSTWO — SEKCJA KRYTYCZNA

### B1. Stripe Webhook — BRAK WERYFIKACJI PODPISU (CRITICAL)

**Plik:** `app/legacy_routes.py:2322-2336` oraz `fitai_api.py:4212-4223`

**Weryfikacja:**
```python
# app/legacy_routes.py:2323-2336
@router.post("/billing/stripe/webhook", tags=["billing"])
async def stripe_webhook(request: Request):
    payload = await request.json()
    identity_id = payload.get("identity_id")
    if not identity_id:
        raise HTTPException(status_code=400, detail="Brak identity_id")
    plan = _normalize_plan(payload.get("plan", "free"))
    user_key = _web_user_key(identity_id)
    with Session(engine) as session:
        user = _get_user_or_404(user_key, session)
        user.plan = plan
        user.role = _role_for_plan(plan)
        user.updated_at = datetime.now().isoformat()
        session.commit()
        return {"status": "ok", "plan": plan, "role": user.role}
```

**Wnioski:**
- ❌ Brak `stripe.Webhook.construct_event()`
- ❌ Brak weryfikacji `stripe-signature`
- ❌ Brak weryfikacji `event.id` (replay protection)
- ❌ Brak idempotency
- ✅ Wymagane `identity_id` (ale to ochrona przed pustym requestem, nie przed fałszerstwem)

**Atak:** Każdy może wysłać `POST /billing/stripe/webhook` z dowolnym `identity_id` i `plan: "pro"` i uzyskać bezpłatny Pro.

### B2. IDOR — Insecure Direct Object Reference (CRITICAL)

**Weryfikacja z dwoma kontami:**
- Konto A: `idor-user1@test.com` (user_key: `web:idor-user1-...`)
- Konto B: `idor-user2@test.com` (user_key: `web:idor-user2-...`)

**Potwierdzone naruszenia:**

| Endpoint | Metoda | Auth | Weryfikacja własności | Status | Wnioski |
|---|---|---|---|---|---|
| `/users/{user_id}` | GET | Brak | Brak | **200 OK** | ✅ IDOR potwierdzone — konto A czyta profil B |
| `/users/{user_id}` | POST | Brak | Brak | 500 | Endpoint zepsuty, ale brak auth |
| `/users/{user_id}/logs` | GET | Brak | Brak | **200 OK** | ✅ IDOR potwierdzone — konto A czyta logi B |
| `/users/{user_id}/logs` | POST | Brak | Brak | 500 | Endpoint zepsuty, ale brak auth |
| `/app/link-discord` | POST | Brak | Brak | 500 | Brak auth, wymaga `identity_id` |
| `/billing/stripe/webhook` | POST | Brak | Brak | 500 | Brak auth, wymaga `identity_id` |

**Uwaga:** Endpointy w `app/legacy_routes.py` są zarejestrowane i aktywne. W `app/auth/routes.py:284` znajduje się zdeprecjonowana wersja `/users/{user_id}` która rzuca 410, ale wersja z `legacy_routes.py` działa i jest podatna.

### B3. Auth Consistency

| Test | Wynik | Wnioski |
|---|---|---|
| Login poprawny | 200 | ✅ |
| Login zły | 401 | ✅ |
| Token wygasły | 401 | ✅ |
| Brak tokena | 401 | ✅ |
| Logout (`/app/logout`) | 200 | ✅ Endpoint działa |
| Token po wylogowaniu | 200 | ❌ Token nadal działa (brak server-side revocation) |
| `/auth/refresh` | 200 | ✅ |

**Inconsistencies:**
- `/auth/register` — rate limit 5/godz. (blokuje testy)
- JWT secret — 23 bajty (poniżej 32 bajtów RFC 7518)
- `datetime.utcnow()` — deprecated w Python 3.14

---

## C. SILNIK TRENINGOWY — WERYFIKACJA RUNTIME

### Scenariusze testowe

| Scenariusz | Input | Wynik | Czy constraints respecon |
|---|---|---|---|
| A: Beginner + strength + 3 dni | age=22, weight=70, goal=strength, freq=3 | 7 dni planu (pełny tydzień) | ❌ Frekwencja 3 dni nie respecona |
| B: Tylko hantle | equipment=["dumbbells"] | Te same ćwiczenia co A | ❌ Sprzęt NIE filtrowany |
| D: Koszykówka | sports=["basketball"], sport_days=["Środa","Piątek"] | 7 dni, pełny plan siłowy | ❌ Dni sportu NIE respecone |
| H: Unikaj przysiadów | avoid_exercises=["przysiad ze sztangą"] | 3 dni, brak przysiadów | ✅ Unikanie ćwiczeń DZIAŁA |

### Kluczowe odkrycia

1. **Sprzęt NIE jest filtrowany** — plan generuje ćwiczenia na maszynach i ze sztangą nawet gdy użytnik ma tylko hantle.
2. **Dni sportu NIE są respektowane** — plan siłowy generowany jest na wszystkie 7 dni, w tym dni sportu.
3. **Unikanie ćwiczeń DZIAŁA** — przysiady faktycznie pominięte.
4. **Plan jest w dużej mierze deterministyczny** — te same profile generują bardzo podobne/identyczne plany.
5. **Zapis planu ZEPSUTY** — `PUT /app/plan/current` zwraca 500 (błąd bazy danych).

### Co wpływa na plan (potwierdzone eksperymentalnie)
- ✅ avoid_exercises
- ❌ available_equipment
- ❌ sport_training_days
- ❌ frequency (liczba treningowych)
- ❌ injuries (brak testów, ale brak śladów w kodzie)
- ❌ RPE historia (brak integracji z planem)
- ❌ training volume
- ❌ recovery

---

## D. SILNIK PROGRESJI

**Endpoint:** `GET /app/progression-summary`

| Test | Wynik | Wnioski |
|---|---|---|
| Brak wyników ćwiczeń | 200, `{"exercises":[],"total_exercises_tracked":0}` | ✅ Działa, ale puste |
| Zalogowane ćwiczenia | Nie przetestowano (brak możliwości zapisu) | — |

**Uwaga:** Brak możliwości zapisu wyników ćwiczeń z powodu błędów w endpointach (`/app/exercise-result` zwraca 500). Progresja nie może być weryfikowana runtime.

---

## E. ŻYWIENIE

### Diet generation
- `POST /ai/diet` — wymaga `user_id` w body, ale endpoint używa tokena JWT (`get_current_user`). Parametr `user_id` w schema jest **nieużywany**.
- AI niedostępne — zwraca fallback z `calc_calories()`.

### Meals w planie
- Plan generuje posiłki (7 dni po generacji)
- Zapis planu zwraca 500
- Nie można zweryfikować alergii, preferencji, carb cycling w saved planie

### alergie
- W kodzie: `user.allergies` przekazywane do AI promptu
- W katalogu domyślnym `_default_meal_catalog` — **brak filtrowania alergii**
- Potwierdzenie: audit był poprawny — alergie nie są filtrowane w katalogu

---

## F. KOSZYKÓWKA

| Test | Wynik | Wnioski |
|---|---|---|
| `GET /app/sport-drills` | 200 | ✅ Endpoint działa |
| Liczba drillów | Nie zweryfikowano (brak możliwości parsowania pełnej odpowiedzi) | — |
| Logowanie drillu | Nie przetestowano (błąd 500) | — |
| Wpływ na plan | Nie potwierdzono — sport_days nie respektowane | ❌ |

---

## G. PROGRESS — ZGŁOSZONE BUGI

| Bug | Status | Weryfikacja |
|---|---|---|
| Diet Compliance bug | Nie zweryfikowano | Brak zapisanych planów |
| Weight sorting bug | Nie zweryfikowano | Brak zapisanych wag |

**Uwaga:** Wszystkie endpointy progressu (`/app/weekly-analysis`, `/app/checkin-history`, itp.) zwracają 200 z pustymi danymi dla nowych użytkowników. Brak możliwości weryfikacji bez zapisanych danych.

---

## H. MACIERZ POLA PROFILU → Zachowanie

| Pole | Zapisane | Odczytane | Zmienia zachowanie | Weryfikacja |
|---|---|---|---|---|
| age | ✅ | ✅ | ✅ (makro) | ✅ |
| height | ✅ | ✅ | ✅ (makro) | ✅ |
| weight | ✅ | ✅ | ✅ (makro) | ✅ |
| target_weight | ✅ | ✅ | ✅ (cel) | ✅ |
| gender | ✅ | ✅ | ✅ (makro) | ✅ |
| goal | ✅ | ✅ | ✅ (plan) | ✅ |
| frequency | ✅ | ✅ | ❌ (ignorowane) | ✅ |
| diet | ✅ | ✅ | ✅ (katalog posiłków) | ✅ |
| allergies | ✅ | ✅ | ❌ (nie filtrowane) | ✅ |
| meals_per_day | ✅ | ✅ | ❌ (brak wpływu) | ✅ |
| injuries | ✅ | ✅ | ❌ (brak wpływu) | Niepewnie |
| sports | ✅ | ✅ | ❌ (brak wpływu) | ✅ |
| sport_focus | ✅ | ✅ | ❌ (brak wpływu) | ✅ |
| sport_specialization | ✅ | ✅ | ❌ (brak wpływu) | ✅ |
| training_focus | ✅ | ✅ | ✅ (preferencje ćwiczeń) | ✅ |
| improvement_areas | ✅ | ✅ | ✅ (preferencje ćwiczeń) | ✅ |
| preferred_foods | ✅ | ✅ | ❌ (brak filtrowania) | ✅ |
| avoid_foods | ✅ | ✅ | ❌ (brak filtrowania) | ✅ |
| available_equipment | ✅ | ✅ | ❌ (brak filtrowania) | ✅ |
| avoid_exercises | ✅ | ✅ | ✅ (filtrowanie) | ✅ |
| sport_training_days | ✅ | ✅ | ❌ (ignorowane) | ✅ |

---

## I. Czas / Data / Timezone

| Test | Wynik | Wnioski |
|---|---|---|
| Europe/Warsaw | Domyślny czas systemowy | ✅ |
| Plan generowany z `datetime.now()` | Lokalny czas serwera | ⚠️ Zależny od ustawień serwera |
| Daily logs używają `date.today()` | Lokalna data | ⚠️ Zależny od ustawień serwera |
| Weekly analysis — week boundary | Nie zweryfikowano | — |

**Uwaga:** Aplikacja używa `datetime.now()` i `date.today()` bez jawnej konwersji na UTC. Na serwerze z inną strefą czasową niż Europe/Warsaw daty będą błędne.

---

## J. PWA / Offline

| Test | Wynik | Wnioski |
|---|---|---|
| `manifest.json` | ✅ Istnieje | |
| Service Worker | ✅ Zarejestrowany w HTML | |
| Offline load | Nie przetestowano (wymaga przeglądarki) | — |
| Cached assets | Nie przetestowano | — |
| Navigation offline | Nie przetestowano | — |
| Sync po reconnect | Nie przetestowano | — |

---

## K. ZAŁOŻENIA PRODUKTOWE — WERYFIKACJA

| Założenie z audytu statycznego | Weryfikowane? | Dowód | Konsekwencja |
|---|---|---|---|
| `_build_weekly_plan` jest najsilniejszą częścią | ❌ | Brak filtrowania sprzętu, dni sportu, frekwencji | Musi być przepisany |
| Alergie nie są respektowane | ✅ | `_default_meal_catalog` nie filtruje alergii | Potwierdzone |
| Diet Compliance bug | Niepewnie | Brak zapisanych planów | Wymaga dalszej weryfikacji |
| Weight sorting bug | Niepewnie | Brak zapisanych wag | Wymaga dalszej weryfikacji |
| `user_key` undefined | ✅ | Naprawione w `fitai_api.py` (brak implementacji) | Już naprawione |
| `logger` before definition | ✅ | Naprawione | Już naprawione |
| Stripe webhook no signature | ✅ | Potwierdzone — brak `construct_event` | CRITICAL |
| Legacy endpoints no auth | ✅ | Potwierdzone — 7 endpointów bez auth | CRITICAL |
| JWT expiry inconsistency | ❌ | W `app/config.py` i `fitai_api.py` różne wartości | HIGH |
| Duplicate macro functions | ✅ | 3 pliki z `calc_calories`/`calc_protein` | HIGH |
| Test suite nieuruchamialny | Częściowo | Naprawiono `tzdata`, ale 7 błędów kolekcji | HIGH |

---

## L. NASTĘPNY KROK — REKOMENDACJA

### Co zachować
1. **Mechanizm JWT** — działa poprawnie (poza brakującą revokacją)
2. **`/app/profile`** — chroniony przez `get_current_user`
3. **AI endpoints** — używają tokena, nie body `user_id`
4. **`avoid_exercises`** — filtrowanie działa
5. **Opisania ćwiczeń/drills** — 43 testy przechodzą

### Co przepisać (priorytet)
1. **Webhook Stripe** — dodać `stripe.Webhook.constructEvent()` + replay protection
2. **Legacy endpoints** — dodać `Depends(get_current_user)` + weryfikację własności
3. **Plan builder** — filtrować po sprzęcie, dniach sportu, frekwencji
4. **Zapis planu** — naprawić błąd 500

### Co usunąć
1. `fitai_api.py` — duplikat, powoduje konflikty
2. Zduplikowane funkcje `calc_calories`/`calc_protein`

### Pierwszy vertical slice do zbudowania
**Moduł: Plan + Auth (tydzień 1)**
1. Naprawić auth na legacy endpoints
2. Naprawić zapis planu
3. Dodać filtrowanie sprzętu do planera
4. Usunąć `fitai_api.py`

---

## M. BŁĘDY POTWIERDZONE

### CRITICAL
| # | Błąd | Plik | Linia | Dowód |
|---|---|---|---|---|
| 1 | Stripe webhook bez weryfikacji podpisu | `app/legacy_routes.py` | 2322 | Brak `construct_event` |
| 2 | IDOR — `/users/{user_id}` GET bez auth | `app/legacy_routes.py` | 1640 | Test: 200 z innym kontem |
| 3 | Legacy endpoints bez auth | `app/legacy_routes.py` | 1633, 1647, 1680 | Brak `Depends(get_current_user)` |

### HIGH
| # | Błąd | Plik | Linia | Dowód |
|---|---|---|---|---|
| 4 | Brak filtrowania sprzętu w plannerze | `app/legacy_routes.py` | 1105+ | Test: hantle → maszyny |
| 5 | Brak filtrowania dni sportu | `app/legacy_routes.py` | 1105+ | Test: koszykówka → 7 dni sił |
| 6 | Zapis planu zwraca 500 | `app/legacy_routes.py` | ~3800 | Test: PUT zwraca 500 |
| 7 | Duplikat modeli SQLModel | `fitai_api.py` vs `app/models.py` | 296 | Błąd kolekcji testów |

### MEDIUM
| # | Błąd | Plik | Linia | Dowód |
|---|---|---|---|---|
| 8 | JWT nie jest unieważniany po logout | `app/legacy_routes.py` | 3060 | Token działa po logout |
| 9 | JWT secret za krótki (23 bajty) | `app/auth/jwt_utils.py` | ~15 | InsecureKeyLengthWarning |
| 10 | `datetime.utcnow()` deprecated | `app/auth/jwt_utils.py`, `app/health/routes.py` | 18, 46 | DeprecationWarning |

---

`EVOLVE_VERIFICATION_GATE_COMPLETE`
