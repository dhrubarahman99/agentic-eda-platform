# Full analysis pipeline: preprocessing, statistical analysis, ML, and insight ranking.

from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.models.schemas import (
    ErrorResponse,
    ErrorType,
    InsightResult,
    TaskTrace,
)
from app.modules.orchestrator import AnalysisResult, run_analysis
from app.modules.llm_enhancer import enhance_insights_batch
from app.utils.session_store import session_store

router = APIRouter()

# In-memory cache for analysis results (keyed by session_id)
_analysis_cache: dict[str, AnalysisResult] = {}

class TransformationLogResponse(BaseModel):
    column: str | None
    operation: str
    detail: str
    rows_affected: int = 0

class PreprocessingReportResponse(BaseModel):
    session_id: str
    original_shape: tuple[int, int]
    clean_shape: tuple[int, int]
    transformations: list[TransformationLogResponse]
    columns_dropped: list[str]
    new_columns_added: list[str]
    outlier_flag_column: str | None
    execution_time_ms: int
    plain_summary: str
    task_trace: TaskTrace | None

class AnalysisPlanTaskResponse(BaseModel):
    task_id: str
    module: str
    description: str
    trigger_condition: str
    status: str
    skip_reason: str | None = None

class AnalysisPlanResponse(BaseModel):
    session_id: str
    tasks: list[AnalysisPlanTaskResponse]
    total_tasks: int
    executed_tasks: int
    skipped_tasks: int

class AnalysisResponse(BaseModel):
    session_id: str
    status: str = "success"
    total_insights: int
    insights: list[InsightResult]
    preprocessing: PreprocessingReportResponse
    plan: AnalysisPlanResponse
    orchestrator_trace: TaskTrace
    total_execution_time_ms: int
    message: str = "Analysis complete."

def _prep_report_to_response(result: AnalysisResult) -> PreprocessingReportResponse:
    rpt = result.preprocessing_report
    return PreprocessingReportResponse(
        session_id=rpt.session_id,
        original_shape=rpt.original_shape,
        clean_shape=rpt.clean_shape,
        transformations=[
            TransformationLogResponse(
                column=t.column,
                operation=t.operation,
                detail=t.detail,
                rows_affected=t.rows_affected,
            )
            for t in rpt.transformations
        ],
        columns_dropped=rpt.columns_dropped,
        new_columns_added=rpt.new_columns_added,
        outlier_flag_column=rpt.outlier_flag_column,
        execution_time_ms=rpt.execution_time_ms,
        plain_summary=rpt.to_plain_summary(),
        task_trace=rpt.task_trace,
    )

def _plan_to_response(result: AnalysisResult) -> AnalysisPlanResponse:
    plan = result.analysis_plan
    executed = [t for t in plan.tasks if t.status == "executed"]
    skipped = [t for t in plan.tasks if t.status == "skipped"]
    return AnalysisPlanResponse(
        session_id=plan.session_id,
        tasks=[
            AnalysisPlanTaskResponse(
                task_id=t.task_id,
                module=t.module,
                description=t.description,
                trigger_condition=t.trigger_condition,
                status=t.status,
                skip_reason=t.skip_reason,
            )
            for t in plan.tasks
        ],
        total_tasks=len(plan.tasks),
        executed_tasks=len(executed),
        skipped_tasks=len(skipped),
    )

def _get_cached_or_404(session_id: str) -> AnalysisResult:
    result = _analysis_cache.get(session_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No analysis found for session '{session_id}'. "
                "Run POST /api/analyse/{session_id} first."
            ),
        )
    return result

@router.post(
    "/analyse/{session_id}",
    response_model=AnalysisResponse,
    summary="Run autonomous analysis on an uploaded dataset",
    tags=["Analysis"],
)
async def run_analysis_endpoint(
    session_id: str,
    target_column: Optional[str] = Query(
        default=None,
        description=(
            "Override the auto-detected target column. "
            "Must be a column that exists in the dataset. "
            "If omitted the profiler's auto-detected target is used."
        ),
    ),
) -> AnalysisResponse:
    if not session_store.exists(session_id):
        raise HTTPException(
            status_code=404,
            detail=(
                f"Session '{session_id}' not found. "
                "Please upload a CSV file first via POST /api/upload."
            ),
        )

    raw_df = session_store.get_frame(session_id)
    profile = session_store.get_profile(session_id)

    if raw_df is None or profile is None:
        raise HTTPException(
            status_code=500,
            detail="Session data is corrupted. Please re-upload your file.",
        )

    if target_column is not None:
        if target_column in list(raw_df.columns):
            profile = profile.model_copy(update={"potential_target": target_column})
            session_store._profiles[session_id] = profile
        else:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Target column '{target_column}' not found in dataset. "
                    f"Available columns: {', '.join(list(raw_df.columns)[:10])}."
                ),
            )

    try:
        result = run_analysis(raw_df, profile)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error_id=str(uuid.uuid4()),
                error_type=ErrorType.parse_failure,
                message=(
                    "An error occurred while analysing your dataset. "
                    "Please check your file and try again."
                ),
                reason=str(exc),
                suggestions=[
                    "Ensure your CSV has clean numeric and date columns.",
                    "Try re-uploading the file.",
                ],
            ).model_dump(),
        )

    result.insights = enhance_insights_batch(result.insights)

    _analysis_cache[session_id] = result

    session_store._frames[f"{session_id}__clean"] = result.clean_df

    session_store.save_analysis_to_db(
        session_id=session_id,
        insights=result.insights,
        prep_report_summary=result.preprocessing_report.to_plain_summary(),
    )

    return AnalysisResponse(
        session_id=session_id,
        total_insights=len(result.insights),
        insights=result.insights,
        preprocessing=_prep_report_to_response(result),
        plan=_plan_to_response(result),
        orchestrator_trace=result.orchestrator_trace,
        total_execution_time_ms=result.total_execution_time_ms,
    )

@router.get(
    "/analyse/{session_id}",
    response_model=AnalysisResponse,
    summary="Retrieve a previously computed analysis",
    tags=["Analysis"],
)
async def get_analysis(session_id: str) -> AnalysisResponse:
    result = _get_cached_or_404(session_id)
    return AnalysisResponse(
        session_id=session_id,
        total_insights=len(result.insights),
        insights=result.insights,
        preprocessing=_prep_report_to_response(result),
        plan=_plan_to_response(result),
        orchestrator_trace=result.orchestrator_trace,
        total_execution_time_ms=result.total_execution_time_ms,
    )

@router.get(
    "/analyse/{session_id}/insights",
    response_model=list[InsightResult],
    summary="Get only the ranked insights for a session",
    tags=["Analysis"],
)
async def get_insights(session_id: str) -> list[InsightResult]:
    result = _get_cached_or_404(session_id)
    return result.insights

@router.get(
    "/analyse/{session_id}/preprocessing",
    response_model=PreprocessingReportResponse,
    summary="Get the preprocessing report for a session",
    tags=["Analysis"],
)
async def get_preprocessing(session_id: str) -> PreprocessingReportResponse:
    result = _get_cached_or_404(session_id)
    return _prep_report_to_response(result)

@router.get(
    "/analyse/{session_id}/plan",
    response_model=AnalysisPlanResponse,
    summary="Get the analysis plan (what ran and what was skipped)",
    tags=["Analysis"],
)
async def get_plan(session_id: str) -> AnalysisPlanResponse:
    result = _get_cached_or_404(session_id)
    return _plan_to_response(result)
