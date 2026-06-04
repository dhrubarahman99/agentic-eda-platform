# ML module: Random Forest, K-Means clustering, Isolation Forest anomaly detection, and forecasting.

from __future__ import annotations

import time
import uuid
import warnings
from typing import Optional

import numpy as np
import pandas as pd

from app.models.schemas import (
    ChartDataPoint,
    ChartSpec,
    ChartType,
    DatasetProfile,
    InsightResult,
    InsightType,
    ReliabilityWarning,
    Severity,
    SkippedTask,
    SuggestedFollowUp,
    TaskStatus,
    TaskTrace,
    WarningType,
)

# Thresholds

MIN_ROWS_REGRESSION = 30
MIN_ROWS_CLUSTERING = 30
MIN_ROWS_ANOMALY = 50
MIN_ROWS_FORECAST = 12       # minimum distinct time periods
MIN_NUMERIC_CLUSTERING = 2
MAX_CLUSTERS = 6
FORECAST_PERIODS = 3
RF_N_ESTIMATORS = 100
RF_RANDOM_STATE = 42
KMEANS_RANDOM_STATE = 42
ISO_CONTAMINATION = 0.05     # 5% assumed anomaly rate
HIGH_MISSING_WARN = 0.30

# Public entry point

def run_ml_analysis(
    clean_df: pd.DataFrame,
    profile: DatasetProfile,
) -> tuple[list[InsightResult], list[SkippedTask]]:
    """
    Run all applicable ML models based on the DatasetProfile.

    Parameters
    ----------
    clean_df : preprocessed DataFrame (from preprocessor)
    profile  : DatasetProfile from Phase 1

    Returns
    -------
    (insights, skipped_tasks)
    insights      — list of InsightResult objects (unranked)
    skipped_tasks — list of SkippedTask objects explaining what was skipped
    """
    insights: list[InsightResult] = []
    skipped: list[SkippedTask] = []

    numeric_cols = [c for c in profile.numeric_columns if c in clean_df.columns]
    # Binary (boolean) columns hold 0/1 integer values and are valid numeric
    # inputs for every ML model — include them alongside true numeric columns.
    binary_cols = [
        c for c in (profile.binary_columns or [])
        if c in clean_df.columns and c not in numeric_cols
    ]
    numeric_cols = numeric_cols + binary_cols
    datetime_cols = [c for c in profile.datetime_columns if c in clean_df.columns]
    row_count = len(clean_df)

    # Model 1: Random Forest Feature Importance

    if (
        profile.ml_eligible
        and profile.potential_target
        and profile.potential_target in clean_df.columns
        and len(numeric_cols) >= 2
        and row_count >= MIN_ROWS_REGRESSION
    ):
        result = _run_feature_importance(clean_df, profile, numeric_cols)
        if result:
            insights.append(result)
    else:
        reason = _skip_reason_regression(profile, numeric_cols, row_count)
        skipped.append(SkippedTask(
            task_id="ml_regression",
            module="ml_module",
            skip_reason=reason,
        ))

    # Model 2: K-Means Clustering

    if (
        profile.ml_eligible
        and len(numeric_cols) >= MIN_NUMERIC_CLUSTERING
        and row_count >= MIN_ROWS_CLUSTERING
    ):
        result = _run_clustering(clean_df, profile, numeric_cols)
        if result:
            insights.append(result)
    else:
        reason = _skip_reason_clustering(profile, numeric_cols, row_count)
        skipped.append(SkippedTask(
            task_id="ml_clustering",
            module="ml_module",
            skip_reason=reason,
        ))

    # Model 3: Isolation Forest Anomaly Detection

    if len(numeric_cols) >= 1 and row_count >= MIN_ROWS_ANOMALY:
        result = _run_anomaly_detection(clean_df, profile, numeric_cols)
        if result:
            insights.append(result)
    else:
        skipped.append(SkippedTask(
            task_id="ml_anomaly",
            module="ml_module",
            skip_reason=(
                f"Anomaly detection needs at least {MIN_ROWS_ANOMALY} rows "
                f"and 1 numeric column. "
                f"Found {row_count} rows and {len(numeric_cols)} numeric column(s)."
            ),
        ))

    # Model 4: Exponential Smoothing Forecast

    if datetime_cols and numeric_cols and row_count >= MIN_ROWS_FORECAST:
        result = _run_forecast(clean_df, profile, datetime_cols[0], numeric_cols[0])
        if result:
            insights.append(result)
    else:
        reason = _skip_reason_forecast(datetime_cols, numeric_cols, row_count)
        skipped.append(SkippedTask(
            task_id="ml_forecasting",
            module="ml_module",
            skip_reason=reason,
        ))

    return insights, skipped

