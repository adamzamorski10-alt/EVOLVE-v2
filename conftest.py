"""
Pytest configuration for FitAI tests.

Ensures tests run against an isolated in-memory SQLite database and
that rate limiting does not interfere with test execution.
"""

import os
import sys

# Use in-memory SQLite for tests so each pytest invocation starts fresh.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

# Bump rate limits to effectively-unlimited values before any app imports.
os.environ.setdefault("AI_RATE_PER_MINUTE", "999999/minute")
os.environ.setdefault("AI_RATE_PER_HOUR", "999999/hour")


def _disable_limiters():
    """Find and disable all slowapi limiters across the app."""
    modules_to_check = [
        "app",
        "app.auth.routes",
        "app.legacy_routes",
        "app.ai.routes",
        "app.notifications.routes",
    ]
    for mod_name in modules_to_check:
        try:
            mod = sys.modules.get(mod_name)
            if mod is None:
                continue
            limiter = getattr(mod, "limiter", None)
            if limiter is not None:
                limiter.enabled = False
                fallback = getattr(limiter, "_in_memory_fallback", None)
                if isinstance(fallback, list):
                    fallback.clear()
        except Exception:
            pass


def pytest_configure(config):
    """After app is imported, disable all limiters for TestClient tests."""
    try:
        # Force import of app modules so we can find their limiters
        import app
        import app.auth.routes
        import app.legacy_routes
        import app.ai.routes
        _disable_limiters()
    except Exception:
        pass


def pytest_runtest_setup(item):
    """Disable limiters and clear state before each test."""
    _disable_limiters()
