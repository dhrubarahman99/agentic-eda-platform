# File download endpoints: insights CSV/JSON, chart data, preprocessing report, dataset preview.

from __future__ import annotations

import io
import json
import re
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.modules.exporter import (
    build_dataset_preview,
    build_export_bundle,
    chart_to_csv,
    insights_to_csv,
)
from app.utils.session_store import session_store
from app.api.analysis import _analysis_cache

router = APIRouter()

def _csv_response(content: str, filename: str) -> StreamingResponse:
    return StreamingResponse(
        io.StringIO(content),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

def _json_response(content: dict, filename: str) -> StreamingResponse:
    raw = json.dumps(content, indent=2, default=str)
    return StreamingResponse(
        io.StringIO(raw),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

def _text_response(content: str, filename: str) -> StreamingResponse:
    return StreamingResponse(
        io.StringIO(content),
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

def _require_session(session_id: str) -> None:
    if not session_store.exists(session_id):
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found. Upload a CSV first.",
        )

def _require_analysis(session_id: str):
    cached = _analysis_cache.get(session_id)
    if cached is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No analysis found for session '{session_id}'. "
                "Run POST /api/analyse/{session_id} first."
            ),
        )
    return cached

@router.get(
    "/export/{session_id}/insights.csv",
    summary="Download all ranked insights as a CSV file",
    tags=["Export"],
)
async def export_insights_csv(session_id: str) -> StreamingResponse:
    _require_session(session_id)
    cached = _require_analysis(session_id)

    filename = session_store.get_filename(session_id) or "dataset"
    stem = filename.replace(".csv", "")

    csv_content = insights_to_csv(cached.insights)
    return _csv_response(csv_content, f"{stem}_insights.csv")

@router.get(
    "/export/{session_id}/insights.json",
    summary="Download the full analysis bundle as a JSON file",
    tags=["Export"],
)
async def export_insights_json(session_id: str) -> StreamingResponse:
    _require_session(session_id)
    cached = _require_analysis(session_id)

    profile = session_store.get_profile(session_id)
    filename = session_store.get_filename(session_id) or "dataset"
    stem = filename.replace(".csv", "")

    plan_tasks = [
        {
            "task_id": t.task_id,
            "module": t.module,
            "status": t.status,
            "description": t.description,
        }
        for t in cached.analysis_plan.tasks
    ]

    bundle = build_export_bundle(
        profile=profile,
        insights=cached.insights,
        preprocessing_summary=cached.preprocessing_report.to_plain_summary(),
        plan_tasks=plan_tasks,
    )

    return _json_response(bundle, f"{stem}_analysis.json")

@router.get(
    "/export/{session_id}/chart/{insight_id}.csv",
    summary="Download chart data for a specific insight as CSV",
    tags=["Export"],
)
async def export_chart_csv(session_id: str, insight_id: str) -> StreamingResponse:
    _require_session(session_id)
    cached = _require_analysis(session_id)

    insight = next(
        (i for i in cached.insights if i.insight_id == insight_id),
        None,
    )
    if insight is None:
        raise HTTPException(
            status_code=404,
            detail=f"Insight '{insight_id}' not found in session '{session_id}'.",
        )

    if insight.chart is None:
        raise HTTPException(
            status_code=404,
            detail=f"Insight '{insight_id}' does not have chart data.",
        )

    csv_content = chart_to_csv(insight)
    safe_id = insight_id[:12]
    return _csv_response(csv_content, f"chart_{safe_id}.csv")

@router.get(
    "/export/{session_id}/preprocessing.txt",
    summary="Download the preprocessing audit report as plain text",
    tags=["Export"],
)
async def export_preprocessing_report(session_id: str) -> StreamingResponse:
    _require_session(session_id)
    cached = _require_analysis(session_id)
    profile = session_store.get_profile(session_id)

    rpt = cached.preprocessing_report
    filename = session_store.get_filename(session_id) or "dataset.csv"
    stem = filename.replace(".csv", "")

    text_content = _build_professional_report(rpt, profile, filename)
    return _text_response(text_content, f"{stem}_preprocessing_report.txt")