# Model 1 — Random Forest Feature Importance

def _run_feature_importance(
    df: pd.DataFrame,
    profile: DatasetProfile,
    numeric_cols: list[str],
) -> Optional[InsightResult]:
    start = time.time()

    try:
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.preprocessing import LabelEncoder
    except ImportError:
        return None

    target = profile.potential_target
    features = [c for c in numeric_cols if c != target]
    if not features:
        return None

    # Build feature matrix — numeric only, drop NaN rows
    X = df[features].apply(pd.to_numeric, errors="coerce")
    y = pd.to_numeric(df[target], errors="coerce")
    mask = X.notna().all(axis=1) & y.notna()
    X_clean = X[mask]
    y_clean = y[mask]

    if len(X_clean) < MIN_ROWS_REGRESSION:
        return None

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rf = RandomForestRegressor(
            n_estimators=RF_N_ESTIMATORS,
            random_state=RF_RANDOM_STATE,
            n_jobs=-1,
        )
        rf.fit(X_clean, y_clean)

    importances = rf.feature_importances_
    oob_eligible = len(X_clean) >= 50

    # R² as a proxy confidence metric
    y_pred = rf.predict(X_clean)
    ss_res = np.sum((y_clean.values - y_pred) ** 2)
    ss_tot = np.sum((y_clean.values - y_clean.mean()) ** 2)
    r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0

    # Build ranked importance records
    importance_records = sorted(
        [
            {
                "feature": feat,
                "importance": round(float(imp), 4),
                "importance_pct": round(float(imp) * 100, 2),
            }
            for feat, imp in zip(features, importances)
        ],
        key=lambda x: x["importance"],
        reverse=True,
    )

    top = importance_records[0]
    second = importance_records[1] if len(importance_records) > 1 else None
    plain = (
        f"Using Random Forest analysis, '{top['feature']}' is the most important "
        f"factor for predicting '{target}', accounting for "
        f"{top['importance_pct']:.1f}% of the model's predictive power "
        f"(model R² = {r2:.2f})."
    )
    takeaway = (
        f"'{top['feature']}' has the strongest influence on '{target}'. "
        f"Focus on this column to understand or improve {target}."
    )
    if second:
        fi_subtitle = (
            f"{top['feature']} accounts for {top['importance_pct']:.0f}% of what moves {target} — "
            f"more than all other factors combined. "
            f"{second['feature']} is the next closest at {second['importance_pct']:.0f}%."
        )
    else:
        fi_subtitle = (
            f"{top['feature']} accounts for {top['importance_pct']:.0f}% of what determines {target}. "
            f"Focus here first when trying to understand or shift this number."
        )

    chart = ChartSpec(
        chart_type=ChartType.bar,
        title=f"Feature Importance for '{target}'",
        x_field="feature",
        y_field="importance_pct",
        x_axis_label="Feature",
        y_axis_label="Importance (%)",
        data=[
            ChartDataPoint(
                label=r["feature"],
                value=round(r["importance_pct"], 2),
            )
            for r in importance_records
        ],
        color_scheme="sequential",
    )

    reliability = None
    if r2 < 0.3:
        reliability = ReliabilityWarning(
            warning_type=WarningType.weak_model,
            severity=Severity.medium,
            message=(
                f"The feature importance model has a low R² of {r2:.2f}, "
                "meaning it explains only a small portion of the variation. "
                "The rankings may not be reliable."
            ),
            affected_columns=[target],
            suggested_action="Collect more data or review column quality.",
        )

    col_meta = next((c for c in profile.columns if c.name == target), None)
    null_rate = col_meta.null_rate if col_meta else 0.0
    if null_rate > HIGH_MISSING_WARN and reliability is None:
        reliability = _missing_warning(target, null_rate)

    impact = round(min(1.0, max(0.0, r2)), 4)
    confidence = round(min(1.0, 0.5 + r2 * 0.5), 4)

    trace = TaskTrace(
        task_id=f"ml_rf_{uuid.uuid4().hex[:6]}",
        module="ml_module",
        operation="random_forest_feature_importance",
        columns_used=[target] + features,
        trigger_reason=(
            f"ML-eligible dataset with detected target column '{target}' "
            f"and {len(features)} numeric feature(s)."
        ),
        plain_explanation=(
            f"Trained a Random Forest regressor on {len(X_clean)} rows "
            f"to predict '{target}' from {len(features)} numeric columns. "
            f"Extracted feature importances (R² = {r2:.2f})."
        ),
        execution_time_ms=int((time.time() - start) * 1000),
        status=TaskStatus.completed,
    )

    follow_ups = _build_follow_ups([target], "feature_importance", profile)

    return InsightResult(
        insight_id=f"ins_{uuid.uuid4().hex[:8]}",
        source_module="ml_module",
        insight_type=InsightType.correlation,
        columns_used=[target] + features,
        value={
            "target": target,
            "importances": importance_records,
            "r_squared": round(r2, 4),
            "n_rows_used": int(len(X_clean)),
            "model": "RandomForestRegressor",
        },
        plain_summary=plain,
        key_takeaway=takeaway,
        subtitle=fi_subtitle,
        impact_score=impact,
        confidence_score=confidence,
        chart=chart,
        suggested_follow_ups=follow_ups,
        reliability_warning=reliability,
        trace=trace,
    )

