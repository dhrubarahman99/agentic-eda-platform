# Natural language query pipeline: interpretation, execution, and LLM explanation.

from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.models.schemas import (
    ErrorResponse,
    ErrorType,
    QueryObject,
    QueryResult,
    QueryStatus,
)
from app.modules.query_interpreter import interpret_query
from app.modules.query_executor import execute_query
from app.utils.auth_store import get_user_id_from_token
from app.utils.session_store import session_store
from app.utils.feedback_store import feedback_store

router = APIRouter()

# In-memory query history per session
_query_history: dict[str, list[dict[str, Any]]] = {}

class QueryRequest(BaseModel):
    question: str

class InterpretResponse(BaseModel):
    query_object: QueryObject | None = None
    error: ErrorResponse | None = None
    interpretable: bool

class QueryHistoryItem(BaseModel):
    query_id: str
    question: str
    intent: str
    status: str
    plain_summary: str | None = None

def _get_working_df(session_id: str):
    clean_df = session_store.get_frame(f"{session_id}__clean")
    if clean_df is not None:
        return clean_df, True
    raw_df = session_store.get_frame(session_id)
    return raw_df, False

def _record_history(
    session_id: str,
    question: str,
    result: QueryResult,
    user_id: Optional[int] = None,
) -> None:
    intent = result.interpretation.intent if result.interpretation else "unknown"
    if session_id not in _query_history:
        _query_history[session_id] = []
    _query_history[session_id].append({
        "query_id":     result.query_id,
        "question":     question,
        "intent":       intent,
        "status":       result.status.value,
        "plain_summary":result.plain_summary,
    })
    try:
        from app.utils.database import get_db
        with get_db() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO query_history
                   (query_id, user_id, session_id, question, intent, status)
                   VALUES (?,?,?,?,?,?)""",
                (
                    result.query_id,
                    user_id,
                    session_id,
                    question,
                    str(intent) if not isinstance(intent, str) else intent,
                    result.status.value,
                ),
            )
    except Exception:
        pass

def _register_for_llm(session_id: str, result: QueryResult) -> None:
    try:
        from app.api.llm import register_query_result
        register_query_result(session_id, result)
    except Exception:
        pass

def _apply_llm_explanation(
    question: str,
    query_obj: QueryObject,
    result: QueryResult,
) -> None:
    # Optionally rewrites plain_summary using OpenAI; no-ops on any failure.
    import os

    enabled = os.environ.get("LLM_ENHANCEMENT_ENABLED", "true").strip().lower()
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if enabled in ("false", "0", "no", "off") or not api_key:
        return
    if result.status.value != "success" or not result.plain_summary:
        return

    try:
        from app.modules import openai_planner

        result_data: dict[str, Any] = {}
        if isinstance(result.result_value, dict):
            # Only include scalar / short values; skip large lists
            for k, v in result.result_value.items():
                if isinstance(v, (int, float, str, bool)):
                    result_data[k] = v
                elif isinstance(v, list) and len(v) <= 5:
                    result_data[k] = v
        elif isinstance(result.result_value, list) and len(result.result_value) <= 10:
            result_data = {"records": result.result_value[:5]}

        if not result_data:
            return

        intent_str = query_obj.intent.value if query_obj else "query"
        explanation = openai_planner.explain_result(question, result_data, intent_str)

        if explanation and len(explanation) > 10:
            result.plain_summary = explanation
            if result.key_takeaway:
                # Append a short note rather than overwriting the computed takeaway
                result.key_takeaway = result.key_takeaway
    except Exception:
        pass

@router.post(
    "/query/{session_id}",
    response_model=QueryResult,
    summary="Ask a natural-language question about your dataset",
    tags=["Query"],
)
async def query_dataset(
    session_id: str,
    body: QueryRequest,
    authorization: Optional[str] = Header(default=None),
) -> QueryResult:
    if not session_store.exists(session_id):
        raise HTTPException(
            status_code=404,
            detail=(
                f"Session '{session_id}' not found. "
                "Please upload a CSV file first via POST /api/upload."
            ),
        )

    profile = session_store.get_profile(session_id)
    if profile is None:
        raise HTTPException(status_code=500, detail="Session profile missing.")

    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question cannot be empty.")

    df, using_clean = _get_working_df(session_id)
    if df is None:
        raise HTTPException(
            status_code=500,
            detail="No data found for this session. Please re-upload.",
        )

    user_id = get_user_id_from_token(authorization)

    try:
        feedback_hints = feedback_store.get_adaptation_hints(question, user_id=user_id)
    except Exception:
        feedback_hints = {}

    query_obj, interp_error = interpret_query(question, profile, feedback_hints=feedback_hints)

    if interp_error is not None:
        result = QueryResult(
            query_id=str(uuid.uuid4()),
            session_id=session_id,
            status=QueryStatus.error,
            error=interp_error,
        )
        _record_history(session_id, question, result, user_id=user_id)
        return result

    result = execute_query(query_obj, df, profile)
    result.session_id = session_id
    result.raw_query = question
    _apply_llm_explanation(question, query_obj, result)

    _register_for_llm(session_id, result)

    _record_history(session_id, question, result, user_id=user_id)
    return result

@router.post(
    "/query/{session_id}/interpret",
    response_model=InterpretResponse,
    summary="Interpret a question without executing it",
    tags=["Query"],
)
async def interpret_only(
    session_id: str,
    body: QueryRequest,
) -> InterpretResponse:
    if not session_store.exists(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    profile = session_store.get_profile(session_id)
    if profile is None:
        raise HTTPException(status_code=500, detail="Session profile missing.")

    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question cannot be empty.")

    query_obj, error = interpret_query(question, profile)

    return InterpretResponse(
        query_object=query_obj,
        error=error,
        interpretable=query_obj is not None,
    )

@router.get(
    "/query/{session_id}/history",
    response_model=list[QueryHistoryItem],
    summary="Get the query history for a session",
    tags=["Query"],
)
async def get_query_history(session_id: str) -> list[QueryHistoryItem]:
    if not session_store.exists(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    history = _query_history.get(session_id, [])
    return [QueryHistoryItem(**item) for item in history]