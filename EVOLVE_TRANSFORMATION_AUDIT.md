# EVOLVE TRANSFORMATION AUDIT — RAPORT KOŃCOWY

> **Uwaga:** To jest wyłącznie raport z audytu. Żadne zmiany nie zostały wprowadzone.
> **Status:** Discovery / Audit / Product Design — bez implementacji.

---

## 1. AUDYT CAŁEGO PROGRAMU — INWENTARYZACJA

### 1.1 Stack technologiczny

| Warstwa | Technologia | Ocena |
|---|---|---|
| Backend | FastAPI + SQLModel + SQLite | Działa, ale SQLite nie jest skalowalne dla SaaS |
| Frontend | Monolityczny `index.html` (~25k linii) + Tailwind CDN | Działa, ale trudne w utrzymaniu |
| Auth | JWT własnej implementacji + opcjonalnie Netlify Identity | Działa, brak MFA/SSO |
| AI | Groq (primary) + Gemini (fallback) | Działa, deprecated Gemini SDK |
| Billing | Stripe przez Netlify Functions | Placeholder, nie testowany |
| PWA | Service Worker + manifest | Działa, brak offline-first |
| Hosting | Render (backend) + Netlify (frontend) | Działa |

### 1.2 Główne moduły

| Moduł | Pliki | Status techniczny | Status produktowy |
|---|---|---|---|
| Auth/Rejestracja | `app/auth/*` | Działa | KEEP |
| Profil użytkownika | `app/models.py`, `app/fitness/routes.py` | Działa | KEEP + IMPROVE |
| Plan tygodniowy | `app/legacy_routes.py` + `app/plan/routes.py` | Działa | REWORK |
| Mój Dzień | `app/fitness/routes.py` + `index.html` | Działa częściowo | REWORK |
| Dieta | `_default_meal_catalog`, `calc_daily_macros` | Działa | IMPROVE |
| Trening | `_exercise_pool`, `_build_weekly_plan` | Działa | KEEP + IMPROVE |
| Sport (Koszykówka) | `SPORT_DRILLS_DB`, `DrillResultDB` | Działa ograniczenie | KEEP + EXPAND |
| Postępy | `app/legacy_routes.py:2838+`, `index.html:4054+` | Działa | REWORK |
| Gamification (XP/Streak) | `app/fitness/calculations.py` | Działa | IMPROVE |
| AI (Kitchen, Analysis) | `app/ai/*`, `app/legacy_routes.py:2415+` | Działa | DEFER |
| Discord/Notifications | `app/notifications/*` | Działa | MOVE/REMOVE |
| Billing/Subskrypcje | `app/legacy_routes.py:2311+` | Placeholder | REMOVE |

---

## 2. "MÓJ DZIEŃ" — AUDYT SZCZEGÓŁOWY

### 2.1 Co istnieje

**Backend:**
- `GET /app/day/today` — pobiera dzienny log, scala z planem tygodniowym
- `POST /app/day/item/toggle` — zaznaczanie posiłków/ćwiczeń
- `POST /app/day/item/add` — dodawanie custom posiłków/ćwiczeń
- `POST /app/day/item/swap` — zamiana na alternatywę
- `_sync_day_log_fields()` — przelicza kcal/protein z zaznaczonych posiłków

**Frontend (`index.html:1909-2077`):**
- Nagłówek z datą i postępem procentowym
- Karty: Kalorie, Białko, Aktywności
- Sekcja "Plan na dziś" z posiłkami i treningiem
- RPE slider
- Podsumowanie dnia / inteliggentne sugestie
- Modale do dodawania posiłków/ćwiczeń

### 2.2 Problemy

| Problem | Priorytet | Opis |
|---|---|---|
| **Brak klarownej hierarchii** | CRITICAL | Użytkownik nie widzi w 5 sekund co ma zrobić |
| **Plan nie jest "centralnym elementem"** | CRITICAL | Mój Dzień pokazuje listę, ale nie kieruje |
| **Sugestie są słabe** | HIGH | "Rozpocznij dzień od pierwszego zadania" — nie personalizowane |
| **Brak czasu** | HIGH | Nie ma "o której" ma rozpocząć trening |
| **Brak miejsca** | HIGH | Nie ma "gdzie" (siłownia/hala) |
| **Brak kontekstu** | HIGH | Nie ma "dlaczego" tego treningu |
| **Duplikacja danych** | MEDIUM | `meals_json` + `custom_meals_json` — złożone |
| **Brak quick actions** | MEDIUM | Brak przycisków do szybkich akcji |

### 2.3 Co zostaje / co znika / co powstaje

**CO ZOSTAJE:**
- Toggle posiłków/ćwiczeń
- Podsumowanie kalorii i białka
- RPE slider
- Podstawowa struktura logu

**CO USUWAMY:**
- Samodzielne dodawanie posiłków bez kontekstu planu
- Ogólne "Podsumowanie dnia" jako placeholder

**CO DODAJEMY:**
- **EVOLVE TODAY HEADER**: "Dzień 3/7 — Poniedziałek"
- **PRIMARY ACTION CARD**: "Trening siłowy — 16:00, Siłownia"
- **QUICK ACTIONS**: "Zaloguj trening", "Zaloguj posiłki", "Check-in"
- **CONTEXT CARD**: "Dlaczego dziś klatka? Bo wczoraj była plecy"
- **TIME & PLACE**: Godzina i lokalizacja treningu

---

## 3. DIETA — AUDYT

### 3.1 Generowanie diety

**Co działa:**
- Algorytm generuje 7-dniowy plan z unikalnymi posiłkami
- Carb cycling działa (heavy/moderate/rest)
- Makra są poprawne matematyczcznie

**Co jest błędne:**
- **Brak filtracji alergii** — `_default_meal_catalog` NIE filtruje alergii
- **Preferencje są słabe** — `preferred_foods` filtruje po substringie, co jest niedokładne
- **Meal catalog jest hardkodowany** — 35 posiłków na dietę, brak rozbudowy
- **Brak pełnych makroskładników** — tylko kcal, brak P/C/F na posiłek
- **Duplikacja kodu** — `_default_meal_catalog` powtórzona w `legacy_routes.py` i `fitai_api.py`

### 3.2 Biblioteka posiłków

**Aktualny stan:**
- Backend: hardcoded dict w Pythonie
- Frontend: `MEAL_DB` w JavaScript + `fitai_seed_data.js`
- Brak struktury DB, brak API do zarządzania

