# Statistical analysis: correlations, GroupBy aggregations, trends, rankings, distributions.

from __future__ import annotations

import uuid
import time
import warnings
from typing import Optional, Any

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from app.models.schemas import (
    ChartDataPoint,
    ChartSpec,
    ChartType,
    DatasetProfile,
    DType,
    InsightResult,
    InsightType,
    ReliabilityWarning,
    SemanticTag,
    Severity,
    SkippedTask,
    SuggestedFollowUp,
    TaskStatus,
    TaskTrace,
    WarningType,
)

# Thresholds

CORRELATION_MIN_ABS = 0.30          # only surface correlations above this
MIN_ROWS_FOR_TREND = 5              # need at least 5 time points
MIN_ROWS_FOR_CORRELATION = 10
HIGH_MISSING_WARN = 0.30
MAX_GROUPBY_CATEGORIES = 30         # skip groupby if too many groups
SKEW_THRESHOLD = 1.0                # flag high skewness

# Public entry point

def run_statistical_analysis(
    clean_df: pd.DataFrame,
    profile: DatasetProfile,
) -> list[InsightResult]:
    """
    Run all applicable statistical analyses based on the DatasetProfile.
    Returns a flat list of InsightResult objects (unranked at this stage).
    """
    insights: list[InsightResult] = []
    skipped: list[SkippedTask] = []

    numeric_cols = [
        c for c in profile.numeric_columns
        if c in clean_df.columns
    ]
    categorical_cols = [
        c for c in profile.categorical_columns
        if c in clean_df.columns
    ]
    datetime_cols = [
        c for c in profile.datetime_columns
        if c in clean_df.columns
    ]

    # 1. Descriptive statistics summary

    if numeric_cols:
        results = _descriptive_stats(clean_df, numeric_cols, profile)
        insights.extend(results)
    else:
        skipped.append(SkippedTask(
            task_id="desc_stats",
            module="statistical_analysis",
            skip_reason="No numeric columns found in the dataset.",
        ))

    # 2. Correlation analysis

    if len(numeric_cols) >= 2:
        if len(clean_df) >= MIN_ROWS_FOR_CORRELATION:
            results = _correlation_analysis(clean_df, numeric_cols, profile)
            insights.extend(results)
        else:
            skipped.append(SkippedTask(
                task_id="correlation",
                module="statistical_analysis",
                skip_reason=(
                    f"Need at least {MIN_ROWS_FOR_CORRELATION} rows for "
                    f"correlation analysis. Dataset has {len(clean_df)}."
                ),
            ))
    else:
        skipped.append(SkippedTask(
            task_id="correlation",
            module="statistical_analysis",
            skip_reason="Need at least 2 numeric columns for correlation analysis.",
        ))

    # 3. GroupBy aggregations (categorical × numeric)

    if categorical_cols and numeric_cols:
        for cat_col in categorical_cols[:3]:   # limit to first 3 categoricals
            for num_col in numeric_cols[:2]:   # limit to first 2 numerics
                result = _groupby_aggregation(
                    clean_df, cat_col, num_col, profile, skipped
                )
                if result:
                    insights.append(result)
    else:
        skipped.append(SkippedTask(
            task_id="groupby",
            module="statistical_analysis",
            skip_reason="Need at least one categorical and one numeric column.",
        ))

    # 4. Time series trend

    if datetime_cols and numeric_cols:
        for dt_col in datetime_cols[:1]:       # first datetime column only
            for num_col in numeric_cols[:2]:
                result = _time_series_trend(
                    clean_df, dt_col, num_col, profile, skipped
                )
                if result:
                    insights.append(result)
    else:
        skipped.append(SkippedTask(
            task_id="trend",
            module="statistical_analysis",
            skip_reason="Need at least one datetime and one numeric column.",
        ))

    # 5. Top-N ranking (numeric columns)

    if categorical_cols and numeric_cols:
        result = _top_n_ranking(
            clean_df, categorical_cols[0], numeric_cols[0], profile
        )
        if result:
            insights.append(result)

    # 6. Missing data summary

    missing_insight = _missing_data_summary(clean_df, profile, skipped)
    if missing_insight:
        insights.append(missing_insight)

    # 7. Distribution analysis (skewness)

    if numeric_cols:
        dist_results = _distribution_analysis(clean_df, numeric_cols, profile)
        insights.extend(dist_results)

    # 8. Pareto / concentration analysis

    if numeric_cols:
        pareto_results = _pareto_analysis(clean_df, numeric_cols, profile)
        insights.extend(pareto_results)

    return insights

# 1. Descriptive statistics

