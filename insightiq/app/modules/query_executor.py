# Executes interpreted queries against the DataFrame and returns structured QueryResult objects.

from __future__ import annotations

import re
import time
import uuid
import warnings
from typing import Any, Optional

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from app.models.schemas import (
    AmbiguityItem,
    ChartDataPoint,
    ChartSpec,
    ChartType,
    DatasetProfile,
    ErrorResponse,
    ErrorType,
    QueryIntent,
    QueryObject,
    QueryResult,
    QueryStatus,
    QueryInterpretationFeedback,
    ReliabilityWarning,
    Severity,
    SkippedTask,
    SuggestedFollowUp,
    TaskStatus,
    TaskTrace,
    WarningType,
)
from app.modules.threshold_resolver import resolve_threshold, extract_numeric_threshold

# Constants

MAX_GROUPBY_CATEGORIES = 30
HIGH_MISSING_WARN = 0.30
MIN_TREND_POINTS = 5
TOP_N = 5

# Public entry point

def execute_query(
    query_obj: QueryObject,
    clean_df: pd.DataFrame,
    profile: DatasetProfile,
) -> QueryResult:
    """
    Execute a validated QueryObject against the clean DataFrame.

    Parameters
    ----------
    query_obj : fully parsed QueryObject from query_interpreter
    clean_df  : preprocessed DataFrame from the session store
    profile   : DatasetProfile from Phase 1

    Returns
    -------
    QueryResult — always returned; errors are embedded in .error field
    """
    start = time.time()

    interpretation = QueryInterpretationFeedback(
        confidence=query_obj.confidence,
        intent=query_obj.intent.value,
        mapped_columns=query_obj.mapped_columns,
        explanation=query_obj.interpretation_explanation,
    )

    # Apply filter if present
    working_df = _apply_filter(clean_df, query_obj, profile)
    if working_df is None:
        # Filter column or value not found — return mismatch error
        return _error_result(
            query_obj.query_id,
            profile.session_id,
            ErrorType.mismatch,
            f"The filter value '{query_obj.filters.value}' "
            f"was not found in column '{query_obj.filters.column}'.",
            f"Filter value not present in column.",
            ["Try a different filter value", "Check the column values first"],
            interpretation=interpretation,
        )

    # Dispatch to the right operation
    try:
        result = _dispatch(query_obj, working_df, profile, start)
    except Exception as exc:
        result = _error_result(
            query_obj.query_id,
            profile.session_id,
            ErrorType.parse_failure,
            "Something went wrong while computing your answer. "
            "Please try rephrasing your question.",
            str(exc),
            ["Try a simpler question", "Ensure the columns exist"],
            interpretation=interpretation,
        )

    # Attach interpretation feedback to every result
    result.interpretation = interpretation
    return result

# Dispatcher

def _dispatch(
    q: QueryObject,
    df: pd.DataFrame,
    profile: DatasetProfile,
    start: float,
) -> QueryResult:
    intent = q.intent

    if intent == QueryIntent.missing_data:
        return _exec_missing(q, df, profile, start)
    elif intent == QueryIntent.distribution:
        return _exec_distribution(q, df, profile, start)
    elif intent == QueryIntent.ranking:
        return _exec_ranking(q, df, profile, start)
    elif intent == QueryIntent.comparison:
        return _exec_comparison(q, df, profile, start)
    elif intent == QueryIntent.aggregation:
        return _exec_aggregation(q, df, profile, start)
    elif intent == QueryIntent.trend:
        return _exec_trend(q, df, profile, start)
    elif intent == QueryIntent.correlation:
        return _exec_correlation(q, df, profile, start)
    elif intent == QueryIntent.feature_importance:
        return _exec_feature_importance(q, df, profile, start)
    # ---- Phase 3 advanced intents ----
    elif intent == QueryIntent.targeted_correlation:
        return _exec_targeted_correlation(q, df, profile, start)
    elif intent == QueryIntent.compound_filter:
        return _exec_compound_filter(q, df, profile, start)
    elif intent == QueryIntent.derived_metric:
        return _exec_derived_metric(q, df, profile, start)
    elif intent == QueryIntent.period_growth:
        return _exec_period_growth(q, df, profile, start)
    elif intent == QueryIntent.anomaly_query:
        return _exec_anomaly_query(q, df, profile, start)
    elif intent == QueryIntent.multi_criteria_rank:
        return _exec_multi_criteria_rank(q, df, profile, start)
    elif intent == QueryIntent.business_decision:
        return _exec_business_decision(q, df, profile, start)
    elif intent == QueryIntent.scenario_analysis:
        return _exec_scenario_analysis(q, df, profile, start)
    elif intent == QueryIntent.open_ended_insight:
        return _exec_open_ended_insight(q, df, profile, start)
    elif intent == QueryIntent.segment_comparison:
        return _exec_segment_comparison(q, df, profile, start)
    elif intent == QueryIntent.threshold_analysis:
        return _exec_threshold_analysis(q, df, profile, start)
    elif intent == QueryIntent.seasonal_pattern:
        return _exec_seasonal_pattern(q, df, profile, start)
    elif intent == QueryIntent.combination_ranking:
        return _exec_combination_ranking(q, df, profile, start)
    elif intent == QueryIntent.efficiency_query:
        return _exec_efficiency_query(q, df, profile, start)
    else:
        return _error_result(
            q.query_id, profile.session_id,
            ErrorType.unsupported,
            "I don't know how to answer that type of question yet.",
            f"Unsupported intent: {intent}",
            ["Try asking about trends, rankings, comparisons, or missing data"],
        )

# Executors

def _exec_missing(
    q: QueryObject,
    df: pd.DataFrame,
    profile: DatasetProfile,
    start: float,
) -> QueryResult:
    """Count and rank missing values per column."""
    missing = df.isnull().sum()
    missing = missing[missing > 0].sort_values(ascending=False)

    if missing.empty:
        result_value = {"message": "No missing values found.", "columns": []}
        plain = "Great news — your dataset has no missing values."
        takeaway = "Your data is complete with no gaps."
        chart = None
    else:
        pct = (missing / len(df) * 100).round(2)
        records = [
            {
                "column": col,
                "missing_count": int(cnt),
                "missing_pct": float(pct[col]),
            }
            for col, cnt in missing.items()
        ]
        worst = records[0]
        result_value = records
        plain = (
            f"{len(records)} column(s) have missing values. "
            f"'{worst['column']}' is the most affected, with "
            f"{worst['missing_count']} missing entries "
            f"({worst['missing_pct']:.1f}% of rows)."
        )
        takeaway = (
            f"'{worst['column']}' needs the most attention — "
            f"{worst['missing_pct']:.1f}% of its values are missing."
        )
        chart = ChartSpec(
            chart_type=ChartType.bar,
            title="Missing Values by Column (%)",
            x_field="column",
            y_field="missing_pct",
            x_axis_label="Column",
            y_axis_label="Missing (%)",
            data=[
                ChartDataPoint(label=r["column"], value=round(r["missing_pct"], 2))
                for r in records
            ],
            color_scheme="sequential",
        )

    trace = _make_trace(
        q, "missing_value_count", list(df.columns), start,
        "Counted null values per column and ranked by frequency.",
    )
    follow_ups = _build_follow_ups([], "missing_data", profile)

    return QueryResult(
        query_id=q.query_id,
        session_id=profile.session_id,
        status=QueryStatus.success,
        result_value=result_value,
        plain_summary=plain,
        key_takeaway=takeaway,
        chart=chart,
        suggested_follow_ups=follow_ups,
        trace=trace,
    )

def _exec_distribution(
    q: QueryObject,
    df: pd.DataFrame,
    profile: DatasetProfile,
    start: float,
) -> QueryResult:
    """Descriptive statistics for mapped numeric columns."""
    num_cols = _get_numeric_cols(q.mapped_columns, df, profile)
    if not num_cols:
        return _error_result(
            q.query_id, profile.session_id,
            ErrorType.mismatch,
            "I couldn't find a numeric column to compute statistics for. "
            f"Your numeric columns are: {', '.join(profile.numeric_columns[:6])}.",
            "No numeric columns in mapped_columns",
            [f"Try asking about '{c}'" for c in profile.numeric_columns[:3]],
        )

    col = num_cols[0]
    series = pd.to_numeric(df[col], errors="coerce").dropna()

    stats = {
        "column": col,
        "count": int(len(series)),
        "mean": round(float(series.mean()), 4),
        "median": round(float(series.median()), 4),
        "std": round(float(series.std()), 4),
        "min": round(float(series.min()), 4),
        "max": round(float(series.max()), 4),
        "q1": round(float(series.quantile(0.25)), 4),
        "q3": round(float(series.quantile(0.75)), 4),
    }

    plain = (
        f"'{col}' ranges from {_fmt(stats['min'])} to {_fmt(stats['max'])}, "
        f"with an average of {_fmt(stats['mean'])} "
        f"and median of {_fmt(stats['median'])}."
    )
    takeaway = f"The typical value of '{col}' is around {_fmt(stats['median'])}."

    chart = ChartSpec(
        chart_type=ChartType.histogram,
        title=f"Distribution of {col}",
        x_field=col,
        y_field="frequency",
        x_axis_label=col,
        y_axis_label="Count",
        data=_histogram_data(series),
        color_scheme="sequential",
    )

    col_meta = next((c for c in profile.columns if c.name == col), None)
    reliability = _check_reliability(col, col_meta.null_rate if col_meta else 0, len(series))
    trace = _make_trace(q, "descriptive_stats", [col], start,
                        f"Computed summary statistics for '{col}'.")
    follow_ups = _build_follow_ups([col], "distribution", profile)

    return QueryResult(
        query_id=q.query_id,
        session_id=profile.session_id,
        status=QueryStatus.success,
        result_value=stats,
        plain_summary=plain,
        key_takeaway=takeaway,
        chart=chart,
        suggested_follow_ups=follow_ups,
        reliability_warning=reliability,
        trace=trace,
    )

def _exec_ranking(
    q: QueryObject,
    df: pd.DataFrame,
    profile: DatasetProfile,
    start: float,
) -> QueryResult:
    """Top-N or bottom-N ranking: categorical grouped by numeric."""
    cat_cols = _get_categorical_cols(q.mapped_columns, df, profile)
    num_cols = _get_numeric_cols(q.mapped_columns, df, profile)

    # Fallback: use first available pair
    if not cat_cols:
        cat_cols = [c for c in profile.categorical_columns if c in df.columns]
    if not num_cols:
        num_cols = [c for c in profile.numeric_columns if c in df.columns]

    if not cat_cols or not num_cols:
        return _error_result(
            q.query_id, profile.session_id,
            ErrorType.mismatch,
            "Ranking needs both a category column and a numeric column. "
            f"Try: 'Top products by revenue'.",
            "Missing cat or num column for ranking",
            [f"Try 'top {profile.categorical_columns[0]} by "
             f"{profile.numeric_columns[0]}'"
             if profile.categorical_columns and profile.numeric_columns
             else "Ensure your dataset has category and numeric columns"],
        )

    cat_col = cat_cols[0]
    # Prefer the most query-relevant numeric column
    num_col = _pick_best_numeric_col(num_cols, q.raw_query)

    # Detect bottom vs top from query
    raw_lower = q.raw_query.lower()
    is_bottom = bool(re.search(r"\b(bottom|worst|lowest|least|minimum|last)\b", raw_lower))

    # Detect variability/inconsistency ranking → use std deviation
    use_std = bool(re.search(
        r"\b(variab|inconsistent|volatile|volatility|std|deviation|spread|irregular)\b",
        raw_lower,
    ))
    # Detect count-based ranking ("most used", "most common", "most frequent")
    use_count = bool(re.search(
        r"\b(most\s+used|most\s+common|most\s+frequent|least\s+used|least\s+common|least\s+frequent)\b",
        raw_lower,
    ))
    # Detect whether the query asks for an average/mean rather than a total
    use_mean = bool(re.search(r"\b(average|mean|avg|per[- ]order|per[- ]transaction|per[- ]unit)\b", raw_lower))

    if use_std:
        agg_fn = "std"
        agg_label = "std dev of"
    elif use_count:
        agg_fn = "count"
        agg_label = "count of"
        # For count-based ranking on categorical columns, count rows per group
        num_col = num_col  # still need num_col for fallback, but count won't use it
    elif use_mean:
        agg_fn = "mean"
        agg_label = "average"
    else:
        agg_fn = "sum"
        agg_label = "total"

    if use_count:
        grouped = (
            df.groupby(cat_col)[cat_col]
            .count()
            .sort_values(ascending=is_bottom)
            .head(TOP_N)
            .reset_index(name=num_col)
        )
        grouped.columns = [cat_col, num_col]
    else:
        grouped = (
            df.groupby(cat_col)[num_col]
            .agg(agg_fn)
            .sort_values(ascending=is_bottom)
            .head(TOP_N)
            .reset_index()
        )
        grouped.columns = [cat_col, num_col]

    top_name = str(grouped.iloc[0][cat_col])
    top_val = float(grouped.iloc[0][num_col])
    rank_word = "bottom" if is_bottom else "top"

    plain = (
        f"The {rank_word} {len(grouped)} {cat_col} values by {agg_label} {num_col}: "
        + ", ".join(
            f"'{row[cat_col]}' ({_fmt(float(row[num_col]))})"
            for _, row in grouped.iterrows()
        ) + "."
    )
    takeaway = (
        f"'{top_name}' {'has the lowest' if is_bottom else 'leads with'} "
        f"{agg_label} {num_col} at {_fmt(top_val)}."
    )

    chart = ChartSpec(
        chart_type=ChartType.bar,
        title=f"{rank_word.title()} {TOP_N} {cat_col} by {num_col}",
        x_field=cat_col,
        y_field=num_col,
        x_axis_label=cat_col,
        y_axis_label=f"{agg_label.title()} {num_col}",
        data=[
            ChartDataPoint(label=str(r[cat_col]), value=round(float(r[num_col]), 4))
            for _, r in grouped.iterrows()
        ],
        color_scheme="categorical",
    )

    col_meta = next((c for c in profile.columns if c.name == num_col), None)
    reliability = _check_reliability(num_col, col_meta.null_rate if col_meta else 0, len(df))
    trace = _make_trace(q, "groupby_sum_rank", [cat_col, num_col], start,
                        f"Grouped '{num_col}' by '{cat_col}', summed, and ranked.")
    follow_ups = _build_follow_ups([cat_col, num_col], "ranking", profile)

    return QueryResult(
        query_id=q.query_id,
        session_id=profile.session_id,
        status=QueryStatus.success,
        result_value=grouped.to_dict(orient="records"),
        plain_summary=plain,
        key_takeaway=takeaway,
        chart=chart,
        suggested_follow_ups=follow_ups,
        reliability_warning=reliability,
        trace=trace,
    )