**Problemy:**
- Brak struktury DB
- Brak wersjonowania
- Brak możliwości dodawania własnych przez użytkowników
- Duplikacja między backend a frontend

### 3.3 Kitchen AI

**Co działa:**
- `/app/fridge-chef` — generuje przepis z lodówki
- `/app/kitchen/generate` — generuje 4 przepisy w JSON
- `/app/meal-prep-plan` — plan zakupów + batch cooking

**Problemy:**
- Używa deprecated `google.generativeai`
- Bardzo duży plik `legacy_routes.py` (~3090 linii)
- Brak cache'owania odpowiedzi AI
- Brak rate limiting per-user
- Auth inconsistency: `/app/fridge-chef` używa JWT, `/app/kitchen/generate` używa `identity_id`

### 3.4 Rekomendacja modułu Nutrition

**Docelowy model:**
1. **Meal Library w DB** — zamiast hardcoded dict
2. **Meal Templates** — zamiast konkretnych posiłków
3. **Portion-based scaling** — 0.5 / 1 / 1.5 / 2 porcje
4. **Full macros per meal** — kcal + P + C + F
5. **Allergy/preference filtering** — na poziomie DB query
6. **User-generated meals** — możliwość dodawania własnych

---

## 4. TRENING — AUDYT

### 4.1 Generowanie treningu

**Algorytm (`_build_weekly_plan`):**
- Wybór partii mięśniowej na dzień
- 4 ćwiczenia z przetasowanej puli
- Alternatywy z tej samej partii + 1 z sąsiedniej
- Carb cycling integracja
- Sport sessions zastępują trening siłowy

**Czy zależy od profilu?**

| Paramet | Wykorzystany | Wpływ |
|---|---|---|
| Cel (masa/redukcja) | Tak | Kalorie, nie trening |
| Wiek | Nie | — |
| Płeć | Nie | — |
| Wzrost | Nie | — |
| Masa | Nie (poza kaloriami) | — |
| Poziom zaawansowania | Nie | — |
| Historia treningów | Tak (progression enrichment) | Sugestie ciężaru/powtórzeń |
| RPE | Tak (suggest_progression) | Progresja |
| Objętość | Nie | — |
| Częstotliwość | Nie | — |
| Dostępność | Nie | — |
| Lokalizacja | Nie | — |
| Sprzęt | Częściowo (avoid_exercises) | Filtrowanie |
| Preferencje | Tak (training_focus) | Wybór partii |
| Ograniczenia | Częściowo (avoid_exercises, injuries) | Filtrowanie |
| Sport | Tak | Sport sessions |
| Priorytety | Nie | — |
| Regeneracja | Nie | — |

**Wnioski:**
- Plan generowany jest deterministyczny na tydzień
- Brak adaptacji do zaawansowania
- Brak uwzględnienia sprzętu (poza avoid_exercises)
- Brak dostosowania do dostępności

### 4.2 Adaptacja

**Co działa:**
- `_enrich_exercises_with_progression` dodaje sugestie ciężaru/powtórzeń
- `suggest_progression` analizuje RPE z ostatnich 3 sesji
- `_check_overload` wykrywa >20% wzrost wolumenu

**Co nie działa:**
- Sugestie nie zmieniają automatycznie przyszłych planów
- Użytkownik musi ręcznie wprowadzić zmiany
- Brak automatycznej korekty planu na podstawie wyników
- Progresja działa tylko na RPE, nie na objętość/ciężar

### 4.3 Atlas ćwiczeń

**Aktualny stan:**
- 70+ ćwiczeń w `_exercise_pool()`
- 9 grup mięśniowych
- Każde ćwiczenie ma: name, sets, reps, notes, how_to
- `EXERCISE_HOW_TO` w `exercise_descriptions.py` — ~50 wpisów

**Problemy:**
- Brak `muscle_group` w exercise pool (tylko jako key w dict)
- Brak `equipment` w exercise pool
- Brak `difficulty` w exercise pool
- Brak `video_url` w exercise pool
- `how_to` w exercise pool + `EXERCISE_HOW_TO` — duplikacja
- Brak id dla ćwiczeń

### 4.4 Rekomendacja modułu Training

**Docelowy model:**
1. **Exercise DB** — zamiast hardcoded dict
2. **Fields**: id, name, muscle_group, equipment, difficulty, description, video_url, alternatives
3. **Deterministic progression engine** — automatyczne dostosowywanie planu
4. **Equipment-aware** — filtrowanie po dostępnym sprzęcie
5. **History-based selection** — pomijanie ćwiczeń z niskim RPE (za łatwe) lub wysokim (za trudne)

---

## 5. SPORT — PRIORYTET: KOSZYKÓWKA

### 5.1 Aktualny stan

**Drill Database:**
- `SPORT_DRILLS_DB` — tylko koszykówka, 3 kategorie (rzuty, drybling, obrona)
- `_SPORT_DRILL_CATALOG` — 25+ drilli, wiele sportów (bezpieczna baza w `fitness/routes.py`)

**Drill Logging:**
- `DrillResultDB` — przechowuje wyniki
- `POST /app/drill-result` — logowanie
- `GET /app/drill-history` — historia
- `suggest_drill_progression` — propozycja zwiększenia prób

**Problemy:**
- Tylko 10 drilli koszykarskich w `SPORT_DRILLS_DB`
- Brak struktury DB dla drilli
- Brak video w większości drilli
- Brak poziomów trudności
- Brak connecta z treningiem siłowym

### 5.2 Docelowy Basketball Hub

```
Sport Hub (Koszykówka)
├── Profil Koszykarski
│   ├── Pozycja (Point/Shooting/Small/Power/Center)
│   ├── Poziom (Początkujący/Średniozaawansowany/Awansowany)
│   ├── Mocne strony
│   ├── Słabe strony
│   └── Cele sportowe
├── Assessment
│   ├── Testy fizyczne (sprint, skok, zmęczenie)
│   ├── Testy techniczne (rzuty, drybling)
│   └── Wyniki i rekomendacje
├── Drille
│   ├── Przypisane na dziś/tydzień
│   ├── Historia
│   ├── Progresja
│   └── Rekomendacje
├── Statystyki
│   ├── Accuracy %
│   ├── Czas wykonania
│   ├── Trendy
│   └── Porównania
└── Trening Sportowy
    ├── Plan sesji
    ├── Logowanie
    └── Analiza
```

---

## 6. POSTĘPY — AUDYT

### 6.1 Co istnieje