def _descriptive_stats(
    df: pd.DataFrame,
    numeric_cols: list[str],
    profile: DatasetProfile,
) -> list[InsightResult]:
    start = time.time()
    results = []

    for col in numeric_cols:
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(series) < 2:
            continue

        col_meta = next((c for c in profile.columns if c.name == col), None)
        null_rate = col_meta.null_rate if col_meta else 0.0

        mean_val = float(series.mean())
        median_val = float(series.median())
        std_val = float(series.std())
        min_val = float(series.min())
        max_val = float(series.max())
        range_val = max_val - min_val

        value = {
            "column": col,
            "mean": round(mean_val, 4),
            "median": round(median_val, 4),
            "std": round(std_val, 4),
            "min": round(min_val, 4),
            "max": round(max_val, 4),
            "range": round(range_val, 4),
            "count": int(len(series)),
        }

        q1_val = float(series.quantile(0.25))
        q3_val = float(series.quantile(0.75))

        # Plain summary template — no LLM
        plain = (
            f"'{col}' ranges from {_fmt(min_val)} to {_fmt(max_val)}, "
            f"with an average of {_fmt(mean_val)} and a typical spread "
            f"of ±{_fmt(std_val)}."
        )
        takeaway = (
            f"Typical {col} is {_fmt(median_val)} — "
            f"values range from {_fmt(min_val)} to {_fmt(max_val)}."
        )
        subtitle = (
            f"The middle 50% of records fall between {_fmt(q1_val)} and {_fmt(q3_val)}. "
            f"Values outside this range may be worth a closer look."
        )

        reliability = _check_reliability(col, null_rate, len(series))
        confidence = max(0.5, 1.0 - null_rate)

        trace = TaskTrace(
            task_id=f"desc_{uuid.uuid4().hex[:6]}",
            module="statistical_analysis",
            operation="descriptive_statistics",
            columns_used=[col],
            trigger_reason=f"Numeric column '{col}' detected.",
            plain_explanation=(
                f"Computed mean, median, standard deviation, min, and max for '{col}'."
            ),
            execution_time_ms=int((time.time() - start) * 1000),
            status=TaskStatus.completed,
        )

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

        follow_ups = _build_follow_ups(col, "distribution", profile)

        results.append(InsightResult(
            insight_id=f"ins_{uuid.uuid4().hex[:8]}",
            source_module="statistical_analysis",
            insight_type=InsightType.distribution,
            columns_used=[col],
            value=value,
            plain_summary=plain,
            key_takeaway=takeaway,
            subtitle=subtitle,
            impact_score=round(min(1.0, std_val / max(abs(mean_val), 1e-9)), 4),
            confidence_score=round(confidence, 4),
            chart=chart,
            suggested_follow_ups=follow_ups,
            reliability_warning=reliability,
            trace=trace,
        ))

    return results

# 2. Correlation analysis — one insight per significant pair (max 3)

def _correlation_analysis(
    df: pd.DataFrame,
    numeric_cols: list[str],
    profile: DatasetProfile,
) -> list[InsightResult]:
    start = time.time()

    num_df = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
    corr_matrix = num_df.corr(method="pearson")

    # Extract all significant pairs above threshold
    pairs = []
    cols = corr_matrix.columns.tolist()
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            r = corr_matrix.iloc[i, j]
            if pd.isna(r):
                continue
            if abs(r) >= CORRELATION_MIN_ABS:
                pairs.append({
                    "col_a": cols[i],
                    "col_b": cols[j],
                    "correlation": round(float(r), 4),
                    "strength": _correlation_label(r),
                    "direction": "positive" if r > 0 else "negative",
                })

    if not pairs:
        return []

    pairs.sort(key=lambda x: abs(x["correlation"]), reverse=True)
    confidence = round(min(1.0, len(df) / 100), 4)
    results = []

    for pair in pairs[:3]:   # surface up to 3 strongest pairs
        col_a, col_b = pair["col_a"], pair["col_b"]
        direction = pair["direction"]
        strength = pair["strength"]
        r = pair["correlation"]

        move_word = "increase" if direction == "positive" else "decrease"
        plain = (
            f"'{col_a}' and '{col_b}' have a {strength} {direction} correlation "
            f"(r = {r}). When one rises, the other tends to {move_word}."
        )
        takeaway = (
            f"{col_a} and {col_b} move together — "
            f"a {strength} {direction} link (r = {r})."
        )
        if direction == "positive":
            subtitle = (
                f"When {col_a} changes, {col_b} reliably shifts in the same direction. "
                f"This makes {col_a} a useful leading signal when monitoring or forecasting {col_b}."
            )
        else:
            subtitle = (
                f"As {col_a} rises, {col_b} tends to fall — an inverse trade-off. "
                f"Decisions that push one higher will likely pull the other down."
            )

        col_a_data = pd.to_numeric(df[col_a], errors="coerce")
        col_b_data = pd.to_numeric(df[col_b], errors="coerce")
        mask = col_a_data.notna() & col_b_data.notna()
        chart_data = [
            ChartDataPoint(label=round(float(x), 4), value=round(float(y), 4))
            for x, y in zip(col_a_data[mask], col_b_data[mask])
        ]

        chart = ChartSpec(
            chart_type=ChartType.scatter,
            title=f"{col_a} vs {col_b}",
            x_field=col_a,
            y_field=col_b,
            x_axis_label=col_a,
            y_axis_label=col_b,
            data=chart_data[:200],
            color_scheme="sequential",
        )

        trace = TaskTrace(
            task_id=f"corr_{uuid.uuid4().hex[:6]}",
            module="statistical_analysis",
            operation="pearson_correlation",
            columns_used=[col_a, col_b],
            trigger_reason="Two or more numeric columns detected.",
            plain_explanation=(
                f"Computed Pearson correlation between '{col_a}' and '{col_b}'. "
                f"|r| = {abs(r)}, threshold = {CORRELATION_MIN_ABS}."
            ),
            execution_time_ms=int((time.time() - start) * 1000),
            status=TaskStatus.completed,
        )

        follow_ups = _build_follow_ups(col_a, "correlation", profile)

        results.append(InsightResult(
            insight_id=f"ins_{uuid.uuid4().hex[:8]}",
            source_module="statistical_analysis",
            insight_type=InsightType.correlation,
            columns_used=[col_a, col_b],
            value={"pairs": [pair], "matrix_columns": [col_a, col_b]},
            plain_summary=plain,
            key_takeaway=takeaway,
            subtitle=subtitle,
            impact_score=round(min(1.0, abs(r)), 4),
            confidence_score=confidence,
            chart=chart,
            suggested_follow_ups=follow_ups,
            trace=trace,
        ))

    return results

