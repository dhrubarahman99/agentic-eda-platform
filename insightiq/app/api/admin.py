# Admin-only endpoints. All routes require a valid admin Bearer token.

from __future__ import annotations

from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.utils.auth_store import require_admin
from app.utils.database import get_db

router = APIRouter(prefix="/admin", tags=["Admin"])

class AdminStats(BaseModel):
    total_users:    int
    total_sessions: int
    total_feedback: int
    total_queries:  int

class AdminUserResponse(BaseModel):
    id:            int
    email:         str
    name:          str
    is_admin:      bool
    created_at:    str
    session_count: int
    query_count:   int

class AdminSessionResponse(BaseModel):
    session_id:     str
    filename:       str
    user_email:     Optional[str]
    row_count:      int
    col_count:      int
    has_analysis:   bool
    total_insights: int
    created_at:     str

class AdminFeedbackEntry(BaseModel):
    id:         int
    record_id:  str
    user_email: Optional[str]
    user_id:    Optional[int]
    question:   str
    intent:     str
    feedback:   str
    created_at: str

class AdminFeedbackGroup(BaseModel):
    user_id:        Optional[int]
    user_email:     Optional[str]
    user_name:      Optional[str]
    total_feedback: int
    positive:       int
    negative:       int
    entries:        list[AdminFeedbackEntry]

class MessageResponse(BaseModel):
    message: str

class DeletedCountResponse(BaseModel):
    message:       str
    deleted_count: int

@router.get("/stats", response_model=AdminStats, summary="System overview counts")
async def get_admin_stats(_: dict = Depends(require_admin)) -> AdminStats:
    with get_db() as conn:
        total_users    = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_sessions = conn.execute("SELECT COUNT(*) FROM dataset_sessions").fetchone()[0]
        total_feedback = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
        total_queries  = conn.execute("SELECT COUNT(*) FROM query_history").fetchone()[0]
    return AdminStats(
        total_users=total_users,
        total_sessions=total_sessions,
        total_feedback=total_feedback,
        total_queries=total_queries,
    )

@router.get("/users", response_model=list[AdminUserResponse], summary="List all user accounts")
async def list_users(_: dict = Depends(require_admin)) -> list[AdminUserResponse]:
    with get_db() as conn:
        rows = conn.execute(
            """SELECT u.id, u.email, u.name, u.is_admin, u.created_at,
                      COUNT(DISTINCT ds.session_id) AS session_count,
                      COUNT(DISTINCT qh.id)         AS query_count
               FROM users u
               LEFT JOIN dataset_sessions ds ON ds.user_id = u.id
               LEFT JOIN query_history    qh ON qh.user_id = u.id
               GROUP BY u.id
               ORDER BY u.created_at DESC"""
        ).fetchall()
    return [
        AdminUserResponse(
            id=r["id"],
            email=r["email"],
            name=r["name"],
            is_admin=bool(r["is_admin"]),
            created_at=r["created_at"] or "",
            session_count=r["session_count"] or 0,
            query_count=r["query_count"] or 0,
        )
        for r in rows
    ]

@router.delete(
    "/users/{user_id}",
    response_model=MessageResponse,
    summary="Delete a user account",
)
async def delete_user(user_id: int, _: dict = Depends(require_admin)) -> MessageResponse:
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, is_admin FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found.")
        if row["is_admin"]:
            raise HTTPException(status_code=403, detail="Admin accounts cannot be deleted.")
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    return MessageResponse(message=f"User {user_id} has been deleted.")

@router.get(
    "/sessions",
    response_model=list[AdminSessionResponse],
    summary="List all dataset sessions across all users",
)
async def list_sessions(_: dict = Depends(require_admin)) -> list[AdminSessionResponse]:
    with get_db() as conn:
        rows = conn.execute(
            """SELECT ds.session_id, ds.filename, ds.row_count, ds.col_count,
                      ds.has_analysis, ds.total_insights, ds.created_at,
                      u.email AS user_email
               FROM dataset_sessions ds
               LEFT JOIN users u ON u.id = ds.user_id
               ORDER BY ds.created_at DESC"""
        ).fetchall()
    return [
        AdminSessionResponse(
            session_id=r["session_id"],
            filename=r["filename"],
            user_email=r["user_email"],
            row_count=r["row_count"] or 0,
            col_count=r["col_count"] or 0,
            has_analysis=bool(r["has_analysis"]),
            total_insights=r["total_insights"] or 0,
            created_at=r["created_at"] or "",
        )
        for r in rows
    ]

@router.delete(
    "/sessions/{session_id}",
    response_model=MessageResponse,
    summary="Delete a dataset session record",
)
async def delete_session(session_id: str, _: dict = Depends(require_admin)) -> MessageResponse:
    with get_db() as conn:
        row = conn.execute(
            "SELECT session_id FROM dataset_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Session not found.")
        conn.execute(
            "DELETE FROM dataset_sessions WHERE session_id = ?", (session_id,)
        )
    return MessageResponse(message=f"Session {session_id} has been deleted.")

@router.get(
    "/feedback",
    response_model=list[AdminFeedbackGroup],
    summary="Feedback log grouped by user",
)
async def list_feedback(_: dict = Depends(require_admin)) -> list[AdminFeedbackGroup]:
    with get_db() as conn:
        rows = conn.execute(
            """SELECT f.id, f.record_id, f.user_id, f.question, f.intent,
                      f.feedback, f.created_at,
                      u.email AS user_email, u.name AS user_name
               FROM feedback f
               LEFT JOIN users u ON u.id = f.user_id
               ORDER BY f.created_at DESC"""
        ).fetchall()

    groups: dict = defaultdict(
        lambda: {"user_id": None, "user_email": None, "user_name": None, "entries": []}
    )

    for r in rows:
        key = r["user_id"] if r["user_id"] is not None else "anonymous"
        groups[key]["user_id"]    = r["user_id"]
        groups[key]["user_email"] = r["user_email"]
        groups[key]["user_name"]  = r["user_name"]
        groups[key]["entries"].append(
            AdminFeedbackEntry(
                id=r["id"],
                record_id=r["record_id"],
                user_email=r["user_email"],
                user_id=r["user_id"],
                question=r["question"],
                intent=r["intent"],
                feedback=r["feedback"],
                created_at=r["created_at"] or "",
            )
        )

    result: list[AdminFeedbackGroup] = []
    for g in groups.values():
        entries  = g["entries"]
        positive = sum(1 for e in entries if e.feedback == "positive")
        negative = sum(1 for e in entries if e.feedback == "negative")
        result.append(
            AdminFeedbackGroup(
                user_id=g["user_id"],
                user_email=g["user_email"],
                user_name=g["user_name"],
                total_feedback=len(entries),
                positive=positive,
                negative=negative,
                entries=entries,
            )
        )
    return result

@router.delete(
    "/feedback/user/{user_id}",
    response_model=DeletedCountResponse,
    summary="Clear all feedback records for a specific user",
)
async def clear_user_feedback(
    user_id: int,
    _: dict = Depends(require_admin),
) -> DeletedCountResponse:
    with get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM feedback WHERE user_id = ?", (user_id,)
        )
        deleted = cursor.rowcount
    return DeletedCountResponse(
        message=f"Cleared {deleted} feedback record(s) for user {user_id}.",
        deleted_count=deleted,
    )
