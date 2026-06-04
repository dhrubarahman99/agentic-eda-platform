import { useEffect, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useSessionStore } from '@/stores/sessionStore'
import { getStoredUser } from '@/api/auth'
import { useChatStore } from '@/stores/chatStore'
import WelcomeScreen from '@/components/dashboard/WelcomeScreen'
import ProcessingScreen from '@/components/dashboard/ProcessingScreen'
import TargetColumnSelector from '@/components/dashboard/TargetColumnSelector'
import DashboardLayout from '@/components/dashboard/DashboardLayout'
import ErrorBoundary from '@/components/ErrorBoundary'
import InsightsTab from '@/pages/tabs/InsightsTab'
import ChatTab from '@/pages/tabs/ChatTab'
import PreviewTab from '@/pages/tabs/PreviewTab'
import ColumnsTab from '@/pages/tabs/ColumnsTab'
import { uploadCSV, runAnalysis } from '@/api/upload'
import { getDashboard } from '@/api/dashboard'
import type { ProcessingStep } from '@/api/types'
import ToastContainer from '@/components/dashboard/Toast'

// ── Upload error extraction ───────────────────────────────────────────────────
// The backend returns upload errors as HTTPException(422) with a structured
// detail object: { error_type, message, reason, suggestions }.
// This helper pulls the human-readable message out for inline display.
function extractUploadErrorMessage(err: unknown): string {
  if (err && typeof err === 'object' && 'response' in err) {
    const res = (err as { response?: { data?: { detail?: unknown } } }).response
    const detail = res?.data?.detail
    // Structured ErrorResponse object from upload.py
    if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
      const msg = (detail as Record<string, unknown>).message
      if (typeof msg === 'string') return msg
    }
    // Plain string fallback
    if (typeof detail === 'string') return detail
  }
  return 'Upload failed. Please check the file and try again.'
}

const STEPS: ProcessingStep[] = [
  { id: 'step1', label: 'File received',                status: 'running' },
  { id: 'step2', label: 'Profiling dataset',            status: 'pending' },
  { id: 'step3', label: 'Preprocessing data',           status: 'pending' },
  { id: 'step4', label: 'Running statistical analysis', status: 'pending' },
  { id: 'step5', label: 'Running ML models',            status: 'pending' },
  { id: 'step6', label: 'Ranking insights',             status: 'pending' },
  { id: 'step7', label: 'Done',                         status: 'pending' },
]

/** Minimum milliseconds each step stays in "running" state so the user can see it. */
const STEP_MIN_MS = 850

