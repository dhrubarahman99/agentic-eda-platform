# Pydantic data contracts shared across all modules and API responses.

from __future__ import annotations
from enum import Enum
from typing import Any, Optional, Union
from pydantic import BaseModel, Field

class DType(str, Enum):
    numeric = "numeric"
    categorical = "categorical"
    datetime = "datetime"
    boolean = "boolean"
    text = "text"

class SemanticTag(str, Enum):
    quantity = "quantity"
    category = "category"
    date = "date"
    identifier = "identifier"
    unknown = "unknown"

class QualityStatus(str, Enum):
    good = "good"
    fair = "fair"
    poor = "poor"

class FlagType(str, Enum):
    high_missing = "high_missing"
    small_sample = "small_sample"
    outliers_detected = "outliers_detected"
    high_cardinality = "high_cardinality"
    low_variance = "low_variance"

class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"

class ChartType(str, Enum):
    bar = "bar"
    line = "line"
    scatter = "scatter"
    pie = "pie"
    histogram = "histogram"
    radar = "radar"
    bubble = "bubble"

class InsightType(str, Enum):
    trend = "trend"
    correlation = "correlation"
    segment = "segment"
    anomaly = "anomaly"
    ranking = "ranking"
    distribution = "distribution"
    missing_data = "missing_data"
    summary = "summary"

class TaskStatus(str, Enum):
    completed = "completed"
    failed = "failed"
    skipped = "skipped"

class ErrorType(str, Enum):
    mismatch = "mismatch"
    ambiguity = "ambiguity"
    unsupported = "unsupported"
    low_confidence = "low_confidence"
    data_quality = "data_quality"
    parse_failure = "parse_failure"
    upload_error = "upload_error"

class QueryStatus(str, Enum):
    success = "success"
    error = "error"
    ambiguous = "ambiguous"
    low_confidence = "low_confidence"

class WarningType(str, Enum):
    high_missing = "high_missing"
    small_sample = "small_sample"
    outlier_influence = "outlier_influence"
    weak_model = "weak_model"
    low_query_confidence = "low_query_confidence"
    partial_data = "partial_data"

class QueryIntent(str, Enum):
    ranking = "ranking"
    trend = "trend"
    correlation = "correlation"
    distribution = "distribution"
    missing_data = "missing_data"
    aggregation = "aggregation"
    comparison = "comparison"
    feature_importance = "feature_importance"
    unknown = "unknown"
    targeted_correlation = "targeted_correlation"
    compound_filter = "compound_filter"
    derived_metric = "derived_metric"
    period_growth = "period_growth"
    anomaly_query = "anomaly_query"
    multi_criteria_rank = "multi_criteria_rank"
    business_decision = "business_decision"
    scenario_analysis = "scenario_analysis"
    open_ended_insight = "open_ended_insight"
    segment_comparison = "segment_comparison"
    threshold_analysis = "threshold_analysis"
    seasonal_pattern = "seasonal_pattern"
    combination_ranking = "combination_ranking"
    efficiency_query = "efficiency_query"

class DescriptiveStats(BaseModel):
    mean: float
    median: float
    std: float
    min: float
    max: float
    q1: float
    q3: float

class DataQualityFlag(BaseModel):
    column: Optional[str] = None          # None = dataset-level flag
    flag_type: FlagType
    severity: Severity
    message: str                          # plain-language, non-technical

class DataQualityStatus(BaseModel):
    overall: QualityStatus
    flags: list[DataQualityFlag] = Field(default_factory=list)

class ColumnProfile(BaseModel):
    name: str
    dtype: DType
    semantic_tag: SemanticTag
    null_rate: float                      # 0.0–1.0
    null_count: int
    cardinality: int
    stats: Optional[DescriptiveStats] = None   # numeric columns only
    has_outliers: bool = False
    outlier_count: Optional[int] = None
    sample_values: list[Any] = Field(default_factory=list)  # up to 5 unique non-null values
    is_binary: bool = False               # True when column has exactly 2 distinct values (e.g. 0/1)
    normalized_alias: str = ""            # symbol/space/case-stripped alias for fuzzy matching

class DatasetSummaryCard(BaseModel):
    row_count: int
    col_count: int
    numeric_col_count: int
    categorical_col_count: int
    datetime_col_count: int
    total_missing_cells: int
    missing_rate_overall: float
    columns_with_high_missing: list[str] = Field(default_factory=list)
    detected_important_columns: list[str] = Field(default_factory=list)
    potential_target_column: Optional[str] = None
    quality_status: QualityStatus
    quality_note: str
    duplicate_row_count: int = 0

class QuickAction(BaseModel):
    action_id: str
    label: str
    description: str
    intent: str
    pre_mapped_columns: list[str] = Field(default_factory=list)
    trigger_condition: str
    priority: int

class GuidedStartItem(BaseModel):
    item_id: str
    label: str
    reasoning: str
    maps_to_action_id: Optional[str] = None
    priority: int

class ChartDataPoint(BaseModel):
    label: Union[str, float, int]
    value: float
    group: Optional[str] = None

class ChartSpec(BaseModel):
    chart_type: ChartType
    title: str
    x_axis_label: Optional[str] = None
    y_axis_label: Optional[str] = None
    x_field: str
    y_field: Optional[str] = None
    group_field: Optional[str] = None
    data: list[ChartDataPoint] = Field(default_factory=list)
    color_scheme: Optional[str] = None   # "sequential" | "categorical"

