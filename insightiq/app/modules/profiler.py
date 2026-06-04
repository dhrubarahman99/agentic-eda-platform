# Profiles an uploaded DataFrame: column types, stats, quality flags, and ML eligibility.

from __future__ import annotations

import re
import uuid
import warnings
from typing import Any, Optional

import numpy as np
import pandas as pd

from app.models.schemas import (
    ColumnProfile,
    DataQualityFlag,
    DataQualityStatus,
    DatasetProfile,
    DatasetSummaryCard,
    DescriptiveStats,
    DType,
    FlagType,
    GuidedStartItem,
    QualityStatus,
    QuickAction,
    SemanticTag,
    Severity,
)

# Constants / thresholds

HIGH_MISSING_THRESHOLD = 0.30        # null_rate > 30%  → flag
HIGH_CARDINALITY_THRESHOLD = 50      # unique values    → not useful for groupby
MIN_ROWS_FOR_ML = 20
MIN_NUMERIC_FOR_ML = 2
LOW_VARIANCE_CV_THRESHOLD = 0.01     # coefficient of variation
OUTLIER_IQR_MULTIPLIER = 1.5

# Column name patterns used for semantic tagging
_DATE_PATTERNS = re.compile(
    r"(date|time|timestamp|month|year|day|week|quarter|period|dt|_at$|_on$)",
    re.IGNORECASE,
)
_QUANTITY_PATTERNS = re.compile(
    r"(revenue|sales|amount|total|price|cost|profit|income|spend|count|qty"
    r"|quantity|volume|units|orders|value|score|rate|fee|salary|budget|expense"
    r"|bmi|risk|pollution|temp|energy|demand|inventory|visits|tickets|margin"
    r"|reading|index|consumption|satisfaction)",
    re.IGNORECASE,
)
_CATEGORY_PATTERNS = re.compile(
    r"(category|type|status|region|country|city|state|department|product"
    r"|segment|group|class|label|gender|tier|brand|channel|condition|weather"
    r"|description|issue|comment|name$)",
    re.IGNORECASE,
)
_ID_PATTERNS = re.compile(
    r"(^id$|_id$|^uuid|^key$|^index$|^row)",
    re.IGNORECASE,
)

# Binary column: numeric column whose only valid values are two distinct integers/floats
# (e.g. 0/1, 1/2). Cardinality == 2 and both values are whole numbers.
_BINARY_CARDINALITY_LIMIT = 2

# Public entry point

def profile_dataset(df: pd.DataFrame, session_id: str) -> DatasetProfile:
    """
    Run the full profiling pipeline on a DataFrame.
    Returns a DatasetProfile with all fields populated.
    """
    columns: list[ColumnProfile] = []
    quality_flags: list[DataQualityFlag] = []

    for col in df.columns:
        series = df[col]
        col_profile = _profile_column(series, quality_flags)
        columns.append(col_profile)

    # Dataset-level small sample flag
    if len(df) < MIN_ROWS_FOR_ML:
        quality_flags.append(DataQualityFlag(
            column=None,
            flag_type=FlagType.small_sample,
            severity=Severity.medium,
            message=(
                f"Your dataset has only {len(df)} rows. "
                "Some analyses work best with 100 or more rows."
            ),
        ))

    numeric_cols = [c.name for c in columns if c.dtype == DType.numeric]
    categorical_cols = [c.name for c in columns if c.dtype == DType.categorical]
    datetime_cols = [c.name for c in columns if c.dtype == DType.datetime]
    binary_cols = [c.name for c in columns if c.is_binary]

    potential_target = _detect_target(columns, df)
    # Binary (boolean) cols are valid numeric inputs for ML models (0/1 values),
    # so count them together with numeric cols when assessing ML eligibility.
    ml_eligible = (
        len(df) >= MIN_ROWS_FOR_ML
        and (len(numeric_cols) + len(binary_cols)) >= MIN_NUMERIC_FOR_ML
    )

    data_quality = _build_quality_status(quality_flags)
    summary_card = _build_summary_card(
        df, columns, numeric_cols, categorical_cols,
        datetime_cols, potential_target, data_quality.overall,
    )
    quick_actions = _build_quick_actions(
        numeric_cols, categorical_cols, datetime_cols,
        summary_card.columns_with_high_missing, ml_eligible, potential_target,
    )
    guided_start = _build_guided_start(
        numeric_cols, categorical_cols, datetime_cols,
        summary_card.columns_with_high_missing, ml_eligible, potential_target,
        quick_actions,
    )

    return DatasetProfile(
        session_id=session_id,
        shape={"rows": len(df), "cols": len(df.columns)},
        columns=columns,
        numeric_columns=numeric_cols,
        categorical_columns=categorical_cols,
        datetime_columns=datetime_cols,
        binary_columns=binary_cols,
        potential_target=potential_target,
        has_datetime=len(datetime_cols) > 0,
        ml_eligible=ml_eligible,
        summary_card=summary_card,
        quick_actions=quick_actions,
        guided_start=guided_start,
        data_quality=data_quality,
    )