def _build_professional_report(rpt: Any, profile: Any, filename: str) -> str:
    W = 72  # total line width

    def divider(char: str = "=") -> str:
        return char * W

    def section_header(number: str, title: str) -> str:
        label = f"  {number}. {title}"
        return f"\n{divider('-')}\n{label}\n{divider('-')}"

    def _table(headers: list, rows: list, col_widths: list | None = None) -> str:
        if not rows:
            return "  (none)"
        if col_widths is None:
            col_widths = []
            for i, h in enumerate(headers):
                w = max(len(str(h)), max(len(str(r[i])) for r in rows))
                col_widths.append(w)
        sep = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"
        hdr = "| " + " | ".join(str(h).ljust(w) for h, w in zip(headers, col_widths)) + " |"
        lines = [sep, hdr, sep]
        for row in rows:
            lines.append("| " + " | ".join(str(v).ljust(w) for v, w in zip(row, col_widths)) + " |")
        lines.append(sep)
        return "\n".join("  " + ln for ln in lines)

    col_meta = {c.name: c for c in profile.columns}
    orig_rows, orig_cols = rpt.original_shape
    clean_rows, clean_cols = rpt.clean_shape

    raw_missing = profile.summary_card.total_missing_cells
    raw_duplicates = profile.summary_card.duplicate_row_count

    imputation_logs = [
        t for t in rpt.transformations
        if t.operation in ("median_imputation", "mode_imputation", "datetime_missing_noted")
    ]
    total_imputed = sum(t.rows_affected for t in imputation_logs)

    outlier_logs = [t for t in rpt.transformations if t.operation == "outlier_flagging"]
    outlier_row_count = rpt.outlier_row_count

    date_logs = [t for t in rpt.transformations if t.operation == "date_decomposition"]
    datetime_cols = profile.datetime_columns or []

    user_added_cols = [c for c in rpt.new_columns_added if not c.startswith("__")]
    engineered_count = len(user_added_cols)

    lines: list[str] = []
    lines += [
        divider("="),
        "  InsightIQ — Data Preprocessing Report",
        divider("="),
        "",
        f"  Dataset Name      : {filename}",
        f"  Original Shape    : {orig_rows:,} rows × {orig_cols} columns",
        f"  Cleaned Shape     : {clean_rows:,} rows × {clean_cols} columns",
        f"  Report Generated  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"  Execution Time    : {rpt.execution_time_ms} ms",
        "",
        divider("="),
    ]

    lines.append(section_header("2", "EXECUTIVE SUMMARY"))
    lines.append("")

    summary_parts: list[str] = []

    if raw_missing > 0:
        affected_cols = len(imputation_logs)
        summary_parts.append(
            f"The dataset initially contained {raw_missing:,} missing value(s) "
            f"across {affected_cols} column(s)."
        )
    else:
        summary_parts.append("The dataset contained no missing values.")

    if raw_duplicates > 0:
        summary_parts.append(
            f"{raw_duplicates:,} duplicate row(s) were detected and removed "
            "(first occurrence preserved)."
        )
    else:
        summary_parts.append("No duplicate rows were detected.")

    if total_imputed > 0:
        summary_parts.append(
            "Missing values were imputed using statistically appropriate methods "
            "(median for numeric columns, mode for categorical columns)."
        )

    if outlier_row_count > 0:
        summary_parts.append(
            f"{outlier_row_count:,} potential outlier row(s) were identified across "
            f"{len(outlier_logs)} numeric column(s) using IQR analysis and flagged "
            "for transparency — they were NOT deleted."
        )
    else:
        summary_parts.append("No statistical outliers were detected.")

    if engineered_count > 0:
        summary_parts.append(
            f"{engineered_count} new engineered feature(s) were derived from "
            f"{len(date_logs)} datetime column(s)."
        )

    if rpt.columns_dropped:
        summary_parts.append(
            f"{len(rpt.columns_dropped)} column(s) were removed due to excessive "
            "sparsity (> 80% missing) or zero variance."
        )

    lines.append("  " + " ".join(summary_parts))
    lines.append("")

    lines.append(section_header("3", "BEFORE VS AFTER DATA QUALITY SUMMARY"))
    lines.append("")

    bva_headers = ["Metric", "Raw Dataset", "Clean Dataset"]
    bva_rows = [
        ["Total Rows",               f"{orig_rows:,}",         f"{clean_rows:,}"],
        ["Total Columns",            str(orig_cols),           str(clean_cols)],
        ["Missing Values",           f"{raw_missing:,}",       "0"],
        ["Duplicate Rows",           f"{raw_duplicates:,}",    "0"],
        ["Outlier Flags",            "0",                      f"{outlier_row_count:,}"],
        ["Date Columns Detected",    str(len(datetime_cols)),  str(len(datetime_cols))],
        ["Engineered Columns Added", "0",                      str(engineered_count)],
    ]
    lines.append(_table(bva_headers, bva_rows, col_widths=[28, 13, 13]))
    lines.append("")

    lines.append(section_header("4", "COLUMN TYPE DETECTION"))
    lines.append("")

    type_groups: dict[str, list[str]] = {
        "Numeric": [], "Categorical": [], "Datetime": [],
        "Boolean": [], "Text": [],
    }
    type_reasons: dict[str, str] = {
        "Numeric":     "Values are predominantly integers or floating-point numbers.",
        "Categorical": "Column contains a limited set of repeating string categories (low cardinality).",
        "Datetime":    "Values match common date/time patterns and were successfully parsed.",
        "Boolean":     "Column contains binary values (True/False, Yes/No, 0/1).",
        "Text":        "Column contains free-form text strings with high cardinality.",
    }

    for c in profile.columns:
        dtype_key = c.dtype.value.capitalize()
        if dtype_key in type_groups:
            type_groups[dtype_key].append(c.name)

    for dtype_label, cols in type_groups.items():
        if not cols:
            continue
        lines.append(f"  {dtype_label} ({len(cols)} column{'s' if len(cols) != 1 else ''}):")
        lines.append(f"    Reason : {type_reasons[dtype_label]}")
        lines.append(f"    Columns: {', '.join(cols)}")
        lines.append("")

    lines.append(section_header("5", "MISSING VALUE HANDLING"))
    lines.append("")

    if imputation_logs:
        mv_headers = ["Column", "Missing", "% Missing", "Type", "Method", "Replacement", "Reason"]
        mv_rows = []
        for t in imputation_logs:
            col = t.column or ""
            missing_count = t.rows_affected
            missing_pct = f"{(missing_count / orig_rows * 100):.1f}%" if orig_rows > 0 else "N/A"
            meta = col_meta.get(col)
            col_type = meta.dtype.value.capitalize() if meta else "Unknown"
            if t.operation == "median_imputation":
                method = "Median"
                reason = "Median is robust against outliers and skewed distributions"
            elif t.operation == "mode_imputation":
                method = "Mode"
                reason = "Mode preserves the most common category; robust to distribution shape"
            else:
                method = "Not Imputed"
                reason = "Datetime columns are excluded from imputation to avoid spurious dates"
            replacement = t.fill_value if t.fill_value else "—"
            mv_rows.append([col, str(missing_count), missing_pct, col_type, method, replacement, reason])
        lines.append(_table(mv_headers, mv_rows))
    else:
        lines.append("  No missing values required imputation — dataset was complete.")
    lines.append("")

    lines.append(section_header("6", "DUPLICATE ROW ANALYSIS"))
    lines.append("")

    lines.append(f"  Duplicates in Raw Dataset  : {raw_duplicates:,}")
    lines.append(f"  Duplicates After Cleaning  : 0")
    if raw_duplicates > 0:
        lines.append(f"  Action Taken               : Removed — first occurrence of each row preserved.")
        lines.append(f"  Rationale                  : Duplicate rows inflate counts and skew statistical")
        lines.append(f"                               averages, leading to misleading analysis results.")
    else:
        lines.append(f"  Action Taken               : None — no duplicates were found.")
    lines.append("")

    lines.append(section_header("7", "OUTLIER ANALYSIS"))
    lines.append("")

    if outlier_logs:
        lines.append(
            "  NOTE: Outliers are flagged for transparency and are NOT automatically\n"
            "  deleted. They may represent legitimate extreme business events or\n"
            "  measurement anomalies that carry analytical value.\n"
        )
        oa_headers = ["Column", "Method", "Lower Bound", "Upper Bound", "Flagged Rows", "Action"]
        oa_rows = []
        _bound_re = re.compile(r"Tukey fence\s+([-\d.e+Ee]+)–([-\d.e+Ee]+)")
        for t in outlier_logs:
            m = _bound_re.search(t.detail)
            lower = m.group(1) if m else "N/A"
            upper = m.group(2) if m else "N/A"
            oa_rows.append([
                t.column or "—",
                "IQR (Tukey)",
                lower,
                upper,
                str(t.rows_affected),
                "Flagged Only",
            ])
        lines.append(_table(oa_headers, oa_rows))
        lines.append("")
        lines.append(f"  Total rows with at least one outlier flag : {outlier_row_count:,}")
        lines.append(f"  Outlier flag column in cleaned dataset    : __outlier_flag__")
        lines.append(f"  Severity column                           : __outlier_severity__ (0=clean, 1=mild, 2=extreme)")
    else:
        lines.append("  No outliers were detected in any numeric column.")
    lines.append("")

    lines.append(section_header("8", "DATE/TIME TRANSFORMATIONS"))
    lines.append("")

    if date_logs:
        for t in date_logs:
            src_col = t.column or "unknown"
            derived = [c for c in user_added_cols if c.startswith(f"{src_col}__")]
            lines.append(f"  Source Column : {src_col}")
            lines.append(f"  Derived Features ({len(derived)}):")
            for dc in derived:
                suffix = dc.replace(f"{src_col}__", "")
                lines.append(f"    + {dc}  →  {_date_feature_explanation(suffix)}")
            lines.append("")
        lines.append(
            "  Rationale: Decomposed datetime features enable time-based grouping,\n"
            "  seasonal analysis, weekday/weekend segmentation, and are required\n"
            "  by machine learning models which cannot process raw datetime values."
        )
    else:
        lines.append("  No datetime columns were detected or decomposed.")
    lines.append("")

    lines.append(section_header("10", "TRANSFORMATION LOG (CHRONOLOGICAL)"))
    lines.append("")

    step = 1
    op_labels = {
        "column_dropped_sparse":    "Dropped sparse column",
        "duplicate_removal":        "Removed duplicate rows",
        "string_cleaning":          "Cleaned string values",
        "case_normalisation":       "Normalised column case",
        "numeric_coercion":         "Coerced string to numeric",
        "datetime_parsing":         "Parsed datetime column",
        "boolean_standardisation":  "Standardised boolean column",
        "median_imputation":        "Imputed missing values (Median)",
        "mode_imputation":          "Imputed missing values (Mode)",
        "datetime_missing_noted":   "Noted missing datetime values (not imputed)",
        "constant_column_dropped":  "Dropped zero-variance column",
        "date_decomposition":       "Decomposed datetime features",
        "outlier_flagging":         "Flagged outliers (IQR mild)",
        "extreme_outlier_flagging": "Flagged outliers (IQR extreme / Z-score)",
    }
    for t in rpt.transformations:
        label = op_labels.get(t.operation, t.operation)
        col_part = f" [{t.column}]" if t.column else ""
        lines.append(f"  [Step {step:>2}]{col_part}  {label}")
        # Compact detail — strip internal formatting junk
        detail_clean = t.detail.strip().rstrip(".")
        lines.append(f"           {detail_clean}.")
        lines.append("")
        step += 1

    lines.append(section_header("11", "PREPROCESSING DECISION EXPLANATIONS"))
    lines.append("")
    explanations = [
        ("Median over Mean for Numeric Imputation",
         "Median is the middle value of a sorted distribution and is unaffected by\n"
         "  extreme outliers. Mean can be pulled significantly by a single anomalous\n"
         "  value, producing a biased fill. Median preserves the true central tendency."),
        ("Mode for Categorical Imputation",
         "Mode fills missing categorical values with the most frequently observed\n"
         "  category, preserving the existing class distribution without introducing\n"
         "  artificial categories or breaking frequency analysis."),
        ("Outliers Flagged, Not Deleted",
         "Automatically deleting outliers risks removing legitimate extreme events\n"
         "  (e.g. record sales, system failures). Flagging them with __outlier_flag__\n"
         "  and __outlier_severity__ allows analysts to make informed decisions while\n"
         "  preserving raw data integrity."),
        ("Datetime Feature Engineering",
         "Machine learning models cannot use raw datetime objects. Decomposed features\n"
         "  (year, month, weekday, quarter) allow models to detect seasonality, trends,\n"
         "  and cyclic patterns. Weekday and is_weekend support customer behaviour\n"
         "  analysis without requiring external time-series libraries."),
        ("Constant Column Removal",
         "Columns with a single unique value carry zero statistical information —\n"
         "  they cannot contribute to correlation, regression, or classification.\n"
         "  Removing them reduces noise and speeds up model training."),
    ]
    for title, body in explanations:
        lines.append(f"  {title}")
        lines.append(f"  {'─' * len(title)}")
        lines.append(f"  {body}")
        lines.append("")

    lines.append(section_header("12", "FINAL DATA QUALITY ASSESSMENT"))
    lines.append("")

    quality_status = profile.data_quality.overall.value.upper()
    lines.append(f"  Overall Data Quality : {quality_status}")
    lines.append(f"  Quality Note         : {profile.summary_card.quality_note}")
    lines.append("")

    remaining_issues: list[str] = []
    if outlier_row_count > 0:
        remaining_issues.append(
            f"- {outlier_row_count:,} row(s) contain flagged outliers. Review the "
            "__outlier_flag__ column manually to validate extreme values against\n"
            "    your domain knowledge before using these rows in predictive models."
        )
    if date_logs:
        remaining_issues.append(
            "- Original datetime columns were retained alongside their decomposed\n"
            "    features. Consider dropping the raw datetime column before ML training\n"
            "    if your model does not support datetime inputs natively."
        )
    if not remaining_issues:
        remaining_issues.append(
            "- No critical issues remain. The dataset is considered clean and\n"
            "    ready for exploratory analysis and machine learning tasks."
        )

    lines.append("  Remaining Considerations:")
    for issue in remaining_issues:
        lines.append(f"    {issue}")
    lines.append("")
    lines.append(
        "  RECOMMENDATION: This cleaned dataset is suitable for exploratory\n"
        "  data analysis, statistical modelling, and supervised machine learning.\n"
        "  Flagged outliers should be reviewed by a domain expert before final\n"
        "  model deployment."
    )
    lines.append("")
    lines.append(divider("="))
    lines.append("  End of InsightIQ Preprocessing Report")
    lines.append(divider("="))

    return "\n".join(lines) + "\n"