class SuggestedFollowUp(BaseModel):
    followup_id: str
    question_text: str
    reasoning: str
    pre_mapped_intent: Optional[str] = None
    pre_mapped_columns: list[str] = Field(default_factory=list)
    priority: int

class ReliabilityWarning(BaseModel):
    warning_type: WarningType
    severity: Severity
    message: str                          # plain-language
    affected_columns: list[str] = Field(default_factory=list)
    suggested_action: Optional[str] = None

class ValidationMetric(BaseModel):
    label: str
    value: str

class InsightValidation(BaseModel):
    validation_score: float = Field(ge=0.0, le=1.0)
    evidence_level: str
    rows_evaluated: int
    completeness: float = Field(ge=0.0, le=1.0)
    dataset_quality: QualityStatus
    confidence_reason: str
    caveats: list[str] = Field(default_factory=list)
    supporting_signals: list[str] = Field(default_factory=list)
    metrics: list[ValidationMetric] = Field(default_factory=list)

class SkippedTask(BaseModel):
    task_id: str
    module: str
    skip_reason: str

class TaskTrace(BaseModel):
    task_id: str
    module: str
    operation: str
    columns_used: list[str] = Field(default_factory=list)
    trigger_reason: str
    skipped_tasks: list[SkippedTask] = Field(default_factory=list)
    plain_explanation: str
    execution_time_ms: Optional[int] = None
    status: TaskStatus

class AmbiguityItem(BaseModel):
    candidate_column: str
    candidate_intent: Optional[str] = None
    similarity_score: float               # 0.0–1.0
    display_label: str

class FilterCondition(BaseModel):
    column: str
    operator: str                         # eq | gt | lt | gte | lte | in
    value: Any

class InsightResult(BaseModel):
    insight_id: str
    rank: int = 0
    source_module: str
    insight_type: InsightType
    columns_used: list[str]
    value: Any
    plain_summary: str
    key_takeaway: str
    subtitle: Optional[str] = None
    impact_score: float = Field(ge=0.0, le=1.0)
    confidence_score: float = Field(ge=0.0, le=1.0)
    composite_score: float = Field(ge=0.0, le=1.0, default=0.0)
    chart: Optional[ChartSpec] = None
    suggested_follow_ups: list[SuggestedFollowUp] = Field(default_factory=list)
    reliability_warning: Optional[ReliabilityWarning] = None
    validation: Optional[InsightValidation] = None
    trace: Optional[TaskTrace] = None

class QueryInterpretationFeedback(BaseModel):
    confidence: float
    intent: str
    mapped_columns: list[str]
    explanation: str                      # plain-language shown to user

class QueryObject(BaseModel):
    query_id: str
    raw_query: str
    intent: QueryIntent
    mapped_columns: list[str] = Field(default_factory=list)
    operation: str
    filters: Optional[FilterCondition] = None
    confidence: float = Field(ge=0.0, le=1.0)
    ambiguities: list[AmbiguityItem] = Field(default_factory=list)
    interpretation_explanation: str
    is_ambiguous: bool = False
    is_low_confidence: bool = False
    parameters: dict[str, Any] = Field(default_factory=dict)
    sub_queries: list[str] = Field(default_factory=list)

class QueryResult(BaseModel):
    query_id: str
    session_id: str
    status: QueryStatus
    raw_query: Optional[str] = None          # original user question (for feedback)
    result_value: Optional[Any] = None
    plain_summary: Optional[str] = None
    key_takeaway: Optional[str] = None
    chart: Optional[ChartSpec] = None
    suggested_follow_ups: list[SuggestedFollowUp] = Field(default_factory=list)
    reliability_warning: Optional[ReliabilityWarning] = None
    interpretation: Optional[QueryInterpretationFeedback] = None
    trace: Optional[TaskTrace] = None
    error: Optional["ErrorResponse"] = None

class ErrorResponse(BaseModel):
    error_id: str
    error_type: ErrorType
    message: str                          # user-friendly, plain-language
    reason: str                           # technical, for server logs
    suggestions: list[str] = Field(default_factory=list)
    ambiguity_options: list[AmbiguityItem] = Field(default_factory=list)
    valid_columns_hint: list[str] = Field(default_factory=list)

class DatasetProfile(BaseModel):
    session_id: str
    shape: dict[str, int]                 # {"rows": N, "cols": M}
    columns: list[ColumnProfile]
    numeric_columns: list[str]
    categorical_columns: list[str]
    datetime_columns: list[str]
    binary_columns: list[str] = Field(default_factory=list)  # subset of numeric_columns flagged as binary (0/1-like)
    potential_target: Optional[str] = None
    has_datetime: bool
    ml_eligible: bool
    summary_card: DatasetSummaryCard
    quick_actions: list[QuickAction] = Field(default_factory=list)
    guided_start: list[GuidedStartItem] = Field(default_factory=list)
    data_quality: DataQualityStatus

class UploadResponse(BaseModel):
    session_id: str
    filename: str
    profile: DatasetProfile
    message: str = "File uploaded and profiled successfully."

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"

# Update forward reference
QueryResult.model_rebuild()