**Backend:**
- `GET /app/weekly-analysis` — 7-dniowy przegląd
- `GET /app/stats` — agregacja postępów (waga, objętość, compliance)
- `GET /app/progression-summary` — progresja dla wszystkich ćwiczeń

**Frontend:**
- Wykresy: waga, objętość, compliance, heatmapa, wellness
- KPI: zmiana wagi, średnie RPE, cel wagowy
- AI Insights

### 6.2 Problemy

| Problem | Priorytet | Opis |
|---|---|---|
| **Za wiele wykresów** | HIGH | Użytkownik nie wie co zobaczyć |
| **Brak jasnych pytań** | HIGH | Każdy wykres powinien odpowiadać na pytanie |
| **Diet Compliance nie działa** | CRITICAL | Liczy dni z `food` != null, ale `food` to text, nie boolean |
| **Weight trend może być błędny** | MEDIUM | `[:14]` na nieposortowanej liście |
| **Brak trend lines** | MEDIUM | Wykresy pokazują punkty, nie trendy |
| **Brak predictions** | MEDIUM | Nie prognozuje osiągnięcia celu |

---

## 7. PROFIL — AUDYT

### 7.1 Pola w UserDB

| Pole | Istnieje | Zapisane | Używane | Gdzie | Potrzebne |
|---|---|---|---|---|---|
| name | ✅ | ✅ | ✅ | Wszędzie | ✅ |
| age | ✅ | ✅ | ✅ | calc_calories | ✅ |
| height | ✅ | ✅ | ✅ | calc_calories | ✅ |
| weight | ✅ | ✅ | ✅ | calc_calories, checkin | ✅ |
| start_weight | ✅ | ✅ | ⚠️ | Tylko przy rejestracji | ✅ |
| target_weight | ✅ | ✅ | ✅ | UI, stats | ✅ |
| gender | ✅ | ✅ | ✅ | calc_calories | ✅ |
| goal | ✅ | ✅ | ✅ | Makro, plan | ✅ |
| frequency | ✅ | ✅ | ✅ | TDEE | ✅ |
| diet | ✅ | ✅ | ✅ | Meal catalog | ✅ |
| allergies | ✅ | ✅ | ❌ | NIKT NIE FILTRUJE | ✅ |
| meals_per_day | ✅ | ✅ | ✅ | UI | ✅ |
| notes | ✅ | ✅ | ⚠️ | Tylko wyświetlanie | ❌ |
| plan | ✅ | ✅ | ✅ | Billing, how_to AI | ✅ |
| role | ✅ | ✅ | ✅ | Auth | ✅ |
| calories_target | ✅ | ✅ | ✅ | Diet | ✅ |
| protein_target | ✅ | ✅ | ✅ | Diet | ✅ |
| streak_days | ✅ | ✅ | ✅ | Gamification | ✅ |
| total_xp | ✅ | ✅ | ✅ | Gamification | ✅ |
| injuries | ✅ | ✅ | ⚠️ | Tylko w AI prompt | ✅ |
| linked_discord_id | ✅ | ✅ | ✅ | Discord bot | ❌ (MOVE) |
| reminder_time | ✅ | ✅ | ✅ | Discord bot | ❌ (MOVE) |
| reminder_enabled | ✅ | ✅ | ✅ | Discord bot | ❌ (MOVE) |
| sports_json | ✅ | ✅ | ✅ | Plan | ✅ |
| training_focus_json | ✅ | ✅ | ✅ | Plan | ✅ |
| improvement_areas_json | ✅ | ✅ | ⚠️ | Plan (częściowo) | ✅ |
| preferred_foods_json | ✅ | ✅ | ⚠️ | Filtrowanie (słabe) | ✅ |
| avoid_foods_json | ✅ | ✅ | ⚠️ | Filtrowanie (słabe) | ✅ |
| available_equipment_json | ✅ | ✅ | ❌ | NIKT NIE UŻYWA | ✅ |
| avoid_exercises_json | ✅ | ✅ | ✅ | Plan generation | ✅ |
| sport_focus | ✅ | ✅ | ✅ | Plan, sport | ✅ |
| sport_specialization | ✅ | ✅ | ✅ | Plan, sport | ✅ |
| sport_training_days_json | ✅ | ✅ | ✅ | Plan, sport | ✅ |
| weekly_plan_json | ✅ | ✅ | ✅ | Plan | ✅ |
| substitutes_history_json | ✅ | ✅ | ⚠️ | History (nieużywane?) | ❌ |

### 7.2 Brakujące dane

| Brakuje | Potrzebne do | Priorytet |
|---|---|---|
| equipment list (użytkownika) | Filtrowanie ćwiczeń | HIGH |
| availability slots | Planowanie godzin | HIGH |
| experience_level | Dostosowanie trudności | HIGH |
| injuries_list (osobne pole) | Bezpieczeństwo | MEDIUM |
| timezone | Notifications, scheduling | MEDIUM |
| measurement_history (obwody) | Progress | LOW |
| workout_preferences | Personalizacja | MEDIUM |

---

## 8. DOSTĘPNOŚĆ — AUDYT

### 8.1 Aktualny stan

**Brakuje implementacji.** `available_equipment_json` istnieje w profilu, ale:
- Nie ma UI do edycji
- Nie ma API do zarządzania
- Nie jest używane przez plan generator (tylko `avoid_exercises`)

### 8.2 Docelowy model Availability

```json
{
  "slots": [
    {
      "day": "Poniedziałek",
      "from": "17:00",
      "to": "19:00",
      "location": "Siłownia",
      "equipment": ["sztanga", "hantle", "ławka"]
    },
    {
      "day": "Środa",
      "from": "18:00",
      "to": "20:00",
      "location": "Hala sportowa",
      "equipment": ["piłka", "kosz"]
    }
  ]
}
```

**Priorytet:** HIGH — to jest kluczowe dla planera.

---

## 9. AI — AUDYT ARCHITEKTURY

### 9.1 Aktualny stan

**Provider abstraction:**
- `app/ai/service.py` — `ask_ai()` z fallback Groq → Gemini
- `app/legacy_routes.py` — duplikacja logiki AI
- Brak provider-agnostic architecture

**Problemy:**
- Deprecated `google.generativeai` (FutureWarning)
- `ask_claude` alias na `ask_ai` — mylące
- Brak BYOK (Bring Your Own Key)
- Brak storage credentials
- Brak rate limits per-user
- Brak privacy controls
- Brak możliwości wyłączenia AI

### 9.2 Rekomendacja