# Column-level profiling

def _normalize_column_alias(name: str) -> str:
    """
    Produce a search-friendly alias from a raw column name.
    Used by the column mapper to match noisy names like "Revenue($)" or "Avg-Cost".

    Steps:
      1. lowercase
      2. strip currency/unit symbols  ($, £, €, %, #, @, !, ?)
      3. normalise separators (spaces, hyphens, dots, slashes) → single underscore
      4. collapse repeated underscores and strip leading/trailing underscores
    """
    alias = str(name).lower()
    alias = re.sub(r"[$£€%#@!?()[\]{}]", "", alias)   # remove currency/unit chars
    alias = re.sub(r"[\s\-./\\]+", "_", alias)          # separators → underscore
    alias = re.sub(r"_+", "_", alias).strip("_")        # collapse repeated underscores
    return alias

def _profile_column(
    series: pd.Series,
    quality_flags: list[DataQualityFlag],
) -> ColumnProfile:
    name = series.name
    null_count = int(series.isna().sum())
    null_rate = round(null_count / max(len(series), 1), 4)
    cardinality = int(series.nunique(dropna=True))

    # Infer dtype and semantic tag
    dtype = _infer_dtype(series)
    semantic_tag = _infer_semantic_tag(name, dtype, cardinality, len(series))

    # Detect binary column: numeric dtype with exactly 2 distinct non-null values
    # whose unique values are a subset of {0, 1} or any pair of integers.
    # This prevents binary flags from being treated as continuous metrics.
    is_binary = False
    if dtype == DType.numeric and cardinality == _BINARY_CARDINALITY_LIMIT:
        coerced = pd.to_numeric(series, errors="coerce").dropna()
        unique_vals = set(coerced.unique())
        # Accept 0/1 or any two-value integer pair (e.g. 1/2, -1/1)
        if all(float(v).is_integer() for v in unique_vals):
            is_binary = True

    # Binary columns are reclassified as boolean so they group with categoricals
    # in the explorer and get value-count display instead of numeric stats.
    if is_binary:
        dtype = DType.boolean

    # Normalised alias for fuzzy column matching
    normalized_alias = _normalize_column_alias(name)

    # Sample values — up to 5 unique non-null
    sample_values = _get_sample_values(series)

    # Stats and outlier detection for numeric columns
    stats: Optional[DescriptiveStats] = None
    has_outliers = False
    outlier_count: Optional[int] = None

    if dtype == DType.numeric:
        stats, has_outliers, outlier_count = _numeric_stats(series)

        # Skip outlier flags for binary columns — all values are by definition "extreme"
        # relative to IQR when the column is 0/1.
        if not is_binary and has_outliers and outlier_count and outlier_count > 0:
            quality_flags.append(DataQualityFlag(
                column=str(name),
                flag_type=FlagType.outliers_detected,
                severity=Severity.low,
                message=(
                    f"The column '{name}' has {outlier_count} unusual values "
                    "that are much higher or lower than the rest. "
                    "These may affect averages and trends."
                ),
            ))

        # Low variance flag
        if stats and stats.std is not None and stats.mean and stats.mean != 0:
            cv = abs(stats.std / stats.mean)
            if cv < LOW_VARIANCE_CV_THRESHOLD:
                quality_flags.append(DataQualityFlag(
                    column=str(name),
                    flag_type=FlagType.low_variance,
                    severity=Severity.low,
                    message=(
                        f"The column '{name}' has very little variation. "
                        "It may not be useful for analysis."
                    ),
                ))

    # High missing values flag
    if null_rate > HIGH_MISSING_THRESHOLD:
        quality_flags.append(DataQualityFlag(
            column=str(name),
            flag_type=FlagType.high_missing,
            severity=Severity.high if null_rate > 0.6 else Severity.medium,
            message=(
                f"'{name}' is missing {null_rate:.0%} of its values. "
                "Results using this column may not be reliable."
            ),
        ))

    # High cardinality flag for categoricals
    if dtype == DType.categorical and cardinality > HIGH_CARDINALITY_THRESHOLD:
        quality_flags.append(DataQualityFlag(
            column=str(name),
            flag_type=FlagType.high_cardinality,
            severity=Severity.low,
            message=(
                f"'{name}' has {cardinality} unique values, which is quite high. "
                "It may not group well."
            ),
        ))

    return ColumnProfile(
        name=str(name),
        dtype=dtype,
        semantic_tag=semantic_tag,
        null_rate=null_rate,
        null_count=null_count,
        cardinality=cardinality,
        stats=stats,
        has_outliers=has_outliers,
        outlier_count=outlier_count,
        sample_values=sample_values,
        is_binary=is_binary,
        normalized_alias=normalized_alias,
    )

