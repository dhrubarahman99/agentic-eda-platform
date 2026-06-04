# LLM enhancement endpoints: rewrite insight/query text using OpenAI (optional, never changes data).

from __future__ import annotations

import copy
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.schemas import InsightResult, QueryResult
from app.modules.llm_enhancer import (
    enhance_insight,
    enhance_insights_batch,
    enhance_query_result,
    is_llm_available,
)
from app.utils.session_store import session_store

from app.api.analysis import _analysis_cache
from app.api.query import _query_history

router = APIRouter()

class LLMStatusResponse(BaseModel):
    available: bool
    reason: str
    model: str
    note: str = (
        "The LLM layer only improves phrasing. "
        "It never changes computed values, numbers, or rankings."
    )

class EnhancedInsightResponse(BaseModel):
    insight_id: str
    session_id: str
    llm_enhanced: bool
    plain_summary: str
    key_takeaway: str
    insight: InsightResult

class EnhancedAnalysisResponse(BaseModel):
    session_id: str
    llm_enhanced: bool
    total_insights: int
    insights: list[InsightResult]
    note: str = "Only plain_summary and key_takeaway fields were modified."

class EnhancedQueryResponse(BaseModel):
    query_id: str
    session_id: str
    llm_enhanced: bool
    plain_summary: str | None
    key_takeaway: str | None
    result: QueryResult

@router.get(
    "/llm/status",
    response_model=LLMStatusResponse,
    summary="Check LLM enhancement layer availability",
    tags=["LLM Enhancement"],
)
async def llm_status() -> LLMStatusResponse:
    available, reason = is_llm_available()
    return LLMStatusResponse(
        available=available,
        reason=reason,
        model="gpt-4o-mini",
    )

@router.post(
    "/llm/enhance/insight/{session_id}/{insight_id}",
    response_model=EnhancedInsightResponse,
    summary="Enhance a single insight's plain-language explanation",
    tags=["LLM Enhancement"],
)
async def enhance_single_insight(
    session_id: str,
    insight_id: str,
) -> EnhancedInsightResponse:
    if not session_store.exists(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    cached = _analysis_cache.get(session_id)
    if cached is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No analysis found for session '{session_id}'. "
                "Run POST /api/analyse/{session_id} first."
            ),
        )

    target = next(
        (ins for ins in cached.insights if ins.insight_id == insight_id),
        None,
    )
    if target is None:
        raise HTTPException(
            status_code=404,
            detail=f"Insight '{insight_id}' not found in session '{session_id}'.",
        )

    insight_copy = target.model_copy(deep=True)

    original_summary = insight_copy.plain_summary
    original_takeaway = insight_copy.key_takeaway

    enhanced = enhance_insight(insight_copy)

    llm_applied = (
        enhanced.plain_summary != original_summary
        or enhanced.key_takeaway != original_takeaway
    )

    return EnhancedInsightResponse(
        insight_id=insight_id,
        session_id=session_id,
        llm_enhanced=llm_applied,
        plain_summary=enhanced.plain_summary,
        key_takeaway=enhanced.key_takeaway,
        insight=enhanced,
    )

@router.post(
    "/llm/enhance/analysis/{session_id}",
    response_model=EnhancedAnalysisResponse,
    summary="Enhance all insights from a completed analysis",
    tags=["LLM Enhancement"],
)
async def enhance_full_analysis(session_id: str) -> EnhancedAnalysisResponse:
    if not session_store.exists(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    cached = _analysis_cache.get(session_id)
    if cached is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No analysis found for session '{session_id}'. "
                "Run POST /api/analyse/{session_id} first."
            ),
        )

    insights_copy = [ins.model_copy(deep=True) for ins in cached.insights]
    originals = [
        (ins.plain_summary, ins.key_takeaway) for ins in insights_copy
    ]

    enhanced_list = enhance_insights_batch(insights_copy)

    any_enhanced = any(
        enhanced_list[i].plain_summary != originals[i][0]
        or enhanced_list[i].key_takeaway != originals[i][1]
        for i in range(len(enhanced_list))
    )

    return EnhancedAnalysisResponse(
        session_id=session_id,
        llm_enhanced=any_enhanced,
        total_insights=len(enhanced_list),
        insights=enhanced_list,
    )

@router.post(
    "/llm/enhance/query/{session_id}/{query_id}",
    response_model=EnhancedQueryResponse,
    summary="Enhance a query result's plain-language explanation",
    tags=["LLM Enhancement"],
)
async def enhance_single_query(
    session_id: str,
    query_id: str,
) -> EnhancedQueryResponse:
    if not session_store.exists(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    cached_result = _query_result_cache.get(f"{session_id}:{query_id}")
    if cached_result is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Query result '{query_id}' not found. "
                "Ask the question again via POST /api/query/{session_id} first."
            ),
        )

    result_copy = cached_result.model_copy(deep=True)
    original_summary = result_copy.plain_summary
    original_takeaway = result_copy.key_takeaway

    enhanced = enhance_query_result(result_copy)

    llm_applied = (
        enhanced.plain_summary != original_summary
        or enhanced.key_takeaway != original_takeaway
    )

    return EnhancedQueryResponse(
        query_id=query_id,
        session_id=session_id,
        llm_enhanced=llm_applied,
        plain_summary=enhanced.plain_summary,
        key_takeaway=enhanced.key_takeaway,
        result=enhanced,
    )

# Stores full QueryResult objects so they can be enhanced on demand.

_query_result_cache: dict[str, QueryResult] = {}

def register_query_result(session_id: str, result: QueryResult) -> None:
    if result.status.value == "success":
        _query_result_cache[f"{session_id}:{result.query_id}"] = result