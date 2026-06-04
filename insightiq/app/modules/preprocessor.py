# Data cleaning pipeline: deduplication, imputation, normalisation, outlier flagging, date decomposition.

from __future__ import annotations

import re
import time
import uuid
import warnings
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from app.models.schemas import (
    DatasetProfile,
    DType,
    SemanticTag,
    TaskStatus,
    TaskTrace,
)

# Constants

HIGH_MISSING_DROP_THRESHOLD = 0.80   # drop column if > 80% missing
CASE_NORMALIZE_CARDINALITY_LIMIT = 50  # skip case-normalisation above this cardinality
OUTLIER_IQR_MILD = 1.5                # Tukey mild fence multiplier
OUTLIER_IQR_EXTREME = 3.0            # Tukey extreme fence multiplier
OUTLIER_ZSCORE_THRESHOLD = 3.0       # modified Z-score (Hampel identifier) threshold

# Strings that should be treated as missing values
_NULL_STRINGS = frozenset({
    "", "nan", "none", "null", "n/a", "na", "#n/a", "#na",
    "-", "--", "?", "missing", "unknown", "undefined", "not available",
    "not applicable", "na ", " na", "nil",
})

# Currency / formatting characters stripped before numeric coercion
_CURRENCY_RE = re.compile(r"[$£€¥₹₩₺₽,\s]+")
_TRAILING_PERCENT_RE = re.compile(r"%\s*$")

# Boolean value mapping
_BOOL_MAP: dict[str, int] = {
    "true": 1, "false": 0,
    "yes": 1,  "no": 0,
    "y": 1,    "n": 0,
    "t": 1,    "f": 0,
    "1": 1,    "0": 0,
    "on": 1,   "off": 0,
}

# Output contracts

@dataclass
class TransformationLog:
    """Records a single transformation applied to the DataFrame."""
    column: Optional[str]   # None = dataset-level operation
    operation: str          # e.g. "median_imputation"
    detail: str             # plain-language description
    rows_affected: int = 0
    fill_value: Optional[str] = None  # replacement value used (imputation only)

@dataclass
class PreprocessingReport:
    """
    Full audit trail of every transformation applied during preprocessing.
    Returned alongside the clean DataFrame so callers and users know exactly
    what was changed and why.
    """
    session_id: str
    original_shape: tuple[int, int]
    clean_shape: tuple[int, int]
    transformations: list[TransformationLog] = field(default_factory=list)
    columns_dropped: list[str] = field(default_factory=list)
    new_columns_added: list[str] = field(default_factory=list)
    outlier_flag_column: Optional[str] = None
    duplicates_removed: int = 0
    outlier_row_count: int = 0   # total rows flagged with __outlier_flag__ == 1
    execution_time_ms: int = 0
    task_trace: Optional[TaskTrace] = None

    def to_plain_summary(self) -> str:
        """Return a human-readable summary for non-technical users."""
        lines = []

        if self.duplicates_removed > 0:
            lines.append(
                f"Removed {self.duplicates_removed} duplicate row(s) — "
                "keeping only the first occurrence of each."
            )

        if self.columns_dropped:
            cols = ", ".join(f"'{c}'" for c in self.columns_dropped)
            lines.append(
                f"Removed {len(self.columns_dropped)} column(s) that were "
                f"almost entirely empty or had no variation: {cols}."
            )

        string_cleans = [t for t in self.transformations if t.operation == "string_cleaning"]
        if string_cleans:
            lines.append(
                f"Cleaned text in {len(string_cleans)} column(s): "
                "stripped extra whitespace and standardised null-like values."
            )

        case_norms = [t for t in self.transformations if t.operation == "case_normalisation"]
        if case_norms:
            lines.append(
                f"Standardised capitalisation in {len(case_norms)} column(s) "
                "to prevent duplicate groups (e.g. 'North' vs 'NORTH')."
            )

        bool_norms = [t for t in self.transformations if t.operation == "boolean_standardisation"]
        if bool_norms:
            lines.append(
                f"Converted {len(bool_norms)} Yes/No or True/False column(s) "
                "to 0/1 integers for analysis."
            )

        imputations = [t for t in self.transformations if "imputation" in t.operation]
        if imputations:
            total_filled = sum(t.rows_affected for t in imputations)
            lines.append(
                f"Filled {total_filled} missing value(s) across "
                f"{len(imputations)} column(s) using typical values."
            )

        date_decomps = [t for t in self.transformations if t.operation == "date_decomposition"]
        if date_decomps:
            lines.append(
                f"Extracted time components (year, month, weekday, quarter, "
                f"day of year, weekend flag) from {len(date_decomps)} date column(s)."
            )

        outlier_t = [t for t in self.transformations if t.operation == "outlier_flagging"]
        if outlier_t:
            mild_total = sum(t.rows_affected for t in outlier_t)
            extreme_logs = [t for t in self.transformations if t.operation == "extreme_outlier_flagging"]
            extreme_total = sum(t.rows_affected for t in extreme_logs)
            detail = f"Flagged {mild_total} row(s) with unusual numeric values"
            if extreme_total > 0:
                detail += f" ({extreme_total} classified as extreme outliers)"
            detail += ". They are kept in the data but marked for transparency."
            lines.append(detail)

        if not lines:
            lines.append("Your data was already clean — no changes were needed.")
        return " ".join(lines)