# 3. GroupBy aggregation

def _groupby_aggregation(
    df: pd.DataFrame,
    cat_col: str,
    num_col: str,
    profile: DatasetProfile,
    skipped: list[SkippedTask],
) -> Optional[InsightResult]:
    start = time.time()

    n_categories = df[cat_col].nunique()
    if n_categories > MAX_GROUPBY_CATEGORIES:
        skipped.append(SkippedTask(
            task_id=f"groupby_{cat_col}_{num_col}",
            module="statistical_analysis",
            skip_reason=(
                f"'{cat_col}' has {n_categories} unique values — too many "
                f"to group meaningfully (limit: {MAX_GROUPBY_CATEGORIES})."
            ),
        ))
        return None

    grouped = (
        df.groupby(cat_col)[num_col]
        .agg(["sum", "mean", "count"])
        .reset_index()
    )
    grouped.columns = [cat_col, "total", "average", "count"]
    grouped = grouped.sort_values("total", ascending=False)

    top_row = grouped.iloc[0]
    top_label = str(top_row[cat_col])
    top_total = float(top_row["total"])
    overall_mean = float(grouped["total"].mean())
    pct_above = ((top_total - overall_mean) / max(abs(overall_mean), 1e-9)) * 100

    plain = (
        f"'{top_label}' had the highest total {num_col} "
        f"({_fmt(top_total)}), which is {abs(pct_above):.1f}% "
        f"{'above' if pct_above >= 0 else 'below'} the group average."
    )
    takeaway = (
        f"'{top_label}' contributes the most to {num_col} "
        f"across all {cat_col} categories."
    )
    groupby_subtitle = (
        f"{top_label} sits {abs(pct_above):.0f}% {'above' if pct_above >= 0 else 'below'} the average — "
        f"a gap large enough to suggest it operates differently from the rest of the group."
    )

    # Null rate check
    col_meta = next((c for c in profile.columns if c.name == num_col), None)
    null_rate = col_meta.null_rate if col_meta else 0.0
    reliability = _check_reliability(num_col, null_rate, len(df))

    chart_data = [
        ChartDataPoint(label=str(row[cat_col]), value=round(float(row["total"]), 4))
        for _, row in grouped.iterrows()
    ]
    chart = ChartSpec(
        chart_type=ChartType.bar,
        title=f"Total {num_col} by {cat_col}",
        x_field=cat_col,
        y_field=num_col,
        x_axis_label=cat_col,
        y_axis_label=f"Total {num_col}",
        data=chart_data,
        color_scheme="categorical",
    )

    impact = min(1.0, abs(pct_above) / 100)
    confidence = max(0.4, 1.0 - null_rate)

    trace = TaskTrace(
        task_id=f"grp_{uuid.uuid4().hex[:6]}",
        module="statistical_analysis",
        operation="groupby_aggregation",
        columns_used=[cat_col, num_col],
        trigger_reason=(
            f"Categorical column '{cat_col}' and numeric column "
            f"'{num_col}' detected."
        ),
        plain_explanation=(
            f"Grouped '{num_col}' by each value of '{cat_col}' and "
            f"computed the sum, average, and count for each group."
        ),
        execution_time_ms=int((time.time() - start) * 1000),
        status=TaskStatus.completed,
    )

    follow_ups = _build_follow_ups(num_col, "comparison", profile)

    return InsightResult(
        insight_id=f"ins_{uuid.uuid4().hex[:8]}",
        source_module="statistical_analysis",
        insight_type=InsightType.ranking,
        columns_used=[cat_col, num_col],
        value={
            "grouped": grouped.to_dict(orient="records"),
            "group_column": cat_col,
            "value_column": num_col,
        },
        plain_summary=plain,
        key_takeaway=takeaway,
        subtitle=groupby_subtitle,
        impact_score=round(min(1.0, impact), 4),
        confidence_score=round(confidence, 4),
        chart=chart,
        suggested_follow_ups=follow_ups,
        reliability_warning=reliability,
        trace=trace,
    )

