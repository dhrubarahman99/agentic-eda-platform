// ---------------------------------------------------------------------------
// Enumerations
// ---------------------------------------------------------------------------

export type DType = 'numeric' | 'categorical' | 'datetime' | 'boolean' | 'text';

export type SemanticTag = 'quantity' | 'category' | 'date' | 'identifier' | 'unknown';

export type QualityStatus = 'good' | 'fair' | 'poor';

export type FlagType =
  | 'high_missing'
  | 'small_sample'
  | 'outliers_detected'
  | 'high_cardinality'
  | 'low_variance';

export type Severity = 'low' | 'medium' | 'high';

export type ChartType =
  | 'bar'
  | 'line'
  | 'scatter'
  | 'pie'
  | 'histogram'
  | 'radar'
  | 'bubble';

export type InsightType =
  | 'trend'
  | 'correlation'
  | 'segment'
  | 'anomaly'
  | 'ranking'
  | 'distribution'
  | 'missing_data'
  | 'summary';

export type TaskStatus = 'completed' | 'failed' | 'skipped';

export type ErrorType =
  | 'mismatch'
  | 'ambiguity'
  | 'unsupported'
  | 'low_confidence'
  | 'data_quality'
  | 'parse_failure'
  | 'upload_error';

export type QueryStatus = 'success' | 'error' | 'ambiguous' | 'low_confidence';

export type WarningType =
  | 'high_missing'
  | 'small_sample'
  | 'outlier_influence'
  | 'weak_model'
  | 'low_query_confidence'
  | 'partial_data';

export type QueryIntent =
  | 'ranking'
  | 'trend'
  | 'correlation'
  | 'distribution'
  | 'missing_data'
  | 'aggregation'
  | 'comparison'
  | 'feature_importance'
  | 'unknown';

// ---------------------------------------------------------------------------
// Sub-objects
// ---------------------------------------------------------------------------

export interface DescriptiveStats {
  mean: number;
  median: number;
  std: number;
  min: number;
  max: number;
  q1: number;
  q3: number;
}

export interface DataQualityFlag {
  column?: string | null;
  flag_type: FlagType;
  severity: Severity;
  message: string;
}

export interface DataQualityStatus {
  overall: QualityStatus;
  flags: DataQualityFlag[];
}

export interface ColumnProfile {
  name: string;
  dtype: DType;
  semantic_tag: SemanticTag;
  null_rate: number;
  null_count: number;
  cardinality: number;
  stats?: DescriptiveStats | null;
  has_outliers: boolean;
  outlier_count?: number | null;
  sample_values: unknown[];
  is_binary?: boolean;
}

export interface DatasetSummaryCard {
  row_count: number;
  col_count: number;
  numeric_col_count: number;
  categorical_col_count: number;
  datetime_col_count: number;
  total_missing_cells: number;
  missing_rate_overall: number;
  columns_with_high_missing: string[];
  detected_important_columns: string[];
  potential_target_column?: string | null;
  quality_status: QualityStatus;
  quality_note: string;
  duplicate_row_count?: number;
}

export interface QuickAction {
  action_id: string;
  label: string;
  description: string;
  intent: string;
  pre_mapped_columns: string[];
  trigger_condition: string;
  priority: number;
}

export interface GuidedStartItem {
  item_id: string;
  label: string;
  reasoning: string;
  maps_to_action_id?: string | null;
  priority: number;
}

export interface ChartDataPoint {
  label: string | number;
  value: number;
  group?: string | null;
}

export interface ChartSpec {
  chart_type: ChartType;
  title: string;
  x_axis_label?: string | null;
  y_axis_label?: string | null;
  x_field: string;
  y_field?: string | null;
  group_field?: string | null;
  data: ChartDataPoint[];
  color_scheme?: string | null;
}

export interface SuggestedFollowUp {
  followup_id: string;
  question_text: string;
  reasoning: string;
  pre_mapped_intent?: string | null;
  pre_mapped_columns: string[];
  priority: number;
}

export interface ReliabilityWarning {
  warning_type: WarningType;
  severity: Severity;
  message: string;
  affected_columns: string[];
  suggested_action?: string | null;
}

export interface ValidationMetric {
  label: string;
  value: string;
}

export interface InsightValidation {
  validation_score: number;
  evidence_level: string;
  rows_evaluated: number;
  completeness: number;
  dataset_quality: QualityStatus;
  confidence_reason: string;
  caveats: string[];
  supporting_signals: string[];
  metrics: ValidationMetric[];
}