# Public entry point

def preprocess(
    df: pd.DataFrame,
    profile: DatasetProfile,
) -> tuple[pd.DataFrame, PreprocessingReport]:
    """
    Run the full 11-step industry-standard preprocessing pipeline.

    Parameters
    ----------
    df      : raw DataFrame from session store (not modified)
    profile : DatasetProfile from Phase 1 profiler

    Returns
    -------
    (clean_df, PreprocessingReport)
    clean_df is a new DataFrame — the original is never mutated.
    """
    start = time.time()
    clean = df.copy()
    logs: list[TransformationLog] = []
    dropped: list[str] = []
    added: list[str] = []
    outlier_col: Optional[str] = None
    duplicates_removed = 0

    # Build a lookup from column name → ColumnProfile
    col_meta = {c.name: c for c in profile.columns}

    # Step 1: Drop columns that are too sparse to be useful (> 80% missing)

    for col in list(clean.columns):
        meta = col_meta.get(col)
        if meta and meta.null_rate > HIGH_MISSING_DROP_THRESHOLD:
            clean = clean.drop(columns=[col])
            dropped.append(col)
            logs.append(TransformationLog(
                column=col,
                operation="column_dropped_sparse",
                detail=(
                    f"'{col}' removed — {meta.null_rate:.0%} of values were missing. "
                    "Columns with > 80% missing data cannot be reliably imputed."
                ),
            ))

    # Refresh col_meta after drops
    col_meta = {name: meta for name, meta in col_meta.items() if name in clean.columns}

    # Step 2: Remove exact duplicate rows

    n_before = len(clean)
    clean = clean.drop_duplicates()
    duplicates_removed = n_before - len(clean)
    if duplicates_removed > 0:
        clean = clean.reset_index(drop=True)
        logs.append(TransformationLog(
            column=None,
            operation="duplicate_removal",
            detail=(
                f"Removed {duplicates_removed} exact duplicate row(s). "
                "Kept the first occurrence of each; subsequent identical rows removed. "
                "Duplicate rows can skew averages and inflate counts."
            ),
            rows_affected=duplicates_removed,
        ))

    # Step 3: String normalisation — whitespace + null-like string handling

    for col in clean.columns:
        if clean[col].dtype != object:
            continue
        before_null = int(clean[col].isna().sum())
        original = clean[col].copy()

        # Strip whitespace and collapse multiple spaces (on non-null values)
        non_null_mask = original.notna()
        processed = original.copy()
        if non_null_mask.any():
            processed.loc[non_null_mask] = (
                original.loc[non_null_mask]
                .str.strip()
                .str.replace(r"\s+", " ", regex=True)
            )

        # Replace null-like string values with NaN
        # str.lower() on NaN → NaN, isin() on NaN → False → condition keeps NaN
        processed = processed.where(
            processed.isna() | ~processed.str.lower().isin(_NULL_STRINGS),
            other=np.nan,
        )

        after_null = int(processed.isna().sum())
        newly_null = after_null - before_null
        changed = int(
            (processed.notna() & original.notna() & (processed != original)).sum()
        )

        if newly_null > 0 or changed > 0:
            clean[col] = processed
            logs.append(TransformationLog(
                column=col,
                operation="string_cleaning",
                detail=(
                    f"Cleaned text in '{col}': stripped leading/trailing whitespace"
                    + (
                        f"; {newly_null} blank or null-like string(s) "
                        "('', 'N/A', 'none', '-', etc.) converted to missing values"
                        if newly_null > 0 else ""
                    ) + "."
                ),
                rows_affected=newly_null,
            ))

    # Step 4: Case normalisation for low-cardinality categoricals
    # Unifies "North"/"NORTH"/"north" into "North" to prevent spurious groups.
    # Only applied when case variants exist and cardinality ≤ limit.

    for col in clean.columns:
        meta = col_meta.get(col)
        if meta is None or meta.dtype not in (DType.categorical, DType.text):
            continue
        if clean[col].dtype != object:
            continue
        if meta.cardinality > CASE_NORMALIZE_CARDINALITY_LIMIT:
            continue

        non_null = clean[col].dropna()
        if len(non_null) == 0:
            continue

        unique_sensitive = non_null.nunique()
        unique_insensitive = non_null.str.lower().nunique()

        if unique_insensitive < unique_sensitive:
            # Case variants detected — standardise to title case
            clean[col] = clean[col].str.title()
            logs.append(TransformationLog(
                column=col,
                operation="case_normalisation",
                detail=(
                    f"Standardised '{col}' to title case — reduced "
                    f"{unique_sensitive} case variants to {unique_insensitive} "
                    "unique values. This prevents duplicate groups in analysis "
                    "(e.g. 'North' and 'NORTH' are now the same group)."
                ),
            ))

    # Step 5: Numeric coercion — string-encoded numbers
    # Handles: currency symbols ($1,234), comma-formatted numbers (1,234,567),
    # and columns profiled as numeric but stored as object dtype.

    for col in clean.columns:
        meta = col_meta.get(col)
        if meta is None or meta.dtype != DType.numeric:
            continue
        if not pd.api.types.is_numeric_dtype(clean[col]):
            before_nulls = int(clean[col].isna().sum())
            # Strip currency symbols, commas, whitespace then parse
            cleaned_str = (
                clean[col]
                .astype(str)
                .str.strip()
                .pipe(lambda s: s.str.replace(_CURRENCY_RE, "", regex=True))
            )
            coerced = pd.to_numeric(cleaned_str, errors="coerce")
            after_nulls = int(coerced.isna().sum())
            new_nulls = max(0, after_nulls - before_nulls)
            clean[col] = coerced
            logs.append(TransformationLog(
                column=col,
                operation="numeric_coercion",
                detail=(
                    f"Converted '{col}' to numeric (removed currency symbols / "
                    f"comma separators). "
                    + (f"{new_nulls} non-numeric value(s) became missing." if new_nulls > 0 else "")
                ),
                rows_affected=new_nulls,
            ))

    # Step 6: Datetime parsing

    for col in clean.columns:
        meta = col_meta.get(col)
        if meta is None or meta.dtype != DType.datetime:
            continue
        if pd.api.types.is_datetime64_any_dtype(clean[col]):
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            clean[col] = pd.to_datetime(clean[col], errors="coerce")
        logs.append(TransformationLog(
            column=col,
            operation="datetime_parsing",
            detail=f"Parsed '{col}' as a date/time column.",
        ))

    # Step 7: Boolean standardisation — True/False/Yes/No → 0/1 integer
    # Makes boolean columns directly usable in statistical analysis and ML.

    for col in clean.columns:
        meta = col_meta.get(col)
        if meta is None or meta.dtype != DType.boolean:
            continue

        if pd.api.types.is_bool_dtype(clean[col]):
            clean[col] = clean[col].astype("Int64")
            logs.append(TransformationLog(
                column=col,
                operation="boolean_standardisation",
                detail=f"Converted boolean '{col}' to 0/1 integer for analysis.",
                rows_affected=int(clean[col].notna().sum()),
            ))
        elif clean[col].dtype == object:
            lower_series = clean[col].str.lower()
            mapped = lower_series.map(_BOOL_MAP)
            non_null_mask = clean[col].notna()
            # Only apply if all non-null values were successfully mapped
            if non_null_mask.any() and mapped.loc[non_null_mask].notna().all():
                clean[col] = mapped
                logs.append(TransformationLog(
                    column=col,
                    operation="boolean_standardisation",
                    detail=(
                        f"Standardised '{col}' from text "
                        "(Yes/No/True/False/On/Off) to 0/1 integer."
                    ),
                    rows_affected=int(non_null_mask.sum()),
                ))

    # Step 8: Imputation
    # Numeric          → median  (robust to skew and outlier influence)
    # Categorical/text → mode    (most frequently observed value)
    # Datetime         → left as NaT with an audit note
    # Identifier cols  → NEVER imputed (would destroy uniqueness)

    for col in clean.columns:
        meta = col_meta.get(col)
        if meta is None:
            continue
        if meta.semantic_tag == SemanticTag.identifier:
            continue  # identifiers must not be imputed

        null_count = int(clean[col].isna().sum())
        if null_count == 0:
            continue

        if meta.dtype == DType.numeric or pd.api.types.is_numeric_dtype(clean[col]):
            fill_val = clean[col].median()
            if pd.isna(fill_val):
                continue
            clean[col] = clean[col].fillna(fill_val)
            logs.append(TransformationLog(
                column=col,
                operation="median_imputation",
                detail=(
                    f"Filled {null_count} missing value(s) in '{col}' "
                    f"with the column median ({fill_val:.4g}). "
                    "Median is preferred over mean because it is robust to outliers."
                ),
                rows_affected=null_count,
                fill_value=f"{fill_val:.4g}",
            ))

        elif meta.dtype in (DType.categorical, DType.boolean, DType.text):
            mode_series = clean[col].mode()
            if mode_series.empty:
                continue
            fill_val = mode_series.iloc[0]
            clean[col] = clean[col].fillna(fill_val)
            logs.append(TransformationLog(
                column=col,
                operation="mode_imputation",
                detail=(
                    f"Filled {null_count} missing value(s) in '{col}' "
                    f"with the most common value ('{fill_val}')."
                ),
                rows_affected=null_count,
                fill_value=str(fill_val),
            ))

        elif meta.dtype == DType.datetime:
            logs.append(TransformationLog(
                column=col,
                operation="datetime_missing_noted",
                detail=(
                    f"'{col}' has {null_count} missing date(s). "
                    "Datetime columns are not imputed — missing timestamps are "
                    "excluded from time-series analysis automatically."
                ),
                rows_affected=null_count,
            ))

    # Step 9: Constant column removal (after imputation)
    # After imputation, any column with a single unique value carries zero
    # analytical information and is removed.

    cols_to_drop_constant = []
    for col in list(clean.columns):
        if col.startswith("__"):
            continue
        meta = col_meta.get(col)
        if meta and meta.semantic_tag == SemanticTag.identifier:
            continue
        unique_count = int(clean[col].nunique(dropna=True))
        if unique_count <= 1:
            cols_to_drop_constant.append(col)

    for col in cols_to_drop_constant:
        unique_vals = clean[col].dropna().unique()
        val_str = str(unique_vals[0]) if len(unique_vals) > 0 else "all missing"
        clean = clean.drop(columns=[col])
        if col not in dropped:
            dropped.append(col)
        logs.append(TransformationLog(
            column=col,
            operation="constant_column_dropped",
            detail=(
                f"'{col}' removed — all values are identical ('{val_str}'). "
                "Zero-variance columns contribute nothing to statistical analysis or ML."
            ),
        ))

    # Refresh col_meta after constant-column drops
    col_meta = {name: meta for name, meta in col_meta.items() if name in clean.columns}

    # Step 10: Date decomposition
    # Extracts year, month (int), month_name, day, weekday, quarter,
    # day_of_year, and is_weekend as new integer/string columns.

    for col in list(clean.columns):
        meta = col_meta.get(col)
        if meta is None or meta.dtype != DType.datetime:
            continue
        if not pd.api.types.is_datetime64_any_dtype(clean[col]):
            continue
        new_cols = _decompose_date(clean, col)
        added.extend(new_cols)
        logs.append(TransformationLog(
            column=col,
            operation="date_decomposition",
            detail=(
                f"Extracted year, month, month_name, day, weekday, quarter, "
                f"day_of_year, and is_weekend from '{col}' as new columns. "
                "These features enable time-based grouping and trend analysis."
            ),
            rows_affected=len(clean),
        ))

    # Step 11: Two-tier outlier detection (IQR + modified Z-score)
    #
    # Tier 1 — Mild outliers   (IQR × 1.5, Tukey fence): values that are
    #   unusual but may still be legitimate data points.
    # Tier 2 — Extreme outliers (IQR × 3.0 OR modified Z-score > 3,
    #   Hampel identifier using MAD): values highly likely to be errors or
    #   truly anomalous events.
    #
    # Result columns:
    #   __outlier_flag__     : 0 = clean row, 1 = at least one mild or extreme outlier
    #   __outlier_severity__ : 0 = clean, 1 = mild, 2 = extreme
    #
    # Rows are NEVER removed — they are flagged for transparency.

    numeric_cols_for_outliers = [
        col for col in clean.columns
        if pd.api.types.is_numeric_dtype(clean[col])
        and col_meta.get(col) is not None
        and col_meta[col].semantic_tag != SemanticTag.identifier
        and not col.startswith("__")
    ]

    if numeric_cols_for_outliers:
        outlier_severity = pd.Series(0, index=clean.index, dtype=int)

        for col in numeric_cols_for_outliers:
            series = clean[col].dropna()
            if len(series) < 4:
                continue

            q1 = float(series.quantile(0.25))
            q3 = float(series.quantile(0.75))
            iqr = q3 - q1

            if iqr == 0:
                # Zero-IQR means constant column (already dropped above), skip
                continue

            mild_lower = q1 - OUTLIER_IQR_MILD * iqr
            mild_upper = q3 + OUTLIER_IQR_MILD * iqr
            extreme_lower = q1 - OUTLIER_IQR_EXTREME * iqr
            extreme_upper = q3 + OUTLIER_IQR_EXTREME * iqr

            # Modified Z-score (Hampel identifier — robust to non-normal distributions)
            median_val = float(series.median())
            mad = float((series - median_val).abs().median())
            if mad > 0:
                modified_z = 0.6745 * (clean[col] - median_val) / mad
            else:
                modified_z = pd.Series(0.0, index=clean.index)

            not_null = clean[col].notna()
            mild_mask = not_null & (
                (clean[col] < mild_lower) | (clean[col] > mild_upper)
            )
            extreme_mask = not_null & (
                (clean[col] < extreme_lower)
                | (clean[col] > extreme_upper)
                | (modified_z.abs() > OUTLIER_ZSCORE_THRESHOLD)
            )

            # Update severity map: extreme (2) overrides mild (1)
            outlier_severity = outlier_severity.mask(
                mild_mask & (outlier_severity < 1), 1
            )
            outlier_severity = outlier_severity.mask(
                extreme_mask & (outlier_severity < 2), 2
            )

            mild_count = int(mild_mask.sum())
            extreme_count = int(extreme_mask.sum())

            if mild_count > 0:
                logs.append(TransformationLog(
                    column=col,
                    operation="outlier_flagging",
                    detail=(
                        f"Found {mild_count} unusual value(s) in '{col}' "
                        f"(outside Tukey fence {mild_lower:.4g}–{mild_upper:.4g})"
                        + (
                            f"; {extreme_count} classified as extreme "
                            f"(IQR×3 or modified Z-score > {OUTLIER_ZSCORE_THRESHOLD})"
                            if extreme_count > 0 else ""
                        ) + "."
                    ),
                    rows_affected=mild_count,
                ))
                if extreme_count > 0:
                    logs.append(TransformationLog(
                        column=col,
                        operation="extreme_outlier_flagging",
                        detail=(
                            f"{extreme_count} extreme outlier(s) in '{col}' "
                            f"detected by both IQR×3 fence "
                            f"({extreme_lower:.4g}–{extreme_upper:.4g}) and "
                            f"modified Z-score (MAD-based, threshold={OUTLIER_ZSCORE_THRESHOLD})."
                        ),
                        rows_affected=extreme_count,
                    ))

        # Write flag columns to clean DataFrame (backward-compatible + new severity)
        clean["__outlier_flag__"] = (outlier_severity > 0).astype(int)
        clean["__outlier_severity__"] = outlier_severity
        outlier_col = "__outlier_flag__"
        added.extend(["__outlier_flag__", "__outlier_severity__"])
        _outlier_row_count = int((outlier_severity > 0).sum())

    elapsed_ms = int((time.time() - start) * 1000)
    try:
        _outlier_row_count
    except NameError:
        _outlier_row_count = 0

    trace = TaskTrace(
        task_id=f"preprocess_{uuid.uuid4().hex[:8]}",
        module="preprocessor",
        operation="full_preprocessing_pipeline",
        columns_used=list(df.columns),
        trigger_reason="Runs automatically after every upload before statistical analysis.",
        plain_explanation=_build_plain_explanation(logs, duplicates_removed),
        execution_time_ms=elapsed_ms,
        status=TaskStatus.completed,
    )

    report = PreprocessingReport(
        session_id=profile.session_id,
        original_shape=df.shape,
        clean_shape=clean.shape,
        transformations=logs,
        columns_dropped=dropped,
        new_columns_added=added,
        outlier_flag_column=outlier_col,
        duplicates_removed=duplicates_removed,
        outlier_row_count=_outlier_row_count,
        execution_time_ms=elapsed_ms,
        task_trace=trace,
    )

    return clean, report

