# Scores and ranks InsightResult objects by impact, confidence, and type weight.

from __future__ import annotations

from app.models.schemas import (
    DatasetProfile,
    InsightResult,
    InsightType,
    InsightValidation,
    QualityStatus,
    Severity,
    ValidationMetric,
)

# Scoring configuration — explicit and auditable

# Weight of each score dimension (must sum to 1.0)
WEIGHT_IMPACT = 0.50
WEIGHT_CONFIDENCE = 0.35
WEIGHT_TYPE = 0.15

# Type weight — some insight types are intrinsically more actionable
TYPE_WEIGHTS: dict[str, float] = {
    InsightType.trend: 1.0,
    InsightType.correlation: 0.9,
    InsightType.ranking: 0.85,
    InsightType.segment: 0.85,
    InsightType.anomaly: 0.8,
    InsightType.distribution: 0.6,
    InsightType.missing_data: 0.5,
    InsightType.summary: 0.4,
}

MAX_INSIGHTS = 10   # maximum number of insights returned to the frontend

# Per-type caps — prevent low-value types from flooding the top-10
MAX_PER_TYPE: dict = {
    InsightType.distribution: 2,
}

# Public entry point

def rank_insights(
    insights: list[InsightResult],
    profile: DatasetProfile | None = None,
) -> list[InsightResult]:
    """
    Score, sort, and rank a list of InsightResult objects.

    Parameters
    ----------
    insights : raw list from statistical_analysis or ML module

    Returns
    -------
    Sorted list (highest composite_score first), truncated to MAX_INSIGHTS.
    Each item has .rank and .composite_score set.
    """
    if not insights:
        return []

    scored = [_score(ins) for ins in insights]
    scored.sort(key=lambda x: x.composite_score, reverse=True)

    # Assign ranks, respecting per-type caps
    type_counts: dict = {}
    ranked = []
    for ins in scored:
        if len(ranked) >= MAX_INSIGHTS:
            break
        cap = MAX_PER_TYPE.get(ins.insight_type)
        if cap is not None and type_counts.get(ins.insight_type, 0) >= cap:
            continue
        type_counts[ins.insight_type] = type_counts.get(ins.insight_type, 0) + 1
        ins.rank = len(ranked) + 1
        if profile is not None:
            ins.validation = _build_validation(ins, profile)
        ranked.append(ins)

    return ranked

# Internal scoring

def _score(ins: InsightResult) -> InsightResult:
    """Compute and set composite_score for a single InsightResult."""
    type_weight = TYPE_WEIGHTS.get(ins.insight_type, 0.5)

    composite = (
        WEIGHT_IMPACT * ins.impact_score
        + WEIGHT_CONFIDENCE * ins.confidence_score
        + WEIGHT_TYPE * type_weight
    )

    # Penalise if there is a high-severity reliability warning
    if ins.reliability_warning:
        if ins.reliability_warning.severity == Severity.high:
            composite *= 0.70
        elif ins.reliability_warning.severity == Severity.medium:
            composite *= 0.85

    ins.composite_score = round(min(1.0, max(0.0, composite)), 4)
    return ins

def _build_validation(
    ins: InsightResult,
    profile: DatasetProfile,
) -> InsightValidation:
    row_count = max(int(profile.shape.get("rows", 0)), 0)
    column_map = {c.name: c for c in profile.columns}
    used_columns = [column_map[c] for c in ins.columns_used if c in column_map]

    completeness = 1.0
    if used_columns:
        completeness = sum(1.0 - c.null_rate for c in used_columns) / len(used_columns)
    completeness = round(min(1.0, max(0.0, completeness)), 4)

    rows_evaluated = _estimate_rows_evaluated(ins, row_count)
    warning_penalty = _warning_penalty(ins)
    quality_penalty = {
        QualityStatus.good: 0.0,
        QualityStatus.fair: 0.06,
        QualityStatus.poor: 0.14,
    }.get(profile.data_quality.overall, 0.06)

    validation_score = (
        ins.confidence_score * 0.55
        + completeness * 0.25
        + min(1.0, rows_evaluated / 100) * 0.20
        - warning_penalty
        - quality_penalty
    )
    validation_score = round(min(1.0, max(0.0, validation_score)), 4)

    if validation_score >= 0.8:
        evidence_level = "Strong"
    elif validation_score >= 0.6:
        evidence_level = "Moderate"
    else:
        evidence_level = "Exploratory"

    metrics = _extract_metrics(ins, completeness)
    supporting_signals = _build_supporting_signals(ins, profile, rows_evaluated, completeness)
    caveats = _build_caveats(ins, profile, rows_evaluated, completeness)
    confidence_reason = _build_confidence_reason(ins, rows_evaluated, completeness)

    return InsightValidation(
        validation_score=validation_score,
        evidence_level=evidence_level,
        rows_evaluated=rows_evaluated,
        completeness=completeness,
        dataset_quality=profile.data_quality.overall,
        confidence_reason=confidence_reason,
        caveats=caveats,
        supporting_signals=supporting_signals,
        metrics=metrics,
    )

