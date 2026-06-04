import {
  Sparkles, Sun, Moon, FileSpreadsheet, Loader2,
  CheckCircle2, XCircle, AlertTriangle,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useSessionStore } from '@/stores/sessionStore'
import type { ProcessingStep } from '@/api/types'

// ---------------------------------------------------------------------------
// TopBar (unchanged from original)
// ---------------------------------------------------------------------------

function TopBar() {
  const theme       = useSessionStore((s) => s.theme)
  const toggleTheme = useSessionStore((s) => s.toggleTheme)

  return (
    <header className="h-14 flex items-center justify-between px-6 border-b border-[#2A2A2A] bg-[#0A0A0A]/95 backdrop-blur-md flex-shrink-0">
      <div className="flex items-center gap-2.5">
        <div
          className="w-8 h-8 rounded-xl flex items-center justify-center"
          style={{
            background: 'linear-gradient(135deg, #7c3aed 0%, #3b82f6 100%)',
            boxShadow: '0 0 12px rgba(124,58,237,0.5)',
          }}
        >
          <Sparkles className="w-4 h-4 text-white" />
        </div>
        <span className="font-bold text-white text-base tracking-tight">
          Insights<span className="text-purple-400">.ai</span>
        </span>
      </div>

      <button
        onClick={toggleTheme}
        className="w-9 h-9 flex items-center justify-center rounded-lg text-[#A1A1AA] hover:text-white hover:bg-[#1A1A1A] transition-all duration-150"
        aria-label="Toggle theme"
      >
        {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
      </button>
    </header>
  )
}

// ---------------------------------------------------------------------------
// StepRow — one checklist item
// ---------------------------------------------------------------------------

interface StepRowProps {
  step: ProcessingStep
  isLast: boolean
}

function StepRow({ step, isLast }: StepRowProps) {
  const isPending = step.status === 'pending'
  const isRunning = step.status === 'running'
  const isDone    = step.status === 'done'
  const isError   = step.status === 'error'

  return (
    <div className="relative">
      {/* Vertical connector line between rows */}
      {!isLast && (
        <div
          className="absolute left-[22px] top-[38px] w-px h-3 transition-colors duration-500"
          style={{ background: isDone ? '#10B981' : '#2A2A2A' }}
        />
      )}

      <motion.div
        layout
        className={`
          relative flex items-center gap-3 px-3 py-2.5 rounded-xl
          transition-colors duration-300
          ${isRunning ? 'bg-purple-950/40 ring-1 ring-purple-500/25' : 'bg-transparent'}
        `}
      >
        {/* ── State icon ─────────────────────────────────────────────── */}
        <div className="flex-shrink-0 w-[18px] h-[18px] relative">
          <AnimatePresence mode="wait">
            {isPending && (
              <motion.div
                key="pending"
                initial={{ opacity: 0, scale: 0.6 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.6 }}
                transition={{ duration: 0.18 }}
                className="absolute inset-0 flex items-center justify-center"
              >
                {/* Empty circle for pending */}
                <span
                  className="w-[14px] h-[14px] rounded-full border-2 border-[#2A2A2A] block"
                />
              </motion.div>
            )}

            {isRunning && (
              <motion.div
                key="running"
                initial={{ opacity: 0, scale: 0.6 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.6 }}
                transition={{ duration: 0.2 }}
                className="absolute inset-0 flex items-center justify-center"
              >
                <Loader2 size={18} className="text-purple-400 animate-spin" />
              </motion.div>
            )}

            {isDone && (
              <motion.div
                key="done"
                initial={{ opacity: 0, scale: 0 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0 }}
                transition={{ type: 'spring', stiffness: 380, damping: 22 }}
                className="absolute inset-0 flex items-center justify-center"
              >
                <CheckCircle2 size={18} className="text-emerald-400" />
              </motion.div>
            )}

            {isError && (
              <motion.div
                key="error"
                initial={{ opacity: 0, scale: 0.6 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.6 }}
                transition={{ duration: 0.18 }}
                className="absolute inset-0 flex items-center justify-center"
              >
                <XCircle size={18} className="text-red-400" />
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* ── Label ──────────────────────────────────────────────────── */}
        <span
          className={`text-sm flex-1 select-none transition-all duration-300 ${
            isPending ? 'text-[#383838]'       :
            isRunning ? 'text-white font-medium' :
            isDone    ? 'text-[#52525B]'       :
                        'text-red-400'
          }`}
        >
          {step.label}
        </span>

        {/* ── Pulsing dot while running ───────────────────────────────── */}
        {isRunning && (
          <motion.span
            className="flex-shrink-0 w-1.5 h-1.5 rounded-full bg-purple-400"
            animate={{ opacity: [0.3, 1, 0.3] }}
            transition={{ duration: 1.4, repeat: Infinity, ease: 'easeInOut' }}
          />
        )}
      </motion.div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// ProcessingScreen
// ---------------------------------------------------------------------------

interface ProcessingScreenProps {
  filename: string
  processingSteps: ProcessingStep[]
  onRetry: () => void
  hasError: boolean
}

export default function ProcessingScreen({
  filename,
  processingSteps,
  onRetry,
  hasError,
}: ProcessingScreenProps) {
  const total     = processingSteps.length
  const doneCount = processingSteps.filter((s) => s.status === 'done').length
  const allDone   = total > 0 && doneCount === total
  const pct       = total > 0 ? Math.round((doneCount / total) * 100) : 0

  return (
    <div className="min-h-screen flex flex-col bg-[#0A0A0A]">
      <TopBar />

      {/* Centred card */}
      <div className="flex-1 flex items-center justify-center px-4 py-12">
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="max-w-md w-full bg-[#141414] rounded-2xl border border-[#242424] p-8 shadow-xl"
        >
          {/* Filename chip */}
          <div className="inline-flex items-center gap-1.5 bg-purple-900/30 border border-purple-500/30 rounded-full px-3 py-1">
            <FileSpreadsheet size={12} className="text-purple-300 flex-shrink-0" />
            <span className="text-purple-300 text-xs truncate max-w-[260px]">{filename}</span>
          </div>

          {hasError ? (
            /* ── Error state ─────────────────────────────────────────── */
            <div className="mt-6 flex flex-col items-center text-center gap-3">
              <AlertTriangle size={36} className="text-red-400" />
              <p className="text-white font-semibold text-lg">Analysis failed</p>
              <p className="text-[#A1A1AA] text-sm max-w-xs">
                Something went wrong while processing your file. Please check the file format and try again.
              </p>
              <button
                onClick={onRetry}
                className="mt-2 border border-[#2A2A2A] rounded-xl px-4 py-2 text-sm text-white hover:bg-[#2A2A2A] transition-all duration-150 cursor-pointer"
              >
                Try Again
              </button>
            </div>
          ) : (
            <>
              {/* ── Heading ──────────────────────────────────────────── */}
              <h2 className="text-white text-xl font-semibold mt-4">
                {allDone ? 'Analysis complete!' : 'Analysing your data…'}
              </h2>
              <p className="text-[#52525B] text-sm mt-1">
                {allDone
                  ? 'Loading your dashboard…'
                  : 'This usually takes 5–15 seconds'}
              </p>

              {/* ── Progress bar ─────────────────────────────────────── */}
              <div className="mt-5 h-1 w-full bg-[#1F1F1F] rounded-full overflow-hidden">
                <motion.div
                  className="h-full rounded-full"
                  style={{
                    background: 'linear-gradient(90deg, #7C3AED 0%, #3B82F6 100%)',
                  }}
                  initial={{ width: 0 }}
                  animate={{ width: `${pct}%` }}
                  transition={{ duration: 0.45, ease: 'easeOut' }}
                />
              </div>

              {/* ── Steps checklist ──────────────────────────────────── */}
              <div className="mt-5 space-y-0.5">
                {processingSteps.map((step, i) => (
                  <StepRow
                    key={step.id}
                    step={step}
                    isLast={i === processingSteps.length - 1}
                  />
                ))}
              </div>
            </>
          )}
        </motion.div>
      </div>
    </div>
  )
}
