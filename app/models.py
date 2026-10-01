"""
FitAI Models — SQLModel definitions for database tables
"""

import json
import uuid as _uuid_mod
from datetime import datetime, date
from typing import TYPE_CHECKING, Optional

from sqlalchemy.orm import relationship
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.fitness.calculations import _xp_to_level  # avoid circular import


class UserDB(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[str] = Field(
        default_factory=lambda: str(_uuid_mod.uuid4()),
        primary_key=True,
    )
    user_key: str = Field(unique=True, index=True)          # "web:<identity_id>" lub legacy user_id
    identity_id: Optional[str] = Field(default=None, index=True)
    email: Optional[str] = Field(default=None, index=True)
    nickname: Optional[str] = Field(default=None, unique=True, index=True)
    user_number: Optional[int] = Field(default=None, unique=True, index=True)
    name: str
    age: int
    height: float
    weight: float
    start_weight: float
    target_weight: float
    gender: str = "mężczyzna"
    goal: str
    frequency: str
    diet: str
    allergies: str = ""
    meals_per_day: int = 4
    notes: str = ""
    plan: str = "free"          # "free" | "pro"
    role: str = "free_user"
    calories_target: int = 0
    protein_target: int = 0
    streak_days: int = 0
    linked_discord_id: Optional[str] = None

    # ─── Discord Integration & Reminders ──────────────────────────────────────
    # Pola obsługują parowanie konta Discord (przez tymczasowy kod) oraz
    # harmonogram codziennych przypomnień o treningu wysyłanych przez DM.

    discord_user_id: Optional[str] = None
    # ID użytkownika Discord (snowflake jako string) po pomyślnym połączeniu kont.
    # None = konto nie połączone.

    discord_connect_code: Optional[str] = None
    # Tymczasowy kod parujący generowany przy żądaniu połączenia, np. "FIT-7K2M".
    # Użytkownik wpisuje go w kanale Discord; po weryfikacji pole jest zerowane.

    discord_connect_code_expires_at: Optional[datetime] = None
    # Czas wygaśnięcia kodu parującego (UTC). Typowo: now() + 10 minut.
    # Po wygaśnięciu kod jest traktowany jak nieistniejący.

    reminder_time: Optional[str] = None
    # Godzina wysyłania codziennego przypomnienia o treningu w formacie "HH:MM",
    # np. "18:00". Wartość None oznacza brak ustawionej godziny.

    reminder_enabled: bool = False
    # Czy przypomnienia Discord DM są aktywne dla tego konta.
    # Wymaga ustawionego discord_user_id oraz reminder_time.

    last_reminder_sent_date: Optional[date] = None
    # Data (bez czasu) ostatnio wysłanego przypomnienia.
    # Używana przez scheduler do deduplicacji — nie wysyłamy dwa razy tego samego dnia.

    # ─── JSON-encoded lists/dicts ─────────────────────────────────────────────
    # SQLite nie ma ARRAY
    sports_json: str = "[]"
    training_focus_json: str = "[]"
    improvement_areas_json: str = "[]"
    preferred_foods_json: str = "[]"
    avoid_foods_json: str = "[]"
    available_equipment_json: str = "[]"
    avoid_exercises_json: str = "[]"
    reminders_json: str = '{"email_enabled":true,"discord_enabled":false,"discord_channel_id":null}'
    weekly_plan_json: Optional[str] = None
    substitutes_history_json: str = "{}"
    availability_json: str = "{}"  # per-day availability: {"Poniedziałek": {"available": true, "time_window": "18:00-20:00", "location": "gym", "equipment": ["sztanga"]}}
    # ─── Sports module ───────────────────────────────────────────────────────
    sport_focus: Optional[str] = None                  # np. "koszykówka"
    sport_specialization: Optional[str] = None         # np. "rzuty"
    sport_training_days_json: str = "[]"               # np. ["Środa", "Sobota"]
    # ─── Auth (dodane w v2.1) ───────────────────────────────────────────────
    hashed_password: Optional[str] = None             # None = konto Netlify Identity (stare)
    is_active: bool = True                             # możliwość blokowania konta
    # ─── Gamification & safety ───────────────────────────────────────────────
    total_xp: int = 0                                  # łączne punkty XP
    injuries: str = ""                                 # przecinkowy string: "kolano lewe,bark"
    last_weight_change: float = 0.0                    # delta wagi wzgl. poprzedniego wpisu [kg]
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # ── Relacje ──────────────────────────────────────────────────────────────────
    logs: list["DailyLogDB"] = Relationship(
        sa_relationship=relationship(
            "DailyLogDB",
            back_populates="user",
            lazy="select",
        )
    )
    exercise_results: list["ExerciseResultDB"] = Relationship(
        sa_relationship=relationship(
            "ExerciseResultDB",
            back_populates="user",
            lazy="select",
        )
    )
    exercise_sets: list["ExerciseSetDB"] = Relationship(
        sa_relationship=relationship(
            "ExerciseSetDB",
            back_populates="user",
            lazy="select",
        )
    )

    # Helpers
    def get_list(self, field: str) -> list:
        return json.loads(getattr(self, field, "[]") or "[]")

    def set_list(self, field: str, value: list):
        setattr(self, field, json.dumps(value, ensure_ascii=False))

    def get_dict(self, field: str) -> dict:
        return json.loads(getattr(self, field, "{}") or "{}")

    def set_dict(self, field: str, value: dict):
        setattr(self, field, json.dumps(value, ensure_ascii=False))

    @property
    def display_name(self) -> str:
        """Zwraca wyświetlaną nazwę: Użytkownik#0047 lub imię jeśli ustawione."""
        if self.user_number:
            return f"Użytkownik#{self.user_number:04d}"
        return self.name or "Użytkownik"

    def to_profile_dict(self) -> dict:
        from app.fitness.calculations import _xp_to_level
        
        return {
            "user_key": self.user_key,
            "identity_id": self.identity_id,
            "email": self.email,
            "nickname": self.nickname,
            "user_number": self.user_number,
            "display_name": self.display_name,
            "name": self.name,
            "age": self.age,
            "height": self.height,
            "weight": self.weight,
            "start_weight": self.start_weight,
            "target_weight": self.target_weight,
            "gender": self.gender,
            "goal": self.goal,
            "frequency": self.frequency,
            "diet": self.diet,
            "allergies": self.allergies,
            "meals_per_day": self.meals_per_day,
            "notes": self.notes,
            "plan": self.plan,
            "role": self.role,
            "calories_target": self.calories_target,
            "protein_target": self.protein_target,
            "streak_days": self.streak_days,
            "linked_discord_id": self.linked_discord_id,
            "sports": self.get_list("sports_json"),
            "training_focus": self.get_list("training_focus_json"),
            "improvement_areas": self.get_list("improvement_areas_json"),
            "preferred_foods": self.get_list("preferred_foods_json"),
            "avoid_foods": self.get_list("avoid_foods_json"),
            "available_equipment": self.get_list("available_equipment_json"),
            "avoid_exercises": self.get_list("avoid_exercises_json"),
            "reminders": self.get_dict("reminders_json"),
            "weekly_plan": self.get_dict("weekly_plan_json") if self.weekly_plan_json else None,
            "substitutes_history": self.get_dict("substitutes_history_json"),
            "sport_focus": self.sport_focus,
            "sport_specialization": self.sport_specialization,
            "sport_training_days": self.get_list("sport_training_days_json"),
            "availability": self.get_dict("availability_json"),
            "total_xp": self.total_xp,
            "level": _xp_to_level(self.total_xp),
            "injuries": [i.strip() for i in self.injuries.split(",") if i.strip()],
            "last_weight_change": self.last_weight_change,
            "created_at": self.created_at.isoformat(),  # Serialize datetime to ISO string
            "updated_at": self.updated_at.isoformat(),
        }


class UserNumberSequenceDB(SQLModel, table=True):
    """Tabela-sekwencja do atomowego przydzielania user_number.

    INTEGER PRIMARY KEY w SQLite = AUTOINCREMENT — gwarantuje unikalność
    nawet przy równoczesnych requestach (race condition safe).
    """
    __tablename__ = "user_number_sequence"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="users.id", unique=True)


