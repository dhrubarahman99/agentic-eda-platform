# Orchestrates preprocessing, statistical analysis, ML, and insight ranking.

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from app.models.schemas import (
    DatasetProfile,
    InsightResult,
    SkippedTask,
    TaskStatus,
    TaskTrace,
)
from app.modules.preprocessor import PreprocessingReport, preprocess
from app.modules.statistical_analysis import run_statistical_analysis
from app.modules.insight_ranker import rank_insights
from app.modules.ml_module import run_ml_analysis   # Phase 4 — now active

@dataclass
class AnalysisPlanTask:
    task_id: str
    module: str
    description: str
    trigger_condition: str
    status: str = "pending"
    skip_reason: Optional[str] = None

@dataclass
class AnalysisPlan:
    session_id: str
    tasks: list[AnalysisPlanTask] = field(default_factory=list)
    skipped_tasks: list[SkippedTask] = field(default_factory=list)

@dataclass
class AnalysisResult:
    session_id: str
    clean_df: pd.DataFrame
    preprocessing_report: PreprocessingReport
    insights: list[InsightResult]
    analysis_plan: AnalysisPlan
    orchestrator_trace: TaskTrace
    total_execution_time_ms: int

# Public entry point

def run_analysis(
    raw_df: pd.DataFrame,
    profile: DatasetProfile,
) -> AnalysisResult:
    start_total = time.time()
    session_id = profile.session_id

    # Step 1: Build analysis plan
    plan = _build_plan(profile)

    # Step 2: Preprocessing
    t0 = time.time()
    clean_df, prep_report = preprocess(raw_df, profile)
    _mark_executed(plan, "preprocessing", int((time.time() - t0) * 1000))

    # Step 3: Statistical analysis
    t0 = time.time()
    stat_insights = run_statistical_analysis(clean_df, profile)
    _mark_executed(plan, "statistical_analysis", int((time.time() - t0) * 1000))

    # Step 4: ML analysis (Phase 4 - now active)
    t0 = time.time()
    ml_insights, ml_skipped = run_ml_analysis(clean_df, profile)
    _mark_executed(plan, "ml_analysis", int((time.time() - t0) * 1000))

    # Surface ML skipped tasks and mark executed sub-tasks
    for sk in ml_skipped:
        plan.skipped_tasks.append(sk)
        for task in plan.tasks:
            if task.task_id == sk.task_id and task.status == "pending":
                task.status = "skipped"
                task.skip_reason = sk.skip_reason

    # Mark ML sub-tasks that actually ran as executed
    model_to_task = {
        "RandomForestRegressor": "ml_regression",
        "KMeans": "ml_clustering",
        "IsolationForest": "ml_anomaly",
        "ExponentialSmoothing": "ml_forecasting",
    }
    for ins in ml_insights:
        if isinstance(ins.value, dict):
            model_name = ins.value.get("model", "")
            task_id = model_to_task.get(model_name)
            if task_id:
                for task in plan.tasks:
                    if task.task_id == task_id:
                        task.status = "executed"
                        task.skip_reason = None

    # Step 5: Merge and rank all insights
    t0 = time.time()
    all_insights = stat_insights + ml_insights
    ranked_insights = rank_insights(all_insights, profile)
    _mark_executed(plan, "insight_ranking", int((time.time() - t0) * 1000))

    total_ms = int((time.time() - start_total) * 1000)
    executed_count = len([t for t in plan.tasks if t.status == "executed"])

    orchestrator_trace = TaskTrace(
        task_id=f"orch_{uuid.uuid4().hex[:8]}",
        module="orchestrator",
        operation="full_autonomous_analysis",
        columns_used=list(raw_df.columns),
        trigger_reason="Triggered automatically on CSV upload.",
        skipped_tasks=plan.skipped_tasks,
        plain_explanation=(
            f"The system analysed your dataset automatically. "
            f"It ran {executed_count} analysis tasks "
            f"({len(stat_insights)} statistical, {len(ml_insights)} ML) "
            f"and skipped {len(plan.skipped_tasks)} task(s) that were not applicable. "
            f"Total time: {total_ms}ms."
        ),
        execution_time_ms=total_ms,
        status=TaskStatus.completed,
    )

    return AnalysisResult(
        session_id=session_id,
        clean_df=clean_df,
        preprocessing_report=prep_report,
        insights=ranked_insights,
        analysis_plan=plan,
        orchestrator_trace=orchestrator_trace,
        total_execution_time_ms=total_ms,
    )

# Plan builder

def _build_plan(profile: DatasetProfile) -> AnalysisPlan:
    plan = AnalysisPlan(session_id=profile.session_id)

    numeric_count = len(profile.numeric_columns)
    datetime_count = len(profile.datetime_columns)
    row_count = profile.shape.get("rows", 0)

    # Always-run tasks
    plan.tasks.append(AnalysisPlanTask(
        task_id="preprocessing",
        module="preprocessor",
        description="Clean and prepare the data for analysis.",
        trigger_condition="Always runs on every dataset.",
    ))
    plan.tasks.append(AnalysisPlanTask(
        task_id="statistical_analysis",
        module="statistical_analysis",
        description="Run descriptive statistics, correlations, groupby, and trends.",
        trigger_condition="Always runs when at least one column is present.",
    ))
    plan.tasks.append(AnalysisPlanTask(
        task_id="ml_analysis",
        module="ml_module",
        description="Run ML models: feature importance, clustering, anomaly detection, forecasting.",
        trigger_condition="Always attempted; individual models activate based on data conditions.",
    ))
    plan.tasks.append(AnalysisPlanTask(
        task_id="insight_ranking",
        module="insight_ranker",
        description="Score and prioritise all insights by impact and confidence.",
        trigger_condition="Always runs after statistical and ML analysis.",
    ))

    # ML sub-tasks with explicit trigger conditions
    if profile.ml_eligible and profile.potential_target:
        plan.tasks.append(AnalysisPlanTask(
            task_id="ml_regression",
            module="ml_module",
            description=f"Random Forest: find what drives '{profile.potential_target}'.",
            trigger_condition=(
                f"ML-eligible dataset ({row_count} rows, {numeric_count} numeric cols) "
                f"with detected target '{profile.potential_target}'."
            ),
        ))

    if profile.ml_eligible and numeric_count >= 2:
        plan.tasks.append(AnalysisPlanTask(
            task_id="ml_clustering",
            module="ml_module",
            description="K-Means: discover natural segments in the data.",
            trigger_condition=f"ML-eligible with {numeric_count} numeric columns.",
        ))

    if row_count >= 50 and numeric_count >= 1:
        plan.tasks.append(AnalysisPlanTask(
            task_id="ml_anomaly",
            module="ml_module",
            description="Isolation Forest: detect anomalous rows.",
            trigger_condition=f"{row_count} rows and {numeric_count} numeric column(s).",
        ))

    if datetime_count > 0 and numeric_count > 0 and row_count >= 12:
        plan.tasks.append(AnalysisPlanTask(
            task_id="ml_forecasting",
            module="ml_module",
            description="Exponential Smoothing: project future values.",
            trigger_condition=f"Datetime column with {row_count} rows.",
        ))

    return plan

def _mark_executed(plan: AnalysisPlan, task_id: str, ms: int) -> None:
    for task in plan.tasks:
        if task.task_id == task_id and task.status not in ("skipped", "executed"):
            task.status = "executed"
            return