def _exec_comparison(
    q: QueryObject,
    df: pd.DataFrame,
    profile: DatasetProfile,
    start: float,
) -> QueryResult:
    """Compare a numeric column across categories."""
    cat_cols = _get_categorical_cols(q.mapped_columns, df, profile)
    num_cols = _get_numeric_cols(q.mapped_columns, df, profile)

    if not cat_cols:
        cat_cols = [c for c in profile.categorical_columns if c in df.columns]
    if not num_cols:
        num_cols = [c for c in profile.numeric_columns if c in df.columns]

    if not cat_cols or not num_cols:
        return _error_result(
            q.query_id, profile.session_id,
            ErrorType.mismatch,
            "Comparison needs a category column and a numeric column.",
            "No cat or num cols available",
            ["Try: 'Compare revenue by region'"],
        )

    num_col = _pick_best_numeric_col(num_cols, q.raw_query)
    cmp_raw_lower = q.raw_query.lower()

    # ── Quarter-vs-quarter comparison ("Q4 vs Q1", "Q4 compared to Q1") ──
    qtr_mentions = re.findall(r"\bQ([1-4])\b", q.raw_query, re.IGNORECASE)
    dt_cols_cmp = _get_datetime_cols(q.mapped_columns, df, profile)
    if not dt_cols_cmp:
        dt_cols_cmp = [c for c in profile.datetime_columns if c in df.columns]
    if len(qtr_mentions) >= 2 and dt_cols_cmp:
        dt_col_cmp = dt_cols_cmp[0]
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                dt_s_cmp = pd.to_datetime(df[dt_col_cmp], errors="coerce")
        except Exception:
            dt_s_cmp = None
        if dt_s_cmp is not None:
            num_s_cmp = pd.to_numeric(df[num_col], errors="coerce")
            temp_cmp = pd.DataFrame({
                "__q": dt_s_cmp.dt.quarter,
                num_col: num_s_cmp,
            }).dropna()
            q_totals = temp_cmp.groupby("__q")[num_col].sum()
            q_labels = {1: "Q1", 2: "Q2", 3: "Q3", 4: "Q4"}
            results_q = {}
            plain_parts_q = []
            for qn_str in qtr_mentions[:4]:
                qn = int(qn_str)
                val_q = float(q_totals.get(qn, 0))
                results_q[f"Q{qn}"] = round(val_q, 4)
                plain_parts_q.append(f"Q{qn}: {_fmt(val_q)}")
            qa, qb = int(qtr_mentions[0]), int(qtr_mentions[1])
            val_a = float(q_totals.get(qa, 0))
            val_b = float(q_totals.get(qb, 0))
            pct_diff_q = ((val_a - val_b) / max(abs(val_b), 1e-9)) * 100
            plain_q = (
                f"Comparing {num_col} by quarter: "
                + ", ".join(plain_parts_q) + f". "
                f"Q{qa} is {abs(pct_diff_q):.1f}% "
                f"{'higher' if pct_diff_q > 0 else 'lower'} than Q{qb}."
            )
            takeaway_q = (
                f"Q{qa} {num_col} ({_fmt(val_a)}) vs Q{qb} ({_fmt(val_b)}): "
                f"{abs(pct_diff_q):.1f}% difference."
            )
            trace_q = _make_trace(q, "quarter_comparison", [dt_col_cmp, num_col], start,
                                  f"Compared quarterly {num_col}.")
            return QueryResult(
                query_id=q.query_id, session_id=profile.session_id,
                status=QueryStatus.success,
                result_value=results_q,
                plain_summary=plain_q, key_takeaway=takeaway_q, trace=trace_q,
            )

    # Multi-dimensional groupby: 2 categorical columns mapped
    if len(cat_cols) >= 2:
        cat_a, cat_b = cat_cols[0], cat_cols[1]
        combined_cardinality = df[cat_a].nunique() * df[cat_b].nunique()
        if combined_cardinality <= MAX_GROUPBY_CATEGORIES * 4:
            grouped2 = (
                df.groupby([cat_a, cat_b])[num_col]
                .sum()
                .reset_index()
                .rename(columns={num_col: "total"})
                .sort_values("total", ascending=False)
            )
            grouped2["label"] = grouped2[cat_a].astype(str) + " / " + grouped2[cat_b].astype(str)
            top2 = grouped2.iloc[0]
            top_label2 = str(top2["label"])
            top_total2 = float(top2["total"])
            overall_avg2 = float(grouped2["total"].mean())
            pct2 = ((top_total2 - overall_avg2) / max(abs(overall_avg2), 1e-9)) * 100

            plain2 = (
                f"Comparing {num_col} by {cat_a} and {cat_b}: "
                f"'{top_label2}' leads with {_fmt(top_total2)}, "
                f"{abs(pct2):.1f}% {'above' if pct2 >= 0 else 'below'} the group average."
            )
            takeaway2 = f"The combination '{top_label2}' contributes the most to total {num_col}."

            chart2 = ChartSpec(
                chart_type=ChartType.bar,
                title=f"{num_col} by {cat_a} and {cat_b}",
                x_field="label",
                y_field=num_col,
                x_axis_label=f"{cat_a} / {cat_b}",
                y_axis_label=f"Total {num_col}",
                data=[
                    ChartDataPoint(label=str(r["label"]), value=round(float(r["total"]), 4))
                    for _, r in grouped2.iterrows()
                ],
                color_scheme="categorical",
            )

            col_meta2 = next((c for c in profile.columns if c.name == num_col), None)
            reliability2 = _check_reliability(num_col, col_meta2.null_rate if col_meta2 else 0, len(df))
            trace2 = _make_trace(q, "groupby_aggregation", [cat_a, cat_b, num_col], start,
                                 f"Grouped '{num_col}' by '{cat_a}' and '{cat_b}'.")
            follow_ups2 = _build_follow_ups([cat_a, cat_b, num_col], "comparison", profile)

            return QueryResult(
                query_id=q.query_id,
                session_id=profile.session_id,
                status=QueryStatus.success,
                result_value=grouped2.drop(columns="label").to_dict(orient="records"),
                plain_summary=plain2,
                key_takeaway=takeaway2,
                chart=chart2,
                suggested_follow_ups=follow_ups2,
                reliability_warning=reliability2,
                trace=trace2,
            )

    cat_col = cat_cols[0]

    if df[cat_col].nunique() > MAX_GROUPBY_CATEGORIES:
        return _error_result(
            q.query_id, profile.session_id,
            ErrorType.unsupported,
            f"'{cat_col}' has too many unique values ({df[cat_col].nunique()}) "
            "to compare meaningfully.",
            f"Cardinality {df[cat_col].nunique()} exceeds limit {MAX_GROUPBY_CATEGORIES}",
            [f"Try a column with fewer categories"],
        )

    grouped = (
        df.groupby(cat_col)[num_col]
        .agg(["sum", "mean", "count"])
        .reset_index()
    )
    grouped.columns = [cat_col, "total", "average", "count"]

    # Use the metric that matches the query intent
    cmp_raw = q.raw_query.lower()
    use_mean_cmp = bool(re.search(r"\b(average|mean|avg|per[- ]order|per[- ]transaction|per[- ]unit)\b", cmp_raw))
    sort_col = "average" if use_mean_cmp else "total"
    metric_label = "average" if use_mean_cmp else "total"

    grouped = grouped.sort_values(sort_col, ascending=False)

    top = grouped.iloc[0]
    top_label = str(top[cat_col])
    top_val = float(top[sort_col])
    overall_ref = float(grouped[sort_col].mean())
    pct = ((top_val - overall_ref) / max(abs(overall_ref), 1e-9)) * 100

    plain = (
        f"Comparing {num_col} by {cat_col}: "
        f"'{top_label}' leads with a {metric_label} of {_fmt(top_val)}, "
        f"which is {abs(pct):.1f}% "
        f"{'above' if pct >= 0 else 'below'} the group average."
    )
    takeaway = f"'{top_label}' has the highest {metric_label} {num_col} ({_fmt(top_val)})."

    chart = ChartSpec(
        chart_type=ChartType.bar,
        title=f"{num_col} by {cat_col}",
        x_field=cat_col,
        y_field=num_col,
        x_axis_label=cat_col,
        y_axis_label=f"Total {num_col}",
        data=[
            ChartDataPoint(label=str(r[cat_col]), value=round(float(r["total"]), 4))
            for _, r in grouped.iterrows()
        ],
        color_scheme="categorical",
    )

    col_meta = next((c for c in profile.columns if c.name == num_col), None)
    reliability = _check_reliability(num_col, col_meta.null_rate if col_meta else 0, len(df))
    trace = _make_trace(q, "groupby_aggregation", [cat_col, num_col], start,
                        f"Grouped '{num_col}' by '{cat_col}' and aggregated.")
    follow_ups = _build_follow_ups([cat_col, num_col], "comparison", profile)

    return QueryResult(
        query_id=q.query_id,
        session_id=profile.session_id,
        status=QueryStatus.success,
        result_value=grouped.to_dict(orient="records"),
        plain_summary=plain,
        key_takeaway=takeaway,
        chart=chart,
        suggested_follow_ups=follow_ups,
        reliability_warning=reliability,
        trace=trace,
    )

def _exec_aggregation(
    q: QueryObject,
    df: pd.DataFrame,
    profile: DatasetProfile,
    start: float,
) -> QueryResult:
    """Simple total, average, or count for a numeric column.

    Extended to handle:
    - Row count queries ("how many orders/records in the dataset")
    - Quarterly groupby ("total revenue for each quarter")
    - Proportion/fraction queries ("what fraction of revenue comes from X")
    - Cross-column comparison ("how many orders where cost > revenue")
    - Above/below average group filter ("which stores are above average revenue")
    """
    raw = q.raw_query.lower()
    dt_cols = _get_datetime_cols(q.mapped_columns, df, profile)
    if not dt_cols:
        dt_cols = [c for c in profile.datetime_columns if c in df.columns]

    num_cols = _get_numeric_cols(q.mapped_columns, df, profile)
    if not num_cols:
        num_cols = [c for c in profile.numeric_columns if c in df.columns]
    cat_cols = _get_categorical_cols(q.mapped_columns, df, profile)
    if not cat_cols:
        cat_cols = [c for c in profile.categorical_columns if c in df.columns]

    # ── Row-count queries ("how many total orders/records/rows in the dataset") ──
    is_count_query = bool(re.search(r"\b(how many|count|number of)\b", raw))
    is_row_entity = bool(re.search(r"\b(order|record|row|entry|entries|item|transaction)\b", raw))
    if is_count_query and is_row_entity and not num_cols:
        total_rows = len(df)
        plain = f"There are {total_rows:,} total rows in the dataset."
        takeaway = f"Dataset contains {total_rows:,} rows."
        trace = _make_trace(q, "row_count", [], start, "Counted total rows in dataset.")
        return QueryResult(
            query_id=q.query_id, session_id=profile.session_id,
            status=QueryStatus.success,
            result_value={"count": total_rows},
            plain_summary=plain, key_takeaway=takeaway, trace=trace,
        )

    # Even when a numeric col is mapped, "how many orders" means row count
    if is_count_query and is_row_entity:
        total_rows = len(df)
        plain = f"There are {total_rows:,} total rows (orders) in the dataset."
        takeaway = f"Dataset contains {total_rows:,} rows."
        trace = _make_trace(q, "row_count", [], start, "Counted total rows in dataset.")
        return QueryResult(
            query_id=q.query_id, session_id=profile.session_id,
            status=QueryStatus.success,
            result_value={"count": total_rows},
            plain_summary=plain, key_takeaway=takeaway, trace=trace,
        )

    # ── Cross-column comparison count ("how many orders where cost > revenue") ──
    cross_col_match = re.search(
        r"\b(cost|expense|spend)\b.{0,30}\b(exceed|higher than|greater than|more than)\b.{0,20}\b(revenue|income|sales)\b",
        raw, re.IGNORECASE,
    )
    if cross_col_match:
        cost_col = next((c for c in profile.numeric_columns if "cost" in c.lower() and c in df.columns), None)
        rev_col = next((c for c in profile.numeric_columns if "revenue" in c.lower() and c in df.columns), None)
        if cost_col and rev_col:
            cost_s = pd.to_numeric(df[cost_col], errors="coerce")
            rev_s = pd.to_numeric(df[rev_col], errors="coerce")
            loss_mask = cost_s > rev_s
            n_loss = int(loss_mask.sum())
            pct = round(n_loss / max(len(df), 1) * 100, 2)
            plain = (
                f"{n_loss} orders ({pct}% of data) have '{cost_col}' exceeding '{rev_col}' "
                f"(loss-making orders)."
            )
            takeaway = f"{n_loss} loss-making orders found where {cost_col} > {rev_col}."
            trace = _make_trace(q, "cross_column_compare", [cost_col, rev_col], start,
                                f"Counted rows where {cost_col} > {rev_col}.")
            return QueryResult(
                query_id=q.query_id, session_id=profile.session_id,
                status=QueryStatus.success,
                result_value={"n_loss": n_loss, "pct": pct, "cost_col": cost_col, "rev_col": rev_col},
                plain_summary=plain, key_takeaway=takeaway, trace=trace,
            )

    # ── Proportion/fraction/contribution queries ──
    is_proportion = bool(re.search(
        r"\b(fraction|proportion|contribution|share|percentage of total|relative to total|relative to)\b",
        raw, re.IGNORECASE,
    ))
    if is_proportion and num_cols:
        num_col = _pick_best_numeric_col(num_cols, q.raw_query)
        num_s = pd.to_numeric(df[num_col], errors="coerce")
        total_val = float(num_s.sum())

        # Build a combined subset mask from ALL categorical columns (not just mapped)
        # by finding column values that appear as words in the query text.
        combined_mask = pd.Series([True] * len(df), index=df.index)
        conditions_applied: list[str] = []
        for cc in [c for c in profile.categorical_columns if c in df.columns]:
            col_vals = df[cc].dropna().unique()
            for val in col_vals:
                if str(val).lower() in raw:
                    group_mask = df[cc].astype(str).str.lower() == str(val).lower()
                    combined_mask = combined_mask & group_mask
                    conditions_applied.append(f"{cc}='{val}'")
                    break  # only one value per column

        subset_val = float(num_s[combined_mask].sum())
        pct_val = round(subset_val / max(abs(total_val), 1e-9) * 100, 2)
        group_label = " AND ".join(conditions_applied) if conditions_applied else "subset"

        plain = (
            f"The {num_col} for {group_label} is {_fmt(subset_val)}, "
            f"which is {pct_val}% of the total {num_col} ({_fmt(total_val)})."
        )
        takeaway = f"{group_label} contributes {pct_val}% of total {num_col}."
        trace = _make_trace(q, "proportion", [num_col], start,
                            f"Computed {num_col} proportion for {group_label}.")
        return QueryResult(
            query_id=q.query_id, session_id=profile.session_id,
            status=QueryStatus.success,
            result_value={"conditions": conditions_applied, "subset_total": round(subset_val, 4),
                          "overall_total": round(total_val, 4), "pct_of_total": pct_val},
            plain_summary=plain, key_takeaway=takeaway, trace=trace,
        )

    # ── Above/below average group filter ──
    above_avg_match = re.search(r"\b(above|over)\b.{0,20}\b(average|avg|mean)\b", raw)
    below_avg_match = re.search(r"\b(below|under)\b.{0,20}\b(average|avg|mean)\b", raw)
    if (above_avg_match or below_avg_match) and cat_cols and num_cols:
        cat_col = cat_cols[0]
        num_col = _pick_best_numeric_col(num_cols, q.raw_query)
        use_mean = bool(re.search(r"\bper\s+(order|transaction|unit)\b", raw))
        grouped = df.groupby(cat_col)[num_col].mean() if use_mean else df.groupby(cat_col)[num_col].sum()
        overall_avg = float(grouped.mean())
        if above_avg_match:
            above_groups = grouped[grouped > overall_avg].sort_values(ascending=False)
            group_list = above_groups.index.tolist()
            plain = (
                f"{len(group_list)} {cat_col}(s) generate above-average {num_col} "
                f"(avg: {_fmt(overall_avg)}): "
                + ", ".join(f"'{g}' ({_fmt(float(v))})" for g, v in above_groups.items()) + "."
            )
            takeaway = f"{len(group_list)} {cat_col}(s) are above the average {num_col} of {_fmt(overall_avg)}."
        else:
            below_groups = grouped[grouped < overall_avg].sort_values(ascending=True)
            group_list = below_groups.index.tolist()
            plain = (
                f"{len(group_list)} {cat_col}(s) generate below-average {num_col} "
                f"(avg: {_fmt(overall_avg)}): "
                + ", ".join(f"'{g}' ({_fmt(float(v))})" for g, v in below_groups.items()) + "."
            )
            takeaway = f"{len(group_list)} {cat_col}(s) are below the average {num_col} of {_fmt(overall_avg)}."
        all_groups = grouped.sort_values(ascending=False).reset_index()
        all_groups.columns = [cat_col, f"total_{num_col}"]
        trace = _make_trace(q, "above_below_average", [cat_col, num_col], start,
                            f"Compared {cat_col} groups against overall average {num_col}.")
        return QueryResult(
            query_id=q.query_id, session_id=profile.session_id,
            status=QueryStatus.success,
            result_value={"cat_col": cat_col, "num_col": num_col,
                          "overall_avg": round(overall_avg, 4),
                          "groups": all_groups.to_dict(orient="records")},
            plain_summary=plain, key_takeaway=takeaway, trace=trace,
        )

    # ── Quarterly breakdown ("total revenue for each quarter") ──
    if re.search(r"\b(quarter|Q1|Q2|Q3|Q4)\b", raw, re.IGNORECASE) and dt_cols and num_cols:
        dt_col = dt_cols[0]
        num_col = _pick_best_numeric_col(num_cols, q.raw_query)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                dt_s = pd.to_datetime(df[dt_col], errors="coerce")
        except Exception:
            dt_s = None
        if dt_s is not None:
            num_s = pd.to_numeric(df[num_col], errors="coerce")
            mask = dt_s.notna() & num_s.notna()
            temp = pd.DataFrame({"__q": dt_s[mask].dt.quarter, num_col: num_s[mask]})
            qtr_totals = temp.groupby("__q")[num_col].sum().reset_index()
            qtr_totals.columns = ["quarter", num_col]
            qtr_totals["quarter_label"] = qtr_totals["quarter"].apply(lambda x: f"Q{int(x)}")
            qtr_totals = qtr_totals.sort_values("quarter")
            peak_row = qtr_totals.loc[qtr_totals[num_col].idxmax()]
            peak_q = str(peak_row["quarter_label"])
            peak_v = float(peak_row[num_col])
            records = [{"quarter": r["quarter_label"], num_col: round(float(r[num_col]), 4)}
                       for _, r in qtr_totals.iterrows()]
            plain = (
                f"Total {num_col} by quarter: "
                + ", ".join(f"{r['quarter']}: {_fmt(r[num_col])}" for r in records)
                + f". Peak quarter: {peak_q} ({_fmt(peak_v)})."
            )
            takeaway = f"Highest {num_col} in {peak_q}: {_fmt(peak_v)}."
            chart = ChartSpec(
                chart_type=ChartType.bar,
                title=f"{num_col} by Quarter",
                x_field="quarter", y_field=num_col,
                x_axis_label="Quarter", y_axis_label=f"Total {num_col}",
                data=[ChartDataPoint(label=r["quarter"], value=r[num_col]) for r in records],
                color_scheme="categorical",
            )
            trace = _make_trace(q, "quarterly_aggregate", [dt_col, num_col], start,
                                f"Aggregated '{num_col}' by quarter.")
            return QueryResult(
                query_id=q.query_id, session_id=profile.session_id,
                status=QueryStatus.success,
                result_value={"quarters": records},
                plain_summary=plain, key_takeaway=takeaway, chart=chart, trace=trace,
            )

    if not num_cols:
        return _error_result(
            q.query_id, profile.session_id,
            ErrorType.mismatch,
            "I need a numeric column to compute totals or averages.",
            "No numeric columns available",
            [f"Try asking about '{c}'" for c in profile.numeric_columns[:3]],
        )

    # Pick the most query-relevant numeric column when multiple are mapped
    col = _pick_best_numeric_col(num_cols, q.raw_query)
    series = pd.to_numeric(df[col], errors="coerce").dropna()

    if re.search(r"\b(average|mean|avg)\b", raw):
        agg_val = float(series.mean())
        agg_label = "average"
    elif re.search(r"\b(count|how many)\b", raw):
        # Count non-null values in the selected column
        agg_val = float(len(series))
        agg_label = "count"
    elif re.search(r"\b(max|maximum|highest|largest)\b", raw):
        agg_val = float(series.max())
        agg_label = "maximum"
    elif re.search(r"\b(min|minimum|lowest|smallest)\b", raw):
        agg_val = float(series.min())
        agg_label = "minimum"
    else:
        agg_val = float(series.sum())
        agg_label = "total"

    plain = f"The {agg_label} of '{col}' is {_fmt(agg_val)}."
    takeaway = f"'{col}' {agg_label}: {_fmt(agg_val)}."

    col_meta = next((c for c in profile.columns if c.name == col), None)
    reliability = _check_reliability(col, col_meta.null_rate if col_meta else 0, len(series))
    trace = _make_trace(q, f"aggregate_{agg_label}", [col], start,
                        f"Computed {agg_label} of '{col}'.")
    follow_ups = _build_follow_ups([col], "aggregation", profile)

    return QueryResult(
        query_id=q.query_id,
        session_id=profile.session_id,
        status=QueryStatus.success,
        result_value={"column": col, "operation": agg_label, "value": round(agg_val, 4)},
        plain_summary=plain,
        key_takeaway=takeaway,
        suggested_follow_ups=follow_ups,
        reliability_warning=reliability,
        trace=trace,
    )