# Helpers

def _decompose_date(df: pd.DataFrame, col: str) -> list[str]:
    """
    Derive temporal feature columns from a parsed datetime column.
    Adds: year, month, month_name, day, weekday, quarter, day_of_year, is_weekend.
    Returns the list of new column names added.
    """
    prefix = col

    df[f"{prefix}__year"] = df[col].dt.year
    df[f"{prefix}__month"] = df[col].dt.month
    df[f"{prefix}__month_name"] = df[col].dt.month_name()
    df[f"{prefix}__day"] = df[col].dt.day
    df[f"{prefix}__weekday"] = df[col].dt.day_name()
    df[f"{prefix}__quarter"] = df[col].dt.quarter
    df[f"{prefix}__day_of_year"] = df[col].dt.day_of_year
    df[f"{prefix}__is_weekend"] = df[col].dt.dayofweek.isin([5, 6]).astype(int)

    return [
        f"{prefix}__year",
        f"{prefix}__month",
        f"{prefix}__month_name",
        f"{prefix}__day",
        f"{prefix}__weekday",
        f"{prefix}__quarter",
        f"{prefix}__day_of_year",
        f"{prefix}__is_weekend",
    ]

def _build_plain_explanation(
    logs: list[TransformationLog],
    duplicates_removed: int,
) -> str:
    """Summarise the transformation log in one plain sentence."""
    ops = {t.operation for t in logs}
    parts = []

    if duplicates_removed > 0:
        parts.append(f"removed {duplicates_removed} duplicate row(s)")
    if "column_dropped_sparse" in ops:
        parts.append("removed extremely sparse columns")
    if "constant_column_dropped" in ops:
        parts.append("removed zero-variance columns")
    if "string_cleaning" in ops:
        parts.append("cleaned string values")
    if "case_normalisation" in ops:
        parts.append("normalised capitalisation")
    if "numeric_coercion" in ops:
        parts.append("parsed string-encoded numbers")
    if "boolean_standardisation" in ops:
        parts.append("standardised boolean columns to 0/1")
    if "median_imputation" in ops or "mode_imputation" in ops:
        parts.append("filled missing values (median / mode)")
    if "date_decomposition" in ops:
        parts.append("extracted time components from date columns")
    if "outlier_flagging" in ops:
        parts.append("flagged unusual values (two-tier IQR + Z-score)")

    if not parts:
        return "Data was already clean — no transformations were needed."
    return "Preprocessing: " + ", ".join(parts) + "."
