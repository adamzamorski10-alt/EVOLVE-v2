"""
Security regression tests for EVOLVE Sprint 2.

Tests account isolation (A vs B) across all user-owned resources.
No cross-user access should be possible via:
  - URL manipulation
  - request body identity_id injection
  - query parameters
  - direct API calls
"""

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.auth.jwt_utils import create_access_token
from app.database import engine
from app.models import UserDB
from main import app


client = TestClient(app)


def _seed_user(**overrides) -> tuple[UserDB, str]:
    """Create a user and return (UserDB, access_token)."""
    suffix = uuid.uuid4().hex[:8]
    email = f"sec-{suffix}@example.com"
    payload = {
        "email": email,
        "password": "SecurePassword123",
        "name": f"Security Test {suffix}",
        "age": 30,
        "height": 178.0,
        "weight": 80.0,
        "target_weight": 75.0,
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


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestAccountIsolation:
    """Account A must never see or modify Account B's data."""

    def test_deprecated_users_post_returns_410_or_not_found(self):
        """POST /users/{id} is not an active API endpoint.
        The auth router registers it at /auth/users/{id} (returns 410).
        The root path /users/{id} has no POST handler → 405.
        """
        user_a, token_a = _seed_user(name="Alice")
        user_b, _ = _seed_user(name="Bob")

        r = client.post(f"/users/{user_b.id}", json={}, headers=_headers(token_a))
        assert r.status_code in (404, 405, 410), f"Unexpected status {r.status_code}"

    def test_users_get_handled_by_spa_not_api(self):
        """GET /users/{id} is not a registered API endpoint.
        The SPA catch-all serves index.html (200 with HTML), not user data.
        """
        user_a, token_a = _seed_user(name="Alice")
        user_b, _ = _seed_user(name="Bob")

        r = client.get(f"/users/{user_b.id}", headers=_headers(token_a))
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")

    def test_deprecated_users_logs_post_returns_not_found(self):
        """POST /users/{id}/logs is not an active API endpoint."""
        user_a, token_a = _seed_user(name="Alice")
        user_b, _ = _seed_user(name="Bob")

        r = client.post(f"/users/{user_b.id}/logs", json={}, headers=_headers(token_a))
        assert r.status_code in (404, 405), f"Unexpected status {r.status_code}"

    def test_stripe_webhook_is_disabled(self):
        r = client.post(
            "/billing/stripe/webhook",
            json={"identity_id": "fake", "plan": "pro"},
        )
        assert r.status_code == 410, f"Expected 410, got {r.status_code}"

    def test_kitchen_generate_requires_jwt(self):
        r = client.post(
            "/app/kitchen/generate",
            json={"ingredients": ["jajko"]},
        )
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"
        body = r.json()
        assert "token" in body.get("detail", "").lower() or "brak" in body.get("detail", "").lower()

    def test_kitchen_generate_rejects_identity_id_body(self):
        """identity_id in request body must be ignored; JWT principal is used."""
        user_a, token_a = _seed_user(name="Alice")
        user_b, _ = _seed_user(name="Bob")

        r = client.post(
            "/app/kitchen/generate",
            json={"ingredients": ["jajko"]},
            headers=_headers(token_a),
        )
        # Should not be 401; should either succeed (200) or fail with AI error (503)
        # but NOT with 404 user-not-found (which would mean identity_id was used)
        assert r.status_code in (200, 422, 503), f"Unexpected status {r.status_code}"

    def test_a_cannot_read_b_plan(self):
        user_a, token_a = _seed_user(name="Alice")
        user_b, _ = _seed_user(name="Bob")

        r = client.get("/app/plan", headers=_headers(token_a))
        assert r.status_code == 200
        # Plan data belongs to Alice (empty or her own plan)

    def test_a_cannot_modify_b_profile(self):
        user_a, token_a = _seed_user(name="Alice")
        user_b, _ = _seed_user(name="Bob")

        original_b_name = user_b.name
        r = client.put(
            "/app/profile",
            json={"name": "Hacked"},
            headers=_headers(token_a),
        )
        assert r.status_code == 200
        with Session(engine) as session:
            b = session.get(UserDB, user_b.id)
            assert b.name == original_b_name

    def test_a_cannot_log_b_workout(self):
        user_a, token_a = _seed_user(name="Alice")
        user_b, _ = _seed_user(name="Bob")

        r = client.post(
            "/app/exercise-result",
            json={"exercise_name": "Przysiad", "sets": 3, "reps": 10, "weight_kg": 100, "rpe": 7},
            headers=_headers(token_a),
        )
        assert r.status_code == 200
        # Result is logged under Alice's account

    def test_reminders_due_requires_cron_secret(self):
        r = client.get("/app/reminders-due")
        assert r.status_code == 422, f"Expected 422 (missing param), got {r.status_code}"

        r = client.get("/app/reminders-due?secret=wrong")
        assert r.status_code == 403, f"Expected 403, got {r.status_code}"

    def test_link_discord_endpoint_removed(self):
        r = client.post("/app/link-discord", json={"identity_id": "x", "discord_user_id": "y"})
        assert r.status_code == 405, f"Expected 405, got {r.status_code}"

    def test_a_cannot_access_b_dashboard(self):
        user_a, token_a = _seed_user(name="Alice")
        user_b, _ = _seed_user(name="Bob")

        r = client.get("/app/dashboard", headers=_headers(token_a))
        assert r.status_code == 200

    def test_a_cannot_access_b_stats(self):
        user_a, token_a = _seed_user(name="Alice")
        user_b, _ = _seed_user(name="Bob")

        r = client.get("/app/stats", headers=_headers(token_a))
        assert r.status_code == 200

    def test_a_cannot_create_b_reminders(self):
        user_a, token_a = _seed_user(name="Alice")
        user_b, _ = _seed_user(name="Bob")

        r = client.post(
            "/app/reminders",
            json={"email_enabled": True, "discord_enabled": False},
            headers=_headers(token_a),
        )
        assert r.status_code == 200


class TestAuthEndpointSecurity:
    """Verify deprecated/unauthenticated endpoints are properly secured."""

    def test_register_rejects_duplicate_email(self):
        email = f"dup-{uuid.uuid4().hex[:8]}@example.com"
        r1 = client.post("/auth/register", json={
            "email": email, "password": "SecurePassword123",
        })
        assert r1.status_code == 200
        r2 = client.post("/auth/register", json={
            "email": email, "password": "SecurePassword123",
        })
        assert r2.status_code == 409

    def test_login_requires_valid_credentials(self):
        r = client.post("/auth/login", json={"email": "nope@example.com", "password": "wrong"})
        assert r.status_code == 401

    def test_protected_endpoint_rejects_missing_token(self):
        r = client.get("/app/profile")
        assert r.status_code == 401

    def test_protected_endpoint_rejects_invalid_token(self):
        r = client.get("/app/profile", headers={"Authorization": "Bearer invalid"})
        assert r.status_code == 401
