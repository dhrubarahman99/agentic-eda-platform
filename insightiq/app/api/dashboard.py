# Dashboard, data preview, and column detail endpoints.

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.models.schemas import (
    DatasetProfile,
    DataQualityStatus,
    GuidedStartItem,
    InsightResult,
    QuickAction,
)
from app.modules.exporter import build_column_detail, build_dataset_preview
from app.utils.session_store import session_store
from app.api.analysis import _analysis_cache

router = APIRouter()

class SessionMetadata(BaseModel):
    session_id: str
    filename: str
    has_analysis: bool
    has_ml_insights: bool
    total_insights: int
    insight_types_present: list[str]

class DashboardResponse(BaseModel):
    session_id: str
    filename: str
    # Dataset overview
    shape: dict[str, int]
    numeric_columns: list[str]
    categorical_columns: list[str]
    datetime_columns: list[str]
    potential_target: Optional[str]
    ml_eligible: bool
    has_datetime: bool
    quality_status: str
    quality_note: str
    missing_rate_overall: float
    columns_with_high_missing: list[str]
    duplicate_row_count: int = 0
    # Column profiles (lightweight — full detail via /column/{name})
    columns: list[dict[str, Any]]
    # UX features
    quick_actions: list[QuickAction]
    guided_start: list[GuidedStartItem]
    # Analysis results (null if analysis not yet run)
    has_analysis: bool
    total_insights: int
    insights: list[InsightResult]
    plan_summary: Optional[dict[str, Any]]
    # ML status
    has_ml_insights: bool
    ml_models_run: list[str]
    # LLM status
    llm_available: bool

class DataPreviewResponse(BaseModel):
    session_id: str
    columns: list[str]
    rows: list[dict[str, Any]]
    total_rows_in_dataset: int
    preview_rows_shown: int
    offset: int = 0

class ColumnDetailResponse(BaseModel):
    session_id: str
    column_name: str
    detail: dict[str, Any]

@router.get(
    "/dashboard/{session_id}",
    response_model=DashboardResponse,
    summary="Get full dashboard data for a session in one call",
    tags=["Dashboard"],
)
async def get_dashboard(session_id: str) -> DashboardResponse:
    if not session_store.exists(session_id):
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found. Upload a CSV first.",
        )

    profile = session_store.get_profile(session_id)
    filename = session_store.get_filename(session_id) or "unknown"

    if profile is None:
        raise HTTPException(status_code=500, detail="Session profile missing.")

    cached = _analysis_cache.get(session_id)
    insights: list[InsightResult] = []
    plan_summary: Optional[dict] = None
    has_ml_insights = False
    ml_models_run: list[str] = []

    if cached is not None:
        insights = cached.insights
        has_ml_insights = any(
            i.source_module == "ml_module" for i in insights
        )
        ml_models_run = list({
            i.value.get("model", "")
            for i in insights
            if i.source_module == "ml_module" and isinstance(i.value, dict)
        } - {""})
        executed = [t for t in cached.analysis_plan.tasks if t.status == "executed"]
        skipped = [t for t in cached.analysis_plan.tasks if t.status == "skipped"]
        plan_summary = {
            "total_tasks": len(cached.analysis_plan.tasks),
            "executed_tasks": len(executed),
            "skipped_tasks": len(skipped),
            "executed_task_ids": [t.task_id for t in executed],
            "skipped_task_ids": [t.task_id for t in skipped],
        }

    llm_available = False
    try:
        from app.modules.llm_enhancer import is_llm_available
        llm_available, _ = is_llm_available()
    except Exception:
        pass

    columns_light = [
        {
            "name":         c.name,
            "dtype":        c.dtype.value,
            "semantic_tag": c.semantic_tag.value,
            "null_rate":    c.null_rate,
            "null_count":   c.null_count,
            "cardinality":  c.cardinality,
            "has_outliers": c.has_outliers,
            "outlier_count":c.outlier_count if c.outlier_count is not None else 0,
            "sample_values":c.sample_values,   # list[Any] — always present (default [])
            "is_binary":    c.is_binary,
        }
        for c in profile.columns
    ]

    return DashboardResponse(
        session_id=session_id,
        filename=filename,
        shape=profile.shape,
        numeric_columns=profile.numeric_columns,
        categorical_columns=profile.categorical_columns,
        datetime_columns=profile.datetime_columns,
        potential_target=profile.potential_target,
        ml_eligible=profile.ml_eligible,
        has_datetime=profile.has_datetime,
        quality_status=profile.data_quality.overall.value,
        quality_note=profile.summary_card.quality_note,
        missing_rate_overall=profile.summary_card.missing_rate_overall,
        columns_with_high_missing=profile.summary_card.columns_with_high_missing,
        duplicate_row_count=profile.summary_card.duplicate_row_count,
        columns=columns_light,
        quick_actions=profile.quick_actions,
        guided_start=profile.guided_start,
        has_analysis=cached is not None,
        total_insights=len(insights),
        insights=insights,
        plan_summary=plan_summary,
        has_ml_insights=has_ml_insights,
        ml_models_run=ml_models_run,
        llm_available=llm_available,
    )

