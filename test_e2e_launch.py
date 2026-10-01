"""
FitAI — End-to-End Launch Test Suite
=====================================
Testuje kluczowe ścieżki API w kolejności: rejestracja → logowanie →
refresh tokenów → profil → checkin → historia → dzień → race condition → zdrowie.

Użycie:
  # Lokalnie (serwer musi działać na :8000):
  python test_e2e_launch.py

  # Na produkcji:
  FITAI_API_URL=https://fitai-backend-l918.onrender.com python test_e2e_launch.py
"""

import os
import sys
import time
import uuid
import threading
import pytest
import requests

pytestmark = pytest.mark.skipif(
    os.getenv("FITAI_API_URL") is None and os.getenv("RUN_E2E") != "1",
    reason="E2E tests require a running server (set FITAI_API_URL or RUN_E2E=1)",
)

# ── Konfiguracja ──────────────────────────────────────────────────────────────
BASE_URL = os.getenv("FITAI_API_URL", "http://localhost:8000")

# ── Shared state (między testami) ─────────────────────────────────────────────
_ctx: dict = {}   # przechowuje token, user_number itp. między testami

# ── Helpers ───────────────────────────────────────────────────────────────────

def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _random_email() -> str:
    return f"test_{uuid.uuid4().hex[:10]}@fitai-e2e.test"


def _run_test(num: int, label: str, fn) -> bool:
    """Uruchamia jeden test, drukuje wynik, zwraca True/False."""
    try:
        msg = fn()
        print(f"  ✅ Test {num:>2}: {label} — PASS{(' (' + msg + ')') if msg else ''}")
        return True
    except AssertionError as exc:
        print(f"  ❌ Test {num:>2}: {label} — FAIL ({exc})")
        return False
    except Exception as exc:
        print(f"  ❌ Test {num:>2}: {label} — ERROR ({type(exc).__name__}: {exc})")
        return False


# ── Testy ─────────────────────────────────────────────────────────────────────

def test_1_register():
    """POST /auth/register — nowe konto."""
    email = _random_email()
    _ctx["email"] = email
    _ctx["password"] = "haslo123"

    r = requests.post(f"{BASE_URL}/auth/register", json={
        "email": email,
        "password": _ctx["password"],
    }, timeout=15)

    assert r.status_code == 200, f"status={r.status_code}, body={r.text[:200]}"
    data = r.json()
    assert "access_token" in data,  "brak access_token"
    assert "refresh_token" in data, "brak refresh_token"
    assert isinstance(data.get("user_number"), int), f"user_number nie jest int: {data.get('user_number')!r}"

    num = data["user_number"]
    dn  = data.get("display_name", "")
    expected_dn = f"Użytkownik#{num:04d}"
    assert dn == expected_dn, f"display_name={dn!r}, oczekiwano {expected_dn!r}"

    _ctx["user_number"]   = num
    _ctx["display_name"]  = dn
    _ctx["access_token"]  = data["access_token"]
    _ctx["refresh_token"] = data["refresh_token"]

    return f"user_number={num}, {dn}"


def test_2_register_duplicate():
    """POST /auth/register — duplikat emaila → 409."""
    r = requests.post(f"{BASE_URL}/auth/register", json={
        "email": _ctx["email"],
        "password": _ctx["password"],
    }, timeout=15)

    assert r.status_code == 409, f"status={r.status_code}, oczekiwano 409"
    detail = r.json().get("detail", "")
    assert "e-mailem" in detail or "email" in detail.lower(), \
        f"nieoczekiwany detail: {detail!r}"
    return f"409, detail OK"


def test_3_register_short_password():
    """POST /auth/register — hasło < 8 znaków → 422."""
    r = requests.post(f"{BASE_URL}/auth/register", json={
        "email": _random_email(),
        "password": "abc",
    }, timeout=15)

    assert r.status_code == 422, f"status={r.status_code}, oczekiwano 422"
    return "422"