def _exec_trend(
    q: QueryObject,
    df: pd.DataFrame,
    profile: DatasetProfile,
    start: float,
) -> QueryResult:
    """Time-series aggregation and trend direction."""
    dt_cols = _get_datetime_cols(q.mapped_columns, df, profile)
    num_cols = _get_numeric_cols(q.mapped_columns, df, profile)

    if not dt_cols:
        dt_cols = [c for c in profile.datetime_columns if c in df.columns]
    if not num_cols:
        num_cols = [c for c in profile.numeric_columns if c in df.columns]

    if not dt_cols:
        return _error_result(
            q.query_id, profile.session_id,
            ErrorType.mismatch,
            "Trend analysis needs a date or time column. "
            "I couldn't find one in your dataset.",
            "No datetime column available",
            ["Ensure your dataset has a date column"],
        )
    if not num_cols:
        return _error_result(
            q.query_id, profile.session_id,
            ErrorType.mismatch,
            "Trend analysis needs a numeric column to track over time.",
            "No numeric column available",
            [f"Try: 'Show {c} over time'" for c in profile.numeric_columns[:2]],
        )

    dt_col = dt_cols[0]
    num_col = num_cols[0]

    # Parse datetime
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            dt_series = pd.to_datetime(df[dt_col], errors="coerce")
    except Exception:
        return _error_result(
            q.query_id, profile.session_id,
            ErrorType.parse_failure,
            f"Could not parse '{dt_col}' as dates.",
            f"datetime parse failed for column {dt_col}",
            ["Check that the date column contains valid dates"],
        )

    num_series = pd.to_numeric(df[num_col], errors="coerce")
    mask = dt_series.notna() & num_series.notna()

    temp = pd.DataFrame({dt_col: dt_series[mask], num_col: num_series[mask]})
    temp["__period"] = temp[dt_col].dt.to_period("M")
    monthly = (
        temp.groupby("__period")[num_col]
        .sum()
        .reset_index()
    )
    monthly["period_str"] = monthly["__period"].astype(str)
    monthly = monthly.sort_values("__period")

    if len(monthly) < MIN_TREND_POINTS:
        return _error_result(
            q.query_id, profile.session_id,
            ErrorType.data_quality,
            f"Not enough time periods to show a trend "
            f"(found {len(monthly)}, need at least {MIN_TREND_POINTS}).",
            f"Only {len(monthly)} time periods",
            ["Upload more data with more date entries"],
        )

    x = np.arange(len(monthly))
    y = monthly[num_col].values.astype(float)
    slope, _, r_val, _, _ = scipy_stats.linregress(x, y)

    direction = "upward" if slope > 0 else "downward"
    peak_idx = int(np.argmax(y))
    peak_period = str(monthly["period_str"].iloc[peak_idx])
    peak_val = float(y[peak_idx])
    avg_val = float(y.mean())
    pct = ((peak_val - avg_val) / max(abs(avg_val), 1e-9)) * 100

    plain = (
        f"'{num_col}' shows a {direction} trend over time "
        f"(slope: {slope:+.2f} per period, R²={r_val**2:.2f}). "
        f"The peak was in {peak_period} at {_fmt(peak_val)}, "
        f"{abs(pct):.1f}% {'above' if pct >= 0 else 'below'} the period average."
    )
    takeaway = (
        f"'{num_col}' is trending {direction}. "
        f"Highest point: {peak_period} ({_fmt(peak_val)})."
    )

    chart = ChartSpec(
        chart_type=ChartType.line,
        title=f"{num_col} Over Time",
        x_field=dt_col,
        y_field=num_col,
        x_axis_label="Period",
        y_axis_label=num_col,
        data=[
            ChartDataPoint(
                label=str(row["period_str"]),
                value=round(float(row[num_col]), 4),
            )
            for _, row in monthly.iterrows()
        ],
        color_scheme="sequential",
    )

    col_meta = next((c for c in profile.columns if c.name == num_col), None)
    reliability = _check_reliability(num_col, col_meta.null_rate if col_meta else 0, len(monthly))
    trace = _make_trace(q, "time_series_aggregate", [dt_col, num_col], start,
                        f"Aggregated '{num_col}' by month across '{dt_col}'.")
    follow_ups = _build_follow_ups([dt_col, num_col], "trend", profile)

    return QueryResult(
        query_id=q.query_id,
        session_id=profile.session_id,
        status=QueryStatus.success,
        result_value={
            "period_data": monthly[["period_str", num_col]].to_dict(orient="records"),
            "slope": round(float(slope), 6),
            "r_squared": round(float(r_val**2), 4),
            "direction": direction,
            "peak_period": peak_period,
            "peak_value": round(peak_val, 4),
        },
        plain_summary=plain,
        key_takeaway=takeaway,
        chart=chart,
        suggested_follow_ups=follow_ups,
        reliability_warning=reliability,
        trace=trace,
    )

def _exec_correlation(
    q: QueryObject,
    df: pd.DataFrame,
    profile: DatasetProfile,
    start: float,
) -> QueryResult:
    """
    Correlation analysis.
    - If mapped columns include a categorical + numeric → categorical relationship.
    - If exactly 2 numeric columns mapped → targeted Pearson correlation with rich output.
    - Otherwise → general correlation matrix across all numeric columns.
    """
    cat_mapped = _get_categorical_cols(q.mapped_columns, df, profile)
    num_mapped = _get_numeric_cols(q.mapped_columns, df, profile)

    # Explicit correlation keywords → skip categorical grouping detour
    explicit_corr = bool(re.search(
        r"\bcorrelat|\brelated\s+to\b|\brelationship\s+between\b|\bassociated\b|\bis\b.{0,20}\brelated\b",
        q.raw_query, re.IGNORECASE,
    ))

    # Case A: categorical + numeric → group the numeric by the categorical
    # Skip when query explicitly asks for correlation (Pearson path is more appropriate)
    if cat_mapped and num_mapped and not explicit_corr:
        return _exec_categorical_relationship_inline(
            q, df, profile, start, cat_mapped[0], num_mapped[0]
        )

    # Case B: exactly 2 numeric columns mapped → targeted correlation
    if len(num_mapped) == 2:
        return _exec_targeted_correlation_inline(
            q, df, profile, start, num_mapped[0], num_mapped[1]
        )

    # Case C: general correlation matrix
    num_cols = num_mapped if len(num_mapped) >= 2 else [c for c in profile.numeric_columns if c in df.columns]
    if len(num_cols) < 2:
        return _error_result(
            q.query_id, profile.session_id,
            ErrorType.mismatch,
            "Correlation analysis needs at least two numeric columns.",
            "Fewer than 2 numeric columns",
            ["Upload a dataset with more numeric columns"],
        )

    num_df = df[num_cols].apply(pd.to_numeric, errors="coerce")
    corr_matrix = num_df.corr(method="pearson")

    pairs = []
    cols = corr_matrix.columns.tolist()
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            r = corr_matrix.iloc[i, j]
            if pd.isna(r):
                continue
            pairs.append({
                "col_a": cols[i],
                "col_b": cols[j],
                "correlation": round(float(r), 4),
                "strength": _corr_label(r),
                "direction": "positive" if r > 0 else "negative",
            })

    pairs.sort(key=lambda x: abs(x["correlation"]), reverse=True)

    if not pairs:
        return _error_result(
            q.query_id, profile.session_id,
            ErrorType.data_quality,
            "Could not compute correlations — columns may not have enough overlap.",
            "All correlation values were NaN",
            ["Ensure numeric columns have sufficient non-null values"],
        )

    top = pairs[0]
    abs_r = abs(top["correlation"])
    strength = _corr_label(top["correlation"])
    direction = top["direction"]

    if abs_r >= 0.7:
        business_note = (
            f"This is a {strength} link — changes in '{top['col_a']}' "
            f"reliably {'increase' if direction == 'positive' else 'decrease'} '{top['col_b']}'."
        )
    elif abs_r >= 0.4:
        business_note = (
            f"This is a {strength} link — '{top['col_a']}' has some influence on "
            f"'{top['col_b']}', but other factors also play a role."
        )
    else:
        business_note = (
            f"This is a {strength} link — '{top['col_a']}' has little consistent "
            f"relationship with '{top['col_b']}'. Other factors are likely more important."
        )

    plain = (
        f"The strongest relationship is between '{top['col_a']}' and "
        f"'{top['col_b']}': r = {top['correlation']:+.3f} ({strength} {direction}). "
        + business_note
    )
    takeaway = (
        f"When '{top['col_a']}' goes up, '{top['col_b']}' tends to "
        f"{'increase' if direction == 'positive' else 'decrease'} ({strength} correlation, "
        f"r = {top['correlation']:+.3f})."
    )

    s_a = pd.to_numeric(df[top["col_a"]], errors="coerce")
    s_b = pd.to_numeric(df[top["col_b"]], errors="coerce")
    mask = s_a.notna() & s_b.notna()
    chart = ChartSpec(
        chart_type=ChartType.scatter,
        title=f"{top['col_a']} vs {top['col_b']} (r = {top['correlation']:+.3f})",
        x_field=top["col_a"],
        y_field=top["col_b"],
        x_axis_label=top["col_a"],
        y_axis_label=top["col_b"],
        data=[
            ChartDataPoint(label=round(float(x), 4), value=round(float(y), 4))
            for x, y in zip(s_a[mask], s_b[mask])
        ][:200],
        color_scheme="sequential",
    )

    trace = _make_trace(q, "pearson_correlation", num_cols, start,
                        f"Computed Pearson correlation across {len(num_cols)} numeric columns.")
    follow_ups = _build_follow_ups(num_cols[:2], "correlation", profile)

    return QueryResult(
        query_id=q.query_id,
        session_id=profile.session_id,
        status=QueryStatus.success,
        result_value={"pairs": pairs},
        plain_summary=plain,
        key_takeaway=takeaway,
        chart=chart,
        suggested_follow_ups=follow_ups,
        trace=trace,
    )

def _exec_targeted_correlation_inline(
    q: QueryObject,
    df: pd.DataFrame,
    profile: DatasetProfile,
    start: float,
    col_a: str,
    col_b: str,
) -> QueryResult:
    """Targeted Pearson correlation between two specific columns — rich output."""
    s_a = pd.to_numeric(df[col_a], errors="coerce")
    s_b = pd.to_numeric(df[col_b], errors="coerce")
    mask = s_a.notna() & s_b.notna()
    n_pairs = int(mask.sum())

    if n_pairs < 5:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.data_quality,
            f"Not enough overlapping values between '{col_a}' and '{col_b}' (found {n_pairs}).",
            f"Only {n_pairs} non-null pairs", ["Check for missing values"],
        )

    r, p_val = scipy_stats.pearsonr(s_a[mask], s_b[mask])
    r = float(r)
    abs_r = abs(r)
    strength = _corr_label(r)
    direction = "positive" if r >= 0 else "negative"
    sig = "statistically significant" if p_val < 0.05 else "not statistically significant"

    # Business interpretation
    if abs_r >= 0.7:
        biz = (
            f"Higher '{col_a}' strongly {'increases' if direction == 'positive' else 'decreases'} "
            f"'{col_b}'. This relationship is reliable enough to inform business decisions."
        )
    elif abs_r >= 0.4:
        biz = (
            f"Higher '{col_a}' tends to {'increase' if direction == 'positive' else 'decrease'} "
            f"'{col_b}', but the effect is moderate — other factors also contribute."
        )
    else:
        biz = (
            f"There is no clear {direction} pattern between '{col_a}' and '{col_b}'. "
            f"The weak correlation (r = {r:+.3f}) suggests these columns vary largely independently."
        )

    plain = (
        f"'{col_a}' and '{col_b}' have a {strength} {direction} correlation "
        f"(r = {r:+.3f}, p = {p_val:.4f}, n = {n_pairs}). "
        f"This is {sig} at the 5% level. {biz}"
    )
    takeaway = (
        f"{strength.capitalize()} {direction} relationship: r = {r:+.3f}. "
        f"When '{col_a}' increases, '{col_b}' tends to "
        f"{'increase' if direction == 'positive' else 'decrease'}."
    )

    chart = ChartSpec(
        chart_type=ChartType.scatter,
        title=f"{col_a} vs {col_b}  (r = {r:+.3f})",
        x_field=col_a, y_field=col_b,
        x_axis_label=col_a, y_axis_label=col_b,
        data=[
            ChartDataPoint(label=round(float(x), 4), value=round(float(y), 4))
            for x, y in zip(s_a[mask], s_b[mask])
        ][:200],
        color_scheme="sequential",
    )

    trace = _make_trace(q, "targeted_correlation", [col_a, col_b], start,
                        f"Computed Pearson r between '{col_a}' and '{col_b}'.")
    return QueryResult(
        query_id=q.query_id, session_id=profile.session_id,
        status=QueryStatus.success,
        result_value={"col_a": col_a, "col_b": col_b,
                      "correlation": round(r, 4), "p_value": round(p_val, 6),
                      "n_pairs": n_pairs, "strength": strength, "direction": direction},
        plain_summary=plain, key_takeaway=takeaway,
        chart=chart, trace=trace,
    )

def _exec_categorical_relationship_inline(
    q: QueryObject,
    df: pd.DataFrame,
    profile: DatasetProfile,
    start: float,
    cat_col: str,
    num_col: str,
) -> QueryResult:
    """Analyse how a numeric metric varies across a categorical column — no clarification needed."""
    if df[cat_col].nunique() > MAX_GROUPBY_CATEGORIES:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.unsupported,
            f"'{cat_col}' has too many unique values ({df[cat_col].nunique()}) to compare.",
            f"Cardinality exceeds limit {MAX_GROUPBY_CATEGORIES}",
            ["Try a categorical column with fewer distinct values"],
        )

    grouped = (
        df.groupby(cat_col)[num_col]
        .agg(total="sum", average="mean", count="count")
        .reset_index()
    )

    if grouped.empty:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.data_quality,
            f"No valid data found when grouping '{num_col}' by '{cat_col}'.",
            "Grouped DataFrame is empty", ["Check for missing values"],
        )

    # Use average when query mentions it, otherwise use total
    cat_raw = q.raw_query.lower()
    use_mean_cat = bool(re.search(r"\b(average|mean|avg|per[- ]order|per[- ]transaction|per[- ]unit)\b", cat_raw))
    metric_col = "average" if use_mean_cat else "total"
    metric_label = "average" if use_mean_cat else "total"

    grouped = grouped.sort_values(metric_col, ascending=False)
    top = grouped.iloc[0]
    bottom = grouped.iloc[-1]
    n_groups = len(grouped)
    gap = float(top[metric_col]) - float(bottom[metric_col])
    gap_pct = abs(gap) / max(abs(float(bottom[metric_col])), 1e-9) * 100

    records = grouped.rename(columns={
        "total": f"total_{num_col}",
        "average": f"avg_{num_col}",
        "count": "order_count",
    }).to_dict(orient="records")

    plain = (
        f"Across {n_groups} {cat_col} groups, {metric_label} {num_col} ranges from "
        f"{_fmt(float(bottom[metric_col]))} ('{bottom[cat_col]}') to "
        f"{_fmt(float(top[metric_col]))} ('{top[cat_col]}'). "
        f"'{top[cat_col]}' leads by {_fmt(abs(gap))} — {gap_pct:.1f}% more than the lowest group."
    )
    takeaway = (
        f"'{top[cat_col]}' has the highest {metric_label} {num_col} ({_fmt(float(top[metric_col]))}); "
        f"'{bottom[cat_col]}' has the lowest ({_fmt(float(bottom[metric_col]))})."
    )

    chart = ChartSpec(
        chart_type=ChartType.bar,
        title=f"Total {num_col} by {cat_col}",
        x_field=cat_col, y_field=num_col,
        x_axis_label=cat_col, y_axis_label=f"Total {num_col}",
        data=[
            ChartDataPoint(label=str(r[cat_col]), value=round(float(r[f"total_{num_col}"]), 4))
            for r in records
        ],
        color_scheme="categorical",
    )

    col_meta = next((c for c in profile.columns if c.name == num_col), None)
    reliability = _check_reliability(num_col, col_meta.null_rate if col_meta else 0, len(df))
    trace = _make_trace(q, "categorical_relationship", [cat_col, num_col], start,
                        f"Grouped '{num_col}' by '{cat_col}' and compared totals, averages, counts.")
    follow_ups = _build_follow_ups([cat_col, num_col], "comparison", profile)

    return QueryResult(
        query_id=q.query_id, session_id=profile.session_id,
        status=QueryStatus.success,
        result_value={"cat_col": cat_col, "num_col": num_col, "groups": records},
        plain_summary=plain, key_takeaway=takeaway,
        chart=chart, reliability_warning=reliability,
        suggested_follow_ups=follow_ups, trace=trace,
    )