**Docelowa architektura:**
```
AI Layer (EVOLVE)
├── Provider Abstraction
│   ├── GroqProvider
│   ├── OpenAIProvider
│   ├── AnthropicProvider
│   └── GoogleProvider
├── Credential Storage
│   ├── User-provided (BYOK)
│   └── System-provided (default free)
├── Rate Limiting
│   ├── Per-user
│   └── Per-provider
├── Fallback Chain
│   └── Provider A → B → C → Deterministic
├── Privacy
│   ├── Opt-in AI
│   └── Data minimization
└── Feature Flags
    └── AI_ENABLED (global toggle)
```

---

## 10. FUNKCJE NIEWYMIENIONE

### 10.1 Wartowe elementy

| Element | Opis | Decyzja |
|---|---|---|
| XP/Level system | Prosty ale działający | IMPROVE |
| Streak | Motywujący | IMPROVE |
| Carb Cycling | Warto zachować | KEEP |
| Alternatywy w planie | Dobry UX | KEEP |
| Overload detection | Przydatne | IMPROVE |
| Weekly analysis | Dobre podsumowanie | REWORK |

### 10.2 Zbędne elementy

| Element | Powód | Decyzja |
|---|---|---|
| Netlify Identity | Nie używany | REMOVE |
| Billing/Subskrypcje | Placeholder | REMOVE |
| `fitai_api.py` | Duplikat `legacy_routes.py` | REMOVE/MERGE |
| `fitai_dashboard.html` | Stary dashboard | REMOVE |
| `fitai_discord_bot.py` | Oddzielny plik | MOVE |
| `substitutes_history_json` | Nieużywane | REMOVE |
| `energy_score` (alias) | Duplikat `energy_level` | REMOVE |

### 10.3 Dead code / Duplikaty

- `calc_calories` i `calc_protein` — duplikowane w `fitness/calculations.py` i `legacy_routes.py`
- `_day_type` i `day_type` — duplikowane
- `_suggest_progression` i `suggest_progression` — duplikowane
- `fitai_api.py` — ~5000 linii duplikatu

---

## 11. GAMIFICATION

### 11.1 Co działa

- **XP system**: Prosty, zrozumiały
- **Levels**: 20 poziomów, każde 100 XP
- **Streak**: Motywujący, ale łatwy do "zhacking" (checkin = streak)

### 11.2 Problemy

| Problem | Opis | Decyzja |
|---|---|---|
| **Fałszowanie danych** | Użytkownik może zaznaczyć wszystko bez wysiłku | REWORK |
| **Słaba widoczność** | XP widoczny tylko w Postępy | IMPROVE |
| **Brak achievementów** | Tylko levels | IMPROVE |
| **Streak nie ma recovery** | Brak "grace days" | IMPROVE |

### 11.3 Rekomendacja

- **Make it meaningful**: XP za rzeczywiste działania (RPE, objętość, progresja)
- **Add recovery streak**: "5 dni treningu w ostatnich 7"
- **Add milestones**: "100 treningów", "10kg utracone"
- **Hide from Today**: Gamification jako background, nie foreground

---

## 12. UX/UI

### 12.1 Obecny layout

| Komponent | Ocena | Problem |
|---|---|---|
| Sidebar | Działa | Za mało miejsca na mobile |
| Top bar | Brak | Brak globalnych actions |
| Today | ⚠️ | Nie jest centrum |
| Plan | Działa | Zbyt wiele pod-tabów |
| Profile | Działa | Za dużo pól na raz |
| Progress | ⚠️ | Za dużo wykresów |

### 12.2 Docelowa architektura UI

```
EVOLVE — Desktop
┌──────────────────────────────────────────────────────┐
│  Top Bar: Logo | Today | Training | Sport | Nutrition │  Progress | Profile │
├──────────────────────────────────────────────────────┤
│  Main Content Area                                    │
│  (Today jako domyślna strona)                         │
└──────────────────────────────────────────────────────┘

EVOLVE — Mobile
┌──────────────────────┐
│  Top Bar             │
├──────────────────────┤
│  Main Content        │
│  (Today)             │
├──────────────────────┤
│  Bottom Nav:        │
│  🏠 Today | 💪 Train │
│  🏀 Sport | 📊 Stats│
│  👤 Profile          │
└──────────────────────┘
```

---

## 13. DOCELOWY EVOLVE — PROJEKT

### 13.A Co dokładnie powinien być EVOLVE?

EVOLVE to **inteligentny asystent treningowy i żywieniowy** z centralnym modułem **TODAY**, który:

1. **W 5 sekund mówi użytkownikowi** co ma dziś zrobić, kiedy, gdzie, dlaczego
2. **Automatycznie planuje** tygodniowe treningi i dietę na podstawie profilu, dostępności i sprzętu
3. **Adaptuje się** na podstawie wyników (RPE, objętość, progresja)
4. **Łączy** trening siłowy z treningiem sportowym (koszykówka priorytet)
5. **Śledzi** postępy w sposób zrozumiały i actionable

### 13.B User Journey

```
REGISTER
  ↓ (email + password, 30s)
ONBOARDING
  ↓ (cel, poziom, sprzęt, dostępność, preferencje, 3-5 min)
ASSESSMENT (opcjonalnie)
  ↓ (testy fizyczne/techniczne, koszykówka)
AUTOMATIC PLAN GENERATION
  ↓ (algorithm, <1s, deterministic)
TODAY ← CENTRUM
  ↓ (każdego dnia)
TRAINING SESSION
  ↓ (logowanie w czasie rzeczywistym)
RESULT ENTRY
  ↓ (RPE, serie, powtórzenia, ciężar)
ANALYSIS
  ↓ (automatyczna, <1s)
ADAPTATION
  ↓ (automatyczna korekta planu)
NEXT TRAINING (zaktualizowany)
```

**Zmiany względem obecnego:**
- Assessment jako opcjonalny, nie wymagany
- Availability wprowadzana w onboardingie
- Plan generowany automatycznie od razu
- Today jako centrum — nie dashboard
- Adaptacja automatyczna — użytkownik tylko zatwierdza

### 13.C Główne zakładki

| Zakładka | Priorytet | Opis |
|---|---|---|
| **Today** | MUST HAVE | Centrum, wszystko co trzeba dziś zrobić |
| **Training** | MUST HAVE | Plan tygodniowy, historia, progression |
| **Sport** | MUST HAVE | Basketball Hub (priorytet) |
| **Nutrition** | MUST HAVE | Plan diety, logowanie, Kitchen AI (później) |
| **Progress** | MUST HAVE | Wykresy, trendy, wnioski |
| **Recovery** | SHOULD HAVE | Sen, stres, energia, regeneracja |
| **Profile** | MUST HAVE | Dane, cele, preferencje, dostępność |