# Model 2 — K-Means Clustering

def _run_clustering(
    df: pd.DataFrame,
    profile: DatasetProfile,
    numeric_cols: list[str],
) -> Optional[InsightResult]:
    start = time.time()

    try:
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler
        from sklearn.metrics import silhouette_score
    except ImportError:
        return None

    # Use only numeric columns with sufficient coverage
    usable_cols = [
        c for c in numeric_cols
        if df[c].notna().sum() / len(df) >= 0.7
        and not c.startswith("__")
    ]

    if len(usable_cols) < 2:
        return None

    X = df[usable_cols].apply(pd.to_numeric, errors="coerce").dropna()
    if len(X) < MIN_ROWS_CLUSTERING:
        return None

    # Scale
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Find best k via silhouette score (k = 2..MAX_CLUSTERS)
    best_k = 2
    best_score = -1.0
    best_model = None

    for k in range(2, min(MAX_CLUSTERS + 1, len(X) // 5 + 1)):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                km = KMeans(
                    n_clusters=k,
                    random_state=KMEANS_RANDOM_STATE,
                    n_init=10,
                )
                labels = km.fit_predict(X_scaled)
                if len(np.unique(labels)) < 2:
                    continue
                score = float(silhouette_score(X_scaled, labels))
            if score > best_score:
                best_score = score
                best_k = k
                best_model = km
        except Exception:
            continue

    if best_model is None:
        return None

    labels = best_model.predict(X_scaled)
    X_with_labels = X.copy()
    X_with_labels["__cluster__"] = labels

    # Build cluster profiles — mean values reported in ORIGINAL units so that
    # the insight card shows real Revenue figures, not z-scores.
    cluster_profiles = []
    for cluster_id in range(best_k):
        cluster_rows = X_with_labels[X_with_labels["__cluster__"] == cluster_id]
        size = len(cluster_rows)
        pct = round(size / len(X) * 100, 1)
        means = cluster_rows[usable_cols].mean().round(3).to_dict()
        cluster_profiles.append({
            "cluster_id": cluster_id,
            "size": size,
            "pct_of_data": pct,
            "mean_values": means,
            "label": f"Segment {cluster_id + 1} ({pct}% of data)",
        })

    # Identify the top 2 differentiating columns using the SCALED cluster
    # centroids (best_model.cluster_centers_ are in z-score units).
    # This gives an unbiased comparison: a column with Revenue ranging
    # $10K–$500K does not automatically win over Rating ranging 1–5.
    # Using original-unit means would always favour high-magnitude columns.
    centers_scaled = pd.DataFrame(
        best_model.cluster_centers_,
        columns=usable_cols,
    )
    col_variance = centers_scaled.var().sort_values(ascending=False)
    top_cols = list(col_variance.index[:2])

    plain = (
        f"K-Means clustering found {best_k} natural segments in your data "
        f"(silhouette score: {best_score:.2f}). "
        f"The segments differ most by '{top_cols[0]}'"
        f"{(' and ' + chr(39) + top_cols[1] + chr(39)) if len(top_cols) > 1 else ''}. "
        + " | ".join(
            f"Segment {cp['cluster_id'] + 1}: {cp['pct_of_data']}% of rows"
            for cp in cluster_profiles
        ) + "."
    )

    # Compare best and worst segment on the primary differentiating column
    primary_col = top_cols[0] if top_cols else None
    cluster_subtitle = (
        f"These segments represent naturally distinct behavioral or value groups in your data. "
        f"Treating them separately — rather than averaging across all records — will give sharper analysis."
    )
    if primary_col:
        seg_sorted = sorted(
            cluster_profiles,
            key=lambda cp: cp["mean_values"].get(primary_col, 0),
        )
        best_seg = seg_sorted[-1]
        worst_seg = seg_sorted[0]
        best_val = best_seg["mean_values"].get(primary_col, 0)
        worst_val = worst_seg["mean_values"].get(primary_col, 0)
        if worst_val > 0 and best_val > 0:
            ratio = best_val / worst_val
            takeaway = (
                f"Segment {best_seg['cluster_id'] + 1} averages {_fmt(best_val)} in {primary_col} — "
                f"{ratio:.1f}x more than Segment {worst_seg['cluster_id'] + 1}."
            )
            cluster_subtitle = (
                f"Segment {best_seg['cluster_id'] + 1} ({best_seg['pct_of_data']}% of records) "
                f"has significantly higher {primary_col} than the rest. "
                f"Understanding what this group has in common could reveal your highest-value transactions or customers."
            )
        else:
            takeaway = (
                f"Your data splits into {best_k} groups — "
                f"they differ most on '{primary_col}'."
            )
    else:
        takeaway = (
            f"Your data naturally falls into {best_k} distinct groups. "
            f"Segment 1 is the largest at {cluster_profiles[0]['pct_of_data']}% of rows."
        )

    # Chart: bar showing segment sizes
    chart = ChartSpec(
        chart_type=ChartType.bar,
        title=f"Cluster Segment Sizes (k={best_k})",
        x_field="segment",
        y_field="size",
        x_axis_label="Segment",
        y_axis_label="Number of Rows",
        data=[
            ChartDataPoint(
                label=f"Segment {cp['cluster_id'] + 1}",
                value=float(cp["size"]),
            )
            for cp in cluster_profiles
        ],
        color_scheme="categorical",
    )

    reliability = None
    if best_score < 0.3:
        reliability = ReliabilityWarning(
            warning_type=WarningType.weak_model,
            severity=Severity.medium,
            message=(
                f"The clustering silhouette score is low ({best_score:.2f}), "
                "suggesting the segments are not strongly distinct. "
                "Interpret with caution."
            ),
            affected_columns=usable_cols,
            suggested_action="Try removing highly correlated columns or collecting more data.",
        )

    impact = round(min(1.0, best_score + 0.2), 4)
    confidence = round(min(1.0, 0.4 + best_score * 0.6), 4)

    trace = TaskTrace(
        task_id=f"ml_km_{uuid.uuid4().hex[:6]}",
        module="ml_module",
        operation="kmeans_clustering",
        columns_used=usable_cols,
        trigger_reason=(
            f"ML-eligible dataset with {len(usable_cols)} usable numeric columns "
            f"and {len(X)} rows."
        ),
        plain_explanation=(
            f"Applied StandardScaler to {len(usable_cols)} numeric columns before "
            f"clustering (zero mean, unit variance) so that high-magnitude columns "
            f"do not dominate Euclidean distance. "
            f"Ran K-Means with k=2 to {min(MAX_CLUSTERS, len(X) // 5)} and selected "
            f"k={best_k} via highest silhouette score ({best_score:.2f}). "
            f"Cluster means are reported in original units for interpretability. "
            f"Differentiating columns identified from scaled centroid variance."
        ),
        execution_time_ms=int((time.time() - start) * 1000),
        status=TaskStatus.completed,
    )

    follow_ups = _build_follow_ups(usable_cols[:2], "segment", profile)

    return InsightResult(
        insight_id=f"ins_{uuid.uuid4().hex[:8]}",
        source_module="ml_module",
        insight_type=InsightType.segment,
        columns_used=usable_cols,
        value={
            "n_clusters": best_k,
            "silhouette_score": round(best_score, 4),
            "cluster_profiles": cluster_profiles,
            "differentiating_columns": top_cols,
            "model": "KMeans",
        },
        plain_summary=plain,
        key_takeaway=takeaway,
        subtitle=cluster_subtitle,
        impact_score=impact,
        confidence_score=confidence,
        chart=chart,
        suggested_follow_ups=follow_ups,
        reliability_warning=reliability,
        trace=trace,
    )

# Model 3 — Isolation Forest Anomaly Detection

def _run_anomaly_detection(
    df: pd.DataFrame,
    profile: DatasetProfile,
    numeric_cols: list[str],
) -> Optional[InsightResult]:
    start = time.time()

    try:
        from sklearn.ensemble import IsolationForest
    except ImportError:
        return None

    usable_cols = [
        c for c in numeric_cols
        if df[c].notna().sum() / len(df) >= 0.7
        and not c.startswith("__")
    ]
    if not usable_cols:
        return None

    X = df[usable_cols].apply(pd.to_numeric, errors="coerce").dropna()
    if len(X) < MIN_ROWS_ANOMALY:
        return None

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        iso = IsolationForest(
            contamination=ISO_CONTAMINATION,
            random_state=RF_RANDOM_STATE,
            n_jobs=-1,
        )
        predictions = iso.fit_predict(X)
        scores = iso.score_samples(X)

    anomaly_mask = predictions == -1
    n_anomalies = int(anomaly_mask.sum())
    anomaly_pct = round(n_anomalies / len(X) * 100, 2)

    # Get the most anomalous rows (lowest score = most anomalous)
    anomaly_indices = np.where(anomaly_mask)[0]
    top_anomaly_indices = anomaly_indices[
        np.argsort(scores[anomaly_indices])[:10]
    ]

    top_anomalies = []
    for idx in top_anomaly_indices:
        row_data = X.iloc[idx][usable_cols[:4]].round(4).to_dict()
        top_anomalies.append({
            "row_index": int(X.index[idx]),
            "anomaly_score": round(float(scores[idx]), 4),
            "values": row_data,
        })

    plain = (
        f"Isolation Forest detected {n_anomalies} anomalous rows "
        f"({anomaly_pct}% of your data). "
        f"These rows have unusual combinations of values across "
        f"{len(usable_cols)} numeric column(s) and may deserve closer inspection."
    )

    # Find which column stands out most in the anomalous rows
    most_extreme_col = None
    try:
        normal_mask = predictions == 1
        if normal_mask.sum() > 5:
            normal_means = X[normal_mask].mean()
            normal_stds = X[normal_mask].std().replace(0, 1)
        else:
            normal_means = X.mean()
            normal_stds = X.std().replace(0, 1)
        anomaly_rows = X[anomaly_mask]
        mean_z_per_col = ((anomaly_rows - normal_means) / normal_stds).abs().mean()
        most_extreme_col = str(mean_z_per_col.idxmax())
    except Exception:
        pass

    if most_extreme_col:
        takeaway = (
            f"{n_anomalies} unusual rows detected — they stand out most on '{most_extreme_col}'. "
            f"Check for data entry errors or exceptional events."
        )
        anomaly_subtitle = (
            f"The flagged rows have extreme {most_extreme_col} values relative to the rest of your data. "
            f"They could be data entry errors, one-off exceptions, or genuinely high-signal events — worth a manual review."
        )
    else:
        takeaway = (
            f"{n_anomalies} rows appear to be statistical outliers. "
            f"Review them to check for data entry errors or genuinely unusual events."
        )
        anomaly_subtitle = (
            f"These rows don't fit the normal patterns across your numeric columns. "
            f"They may be data errors or genuine outliers — either way, they deserve a closer look."
        )

    # Chart: bar of anomaly score distribution
    score_series = pd.Series(scores)
    hist_counts, hist_edges = np.histogram(score_series, bins=10)
    chart = ChartSpec(
        chart_type=ChartType.histogram,
        title="Anomaly Score Distribution",
        x_field="anomaly_score",
        y_field="count",
        x_axis_label="Anomaly Score (lower = more anomalous)",
        y_axis_label="Number of Rows",
        data=[
            ChartDataPoint(
                label=f"{_fmt(float(hist_edges[i]))} - {_fmt(float(hist_edges[i + 1]))}",
                value=float(c),
            )
            for i, c in enumerate(hist_counts)
        ],
        color_scheme="sequential",
    )

    impact = round(min(1.0, anomaly_pct / 10 + 0.3), 4)
    confidence = round(min(1.0, 0.6 + len(X) / 1000 * 0.4), 4)

    trace = TaskTrace(
        task_id=f"ml_iso_{uuid.uuid4().hex[:6]}",
        module="ml_module",
        operation="isolation_forest_anomaly",
        columns_used=usable_cols,
        trigger_reason=(
            f"{len(X)} rows and {len(usable_cols)} numeric columns — "
            f"enough for anomaly detection."
        ),
        plain_explanation=(
            f"Trained Isolation Forest on {len(X)} rows across "
            f"{len(usable_cols)} columns with contamination={ISO_CONTAMINATION}. "
            f"Found {n_anomalies} anomalous rows."
        ),
        execution_time_ms=int((time.time() - start) * 1000),
        status=TaskStatus.completed,
    )

    follow_ups = _build_follow_ups(usable_cols[:2], "anomaly", profile)

    return InsightResult(
        insight_id=f"ins_{uuid.uuid4().hex[:8]}",
        source_module="ml_module",
        insight_type=InsightType.anomaly,
        columns_used=usable_cols,
        value={
            "n_anomalies": n_anomalies,
            "anomaly_pct": anomaly_pct,
            "top_anomalies": top_anomalies,
            "columns_used": usable_cols,
            "model": "IsolationForest",
        },
        plain_summary=plain,
        key_takeaway=takeaway,
        subtitle=anomaly_subtitle,
        impact_score=impact,
        confidence_score=confidence,
        chart=chart,
        suggested_follow_ups=follow_ups,
        trace=trace,
    )

# Model 4 — Exponential Smoothing Forecast

def _run_forecast(
    df: pd.DataFrame,
    profile: DatasetProfile,
    dt_col: str,
    num_col: str,
) -> Optional[InsightResult]:
    start = time.time()

    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
    except ImportError:
        return None

    # Parse datetime and aggregate by month
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            dt_series = pd.to_datetime(df[dt_col], errors="coerce")
    except Exception:
        return None

    num_series = pd.to_numeric(df[num_col], errors="coerce")
    mask = dt_series.notna() & num_series.notna()
    temp = pd.DataFrame({dt_col: dt_series[mask], num_col: num_series[mask]})
    temp["__period"] = temp[dt_col].dt.to_period("M")
    monthly = (
        temp.groupby("__period")[num_col]
        .sum()
        .reset_index()
        .sort_values("__period")
    )
    monthly["period_str"] = monthly["__period"].astype(str)

    if len(monthly) < MIN_ROWS_FORECAST:
        return None

    y = monthly[num_col].values.astype(float)

    # Fit Exponential Smoothing (Holt's linear — handles trend)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = ExponentialSmoothing(
                y,
                trend="add",
                seasonal=None,
                initialization_method="estimated",
            )
            fitted = model.fit(optimized=True)
            forecast_vals = fitted.forecast(FORECAST_PERIODS)
    except Exception:
        # Fallback: simple linear extrapolation
        x = np.arange(len(y))
        slope, intercept = np.polyfit(x, y, 1)
        forecast_vals = np.array([
            slope * (len(y) + i) + intercept
            for i in range(FORECAST_PERIODS)
        ])

    # Generate future period labels
    last_period = monthly["__period"].iloc[-1]
    future_periods = [str(last_period + i + 1) for i in range(FORECAST_PERIODS)]

    historical_records = [
        {"period": str(row["period_str"]), "value": round(float(row[num_col]), 4), "type": "historical"}
        for _, row in monthly.iterrows()
    ]
    forecast_records = [
        {"period": p, "value": round(float(v), 4), "type": "forecast"}
        for p, v in zip(future_periods, forecast_vals)
    ]
    all_records = historical_records + forecast_records

    last_actual = float(y[-1])
    next_forecast = float(forecast_vals[0])
    direction = "increase" if next_forecast > last_actual else "decrease"
    change_pct = abs((next_forecast - last_actual) / max(abs(last_actual), 1e-9)) * 100

    plain = (
        f"Based on {len(monthly)} months of data, '{num_col}' is projected to "
        f"{direction} by {change_pct:.1f}% in the next period "
        f"(from {_fmt(last_actual)} to {_fmt(next_forecast)}). "
        f"The {FORECAST_PERIODS}-period forecast uses exponential smoothing."
    )
    takeaway = (
        f"'{num_col}' is expected to {direction} over the next "
        f"{FORECAST_PERIODS} periods. Next period forecast: {_fmt(next_forecast)}."
    )
    forecast_subtitle = (
        f"This projection is based on the historical trend in your data — it assumes patterns continue as-is. "
        f"Treat it as a directional guide rather than a precise target, especially if external factors could shift the trend."
    )

    chart = ChartSpec(
        chart_type=ChartType.line,
        title=f"{num_col} — Historical + {FORECAST_PERIODS}-Period Forecast",
        x_field="period",
        y_field="value",
        x_axis_label="Period",
        y_axis_label=num_col,
        data=[
            ChartDataPoint(
                label=r["period"],
                value=round(r["value"], 4),
                group=r["type"],
            )
            for r in all_records
        ],
        color_scheme="sequential",
    )

    reliability = ReliabilityWarning(
        warning_type=WarningType.partial_data,
        severity=Severity.low,
        message=(
            "Forecasts are projections based on historical patterns "
            "and may not account for seasonal changes or external factors. "
            "Use as a directional guide, not a precise prediction."
        ),
        affected_columns=[num_col],
        suggested_action="Validate against domain knowledge before making decisions.",
    )

    col_meta = next((c for c in profile.columns if c.name == num_col), None)
    null_rate = col_meta.null_rate if col_meta else 0.0
    confidence = round(max(0.4, 1.0 - null_rate - (0.1 if len(monthly) < 24 else 0.0)), 4)
    impact = round(min(1.0, change_pct / 50 + 0.4), 4)

    trace = TaskTrace(
        task_id=f"ml_fc_{uuid.uuid4().hex[:6]}",
        module="ml_module",
        operation="exponential_smoothing_forecast",
        columns_used=[dt_col, num_col],
        trigger_reason=(
            f"Datetime column '{dt_col}' and numeric column '{num_col}' detected "
            f"with {len(monthly)} monthly periods — enough for forecasting."
        ),
        plain_explanation=(
            f"Fitted Holt's Exponential Smoothing on {len(monthly)} monthly "
            f"aggregated values of '{num_col}' and projected {FORECAST_PERIODS} "
            f"periods ahead."
        ),
        execution_time_ms=int((time.time() - start) * 1000),
        status=TaskStatus.completed,
    )

    follow_ups = _build_follow_ups([dt_col, num_col], "trend", profile)

    return InsightResult(
        insight_id=f"ins_{uuid.uuid4().hex[:8]}",
        source_module="ml_module",
        insight_type=InsightType.trend,
        columns_used=[dt_col, num_col],
        value={
            "historical": historical_records,
            "forecast": forecast_records,
            "forecast_periods": FORECAST_PERIODS,
            "direction": direction,
            "next_period_forecast": round(next_forecast, 4),
            "model": "ExponentialSmoothing",
        },
        plain_summary=plain,
        key_takeaway=takeaway,
        subtitle=forecast_subtitle,
        impact_score=impact,
        confidence_score=confidence,
        chart=chart,
        suggested_follow_ups=follow_ups,
        reliability_warning=reliability,
        trace=trace,
    )