# Type inference

def _infer_dtype(series: pd.Series) -> DType:
    """
    Infer the logical data type of a column.
    Tries numeric coercion first, then datetime, then boolean, then categorical.
    """
    non_null = series.dropna()
    if len(non_null) == 0:
        return DType.categorical

    # Already numeric
    if pd.api.types.is_numeric_dtype(series):
        return DType.numeric

    # Already boolean
    if pd.api.types.is_bool_dtype(series):
        return DType.boolean

    # Already datetime
    if pd.api.types.is_datetime64_any_dtype(series):
        return DType.datetime

    # Try coercing to numeric
    coerced_num = pd.to_numeric(non_null, errors="coerce")
    if coerced_num.notna().sum() / len(non_null) > 0.85:
        return DType.numeric

    # Try coercing to datetime
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            coerced_dt = pd.to_datetime(non_null, infer_datetime_format=True, errors="coerce")
        if coerced_dt.notna().sum() / len(non_null) > 0.80:
            return DType.datetime
    except Exception:
        pass

    # Boolean-like strings
    bool_vals = {"true", "false", "yes", "no", "1", "0", "t", "f"}
    str_vals = set(non_null.astype(str).str.lower().unique())
    if str_vals.issubset(bool_vals):
        return DType.boolean

    # Long free text (avg length > 50 chars → treat as text)
    avg_len = non_null.astype(str).str.len().mean()
    if avg_len > 50:
        return DType.text

    return DType.categorical

# Semantic tag inference

def _infer_semantic_tag(
    name: str,
    dtype: DType,
    cardinality: int,
    total_rows: int,
) -> SemanticTag:
    """Assign a semantic role based on column name patterns and type."""

    name_str = str(name)

    if _ID_PATTERNS.search(name_str):
        return SemanticTag.identifier

    if dtype == DType.datetime or _DATE_PATTERNS.search(name_str):
        return SemanticTag.date

    if dtype == DType.numeric:
        if _QUANTITY_PATTERNS.search(name_str):
            return SemanticTag.quantity
        # Numeric columns with low cardinality might be ordinal/label
        if cardinality <= 10 and total_rows > 20:
            return SemanticTag.category
        return SemanticTag.quantity    # default for numeric

    if dtype in (DType.categorical, DType.boolean, DType.text):
        if _CATEGORY_PATTERNS.search(name_str):
            return SemanticTag.category
        return SemanticTag.category    # default for categorical

    return SemanticTag.unknown