def test_4_login():
    """POST /auth/login — poprawne dane → token + refresh_token."""
    r = requests.post(f"{BASE_URL}/auth/login", json={
        "email": _ctx["email"],
        "password": _ctx["password"],
    }, timeout=15)

    assert r.status_code == 200, f"status={r.status_code}, body={r.text[:200]}"
    data = r.json()
    assert "access_token"  in data, "brak access_token"
    assert "refresh_token" in data, "brak refresh_token"
    assert data.get("user_number") == _ctx["user_number"], \
        f"user_number={data.get('user_number')}, oczekiwano {_ctx['user_number']}"

    # Zaktualizuj tokeny (nowe z logowania)
    _ctx["access_token"]  = data["access_token"]
    _ctx["refresh_token"] = data["refresh_token"]
    return f"access_token OK, user_number={data['user_number']}"


def test_5_refresh_access():
    """POST /auth/refresh-access — wymiana refresh_token → nowy access_token."""
    r = requests.post(f"{BASE_URL}/auth/refresh-access", json={
        "refresh_token": _ctx["refresh_token"],
    }, timeout=15)

    assert r.status_code == 200, f"status={r.status_code}, body={r.text[:200]}"
    data = r.json()
    assert "access_token" in data, f"brak access_token w response: {data}"

    # Użyj nowego access_token do dalszych testów
    _ctx["access_token"] = data["access_token"]
    return "nowy access_token OK"


def test_6_refresh_wrong_type():
    """POST /auth/refresh-access — podanie access_token zamiast refresh → 401."""
    r = requests.post(f"{BASE_URL}/auth/refresh-access", json={
        "refresh_token": _ctx["access_token"],   # celowo zły typ
    }, timeout=15)

    assert r.status_code == 401, f"status={r.status_code}, oczekiwano 401"
    detail = r.json().get("detail", "")
    assert "typ" in detail.lower() or "type" in detail.lower() or "token" in detail.lower(), \
        f"nieoczekiwany detail: {detail!r}"
    return f"401, detail={detail!r}"


def test_7_profile():
    """GET /app/profile — zalogowany użytkownik."""
    r = requests.get(
        f"{BASE_URL}/app/profile",
        headers=_auth_headers(_ctx["access_token"]),
        timeout=15,
    )

    assert r.status_code == 200, f"status={r.status_code}, body={r.text[:200]}"
    data = r.json()
    assert data.get("user_number") == _ctx["user_number"], \
        f"user_number={data.get('user_number')}, oczekiwano {_ctx['user_number']}"

    dn = data.get("display_name", "")
    assert dn == _ctx["display_name"], \
        f"display_name={dn!r}, oczekiwano {_ctx['display_name']!r}"
    return f"user_number={data['user_number']}, display_name={dn!r}"


def test_8_checkin():
    """POST /app/checkin — zapisz dane dnia."""
    r = requests.post(
        f"{BASE_URL}/app/checkin",
        headers=_auth_headers(_ctx["access_token"]),
        json={
            "energy_level": 8,
            "fatigue_score": 5,
            "stress_level": 3,
        },
        timeout=15,
    )

    assert r.status_code == 200, f"status={r.status_code}, body={r.text[:200]}"
    data = r.json()
    xp = data.get("xp_earned", data.get("xp", -1))
    assert isinstance(xp, (int, float)) and xp >= 0, f"xp_earned={xp!r}"
    return f"xp_earned={xp}"


def test_9_checkin_history():
    """GET /app/checkin-history — historia zawiera log z energy_level=8."""
    r = requests.get(
        f"{BASE_URL}/app/checkin-history",
        headers=_auth_headers(_ctx["access_token"]),
        timeout=15,
    )

    assert r.status_code == 200, f"status={r.status_code}, body={r.text[:200]}"
    data = r.json()

    # Obsłuż zarówno listę jak i obiekt z kluczem "logs"/"history"
    logs = data if isinstance(data, list) else data.get("logs") or data.get("history") or []
    assert isinstance(logs, list), f"oczekiwano listy logów, otrzymano: {type(data)}"

    energy_values = [
        e.get("energy_level") or e.get("energy_score")
        for e in logs
        if isinstance(e, dict)
    ]
    assert any(v == 8 for v in energy_values), \
        f"brak logu z energy_level=8 w historii; znalezione wartości: {energy_values[:5]}"
    return f"{len(logs)} log(ów), energy_level=8 znaleziony ✓"