### 13.D Co w każdej zakładce

**Today:**
- Header: dzień tygodnia, data, streak
- Primary Card: najważniejsza akcja (trening/jadłospis)
- Quick Actions: loguj trening, posiłki, check-in
- Context: dlaczego ten trening, co po nim
- Summary: kalorie, treningi, woda

**Training:**
- Tydzień: 7 dni, każdy z workoutem
- Historia: wykonyane treningi
- Progression: sugestie, osiągnięcia
- Exercise Atlas: przegląd, wyszukiwanie

**Sport (Koszykówka):**
- Profil: pozycja, poziom, cele
- Drille: przypisane, historia, progresja
- Statystyki: accuracy, czas, trendy
- Assessment: wyniki, rekomendacje

**Nutrition:**
- Jadłospis na dziś/tydzień
- Logowanie posiłków
- Biblioteka posiłków
- Kitchen AI (później)

**Progress:**
- Waga: trend, prognoza
- Trening: objętość, RPE, frekwencja
- Sport: accuracy, progresja drilli
- Wellness: sen, energia, stres

### 13.E Centralny element

**EVOLVE TODAY** — jedna karta mówiąca:
> "Dziś: Trening klatki i tricepsów — 17:00, Siłownia"
> "Po treningu: 30 min regeneracji, 2L wody"
> "Sprawdzone: 2/4 posiłków, brakujący obiad"

### 13.F Co jest automatyczne

| Automatycznie | Opis |
|---|---|
| Plan tygodniowy | Generowany od razu po onboardingu |
| Adaptacja planu | Zmiana ciężaru/powtórzeń na podstawie RPE |
| Progresja | Sugestie, a później automatyczne |
| Powiadomienia | Przypomnienia o treningu |
| Kalkulacje | Kalorie, makro, progression |
| Analysis | Tygodniowe podsumowanie |

### 13.G Co użytkownik kontroluje

| Użytkownik kontroluje | Opis |
|---|---|
| Cel | Główny cel treningowy |
| Profil | Wszystkie dane osobowe |
| Dostępność | Dni, godziny, lokalizacje, sprzęt |
| Preferencje | Jedzenie, ćwiczenia, sport |
| Alternatywy | Zamiana posiłków/ćwiczeń |
| Check-in | Wszystkie dane dzienne |
| Priorytety | Co jest ważne w danym tygodniu |

### 13.H Co jest opcjonalne

| Opcjonalne | Opis |
|---|---|
| AI | Można wyłączyć całkowicie |
| Kitchen AI | Wymaga AI |
| Discord | Integracja zewnętrzna |
| Assessment | Nie wymagany do startu |
| Gamification | Można wyłączyć |
| Sport | Tylko jeśli użytkownik uprawia |

### 13.I Co usuwamy całkowicie

| Usuwamy | Powód |
|---|---|
| Netlify Identity | Nieużywany, zastąpiony przez email+password |
| Billing/Subskrypcje | Placeholder, nie testowany |
| `fitai_api.py` | Duplikat `legacy_routes.py` |
| `fitai_dashboard.html` | Stary dashboard |
| `fitai_discord_bot.py` | Do przeniesienia do osobnego serwisu |
| `substitutes_history_json` | Nieużywane |
| `energy_score` (alias) | Duplikat |
| Duplikaty makr | Jedna implementacja |
| Stare endpointy | Wszystkie z `fitai_api.py` |

---

## 14. PRIORYTETY — TABELA

| Funkcja | Stan | Decyzja | Priorytet | Powód |
|---|---|---|---|---|
| Auth/Rejestracja | Działa | KEEP | MUST HAVE | Podstawa |
| Profil | Działa | IMPROVE | MUST HAVE | Potrzebuje więcej pól |
| Plan tygodniowy | Działa | REWORK | MUST HAVE | Centralny element |
| Mój Dzień | Częściowo | REWORK | MUST HAVE | Centrum UX |
| Trening (generacja) | Działa | IMPROVE | MUST HAVE | Serce produktu |
| Trening (adaptacja) | Częściowo | REWORK | MUST HAVE | Brak automatyczności |
| Atlas ćwiczeń | Działa | IMPROVE | MUST HAVE | Potrzebuje DB |
| Dieta (generacja) | Działa | IMPROVE | MUST HAVE | Brak alergii |
| Dieta (biblioteka) | Hardkodowana | REWORK | SHOULD HAVE | Potrzebuje DB |
| Sport (Koszykówka) | Ograniczony | IMPROVE | MUST HAVE | Priorytet sportu |
| Sport (drille) | 10 drilli | EXPAND | MUST HAVE | Za mało |
| Postępy | Działa | REWORK | MUST HAVE | Za dużo wykresów |
| Gamification | Działa | IMPROVE | SHOULD HAVE | Może lepsze |
| Availability | Brak | CREATE | MUST HAVE | Kluczowe dla planera |
| AI (Kitchen) | Działa | DEFER | COULD HAVE | Nie teraz |
| AI (Analysis) | Działa | DEFER | COULD HAVE | Nie teraz |
| Discord | Działa | MOVE | COULD HAVE | Nie kluczowe |
| Billing | Placeholder | REMOVE | — | Nieużywany |
| PWA | Działa | IMPROVE | SHOULD HAVE | Offline-first |

---

## 15. ROADMAPA

### PHASE 0: Audit & Corrections (TYDZIEŃ 1-2)

- [ ] Napraw testy (tzdata)
- [ ] Usuń duplikaty kodu (fitai_api.py)
- [ ] Usuń unused code
- [ ] Napraw alergie w meal catalog
- [ ] Ujednolic auth (usuń Netlify Identity references)
- [ ] Dodaj brakujące pola do UserDB (availability, equipment, timezone)

### PHASE 1: Core Training Product (TYDZIEŃ 3-6)

**Cel: Działający vertical slice: Profile → Plan → Today → Training → Result → Analysis → Adaptation**

- [ ] **Availability Module**: DB + API + UI
- [ ] **Exercise DB**: Migracja z hardcoded do DB
- [ ] **Training Plan Rework**: Equipment-aware, availability-aware, deterministic
- [ ] **Today Rework**: Centralny element, 5-sekund clarity
- [ ] **Result Logging**: Poprawione UI, RPE, auto-suggest
- [ ] **Automatic Adaptation**: Zmiana planu na podstawie wyników
- [ ] **Progression Engine**: Ulepszona logika, więcej sygnałów