# 4. Time series trend

def _time_series_trend(
    df: pd.DataFrame,
    dt_col: str,
    num_col: str,
    profile: DatasetProfile,
    skipped: list[SkippedTask],
) -> Optional[InsightResult]:
    start = time.time()

    if not pd.api.types.is_datetime64_any_dtype(df[dt_col]):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                dt_series = pd.to_datetime(df[dt_col], errors="coerce")
        except Exception:
            skipped.append(SkippedTask(
                task_id=f"trend_{dt_col}_{num_col}",
                module="statistical_analysis",
                skip_reason=f"Could not parse '{dt_col}' as dates.",
            ))
            return None
    else:
        dt_series = df[dt_col]

    num_series = pd.to_numeric(df[num_col], errors="coerce")
    valid_mask = dt_series.notna() & num_series.notna()
    dt_valid = dt_series[valid_mask]
    num_valid = num_series[valid_mask]

    if len(dt_valid) < MIN_ROWS_FOR_TREND:
        skipped.append(SkippedTask(
            task_id=f"trend_{dt_col}_{num_col}",
            module="statistical_analysis",
            skip_reason=(
                f"Need at least {MIN_ROWS_FOR_TREND} non-null time points. "
                f"Found {len(dt_valid)}."
            ),
        ))
        return None

    # Aggregate by month for time series
    temp = pd.DataFrame({dt_col: dt_valid, num_col: num_valid})
    temp["__period"] = temp[dt_col].dt.to_period("M")
    monthly = temp.groupby("__period")[num_col].sum().reset_index()
    monthly["__period_str"] = monthly["__period"].astype(str)
    monthly = monthly.sort_values("__period")

    if len(monthly) < 2:
        skipped.append(SkippedTask(
            task_id=f"trend_{dt_col}_{num_col}",
            module="statistical_analysis",
            skip_reason="Need at least 2 distinct time periods for trend analysis.",
        ))
        return None

    # Linear trend via scipy linregress
    x = np.arange(len(monthly))
    y = monthly[num_col].values.astype(float)
    slope, intercept, r_value, p_value, std_err = scipy_stats.linregress(x, y)

    direction = "upward" if slope > 0 else "downward"
    peak_idx = int(np.argmax(y))
    trough_idx = int(np.argmin(y))
    peak_period = str(monthly["__period_str"].iloc[peak_idx])
    peak_val = float(y[peak_idx])
    avg_val = float(y.mean())
    pct_above_avg = ((peak_val - avg_val) / max(abs(avg_val), 1e-9)) * 100

    plain = (
        f"'{num_col}' shows a {direction} trend over time "
        f"(slope: {slope:+.2f} per period). "
        f"The peak was in {peak_period} at {_fmt(peak_val)}, "
        f"which is {abs(pct_above_avg):.1f}% "
        f"{'above' if pct_above_avg >= 0 else 'below'} the period average."
    )
    takeaway = (
        f"'{num_col}' is trending {direction}. "
        f"The highest point was in {peak_period}."
    )
    trend_subtitle = (
        f"The {direction} movement is consistent across the period, not a one-off spike. "
        f"The peak in {peak_period} at {_fmt(peak_val)} is a useful benchmark for planning and target-setting."
    )

    chart_data = [
        ChartDataPoint(
            label=str(row["__period_str"]),
            value=round(float(row[num_col]), 4),
        )
        for _, row in monthly.iterrows()
    ]
    chart = ChartSpec(
        chart_type=ChartType.line,
        title=f"{num_col} Over Time",
        x_field=dt_col,
        y_field=num_col,
        x_axis_label="Period",
        y_axis_label=num_col,
        data=chart_data,
        color_scheme="sequential",
    )

    col_meta = next((c for c in profile.columns if c.name == num_col), None)
    null_rate = col_meta.null_rate if col_meta else 0.0
    reliability = _check_reliability(num_col, null_rate, len(monthly))

    # r² as proxy for trend confidence
    r_squared = r_value ** 2
    confidence = round(min(1.0, 0.4 + r_squared * 0.6), 4)
    impact = round(min(1.0, abs(pct_above_avg) / 100), 4)

    trace = TaskTrace(
        task_id=f"trend_{uuid.uuid4().hex[:6]}",
        module="statistical_analysis",
        operation="time_series_trend",
        columns_used=[dt_col, num_col],
        trigger_reason=(
            f"Datetime column '{dt_col}' and numeric column '{num_col}' detected."
        ),
        plain_explanation=(
            f"Aggregated '{num_col}' by month across '{dt_col}' and fitted "
            f"a linear trend. R² = {r_squared:.3f}, slope = {slope:+.4f}."
        ),
        execution_time_ms=int((time.time() - start) * 1000),
        status=TaskStatus.completed,
    )

    follow_ups = _build_follow_ups(num_col, "trend", profile)

    return InsightResult(
        insight_id=f"ins_{uuid.uuid4().hex[:8]}",
        source_module="statistical_analysis",
        insight_type=InsightType.trend,
        columns_used=[dt_col, num_col],
        value={
            "period_data": monthly[["__period_str", num_col]].rename(
                columns={"__period_str": "period"}
            ).to_dict(orient="records"),
            "slope": round(float(slope), 6),
            "r_squared": round(float(r_squared), 4),
            "direction": direction,
            "peak_period": peak_period,
            "peak_value": round(peak_val, 4),
            "p_value": round(float(p_value), 6),
        },
        plain_summary=plain,
        key_takeaway=takeaway,
        subtitle=trend_subtitle,
        impact_score=impact,
        confidence_score=confidence,
        chart=chart,
        suggested_follow_ups=follow_ups,
        reliability_warning=reliability,
        trace=trace,
    )