export interface SkippedTask {
  task_id: string;
  module: string;
  skip_reason: string;
}

export interface TaskTrace {
  task_id: string;
  module: string;
  operation: string;
  columns_used: string[];
  trigger_reason: string;
  skipped_tasks: SkippedTask[];
  plain_explanation: string;
  execution_time_ms?: number | null;
  status: TaskStatus;
}

export interface AmbiguityItem {
  candidate_column: string;
  candidate_intent?: string | null;
  similarity_score: number;
  display_label: string;
}

export interface FilterCondition {
  column: string;
  operator: string;
  value: unknown;
}

export interface InsightResult {
  insight_id: string;
  rank: number;
  source_module: string;
  insight_type: InsightType;
  columns_used: string[];
  value: unknown;
  plain_summary: string;
  key_takeaway: string;
  subtitle?: string | null;
  impact_score: number;
  confidence_score: number;
  composite_score: number;
  chart?: ChartSpec | null;
  suggested_follow_ups: SuggestedFollowUp[];
  reliability_warning?: ReliabilityWarning | null;
  validation?: InsightValidation | null;
  trace?: TaskTrace | null;
}

export interface QueryInterpretationFeedback {
  confidence: number;
  intent: string;
  mapped_columns: string[];
  explanation: string;
}

export interface QueryObject {
  query_id: string;
  raw_query: string;
  intent: QueryIntent;
  mapped_columns: string[];
  operation: string;
  filters?: FilterCondition | null;
  confidence: number;
  ambiguities: AmbiguityItem[];
  interpretation_explanation: string;
  is_ambiguous: boolean;
  is_low_confidence: boolean;
}

export interface ErrorResponse {
  error_id: string;
  error_type: ErrorType;
  message: string;
  reason: string;
  suggestions: string[];
  ambiguity_options: AmbiguityItem[];
  valid_columns_hint: string[];
}

export interface QueryResult {
  query_id: string;
  session_id: string;
  status: QueryStatus;
  raw_query?: string | null;           // original user question (for feedback system)
  result_value?: unknown | null;
  plain_summary?: string | null;
  key_takeaway?: string | null;
  chart?: ChartSpec | null;
  suggested_follow_ups: SuggestedFollowUp[];
  reliability_warning?: ReliabilityWarning | null;
  interpretation?: QueryInterpretationFeedback | null;
  trace?: TaskTrace | null;
  error?: ErrorResponse | null;
}

// ---------------------------------------------------------------------------
// Top-level response objects
// ---------------------------------------------------------------------------

export interface DatasetProfile {
  session_id: string;
  shape: Record<string, number>;
  columns: ColumnProfile[];
  numeric_columns: string[];
  categorical_columns: string[];
  datetime_columns: string[];
  potential_target?: string | null;
  has_datetime: boolean;
  ml_eligible: boolean;
  summary_card: DatasetSummaryCard;
  quick_actions: QuickAction[];
  guided_start: GuidedStartItem[];
  data_quality: DataQualityStatus;
}

export interface UploadResponse {
  session_id: string;
  filename: string;
  profile: DatasetProfile;
  message: string;
}

// ---------------------------------------------------------------------------
// Analysis API response objects (from insightiq/app/api/analysis.py)
// ---------------------------------------------------------------------------

export interface TransformationLogResponse {
  column: string | null;
  operation: string;
  detail: string;
  rows_affected: number;
}

export interface PreprocessingReportResponse {
  session_id: string;
  original_shape: [number, number];
  clean_shape: [number, number];
  transformations: TransformationLogResponse[];
  columns_dropped: string[];
  new_columns_added: string[];
  outlier_flag_column: string | null;
  execution_time_ms: number;
  plain_summary: string;
  task_trace: TaskTrace | null;
}

export interface AnalysisPlanTaskResponse {
  task_id: string;
  module: string;
  description: string;
  trigger_condition: string;
  status: string;
  skip_reason?: string | null;
}

export interface AnalysisPlanResponse {
  session_id: string;
  tasks: AnalysisPlanTaskResponse[];
  total_tasks: number;
  executed_tasks: number;
  skipped_tasks: number;
}

export interface AnalysisResponse {
  session_id: string;
  status: string;
  total_insights: number;
  insights: InsightResult[];
  preprocessing: PreprocessingReportResponse;
  plan: AnalysisPlanResponse;
  orchestrator_trace: TaskTrace;
  total_execution_time_ms: number;
  message: string;
}