export default function AppPage() {
  const navigate      = useNavigate()
  const queryClient   = useQueryClient()
  const [hasError, setHasError]       = useState(false)
  const [uploadError, setUploadError] = useState('')

  const {
    sessionId,
    isUploading,
    isAnalysing,
    isSelectingTarget,
    pendingUploadData,
    processingSteps,
    filename,
    activeTab,
    setActiveTab,
    setSession,
    setDashboardData,
    setProcessingSteps,
    updateStepStatus,
    setIsUploading,
    setIsAnalysing,
    setSelectingTarget,
    setPendingUploadData,
    resetSession,
    theme,
  } = useSessionStore()

  const clearChatSession = useChatStore((s) => s.clearSession)

  function handleSendToChat(_question: string) {
    setActiveTab('chat')
  }

  // Auth guard — also redirect admin users to their panel
  useEffect(() => {
    if (!localStorage.getItem('insightsai_token')) {
      navigate('/login')
    } else if (getStoredUser()?.is_admin) {
      navigate('/admin', { replace: true })
    }
  }, [navigate])

  // Apply theme on mount and when theme changes
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  // ── Phase 1: Upload the file and show the target-column selector ──────────

  async function handleFileSelect(file: File) {
    setHasError(false)
    setUploadError('')
    setIsUploading(true)
    setProcessingSteps(STEPS.map((s) => ({ ...s })))

    try {
      // Step 1: upload only (no analysis yet)
      const uploadData = await uploadCSV(file)
      clearChatSession(uploadData.session_id)

      updateStepStatus('step1', 'done')
      setIsUploading(false)

      // Transition to target-column selection screen
      setPendingUploadData(uploadData)
      setSelectingTarget(true)
    } catch (err: unknown) {
      // Upload failed — extract the server message and show it inline
      // on the welcome screen rather than the full-page error state.
      const msg = extractUploadErrorMessage(err)
      setUploadError(msg)
      setIsUploading(false)
    }
  }

  // ── Phase 2: User confirmed target column → run analysis ─────────────────

  async function handleTargetConfirmed(targetColumn: string | null) {
    if (!pendingUploadData) return

    const uploadData   = pendingUploadData
    const newSessionId = uploadData.session_id

    // Leave target-selection screen, enter analysis screen
    setSelectingTarget(false)
    setPendingUploadData(null)
    setIsAnalysing(true)
    // Keep the steps visible from phase 1 — step1 is already 'done'
    setSession(newSessionId, uploadData.filename, uploadData.profile)

    try {
      // Kick off analysis (with optional target column override)
      const analysisPromise = runAnalysis(newSessionId, targetColumn)

      // Steps 2-5: sequential, each visible for at least STEP_MIN_MS
      const midSteps = ['step2', 'step3', 'step4', 'step5'] as const
      for (const id of midSteps) {
        updateStepStatus(id, 'running')
        await new Promise<void>((r) => setTimeout(r, STEP_MIN_MS))
        updateStepStatus(id, 'done')
      }

      // Step 6: visible for at least STEP_MIN_MS AND waits for backend
      updateStepStatus('step6', 'running')
      await Promise.all([
        new Promise<void>((r) => setTimeout(r, STEP_MIN_MS)),
        analysisPromise,
      ])
      updateStepStatus('step6', 'done')

      // Step 7: "Done" — brief moment so user can see it complete
      updateStepStatus('step7', 'running')
      await new Promise<void>((r) => setTimeout(r, 680))
      updateStepStatus('step7', 'done')

      // Fetch dashboard data, then transition
      const dash = await getDashboard(newSessionId)
      setDashboardData(dash)
      queryClient.invalidateQueries({ queryKey: ['sessions'] })

      // Brief pause so user sees all steps green before screen changes
      await new Promise<void>((r) => setTimeout(r, 700))
      setIsAnalysing(false)
    } catch {
      setHasError(true)
      setIsAnalysing(false)
    }
  }

  function handleRetry() {
    setHasError(false)
    setUploadError('')
    resetSession()
  }

  // ── State machine ─────────────────────────────────────────────────────────

  let content: ReactNode

  if (isSelectingTarget && pendingUploadData) {
    content = (
      <TargetColumnSelector
        uploadData={pendingUploadData}
        onConfirm={handleTargetConfirmed}
      />
    )
  } else if (isUploading || isAnalysing || hasError) {
    content = (
      <ProcessingScreen
        filename={filename ?? pendingUploadData?.filename ?? 'Uploading…'}
        processingSteps={processingSteps}
        onRetry={handleRetry}
        hasError={hasError}
      />
    )
  } else if (sessionId) {
    // Show dashboard when we have a sessionId — profile may come from upload
    // or from switchSession (where profile is null but dashboardData is set)
    const tabContent = (() => {
      if (activeTab === 'insights') return <InsightsTab onSendToChat={handleSendToChat} />
      if (activeTab === 'chat') return <ChatTab />
      if (activeTab === 'preview') return <PreviewTab />
      return <ColumnsTab />
    })()
    content = (
      <ErrorBoundary>
        <DashboardLayout>{tabContent}</DashboardLayout>
      </ErrorBoundary>
    )
  } else {
    // No active session — show the dashboard shell with an upload prompt.
    // This makes the dashboard (not a blank upload page) the first thing
    // users see after login.
    content = (
      <ErrorBoundary>
        <DashboardLayout>
          <WelcomeScreen
            onFileSelect={handleFileSelect}
            uploadError={uploadError}
            embedded
          />
        </DashboardLayout>
      </ErrorBoundary>
    )
  }

  return (
    <>
      {content}
      <ToastContainer />
    </>
  )
}