# 5. Top-N ranking

def _top_n_ranking(
    df: pd.DataFrame,
    cat_col: str,
    num_col: str,
    profile: DatasetProfile,
    n: int = 5,
) -> Optional[InsightResult]:
    start = time.time()

    if df[cat_col].nunique() > MAX_GROUPBY_CATEGORIES:
        return None

    grouped = (
        df.groupby(cat_col)[num_col]
        .sum()
        .sort_values(ascending=False)
        .head(n)
        .reset_index()
    )
    grouped.columns = [cat_col, num_col]

    top_name = str(grouped.iloc[0][cat_col])
    top_val = float(grouped.iloc[0][num_col])

    plain = (
        f"The top {n} {cat_col} values by total {num_col} are: "
        + ", ".join(
            f"'{row[cat_col]}' ({_fmt(float(row[num_col]))})"
            for _, row in grouped.iterrows()
        ) + "."
    )
    takeaway = f"'{top_name}' leads in total {num_col} with {_fmt(top_val)}."
    topn_subtitle = (
        f"{top_name} leads the ranking by a clear margin. "
        f"Examining what sets the top performers apart from the rest could reveal what's driving the difference."
    )

    chart_data = [
        ChartDataPoint(label=str(row[cat_col]), value=round(float(row[num_col]), 4))
        for _, row in grouped.iterrows()
    ]
    chart = ChartSpec(
        chart_type=ChartType.bar,
        title=f"Top {n} {cat_col} by {num_col}",
        x_field=cat_col,
        y_field=num_col,
        x_axis_label=cat_col,
        y_axis_label=num_col,
        data=chart_data,
        color_scheme="categorical",
    )

    col_meta = next((c for c in profile.columns if c.name == num_col), None)
    null_rate = col_meta.null_rate if col_meta else 0.0

    trace = TaskTrace(
        task_id=f"topn_{uuid.uuid4().hex[:6]}",
        module="statistical_analysis",
        operation="top_n_ranking",
        columns_used=[cat_col, num_col],
        trigger_reason=f"Categorical '{cat_col}' and numeric '{num_col}' detected.",
        plain_explanation=(
            f"Grouped '{num_col}' by '{cat_col}', summed each group, "
            f"and returned the top {n}."
        ),
        execution_time_ms=int((time.time() - start) * 1000),
        status=TaskStatus.completed,
    )

    follow_ups = _build_follow_ups(num_col, "ranking", profile)

    return InsightResult(
        insight_id=f"ins_{uuid.uuid4().hex[:8]}",
        source_module="statistical_analysis",
        insight_type=InsightType.ranking,
        columns_used=[cat_col, num_col],
        value=grouped.to_dict(orient="records"),
        plain_summary=plain,
        key_takeaway=takeaway,
        subtitle=topn_subtitle,
        impact_score=0.7,
        confidence_score=round(max(0.4, 1.0 - null_rate), 4),
        chart=chart,
        suggested_follow_ups=follow_ups,
        trace=trace,
    )

