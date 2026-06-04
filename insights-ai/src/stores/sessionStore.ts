import { create } from 'zustand';
import type {
  DatasetProfile,
  DashboardResponse,
  InsightResult,
  ProcessingStep,
  QualityStatus,
  UploadResponse,
} from '../api/types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function readStoredName(): string {
  try {
    const raw = localStorage.getItem('insightsai_user')
    if (raw) {
      const parsed = JSON.parse(raw) as { name?: string }
      if (parsed.name) return parsed.name
    }
  } catch { /* ignore */ }
  return 'User'
}

/**
 * Build a DatasetProfile that is good enough for all dashboard components
 * from the fields available in DashboardResponse.  Used when switching to an
 * existing session (we have dashboardData but not the original upload profile).
 */
function profileFromDashboard(d: DashboardResponse): DatasetProfile {
  return {
    session_id: d.session_id,
    shape: d.shape,
    columns: d.columns as unknown as DatasetProfile['columns'],
    numeric_columns: d.numeric_columns,
    categorical_columns: d.categorical_columns,
    datetime_columns: d.datetime_columns,
    potential_target: d.potential_target ?? null,
    has_datetime: d.has_datetime,
    ml_eligible: d.ml_eligible,
    quick_actions: d.quick_actions,
    guided_start: d.guided_start,
    summary_card: {
      row_count: d.shape['rows'] ?? 0,
      col_count: d.shape['cols'] ?? 0,
      numeric_col_count: d.numeric_columns.length,
      categorical_col_count: d.categorical_columns.length,
      datetime_col_count: d.datetime_columns.length,
      total_missing_cells: 0,
      missing_rate_overall: d.missing_rate_overall,
      columns_with_high_missing: d.columns_with_high_missing,
      detected_important_columns: [],
      potential_target_column: d.potential_target ?? null,
      quality_status: d.quality_status as QualityStatus,
      quality_note: d.quality_note,
      duplicate_row_count: d.duplicate_row_count ?? 0,
    },
    data_quality: {
      overall: d.quality_status as QualityStatus,
      flags: [],
    },
  }
}

// ---------------------------------------------------------------------------
// Store interface
// ---------------------------------------------------------------------------

interface SessionState {
  sessionId: string | null;
  filename: string | null;
  profile: DatasetProfile | null;
  dashboardData: DashboardResponse | null;
  insights: InsightResult[];
  isUploading: boolean;
  isAnalysing: boolean;
  /** True while the target-column selection screen is shown (between upload and analysis). */
  isSelectingTarget: boolean;
  /** Holds the full upload response while the user picks a target column. */
  pendingUploadData: UploadResponse | null;
  processingSteps: ProcessingStep[];
  activeTab: 'insights' | 'chat' | 'preview' | 'columns';
  llmEnabled: boolean;
  theme: 'dark' | 'light';
  userName: string;
  isMenuOpen: boolean;
  queuedQuestion: { text: string; seq: number } | null;

  setSession: (sessionId: string, filename: string, profile: DatasetProfile) => void;
  switchSession: (sessionId: string, filename: string, dashboardData: DashboardResponse) => void;
  setDashboardData: (data: DashboardResponse) => void;
  updateInsights: (insights: InsightResult[]) => void;
  setProcessingSteps: (steps: ProcessingStep[]) => void;
  updateStepStatus: (id: string, status: ProcessingStep['status']) => void;
  setActiveTab: (tab: 'insights' | 'chat' | 'preview' | 'columns') => void;
  toggleTheme: () => void;
  setLLMEnabled: (val: boolean) => void;
  setMenuOpen: (val: boolean) => void;
  setIsUploading: (val: boolean) => void;
  setIsAnalysing: (val: boolean) => void;
  setSelectingTarget: (val: boolean) => void;
  setPendingUploadData: (data: UploadResponse | null) => void;
  resetSession: () => void;
  refreshUserName: () => void;
  setQueuedQuestion: (q: { text: string; seq: number } | null) => void;
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useSessionStore = create<SessionState>((set) => ({
  sessionId: null,
  filename: null,
  profile: null,
  dashboardData: null,
  insights: [],
  isUploading: false,
  isAnalysing: false,
  isSelectingTarget: false,
  pendingUploadData: null,
  processingSteps: [],
  activeTab: 'insights',
  llmEnabled: false,
  isMenuOpen: false,
  queuedQuestion: null,
  theme: (localStorage.getItem('insightsai_theme') as 'dark' | 'light') || 'dark',
  userName: readStoredName(),

  // Called during NEW upload — does NOT clear processingSteps so the checklist
  // stays visible throughout the entire upload + analysis pipeline.
  setSession: (sessionId, filename, profile) =>
    set({ sessionId, filename, profile, queuedQuestion: null }),

  // Called when the user clicks a session in the sidebar.
  // Synthesises a profile from dashboardData so components that guard on
  // `profile !== null` (InsightsTab, ColumnsTab) always have valid data.
  switchSession: (sessionId, filename, dashboardData) =>
    set({
      sessionId,
      filename,
      dashboardData,
      profile: profileFromDashboard(dashboardData),
      insights: dashboardData.insights,
      isUploading: false,
      isAnalysing: false,
      processingSteps: [],
      llmEnabled: false,
      activeTab: 'insights',
      queuedQuestion: null,
    }),

  setDashboardData: (data) =>
    set({ dashboardData: data, insights: data.insights }),

  updateInsights: (insights) => set({ insights }),

  setProcessingSteps: (steps) => set({ processingSteps: steps }),

  updateStepStatus: (id, status) =>
    set((state) => ({
      processingSteps: state.processingSteps.map((step) =>
        step.id === id ? { ...step, status } : step,
      ),
    })),

  setActiveTab: (tab) => set({ activeTab: tab }),

  toggleTheme: () =>
    set((state) => {
      const next = state.theme === 'dark' ? 'light' : 'dark';
      localStorage.setItem('insightsai_theme', next);
      document.documentElement.setAttribute('data-theme', next);
      return { theme: next };
    }),

  setLLMEnabled: (val) => set({ llmEnabled: val }),

  setMenuOpen: (val) => set({ isMenuOpen: val }),

  setIsUploading: (val) => set({ isUploading: val }),

  setIsAnalysing: (val) => set({ isAnalysing: val }),

  setSelectingTarget: (val) => set({ isSelectingTarget: val }),

  setPendingUploadData: (data) => set({ pendingUploadData: data }),

  resetSession: () =>
    set({
      sessionId: null,
      filename: null,
      profile: null,
      dashboardData: null,
      insights: [],
      isUploading: false,
      isAnalysing: false,
      isSelectingTarget: false,
      pendingUploadData: null,
      processingSteps: [],
      llmEnabled: false,
      queuedQuestion: null,
    }),

  refreshUserName: () => set({ userName: readStoredName() }),

  setQueuedQuestion: (q) => set({ queuedQuestion: q }),
}));