# Numeric stats and outlier detection

def _numeric_stats(
    series: pd.Series,
) -> tuple[Optional[DescriptiveStats], bool, Optional[int]]:
    """
    Compute descriptive statistics and detect outliers via IQR method.
    Returns (DescriptiveStats | None, has_outliers, outlier_count).
    """
    coerced = pd.to_numeric(series, errors="coerce").dropna().astype(float)
    if len(coerced) < 2:
        return None, False, None

    q1 = float(coerced.quantile(0.25))
    q3 = float(coerced.quantile(0.75))
    iqr = q3 - q1
    lower = q1 - OUTLIER_IQR_MULTIPLIER * iqr
    upper = q3 + OUTLIER_IQR_MULTIPLIER * iqr

    outlier_mask = (coerced < lower) | (coerced > upper)
    outlier_count = int(outlier_mask.sum())
    has_outliers = outlier_count > 0

    stats = DescriptiveStats(
        mean=round(float(coerced.mean()), 4),
        median=round(float(coerced.median()), 4),
        std=round(float(coerced.std()), 4),
        min=round(float(coerced.min()), 4),
        max=round(float(coerced.max()), 4),
        q1=round(q1, 4),
        q3=round(q3, 4),
    )
    return stats, has_outliers, outlier_count

# Sample values

def _get_sample_values(series: pd.Series) -> list[Any]:
    """Return up to 5 unique non-null values, coerced to JSON-safe types."""
    non_null = series.dropna()
    if len(non_null) == 0:
        return []
    unique_vals = non_null.unique()[:5]
    safe = []
    for v in unique_vals:
        if isinstance(v, (np.integer,)):
            safe.append(int(v))
        elif isinstance(v, (np.floating,)):
            safe.append(round(float(v), 4))
        elif isinstance(v, (np.bool_,)):
            safe.append(bool(v))
        else:
            safe.append(str(v))
    return safe

# Potential target variable detection

def _detect_target(
    columns: list[ColumnProfile],
    df: pd.DataFrame,
) -> Optional[str]:
    """
    Heuristic: the most likely target is a numeric quantity column
    that is not an identifier and has moderate variance.
    Prefer columns whose name matches quantity patterns.
    """
    candidates = [
        c for c in columns
        if c.dtype == DType.numeric
        and c.semantic_tag == SemanticTag.quantity
        and c.null_rate < 0.3
        and c.stats is not None
        and c.stats.std > 0
    ]
    if not candidates:
        return None

    # Prefer columns whose name is explicitly revenue/sales/profit
    priority_patterns = re.compile(
        r"(revenue|profit|sales|income|amount|total)", re.IGNORECASE
    )
    priority = [c for c in candidates if priority_patterns.search(c.name)]
    return (priority or candidates)[0].name

# Quality status

def _build_quality_status(flags: list[DataQualityFlag]) -> DataQualityStatus:
    if not flags:
        return DataQualityStatus(overall=QualityStatus.good, flags=[])

    has_high = any(f.severity == Severity.high for f in flags)
    has_medium = any(f.severity == Severity.medium for f in flags)

    if has_high:
        overall = QualityStatus.poor
    elif has_medium:
        overall = QualityStatus.fair
    else:
        overall = QualityStatus.good

    return DataQualityStatus(overall=overall, flags=flags)

# Dataset summary card

