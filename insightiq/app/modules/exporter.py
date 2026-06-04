# Pure formatting functions for insights CSV, chart CSV, JSON bundle, and dataset preview.

from __future__ import annotations

import csv
import io
import json
from typing import TYPE_CHECKING, Any

# TYPE_CHECKING guard prevents the circular import at runtime.
# These names are only needed for type hints, not at execution time.
if TYPE_CHECKING:
    from app.models.schemas import DatasetProfile, InsightResult

# Insights → CSV

def insights_to_csv(insights: list) -> str:
    """
    Convert a ranked insight list to CSV string.
    Each row = one insight. Chart data and trace are excluded (too nested).
    """
    if not insights:
        return "rank,insight_id,type,source_module,columns_used,plain_summary,key_takeaway,impact_score,confidence_score,composite_score,has_chart,has_reliability_warning\n"

    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")

    writer.writerow([
        "rank", "insight_id", "type", "source_module",
        "columns_used", "plain_summary", "key_takeaway",
        "impact_score", "confidence_score", "composite_score",
        "has_chart", "has_reliability_warning",
    ])

    for ins in insights:
        writer.writerow([
            ins.rank,
            ins.insight_id,
            ins.insight_type.value,
            ins.source_module,
            "; ".join(ins.columns_used),
            ins.plain_summary,
            ins.key_takeaway,
            round(ins.impact_score, 4),
            round(ins.confidence_score, 4),
            round(ins.composite_score, 4),
            "yes" if ins.chart is not None else "no",
            "yes" if ins.reliability_warning is not None else "no",
        ])

    return output.getvalue()

# Chart data → CSV

def chart_to_csv(insight) -> str:
    """
    Convert the chart data of a single InsightResult to CSV string.
    Returns an error message string if the insight has no chart.
    """
    if insight.chart is None:
        return "error\nThis insight does not have chart data.\n"

    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")

    chart = insight.chart
    has_group = any(pt.group for pt in chart.data)

    if has_group:
        writer.writerow(["label", "value", "group"])
        for pt in chart.data:
            writer.writerow([pt.label, pt.value, pt.group or ""])
    else:
        writer.writerow(["label", "value"])
        for pt in chart.data:
            writer.writerow([pt.label, pt.value])

    return output.getvalue()

# Full analysis bundle → JSON

def build_export_bundle(
    profile,
    insights: list,
    preprocessing_summary: str,
    plan_tasks: list[dict],
) -> dict[str, Any]:
    """
    Build a complete JSON export bundle containing all analysis outputs.
    """
    return {
        "export_metadata": {
            "session_id": profile.session_id,
            "exported_by": "InsightIQ",
            "version": "6.0.0",
        },
        "dataset_summary": {
            "rows": profile.shape.get("rows", 0),
            "columns": profile.shape.get("cols", 0),
            "numeric_columns": profile.numeric_columns,
            "categorical_columns": profile.categorical_columns,
            "datetime_columns": profile.datetime_columns,
            "potential_target": profile.potential_target,
            "ml_eligible": profile.ml_eligible,
            "quality_status": profile.data_quality.overall.value,
            "quality_note": profile.summary_card.quality_note,
            "missing_rate_overall": profile.summary_card.missing_rate_overall,
            "columns_with_high_missing": profile.summary_card.columns_with_high_missing,
        },
        "preprocessing_summary": preprocessing_summary,
        "analysis_plan": plan_tasks,
        "insights": [
            {
                "rank": ins.rank,
                "insight_id": ins.insight_id,
                "type": ins.insight_type.value,
                "source_module": ins.source_module,
                "columns_used": ins.columns_used,
                "plain_summary": ins.plain_summary,
                "key_takeaway": ins.key_takeaway,
                "impact_score": round(ins.impact_score, 4),
                "confidence_score": round(ins.confidence_score, 4),
                "composite_score": round(ins.composite_score, 4),
                "reliability_warning": (
                    {
                        "severity": ins.reliability_warning.severity.value,
                        "message": ins.reliability_warning.message,
                    }
                    if ins.reliability_warning else None
                ),
                "chart": (
                    {
                        "type": ins.chart.chart_type.value,
                        "title": ins.chart.title,
                        "data": [
                            {"label": pt.label, "value": pt.value, "group": pt.group}
                            for pt in ins.chart.data
                        ],
                    }
                    if ins.chart else None
                ),
                "suggested_follow_ups": [
                    fu.question_text for fu in ins.suggested_follow_ups
                ],
            }
            for ins in insights
        ],
    }