# Skip reason builders

def _skip_reason_regression(
    profile: DatasetProfile,
    numeric_cols: list[str],
    row_count: int,
) -> str:
    if not profile.ml_eligible:
        return (
            f"Dataset has fewer than {MIN_ROWS_REGRESSION} rows or fewer than "
            f"2 numeric columns — not eligible for ML."
        )
    if not profile.potential_target:
        return "No clear target column detected for regression."
    if len(numeric_cols) < 2:
        return "Need at least 2 numeric columns for feature importance."
    if row_count < MIN_ROWS_REGRESSION:
        return (
            f"Need at least {MIN_ROWS_REGRESSION} rows for regression. "
            f"Dataset has {row_count}."
        )
    return "Regression conditions not met."

def _skip_reason_clustering(
    profile: DatasetProfile,
    numeric_cols: list[str],
    row_count: int,
) -> str:
    if not profile.ml_eligible:
        return "Dataset not ML-eligible (too few rows or numeric columns)."
    if len(numeric_cols) < MIN_NUMERIC_CLUSTERING:
        return f"Need at least {MIN_NUMERIC_CLUSTERING} numeric columns for clustering."
    if row_count < MIN_ROWS_CLUSTERING:
        return f"Need at least {MIN_ROWS_CLUSTERING} rows for clustering. Found {row_count}."
    return "Clustering conditions not met."

