# Feedback recording and adaptation hints for query interpretation.

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from app.utils.auth_store import get_user_id_from_token
from app.utils.feedback_store import feedback_store

router = APIRouter()

class FeedbackRequest(BaseModel):
    query_id:     str
    session_id:   str
    question:     str
    intent:       str
    columns_used: list[str] = Field(default_factory=list)
    plain_summary:str = ""
    feedback:     Literal["positive", "negative"]

class FeedbackResponse(BaseModel):
    record_id: str
    message:   str

class FeedbackStatsResponse(BaseModel):
    total_records:  int
    positive_count: int
    negative_count: int
    store_path:     str

@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    summary="Submit feedback for a query answer",
    tags=["Feedback"],
)
async def submit_feedback(
    body: FeedbackRequest,
    authorization: Optional[str] = Header(default=None),
) -> FeedbackResponse:
    user_id = get_user_id_from_token(authorization)

    record_id = feedback_store.add_feedback(
        session_id=body.session_id,
        query_id=body.query_id,
        question=body.question,
        intent=body.intent,
        columns_used=body.columns_used,
        plain_summary=body.plain_summary,
        feedback=body.feedback,
        user_id=user_id,
    )
    label = "positive" if body.feedback == "positive" else "negative"
    return FeedbackResponse(
        record_id=record_id,
        message=f"Feedback recorded as {label} (id={record_id}).",
    )

@router.get(
    "/feedback",
    summary="List all stored feedback records",
    tags=["Feedback"],
)
async def list_feedback() -> list:
    return feedback_store.list_all()

@router.get(
    "/feedback/stats",
    response_model=FeedbackStatsResponse,
    summary="Feedback statistics",
    tags=["Feedback"],
)
async def feedback_stats() -> FeedbackStatsResponse:
    from app.utils.feedback_store import _STORE_PATH

    records  = feedback_store.list_all()
    positive = sum(1 for r in records if r.get("feedback") == "positive")
    negative = sum(1 for r in records if r.get("feedback") == "negative")

    return FeedbackStatsResponse(
        total_records=len(records),
        positive_count=positive,
        negative_count=negative,
        store_path=_STORE_PATH,
    )