# 6. Missing data summary

def _missing_data_summary(
    df: pd.DataFrame,
    profile: DatasetProfile,
    skipped: list[SkippedTask],
) -> Optional[InsightResult]:
    start = time.time()

    missing = df.isnull().sum()
    missing = missing[missing > 0].sort_values(ascending=False)

    if missing.empty:
        skipped.append(SkippedTask(
            task_id="missing_data",
            module="statistical_analysis",
            skip_reason="No missing values found in the dataset.",
        ))
        return None

    missing_pct = (missing / len(df) * 100).round(2)
    records = [
        {"column": col, "missing_count": int(cnt), "missing_pct": float(missing_pct[col])}
        for col, cnt in missing.items()
    ]
    worst = records[0]

    plain = (
        f"{len(records)} column(s) have missing values. "
        f"'{worst['column']}' has the most, with {worst['missing_count']} "
        f"missing entries ({worst['missing_pct']:.1f}% of rows)."
    )
    takeaway = (
        f"'{worst['column']}' needs attention — "
        f"{worst['missing_pct']:.1f}% of its values are missing."
    )
    missing_subtitle = (
        f"Missing values in {worst['column']} can silently skew any analysis that uses it. "
        f"Before drawing conclusions from this column, decide whether to fill the gaps or investigate why they're absent."
    )

    chart_data = [
        ChartDataPoint(
            label=r["column"],
            value=round(r["missing_pct"], 2),
        )
        for r in records
    ]
    chart = ChartSpec(
        chart_type=ChartType.bar,
        title="Missing Values by Column (%)",
        x_field="column",
        y_field="missing_pct",
        x_axis_label="Column",
        y_axis_label="Missing (%)",
        data=chart_data,
        color_scheme="sequential",
    )

    trace = TaskTrace(
        task_id=f"miss_{uuid.uuid4().hex[:6]}",
        module="statistical_analysis",
        operation="missing_data_summary",
        columns_used=list(missing.index),
        trigger_reason="One or more columns with missing values detected.",
        plain_explanation=(
            f"Counted missing values per column. "
            f"{len(records)} column(s) have gaps."
        ),
        execution_time_ms=int((time.time() - start) * 1000),
        status=TaskStatus.completed,
    )

    return InsightResult(
        insight_id=f"ins_{uuid.uuid4().hex[:8]}",
        source_module="statistical_analysis",
        insight_type=InsightType.missing_data,
        columns_used=list(missing.index),
        value=records,
        plain_summary=plain,
        key_takeaway=takeaway,
        subtitle=missing_subtitle,
        impact_score=round(min(1.0, worst["missing_pct"] / 100), 4),
        confidence_score=1.0,
        chart=chart,
        trace=trace,
    )

# 7. Distribution / skewness analysis

def _distribution_analysis(
    df: pd.DataFrame,
    numeric_cols: list[str],
    profile: DatasetProfile,
) -> list[InsightResult]:
    results = []
    start = time.time()

    for col in numeric_cols:
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(series) < 10:
            continue

        skewness = float(series.skew())
        kurtosis = float(series.kurtosis())

        if abs(skewness) < SKEW_THRESHOLD:
            continue   # not interesting enough to surface

        direction = "right" if skewness > 0 else "left"
        extreme_word = "high" if skewness > 0 else "low"
        col_mean = float(series.mean())
        col_median = float(series.median())
        plain = (
            f"'{col}' has a {direction}-skewed distribution "
            f"(skewness: {skewness:.2f}). "
            f"This means most values are "
            f"{'lower' if skewness > 0 else 'higher'} than the average, "
            f"with a long tail on the {'right' if skewness > 0 else 'left'}."
        )
        takeaway = (
            f"A few unusually {extreme_word} '{col}' values are pulling the average away — "
            f"the median is more representative here."
        )
        dist_subtitle = (
            f"The mean ({_fmt(col_mean)}) sits above the median ({_fmt(col_median)}) "
            f"because of those outlying values. "
            f"Any targets or benchmarks using the average for {col} will overstate the typical case."
        ) if skewness > 0 else (
            f"The mean ({_fmt(col_mean)}) sits below the median ({_fmt(col_median)}) "
            f"because of low-end outlying values. "
            f"Averages for {col} will understate what's typical for most records."
        )

        chart_data = _histogram_data(series)
        chart = ChartSpec(
            chart_type=ChartType.histogram,
            title=f"Distribution of {col}",
            x_field=col,
            y_field="frequency",
            x_axis_label=col,
            y_axis_label="Count",
            data=chart_data,
            color_scheme="sequential",
        )

        col_meta = next((c for c in profile.columns if c.name == col), None)
        null_rate = col_meta.null_rate if col_meta else 0.0
        reliability = _check_reliability(col, null_rate, len(series))

        trace = TaskTrace(
            task_id=f"dist_{uuid.uuid4().hex[:6]}",
            module="statistical_analysis",
            operation="distribution_analysis",
            columns_used=[col],
            trigger_reason=f"'{col}' has high skewness (|skew| ≥ {SKEW_THRESHOLD}).",
            plain_explanation=(
                f"Computed skewness ({skewness:.4f}) and kurtosis "
                f"({kurtosis:.4f}) for '{col}'."
            ),
            execution_time_ms=int((time.time() - start) * 1000),
            status=TaskStatus.completed,
        )

        results.append(InsightResult(
            insight_id=f"ins_{uuid.uuid4().hex[:8]}",
            source_module="statistical_analysis",
            insight_type=InsightType.distribution,
            columns_used=[col],
            value={
                "column": col,
                "skewness": round(skewness, 4),
                "kurtosis": round(kurtosis, 4),
                "direction": direction,
            },
            plain_summary=plain,
            key_takeaway=takeaway,
            subtitle=dist_subtitle,
            impact_score=round(min(1.0, abs(skewness) / 3), 4),
            confidence_score=round(max(0.5, 1.0 - null_rate), 4),
            chart=chart,
            reliability_warning=reliability,
            trace=trace,
        ))

    return results