def _exec_feature_importance(
    q: QueryObject,
    df: pd.DataFrame,
    profile: DatasetProfile,
    start: float,
) -> QueryResult:
    """
    Factor influence analysis: ranks both numeric and categorical factors by
    their impact on the target column.
    - Numeric factors: |Pearson r| with the target.
    - Categorical factors: grouped variation — (max_group_mean - min_group_mean)
      normalised by the overall std of the target (a transparent, explainable proxy).
    Results are ranked by absolute impact and displayed on a horizontal bar chart.
    """
    num_cols = [c for c in profile.numeric_columns if c in df.columns]
    cat_cols = [c for c in profile.categorical_columns if c in df.columns]
    binary_cols = [c for c in profile.binary_columns if c in df.columns]

    # All numeric cols including binary are valid TARGET candidates
    # (e.g. "what affects churn?" where churn=0/1 is binary)
    all_num_for_target = num_cols  # includes binary

    if len(all_num_for_target) < 1:
        return _error_result(
            q.query_id, profile.session_id,
            ErrorType.mismatch,
            "Factor analysis needs at least one numeric column to use as the target.",
            "No numeric columns",
            ["Upload a dataset with numeric columns"],
        )

    # Identify target column — prefer explicitly mapped numeric column.
    # Binary columns are valid targets (e.g. churned, smoker, is_premium).
    target = None
    for col in q.mapped_columns:
        if col in all_num_for_target:
            target = col
            break
    if target is None:
        # Try profile target or semantic name matching — no hardcoded column list
        target = profile.potential_target
        if target not in all_num_for_target:
            # Prefer non-binary quantity column with highest variance
            continuous = [c for c in num_cols if c not in binary_cols]
            if continuous:
                target = max(
                    continuous,
                    key=lambda c: pd.to_numeric(df[c], errors="coerce").std() or 0,
                )
            else:
                target = all_num_for_target[0]

    target_series = pd.to_numeric(df[target], errors="coerce")
    target_std = float(target_series.std()) if target_series.std() > 0 else 1.0
    target_valid = target_series.notna()

    factors: list[dict] = []

    # Numeric factors — |Pearson r|
    # Use all numeric columns as features (binary columns are valid predictors)
    for feat in [c for c in num_cols if c != target]:
        feat_series = pd.to_numeric(df[feat], errors="coerce")
        mask = target_valid & feat_series.notna()
        if mask.sum() < 5:
            continue
        r, p_val = scipy_stats.pearsonr(feat_series[mask], target_series[mask])
        r = float(r)
        direction = "positive" if r >= 0 else "negative"
        factors.append({
            "feature": feat,
            "type": "numeric",
            "impact_score": round(abs(r), 4),
            "correlation": round(r, 4),
            "direction": direction,
            "strength": _corr_label(r),
            "p_value": round(float(p_val), 6),
        })

    # Categorical factors — normalised between-group range
    for cat in cat_cols:
        if df[cat].nunique() > MAX_GROUPBY_CATEGORIES:
            continue
        group_means = (
            df[[cat, target]].copy()
            .assign(**{target: target_series})
            .groupby(cat)[target]
            .mean()
            .dropna()
        )
        if len(group_means) < 2:
            continue
        spread = float(group_means.max() - group_means.min())
        norm_impact = spread / target_std  # how many std-deviations does the category span?
        best_group = str(group_means.idxmax())
        worst_group = str(group_means.idxmin())
        factors.append({
            "feature": cat,
            "type": "categorical",
            "impact_score": round(min(norm_impact, 1.0), 4),  # cap at 1.0 for chart scale
            "group_spread": round(spread, 4),
            "best_group": best_group,
            "worst_group": worst_group,
            "n_groups": int(len(group_means)),
        })

    factors.sort(key=lambda x: x["impact_score"], reverse=True)

    if not factors:
        return _error_result(
            q.query_id, profile.session_id,
            ErrorType.data_quality,
            f"Could not compute factor influence on '{target}' — not enough data.",
            "All correlations and group analyses failed",
            ["Check for missing values in your columns"],
        )

    top = factors[0]
    top_name = top["feature"]

    # Build plain summary from computed values
    top_desc: str
    if top["type"] == "numeric":
        top_desc = (
            f"'{top_name}' (numeric, r = {top['correlation']:+.3f}, "
            f"{top['strength']} {top['direction']} correlation)"
        )
    else:
        top_desc = (
            f"'{top_name}' (categorical, {top['n_groups']} groups — "
            f"'{top['best_group']}' vs '{top['worst_group']}' differ by {_fmt(top['group_spread'])})"
        )

    runner_ups = []
    for f in factors[1:3]:
        if f["type"] == "numeric":
            runner_ups.append(f"'{f['feature']}' (r = {f['correlation']:+.3f})")
        else:
            runner_ups.append(f"'{f['feature']}' (categorical, spread = {_fmt(f['group_spread'])})")

    plain = (
        f"The strongest factor influencing '{target}' is {top_desc}. "
        + (f"Also notable: {', '.join(runner_ups)}. " if runner_ups else "")
        + f"Rankings are based on {len([f for f in factors if f['type'] == 'numeric'])} numeric "
        f"and {len([f for f in factors if f['type'] == 'categorical'])} categorical factors."
    )
    takeaway = (
        f"'{top_name}' has the greatest impact on '{target}' "
        f"(impact score: {top['impact_score']:.3f})."
    )

    chart = ChartSpec(
        chart_type=ChartType.bar,
        title=f"Factor Impact on '{target}'  (ranked by influence score)",
        x_field="feature",
        y_field="impact_score",
        x_axis_label="Factor",
        y_axis_label="Impact Score",
        data=[
            ChartDataPoint(label=f["feature"], value=round(f["impact_score"], 4))
            for f in factors[:10]
        ],
        color_scheme="sequential",
    )

    trace = _make_trace(
        q, "feature_importance",
        [target] + [f["feature"] for f in factors[:5]], start,
        f"Ranked {len(factors)} factors (numeric + categorical) by influence on '{target}'.",
    )
    follow_ups = _build_follow_ups([target], "feature_importance", profile)

    return QueryResult(
        query_id=q.query_id,
        session_id=profile.session_id,
        status=QueryStatus.success,
        result_value={"target": target, "factors": factors},
        plain_summary=plain,
        key_takeaway=takeaway,
        chart=chart,
        suggested_follow_ups=follow_ups,
        trace=trace,
    )

# Phase 3 — Advanced executors

def _exec_targeted_correlation(
    q: QueryObject,
    df: pd.DataFrame,
    profile: DatasetProfile,
    start: float,
) -> QueryResult:
    """Pearson r for a specific column pair with direction interpretation."""
    params = q.parameters
    num_cols_avail = [c for c in profile.numeric_columns if c in df.columns]

    col_a = params.get("col_a") or (q.mapped_columns[0] if len(q.mapped_columns) >= 1 else None)
    col_b = params.get("col_b") or (q.mapped_columns[1] if len(q.mapped_columns) >= 2 else None)

    # Fallback to first two numeric columns
    if not col_a or col_a not in df.columns:
        col_a = num_cols_avail[0] if len(num_cols_avail) >= 1 else None
    if not col_b or col_b not in df.columns:
        candidates = [c for c in num_cols_avail if c != col_a]
        col_b = candidates[0] if candidates else None

    if not col_a or not col_b:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.mismatch,
            "Need two numeric columns for targeted correlation.",
            "col_a or col_b not resolved", ["Specify two numeric columns"],
        )

    s_a = pd.to_numeric(df[col_a], errors="coerce")
    s_b = pd.to_numeric(df[col_b], errors="coerce")
    mask = s_a.notna() & s_b.notna()
    if mask.sum() < 5:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.data_quality,
            f"Not enough overlapping values between '{col_a}' and '{col_b}'.",
            f"Only {mask.sum()} non-null pairs", ["Check for missing values"],
        )

    r, p_val = scipy_stats.pearsonr(s_a[mask], s_b[mask])
    r = float(r)
    abs_r = abs(r)
    strength = _corr_label(r)
    direction = "positive" if r >= 0 else "negative"
    sig = "statistically significant" if p_val < 0.05 else "not statistically significant"

    if abs_r >= 0.7:
        biz = (
            f"Higher '{col_a}' strongly {'increases' if direction == 'positive' else 'decreases'} "
            f"'{col_b}'. This is reliable enough to inform business decisions."
        )
    elif abs_r >= 0.4:
        biz = (
            f"Higher '{col_a}' tends to {'increase' if direction == 'positive' else 'decrease'} "
            f"'{col_b}', but the effect is moderate — other factors also contribute."
        )
    else:
        biz = (
            f"There is no clear pattern between '{col_a}' and '{col_b}'. "
            f"They vary largely independently (r = {r:+.3f})."
        )

    plain = (
        f"'{col_a}' and '{col_b}' have a {strength} {direction} correlation "
        f"(r = {r:+.3f}, p = {p_val:.4f}, n = {int(mask.sum())}). "
        f"This is {sig} at the 5% level. {biz}"
    )
    takeaway = (
        f"{strength.capitalize()} {direction} link: r = {r:+.3f}. "
        f"When '{col_a}' increases, '{col_b}' tends to "
        f"{'increase' if direction == 'positive' else 'decrease'}."
    )

    chart = ChartSpec(
        chart_type=ChartType.scatter,
        title=f"{col_a} vs {col_b}  (r = {r:+.3f})",
        x_field=col_a, y_field=col_b,
        x_axis_label=col_a, y_axis_label=col_b,
        data=[
            ChartDataPoint(label=round(float(x), 4), value=round(float(y), 4))
            for x, y in zip(s_a[mask], s_b[mask])
        ][:200],
        color_scheme="sequential",
    )

    trace = _make_trace(q, "targeted_correlation", [col_a, col_b], start,
                        f"Computed Pearson r between '{col_a}' and '{col_b}'.")
    return QueryResult(
        query_id=q.query_id, session_id=profile.session_id,
        status=QueryStatus.success,
        result_value={"col_a": col_a, "col_b": col_b,
                      "correlation": round(r, 4), "p_value": round(p_val, 6),
                      "n_pairs": int(mask.sum()), "strength": strength, "direction": direction},
        plain_summary=plain, key_takeaway=takeaway,
        chart=chart, trace=trace,
    )

def _exec_compound_filter(
    q: QueryObject,
    df: pd.DataFrame,
    profile: DatasetProfile,
    start: float,
) -> QueryResult:
    """Apply two simultaneous percentile conditions and summarise results."""
    params = q.parameters
    conditions: list[dict] = params.get("conditions", [])

    # Fallback: use first two numeric columns with "high"
    if len(conditions) < 2:
        num_cols = [c for c in profile.numeric_columns if c in df.columns]
        if len(num_cols) < 2:
            return _error_result(
                q.query_id, profile.session_id, ErrorType.mismatch,
                "Compound filter needs at least two numeric columns.",
                "Fewer than 2 numeric columns", ["Upload a dataset with more numeric columns"],
            )
        conditions = [
            {"col": num_cols[0], "word": "high"},
            {"col": num_cols[1], "word": "high"},
        ]

    mask = pd.Series([True] * len(df), index=df.index)
    applied: list[dict] = []
    for cond in conditions[:2]:
        col = cond.get("col", "")
        word = cond.get("word", "high")
        if col not in df.columns:
            continue
        series = pd.to_numeric(df[col], errors="coerce")
        threshold = resolve_threshold(word, series)
        low_words = {"low", "lowest", "small", "very low"}
        if word.lower() in low_words:
            mask = mask & (series <= threshold)
        else:
            mask = mask & (series >= threshold)
        applied.append({"col": col, "word": word, "threshold": round(threshold, 4)})

    filtered = df[mask]
    n_filtered = len(filtered)
    pct = round(n_filtered / max(len(df), 1) * 100, 2)

    num_summary: dict = {}
    for col in [c["col"] for c in applied]:
        if col in filtered.columns:
            s = pd.to_numeric(filtered[col], errors="coerce").dropna()
            if len(s) > 0:
                num_summary[col] = {"mean": round(float(s.mean()), 4),
                                    "min": round(float(s.min()), 4),
                                    "max": round(float(s.max()), 4)}

    cols_desc = " AND ".join(f"{c['col']} is {c['word']}" for c in applied)
    plain = (
        f"{n_filtered} rows ({pct}% of data) satisfy: {cols_desc}. "
        + (f"Mean values in filtered set: "
           + ", ".join(f"{k}={v['mean']}" for k, v in num_summary.items()) + "."
           if num_summary else "")
    )
    takeaway = f"{n_filtered} rows match both conditions ({pct}% of dataset)."

    trace = _make_trace(q, "compound_filter", [c["col"] for c in applied], start,
                        f"Applied {len(applied)} percentile-based filters.")
    return QueryResult(
        query_id=q.query_id, session_id=profile.session_id,
        status=QueryStatus.success,
        result_value={"n_filtered": n_filtered, "pct_of_data": pct,
                      "conditions_applied": applied, "numeric_summary": num_summary},
        plain_summary=plain, key_takeaway=takeaway, trace=trace,
    )

def _exec_derived_metric(
    q: QueryObject,
    df: pd.DataFrame,
    profile: DatasetProfile,
    start: float,
) -> QueryResult:
    """Compute numerator/denominator derived column and summarise it.

    Extended: detects year-filter queries like "revenue for 2024" and returns
    year-filtered totals instead of computing a derived ratio.
    """
    params = q.parameters
    raw_lower = q.raw_query.lower()
    num_cols = [c for c in profile.numeric_columns if c in df.columns]

    # ── Group-ratio queries ("revenue ratio of Online to In-Store") ──
    ratio_match = re.search(
        r"\bratio\s+of\s+(\w[\w\s]*?)\s+to\s+(\w[\w\s]*?)(?:\s+\w+)?\s*[?.]?$",
        q.raw_query, re.IGNORECASE,
    )
    if ratio_match:
        group_a_raw = ratio_match.group(1).strip()
        group_b_raw = ratio_match.group(2).strip()
        # Find the best categorical column with these values
        mapped_num_dm = _get_numeric_cols(q.mapped_columns, df, profile)
        metric_col_dm = (mapped_num_dm[0] if mapped_num_dm else
                         next((c for c in num_cols if any(k in c.lower() for k in
                               ("revenue", "profit", "sales", "cost"))), None)
                         or (num_cols[0] if num_cols else None))
        cat_cols_dm = [c for c in profile.categorical_columns if c in df.columns]
        best_cat_dm = None
        group_a_val, group_b_val = None, None
        for cc in cat_cols_dm:
            col_vals_dm = [str(v) for v in df[cc].dropna().unique()]
            a_match = next((v for v in col_vals_dm if group_a_raw.lower() in v.lower()), None)
            b_match = next((v for v in col_vals_dm if group_b_raw.lower() in v.lower()), None)
            if a_match and b_match:
                best_cat_dm = cc
                group_a_val, group_b_val = a_match, b_match
                break
        if best_cat_dm and metric_col_dm and group_a_val and group_b_val:
            m_s_dm = pd.to_numeric(df[metric_col_dm], errors="coerce")
            val_a_dm = float(m_s_dm[df[best_cat_dm] == group_a_val].sum())
            val_b_dm = float(m_s_dm[df[best_cat_dm] == group_b_val].sum())
            ratio_dm = round(val_a_dm / max(abs(val_b_dm), 1e-9), 6)
            plain_dm = (
                f"Revenue ratio of '{group_a_val}' to '{group_b_val}' ({best_cat_dm}): "
                f"{_fmt(ratio_dm)} "
                f"({group_a_val}: {_fmt(val_a_dm)}, {group_b_val}: {_fmt(val_b_dm)})."
            )
            takeaway_dm = (
                f"'{group_a_val}' / '{group_b_val}' {metric_col_dm} ratio: {_fmt(ratio_dm)}."
            )
            trace_dm = _make_trace(q, "group_ratio", [best_cat_dm, metric_col_dm], start,
                                   f"Computed {metric_col_dm} ratio: {group_a_val} / {group_b_val}.")
            return QueryResult(
                query_id=q.query_id, session_id=profile.session_id,
                status=QueryStatus.success,
                result_value={"group_col": best_cat_dm, "group_a": group_a_val,
                              "group_b": group_b_val, "ratio": ratio_dm,
                              "val_a": round(val_a_dm, 4), "val_b": round(val_b_dm, 4)},
                plain_summary=plain_dm, key_takeaway=takeaway_dm, trace=trace_dm,
            )

    # ── Year-filter aggregation ("revenue for 2024", "total profit in 2022") ──
    year_match = re.search(r"\b(20\d{2}|19\d{2})\b", q.raw_query)
    dt_cols_all = [c for c in profile.datetime_columns if c in df.columns]
    if year_match and dt_cols_all:
        target_year = int(year_match.group(1))
        dt_col = dt_cols_all[0]
        # Pick the best numeric column from mapped_columns
        mapped_num = _get_numeric_cols(q.mapped_columns, df, profile)
        metric_col = (mapped_num[0] if mapped_num else
                      next((c for c in num_cols if any(k in c.lower() for k in
                            ("revenue", "profit", "cost", "sales", "spend", "unit"))), None)
                      or (num_cols[0] if num_cols else None))
        if metric_col:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    dt_s = pd.to_datetime(df[dt_col], errors="coerce")
            except Exception:
                dt_s = None
            if dt_s is not None:
                year_mask = dt_s.dt.year == target_year
                yr_df = df[year_mask]
                metric_s = pd.to_numeric(yr_df[metric_col], errors="coerce").dropna()
                year_total = float(metric_s.sum())
                n_rows = int(year_mask.sum())
                plain = (
                    f"Total {metric_col} for {target_year}: {_fmt(year_total)} "
                    f"({n_rows} orders)."
                )
                takeaway = f"{target_year} total {metric_col}: {_fmt(year_total)}."
                trace = _make_trace(q, "year_filter_aggregate", [dt_col, metric_col], start,
                                    f"Filtered by year {target_year}, summed '{metric_col}'.")
                return QueryResult(
                    query_id=q.query_id, session_id=profile.session_id,
                    status=QueryStatus.success,
                    result_value={"year": target_year, "metric_col": metric_col,
                                  "total": round(year_total, 4), "n_rows": n_rows},
                    plain_summary=plain, key_takeaway=takeaway, trace=trace,
                )

    numerator = params.get("numerator_col") or (num_cols[0] if len(num_cols) >= 1 else None)
    denominator = params.get("denominator_col") or (num_cols[1] if len(num_cols) >= 2 else None)
    derived_name = params.get("derived_name") or (
        f"{numerator}_per_{denominator}" if numerator and denominator else "derived_metric"
    )

    if not numerator or not denominator:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.mismatch,
            "Derived metric needs at least two numeric columns (numerator / denominator).",
            "numerator or denominator not found", ["Specify two numeric columns"],
        )
    if numerator not in df.columns or denominator not in df.columns:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.mismatch,
            f"Column '{numerator}' or '{denominator}' not found in dataset.",
            "column missing", [f"Available: {', '.join(num_cols[:5])}"],
        )

    num_s = pd.to_numeric(df[numerator], errors="coerce")
    den_s = pd.to_numeric(df[denominator], errors="coerce")
    with np.errstate(divide="ignore", invalid="ignore"):
        derived = np.where(den_s != 0, num_s / den_s, np.nan)
    derived_s = pd.Series(derived, index=df.index).dropna()

    if derived_s.empty:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.data_quality,
            f"Could not compute {derived_name} — denominator may be all zeros.",
            "derived series empty", ["Check denominator column for zeros"],
        )

    # Rank by derived metric (top 10 rows)
    temp = pd.DataFrame({numerator: num_s, denominator: den_s, derived_name: derived})
    # Add categorical column for grouping if available
    cat_cols = [c for c in profile.categorical_columns if c in df.columns]
    if cat_cols:
        group_col = cat_cols[0]
        grouped = (
            temp.dropna(subset=[derived_name])
            .assign(**{group_col: df[group_col]})
            .groupby(group_col, dropna=True)[derived_name]
            .mean()
            .sort_values(ascending=False)
            .head(10)
            .reset_index()
        )
        result_records = grouped.to_dict(orient="records")
        chart = ChartSpec(
            chart_type=ChartType.bar,
            title=f"{derived_name} by {group_col}",
            x_field=group_col, y_field=derived_name,
            x_axis_label=group_col, y_axis_label=derived_name,
            data=[ChartDataPoint(label=str(r[group_col]),
                                 value=round(float(r[derived_name]), 4))
                  for r in result_records],
            color_scheme="sequential",
        )
    else:
        result_records = []
        chart = None

    stats = {
        "mean": round(float(derived_s.mean()), 4),
        "median": round(float(derived_s.median()), 4),
        "std": round(float(derived_s.std()), 4),
        "min": round(float(derived_s.min()), 4),
        "max": round(float(derived_s.max()), 4),
    }
    plain = (
        f"'{derived_name}' ({numerator} / {denominator}) averages "
        f"{_fmt(stats['mean'])} across {len(derived_s)} rows "
        f"(range: {_fmt(stats['min'])} – {_fmt(stats['max'])})."
    )
    takeaway = f"The typical '{derived_name}' is {_fmt(stats['median'])} (median)."

    trace = _make_trace(q, "derived_metric", [numerator, denominator], start,
                        f"Computed derived metric '{derived_name}' = {numerator}/{denominator}.")
    return QueryResult(
        query_id=q.query_id, session_id=profile.session_id,
        status=QueryStatus.success,
        result_value={"derived_name": derived_name, "stats": stats,
                      "group_ranking": result_records},
        plain_summary=plain, key_takeaway=takeaway,
        chart=chart, trace=trace,
    )