def _build_summary_card(
    df: pd.DataFrame,
    columns: list[ColumnProfile],
    numeric_cols: list[str],
    categorical_cols: list[str],
    datetime_cols: list[str],
    potential_target: Optional[str],
    quality_status: QualityStatus,
) -> DatasetSummaryCard:
    total_cells = df.shape[0] * df.shape[1]
    total_missing = int(df.isna().sum().sum())
    missing_rate = round(total_missing / max(total_cells, 1), 4)

    high_missing_cols = [
        c.name for c in columns if c.null_rate > HIGH_MISSING_THRESHOLD
    ]

    # Important columns: low null rate + high semantic weight
    important = [
        c.name for c in columns
        if c.semantic_tag in (SemanticTag.quantity, SemanticTag.date)
        and c.null_rate < 0.1
    ]

    quality_note = _quality_note(quality_status, high_missing_cols, len(df))

    duplicate_row_count = int(df.duplicated().sum())

    return DatasetSummaryCard(
        row_count=len(df),
        col_count=len(df.columns),
        numeric_col_count=len(numeric_cols),
        categorical_col_count=len(categorical_cols),
        datetime_col_count=len(datetime_cols),
        total_missing_cells=total_missing,
        missing_rate_overall=missing_rate,
        columns_with_high_missing=high_missing_cols,
        detected_important_columns=important,
        potential_target_column=potential_target,
        quality_status=quality_status,
        quality_note=quality_note,
        duplicate_row_count=duplicate_row_count,
    )

def _quality_note(
    status: QualityStatus,
    high_missing: list[str],
    row_count: int,
) -> str:
    parts = []
    if high_missing:
        cols_str = ", ".join(f"'{c}'" for c in high_missing[:3])
        parts.append(f"{len(high_missing)} column(s) have significant missing data ({cols_str})")
    if row_count < MIN_ROWS_FOR_ML:
        parts.append(f"only {row_count} rows — some analyses may be limited")
    if not parts:
        return "Your dataset looks clean and ready for analysis."
    return "Note: " + "; ".join(parts) + "."

# Quick actions

_METRIC_PREF_KEYWORDS = [
    "revenue", "profit", "sales", "cost", "spend", "margin",
    "amount", "price", "income", "units", "score", "satisfaction",
    "value", "total", "quantity", "qty", "orders",
]
_AVOID_AS_DEFAULT_METRIC = ["age", "_id", "index", "code", "zip", "number"]

def _best_metric_col(numeric_cols: list[str]) -> str:
    """Return the most suitable business metric from a numeric column list.

    Prefers revenue/profit/sales-style columns over demographic ones like age.
    """
    if len(numeric_cols) == 1:
        return numeric_cols[0]
    for kw in _METRIC_PREF_KEYWORDS:
        for col in numeric_cols:
            if kw in col.lower():
                return col
    for avoid in _AVOID_AS_DEFAULT_METRIC:
        non_avoid = [c for c in numeric_cols if avoid not in c.lower()]
        if non_avoid:
            return non_avoid[0]
    return numeric_cols[0]