class DailyLogDB(SQLModel, table=True):
    __tablename__ = "daily_logs"

    id: Optional[str] = Field(
        default_factory=lambda: str(_uuid_mod.uuid4()),
        primary_key=True,
    )
    user_id: str = Field(foreign_key="users.id", index=True)
    log_date: date = Field(index=True)           # Rzeczywista data, nie string
    food: str = ""
    workout: str = ""
    meals_json: str = "[]"
    workouts_json: str = "[]"
    custom_meals_json: str = "[]"
    mood: str = ""
    weight: Optional[float] = None
    water_liters: Optional[float] = None          # spożycie wody w litrach (inkrementowane)
    # ── Check-in rozszerzony (Mój Dzień v2) ──────────────────────────────
    sleep_hours: Optional[float] = None      # czas snu w godzinach (np. 7.5)
    sleep_quality: Optional[int] = None      # jakość snu 1-10
    sleep_start: Optional[str] = None        # godzina zaśnięcia "23:00"
    sleep_end: Optional[str] = None          # godzina wstania "07:00"
    energy_level: Optional[int] = None       # poziom energii 1-10
    stress_level: Optional[int] = None       # poziom stresu 1-10
    fatigue_score: Optional[int] = None      # zmęczenie 1-10
    mood_score: Optional[int] = None         # nastrój 1-5 (emoji scale)
    rpe: Optional[int] = None                # RPE treningu 1-10
    meals_eaten: Optional[int] = None        # liczba zjedzonych posiłków
    workouts_done: Optional[int] = None      # liczba wykonanych ćwiczeń
    notes: Optional[str] = None              # notatka do dnia
    logged_at: datetime = Field(default_factory=datetime.now)  # Rzeczywisty datetime

    user: "UserDB" = Relationship(
        sa_relationship=relationship(
            "UserDB",
            back_populates="logs",
            lazy="select",
        )
    )

    def to_dict(self) -> dict:
        return {
            "date": self.log_date.isoformat(),  # Serialize to ISO format for API
            "food": self.food,
            "workout": self.workout,
            "meals_json": self.meals_json,
            "workouts_json": self.workouts_json,
            "custom_meals_json": self.custom_meals_json,
            "meals": self.get_meals(),
            "workouts": self.get_workouts(),
            "custom_meals": self.get_custom_meals(),
            "mood": self.mood,
            "weight": self.weight,
            "water_liters": self.water_liters,
            "sleep_hours": self.sleep_hours,
            "sleep_quality": self.sleep_quality,
            "sleep_start": self.sleep_start,
            "sleep_end": self.sleep_end,
            "energy_level": self.energy_level,
            "stress_level": self.stress_level,
            "fatigue_score": self.fatigue_score,
            "mood_score": self.mood_score,
            "rpe": self.rpe,
            "meals_eaten": self.meals_eaten,
            "workouts_done": self.workouts_done,
            "notes": self.notes,
            "logged_at": self.logged_at.isoformat(),
        }

    def _load_json_list(self, field_name: str) -> list:
        try:
            value = json.loads(getattr(self, field_name, "[]") or "[]")
            return value if isinstance(value, list) else []
        except (TypeError, json.JSONDecodeError):
            return []

    def _store_json_list(self, field_name: str, value: list) -> None:
        setattr(self, field_name, json.dumps(value or [], ensure_ascii=False))

    def get_meals(self) -> list:
        return self._load_json_list("meals_json")

    def set_meals(self, value: list) -> None:
        self._store_json_list("meals_json", value)

    def get_workouts(self) -> list:
        return self._load_json_list("workouts_json")

    def set_workouts(self, value: list) -> None:
        self._store_json_list("workouts_json", value)

    def get_custom_meals(self) -> list:
        return self._load_json_list("custom_meals_json")

    def set_custom_meals(self, value: list) -> None:
        self._store_json_list("custom_meals_json", value)