def _exec_period_growth(
    q: QueryObject,
    df: pd.DataFrame,
    profile: DatasetProfile,
    start: float,
) -> QueryResult:
    """Period-over-period delta on a time + metric column pair."""
    import warnings

    params = q.parameters
    date_col = params.get("date_col") or (profile.datetime_columns[0] if profile.datetime_columns else None)
    metric_col = params.get("metric_col") or params.get("target_col") or (
        profile.numeric_columns[0] if profile.numeric_columns else None
    )

    if not date_col or date_col not in df.columns:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.mismatch,
            "Period growth analysis needs a date column.",
            "No date column available", ["Ensure your dataset has a date column"],
        )
    if not metric_col or metric_col not in df.columns:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.mismatch,
            "Period growth analysis needs a numeric metric column.",
            "No numeric column available", ["Specify a numeric column"],
        )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        dt_s = pd.to_datetime(df[date_col], errors="coerce")
    num_s = pd.to_numeric(df[metric_col], errors="coerce")
    mask = dt_s.notna() & num_s.notna()

    if mask.sum() < 4:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.data_quality,
            "Not enough data points for period growth analysis (need at least 4).",
            f"Only {mask.sum()} valid rows", ["Upload more data"],
        )

    temp = pd.DataFrame({date_col: dt_s[mask], metric_col: num_s[mask]})
    temp["__period"] = temp[date_col].dt.to_period("M")
    monthly = (
        temp.groupby("__period")[metric_col].sum()
        .reset_index().sort_values("__period")
    )
    monthly["period_str"] = monthly["__period"].astype(str)
    monthly["growth_pct"] = monthly[metric_col].pct_change() * 100

    if len(monthly) < 2:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.data_quality,
            "Not enough time periods to compute growth rates.",
            "Fewer than 2 periods", ["Upload data spanning more months"],
        )

    valid_growth = monthly.dropna(subset=["growth_pct"])
    highest_idx = valid_growth["growth_pct"].idxmax() if not valid_growth.empty else None
    highest_period = str(monthly.loc[highest_idx, "period_str"]) if highest_idx is not None else "N/A"
    highest_growth = float(monthly.loc[highest_idx, "growth_pct"]) if highest_idx is not None else 0.0

    # Detect spikes (> 2 std dev)
    mean_g = float(valid_growth["growth_pct"].mean())
    std_g = float(valid_growth["growth_pct"].std())
    spike_mask = abs(valid_growth["growth_pct"] - mean_g) > 2 * std_g
    spike_periods = valid_growth.loc[spike_mask, "period_str"].tolist()

    period_records = monthly[["period_str", metric_col, "growth_pct"]].to_dict(orient="records")
    plain = (
        f"'{metric_col}' showed the highest month-over-month growth in "
        f"{highest_period} ({highest_growth:+.1f}%). "
        + (f"Spike periods detected: {', '.join(spike_periods)}." if spike_periods
           else "No unusual spikes detected.")
    )
    takeaway = (
        f"Peak growth for '{metric_col}': {highest_period} ({highest_growth:+.1f}%)."
    )

    chart = ChartSpec(
        chart_type=ChartType.bar,
        title=f"{metric_col} — Period-over-Period Growth (%)",
        x_field="period", y_field="growth_pct",
        x_axis_label="Period", y_axis_label="Growth (%)",
        data=[
            ChartDataPoint(label=str(r["period_str"]),
                           value=round(float(r["growth_pct"]), 2) if r["growth_pct"] is not None and not np.isnan(r["growth_pct"]) else 0.0)
            for r in period_records if r["growth_pct"] is not None
        ],
        color_scheme="sequential",
    )

    trace = _make_trace(q, "period_growth", [date_col, metric_col], start,
                        f"Computed MoM growth for '{metric_col}' over '{date_col}'.")
    return QueryResult(
        query_id=q.query_id, session_id=profile.session_id,
        status=QueryStatus.success,
        result_value={"metric_col": metric_col, "date_col": date_col,
                      "period_data": period_records,
                      "highest_growth_period": highest_period,
                      "highest_growth_pct": round(highest_growth, 2),
                      "spike_periods": spike_periods},
        plain_summary=plain, key_takeaway=takeaway,
        chart=chart, trace=trace,
    )

def _exec_anomaly_query(
    q: QueryObject,
    df: pd.DataFrame,
    profile: DatasetProfile,
    start: float,
) -> QueryResult:
    """Delegate to the existing Isolation Forest in ml_module."""
    params = q.parameters
    # Exclude binary columns (0/1 flags) — they are not meaningful for outlier detection
    _non_binary = [c for c in profile.numeric_columns if c not in profile.binary_columns]
    target_cols: list[str] = params.get("columns") or [
        c for c in _non_binary if c in df.columns
    ]
    target_cols = [c for c in target_cols if c in df.columns]

    if not target_cols:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.mismatch,
            "Anomaly detection needs at least one numeric column.",
            "No numeric columns specified", [f"Available: {', '.join(profile.numeric_columns[:5])}"],
        )

    try:
        from app.modules.ml_module import _run_anomaly_detection  # private but intentional

        insight = _run_anomaly_detection(df, profile, target_cols)

        if insight is None:
            return _error_result(
                q.query_id, profile.session_id, ErrorType.data_quality,
                "Could not run anomaly detection. "
                "The dataset may have too few rows (needs 50+) or insufficient numeric data.",
                "IsolationForest returned None",
                ["Ensure at least 50 rows and 1 well-populated numeric column"],
            )

        return QueryResult(
            query_id=q.query_id, session_id=profile.session_id,
            status=QueryStatus.success,
            result_value=insight.value,
            plain_summary=insight.plain_summary,
            key_takeaway=insight.key_takeaway,
            chart=insight.chart,
            reliability_warning=insight.reliability_warning,
            trace=_make_trace(q, "anomaly_query", target_cols, start,
                              f"Ran Isolation Forest on {len(target_cols)} column(s)."),
        )

    except ImportError:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.unsupported,
            "Anomaly detection requires scikit-learn. Please install it.",
            "scikit-learn not available", ["pip install scikit-learn"],
        )
    except Exception as exc:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.parse_failure,
            "An error occurred during anomaly detection. Please try again.",
            str(exc), ["Check column data quality"],
        )

def _exec_multi_criteria_rank(
    q: QueryObject,
    df: pd.DataFrame,
    profile: DatasetProfile,
    start: float,
) -> QueryResult:
    """Composite score ranking: normalise metrics, apply weights, return top N groups."""
    params = q.parameters
    cat_cols = [c for c in profile.categorical_columns if c in df.columns]
    num_cols = [c for c in profile.numeric_columns if c in df.columns]

    group_col = params.get("group_col") or (cat_cols[0] if cat_cols else None)
    metrics: list[str] = params.get("metrics") or num_cols[:3]
    weights_raw: list[float] = params.get("weights") or [1.0] * len(metrics)
    n_top: int = int(params.get("n_top", 5))

    metrics = [m for m in metrics if m in df.columns]
    if not group_col or not metrics:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.mismatch,
            "Multi-criteria ranking needs a categorical group column and at least one metric.",
            "group_col or metrics missing", ["Specify a group column and numeric metrics"],
        )

    # Align weights length
    if len(weights_raw) < len(metrics):
        weights_raw = weights_raw + [1.0] * (len(metrics) - len(weights_raw))
    weights = weights_raw[: len(metrics)]
    weight_sum = sum(weights)
    weights = [w / weight_sum for w in weights] if weight_sum > 0 else [1 / len(metrics)] * len(metrics)

    grouped = df.groupby(group_col)[metrics].mean().reset_index()

    # Min-max normalise each metric
    for m in metrics:
        col_min = grouped[m].min()
        col_max = grouped[m].max()
        denom = col_max - col_min
        if denom > 0:
            grouped[f"__norm_{m}"] = (grouped[m] - col_min) / denom
        else:
            grouped[f"__norm_{m}"] = 0.5

    grouped["composite_score"] = sum(
        w * grouped[f"__norm_{m}"] for w, m in zip(weights, metrics)
    )
    grouped = grouped.sort_values("composite_score", ascending=False).head(n_top)
    records = grouped[[group_col] + metrics + ["composite_score"]].to_dict(orient="records")

    top = records[0] if records else {}
    top_name = str(top.get(group_col, "N/A"))
    top_score = float(top.get("composite_score", 0.0))

    plain = (
        f"'{top_name}' ranks highest across {len(metrics)} criteria "
        f"(composite score: {top_score:.3f}). "
        f"Top {n_top}: " + ", ".join(str(r[group_col]) for r in records) + "."
    )
    takeaway = f"Best overall performer: '{top_name}' (score {top_score:.3f})."

    chart = ChartSpec(
        chart_type=ChartType.bar,
        title=f"Multi-Criteria Ranking by {group_col}",
        x_field=group_col, y_field="composite_score",
        x_axis_label=group_col, y_axis_label="Composite Score",
        data=[ChartDataPoint(label=str(r[group_col]),
                             value=round(float(r["composite_score"]), 4))
              for r in records],
        color_scheme="sequential",
    )

    trace = _make_trace(q, "multi_criteria_rank", [group_col] + metrics, start,
                        f"Normalised {len(metrics)} metrics and computed weighted composite scores.")
    return QueryResult(
        query_id=q.query_id, session_id=profile.session_id,
        status=QueryStatus.success,
        result_value={"group_col": group_col, "metrics": metrics, "weights": weights,
                      "rankings": records},
        plain_summary=plain, key_takeaway=takeaway,
        chart=chart, trace=trace,
    )

def _exec_business_decision(
    q: QueryObject,
    df: pd.DataFrame,
    profile: DatasetProfile,
    start: float,
) -> QueryResult:
    """
    Strategic segment/group recommendation using a transparent four-component score:
      score = norm(total_metric) + norm(avg_metric) + norm(order_count) - norm(volatility)
    where volatility = coefficient of variation (std/mean) — penalises inconsistent groups.
    All normalisation is min-max so scores are in [0, 1].  The scoring logic is fully
    explainable: no black-box ML, no opaque weights.
    """
    params = q.parameters
    cat_cols = [c for c in profile.categorical_columns if c in df.columns]
    num_cols = [c for c in profile.numeric_columns if c in df.columns]

    group_col = params.get("group_col") or (cat_cols[0] if cat_cols else None)
    raw_metrics: list[str] = params.get("metrics") or num_cols[:3]
    metrics = [m for m in raw_metrics if m in df.columns]

    # If no explicit metrics, prefer profit/revenue-like columns
    if not metrics:
        for candidate in num_cols:
            lower = candidate.lower()
            if any(k in lower for k in ("profit", "revenue", "sales", "income", "margin")):
                metrics.append(candidate)
        if not metrics:
            metrics = num_cols[:2]

    if not group_col or not metrics:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.mismatch,
            "Strategic ranking needs a group column and at least one numeric metric.",
            "group_col or metrics missing", ["Specify a segment/group column and a metric"],
        )

    primary_metric = metrics[0]

    # Compute per-group stats for the primary metric
    grouped = (
        df.groupby(group_col)[primary_metric]
        .agg(total="sum", average="mean", order_count="count", std="std")
        .reset_index()
    )
    grouped["std"] = grouped["std"].fillna(0)
    grouped["avg_abs"] = grouped["average"].abs().clip(lower=1e-9)
    grouped["volatility"] = grouped["std"] / grouped["avg_abs"]  # coefficient of variation

    def _minmax(series: "pd.Series") -> "pd.Series":
        lo, hi = series.min(), series.max()
        if hi == lo:
            return series * 0 + 0.5
        return (series - lo) / (hi - lo)

    grouped["norm_total"] = _minmax(grouped["total"])
    grouped["norm_avg"] = _minmax(grouped["average"])
    grouped["norm_count"] = _minmax(grouped["order_count"])
    grouped["norm_vol"] = _minmax(grouped["volatility"])

    # Score = average of positives minus volatility penalty
    grouped["composite_score"] = (
        (grouped["norm_total"] + grouped["norm_avg"] + grouped["norm_count"]) / 3.0
        - 0.25 * grouped["norm_vol"]
    ).clip(lower=0)

    grouped = grouped.sort_values("composite_score", ascending=False)
    records = grouped[[group_col, "total", "average", "order_count", "volatility",
                        "composite_score"]].to_dict(orient="records")

    top = records[0] if records else {}
    second = records[1] if len(records) > 1 else None
    top_name = str(top.get(group_col, "N/A"))
    top_score = float(top.get("composite_score", 0))
    top_total = float(top.get("total", 0))
    top_avg = float(top.get("average", 0))
    top_count = int(top.get("order_count", 0))
    top_vol = float(top.get("volatility", 0))

    trade_off = ""
    if second:
        sec_name = str(second.get(group_col, ""))
        sec_total = float(second.get("total", 0))
        if sec_total > top_total and float(second.get("composite_score", 0)) < top_score:
            trade_off = (
                f" Note: '{sec_name}' has higher total {primary_metric} ({_fmt(sec_total)}) "
                f"but a lower composite score due to lower average or higher volatility."
            )

    plain = (
        f"The recommended focus segment is '{top_name}' (composite score: {top_score:.3f}). "
        f"It delivers total {primary_metric} of {_fmt(top_total)}, "
        f"averaging {_fmt(top_avg)} per order across {top_count} orders "
        f"with a consistency coefficient of {top_vol:.2f} (lower = more stable). "
        f"Ranking: " + ", ".join(
            f"'{r[group_col]}' ({r['composite_score']:.3f})" for r in records[:5]
        ) + "." + trade_off
    )
    takeaway = (
        f"Recommended: '{top_name}' — highest balanced score across total {primary_metric}, "
        f"average {primary_metric}, order volume, and consistency."
    )

    chart = ChartSpec(
        chart_type=ChartType.bar,
        title=f"Strategic Score by {group_col}  (total + avg + volume − volatility)",
        x_field="group", y_field="composite_score",
        x_axis_label=group_col, y_axis_label="Composite Score (0–1)",
        data=[
            ChartDataPoint(label=str(r[group_col]), value=round(float(r["composite_score"]), 4))
            for r in records[:10]
        ],
        color_scheme="sequential",
    )

    trace = _make_trace(q, "business_decision", [group_col] + metrics, start,
                        f"Scored '{group_col}' groups using norm(total)+norm(avg)+norm(count)-norm(volatility).")
    return QueryResult(
        query_id=q.query_id, session_id=profile.session_id,
        status=QueryStatus.success,
        result_value={"group_col": group_col, "primary_metric": primary_metric,
                      "scoring_components": ["total", "average", "order_count", "volatility"],
                      "rankings": records},
        plain_summary=plain, key_takeaway=takeaway,
        chart=chart, trace=trace,
    )