def _skip_reason_forecast(
    datetime_cols: list[str],
    numeric_cols: list[str],
    row_count: int,
) -> str:
    if not datetime_cols:
        return "No datetime column detected — forecasting requires a date column."
    if not numeric_cols:
        return "No numeric column detected — forecasting requires a numeric column."
    if row_count < MIN_ROWS_FORECAST:
        return (
            f"Need at least {MIN_ROWS_FORECAST} data points for forecasting. "
            f"Found {row_count}."
        )
    return "Forecasting conditions not met."

# Shared helpers

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

def _missing_warning(col: str, null_rate: float) -> ReliabilityWarning:
    return ReliabilityWarning(
        warning_type=WarningType.high_missing,
        severity=Severity.medium,
        message=(
            f"'{col}' has {null_rate:.0%} missing values. "
            "ML results may be less reliable."
        ),
        affected_columns=[col],
        suggested_action="Clean missing values before running ML analysis.",
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

    if context == "feature_importance" and cat_cols and cols:
        follow_ups.append(SuggestedFollowUp(
            followup_id=f"fu_{uuid.uuid4().hex[:6]}",
            question_text=f"Compare {cols[0]} by {cat_cols[0]}",
            reasoning="After finding what drives the target, compare it across categories.",
            pre_mapped_intent="comparison",
            pre_mapped_columns=[cols[0], cat_cols[0]],
            priority=priority,
        ))
        priority += 1

    if context == "segment" and num_cols:
        follow_ups.append(SuggestedFollowUp(
            followup_id=f"fu_{uuid.uuid4().hex[:6]}",
            question_text=f"Show distribution of {num_cols[0]}",
            reasoning="After finding segments, explore the distribution of key numeric columns.",
            pre_mapped_intent="distribution",
            pre_mapped_columns=[num_cols[0]],
            priority=priority,
        ))
        priority += 1

    if context == "anomaly" and cols:
        follow_ups.append(SuggestedFollowUp(
            followup_id=f"fu_{uuid.uuid4().hex[:6]}",
            question_text=f"Show distribution of {cols[0]}",
            reasoning="After finding anomalies, view the full distribution to understand them.",
            pre_mapped_intent="distribution",
            pre_mapped_columns=[cols[0]],
            priority=priority,
        ))
        priority += 1

    if context == "trend" and dt_cols and num_cols:
        target_col = next((c for c in cols if c in num_cols), num_cols[0])
        if cat_cols:
            follow_ups.append(SuggestedFollowUp(
                followup_id=f"fu_{uuid.uuid4().hex[:6]}",
                question_text=f"Compare {target_col} by {cat_cols[0]}",
                reasoning="After seeing the forecast, compare the target across categories.",
                pre_mapped_intent="comparison",
                pre_mapped_columns=[cat_cols[0], target_col],
                priority=priority,
            ))

    return follow_ups[:3]