### PHASE 2: Basketball (TYDZIEŃ 7-9)

- [ ] **Basketball Profile**: Pozycja, poziom, doświadczenie
- [ ] **Drill Database**: Rozszerz do 50+ drilli
- [ ] **Drill Logging**: Poprawione UI, video, timing
- [ ] **Basketball Stats**: Accuracy, tempo, trendy
- [ ] **Assessment**: Podstawowe testy

### PHASE 3: Nutrition (TYDZIEŃ 10-12)

- [ ] **Meal Library DB**: Migracja z hardcoded
- [ ] **Full Macros**: P/C/F na posiłek
- [ ] **Allergy Filtering**: Na poziomie DB
- [ ] **Portion Scaling**: 0.5/1/1.5/2 porcje
- [ ] **User Meals**: Możliwość dodawania własnych

### PHASE 4: Progress / Recovery (TYDZIEŃ 13-14)

- [ ] **Progress Rework**: Mniej wykresów, więcej insights
- [ ] **Recovery Module**: Sen, energia, stres, łagodny trening
- [ ] **Weekly Analysis**: Ulepszona, actionable

### PHASE 5: AI (TYDZIEŃ 15-18)

- [ ] **Provider Abstraction**: Groq, OpenAI, Anthropic, Google
- [ ] **BYOK**: Użytkownik podaje własny klucz
- [ ] **Default Free AI**: Systemowy provider
- [ ] **Privacy Controls**: Opt-in, data minimization
- [ ] **Kitchen AI**: Przeniesienie na nową architekturę

### PHASE 6: Polish / Advanced (TYDZIEŃ 19-20)

- [ ] **UI Polish**: Responsywność, loading states, error states
- [ ] **Import/Export**: Dane użytkownika
- [ ] **Gamification Polish**: Achievementy, milestones
- [ ] **PWA**: Offline-first, background sync
- [ ] **Performance**: Lazy loading, code splitting

---

## 16. RAPORT KOŃCOWY

### 16.1 Pliki sprawdzone

**Backend:**
- `app/__init__.py`
- `app/config.py`
- `app/database.py`
- `app/models.py`
- `app/schemas.py`
- `app/fitness/calculations.py`
- `app/fitness/dashboard.py`
- `app/fitness/routes.py`
- `app/fitness/utils.py`
- `app/plan/routes.py`
- `app/legacy_routes.py` (3090 linii)
- `app/ai/routes.py`
- `app/ai/service.py`
- `app/auth/routes.py`
- `app/auth/security.py`
- `app/auth/jwt_utils.py`
- `app/auth/dependencies.py`
- `app/notifications/routes.py`
- `app/notifications/service.py`
- `app/notifications/discord_bot.py`
- `app/health/routes.py`
- `app/exercise_descriptions.py`
- `app/meta/routes.py`
- `main.py`

**Frontend:**
- `app/index.html` (~25k linii)
- `app/index_new.html`

**Konfiguracja:**
- `requirements.txt`
- `package.json`
- `render.yaml`
- `netlify.toml`
- `Procfile`
- `manifest.json`
- `sw.js`
- `.env` (nie odczytywalny)

**Testy:**
- 50 testów zebranych, 11 błędów kolekcji
- Brak możliwości uruchomienia z powodu `tzdata`

**Dokumentacja:**
- `README.md`
- `PROGRAM_ANALYSIS.md`
- `KITCHEN_AI_FIX.md`
- `KITCHEN_AI_SUMMARY.md`
- `TEST_KITCHEN_AI.md`
- `QUICK_START.md`
- `QUICK_START_KITCHEN_AI.md`
- `QUICK_REFERENCE_ETAP3.md`
- `ETAP_3_SUMMARY.md`
- `ETAP_4_PLAN.md`
- `ETAP_4_SUMMARY.md`
- `ETAP1_SUMMARY.md`
- `FITAI_AUDYT_PRODUKCYJNY.md`
- `FITAI_SAAS_DOCS.md`
- `DASHBOARD_ANALYSIS.md`
- `ENDPOINT_DIFF.md`

### 16.2 Testy wykonane

| Test | Status | Uwagi |
|---|---|---|
| `pytest --collect-only` | ⚠️ 50 collected, 11 errors | Brak `tzdata` |
| `pytest test_exercise_descriptions.py` | ❌ Error | Brak `tzdata` |
| Manual API test (register/login) | Nie wykonano | Brak uruchomionego serwera |
| Manual UI test | Nie wykonano | Brak uruchomionej aplikacji |
| Manual flow: plan generation | Nie wykonano | — |
| Manual flow: diet | Nie wykonano | — |
| Manual flow: training | Nie wykonano | — |

**Błędy testów:**
1. `test_day_tracker.py` — `ZoneInfoNotFoundError: 'Europe/Warsaw'`
2. `test_diet.py` — to samo
3. `test_etap1.py` — to samo
4. `test_etap2_structure.py` — to samo
5. `test_etap3_full.py` — to samo
6. `test_etap4.py` — to samo
7. `test_macros.py` — to samo
8. `test_main.py` — to samo
9. `test_plan_persistence.py` — to samo
10. `test_sport_drills.py` — to samo
11. `test_weekly_analysis.py` — to samo

**Przyczyna:** Brak pakietu `tzdata` w środowisku Python 3.14.

### 16.2 Testy wykonane

**Test suite składa się z 13 plików testowych:**

| Plik testowy | Typ | Co testuje |
|---|---|---|
| `test_e2e_launch.py` | E2E | 12 sekwencyjnych testów: rejestracja, login, refresh, profile, checkin, day tracker, race condition |
| `test_main.py` | Integration | Root endpoint, user creation, logs, onboarding, plan swap |
| `test_diet.py` | Integration | 6 scenariuszy diety → protein (Standard, High-Protein, Low-Carb, Buildmass, weight change, safety limit) |
| `test_macros.py` | Integration | 5 scenariuszy kalorii/białka (baseline, weight change, goal change, frequency change) |
| `test_day_tracker.py` | Integration | Day tracker: toggle meals/workouts, add custom items, swap, XP recalculation |
| `test_plan_persistence.py` | Integration | Weekly plan persistence through profile reload |
| `test_etap1.py` | Integration | Health, profile update, XP anti-spam |
| `test_etap2_structure.py` | Integration | Modularized app: health, auth register, auth me |
| `test_etap3_full.py` | Integration | Full flow: register, profile, checkin, dashboard, exercise/drill logging, AI routes |
| `test_etap4.py` | Integration | DateTime migration, ISO serialization, date types in DB |
| `test_exercise_descriptions.py` | Unit | `get_how_to()` lookup: known/unknown, case-insensitive, substring fallback, dict integrity |
| `test_sport_drills.py` | Integration | Drill search, drill result logging, accuracy, target bonus |
| `test_weekly_analysis.py` | Integration | 7-day summary: checkin, exercises, drills, water, RPE |