# Dataset preview → dict

def build_dataset_preview(
    df,
    n_rows: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """
    Return a paginated slice of the DataFrame as a JSON-serialisable dict.

    offset — starting row index (0-based)
    n_rows — number of rows to return (one page)
    """
    total = len(df)
    safe_offset = max(0, min(offset, total))
    preview_df = df.iloc[safe_offset : safe_offset + n_rows].copy()

    for col in preview_df.columns:
        preview_df[col] = preview_df[col].apply(_to_json_safe)

    return {
        "columns": list(preview_df.columns),
        "rows": preview_df.to_dict(orient="records"),
        "total_rows_in_dataset": total,
        "preview_rows_shown": len(preview_df),
        "offset": safe_offset,
    }

def _to_json_safe(val: Any) -> Any:
    """Convert numpy/pandas scalar types to JSON-serialisable Python types."""
    import numpy as np
    import pandas as pd
    if val is None:
        return None
    if isinstance(val, float) and val != val:   # NaN
        return None
    if isinstance(val, np.integer):
        return int(val)
    if isinstance(val, np.floating):
        return None if val != val else round(float(val), 6)
    if isinstance(val, np.bool_):
        return bool(val)
    if isinstance(val, pd.Timestamp):
        return str(val)
    return val

def _format_display_number(val: float) -> str:
    """Format chart labels without scientific notation."""
    if val != val:
        return ""
    abs_val = abs(float(val))
    if abs_val == 0:
        return "0"
    if abs_val >= 1_000:
        return f"{val:,.2f}".rstrip("0").rstrip(".")
    if abs_val >= 1:
        return f"{val:.2f}".rstrip("0").rstrip(".")
    if abs_val >= 0.001:
        return f"{val:.4f}".rstrip("0").rstrip(".")
    return f"{val:.6f}".rstrip("0").rstrip(".")

# Column stats → dict

def build_column_detail(
    df,
    col_name: str,
    profile,
    compute_live_stats: bool = False,
    raw_df=None,
) -> dict[str, Any]:
    """
    Build a detailed breakdown for a single column.

    Parameters
    ----------
    df               : DataFrame to read the series from (raw or clean).
    col_name         : column to inspect.
    profile          : DatasetProfile (always from the original raw upload).
    compute_live_stats : when True, recompute numeric statistics directly from
                         ``df[col_name]`` instead of using the cached profile
                         stats.  Use this when ``df`` is a clean/preprocessed
                         frame whose distribution may differ from the raw one.
    raw_df           : the original (pre-preprocessing) DataFrame.  Required
                         when ``compute_live_stats=True`` so that outlier
                         detection can be performed on the raw non-null values
                         rather than on the imputed clean series.  Passing the
                         clean frame's imputed values to IQR outlier detection
                         compresses the IQR and produces spurious outlier
                         counts — this parameter prevents that.
    """
    import numpy as np
    import pandas as pd

    col_meta = next((c for c in profile.columns if c.name == col_name), None)
    if col_meta is None:
        return {"error": f"Column '{col_name}' not found in profile."}

    # Guard: column may have been dropped during preprocessing
    if col_name not in df.columns:
        return {"error": f"Column '{col_name}' not present in this DataFrame."}

    series = df[col_name]
    non_null = series.dropna()
    live_null_count = int(series.isna().sum())
    live_null_rate  = round(live_null_count / max(len(series), 1), 4)
    live_cardinality = int(series.nunique(dropna=True))

    detail: dict[str, Any] = {
        "name":          col_name,
        "dtype":         col_meta.dtype.value,
        "semantic_tag":  col_meta.semantic_tag.value,
        # When computing live stats (clean df) use the live counts; otherwise
        # use the profiler-cached counts which correspond to the raw frame.
        "null_count":    live_null_count   if compute_live_stats else col_meta.null_count,
        "null_rate":     live_null_rate    if compute_live_stats else col_meta.null_rate,
        "cardinality":   live_cardinality  if compute_live_stats else col_meta.cardinality,
        "has_outliers":  col_meta.has_outliers,
        "outlier_count": col_meta.outlier_count,
        "sample_values": col_meta.sample_values,
        "total_rows":    len(series),
    }

    # ── Numeric columns ──────────────────────────────────────────────────────
    is_numeric_col = col_meta.stats is not None  # True for non-binary numeric cols

    if is_numeric_col:
        if compute_live_stats:
            # ── Distribution stats from the clean (imputed) series ────────────
            # We show mean/median/std etc. on the full post-imputation frame so
            # the user can see how cleaning shifted the distribution.
            num = pd.to_numeric(non_null, errors="coerce").dropna()
            if len(num) >= 2:
                q1_v = float(num.quantile(0.25))
                q3_v = float(num.quantile(0.75))
                detail["statistics"] = {
                    "mean":   round(float(num.mean()),   4),
                    "median": round(float(num.median()), 4),
                    "std":    round(float(num.std()),    4),
                    "min":    round(float(num.min()),    4),
                    "max":    round(float(num.max()),    4),
                    "q1":     round(q1_v,                4),
                    "q3":     round(q3_v,                4),
                }
            else:
                detail["statistics"] = None

            # ── Outlier detection: ALWAYS use the original raw non-null values ─
            # Re-running IQR outlier detection on the imputed clean series is
            # incorrect: imputation fills gaps with the mean/median which
            # artificially compresses the IQR, causing many legitimate values to
            # fall outside the new (narrower) fences.  The profiler already
            # computed has_outliers / outlier_count on the raw non-null data;
            # we preserve those counts and derive the outlier-values list the
            # same way — from the raw series using the original Q1/Q3 fences.
            # (has_outliers and outlier_count are already set from col_meta in
            # the shared detail dict above; we only need to add outlier_values.)
            if col_meta.has_outliers and col_meta.stats and raw_df is not None:
                try:
                    raw_num = pd.to_numeric(
                        raw_df[col_name].dropna(), errors="coerce"
                    ).dropna()
                    rq1 = float(col_meta.stats.q1)
                    rq3 = float(col_meta.stats.q3)
                    r_iqr = rq3 - rq1
                    r_lower = rq1 - 1.5 * r_iqr
                    r_upper = rq3 + 1.5 * r_iqr
                    raw_outliers = raw_num[
                        (raw_num < r_lower) | (raw_num > r_upper)
                    ]
                    detail["outlier_values"] = [
                        round(float(v), 6)
                        for v in raw_outliers.head(100).tolist()
                    ]
                except Exception:
                    pass  # outlier_values omitted; UI handles absence gracefully
        else:
            detail["statistics"] = {
                "mean":   col_meta.stats.mean,
                "median": col_meta.stats.median,
                "std":    col_meta.stats.std,
                "min":    col_meta.stats.min,
                "max":    col_meta.stats.max,
                "q1":     col_meta.stats.q1,
                "q3":     col_meta.stats.q3,
            }

        # Histogram — always computed from the live series for this df
        try:
            num = pd.to_numeric(non_null, errors="coerce").dropna()
            counts, edges = np.histogram(num, bins=10)
            detail["histogram"] = [
                {
                    "bin_label": (
                        f"{_format_display_number(float(edges[i]))} - "
                        f"{_format_display_number(float(edges[i + 1]))}"
                    ),
                    "count": int(counts[i]),
                }
                for i in range(len(counts))
            ]
            # Outlier values list (raw path only; live path computed above)
            if not compute_live_stats and col_meta.has_outliers and col_meta.stats:
                q1 = float(col_meta.stats.q1)
                q3 = float(col_meta.stats.q3)
                iqr = q3 - q1
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                outliers = num[(num < lower) | (num > upper)]
                detail["outlier_values"] = [
                    round(float(v), 6)
                    for v in outliers.head(100).tolist()
                ]
        except Exception:
            detail["histogram"] = []

    # ── Categorical / Boolean columns (including binary 0/1 flags) ───────────
    else:
        vc = series.value_counts(dropna=True).head(20)
        is_binary = getattr(col_meta, "is_binary", False)

        def _label(k: Any) -> str:
            """Map binary integer keys to human-readable Yes/No labels."""
            if is_binary:
                try:
                    fv = float(k)
                    if fv == 1:
                        return "Yes"
                    if fv == 0:
                        return "No"
                except (ValueError, TypeError):
                    pass
            return str(k)

        # Sort so that "No" (0) always appears before "Yes" (1) for binary cols
        items = list(vc.items())
        if is_binary:
            items.sort(key=lambda kv: (0 if str(kv[0]) in ("0", "0.0") else 1))

        detail["value_counts"] = [
            {
                "value": _label(k),
                "count": int(v),
                "pct":   round(v / max(len(non_null), 1) * 100, 2),
            }
            for k, v in items
        ]

    return detail