// ---------------------------------------------------------------------------
// Dashboard API response objects (from insightiq/app/api/dashboard.py)
// ---------------------------------------------------------------------------

export interface DashboardResponse {
  session_id: string;
  filename: string;
  shape: Record<string, number>;
  numeric_columns: string[];
  categorical_columns: string[];
  datetime_columns: string[];
  potential_target?: string | null;
  ml_eligible: boolean;
  has_datetime: boolean;
  quality_status: string;
  quality_note: string;
  missing_rate_overall: number;
  columns_with_high_missing: string[];
  duplicate_row_count?: number;
  columns: Record<string, unknown>[];
  quick_actions: QuickAction[];
  guided_start: GuidedStartItem[];
  has_analysis: boolean;
  total_insights: number;
  insights: InsightResult[];
  plan_summary?: Record<string, unknown> | null;
  has_ml_insights: boolean;
  ml_models_run: string[];
  llm_available: boolean;
}

export interface DataPreviewResponse {
  session_id: string;
  columns: string[];
  rows: Record<string, unknown>[];
  total_rows_in_dataset: number;
  preview_rows_shown: number;
  offset: number;
}

export interface ColumnDetailResponse {
  session_id: string;
  column_name: string;
  detail: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Sessions API response objects (from insightiq/app/api/sessions.py)
// ---------------------------------------------------------------------------

export interface SessionListItem {
  session_id: string;
  filename: string;
  row_count: number;
  col_count: number;
  has_analysis: boolean;
  has_ml_insights: boolean;
  total_insights: number;
  quality_status: string;
}

export interface SessionStatusResponse {
  session_id: string;
  filename: string;
  row_count: number;
  col_count: number;
  has_profile: boolean;
  has_analysis: boolean;
  has_clean_df: boolean;
  has_ml_insights: boolean;
  total_insights: number;
  total_queries_asked: number;
  numeric_columns: string[];
  categorical_columns: string[];
  datetime_columns: string[];
  quality_status: string;
  ml_eligible: boolean;
  potential_target?: string | null;
  available_actions: string[];
}

// ---------------------------------------------------------------------------
// LLM API response objects (from insightiq/app/api/llm.py)
// ---------------------------------------------------------------------------

export interface LLMStatusResponse {
  available: boolean;
  reason: string;
  model: string;
  note: string;
}

export interface EnhancedAnalysisResponse {
  session_id: string;
  llm_enhanced: boolean;
  total_insights: number;
  insights: InsightResult[];
  note: string;
}

// ---------------------------------------------------------------------------
// Frontend-only types
// ---------------------------------------------------------------------------

export interface ProcessingStep {
  id: string;
  label: string;
  status: 'pending' | 'running' | 'done' | 'error';
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'error';
  content: string;
  queryResult?: QueryResult;
  timestamp: Date;
}

// ---------------------------------------------------------------------------
// Feedback API types (Feedback-Guided Query Adaptation Layer)
// ---------------------------------------------------------------------------

export interface FeedbackRequest {
  query_id: string;
  session_id: string;
  question: string;
  intent: string;
  columns_used: string[];
  plain_summary: string;
  feedback: 'positive' | 'negative';
}

export interface FeedbackResponse {
  record_id: string;
  message: string;
}

// ---------------------------------------------------------------------------
// Admin API types
// ---------------------------------------------------------------------------

export interface AdminStats {
  total_users:    number;
  total_sessions: number;
  total_feedback: number;
  total_queries:  number;
}

export interface AdminUser {
  id:            number;
  email:         string;
  name:          string;
  is_admin:      boolean;
  created_at:    string;
  session_count: number;
  query_count:   number;
}

export interface AdminSession {
  session_id:     string;
  filename:       string;
  user_email:     string | null;
  row_count:      number;
  col_count:      number;
  has_analysis:   boolean;
  total_insights: number;
  created_at:     string;
}

export interface AdminFeedbackEntry {
  id:         number;
  record_id:  string;
  user_email: string | null;
  user_id:    number | null;
  question:   string;
  intent:     string;
  feedback:   'positive' | 'negative';
  created_at: string;
}

export interface AdminFeedbackGroup {
  user_id:        number | null;
  user_email:     string | null;
  user_name:      string | null;
  total_feedback: number;
  positive:       number;
  negative:       number;
  entries:        AdminFeedbackEntry[];
}