**Uruchomienie testów:**
```bash
pytest --collect-only
# Result: 50 collected / 11 errors
# All errors: ZoneInfoNotFoundError: 'Europe/Warsaw' (brak pakietu tzdata)
```

**Żaden test nie został uruchomiony.** Collection fails na starcie z powodu brakującego `tzdata` w Python 3.14.

**Coverage:**
- ✅ Auth flow (register, login, refresh, nickname)
- ✅ Profile CRUD + macro recalculation
- ✅ Daily checkin + XP awards + streak
- ✅ Exercise/drill logging + history
- ✅ Weekly plan generation + persistence + swap
- ✅ Day tracker (toggle, add, swap, macro sync)
- ✅ Macro calculations (Mifflin-St Jeor, protein modifiers, carb cycling)
- ✅ Exercise/drill descriptions lookup
- ✅ Race conditions (5 concurrent registrations)
- ⚠️ AI routes — tylko smoke tests, brak negative cases
- ❌ Service worker — 0 coverage
- ❌ PWA manifest — 0 coverage
- ❌ Export endpoints — nie istnieją
- ❌ Discord notifications — 0 coverage
- ❌ Rate limiting — 0 coverage
- ❌ Error handling / edge cases — 0 coverage
- ❌ `_check_overload` — 0 coverage
- ❌ `suggest_progression` — 0 coverage (poza integracją w etap3)
- ❌ `_ensure_legacy_sqlite_columns` — 0 coverage

### 16.3 Błędy znalezione

| # | Błąd | Plik | Linia | Opis | Priorytet |
|---|---|---|---|---|---|
| 1 | `user_key` undefined | `fitai_api.py` | ~3237, 3269 | `app_log_water` używa `user_key` zamiast `user.user_key` — **NameError na każdym requeście** | CRITICAL |
| 2 | `logger` before definition | `fitai_api.py` | 53, 59 | `logger.info/warning` wywołane podczas importu, przed definicją loggera (linia 156) — **NameError przy imporcie** | CRITICAL |
| 3 | `_xp_to_level` runtime import | `app/models.py` | 14, 182 | Importowany tylko pod `TYPE_CHECKING`, używany w `to_profile_dict()` — **NameError przy każdym wywołaniu** | CRITICAL |
| 4 | Broken Alembic chain | `alembic/versions/` | multiple | `a1b2c3d4e5f6` to placeholder ID, `down_revision=None` — **migracje nie zadziałają** | HIGH |
| 5 | Stripe webhook no signature | `legacy_routes.py` | 2322 | Brak `stripe.Webhook.construct_event()` — każdy może sfałszować request | CRITICAL |
| 6 | Legacy endpoints no auth | `legacy_routes.py` | multiple | `/users/{id}`, `/app/plan`, `/app/reminders-due` bez autoryzacji | CRITICAL |
| 7 | JWT expiry inconsistency | `app/config.py` vs `fitai_api.py` | — | 30 min vs 10080 min (7 dni) — tokeny mają różne lifetimes | HIGH |
| 8 | Groq model mismatch | `app/ai/service.py` vs `legacy_routes.py` | — | `mixtral-8x7b-32768` vs `llama-3.3-70b-versatile` — różne modele | MEDIUM |
| 9 | Schema mismatch date types | `app/models.py` vs `fitai_api.py` | — | `date`/`datetime` vs `str` (ISO) — runtime errors przy użyciu obu modeli | HIGH |
| 10 | Duplicate macro functions | 3 pliki | — | `calc_calories`/`calc_protein` w `fitness/calculations.py`, `legacy_routes.py`, `fitai_api.py` | HIGH |
| 11 | `asyncio.run` w sync routes | `legacy_routes.py` | 1226-1234 | Blokuje event loop, może spowodować RuntimeError | MEDIUM |
| 12 | Deprecated Gemini SDK | `legacy_routes.py` | 19 | `google.generativeai` deprecated — brak aktualizacji | MEDIUM |
| 13 | Test suite nieuruchamialny | wszystkie `test_*.py` | — | Brak `tzdata` — 11 błędów kolekcji, 0 testów uruchomionych | CRITICAL |
| 14 | Version mismatch | `package.json` vs `test_e2e_launch.py` | — | `"1.0.0"` vs oczekiwane `"2.1.0"` | LOW |
| 15 | `energy_score` alias | `schemas.py` | 221-223 | Duplikat `energy_level`, mylący | LOW |
| 16 | `substitutes_history_json` unused | `models.py` | 88 | Pole w DB, nigdzie nie używane | LOW |
| 17 | Diet Compliance bug | `legacy_routes.py` | 2864-2866 | Liczy dni z textem `food` zamiast boolean `meals_eaten` | HIGH |
| 18 | Weight trend sorting | `legacy_routes.py` | 618-621 | `[:14]` na nieposortowanej liście — może zwrócić nieprawidłowe dane | MEDIUM |
| 19 | Two parallel apps | `fitai_api.py` + `main.py` | — | Dwa niezależne FastAPI apps — ryzyko divergence | HIGH |
| 20 | `create_db_and_tables` called twice | `app/__init__.py` | 39, 163 | Redundant ale harmless | LOW |

### 16.4 Decyzje produktowe

| # | Decyzja | Opis |
|---|---|---|
| 1 | **EVOLVE = Training-first, not AI-first** | AI jest warstwą nad deterministycznym rdzeniem |
| 2 | **Today = centrum UX** | Wszystkie moduły prowadzą do Today |
| 3 | **Automatic plan = default** | Użytkownik nie musi generować planu ręcznie |
| 4 | **Basketball = priorytet sportu** | Inne sporty później |
| 5 | **Availability = kluczowe** | Planer MUSI używać dostępności |
| 6 | **Meal Library w DB** | Koniec hardkodowania |
| 7 | **AI = opt-out, nie opt-in** | Domyślnie włączone, ale można wyłączyć |
| 8 | **Remove billing** | Nie teraz, nie jako placeholder |
| 9 | **Merge legacy routes** | Jeden plik, nie dwa |
| 10 | **Exercise DB** | Koniec hardkodowanego dict |

