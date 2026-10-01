"""
FitAI Schemas — Pydantic request/response models for FastAPI
"""

import re  # kept for potential future validators
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.config import JWT_EXPIRE_MINUTES


# ─── Auth Schemas ─────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str
    # Dane profilu — opcjonalne, można uzupełnić później
    name: Optional[str] = "Użytkownik"
    age: Optional[int] = 25
    height: Optional[float] = 170.0
    weight: Optional[float] = 70.0
    target_weight: Optional[float] = 70.0
    gender: str = "mężczyzna"
    goal: str = "Utrzymanie wagi"
    frequency: str = "3-4 razy w tygodniu"
    diet: str = "Brak preferencji"

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Hasło musi mieć co najmniej 8 znaków")
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or "." not in value.split("@")[-1]:
            raise ValueError("Nieprawidłowy adres email")
        return value


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshAccessRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = JWT_EXPIRE_MINUTES * 60   # sekundy
    user_id: str
    user_number: Optional[int] = None
    display_name: str = "Użytkownik"
    name: str
    role: str
    plan: str
    refresh_token: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @classmethod
    def validate_new(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Hasło musi mieć co najmniej 8 znaków")
        return v


# ─── Profile / User Schemas ───────────────────────────────────────────────────

class UserProfile(BaseModel):
    name: str
    age: int
    height: float
    weight: float
    target_weight: float
    gender: str = "mężczyzna"
    goal: str
    frequency: str
    training_focus: list[str] = []
    improvement_areas: list[str] = []
    sports: list[str] = []
    diet: str
    allergies: str = ""
    preferred_foods: list[str] = []
    avoid_foods: list[str] = []
    available_equipment: list[str] = []
    avoid_exercises: list[str] = []
    substitutes_history: dict = {}
    meals_per_day: int = 4
    notes: str = ""


class ProfileUpdateRequest(BaseModel):
    """Edycja profilu użytkownika — tylko zmienne pola."""
    age: Optional[int] = None
    weight: Optional[float] = None
    target_weight: Optional[float] = None
    gender: Optional[str] = None
    goal: Optional[str] = None
    frequency: Optional[str] = None
    diet: Optional[str] = None
    allergies: Optional[str] = None
    meals_per_day: Optional[int] = None
    notes: Optional[str] = None


class NicknameChangeRequest(BaseModel):
    new_nickname: str


class AppOnboardingRequest(BaseModel):
    identity_id: str
    email: str
    name: str
    age: int
    height: float
    weight: float
    target_weight: float
    gender: str
    goal: str
    frequency: str
    sports: list[str] = []
    training_focus: list[str] = []
    improvement_areas: list[str] = []
    diet: str
    allergies: str = ""
    preferred_foods: list[str] = []
    avoid_foods: list[str] = []
    available_equipment: list[str] = []
    avoid_exercises: list[str] = []
    meals_per_day: int = 4
    notes: str = ""


# ─── Daily Log / Check-in Schemas ─────────────────────────────────────────────

class DailyLog(BaseModel):
    food: str = ""
    workout: str = ""
    mood: str = ""
    weight: Optional[float] = None


class WaterLogRequest(BaseModel):
    ml: int


class AppDailyCheckinRequest(BaseModel):
    # Pola tekstowe (legacy — zachowane dla kompatybilności)
    food: str = ""
    workout: str = ""
    mood: str = ""
    # Podstawowe dane liczbowe
    weight: Optional[float] = None
    water_ml: Optional[int] = Field(
        default=None, ge=0, le=10000,
        description="Spożyta woda w ml (zostanie przeliczona na litry)"
    )
    # Sen
    sleep_hours: Optional[float] = Field(
        default=None, ge=0, le=24,
        description="Czas snu w godzinach (np. 7.5)"
    )
    sleep_quality: Optional[int] = Field(
        default=None, ge=1, le=10,
        description="Jakość snu 1–10"
    )
    sleep_start: Optional[str] = Field(
        default=None,
        description="Godzina zaśnięcia HH:MM (np. 23:00)"
    )
    sleep_end: Optional[str] = Field(
        default=None,
        description="Godzina wstania HH:MM (np. 07:00)"
    )
    # Samopoczucie
    energy_level: Optional[int] = Field(
        default=None, ge=1, le=10,
        description="Poziom energii 1–10"
    )
    stress_level: Optional[int] = Field(
        default=None, ge=1, le=10,
        description="Poziom stresu 1–10"
    )
    fatigue_score: Optional[int] = Field(
        default=None, ge=1, le=10,
        description="Poziom zmęczenia 1–10"
    )
    mood_score: Optional[int] = Field(
        default=None, ge=1, le=5,
        description="Nastrój 1–5 (1=fatalny, 5=świetny)"
    )
    # Trening
    rpe: Optional[int] = Field(
        default=None, ge=1, le=10,
        description="RPE treningu 1–10"
    )
    meals_eaten: Optional[int] = Field(
        default=None, ge=0, le=20,
        description="Liczba zjedzonych posiłków"
    )
    workouts_done: Optional[int] = Field(
        default=None, ge=0, le=50,
        description="Liczba wykonanych ćwiczeń/drilli"
    )
    notes: Optional[str] = Field(
        default=None, max_length=1000,
        description="Dowolna notatka do dnia"
    )
    # Legacy — zachowane dla kompatybilności
    energy_score: Optional[int] = Field(
        default=None, ge=1, le=10
    )
    soreness: Optional[str] = None


class DayItemToggleRequest(BaseModel):
    item_id: str
    item_type: str
    checked: bool
    log_date: Optional[str] = None


class DayItemAddRequest(BaseModel):
    item_type: str
    name: str
    source: str = "custom"
    kcal: Optional[int] = None
    protein: Optional[float] = None
    sets: Optional[int] = None
    reps: Optional[int] = None
    weight_kg: Optional[float] = None
    rpe: Optional[int] = None
    meal_type: Optional[str] = None
    log_date: Optional[str] = None


class DayItemSwapRequest(BaseModel):
    item_id: str
    item_type: str
    new_name: str
    new_kcal: Optional[int] = None
    new_protein: Optional[float] = None
    sets: Optional[int] = None
    reps: Optional[int] = None
    weight_kg: Optional[float] = None
    rpe: Optional[int] = None
    log_date: Optional[str] = None


# ─── Fitness / Exercise Schemas ───────────────────────────────────────────────

class ExerciseResultRequest(BaseModel):
    """Wpis wyniku ćwiczenia z oceną RPE."""
    exercise_name: str
    sets: int
    reps: int
    weight_kg: float
    rpe: int = Field(ge=1, le=10, description="Rate of Perceived Exertion 1-10")
    notes: str = ""
    session_date: Optional[str] = None  # ISO date; jeśli brak → today


class ExerciseSetRequest(BaseModel):
    """Zaloguj pojedynczą serię w ramach treningu."""
    exercise_name: str
    set_number: int = Field(ge=1, description="Numer serii (1-based)")
    reps: int = Field(ge=1)
    weight_kg: float = Field(ge=0)
    rpe: int = Field(ge=1, le=10, description="Rate of Perceived Exertion 1-10")
    session_date: Optional[str] = None  # ISO date; jeśli brak → today


class WorkoutCompleteRequest(BaseModel):
    """Zamknij sesję treningową — zapisz agregaty i przyznaj XP."""
    session_date: Optional[str] = None  # ISO date; jeśli brak → today
    exercises: list[dict]  # [{"exercise_name": str, "sets": int, "reps": int, "weight_kg": float, "rpe": int, "notes": str}]
    notes: str = ""


class WorkoutSessionResponse(BaseModel):
    id: str
    session_date: str
    exercises: list[dict]
    total_volume_kg: float
    avg_rpe: float
    xp_earned: int
    exercises_count: int


class DrillResultRequest(BaseModel):
    """Wynik sesji drilla sportowego z oceną RPE.
    
    Pola zależą od typu drilla:
    - Rzuty: success_count + total_attempts
    - Bieg/Sprint: time_seconds + distance_meters
    """
    drill_name: str
    drill_category: Optional[str] = None
    drill_sport: Optional[str] = None
    target_pct: Optional[int] = Field(default=None, ge=0, le=100)
    rpe: int = Field(ge=1, le=10, description="Rate of Perceived Exertion 1-10")
    notes: str = ""
    session_date: Optional[str] = None          # ISO date; jeśli brak → today
    # Rzuty
    success_count: int = 0
    total_attempts: int = 0
    # Bieg / Sprint
    time_seconds: Optional[float] = Field(default=None, gt=0, description="Czas w sekundach")
    distance_meters: Optional[float] = Field(default=None, gt=0, description="Dystans w metrach")
    # Ogólne
    duration_seconds: Optional[int] = Field(default=None, ge=0, description="Czas trwania [s]")
    weight_kg: Optional[float] = Field(default=None, ge=0, description="Obciążenie [kg]")


class SportConfigRequest(BaseModel):
    """Konfiguracja modułu sportowego użytkownika."""
    sport_focus: str                            # np. "koszykówka"
    sport_specialization: str = ""             # np. "rzuty"
    sport_training_days: list[str] = []        # np. ["Środa", "Sobota"]


# ─── Plan / Reminder Schemas ──────────────────────────────────────────────────

class PlanUpdateRequest(BaseModel):
    plan: str


class WeeklyPlanSaveRequest(BaseModel):
    plan: dict


class PlanGenerateRequest(BaseModel):
    force: bool = False


class PlanSwapRequest(BaseModel):
    day_index: int
    section: str
    item_index: int
    alternative_index: int


class ReminderPrefsRequest(BaseModel):
    email_enabled: bool = True
    discord_enabled: bool = True
    discord_channel_id: Optional[str] = None


# ─── AI / Content Schemas ─────────────────────────────────────────────────────

class AIRequest(BaseModel):
    user_id: str
    extra_context: str = ""


# ─── Integration Schemas ──────────────────────────────────────────────────────

class DiscordLinkRequest(BaseModel):
    identity_id: str
    discord_user_id: str