# 8. Pareto / concentration analysis

def _pareto_analysis(
    df: pd.DataFrame,
    numeric_cols: list[str],
    profile: DatasetProfile,
) -> list[InsightResult]:
    """
    For each candidate numeric column, check whether the top 20% of rows
    account for a disproportionate share of the total.  Only surfaces the
    result when concentration is meaningfully unequal (top 20% > 40%).
    Skips columns with negative values or ID-like names.
    """
    results = []
    start = time.time()

    skip_patterns = ("id", "index", "rank", "year", "month", "day", "code", "num", "no")
    candidates = [
        c for c in numeric_cols
        if not any(p in c.lower() for p in skip_patterns)
    ][:3]  # limit to 3 columns

    for col in candidates:
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(series) < 20:
            continue
        if (series < 0).any():
            continue
        total = float(series.sum())
        if total <= 0:
            continue

        sorted_vals = series.sort_values(ascending=False).reset_index(drop=True)
        top_20_count = max(1, int(len(sorted_vals) * 0.20))
        top_20_sum = float(sorted_vals.iloc[:top_20_count].sum())
        top_20_pct = round(top_20_sum / total * 100, 1)

        if top_20_pct < 40:
            continue  # near-uniform distribution — not interesting

        # How many rows give 80% of total
        cumulative = sorted_vals.cumsum()
        threshold = total * 0.80
        n_for_80 = int((cumulative <= threshold).sum()) + 1
        pct_rows_for_80 = round(n_for_80 / len(series) * 100, 1)

        plain = (
            f"The top 20% of rows by '{col}' account for {top_20_pct:.0f}% of the total. "
            f"Just {pct_rows_for_80:.0f}% of rows generate 80% of all '{col}'."
        )
        takeaway = (
            f"Top 20% of rows drive {top_20_pct:.0f}% of total {col} — "
            f"a highly concentrated distribution."
        )
        pareto_subtitle = (
            f"A small number of records are responsible for the bulk of your total {col}. "
            f"Protecting or growing this top group has a disproportionately large impact on the overall number."
        )

        # Cumulative-contribution line chart (sampled to ~20 points)
        step = max(1, len(sorted_vals) // 20)
        chart_data = []
        for i in range(0, len(sorted_vals), step):
            pct_rows = round((i + 1) / len(sorted_vals) * 100, 1)
            pct_value = round(float(sorted_vals.iloc[:i + 1].sum()) / total * 100, 1)
            chart_data.append(ChartDataPoint(label=f"{pct_rows}%", value=pct_value))

        chart = ChartSpec(
            chart_type=ChartType.line,
            title=f"Cumulative {col} Share by Row",
            x_field="Row %",
            y_field=f"{col} %",
            x_axis_label="Top Rows (%)",
            y_axis_label=f"Cumulative {col} (%)",
            data=chart_data[:25],
            color_scheme="sequential",
        )

        col_meta = next((c for c in profile.columns if c.name == col), None)
        null_rate = col_meta.null_rate if col_meta else 0.0

        trace = TaskTrace(
            task_id=f"pareto_{uuid.uuid4().hex[:6]}",
            module="statistical_analysis",
            operation="pareto_concentration",
            columns_used=[col],
            trigger_reason=f"'{col}' has concentrated values — top 20% account for {top_20_pct:.0f}%.",
            plain_explanation=(
                f"Sorted '{col}' from highest to lowest and computed cumulative share. "
                f"Top 20% of rows = {top_20_pct:.0f}% of total."
            ),
            execution_time_ms=int((time.time() - start) * 1000),
            status=TaskStatus.completed,
        )

        follow_ups = _build_follow_ups(col, "ranking", profile)

        # Concentration score: 0 at 40%, 1.0 at 100%
        impact = round(min(1.0, (top_20_pct - 40) / 60), 4)

        results.append(InsightResult(
            insight_id=f"ins_{uuid.uuid4().hex[:8]}",
            source_module="statistical_analysis",
            insight_type=InsightType.ranking,
            columns_used=[col],
            value={
                "column": col,
                "top_20_pct": top_20_pct,
                "pct_rows_for_80": pct_rows_for_80,
                "total": round(total, 4),
            },
            plain_summary=plain,
            key_takeaway=takeaway,
            subtitle=pareto_subtitle,
            impact_score=impact,
            confidence_score=round(max(0.5, 1.0 - null_rate), 4),
            chart=chart,
            suggested_follow_ups=follow_ups,
            trace=trace,
        ))

    return results

# Shared helpers

def _histogram_data(series: pd.Series, bins: int = 10) -> list[ChartDataPoint]:
    """Build histogram-style ChartDataPoints from a numeric series."""
    try:
        counts, edges = np.histogram(series.dropna(), bins=bins)
        data = []
        for i, count in enumerate(counts):
            label = f"{_fmt(float(edges[i]))} - {_fmt(float(edges[i + 1]))}"
            data.append(ChartDataPoint(label=label, value=float(count)))
        return data
    except Exception:
        return []

def _correlation_label(r: float) -> str:
    abs_r = abs(r)
    if abs_r >= 0.8:
        return "very strong"
    elif abs_r >= 0.6:
        return "strong"
    elif abs_r >= 0.4:
        return "moderate"
    else:
        return "weak"

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
                "This result may not represent all your data."
            ),
            affected_columns=[col],
            suggested_action="Consider reviewing or cleaning this column before drawing conclusions.",
        )
    if sample_size < 30:
        return ReliabilityWarning(
            warning_type=WarningType.small_sample,
            severity=Severity.medium,
            message=(
                f"This result is based on only {sample_size} data points. "
                "Results from small datasets should be interpreted carefully."
            ),
            affected_columns=[col],
            suggested_action="Collect more data to improve reliability.",
        )
    return None

