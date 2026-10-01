"""
FitAI Database — SQLModel engine, session management, migrations
"""

from sqlalchemy import text as _text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, SQLModel, create_engine
from app.config import DATABASE_URL
from app.models import ExerciseSetDB, UserDB, UserNumberSequenceDB  # noqa: F401 — rejestruje tabele w metadata

# For in-memory SQLite we must use StaticPool so every connection shares the
# same single database. Otherwise each connection gets its own empty DB and
# TestClient tests see no data.
_engine_kwargs = {}
if DATABASE_URL == "sqlite:///:memory:":
    from sqlalchemy.pool import StaticPool
    _engine_kwargs["poolclass"] = StaticPool
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
elif DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

# Create database engine
engine = create_engine(
    DATABASE_URL,
    echo=False,
    **_engine_kwargs,
)

from sqlalchemy import event
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


def _backfill_user_numbers():
    """Uzupełnia brakujące numery dla starych kont (jednorazowo przy starcie)."""
    if not DATABASE_URL.startswith("sqlite"):
        return
    try:
        with engine.connect() as conn:
            # Sprawdź czy kolumna istnieje
            cols = {r[1] for r in conn.execute(
                _text("PRAGMA table_info(users)")
            ).fetchall()}
            if "user_number" not in cols:
                return  # Kolumna jeszcze nie istnieje — _ensure_legacy... to naprawi

            # Pobierz konta bez numeru posortowane chronologicznie
            rows = conn.execute(
                _text("SELECT id FROM users WHERE user_number IS NULL ORDER BY created_at ASC")
            ).fetchall()

            if not rows:
                return  # Nic do uzupełnienia

            # Pobierz aktualny MAX — użyj jako punkt startowy
            current_max = conn.execute(
                _text("SELECT COALESCE(MAX(user_number), 0) FROM users WHERE user_number IS NOT NULL")
            ).scalar()

            # Przypisz kolejne numery
            for i, (uid,) in enumerate(rows):
                current_max += 1
                conn.execute(
                    _text("UPDATE users SET user_number = :n, user_key = :k WHERE id = :id"),
                    {
                        "n": current_max,
                        "k": f"native:user:{current_max}",
                        "id": uid,
                    },
                )

            conn.commit()
            print(f"[FitAI] Uzupełniono user_number dla {len(rows)} kont "
                  f"(numery {current_max - len(rows) + 1}–{current_max})")

    except Exception as exc:
        print(f"[FitAI] Ostrzeżenie — backfill user_number: {exc}")


def create_db_and_tables():
    """Create all tables in database (run once at startup)."""
    SQLModel.metadata.create_all(engine)
    _ensure_legacy_sqlite_columns()
    _backfill_user_numbers()    # ← uzupełnia user_number dla istniejących kont

    # Backfill tabeli sekwencji dla kont które już mają user_number,
    # ale nie mają wpisu w user_number_sequence (stare konta)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                _text("""
                    SELECT id, user_number FROM users
                    WHERE user_number IS NOT NULL
                    AND id NOT IN (SELECT user_id FROM user_number_sequence)
                """)
            ).fetchall()
            for uid, unum in rows:
                conn.execute(
                    _text("INSERT INTO user_number_sequence (id, user_id) VALUES (:id, :uid)"),
                    {"id": unum, "uid": uid},
                )
            if rows:
                conn.commit()
                print(f"[FitAI] Zsynchronizowano user_number_sequence dla {len(rows)} kont")
    except Exception as exc:
        print(f"[FitAI] Ostrzeżenie — sync user_number_sequence: {exc}")


def _ensure_legacy_sqlite_columns():
    """Add missing columns to older local SQLite databases.

    SQLModel.metadata.create_all() does not alter existing tables, so older
    workspace databases need a tiny compatibility bootstrap for new columns.
    """
    if not DATABASE_URL.startswith("sqlite"):
        return

    table_columns = {
        "users": {
            "nickname": "TEXT",
            "user_number": "INTEGER",       # ← DODAJ
            "discord_user_id": "TEXT",
            "discord_connect_code": "TEXT",
            "discord_connect_code_expires_at": "TEXT",
            "reminder_time": "TEXT",
            "reminder_enabled": "INTEGER DEFAULT 0",
            "last_reminder_sent_date": "TEXT",
        },
        "daily_logs": {
            "meals_json": "TEXT DEFAULT '[]'",
            "workouts_json": "TEXT DEFAULT '[]'",
            "custom_meals_json": "TEXT DEFAULT '[]'",
            "energy_level": "INTEGER",      # ← DODAJ
            "stress_level": "INTEGER",      # ← DODAJ
            "fatigue_score": "INTEGER",     # ← DODAJ
            "mood_score": "INTEGER",        # ← DODAJ
            "sleep_hours": "REAL",          # ← DODAJ
            "sleep_quality": "INTEGER",     # ← DODAJ
            "sleep_start": "TEXT",          # ← DODAJ
            "sleep_end": "TEXT",            # ← DODAJ
            "rpe": "INTEGER",               # ← DODAJ
            "meals_eaten": "INTEGER",       # ← DODAJ
            "workouts_done": "INTEGER",     # ← DODAJ
            "notes": "TEXT",                # ← DODAJ
        },
        "drill_results": {
            "drill_category": "TEXT",
            "drill_sport": "TEXT",
            "target_pct": "INTEGER",
        },
    }

    try:
        with engine.connect() as conn:
            for table_name, required_columns in table_columns.items():
                existing_columns = {
                    row[1]
                    for row in conn.execute(_text(f"PRAGMA table_info({table_name})")).fetchall()
                }
                for column_name, ddl_type in required_columns.items():
                    if column_name not in existing_columns:
                        conn.execute(_text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl_type}"))
            conn.commit()
    except Exception as exc:
        print(f"[FitAI] Ostrzeżenie: nie udało się zaktualizować schematu SQLite: {exc}")


def get_session():
    """FastAPI Dependency — yields database session for each request."""
    with Session(engine) as session:
        yield session