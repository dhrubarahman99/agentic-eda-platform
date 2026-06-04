# User account management and session token storage using SQLite + PBKDF2-HMAC-SHA256.

from __future__ import annotations

import hashlib
import secrets
from typing import Optional

from fastapi import Header, HTTPException

from app.utils.database import get_db

def _hash_password(password: str, salt: str) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
    return dk.hex()

def _extract_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None

def signup_user(name: str, email: str, password: str) -> Optional[str]:
    email = email.strip().lower()
    name  = name.strip()

    salt   = secrets.token_hex(16)
    hashed = _hash_password(password, salt)

    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()
        if existing:
            return None

        conn.execute(
            "INSERT INTO users (email, name, password_hash, salt) VALUES (?,?,?,?)",
            (email, name, hashed, salt),
        )
        user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        token = secrets.token_urlsafe(32)
        conn.execute(
            "INSERT INTO auth_tokens (token, user_id) VALUES (?,?)",
            (token, user_id),
        )

    return token

def login_user(email: str, password: str) -> Optional[tuple[str, dict]]:
    email = email.strip().lower()

    with get_db() as conn:
        row = conn.execute(
            "SELECT id, name, password_hash, salt, is_admin FROM users WHERE email = ?",
            (email,),
        ).fetchone()

        if not row:
            return None

        hashed = _hash_password(password, row["salt"])
        if not secrets.compare_digest(hashed, row["password_hash"]):
            return None

        token = secrets.token_urlsafe(32)
        conn.execute(
            "INSERT INTO auth_tokens (token, user_id) VALUES (?,?)",
            (token, row["id"]),
        )

    user_info = {
        "email":    email,
        "name":     row["name"],
        "id":       row["id"],
        "is_admin": bool(row["is_admin"]) if "is_admin" in row.keys() else False,
    }
    return token, user_info

def logout_user(token: str) -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM auth_tokens WHERE token = ?", (token,))

def get_user_from_token(token: str) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute(
            """SELECT u.id, u.email, u.name, u.is_admin
               FROM auth_tokens t
               JOIN users u ON u.id = t.user_id
               WHERE t.token = ?""",
            (token,),
        ).fetchone()

    if not row:
        return None
    return {
        "id":       row["id"],
        "email":    row["email"],
        "name":     row["name"],
        "is_admin": bool(row["is_admin"]),
    }

def get_user_id_from_token(authorization: Optional[str]) -> Optional[int]:
    token = _extract_token(authorization)
    if not token:
        return None
    user = get_user_from_token(token)
    return user["id"] if user else None

def update_user_credentials(
    user_id: int,
    current_password: str,
    new_name: Optional[str] = None,
    new_email: Optional[str] = None,
    new_password: Optional[str] = None,
) -> Optional[str]:
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT id, name, email, password_hash, salt FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()

            if not row:
                return "error"

            hashed_current = _hash_password(current_password, row["salt"])
            if not secrets.compare_digest(hashed_current, row["password_hash"]):
                return "wrong_password"

            apply_name     = new_name     if (new_name     and new_name     != row["name"])  else None
            apply_email    = new_email    if (new_email    and new_email    != row["email"]) else None
            apply_password = new_password if new_password else None

            if apply_name is None and apply_email is None and apply_password is None:
                return "no_change"

            if apply_email:
                existing = conn.execute(
                    "SELECT id FROM users WHERE email = ? AND id != ?",
                    (apply_email, user_id),
                ).fetchone()
                if existing:
                    return "email_taken"

            sets: list[str] = []
            params: list   = []

            if apply_name:
                sets.append("name = ?")
                params.append(apply_name)

            if apply_email:
                sets.append("email = ?")
                params.append(apply_email)

            if apply_password:
                new_salt   = secrets.token_hex(16)
                new_hash   = _hash_password(apply_password, new_salt)
                sets.append("password_hash = ?")
                sets.append("salt = ?")
                params.extend([new_hash, new_salt])

            params.append(user_id)
            conn.execute(
                f"UPDATE users SET {', '.join(sets)} WHERE id = ?",
                params,
            )

        return None

    except Exception:
        return "error"

async def require_admin(
    authorization: Optional[str] = Header(default=None),
) -> dict:
    """
    FastAPI dependency that validates the Bearer token and requires is_admin=1.
    Raises 401 for missing/invalid tokens, 403 for non-admin users.
    """
    token = _extract_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing authentication token.")
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user