def test_10_day_today():
    """GET /app/day/today — dzienny log."""
    r = requests.get(
        f"{BASE_URL}/app/day/today",
        headers=_auth_headers(_ctx["access_token"]),
        timeout=15,
    )

    assert r.status_code == 200, f"status={r.status_code}, body={r.text[:200]}"
    data = r.json()
    log = data.get("log") or data.get("daily_log") or data
    assert isinstance(log, dict), f"log nie jest dict: {type(log)}"
    return "log OK"


def test_11_race_condition():
    """5 równoczesnych rejestracji → wszystkie 200, user_numbers unikalne."""
    N = 5
    results: list[dict] = [{}] * N
    emails  = [_random_email() for _ in range(N)]

    def register(idx: int):
        try:
            r = requests.post(f"{BASE_URL}/auth/register", json={
                "email": emails[idx],
                "password": "haslo_race_123",
            }, timeout=20)
            results[idx] = {"status": r.status_code, "data": r.json() if r.ok else {}}
        except Exception as exc:
            results[idx] = {"status": 0, "error": str(exc)}

    threads = [threading.Thread(target=register, args=(i,)) for i in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=25)

    statuses     = [r.get("status") for r in results]
    user_numbers = [r.get("data", {}).get("user_number") for r in results if r.get("status") == 200]

    failed = [s for s in statuses if s != 200]
    assert not failed, f"{len(failed)} request(ów) nie zwróciło 200: {statuses}"

    assert len(set(user_numbers)) == N, \
        f"user_numbers nie są unikalne! otrzymano: {user_numbers}"
    return f"5×200, user_numbers={sorted(user_numbers)}"


def test_12_health():
    """GET /health — serwer żyje."""
    r = requests.get(f"{BASE_URL}/health", timeout=10)

    assert r.status_code == 200, f"status={r.status_code}, body={r.text[:200]}"
    data = r.json()
    assert data.get("status") in ("ok", "healthy", "OK"), \
        f"status={data.get('status')!r}"
    version = data.get("version", "")
    assert version == "2.1.0", f"version={version!r}, oczekiwano '2.1.0'"
    return f"status={data['status']!r}, version={version!r}"


# ── Runner ────────────────────────────────────────────────────────────────────

TESTS = [
    (1,  "Rejestracja",                  test_1_register),
    (2,  "Duplikat e-maila (409)",        test_2_register_duplicate),
    (3,  "Złe hasło (422)",              test_3_register_short_password),
    (4,  "Logowanie",                    test_4_login),
    (5,  "Refresh-access",               test_5_refresh_access),
    (6,  "Refresh — zły typ (401)",      test_6_refresh_wrong_type),
    (7,  "Profil",                        test_7_profile),
    (8,  "Checkin — zapis",              test_8_checkin),
    (9,  "Checkin — historia",           test_9_checkin_history),
    (10, "Dzień (today)",                test_10_day_today),
    (11, "Race condition (5 wątków)",    test_11_race_condition),
    (12, "Health",                        test_12_health),
]


def main():
    print()
    print("  FitAI — E2E Launch Tests")
    print(f"  API: {BASE_URL}")
    print("  " + "─" * 48)

    # Sprawdź dostępność serwera przed testami
    try:
        requests.get(f"{BASE_URL}/health", timeout=8)
    except Exception:
        print(f"\n  ⛔ Nie można połączyć z {BASE_URL}")
        print("     Upewnij się że serwer działa lub ustaw FITAI_API_URL.\n")
        sys.exit(2)

    t_start = time.monotonic()
    passed  = 0

    for num, label, fn in TESTS:
        ok = _run_test(num, label, fn)
        if ok:
            passed += 1

    elapsed = time.monotonic() - t_start

    print()
    print("  " + "═" * 48)
    print(f"  Wyniki: {passed}/{len(TESTS)} testów przeszło")
    print(f"  Czas:   {elapsed:.1f}s")
    print("  " + "═" * 48)
    print()

    sys.exit(0 if passed == len(TESTS) else 1)


if __name__ == "__main__":
    main()