def _build_quick_actions(
    numeric_cols: list[str],
    categorical_cols: list[str],
    datetime_cols: list[str],
    high_missing_cols: list[str],
    ml_eligible: bool,
    potential_target: Optional[str],
) -> list[QuickAction]:
    actions: list[QuickAction] = []
    priority = 1

    if numeric_cols:
        actions.append(QuickAction(
            action_id=f"qa_{uuid.uuid4().hex[:8]}",
            label="Show numeric summary",
            description="See the key statistics for all numeric columns in your dataset.",
            intent="distribution",
            pre_mapped_columns=numeric_cols,
            trigger_condition="Numeric columns detected",
            priority=priority,
        ))
        priority += 1

    if len(numeric_cols) >= 2:
        actions.append(QuickAction(
            action_id=f"qa_{uuid.uuid4().hex[:8]}",
            label="Find strongest correlations",
            description="Discover which columns are most closely related to each other.",
            intent="correlation",
            pre_mapped_columns=numeric_cols,
            trigger_condition="Two or more numeric columns detected",
            priority=priority,
        ))
        priority += 1

    if datetime_cols and numeric_cols:
        actions.append(QuickAction(
            action_id=f"qa_{uuid.uuid4().hex[:8]}",
            label="Show trend over time",
            description="See how your numeric values change across time.",
            intent="trend",
            pre_mapped_columns=datetime_cols + [_best_metric_col(numeric_cols)],
            trigger_condition="Date column and numeric column detected",
            priority=priority,
        ))
        priority += 1

    if categorical_cols and numeric_cols:
        actions.append(QuickAction(
            action_id=f"qa_{uuid.uuid4().hex[:8]}",
            label="Compare categories",
            description=f"Compare totals across groups in '{categorical_cols[0]}'.",
            intent="comparison",
            pre_mapped_columns=[categorical_cols[0], _best_metric_col(numeric_cols)],
            trigger_condition="Categorical and numeric columns detected",
            priority=priority,
        ))
        priority += 1

    if high_missing_cols:
        actions.append(QuickAction(
            action_id=f"qa_{uuid.uuid4().hex[:8]}",
            label="Show missing data summary",
            description="See which columns have gaps in your data.",
            intent="missing_data",
            pre_mapped_columns=high_missing_cols,
            trigger_condition="Columns with high missing values detected",
            priority=priority,
        ))
        priority += 1

    if ml_eligible and potential_target:
        actions.append(QuickAction(
            action_id=f"qa_{uuid.uuid4().hex[:8]}",
            label=f"Find what drives '{potential_target}'",
            description=f"Discover which factors most influence '{potential_target}'.",
            intent="feature_importance",
            pre_mapped_columns=[potential_target] + [
                c for c in numeric_cols if c != potential_target
            ],
            trigger_condition=f"ML-eligible dataset with target column '{potential_target}'",
            priority=priority,
        ))
        priority += 1

    return actions

# Guided start panel

def _build_guided_start(
    numeric_cols: list[str],
    categorical_cols: list[str],
    datetime_cols: list[str],
    high_missing_cols: list[str],
    ml_eligible: bool,
    potential_target: Optional[str],
    quick_actions: list[QuickAction],
) -> list[GuidedStartItem]:
    items: list[GuidedStartItem] = []
    priority = 1

    # Map action labels to IDs for cross-linking
    action_map = {a.label: a.action_id for a in quick_actions}

    if high_missing_cols:
        items.append(GuidedStartItem(
            item_id=f"gs_{uuid.uuid4().hex[:8]}",
            label="Start by checking missing data",
            reasoning=(
                f"{len(high_missing_cols)} column(s) have gaps that may affect results."
            ),
            maps_to_action_id=action_map.get("Show missing data summary"),
            priority=priority,
        ))
        priority += 1

    if datetime_cols and numeric_cols:
        items.append(GuidedStartItem(
            item_id=f"gs_{uuid.uuid4().hex[:8]}",
            label="Explore trends over time",
            reasoning="A date column was detected — time-based patterns may be valuable.",
            maps_to_action_id=action_map.get("Show trend over time"),
            priority=priority,
        ))
        priority += 1

    if ml_eligible and potential_target:
        items.append(GuidedStartItem(
            item_id=f"gs_{uuid.uuid4().hex[:8]}",
            label=f"Find what affects '{potential_target}'",
            reasoning=(
                f"'{potential_target}' looks like a key outcome column. "
                "You can discover what drives it."
            ),
            maps_to_action_id=action_map.get(f"Find what drives '{potential_target}'"),
            priority=priority,
        ))
        priority += 1

    if categorical_cols and numeric_cols:
        items.append(GuidedStartItem(
            item_id=f"gs_{uuid.uuid4().hex[:8]}",
            label="Compare categories",
            reasoning=(
                f"You have category columns like '{categorical_cols[0]}'. "
                "Comparing them against numeric values can reveal patterns."
            ),
            maps_to_action_id=action_map.get("Compare categories"),
            priority=priority,
        ))
        priority += 1

    if len(numeric_cols) >= 2:
        items.append(GuidedStartItem(
            item_id=f"gs_{uuid.uuid4().hex[:8]}",
            label="View top insights",
            reasoning="Let the system automatically find the most interesting patterns.",
            maps_to_action_id=None,
            priority=priority,
        ))
        priority += 1

    return items
