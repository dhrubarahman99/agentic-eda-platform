# SQLite connection manager and schema initialisation for InsightIQ.

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

DB_PATH = Path(__file__).parent.parent.parent / "insightiq.db"

@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT    UNIQUE NOT NULL,
    name          TEXT    NOT NULL,
    password_hash TEXT    NOT NULL,
    salt          TEXT    NOT NULL,
    created_at    TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS auth_tokens (
    token      TEXT    PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS dataset_sessions (
    session_id       TEXT    PRIMARY KEY,
    user_id          INTEGER REFERENCES users(id) ON DELETE SET NULL,
    filename         TEXT    NOT NULL,
    row_count        INTEGER DEFAULT 0,
    col_count        INTEGER DEFAULT 0,
    quality_status   TEXT    DEFAULT 'good',
    potential_target TEXT,
    has_analysis     INTEGER DEFAULT 0,
    total_insights   INTEGER DEFAULT 0,
    has_ml_insights  INTEGER DEFAULT 0,
    profile_json     TEXT,
    insights_json    TEXT,
    prep_report_json TEXT,
    created_at       TEXT    DEFAULT (datetime('now')),
    last_accessed    TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS feedback (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id     TEXT    UNIQUE NOT NULL,
    user_id       INTEGER REFERENCES users(id) ON DELETE SET NULL,
    session_id    TEXT,
    query_id      TEXT,
    question      TEXT    NOT NULL,
    intent        TEXT    NOT NULL,
    columns_used  TEXT,
    plain_summary TEXT,
    feedback      TEXT    NOT NULL CHECK(feedback IN ('positive','negative')),
    created_at    TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS query_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    query_id   TEXT    UNIQUE NOT NULL,
    user_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    session_id TEXT,
    question   TEXT    NOT NULL,
    intent     TEXT,
    status     TEXT,
    created_at TEXT    DEFAULT (datetime('now'))
);
"""

def init_db() -> None:
    with get_db() as conn:
        conn.executescript(_DDL)
    _migrate_users_json()
    _migrate_feedback_json()
    _migrate_add_is_admin()
    _seed_admin()

_USERS_JSON    = DB_PATH.parent / "users.json"
_FEEDBACK_JSON = DB_PATH.parent / "feedback_store.json"

def _migrate_users_json() -> None:
    if not _USERS_JSON.exists():
        return

    try:
        data = json.loads(_USERS_JSON.read_text(encoding="utf-8"))
    except Exception:
        return  # corrupted file — skip silently

    if not isinstance(data, dict):
        return

    with get_db() as conn:
        for email, info in data.items():
            email = email.strip().lower()
            name          = info.get("name", "")
            password_hash = info.get("password", "")
            salt          = info.get("salt", "")
            if not email or not password_hash:
                continue
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO users (email, name, password_hash, salt) VALUES (?,?,?,?)",
                    (email, name, password_hash, salt),
                )
            except Exception:
                pass  # skip individual bad rows; never abort the migration

    try:
        _USERS_JSON.rename(_USERS_JSON.with_suffix(".json.migrated"))
    except Exception:
        pass  # if rename fails, migration re-runs harmlessly (INSERT OR IGNORE)

def _migrate_feedback_json() -> None:
    if not _FEEDBACK_JSON.exists():
        return

    try:
        data = json.loads(_FEEDBACK_JSON.read_text(encoding="utf-8"))
    except Exception:
        return

    if not isinstance(data, list):
        return

    with get_db() as conn:
        for rec in data:
            if not isinstance(rec, dict):
                continue
            record_id = rec.get("record_id", "")
            question  = rec.get("question", "")
            intent    = rec.get("intent", "")
            feedback  = rec.get("feedback", "")
            if not record_id or not question or not intent:
                continue
            if feedback not in ("positive", "negative"):
                continue
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO feedback
                       (record_id, session_id, query_id, question, intent,
                        columns_used, plain_summary, feedback, created_at)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        record_id,
                        rec.get("session_id", ""),
                        rec.get("query_id", ""),
                        question,
                        intent,
                        json.dumps(rec.get("columns_used", [])),
                        (rec.get("plain_summary", "") or "")[:400],
                        feedback,
                        rec.get("timestamp", ""),
                    ),
                )
            except Exception:
                pass

    try:
        _FEEDBACK_JSON.rename(_FEEDBACK_JSON.with_suffix(".json.migrated"))
    except Exception:
        pass

def _migrate_add_is_admin() -> None:
    """Add is_admin column to users table if it doesn't already exist."""
    with get_db() as conn:
        try:
            conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
        except Exception:
            pass

def _seed_admin() -> None:
    import hashlib
    import os
    import secrets as _secrets

    admin_email    = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "").strip()
    admin_name     = os.environ.get("ADMIN_NAME", "Admin").strip()

    if not admin_email or not admin_password:
        return

    def _hash(password: str, salt: str) -> str:
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
        return dk.hex()

    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE email = ?", (admin_email,)
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE users SET is_admin = 1 WHERE email = ?", (admin_email,)
            )
        else:
            salt   = _secrets.token_hex(16)
            hashed = _hash(admin_password, salt)
            conn.execute(
                "INSERT INTO users (email, name, password_hash, salt, is_admin) "
                "VALUES (?,?,?,?,1)",
                (admin_email, admin_name, hashed, salt),
            )
