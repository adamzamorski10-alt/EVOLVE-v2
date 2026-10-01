"""
Training Execution Vertical Slice — tests for set logging, workout completion, and history.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.auth.jwt_utils import create_access_token
from app.database import engine
from app.models import ExerciseResultDB, ExerciseSetDB, UserDB
from main import app


client = TestClient(app)


def _seed_user(**overrides) -> tuple[UserDB, str]:
    suffix = uuid.uuid4().hex[:10]
    email = f"exec-{suffix}@example.com"
    payload = {
        "email": email,
        "password": "SecurePassword123",
        "name": "Training Execution Test",
        "age": 30,
        "height": 180.0,
        "weight": 82.0,
        "target_weight": 78.0,
        "gender": "mężczyzna",
        "goal": "weight_loss",
        "frequency": "3-4 razy w tygodniu",
        "diet": "Balanced",
    }
    payload.update(overrides)
    r = client.post("/auth/register", json=payload)
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    token = r.json()["access_token"]
    with Session(engine) as session:
        user = session.exec(select(UserDB).where(UserDB.email == email)).first()
        assert user is not None
        return user, token


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_log_exercise_set_creates_row():
    user, token = _seed_user()
    payload = {
        "exercise_name": "Przysiad",
        "set_number": 1,
        "reps": 5,
        "weight_kg": 100.0,
        "rpe": 7,
    }
    r = client.post("/app/exercise-set", json=payload, headers=_headers(token))
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["set"]["exercise_name"] == "Przysiad"
    assert data["set"]["set_number"] == 1
    assert data["set"]["reps"] == 5

    with Session(engine) as session:
        row = session.exec(
            select(ExerciseSetDB).where(ExerciseSetDB.user_id == user.id)
        ).first()
        assert row is not None
        assert row.exercise_name == "Przysiad"
        assert row.set_number == 1


def test_log_multiple_sets_for_same_exercise():
    user, token = _seed_user()
    for i in range(1, 4):
        payload = {
            "exercise_name": "Przysiad",
            "set_number": i,
            "reps": 5,
            "weight_kg": 100.0,
            "rpe": 7,
        }
        r = client.post("/app/exercise-set", json=payload, headers=_headers(token))
        assert r.status_code == 200

    with Session(engine) as session:
        rows = list(
            session.exec(
                select(ExerciseSetDB)
                .where(ExerciseSetDB.user_id == user.id)
                .where(ExerciseSetDB.exercise_name == "Przysiad")
                .where(ExerciseSetDB.session_date == date.today())
            ).all()
        )
        assert len(rows) == 3


def test_complete_workout_creates_exercise_results_and_awards_xp():
    user, token = _seed_user()
    exercises = [
        {"exercise_name": "Przysiad", "sets": 3, "reps": 5, "weight_kg": 100.0, "rpe": 7, "notes": ""},
        {"exercise_name": "Wyciskanie", "sets": 3, "reps": 8, "weight_kg": 80.0, "rpe": 8, "notes": ""},
    ]
    r = client.post("/app/workout/complete", json={"exercises": exercises}, headers=_headers(token))
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["exercises_count"] == 2
    assert data["total_volume_kg"] == pytest.approx(3 * 5 * 100 + 3 * 8 * 80, rel=1e-3)
    assert data["avg_rpe"] == pytest.approx(7.5, rel=1e-1)
    assert data["xp_earned"] == 50

    with Session(engine) as session:
        db_user = session.get(UserDB, user.id)
        assert db_user is not None
        assert db_user.total_xp >= 50

        results = list(
            session.exec(
                select(ExerciseResultDB)
                .where(ExerciseResultDB.user_id == user.id)
                .where(ExerciseResultDB.session_date == date.today())
            ).all()
        )
        assert len(results) == 2
        names = {r.exercise_name for r in results}
        assert names == {"Przysiad", "Wyciskanie"}


def test_workout_history_returns_sessions():
    user, token = _seed_user()
    exercises = [
        {"exercise_name": "Przysiad", "sets": 3, "reps": 5, "weight_kg": 100.0, "rpe": 7, "notes": ""},
    ]
    client.post("/app/workout/complete", json={"exercises": exercises}, headers=_headers(token))

    r = client.get("/app/workout/history?limit=10", headers=_headers(token))
    assert r.status_code == 200
    data = r.json()
    assert "sessions" in data
    assert len(data["sessions"]) >= 1
    today_str = date.today().isoformat()
    today_session = next((s for s in data["sessions"] if s["date"] == today_str), None)
    assert today_session is not None
    assert today_session["exercises_count"] == 1
    assert today_session["total_volume_kg"] == pytest.approx(3 * 5 * 100, rel=1e-3)


def test_cannot_log_set_for_another_user():
    user_a, token_a = _seed_user(name="Alice")
    user_b, _ = _seed_user(name="Bob")

    payload = {
        "exercise_name": "Przysiad",
        "set_number": 1,
        "reps": 5,
        "weight_kg": 100.0,
        "rpe": 7,
    }
    r = client.post("/app/exercise-set", json=payload, headers=_headers(token_a))
    assert r.status_code == 200

    with Session(engine) as session:
        b_sets = list(
            session.exec(
                select(ExerciseSetDB).where(ExerciseSetDB.user_id == user_b.id)
            ).all()
        )
        assert len(b_sets) == 0


def test_cannot_complete_workout_for_another_user():
    user_a, token_a = _seed_user(name="Alice")
    user_b, _ = _seed_user(name="Bob")

    r = client.post(
        "/app/workout/complete",
        json={"exercises": [{"exercise_name": "Przysiad", "sets": 3, "reps": 5, "weight_kg": 100.0, "rpe": 7}]},
        headers=_headers(token_a),
    )
    assert r.status_code == 200

    with Session(engine) as session:
        b_results = list(
            session.exec(
                select(ExerciseResultDB).where(ExerciseResultDB.user_id == user_b.id)
            ).all()
        )
        assert len(b_results) == 0