def _exec_scenario_analysis(
    q: QueryObject,
    df: pd.DataFrame,
    profile: DatasetProfile,
    start: float,
) -> QueryResult:
    """Split df into high/low condition groups and compare target metric means.
    Also handles what-if simulations: 'if cost increases by 40%'.
    """
    params = q.parameters
    num_cols = [c for c in profile.numeric_columns if c in df.columns]
    raw_lower = q.raw_query.lower()

    # ── What-if pattern: "if <col> increases/decreases by N%" ──────────────
    whatif_m = re.search(
        r"\bif\b.{0,40}?\b(increase[s]?|decrease[s]?|rises?|falls?|goes?\s+up|goes?\s+down)\b"
        r".{0,20}?by\b.{0,5}?(\d+(?:\.\d+)?)\s*%",
        q.raw_query, re.IGNORECASE,
    )
    if whatif_m:
        return _exec_whatif_simulation(q, df, profile, start, num_cols, whatif_m)

    # ── Normal scenario: "when X is high/low" ──────────────────────────────
    condition_col = params.get("condition_col")
    target_col = params.get("target_col")
    threshold_word = params.get("threshold_word", "")

    # When Tier 1 detected the intent, parameters is empty → derive from mapped_columns
    if not condition_col:
        mapped_num = [c for c in q.mapped_columns if c in num_cols]
        if len(mapped_num) >= 2:
            condition_col = mapped_num[0]
            target_col = target_col or mapped_num[1]
        elif len(mapped_num) == 1:
            condition_col = mapped_num[0]

    # Final fallback to first/second numeric column
    if not condition_col:
        condition_col = num_cols[0] if num_cols else None
    if not target_col:
        target_col = next((c for c in num_cols if c != condition_col), None)

    # Derive threshold_word from raw query when not set via parameters
    if not threshold_word:
        if any(w in raw_lower for w in ["low", "small", "minimum", "below", "decrease", "falls", "drop"]):
            threshold_word = "low"
        else:
            threshold_word = "high"

    if not condition_col or condition_col not in df.columns:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.mismatch,
            "Scenario analysis needs a numeric condition column.",
            "condition_col missing", [f"Available: {', '.join(num_cols[:5])}"],
        )
    if not target_col or target_col not in df.columns:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.mismatch,
            "Scenario analysis needs a numeric target column.",
            "target_col missing", [f"Available: {', '.join(num_cols[:5])}"],
        )

    cond_series = pd.to_numeric(df[condition_col], errors="coerce")
    threshold = resolve_threshold(threshold_word, cond_series)
    high_mask = cond_series >= threshold
    low_mask = cond_series < threshold

    target_series = pd.to_numeric(df[target_col], errors="coerce")
    high_vals = target_series[high_mask & target_series.notna()]
    low_vals = target_series[low_mask & target_series.notna()]

    if len(high_vals) < 2 or len(low_vals) < 2:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.data_quality,
            f"Not enough data in each group for scenario analysis.",
            f"High group: {len(high_vals)}, Low group: {len(low_vals)}",
            ["Ensure the threshold splits the data into two meaningful groups"],
        )

    high_mean = float(high_vals.mean())
    low_mean = float(low_vals.mean())
    diff = high_mean - low_mean
    pct_diff = abs(diff) / max(abs(low_mean), 1e-9) * 100

    plain = (
        f"When '{condition_col}' is {threshold_word} (≥ {_fmt(threshold)}), "
        f"the average '{target_col}' is {_fmt(high_mean)} "
        f"vs {_fmt(low_mean)} when it's low — "
        f"a {pct_diff:.1f}% {'increase' if diff >= 0 else 'decrease'}."
    )
    takeaway = (
        f"High '{condition_col}' → {_fmt(high_mean)} '{target_col}' avg; "
        f"Low → {_fmt(low_mean)} (Δ {diff:+.2f})."
    )

    chart = ChartSpec(
        chart_type=ChartType.bar,
        title=f"{target_col} by {condition_col} Scenario",
        x_field="scenario", y_field=target_col,
        x_axis_label="Scenario", y_axis_label=f"Mean {target_col}",
        data=[
            ChartDataPoint(label=f"High {condition_col}", value=round(high_mean, 4)),
            ChartDataPoint(label=f"Low {condition_col}", value=round(low_mean, 4)),
        ],
        color_scheme="categorical",
    )

    trace = _make_trace(q, "scenario_analysis", [condition_col, target_col], start,
                        f"Split '{condition_col}' at {threshold_word} threshold and compared '{target_col}'.")
    return QueryResult(
        query_id=q.query_id, session_id=profile.session_id,
        status=QueryStatus.success,
        result_value={"condition_col": condition_col, "target_col": target_col,
                      "threshold": round(threshold, 4), "threshold_word": threshold_word,
                      "high_group_mean": round(high_mean, 4),
                      "low_group_mean": round(low_mean, 4),
                      "difference": round(diff, 4),
                      "high_n": len(high_vals), "low_n": len(low_vals)},
        plain_summary=plain, key_takeaway=takeaway,
        chart=chart, trace=trace,
    )

def _exec_whatif_simulation(
    q: QueryObject,
    df: pd.DataFrame,
    profile: DatasetProfile,
    start: float,
    num_cols: list[str],
    match,
) -> QueryResult:
    """
    Handle "if X increases/decreases by N%" what-if simulation.
    Uses the observed linear relationship between columns to estimate the impact.
    Does NOT claim causal effects — always adds a caveats section.
    """
    direction_word = match.group(1).lower()
    pct = float(match.group(2))
    is_increase = any(w in direction_word for w in ["increase", "rise", "up", "higher"])

    # Identify condition column (mentioned near "if ... increases")
    # and target column from mapped_columns
    mapped_num = [c for c in q.mapped_columns if c in num_cols]
    condition_col = mapped_num[0] if mapped_num else (num_cols[0] if num_cols else None)
    target_col = (
        mapped_num[1] if len(mapped_num) >= 2
        else next((c for c in num_cols if c != condition_col), None)
    )

    if not condition_col or condition_col not in df.columns:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.mismatch,
            "What-if simulation needs at least one numeric column.",
            "condition_col not found", [f"Available: {', '.join(num_cols[:5])}"],
        )

    cond_s = pd.to_numeric(df[condition_col], errors="coerce").dropna()
    mean_cond = float(cond_s.mean())
    delta_cond = mean_cond * (pct / 100.0) * (1 if is_increase else -1)
    simulated_cond = mean_cond + delta_cond

    result_val: dict = {
        "condition_col": condition_col,
        "direction": "increase" if is_increase else "decrease",
        "pct_change": pct,
        "current_mean": round(mean_cond, 4),
        "simulated_mean": round(simulated_cond, 4),
    }

    chart_data = [
        ChartDataPoint(label=f"Current {condition_col}", value=round(mean_cond, 4)),
        ChartDataPoint(label=f"Simulated ({'+' if is_increase else '-'}{pct}%)", value=round(simulated_cond, 4)),
    ]

    # Revenue + cost caveat: revenue does not directly change from cost increases
    revenue_cost_caveat = ""
    if target_col and "revenue" in target_col.lower() and "cost" in condition_col.lower():
        revenue_cost_caveat = (
            " Note: Revenue does not change directly from a cost increase unless "
            "price, demand, or units sold are also adjusted. "
            "Profit and profit margin are the directly affected metrics."
        )
        target_col = next(
            (c for c in num_cols if "profit" in c.lower() and c != condition_col),
            target_col,
        )

    if target_col and target_col in df.columns:
        tgt_s = pd.to_numeric(df[target_col], errors="coerce")
        cond_s2 = pd.to_numeric(df[condition_col], errors="coerce")
        mask = cond_s2.notna() & tgt_s.notna()
        if mask.sum() >= 5:
            slope, intercept, r_val, _, _ = scipy_stats.linregress(
                cond_s2[mask].values, tgt_s[mask].values
            )
            delta_target = slope * delta_cond
            mean_target = float(tgt_s.dropna().mean())
            simulated_target = mean_target + delta_target

            result_val.update({
                "target_col": target_col,
                "current_target_mean": round(mean_target, 4),
                "simulated_target_mean": round(simulated_target, 4),
                "regression_slope": round(float(slope), 6),
                "r_value": round(float(r_val), 4),
            })
            chart_data += [
                ChartDataPoint(label=f"Current {target_col}", value=round(mean_target, 4)),
                ChartDataPoint(label=f"Simulated {target_col}", value=round(simulated_target, 4)),
            ]
            plain = (
                f"What-if simulation: if '{condition_col}' "
                f"{'increases' if is_increase else 'decreases'} by {pct}%, "
                f"it moves from {_fmt(mean_cond)} to {_fmt(simulated_cond)} (avg). "
                f"Based on the observed relationship (r = {r_val:+.3f}), "
                f"'{target_col}' would shift from {_fmt(mean_target)} to "
                f"{_fmt(simulated_target)} on average. "
                f"This is a statistical estimate — not a causal guarantee."
                + revenue_cost_caveat
            )
            takeaway = (
                f"A {pct}% {'rise' if is_increase else 'fall'} in '{condition_col}' "
                f"→ estimated change in '{target_col}': "
                f"{_fmt(mean_target)} → {_fmt(simulated_target)} "
                f"(Δ {delta_target:+.2f}, r = {r_val:+.3f})."
            )
        else:
            plain = (
                f"If '{condition_col}' {'increases' if is_increase else 'decreases'} by {pct}%, "
                f"its average value changes from {_fmt(mean_cond)} to {_fmt(simulated_cond)}. "
                f"Not enough data to estimate impact on other columns."
                + revenue_cost_caveat
            )
            takeaway = f"Simulated {condition_col}: {_fmt(mean_cond)} → {_fmt(simulated_cond)}."
    else:
        plain = (
            f"If '{condition_col}' {'increases' if is_increase else 'decreases'} by {pct}%, "
            f"its average changes from {_fmt(mean_cond)} to {_fmt(simulated_cond)}."
            + revenue_cost_caveat
        )
        takeaway = f"Simulated {condition_col}: {_fmt(mean_cond)} → {_fmt(simulated_cond)}."

    chart = ChartSpec(
        chart_type=ChartType.bar,
        title=f"What-If: {condition_col} {'↑' if is_increase else '↓'}{pct}%",
        x_field="scenario", y_field="value",
        x_axis_label="Scenario", y_axis_label="Value",
        data=chart_data, color_scheme="categorical",
    )

    cols_used = [condition_col] + ([target_col] if target_col else [])
    trace = _make_trace(q, "scenario_whatif", cols_used, start,
                        f"Simulated {pct}% {'increase' if is_increase else 'decrease'} in '{condition_col}'.")
    return QueryResult(
        query_id=q.query_id, session_id=profile.session_id,
        status=QueryStatus.success,
        result_value=result_val, plain_summary=plain, key_takeaway=takeaway,
        chart=chart, trace=trace,
    )

def _exec_open_ended_insight(
    q: QueryObject,
    df: pd.DataFrame,
    profile: DatasetProfile,
    start: float,
) -> QueryResult:
    """Iterate over sub_queries and aggregate results; fallback to key stats."""
    sub_questions = q.sub_queries or []
    aggregated: list[dict] = []

    if sub_questions:
        # Late import — no circular dependency (interpreter does not import executor)
        from app.modules.query_interpreter import interpret_query  # noqa: PLC0415
        for sub_q in sub_questions[:3]:
            try:
                sub_obj, _ = interpret_query(sub_q, profile)
                # Guard against infinite recursion — skip nested open_ended_insight
                if sub_obj and sub_obj.intent != QueryIntent.open_ended_insight:
                    sub_result = _dispatch(sub_obj, df, profile, time.time())
                    if sub_result.status == QueryStatus.success:
                        aggregated.append({
                            "question": sub_q,
                            "summary": sub_result.plain_summary,
                            "key_finding": sub_result.key_takeaway,
                        })
            except Exception:
                continue

    # Fallback: produce basic numeric summaries
    if not aggregated:
        num_cols = [c for c in profile.numeric_columns if c in df.columns][:3]
        for col in num_cols:
            s = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(s) > 0:
                aggregated.append({
                    "question": f"Describe {col}",
                    "summary": (
                        f"'{col}': mean={_fmt(float(s.mean()))}, "
                        f"median={_fmt(float(s.median()))}, std={_fmt(float(s.std()))}"
                    ),
                    "key_finding": f"'{col}' typical value: {_fmt(float(s.median()))}.",
                })

    n = len(aggregated)
    plain = (
        f"Open-ended analysis produced {n} insight(s): "
        + " | ".join(item["summary"] for item in aggregated[:3])
    ) if aggregated else "Analysis returned no results."
    takeaway = aggregated[0]["key_finding"] if aggregated else "No insights generated."

    trace = _make_trace(q, "open_ended_insight", list(df.columns[:5]), start,
                        f"Aggregated {n} sub-analyses.")
    return QueryResult(
        query_id=q.query_id, session_id=profile.session_id,
        status=QueryStatus.success,
        result_value={"n_insights": n, "insights": aggregated},
        plain_summary=plain, key_takeaway=takeaway, trace=trace,
    )

def _exec_segment_comparison(
    q: QueryObject,
    df: pd.DataFrame,
    profile: DatasetProfile,
    start: float,
) -> QueryResult:
    """Compare two named segments across multiple numeric metrics."""
    params = q.parameters
    cat_cols = [c for c in profile.categorical_columns if c in df.columns]
    num_cols = [c for c in profile.numeric_columns if c in df.columns]

    segment_col = params.get("segment_col") or (cat_cols[0] if cat_cols else None)
    metrics: list[str] = params.get("metrics") or num_cols[:3]
    metrics = [m for m in metrics if m in df.columns]

    if not segment_col or segment_col not in df.columns:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.mismatch,
            "Segment comparison needs a categorical segment column.",
            "segment_col missing", [f"Available: {', '.join(cat_cols[:5])}"],
        )
    if not metrics:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.mismatch,
            "Segment comparison needs at least one numeric metric.",
            "metrics missing", [f"Available: {', '.join(num_cols[:5])}"],
        )

    unique_vals = df[segment_col].dropna().unique().tolist()
    segment_a = params.get("segment_a") or (str(unique_vals[0]) if len(unique_vals) >= 1 else None)
    segment_b = params.get("segment_b") or (str(unique_vals[1]) if len(unique_vals) >= 2 else None)

    if not segment_a or not segment_b:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.mismatch,
            f"'{segment_col}' needs at least two distinct values for comparison.",
            f"Found {len(unique_vals)} unique values",
            ["Specify segment_a and segment_b explicitly"],
        )

    df_a = df[df[segment_col].astype(str) == str(segment_a)]
    df_b = df[df[segment_col].astype(str) == str(segment_b)]

    comparison: list[dict] = []
    for m in metrics:
        a_vals = pd.to_numeric(df_a[m], errors="coerce").dropna()
        b_vals = pd.to_numeric(df_b[m], errors="coerce").dropna()
        if len(a_vals) == 0 or len(b_vals) == 0:
            continue
        a_mean, b_mean = float(a_vals.mean()), float(b_vals.mean())
        diff = a_mean - b_mean
        pct = abs(diff) / max(abs(b_mean), 1e-9) * 100
        comparison.append({
            "metric": m,
            f"{segment_a}_mean": round(a_mean, 4),
            f"{segment_b}_mean": round(b_mean, 4),
            "difference": round(diff, 4),
            "pct_difference": round(pct, 2),
            "winner": segment_a if a_mean >= b_mean else segment_b,
        })

    if not comparison:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.data_quality,
            "Could not compare segments — metrics may have too many missing values.",
            "comparison empty", ["Check data quality"],
        )

    seg_a_key = f"{segment_a}_mean"
    seg_b_key = f"{segment_b}_mean"
    plain_parts = []
    for c in comparison[:2]:
        a_val = c.get(seg_a_key, 0.0)
        b_val = c.get(seg_b_key, 0.0)
        plain_parts.append(
            f"{c['metric']}: {c['winner']} leads ({_fmt(a_val)} vs {_fmt(b_val)})"
        )
    plain = (
        f"Comparing '{segment_a}' vs '{segment_b}' across {len(comparison)} metric(s): "
        + "; ".join(plain_parts) + "."
    )
    takeaway = (
        f"'{comparison[0]['winner']}' outperforms in '{comparison[0]['metric']}' "
        f"({comparison[0]['pct_difference']:.1f}% difference)."
    )

    trace = _make_trace(q, "segment_comparison", [segment_col] + metrics, start,
                        f"Compared segments '{segment_a}' and '{segment_b}' on {len(metrics)} metric(s).")
    return QueryResult(
        query_id=q.query_id, session_id=profile.session_id,
        status=QueryStatus.success,
        result_value={"segment_col": segment_col, "segment_a": segment_a,
                      "segment_b": segment_b, "metrics": metrics,
                      "comparison": comparison},
        plain_summary=plain, key_takeaway=takeaway, trace=trace,
    )

