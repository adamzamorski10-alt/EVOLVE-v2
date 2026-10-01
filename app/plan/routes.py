"""Plan Routes — weekly plan generation, current plan, and swaps."""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import Session

from app.auth.dependencies import get_current_user
from app.database import get_session
from app.legacy_routes import (
    _build_weekly_plan,
    _enrich_exercises_with_progression,
    _is_profile_ready_for_plan,
)
from app.models import UserDB
from app.schemas import PlanGenerateRequest, PlanSwapRequest, WeeklyPlanSaveRequest

router = APIRouter(prefix="/app/plan", tags=["plan"])


@router.post("/generate", tags=["plan"])
def app_generate_plan(
    payload: PlanGenerateRequest,
    user: UserDB = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    try:
        if not _is_profile_ready_for_plan(user):
            raise HTTPException(status_code=400, detail="Najpierw uzupełnij pełny onboarding")
        if payload.force or not user.weekly_plan_json:
            plan = _build_weekly_plan(user)
            user.set_dict("weekly_plan_json", plan)
            # Wzbogać plan o sugestie progresji
            for day in plan.get("days", []):
                exercises = day.get("workout", {}).get("exercises", [])
                if exercises:
                    day["workout"]["exercises"] = _enrich_exercises_with_progression(exercises, user, session)
            user.set_dict("weekly_plan_json", plan)
            user.updated_at = datetime.now().isoformat()
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                print(f"[FitAI][app_generate_plan] IntegrityError user_id={user.id}: {exc}")
                raise HTTPException(status_code=409, detail="Konflikt zapisu planu — spróbuj ponownie.")
            except SQLAlchemyError as exc:
                session.rollback()
                print(f"[FitAI][app_generate_plan] SQLAlchemyError user_id={user.id}: {exc}")
                raise HTTPException(status_code=500, detail="Database error — please try again later")
        return {"status": "ok", "plan": user.get_dict("weekly_plan_json")}
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(status_code=500, detail="Database error — please try again later") from exc
    except Exception as exc:
        print(f"[FitAI][app_generate_plan] ERROR user_id={user.id} — {type(exc).__name__}: {exc}")
        raise HTTPException(status_code=500, detail="Błąd generowania planu. Spróbuj ponownie.")


@router.get("/current", tags=["plan"])
def app_get_plan(
    user: UserDB = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    GET /app/plan

    Zwraca tygodniowy plan użytkownika.
    Gwarantuje klucze: days, diet, training, generated_at, weekly_goal
    — nawet gdy plan jest pusty — żeby frontend nigdy nie dostał KeyError.
    """
    _EMPTY: dict = {
        "days": [],
        "diet": "",
        "training": "",
        "generated_at": None,
        "weekly_goal": None,
        "source": "empty",
    }

    try:
        if not user.weekly_plan_json:
            print(f"[FitAI][app_get_plan] user_id={user.id} — brak weekly_plan_json, zwracam pustą strukturę")
            return _EMPTY

        raw = user.get_dict("weekly_plan_json")
        if not raw or not isinstance(raw, dict):
            print(f"[FitAI][app_get_plan] user_id={user.id} — weekly_plan_json jest null/pusty po deserializacji")
            return _EMPTY

        diet_by_day: dict = {}
        training_by_day: dict = {}
        week_summary: dict = {}

        for day_entry in raw.get("days", []):
            day_name = day_entry.get("day", "")
            if not day_name:
                continue
            diet_by_day[day_name] = day_entry.get("meals", [])
            training_by_day[day_name] = {
                "title": day_entry.get("workout", {}).get("title", ""),
                "focus": day_entry.get("workout", {}).get("focus", ""),
                "exercises": day_entry.get("workout", {}).get("exercises", []),
                "day_type": day_entry.get("day_type", ""),
                "macros": day_entry.get("macros", {}),
                "is_sport_session": day_entry.get("is_sport_session", False),
            }
            week_summary[day_name] = {
                "day_type": day_entry.get("day_type", ""),
                "is_sport_session": day_entry.get("is_sport_session", False),
                "has_workout": bool(day_entry.get("workout", {}).get("exercises")),
                "has_meals": bool(day_entry.get("meals")),
            }

        result = {
            **raw,
            "diet":     diet_by_day     if diet_by_day     else {},
            "training": training_by_day if training_by_day else {},
            "week_summary": week_summary,
            "source":   "database",
        }
        result.setdefault("days", [])
        result.setdefault("generated_at", None)
        result.setdefault("weekly_goal", None)
        result.setdefault("plan_explanation", None)

        print(f"[FitAI][app_get_plan] user_id={user.id} — OK, dni={len(raw.get('days', []))}")
        return result

    except json.JSONDecodeError as exc:
        print(f"[FitAI][app_get_plan] ERROR user_id={user.id} — Uszkodzony JSON: {exc}")
        return {**_EMPTY, "error_hint": "corrupted_plan_json", "source": "error"}
    except SQLAlchemyError as exc:
        print(f"[FitAI][app_get_plan] DB ERROR user_id={user.id} — {type(exc).__name__}: {exc}")
        raise HTTPException(status_code=500, detail="Database error — please try again later") from exc
    except Exception as exc:
        print(f"[FitAI][app_get_plan] ERROR user_id={user.id} — {type(exc).__name__}: {exc}")
        return {**_EMPTY, "source": "error"}


@router.get("/week-summary", tags=["plan"])
def app_get_week_summary(
    user: UserDB = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    GET /app/plan/week-summary

    Zwraca kompaktowe podsumowanie tygodnia dla widoku Plan.
    """
    try:
        if not user.weekly_plan_json:
            return {
                "days": [],
                "strength_sessions": 0,
                "sport_sessions": 0,
                "rest_days": 0,
                "light_days": 0,
                "has_plan": False,
            }

        raw = user.get_dict("weekly_plan_json")
        if not raw or not isinstance(raw, dict):
            return {
                "days": [],
                "strength_sessions": 0,
                "sport_sessions": 0,
                "rest_days": 0,
                "light_days": 0,
                "has_plan": False,
            }

        days = raw.get("days", [])
        strength = sum(1 for d in days if not d.get("is_sport_session") and d.get("workout", {}).get("exercises"))
        sport = sum(1 for d in days if d.get("is_sport_session"))
        rest = sum(1 for d in days if d.get("day_type") == "rest")
        light = sum(1 for d in days if d.get("day_type") == "light")

        return {
            "days": [
                {
                    "day": d.get("day", ""),
                    "day_type": d.get("day_type", ""),
                    "is_sport_session": d.get("is_sport_session", False),
                    "title": d.get("workout", {}).get("title", ""),
                    "has_workout": bool(d.get("workout", {}).get("exercises")),
                    "has_meals": bool(d.get("meals")),
                }
                for d in days
            ],
            "strength_sessions": strength,
            "sport_sessions": sport,
            "rest_days": rest,
            "light_days": light,
            "has_plan": True,
            "plan_explanation": raw.get("plan_explanation"),
        }
    except Exception as exc:
        print(f"[FitAI][app_get_week_summary] ERROR user_id={user.id} — {type(exc).__name__}: {exc}")
        return {
            "days": [],
            "strength_sessions": 0,
            "sport_sessions": 0,
            "rest_days": 0,
            "light_days": 0,
            "has_plan": False,
        }


@router.put("/current", tags=["plan"])
def app_save_plan(
    payload: WeeklyPlanSaveRequest,
    user: UserDB = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if not isinstance(payload.plan, dict):
        raise HTTPException(status_code=422, detail="plan musi być obiektem JSON")

    plan = dict(payload.plan)
    plan.setdefault("days", [])
    plan.setdefault("diet", {})
    plan.setdefault("training", {})
    plan.setdefault("generated_at", datetime.now().isoformat())
    plan["source"] = "user_saved"

    try:
        db_user = session.get(UserDB, user.id)
        if not db_user:
            raise HTTPException(status_code=404, detail="Użytkownik nie znaleziony")
        db_user.set_dict("weekly_plan_json", plan)
        db_user.updated_at = datetime.now()
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
        return {"status": "ok", "plan": db_user.get_dict("weekly_plan_json")}
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(status_code=500, detail="Database error — please try again later") from exc


@router.post("/swap", tags=["plan"])
def app_swap_plan_item(
    payload: PlanSwapRequest,
    user: UserDB = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    try:
        if not user.weekly_plan_json:
            raise HTTPException(status_code=404, detail="Plan nie został jeszcze wygenerowany")
        plan = user.get_dict("weekly_plan_json")
        days = plan.get("days", [])
        if not (0 <= payload.day_index < len(days)):
            raise HTTPException(status_code=400, detail="Niepoprawny day_index")
        day = days[payload.day_index]
        section = (payload.section or "").strip().lower()

        if section == "meal":
            items = day.get("meals", [])
            if not (0 <= payload.item_index < len(items)):
                raise HTTPException(status_code=400, detail="Niepoprawny item_index dla meal")
            item = items[payload.item_index]
            alts = item.get("alternatives", [])
            if not (0 <= payload.alternative_index < len(alts)):
                raise HTTPException(status_code=400, detail="Niepoprawny alternative_index")
            current = {"name": item["name"], "kcal": item["kcal"]}
            selected = alts[payload.alternative_index]
            item.update({"name": selected["name"], "kcal": selected["kcal"]})
            item["alternatives"] = [a for i, a in enumerate(alts) if i != payload.alternative_index] + [current]

        elif section == "exercise":
            exercises = day.get("workout", {}).get("exercises", [])
            if not (0 <= payload.item_index < len(exercises)):
                raise HTTPException(status_code=400, detail="Niepoprawny item_index dla exercise")
            item = exercises[payload.item_index]
            alts = item.get("alternatives", [])
            if not (0 <= payload.alternative_index < len(alts)):
                raise HTTPException(status_code=400, detail="Niepoprawny alternative_index")
            current = {k: item.get(k) for k in ["name", "sets", "reps", "notes", "how_to"]}
            selected = alts[payload.alternative_index]
            item.update({k: selected.get(k) for k in ["name", "sets", "reps", "notes", "how_to"]})
            item["alternatives"] = [a for i, a in enumerate(alts) if i != payload.alternative_index] + [current]
        else:
            raise HTTPException(status_code=400, detail="section musi być meal albo exercise")

        user.set_dict("weekly_plan_json", plan)
        user.updated_at = datetime.now().isoformat()
        session.commit()
        return {"status": "ok", "plan": plan}
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(status_code=500, detail="Database error — please try again later") from exc