class ExerciseResultDB(SQLModel, table=True):
    """Historyczne wyniki ćwiczeń – serce systemu progresji."""
    __tablename__ = "exercise_results"

    id: Optional[str] = Field(
        default_factory=lambda: str(_uuid_mod.uuid4()),
        primary_key=True,
    )
    user_id: str = Field(foreign_key="users.id", index=True)
    exercise_name: str = Field(index=True)
    session_date: date = Field(index=True)       # Rzeczywista data
    sets: int
    reps: int
    weight_kg: float
    rpe: int = Field(ge=1, le=10)               # 1 = bardzo lekko, 10 = maksymalny wysiłek
    notes: str = ""
    logged_at: datetime = Field(default_factory=datetime.now)  # Rzeczywisty datetime

    user: Optional["UserDB"] = Relationship(
        sa_relationship=relationship(
            "UserDB",
            back_populates="exercise_results",
            lazy="select",
        )
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "exercise_name": self.exercise_name,
            "session_date": self.session_date.isoformat(),
            "sets": self.sets,
            "reps": self.reps,
            "weight_kg": self.weight_kg,
            "rpe": self.rpe,
            "notes": self.notes,
            "logged_at": self.logged_at.isoformat(),
        }


class ExerciseSetDB(SQLModel, table=True):
    __tablename__ = "exercise_sets"

    id: Optional[str] = Field(
        default_factory=lambda: str(_uuid_mod.uuid4()),
        primary_key=True,
    )
    user_id: str = Field(foreign_key="users.id", index=True)
    exercise_name: str = Field(index=True)
    session_date: date = Field(index=True)
    set_number: int
    reps: int
    weight_kg: float
    rpe: int = Field(ge=1, le=10)
    logged_at: datetime = Field(default_factory=datetime.now)

    user: Optional["UserDB"] = Relationship(
        sa_relationship=relationship(
            "UserDB",
            back_populates="exercise_sets",
            lazy="select",
        )
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "exercise_name": self.exercise_name,
            "session_date": self.session_date.isoformat(),
            "set_number": self.set_number,
            "reps": self.reps,
            "weight_kg": self.weight_kg,
            "rpe": self.rpe,
            "logged_at": self.logged_at.isoformat(),
        }