def _exec_threshold_analysis(
    q: QueryObject,
    df: pd.DataFrame,
    profile: DatasetProfile,
    start: float,
) -> QueryResult:
    """Filter df where col >= threshold and summarise target metric."""
    params = q.parameters
    num_cols = [c for c in profile.numeric_columns if c in df.columns]

    filter_col = params.get("filter_col")
    target_col = params.get("target_col")
    threshold_word = params.get("threshold_word", "high")

    # When Tier 1 detected the intent (parameters empty), derive from mapped_columns
    if not filter_col:
        mapped_num = [c for c in q.mapped_columns if c in num_cols]
        if mapped_num:
            raw_thr = q.raw_query.lower()
            # Extract the column term that appears immediately before the threshold operator
            # e.g. "discount is below 5%" → term="discount" → matches "discount_pct"
            pre_thresh_m = re.search(
                r"\b(\w+)\s+(?:is\s+)?(?:above|below|over|under|less\s+than|greater\s+than|"
                r"more\s+than|exceeds?|at\s+least|at\s+most)\b",
                raw_thr,
            )
            pre_thresh_term = pre_thresh_m.group(1) if pre_thresh_m else None

            def _col_condition_score(col: str) -> int:
                parts = re.split(r"[_\s]", col.lower())
                # Strong bonus if the pre-threshold term matches a column name part
                bonus = 0
                if pre_thresh_term:
                    bonus = 3 * int(any(
                        bool(re.search(r"\b" + re.escape(p) + r"\b", pre_thresh_term))
                        for p in parts if len(p) >= 3
                    ))
                word_score = sum(
                    1 for p in parts
                    if len(p) >= 3 and bool(re.search(r"\b" + re.escape(p) + r"\b", raw_thr))
                )
                return bonus + word_score

            scored = sorted(mapped_num, key=_col_condition_score, reverse=True)
            filter_col = scored[0]
            remaining = [c for c in mapped_num if c != filter_col]
            target_col = target_col or (remaining[0] if remaining else None)
        elif num_cols:
            filter_col = num_cols[0]

    # Final fallback
    if not filter_col:
        filter_col = num_cols[0] if num_cols else None
    if not target_col:
        target_col = next((c for c in num_cols if c != filter_col), None)

    if not filter_col or filter_col not in df.columns:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.mismatch,
            "Threshold analysis needs a numeric filter column.",
            "filter_col missing", [f"Available: {', '.join(num_cols[:5])}"],
        )

    filter_series = pd.to_numeric(df[filter_col], errors="coerce")

    # Prefer explicit numeric threshold from query, then word-based
    threshold = extract_numeric_threshold(q.raw_query)
    if threshold is None:
        threshold = resolve_threshold(threshold_word, filter_series)

    # Determine direction: "below/less/under/low" → <=, otherwise >=
    raw_lower = q.raw_query.lower()
    use_lower = bool(re.search(
        r"\b(below|less\s+than|under|low|unusually\s+low|suspiciously\s+low)\b",
        raw_lower,
    ))
    if use_lower:
        mask = filter_series <= threshold
        direction_label = "≤"
        direction_word = "below"
    else:
        mask = filter_series >= threshold
        direction_label = "≥"
        direction_word = "above"

    filtered = df[mask]
    n_filtered = int(mask.sum())
    pct = round(n_filtered / max(len(df), 1) * 100, 2)

    if n_filtered == 0:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.data_quality,
            f"No rows found where '{filter_col}' {direction_label} {_fmt(threshold)}.",
            "Empty filtered set",
            ["Try a different threshold"],
        )

    summary: dict = {"filter_col": filter_col, "threshold": round(threshold, 4),
                     "direction": direction_word,
                     "n_rows": n_filtered, "pct_of_data": pct}

    if target_col and target_col in filtered.columns:
        t_vals = pd.to_numeric(filtered[target_col], errors="coerce").dropna()
        if len(t_vals) > 0:
            summary["target_col"] = target_col
            summary["target_mean"] = round(float(t_vals.mean()), 4)
            summary["target_sum"] = round(float(t_vals.sum()), 4)
            summary["target_median"] = round(float(t_vals.median()), 4)

    target_desc = ""
    if "target_sum" in summary and "target_mean" in summary:
        target_desc = (
            f"In those rows, total '{target_col}' is {_fmt(summary['target_sum'])} "
            f"(average: {_fmt(summary['target_mean'])})."
        )
    plain = (
        f"{n_filtered} rows ({pct}% of data) have '{filter_col}' {direction_label} {_fmt(threshold)}. "
        + target_desc
    )
    takeaway = (
        f"{n_filtered} rows {direction_word} the {threshold_word} threshold "
        f"({_fmt(threshold)}) in '{filter_col}'."
        + (f" Total '{target_col}': {_fmt(summary.get('target_sum', 0))}." if "target_sum" in summary else "")
    )

    trace = _make_trace(q, "threshold_analysis", [filter_col] + ([target_col] if target_col else []),
                        start, f"Filtered '{filter_col}' ≥ {threshold:.4g}.")
    return QueryResult(
        query_id=q.query_id, session_id=profile.session_id,
        status=QueryStatus.success,
        result_value=summary, plain_summary=plain, key_takeaway=takeaway, trace=trace,
    )

def _exec_seasonal_pattern(
    q: QueryObject,
    df: pd.DataFrame,
    profile: DatasetProfile,
    start: float,
) -> QueryResult:
    """Decompose date column into month/weekday/quarter and find peaks."""
    import warnings

    params = q.parameters
    date_col = params.get("date_col") or (profile.datetime_columns[0] if profile.datetime_columns else None)
    target_col = params.get("target_col") or params.get("metric_col") or (
        profile.numeric_columns[0] if profile.numeric_columns else None
    )

    if not date_col or date_col not in df.columns:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.mismatch,
            "Seasonal pattern analysis needs a date column.",
            "No date column available", ["Ensure your dataset has a date column"],
        )
    if not target_col or target_col not in df.columns:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.mismatch,
            "Seasonal pattern analysis needs a numeric target column.",
            "No numeric column available", [f"Available: {', '.join(profile.numeric_columns[:5])}"],
        )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        dt_s = pd.to_datetime(df[date_col], errors="coerce")
    num_s = pd.to_numeric(df[target_col], errors="coerce")
    mask = dt_s.notna() & num_s.notna()

    if mask.sum() < 4:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.data_quality,
            "Not enough valid date+value pairs for seasonal analysis.",
            f"Only {mask.sum()} valid rows", ["Upload more data"],
        )

    temp = pd.DataFrame({
        "__month": dt_s[mask].dt.month,
        "__weekday": dt_s[mask].dt.dayofweek,
        "__quarter": dt_s[mask].dt.quarter,
        target_col: num_s[mask],
    })

    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    by_month = temp.groupby("__month")[target_col].mean()
    by_weekday = temp.groupby("__weekday")[target_col].mean()
    by_quarter = temp.groupby("__quarter")[target_col].mean()

    peak_month = int(by_month.idxmax()) if not by_month.empty else 1
    peak_weekday = int(by_weekday.idxmax()) if not by_weekday.empty else 0
    peak_quarter = int(by_quarter.idxmax()) if not by_quarter.empty else 1

    peak_month_name = month_names[peak_month - 1] if 1 <= peak_month <= 12 else str(peak_month)
    peak_day_name = day_names[peak_weekday] if 0 <= peak_weekday <= 6 else str(peak_weekday)

    month_records = [
        {"period": month_names[m - 1] if 1 <= m <= 12 else str(m), "value": round(float(v), 4)}
        for m, v in by_month.items()
    ]

    plain = (
        f"'{target_col}' peaks in {peak_month_name} (month), "
        f"on {peak_day_name}s (day of week), "
        f"and in Q{peak_quarter} (quarter)."
    )
    takeaway = (
        f"Highest average '{target_col}': {peak_month_name}, {peak_day_name}s, Q{peak_quarter}."
    )

    chart = ChartSpec(
        chart_type=ChartType.bar,
        title=f"{target_col} by Month",
        x_field="month", y_field=target_col,
        x_axis_label="Month", y_axis_label=f"Mean {target_col}",
        data=[ChartDataPoint(label=r["period"], value=r["value"]) for r in month_records],
        color_scheme="sequential",
    )

    trace = _make_trace(q, "seasonal_pattern", [date_col, target_col], start,
                        f"Decomposed '{date_col}' into month/weekday/quarter and aggregated '{target_col}'.")
    return QueryResult(
        query_id=q.query_id, session_id=profile.session_id,
        status=QueryStatus.success,
        result_value={
            "date_col": date_col, "target_col": target_col,
            "by_month": month_records,
            "by_weekday": [{"period": day_names[d] if 0 <= d <= 6 else str(d),
                            "value": round(float(v), 4)} for d, v in by_weekday.items()],
            "by_quarter": [{"period": f"Q{q_}", "value": round(float(v), 4)}
                           for q_, v in by_quarter.items()],
            "peak_month": peak_month_name,
            "peak_weekday": peak_day_name,
            "peak_quarter": f"Q{peak_quarter}",
        },
        plain_summary=plain, key_takeaway=takeaway,
        chart=chart, trace=trace,
    )

# New Tier-1 deterministic executors

def _exec_combination_ranking(
    q: QueryObject,
    df: pd.DataFrame,
    profile: DatasetProfile,
    start: float,
) -> QueryResult:
    """
    Multi-column combination ranking: group by 2+ categorical columns, aggregate
    a numeric metric, and return the top combinations.
    Handles queries like: "Which combination of product category and sales channel
    generates the highest revenue?"
    """
    cat_cols = _get_categorical_cols(q.mapped_columns, df, profile)
    num_cols = _get_numeric_cols(q.mapped_columns, df, profile)

    # Fallback to profile columns when not enough are mapped
    if len(cat_cols) < 2:
        all_cats = [c for c in profile.categorical_columns if c in df.columns]
        # Add any not already present
        for c in all_cats:
            if c not in cat_cols:
                cat_cols.append(c)
            if len(cat_cols) >= 2:
                break
    if not num_cols:
        num_cols = [c for c in profile.numeric_columns if c in df.columns]

    if len(cat_cols) < 2 or not num_cols:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.mismatch,
            "Combination ranking needs at least two categorical columns and one numeric metric. "
            f"Found categorical: {cat_cols}, numeric: {num_cols}.",
            "Insufficient columns for combination ranking",
            ["Try: 'Which product category and sales channel generates the most revenue?'"],
        )

    group_cols = cat_cols[:2]  # use the two most relevant categorical columns
    num_col = num_cols[0]

    # Guard: skip if any group column has too many categories
    for gc in group_cols:
        if df[gc].nunique() > MAX_GROUPBY_CATEGORIES:
            return _error_result(
                q.query_id, profile.session_id, ErrorType.unsupported,
                f"'{gc}' has too many unique values ({df[gc].nunique()}) for combination ranking.",
                f"Cardinality exceeds {MAX_GROUPBY_CATEGORIES}",
                [f"Try a column with fewer than {MAX_GROUPBY_CATEGORIES} categories"],
            )

    is_bottom = bool(re.search(
        r"\b(bottom|worst|lowest|least|minimum)\b", q.raw_query.lower()
    ))

    grouped = (
        df.groupby(group_cols)[num_col]
        .sum()
        .reset_index()
        .sort_values(num_col, ascending=is_bottom)
    )
    grouped["combination_label"] = grouped[group_cols[0]].astype(str) + " + " + grouped[group_cols[1]].astype(str)
    top_rows = grouped.head(TOP_N)

    top = top_rows.iloc[0]
    top_label = str(top["combination_label"])
    top_val = float(top[num_col])
    rank_word = "bottom" if is_bottom else "top"

    records = top_rows[["combination_label"] + group_cols + [num_col]].to_dict(orient="records")

    plain = (
        f"The {rank_word} combinations of {group_cols[0]} + {group_cols[1]} by total {num_col}: "
        + ", ".join(
            f"'{r['combination_label']}' ({_fmt(float(r[num_col]))})"
            for r in records
        ) + ". "
        f"'{top_label}' leads with {_fmt(top_val)} in total {num_col}."
    )
    takeaway = (
        f"Best combination: '{top_label}' — "
        f"{'lowest' if is_bottom else 'highest'} total {num_col} at {_fmt(top_val)}."
    )

    chart = ChartSpec(
        chart_type=ChartType.bar,
        title=f"Total {num_col} by {group_cols[0]} × {group_cols[1]}",
        x_field="combination_label",
        y_field=num_col,
        x_axis_label=f"{group_cols[0]} + {group_cols[1]}",
        y_axis_label=f"Total {num_col}",
        data=[
            ChartDataPoint(
                label=str(r["combination_label"]),
                value=round(float(r[num_col]), 4),
            )
            for r in records
        ],
        color_scheme="categorical",
    )

    col_meta = next((c for c in profile.columns if c.name == num_col), None)
    reliability = _check_reliability(num_col, col_meta.null_rate if col_meta else 0, len(df))
    trace = _make_trace(
        q, "combination_groupby_rank", group_cols + [num_col], start,
        f"Grouped by {group_cols} and summed '{num_col}' to find top combinations.",
    )
    follow_ups = _build_follow_ups(group_cols + [num_col], "ranking", profile)

    return QueryResult(
        query_id=q.query_id, session_id=profile.session_id,
        status=QueryStatus.success,
        result_value={"group_cols": group_cols, "num_col": num_col, "combinations": records},
        plain_summary=plain, key_takeaway=takeaway,
        chart=chart, reliability_warning=reliability,
        suggested_follow_ups=follow_ups, trace=trace,
    )