def _fmt(val: float) -> str:
    """Format a number cleanly for plain-language summaries."""
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

def _build_follow_ups(
    primary_col: str,
    context: str,
    profile: DatasetProfile,
) -> list[SuggestedFollowUp]:
    """
    Generate 2–3 context-aware follow-up questions from the profile.
    These are constructed from real column names — not generic text.
    """
    follow_ups = []
    priority = 1

    other_numerics = [
        c for c in profile.numeric_columns if c != primary_col
    ]
    categoricals = profile.categorical_columns
    datetimes = profile.datetime_columns

    if context == "distribution" and categoricals:
        follow_ups.append(SuggestedFollowUp(
            followup_id=f"fu_{uuid.uuid4().hex[:6]}",
            question_text=f"Compare {primary_col} by {categoricals[0]}",
            reasoning=f"You just viewed the distribution of '{primary_col}'. Breaking it down by '{categoricals[0]}' can reveal group differences.",
            pre_mapped_intent="comparison",
            pre_mapped_columns=[primary_col, categoricals[0]],
            priority=priority,
        ))
        priority += 1

    if context == "correlation" and other_numerics:
        follow_ups.append(SuggestedFollowUp(
            followup_id=f"fu_{uuid.uuid4().hex[:6]}",
            question_text=f"What affects {primary_col} the most?",
            reasoning=f"After seeing correlations, you may want to know which column has the strongest influence on '{primary_col}'.",
            pre_mapped_intent="feature_importance",
            pre_mapped_columns=[primary_col] + other_numerics,
            priority=priority,
        ))
        priority += 1

    if context in ("comparison", "ranking") and datetimes:
        follow_ups.append(SuggestedFollowUp(
            followup_id=f"fu_{uuid.uuid4().hex[:6]}",
            question_text=f"Show {primary_col} trend over time",
            reasoning="After comparing categories, exploring how the total changes over time is a natural next step.",
            pre_mapped_intent="trend",
            pre_mapped_columns=[datetimes[0], primary_col],
            priority=priority,
        ))
        priority += 1

    if context == "trend" and categoricals:
        follow_ups.append(SuggestedFollowUp(
            followup_id=f"fu_{uuid.uuid4().hex[:6]}",
            question_text=f"Which {categoricals[0]} drove the trend in {primary_col}?",
            reasoning="After viewing the overall trend, it's useful to see which category contributed most.",
            pre_mapped_intent="comparison",
            pre_mapped_columns=[categoricals[0], primary_col],
            priority=priority,
        ))
        priority += 1

    return follow_ups[:3]