def _date_feature_explanation(suffix: str) -> str:
    mapping = {
        "year":        "Calendar year — tracks long-term trends",
        "month":       "Month number (1–12) — captures seasonality",
        "month_name":  "Month name (January…December) — human-readable labels",
        "day":         "Day of month (1–31)",
        "weekday":     "Day name (Monday…Sunday) — weekly patterns",
        "quarter":     "Fiscal/calendar quarter (1–4)",
        "day_of_year": "Day of year (1–365) — fine-grained seasonal signal",
        "is_weekend":  "Weekend flag (1=Sat/Sun, 0=weekday) — behaviour segmentation",
    }
    return mapping.get(suffix, suffix)

@router.get(
    "/export/{session_id}/dataset-preview.csv",
    summary="Download a preview of the uploaded dataset as CSV",
    tags=["Export"],
)
async def export_dataset_preview(
    session_id: str,
    rows: int = Query(default=50, ge=1, le=500, description="Number of rows (1–500)"),
) -> StreamingResponse:
    _require_session(session_id)

    df = session_store.get_frame(f"{session_id}__clean")
    if df is None:
        df = session_store.get_frame(session_id)
    if df is None:
        raise HTTPException(status_code=500, detail="Dataset not found in session.")

    display_cols = [c for c in df.columns if not c.startswith("__")]
    df_display = df[display_cols].head(rows)

    filename = session_store.get_filename(session_id) or "dataset"
    stem = filename.replace(".csv", "")

    output = io.StringIO()
    df_display.to_csv(output, index=False)
    return _csv_response(output.getvalue(), f"{stem}_preview_{rows}rows.csv")

@router.get(
    "/export/{session_id}/cleaned-dataset.csv",
    summary="Download the fully preprocessed dataset as a CSV file",
    tags=["Export"],
)
async def export_cleaned_dataset(session_id: str) -> StreamingResponse:
    _require_session(session_id)
    _require_analysis(session_id)  # ensures preprocessing has run

    df = session_store.get_frame(f"{session_id}__clean")
    if df is None:
        raise HTTPException(
            status_code=404,
            detail="Cleaned dataset not found. Run analysis first.",
        )

    display_cols = [c for c in df.columns if not c.startswith("__")]
    df_export = df[display_cols]

    filename = session_store.get_filename(session_id) or "dataset"
    stem = filename.replace(".csv", "")

    output = io.StringIO()
    df_export.to_csv(output, index=False)
    return _csv_response(output.getvalue(), f"{stem}_cleaned.csv")