class DrillResultDB(SQLModel, table=True):
    """Wyniki sesji drilli sportowych – serce systemu progresji sportowej."""
    __tablename__ = "drill_results"

    id: Optional[str] = Field(
        default_factory=lambda: str(_uuid_mod.uuid4()),
        primary_key=True,
    )
    user_id: str = Field(foreign_key="users.id", index=True)
    drill_name: str = Field(index=True)
    drill_category: Optional[str] = None
    drill_sport: Optional[str] = None
    target_pct: Optional[int] = None
    session_date: date = Field(index=True)       # Rzeczywista data
    success_count: int = 0                      # trafienia / powtórzenia (rzuty)
    total_attempts: int = 0                     # łączna liczba prób (rzuty)
    rpe: int = Field(ge=1, le=10)              # 1 = bardzo lekko, 10 = maksymalny wysiłek
    notes: str = ""
    # ─── Pola dla typów drilli bieg/sprint ───────────────────────────────────
    time_seconds: Optional[float] = None        # czas w sekundach (Bieg/Sprint)
    distance_meters: Optional[float] = None     # dystans w metrach (Bieg/Sprint)
    # ─── Pola ogólne (Skill/Drill i Cardio/Sport) ─────────────────────────────
    duration_seconds: Optional[int] = None      # czas trwania ćwiczenia/meczu [s]
    weight_kg: Optional[float] = None           # obciążenie [kg] (np. weighted drill)
    logged_at: datetime = Field(default_factory=datetime.now)  # Rzeczywisty datetime

    def to_dict(self) -> dict:
        base = {
            "id": self.id,
            "drill_name": self.drill_name,
            "drill_category": self.drill_category,
            "drill_sport": self.drill_sport,
            "target_pct": self.target_pct,
            "session_date": self.session_date.isoformat(),
            "rpe": self.rpe,
            "notes": self.notes,
            "logged_at": self.logged_at.isoformat(),
        }
        # Rzuty: pola success/attempts
        if self.total_attempts:
            base["success_count"]  = self.success_count
            base["total_attempts"] = self.total_attempts
            base["accuracy_pct"]   = round(self.success_count / self.total_attempts * 100)
        # Bieg/Sprint: pola time/distance
        if self.time_seconds is not None:
            base["time_seconds"]   = self.time_seconds
        if self.distance_meters is not None:
            base["distance_meters"] = self.distance_meters
        if self.duration_seconds is not None:
            base["duration_seconds"] = self.duration_seconds
        if self.weight_kg is not None:
            base["weight_kg"] = self.weight_kg
        return base