**Błędy krytyczne znalezione podczas audytu testów:**

| Błąd | Plik | Linia | Opis | Priorytet |
|---|---|---|---|---|
| `user_key` undefined | `fitai_api.py` | ~3237, 3269 | `app_log_water` używa `user_key` zamiast `user.user_key` | CRITICAL |
| `logger` before definition | `fitai_api.py` | 53, 59 | `logger.info/warning` wywołane przed definicją loggera | CRITICAL |
| `_xp_to_level` runtime import | `app/models.py` | 14, 182 | Importowany tylko pod `TYPE_CHECKING`, używany w runtime | CRITICAL |
| Broken Alembic chain | `alembic/versions/` | multiple | Placeholder revision ID, `down_revision=None` | HIGH |
| Stripe webhook no signature | `legacy_routes.py` | 2322 | Brak weryfikacji podpisu Stripe | CRITICAL |
| Legacy endpoints no auth | `legacy_routes.py` | multiple | `/users/{id}`, `/app/plan` bez autoryzacji | CRITICAL |
| Model mismatch date types | `fitai_api.py` vs `app/models.py` | — | `str` vs `date`/`datetime` dla tych samych pól | HIGH |
| Duplicate `calc_calories` | 3 pliki | — | `fitai_api.py`, `legacy_routes.py`, `fitness/calculations.py` | HIGH |
| Alergie nie filtrowane | `legacy_routes.py` | 649-802 | `_default_meal_catalog` nie filtruje alergii | HIGH |
| Diet Compliance bug | `legacy_routes.py` | 2864-2866 | Liczy dni z textem `food`, nie boolean meals | HIGH |
| `asyncio.run` w sync routes | `legacy_routes.py` | 1226-1234 | Blokuje event loop, może spowodować `RuntimeError` | MEDIUM |
| Deprecated Gemini SDK | `legacy_routes.py` | 19 | `google.generativeai` deprecated, brak aktualizacji | MEDIUM |
| Test suite nieuruchamialny | wszystkie `test_*.py` | — | Brak `tzdata` w środowisku Python 3.14 | CRITICAL |
| Wersja package.json mismatch | `package.json` vs `test_e2e_launch.py` | — | `"1.0.0"` vs oczekiwane `"2.1.0"` | LOW |

---

### 16.5 Proponowana roadmapa

| Faza | Czas | Cel |
|---|---|---|
| **Phase 0** | Tydzień 1-2 | Naprawy, cleanup, foundations |
| **Phase 1** | Tydzień 3-6 | Core Training: Profile → Plan → Today → Training → Result |
| **Phase 2** | Tydzień 7-9 | Basketball Hub |
| **Phase 3** | Tydzień 10-12 | Nutrition (Meal DB, logging) |
| **Phase 4** | Tydzień 13-14 | Progress + Recovery |
| **Phase 5** | Tydzień 15-18 | AI (provider abstraction, BYOK) |
| **Phase 6** | Tydzień 19-20 | Polish, PWA, import/export |

### 16.6 Executive Verdict

**1. Co jest obecnie najlepszą częścią programu?**
Algorytm generowania planu treningowego — `_build_weekly_plan` jest dobrze zaprojektowany, deterministyczny, z sensownym użyciem carb cycling i progresją. Jest to solidny fundament.

**2. Co jest największym problemem?**
Brak centralnego "Today experience" — użytkownik nie wie co ma zrobić, kiedy i gdzie. Plan jest generowany, ale nie jest integrowany z codziennym flowsem.

**3. Co należy zachować za wszelką cenę?**
- Algorytm planowania treningów
- System progresji RPE-based
- Carb cycling
- Struktura danych użytkownika
- XP/streak jako mechanizm motywacji

**4. Co należy wyrzucić?**
- `fitai_api.py` (duplikat)
- Netlify Identity (nieużywany)
- Billing placeholder
- Hardkodowane meal catalog
- Duplikacja kodu między plikami

**5. Co należy przebudować?**
- Mój Dzień → EVOLVE TODAY (centrum)
- Plan → automatyczny, availability-aware
- Atlas ćwiczeń → Exercise DB
- Postępy → mniej, ale lepsze wykresy
- AI → provider-agnostic architecture

**6. Co powinno być pierwszą implementacją?**
**EVOLVE TODAY** — centralna karta mówiąca użytkownikowi co ma zrobić dziś. Bez tego EVOLVE nie jest dobrym produktem.

**7. Jak powinien wyglądać EVOLVE MVP?**
```
REJESTRACJA (30s)
→ ONBOARDING (3-5 min: cel, sprzęt, dostępność, preferencje)
→ AUTOMATYCZNY PLAN (1s, algorithm)
→ TODAY (centrum: co, kiedy, gdzie, dlaczego)
→ TREINING (logowanie, RPE, progresja)
→ ADAPTACJA (automatyczna)
```

**8. Czy obecny Training Coach jest dobrym fundamentem?**
**Tak**, ale z warunkami. Rdzeń (planowanie, progresja, logging) jest solidny. Trzeba tylko usunąć duplikaty, dodać availability, equipment awareness i przebudować Today.

**9. Jak wykorzystać kod bez przenoszenia błędów?**
- Weź `_build_weekly_plan` jako podstawę, ale usuń hardcoding
- Weź `suggest_progression` jako bazę, ale dodaj więcej sygnałów
- Weź strukturę DB, ale dodaj brakujące tabele
- Usuń `fitai_api.py` — cała logika jest w `legacy_routes.py`
- Migruj endpointy po kolei, testując każdy

**10. Jaka jest rekomendowana kolejność dalszej pracy?**
1. Napraw testy i usunięcie duplikatów (Phase 0)
2. Availability Module (Phase 1)
3. EVOLVE TODAY (Phase 1)
4. Exercise DB migration (Phase 1)
5. Automatic adaptation (Phase 1)
6. Basketball Hub (Phase 2)
7. Nutrition DB (Phase 3)
8. Progress rework (Phase 4)
9. AI abstraction (Phase 5)

---

`EVOLVE_TRANSFORMATION_AUDIT_COMPLETE`

**Files inspected:** 50+ backend/frontend/config/docs files  
**Tests executed:** 0 full runs (collection blocked by missing `tzdata`; 11 collection errors across test suite)  
**Manual flows tested:** 0 (audit-only phase)  
**Bugs found:** 20 (including 6 runtime NameError/import bugs that will prevent the app from functioning)  
**Product decisions:** 10  
**Proposed roadmap:** 6 phases, ~20 weeks