@router.get(
    "/dashboard/{session_id}/preview",
    response_model=DataPreviewResponse,
    summary="Get a paginated preview of the uploaded dataset rows",
    tags=["Dashboard"],
)
async def get_data_preview(
    session_id: str,
    rows: int = Query(default=100, ge=1, le=500, description="Rows per page (1–500)"),
    offset: int = Query(default=0, ge=0, description="Starting row offset (0-based)"),
) -> DataPreviewResponse:
    if not session_store.exists(session_id):
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found.",
        )

    df = session_store.get_frame(f"{session_id}__clean")
    if df is None:
        df = session_store.get_frame(session_id)

    if df is None:
        raise HTTPException(status_code=500, detail="Dataset not found in session.")

    display_cols = [c for c in df.columns if not c.startswith("__")]
    df_display = df[display_cols]

    preview = build_dataset_preview(df_display, n_rows=rows, offset=offset)

    return DataPreviewResponse(
        session_id=session_id,
        **preview,
    )

@router.get(
    "/dashboard/{session_id}/column/{column_name}",
    response_model=ColumnDetailResponse,
    summary="Get detailed statistics for a single column",
    tags=["Dashboard"],
)
async def get_column_detail(
    session_id: str,
    column_name: str,
    use_clean: bool = Query(
        default=False,
        description=(
            "When true, compute statistics from the preprocessed (clean) "
            "DataFrame instead of the raw uploaded one. Only available after "
            "analysis has been run."
        ),
    ),
) -> ColumnDetailResponse:
    if not session_store.exists(session_id):
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found.",
        )

    profile = session_store.get_profile(session_id)
    if profile is None:
        raise HTTPException(status_code=500, detail="Session profile missing.")

    col_names = [c.name for c in profile.columns]
    if column_name not in col_names:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Column '{column_name}' not found in dataset. "
                f"Available columns: {', '.join(col_names[:10])}."
            ),
        )

    raw_df = session_store.get_frame(session_id)
    if raw_df is None:
        raise HTTPException(status_code=500, detail="Dataset not found in session.")

    if use_clean:
        clean_df = session_store.get_frame(f"{session_id}__clean")
        compute_live = clean_df is not None
        df = clean_df if clean_df is not None else raw_df
    else:
        df = raw_df
        compute_live = False

    detail = build_column_detail(
        df,
        column_name,
        profile,
        compute_live_stats=compute_live,
        raw_df=raw_df if compute_live else None,
    )

    detail["is_clean_data"] = use_clean and compute_live

    return ColumnDetailResponse(
        session_id=session_id,
        column_name=column_name,
        detail=detail,
    )