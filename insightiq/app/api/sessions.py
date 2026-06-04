# Session listing, status, and deletion endpoints.

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.utils.auth_store import get_user_id_from_token
from app.utils.session_store import session_store
from app.api.analysis import _analysis_cache
from app.api.llm import _query_result_cache

router = APIRouter()

class SessionListItem(BaseModel):
    session_id:      str
    filename:        str
    row_count:       int
    col_count:       int
    has_analysis:    bool
    has_ml_insights: bool
    total_insights:  int
    quality_status:  str

class SessionStatusResponse(BaseModel):
    session_id:          str
    filename:            str
    row_count:           int
    col_count:           int
    has_profile:         bool
    has_analysis:        bool
    has_clean_df:        bool
    has_ml_insights:     bool
    total_insights:      int
    total_queries_asked: int
    numeric_columns:     list[str]
    categorical_columns: list[str]
    datetime_columns:    list[str]
    quality_status:      str
    ml_eligible:         bool
    potential_target:    Optional[str]
    available_actions:   list[str]

class DeleteResponse(BaseModel):
    session_id: str
    deleted:    bool
    message:    str

@router.get(
    "/sessions",
    response_model=list[SessionListItem],
    summary="List all sessions (scoped to authenticated user when logged in)",
    tags=["Sessions"],
)
async def list_sessions(
    authorization: Optional[str] = Header(default=None),
) -> list[SessionListItem]:
    user_id = get_user_id_from_token(authorization)

    db_rows = session_store.list_db_sessions(user_id=user_id)

    result: list[SessionListItem] = []
    seen: set[str] = set()

    for row in db_rows:
        sid = row["session_id"]
        if sid in seen or "__" in sid:
            continue
        seen.add(sid)

        cached  = _analysis_cache.get(sid)
        if cached is not None:
            insights    = cached.insights
            has_ml      = any(i.source_module == "ml_module" for i in insights)
            has_analysis = True
            total_insights = len(insights)
        else:
            has_analysis   = bool(row.get("has_analysis", 0))
            has_ml         = bool(row.get("has_ml_insights", 0))
            total_insights = int(row.get("total_insights", 0))

        result.append(SessionListItem(
            session_id=sid,
            filename=row.get("filename", "unknown"),
            row_count=int(row.get("row_count", 0)),
            col_count=int(row.get("col_count", 0)),
            has_analysis=has_analysis,
            has_ml_insights=has_ml,
            total_insights=total_insights,
            quality_status=row.get("quality_status", "good"),
        ))

    for session_id in session_store.list_sessions():
        if "__" in session_id or session_id in seen:
            continue
        profile  = session_store.get_profile(session_id)
        filename = session_store.get_filename(session_id) or "unknown"
        if profile is None:
            continue
        canonical_id = profile.session_id
        if canonical_id in seen or session_id != canonical_id:
            continue
        seen.add(canonical_id)
        cached = _analysis_cache.get(canonical_id)
        insights   = cached.insights if cached else []
        has_ml     = any(i.source_module == "ml_module" for i in insights)
        result.append(SessionListItem(
            session_id=canonical_id,
            filename=filename,
            row_count=profile.shape.get("rows", 0),
            col_count=profile.shape.get("cols", 0),
            has_analysis=cached is not None,
            has_ml_insights=has_ml,
            total_insights=len(insights),
            quality_status=profile.data_quality.overall.value,
        ))

    return result

@router.get(
    "/sessions/{session_id}/status",
    response_model=SessionStatusResponse,
    summary="Get full status for a session",
    tags=["Sessions"],
)
async def get_session_status(session_id: str) -> SessionStatusResponse:
    if not session_store.exists(session_id):
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found.",
        )

    profile  = session_store.get_profile(session_id)
    filename = session_store.get_filename(session_id) or "unknown"

    if profile is None:
        raise HTTPException(status_code=500, detail="Profile missing.")

    cached       = _analysis_cache.get(session_id)
    has_clean_df = session_store.get_frame(f"{session_id}__clean") is not None
    insights     = cached.insights if cached else []
    has_ml       = any(i.source_module == "ml_module" for i in insights)

    total_queries = sum(
        1 for key in _query_result_cache
        if key.startswith(f"{session_id}:")
    )

    available: list[str] = []
    if cached is None:
        available.append("POST /api/analyse/{session_id} — run analysis")
    available.append("POST /api/query/{session_id} — ask a natural language question")
    if cached is not None:
        available.append("POST /api/llm/enhance/analysis/{session_id} — improve insight phrasing")
        available.append("GET /api/export/{session_id}/insights.csv — download insights")
        available.append("GET /api/export/{session_id}/insights.json — download full bundle")
    available.append("GET /api/dashboard/{session_id} — full dashboard data")
    available.append("GET /api/dashboard/{session_id}/preview — dataset preview")

    return SessionStatusResponse(
        session_id=session_id,
        filename=filename,
        row_count=profile.shape.get("rows", 0),
        col_count=profile.shape.get("cols", 0),
        has_profile=True,
        has_analysis=cached is not None,
        has_clean_df=has_clean_df,
        has_ml_insights=has_ml,
        total_insights=len(insights),
        total_queries_asked=total_queries,
        numeric_columns=profile.numeric_columns,
        categorical_columns=profile.categorical_columns,
        datetime_columns=profile.datetime_columns,
        quality_status=profile.data_quality.overall.value,
        ml_eligible=profile.ml_eligible,
        potential_target=profile.potential_target,
        available_actions=available,
    )

@router.delete(
    "/sessions/{session_id}",
    response_model=DeleteResponse,
    summary="Delete a session and all its cached data",
    tags=["Sessions"],
)
async def delete_session(session_id: str) -> DeleteResponse:
    if not session_store.exists(session_id):
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found.",
        )

    session_store.delete_session(session_id)
    session_store.delete_session(f"{session_id}__clean")

    _analysis_cache.pop(session_id, None)

    keys_to_delete = [k for k in _query_result_cache if k.startswith(f"{session_id}:")]
    for key in keys_to_delete:
        _query_result_cache.pop(key, None)

    return DeleteResponse(
        session_id=session_id,
        deleted=True,
        message=f"Session '{session_id}' and all associated data have been deleted.",
    )