def _estimate_rows_evaluated(ins: InsightResult, fallback_rows: int) -> int:
    value = ins.value
    if isinstance(value, dict):
        if isinstance(value.get("n_rows_used"), int):
            return max(0, int(value["n_rows_used"]))
        period_data = value.get("period_data")
        if isinstance(period_data, list):
            return len(period_data)

    if ins.chart and ins.chart.data:
        if ins.chart.chart_type == "histogram":
            return int(sum(pt.value for pt in ins.chart.data))
        if ins.chart.chart_type == "scatter":
            return len(ins.chart.data)
        if ins.insight_type == InsightType.trend:
            return len(ins.chart.data)

    return fallback_rows

def _warning_penalty(ins: InsightResult) -> float:
    if not ins.reliability_warning:
        return 0.0
    return {
        Severity.low: 0.04,
        Severity.medium: 0.10,
        Severity.high: 0.18,
    }.get(ins.reliability_warning.severity, 0.08)

def _extract_metrics(ins: InsightResult, completeness: float) -> list[ValidationMetric]:
    metrics: list[ValidationMetric] = [
        ValidationMetric(label="Completeness", value=f"{completeness * 100:.0f}%"),
    ]
    value = ins.value
    if not isinstance(value, dict):
        return metrics

    if "r_squared" in value:
        metrics.append(ValidationMetric(label="R²", value=f"{float(value['r_squared']):.3f}"))
    if "p_value" in value:
        p_value = float(value["p_value"])
        metrics.append(ValidationMetric(label="p-value", value=f"{p_value:.4f}"))
    if "skewness" in value:
        metrics.append(ValidationMetric(label="Skewness", value=f"{float(value['skewness']):.2f}"))
    if "silhouette_score" in value:
        metrics.append(ValidationMetric(label="Silhouette", value=f"{float(value['silhouette_score']):.2f}"))
    if "anomaly_pct" in value:
        metrics.append(ValidationMetric(label="Anomaly Rate", value=f"{float(value['anomaly_pct']):.2f}%"))
    if "n_anomalies" in value:
        metrics.append(ValidationMetric(label="Anomalies", value=str(int(value["n_anomalies"]))))

    pairs = value.get("pairs")
    if isinstance(pairs, list) and pairs:
        top_pair = pairs[0]
        if isinstance(top_pair, dict) and "correlation" in top_pair:
            metrics.append(
                ValidationMetric(
                    label="Top |r|",
                    value=f"{abs(float(top_pair['correlation'])):.3f}",
                )
            )

    return metrics[:5]

def _build_supporting_signals(
    ins: InsightResult,
    profile: DatasetProfile,
    rows_evaluated: int,
    completeness: float,
) -> list[str]:
    signals = [
        f"Evaluated on {rows_evaluated:,} row(s) or plotted records.",
        f"Key columns are {completeness * 100:.0f}% complete on average.",
        f"Dataset quality is rated {profile.data_quality.overall.value}.",
    ]
    if ins.trace and ins.trace.execution_time_ms is not None:
        signals.append(f"Computation trace captured in {ins.trace.execution_time_ms} ms.")
    return signals[:4]

def _build_caveats(
    ins: InsightResult,
    profile: DatasetProfile,
    rows_evaluated: int,
    completeness: float,
) -> list[str]:
    caveats: list[str] = []
    if ins.reliability_warning:
        caveats.append(ins.reliability_warning.message)
    if rows_evaluated and rows_evaluated < 30:
        caveats.append("This insight is based on a relatively small sample.")
    if completeness < 0.85:
        caveats.append("Missing values in the key columns may weaken this result.")
    if profile.data_quality.overall == QualityStatus.poor:
        caveats.append("Overall dataset quality is poor, so treat this as exploratory.")
    return caveats[:3]

def _build_confidence_reason(
    ins: InsightResult,
    rows_evaluated: int,
    completeness: float,
) -> str:
    value = ins.value if isinstance(ins.value, dict) else {}
    metric = ""
    if "r_squared" in value:
        metric = f" R² = {float(value['r_squared']):.3f}."
    elif "p_value" in value:
        metric = f" p-value = {float(value['p_value']):.4f}."
    elif "silhouette_score" in value:
        metric = f" Silhouette score = {float(value['silhouette_score']):.2f}."
    elif "anomaly_pct" in value:
        metric = f" Anomaly rate = {float(value['anomaly_pct']):.2f}%."
    elif "pairs" in value and isinstance(value["pairs"], list) and value["pairs"]:
        top_pair = value["pairs"][0]
        if isinstance(top_pair, dict) and "correlation" in top_pair:
            metric = f" Strongest correlation |r| = {abs(float(top_pair['correlation'])):.3f}."

    return (
        f"Confidence is based on {rows_evaluated:,} evaluated row(s), "
        f"{completeness * 100:.0f}% average completeness in the key columns,"
        f" and the method-specific evidence captured for this insight.{metric}"
    )