def _exec_efficiency_query(
    q: QueryObject,
    df: pd.DataFrame,
    profile: DatasetProfile,
    start: float,
) -> QueryResult:
    """
    Efficiency ranking: compute a profit-to-cost ratio (or profit margin if revenue
    is available) per categorical group, then rank groups.
    Handles queries like:
      "Which sales channel is most efficient: high profit but low cost?"
      "Which product category has the best profit margin?"
      "Which region gives the best ROI?"

    Extended: detects "how many orders with [threshold] AND [condition]" to return
    a compound-condition count instead of an efficiency ranking.
    """
    raw_lower = q.raw_query.lower()

    # ── Compound count mode: "How many orders have discount above X% but profitable?" ──
    if re.search(r"\bhow many\b", raw_lower):
        num_cols_all = [c for c in profile.numeric_columns if c in df.columns]
        # Extract numeric threshold from query
        threshold_val = extract_numeric_threshold(q.raw_query)
        # Identify the threshold column from mapped or keyword match
        mapped_num = _get_numeric_cols(q.mapped_columns, df, profile)
        threshold_col = None
        # Prefer discount/pct/rate column when "discount" or "%" in query
        for mc in (mapped_num or num_cols_all):
            if any(k in mc.lower() for k in ("discount", "pct", "rate", "percent")):
                threshold_col = mc
                break
        if threshold_col is None and mapped_num:
            threshold_col = mapped_num[0]
        if threshold_col is None and num_cols_all:
            threshold_col = num_cols_all[0]

        # Profitability condition: profit > 0 or profit_margin_pct > 0
        profit_col = next(
            (c for c in num_cols_all if "profit" in c.lower() and "margin" not in c.lower()), None
        ) or next((c for c in num_cols_all if "profit" in c.lower()), None)

        if threshold_col and threshold_val is not None:
            threshold_series = pd.to_numeric(df[threshold_col], errors="coerce")
            # Determine direction from query ("above"=>=, "below"=<=)
            use_lower = bool(re.search(r"\b(below|less\s+than|under)\b", raw_lower))
            thresh_mask = (threshold_series <= threshold_val if use_lower
                           else threshold_series >= threshold_val)

            # Apply profitability condition if "profitable" mentioned
            if re.search(r"\bprofitab", raw_lower) and profit_col:
                profit_series = pd.to_numeric(df[profit_col], errors="coerce")
                combined_mask = thresh_mask & (profit_series > 0)
            else:
                combined_mask = thresh_mask

            n_matching = int(combined_mask.sum())
            pct = round(n_matching / max(len(df), 1) * 100, 2)
            cond_desc = (
                f"'{threshold_col}' {'≤' if use_lower else '≥'} {_fmt(threshold_val)}"
                + (f" AND '{profit_col}' > 0" if profit_col and re.search(r"\bprofitab", raw_lower) else "")
            )
            plain = f"{n_matching} orders ({pct}% of data) match: {cond_desc}."
            takeaway = f"{n_matching} orders satisfy: {cond_desc}."
            trace = _make_trace(
                q, "compound_count",
                [threshold_col] + ([profit_col] if profit_col else []),
                start, f"Counted rows matching compound conditions.",
            )
            return QueryResult(
                query_id=q.query_id, session_id=profile.session_id,
                status=QueryStatus.success,
                result_value={"n_matching": n_matching, "pct": pct, "conditions": cond_desc},
                plain_summary=plain, key_takeaway=takeaway, trace=trace,
            )

    cat_cols = [c for c in profile.categorical_columns if c in df.columns]
    num_cols = [c for c in profile.numeric_columns if c in df.columns]

    # Auto-detect group column (prefer mapped categorical)
    group_col = next(
        (c for c in _get_categorical_cols(q.mapped_columns, df, profile) if c in df.columns),
        cat_cols[0] if cat_cols else None,
    )

    if not group_col:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.mismatch,
            "Efficiency ranking needs a categorical group column (e.g. sales channel, product).",
            "No categorical group column found",
            [f"Available categorical columns: {', '.join(cat_cols[:5])}"],
        )

    if df[group_col].nunique() > MAX_GROUPBY_CATEGORIES:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.unsupported,
            f"'{group_col}' has too many categories for efficiency ranking.",
            f"Cardinality {df[group_col].nunique()} exceeds {MAX_GROUPBY_CATEGORIES}",
            ["Try a column with fewer categories"],
        )

    # Resolve numerator (profit/metric) and denominator (cost/divisor) columns.
    # Priority: (1) explicitly mapped numeric columns from the query,
    #           (2) keyword heuristics on column names,
    #           (3) generic fallback — first two available numeric columns.
    # This makes the executor work for any dataset regardless of column naming.

    def _find_col_by_keywords(keywords: list[str], candidates: list[str]) -> Optional[str]:
        for k in keywords:
            for c in candidates:
                if k in c.lower():
                    return c
        return None

    mapped_nums = _get_numeric_cols(q.mapped_columns, df, profile)
    # Exclude binary columns from ratio computation
    num_cols_non_binary = [c for c in num_cols if c not in profile.binary_columns]

    profit_col: Optional[str] = None
    cost_col:   Optional[str] = None
    revenue_col: Optional[str] = None

    # Step 1 — check mapped columns first (most reliable signal)
    raw_q_lower = q.raw_query.lower()
    if len(mapped_nums) >= 2:
        # Heuristic: first mapped numeric is numerator, second is denominator.
        # Refine by keyword matching within the mapped set.
        for mc in mapped_nums:
            lower_mc = mc.lower()
            if profit_col is None and any(k in lower_mc for k in ("profit", "margin", "gain", "net")):
                profit_col = mc
            elif cost_col is None and any(k in lower_mc for k in ("cost", "expense", "spend")):
                cost_col = mc
            elif revenue_col is None and any(k in lower_mc for k in ("revenue", "sales", "income", "turnover")):
                revenue_col = mc
        # If keyword matching within mapped set found nothing, treat as generic numerator/denominator
        if profit_col is None and cost_col is None and revenue_col is None:
            profit_col = mapped_nums[0]
            cost_col   = mapped_nums[1]
    elif len(mapped_nums) == 1:
        profit_col = mapped_nums[0]

    # Step 2 — keyword heuristics across all numeric columns (fills gaps)
    if profit_col is None:
        profit_col = _find_col_by_keywords(["profit", "margin", "gain", "net_income", "net"], num_cols_non_binary)
    if cost_col is None:
        cost_col = _find_col_by_keywords(["cost", "expense", "spend", "expenditure"], num_cols_non_binary)
    if revenue_col is None:
        revenue_col = _find_col_by_keywords(["revenue", "sales", "turnover", "income"], num_cols_non_binary)

    # Step 3 — generic fallback: use first two numeric columns as numerator/denominator
    if profit_col is None and revenue_col is None:
        available = [c for c in num_cols_non_binary if c != group_col]
        if len(available) >= 2:
            profit_col = available[0]
            cost_col   = available[1]
        elif len(available) == 1:
            profit_col = available[0]

    if not profit_col and not revenue_col:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.mismatch,
            "Efficiency ranking needs at least one numeric metric column. "
            f"Numeric columns found: {', '.join(num_cols_non_binary[:6])}.",
            "No usable numeric column for efficiency computation",
            ["Specify the numerator column explicitly, e.g. 'revenue per cost'"],
        )

    # Build per-group stats
    agg_dict: dict = {profit_col: ["sum", "mean", "count"]}
    if cost_col and cost_col != profit_col:
        agg_dict[cost_col] = ["sum"]
    if revenue_col and revenue_col not in (profit_col, cost_col):
        agg_dict[revenue_col] = ["sum"]

    grouped_raw = df.groupby(group_col).agg(agg_dict).reset_index()
    grouped_raw.columns = [group_col] + [
        f"{col}_{agg}" for col, agg in grouped_raw.columns[1:]
    ]

    records: list[dict] = []
    for _, row in grouped_raw.iterrows():
        g = str(row[group_col])
        total_profit = float(row.get(f"{profit_col}_sum", 0))
        avg_profit = float(row.get(f"{profit_col}_mean", 0))
        order_count = int(row.get(f"{profit_col}_count", 0))

        efficiency: float
        efficiency_label: str

        if cost_col and f"{cost_col}_sum" in row.index:
            total_cost = float(row.get(f"{cost_col}_sum", 1))
            if total_cost > 0:
                efficiency = total_profit / total_cost
                efficiency_label = f"{profit_col} / {cost_col}"
            else:
                efficiency = 0.0
                efficiency_label = f"{profit_col} / {cost_col}"
        elif revenue_col and f"{revenue_col}_sum" in row.index:
            total_revenue = float(row.get(f"{revenue_col}_sum", 1))
            efficiency = total_profit / total_revenue if total_revenue != 0 else 0.0
            efficiency_label = f"{profit_col} margin (profit / revenue)"
        else:
            efficiency = avg_profit
            efficiency_label = f"avg {profit_col}"

        rec: dict = {
            "group": g,
            "efficiency_score": round(efficiency, 6),
            f"total_{profit_col}": round(total_profit, 4),
            f"avg_{profit_col}": round(avg_profit, 4),
            "order_count": order_count,
        }
        if cost_col and f"{cost_col}_sum" in row.index:
            rec[f"total_{cost_col}"] = round(float(row.get(f"{cost_col}_sum", 0)), 4)
        records.append(rec)

    records.sort(key=lambda x: x["efficiency_score"], reverse=True)

    if not records:
        return _error_result(
            q.query_id, profile.session_id, ErrorType.data_quality,
            "Could not compute efficiency scores — data may be empty.",
            "No records after groupby", ["Check data quality"],
        )

    top = records[0]
    top_name = top["group"]
    top_eff = top["efficiency_score"]
    top_total = top.get(f"total_{profit_col}", 0)
    top_count = top.get("order_count", 0)

    second = records[1] if len(records) > 1 else None
    volume_note = ""
    if second:
        sec_total = second.get(f"total_{profit_col}", 0)
        if sec_total > top_total * 1.2:
            volume_note = (
                f" Note: '{second['group']}' has higher total {profit_col} "
                f"({_fmt(float(sec_total))} vs {_fmt(float(top_total))}) but lower "
                f"efficiency — it may be worth considering for volume strategy."
            )

    plain = (
        f"'{top_name}' is the most efficient {group_col} "
        f"(efficiency score: {_fmt(top_eff)}, based on {efficiency_label}). "
        f"It generates {_fmt(float(top_total))} total {profit_col} across {top_count} orders. "
        f"Full efficiency ranking: "
        + ", ".join(
            f"'{r['group']}' ({_fmt(r['efficiency_score'])})" for r in records[:5]
        ) + "." + volume_note
    )
    takeaway = (
        f"Most efficient: '{top_name}' — "
        f"efficiency score {_fmt(top_eff)} ({efficiency_label})."
    )

    chart = ChartSpec(
        chart_type=ChartType.bar,
        title=f"Efficiency by {group_col}  ({efficiency_label})",
        x_field="group",
        y_field="efficiency_score",
        x_axis_label=group_col,
        y_axis_label="Efficiency Score",
        data=[
            ChartDataPoint(label=r["group"], value=round(r["efficiency_score"], 6))
            for r in records[:10]
        ],
        color_scheme="sequential",
    )

    trace = _make_trace(
        q, "efficiency_score_rank",
        [group_col, profit_col] + ([cost_col] if cost_col else []), start,
        f"Computed efficiency = {efficiency_label} per '{group_col}' group.",
    )
    follow_ups = _build_follow_ups([group_col, profit_col], "ranking", profile)

    return QueryResult(
        query_id=q.query_id, session_id=profile.session_id,
        status=QueryStatus.success,
        result_value={
            "group_col": group_col,
            "efficiency_metric": efficiency_label,
            "rankings": records,
        },
        plain_summary=plain, key_takeaway=takeaway,
        chart=chart, suggested_follow_ups=follow_ups, trace=trace,
    )

# Shared helpers

def _apply_filter(
    df: pd.DataFrame,
    q: QueryObject,
    profile: DatasetProfile,
) -> Optional[pd.DataFrame]:
    """Apply a filter condition if present. Returns None if value not found."""
    if q.filters is None:
        return df
    col = q.filters.column
    val = q.filters.value
    if col not in df.columns:
        return None
    mask = df[col].astype(str).str.lower() == str(val).lower()
    if mask.sum() == 0:
        return None
    return df[mask].copy()

_METRIC_PREF_KEYWORDS = [
    "revenue", "profit", "sales", "cost", "spend", "margin",
    "amount", "price", "income", "units", "score", "satisfaction",
    "value", "total", "quantity", "qty", "orders",
]
_AVOID_AS_FALLBACK = ["age", "_id", "index", "code", "zip", "number"]

def _pick_best_numeric_col(num_cols: list[str], raw_query: str) -> str:
    """Return the numeric column whose name parts best match the query text.

    Priority order:
      1. Column with highest word-boundary match count against the query.
      2. First column whose name contains a business-metric keyword.
      3. First column whose name does not contain a demographic/ID keyword.
      4. num_cols[0] as last resort.
    """
    if len(num_cols) == 1:
        return num_cols[0]
    raw = raw_query.lower()

    def score(col: str) -> int:
        parts = re.split(r"[_\s]", col.lower())
        return sum(
            1 for p in parts
            if len(p) >= 3 and bool(re.search(r"\b" + re.escape(p) + r"\b", raw))
        )

    scores = {c: score(c) for c in num_cols}
    best = max(scores.values())
    if best > 0:
        return max(num_cols, key=lambda c: scores[c])

    # Secondary: prefer columns with business-metric keywords
    for kw in _METRIC_PREF_KEYWORDS:
        for col in num_cols:
            if kw in col.lower():
                return col

    # Tertiary: avoid demographic/ID columns
    for avoid in _AVOID_AS_FALLBACK:
        non_avoid = [c for c in num_cols if avoid not in c.lower()]
        if non_avoid:
            return non_avoid[0]

    return num_cols[0]

def _get_numeric_cols(
    mapped: list[str],
    df: pd.DataFrame,
    profile: DatasetProfile,
) -> list[str]:
    # Prefer non-binary numeric columns as metrics; fall back to binary if nothing else
    non_binary = [
        c for c in mapped
        if c in df.columns
        and c in profile.numeric_columns
        and c not in profile.binary_columns
    ]
    if non_binary:
        return non_binary
    # Fallback: binary columns can serve as metrics (e.g. churn rate 0/1)
    return [
        c for c in mapped
        if c in df.columns
        and c in profile.numeric_columns
    ]

def _get_categorical_cols(
    mapped: list[str],
    df: pd.DataFrame,
    profile: DatasetProfile,
) -> list[str]:
    # Use real categorical columns first
    cat = [c for c in mapped if c in df.columns and c in profile.categorical_columns]
    if not cat:
        # No regular categorical in mapped — use binary columns as groupby keys (e.g. smoker=0/1)
        cat = [c for c in mapped if c in df.columns and c in profile.binary_columns]
    return cat

def _get_datetime_cols(
    mapped: list[str],
    df: pd.DataFrame,
    profile: DatasetProfile,
) -> list[str]:
    return [
        c for c in mapped
        if c in df.columns
        and c in profile.datetime_columns
    ]

def _histogram_data(series: pd.Series, bins: int = 10) -> list[ChartDataPoint]:
    try:
        counts, edges = np.histogram(series.dropna(), bins=bins)
        return [
            ChartDataPoint(
                label=f"{_fmt(float(edges[i]))} - {_fmt(float(edges[i + 1]))}",
                value=float(c),
            )
            for i, c in enumerate(counts)
        ]
    except Exception:
        return []

def _corr_label(r: float) -> str:
    a = abs(r)
    if a >= 0.8: return "very strong"
    if a >= 0.6: return "strong"
    if a >= 0.4: return "moderate"
    return "weak"

def _fmt(val: float) -> str:
    abs_val = abs(float(val))
    if abs_val == 0:
        return "0"
    if abs_val >= 1_000:
        return f"{val:,.2f}"
    elif abs_val >= 1:
        return f"{val:.2f}".rstrip("0").rstrip(".")
    elif abs_val >= 0.001:
        return f"{val:.4f}".rstrip("0").rstrip(".")
    else:
        return f"{val:.6f}".rstrip("0").rstrip(".")

def _check_reliability(
    col: str,
    null_rate: float,
    sample_size: int,
) -> Optional[ReliabilityWarning]:
    if null_rate > HIGH_MISSING_WARN:
        return ReliabilityWarning(
            warning_type=WarningType.high_missing,
            severity=Severity.high if null_rate > 0.6 else Severity.medium,
            message=(
                f"'{col}' has {null_rate:.0%} missing values. "
                "This result may not be fully representative."
            ),
            affected_columns=[col],
            suggested_action="Review or clean this column before drawing conclusions.",
        )
    if sample_size < 30:
        return ReliabilityWarning(
            warning_type=WarningType.small_sample,
            severity=Severity.medium,
            message=(
                f"This result is based on only {sample_size} data points. "
                "Interpret with care."
            ),
            affected_columns=[col],
        )
    return None

def _make_trace(
    q: QueryObject,
    operation: str,
    columns: list[str],
    start: float,
    explanation: str,
) -> TaskTrace:
    return TaskTrace(
        task_id=f"qexec_{uuid.uuid4().hex[:6]}",
        module="query_executor",
        operation=operation,
        columns_used=columns,
        trigger_reason=f"User query: '{q.raw_query[:80]}'",
        plain_explanation=explanation,
        execution_time_ms=int((time.time() - start) * 1000),
        status=TaskStatus.completed,
    )

def _build_follow_ups(
    cols: list[str],
    context: str,
    profile: DatasetProfile,
) -> list[SuggestedFollowUp]:
    follow_ups = []
    priority = 1
    cat_cols = profile.categorical_columns
    num_cols = profile.numeric_columns
    dt_cols = profile.datetime_columns

    if context == "distribution" and cat_cols:
        primary = cols[0] if cols else (num_cols[0] if num_cols else "")
        if primary:
            follow_ups.append(SuggestedFollowUp(
                followup_id=f"fu_{uuid.uuid4().hex[:6]}",
                question_text=f"Compare {primary} by {cat_cols[0]}",
                reasoning=f"Break down '{primary}' by category to find group differences.",
                pre_mapped_intent="comparison",
                pre_mapped_columns=[primary, cat_cols[0]],
                priority=priority,
            ))
            priority += 1

    if context in ("comparison", "ranking") and dt_cols:
        num = next((c for c in cols if c in num_cols), num_cols[0] if num_cols else "")
        if num:
            follow_ups.append(SuggestedFollowUp(
                followup_id=f"fu_{uuid.uuid4().hex[:6]}",
                question_text=f"Show {num} trend over time",
                reasoning="After comparing groups, see how the total changes over time.",
                pre_mapped_intent="trend",
                pre_mapped_columns=[dt_cols[0], num],
                priority=priority,
            ))
            priority += 1

    if context == "trend" and cat_cols:
        num = next((c for c in cols if c in num_cols), num_cols[0] if num_cols else "")
        if num:
            follow_ups.append(SuggestedFollowUp(
                followup_id=f"fu_{uuid.uuid4().hex[:6]}",
                question_text=f"Compare {num} by {cat_cols[0]}",
                reasoning="After seeing the trend, compare across categories.",
                pre_mapped_intent="comparison",
                pre_mapped_columns=[cat_cols[0], num],
                priority=priority,
            ))
            priority += 1

    if context == "missing_data" and num_cols:
        follow_ups.append(SuggestedFollowUp(
            followup_id=f"fu_{uuid.uuid4().hex[:6]}",
            question_text=f"Show distribution of {num_cols[0]}",
            reasoning="After checking missing data, explore the distribution of key columns.",
            pre_mapped_intent="distribution",
            pre_mapped_columns=[num_cols[0]],
            priority=priority,
        ))
        priority += 1

    if context == "feature_importance" and cat_cols:
        target = cols[0] if cols else ""
        if target:
            follow_ups.append(SuggestedFollowUp(
                followup_id=f"fu_{uuid.uuid4().hex[:6]}",
                question_text=f"Compare {target} by {cat_cols[0]}",
                reasoning="After seeing what influences the target, compare it across categories.",
                pre_mapped_intent="comparison",
                pre_mapped_columns=[cat_cols[0], target],
                priority=priority,
            ))

    if context == "aggregation" and cat_cols:
        primary = cols[0] if cols else (num_cols[0] if num_cols else "")
        if primary:
            follow_ups.append(SuggestedFollowUp(
                followup_id=f"fu_{uuid.uuid4().hex[:6]}",
                question_text=f"Compare {primary} by {cat_cols[0]}",
                reasoning="Break the total down by category for more detail.",
                pre_mapped_intent="comparison",
                pre_mapped_columns=[primary, cat_cols[0]],
                priority=priority,
            ))

    return follow_ups[:3]

def _error_result(
    query_id: str,
    session_id: str,
    error_type: ErrorType,
    message: str,
    reason: str,
    suggestions: list[str],
    interpretation: Optional[QueryInterpretationFeedback] = None,
) -> QueryResult:
    from app.models.schemas import QueryStatus
    return QueryResult(
        query_id=query_id,
        session_id=session_id,
        status=QueryStatus.error,
        interpretation=interpretation,
        error=ErrorResponse(
            error_id=str(uuid.uuid4()),
            error_type=error_type,
            message=message,
            reason=reason,
            suggestions=suggestions,
        ),
    )
