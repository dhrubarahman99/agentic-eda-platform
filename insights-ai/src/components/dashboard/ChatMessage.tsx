import { useState, useCallback } from 'react'
import {
  AlertCircle, ChevronRight, HelpCircle, ArrowRight,
  Info, ChevronDown, ChevronUp, Lightbulb,
  ThumbsUp, ThumbsDown, Check,
} from 'lucide-react'
import type { ChatMessage as ChatMessageType, QueryResult } from '@/api/types'
import ChartCard from './ChartCard'
import { submitFeedback } from '@/api/feedback'

// ─── Interpretation text builder ──────────────────────────────────────────

const INTENT_PHRASES: Record<string, string> = {
  ranking:              'rank values by category',
  trend:                'analyze trends over time',
  correlation:          'measure relationships between variables',
  distribution:         'show value distribution',
  missing_data:         'check for missing data',
  aggregation:          'calculate summary statistics',
  comparison:           'compare values across groups',
  feature_importance:   'identify the most important factors',
  groupby:              'group and compare by category',
  anomaly:              'detect anomalies and outliers',
  targeted_correlation: 'measure relationship between specific variables',
  compound_filter:      'filter by multiple conditions',
  derived_metric:       'calculate a derived metric',
  scenario_analysis:    'analyze what-if scenarios',
  threshold_analysis:   'analyze threshold-based conditions',
  period_growth:        'calculate period-over-period growth',
  seasonal_pattern:     'detect seasonal patterns',
  anomaly_query:        'detect anomalies in the data',
  segment_comparison:   'compare different segments',
  multi_criteria_rank:  'rank by multiple criteria',
  business_decision:    'support a business decision',
  open_ended_insight:   'generate actionable insights',
  compare:              'compare revenue by region',
  summary:              'summarize key statistics',
  filter:               'filter records by condition',
}

function buildInterpretationText(qr: QueryResult): string | null {
  const interp = qr.interpretation
  if (!interp?.intent) return null
  const intent = interp.intent.toLowerCase().replace(/-/g, '_')
  const phrase = INTENT_PHRASES[intent] ?? intent.replace(/_/g, ' ')
  if (!phrase) return null
  return `I interpreted your question as: ${phrase}`
}

// Tier-2 intents always go through the OpenAI planner
const AI_PLANNER_INTENTS = new Set([
  'business_decision', 'open_ended_insight', 'multi_criteria_rank',
  'scenario_analysis', 'period_growth', 'seasonal_pattern', 'anomaly_query',
  'segment_comparison', 'targeted_correlation', 'compound_filter',
  'derived_metric', 'threshold_analysis',
])

function wasAIPlanned(qr: QueryResult): boolean {
  const intent = qr.interpretation?.intent?.toLowerCase().replace(/-/g, '_') ?? ''
  if (AI_PLANNER_INTENTS.has(intent)) return true
  if ((qr.interpretation?.confidence ?? 1) < 0.6) return true
  const module = (qr.trace?.module ?? '').toLowerCase()
  if (module.includes('openai') || module.includes('planner')) return true
  return false
}

// ─── Analyst explanation builder for query results ─────────────────────────

function buildQueryExplanation(qr: QueryResult): string[] {
  const steps: string[] = []
  const trace  = qr.trace
  const interp = qr.interpretation

  // Step 1 — what columns the query mapped to
  const cols = trace?.columns_used?.length
    ? trace.columns_used
    : interp?.mapped_columns ?? []
  if (cols.length > 0) {
    const listed =
      cols.length <= 4
        ? cols.join(', ')
        : `${cols.slice(0, 3).join(', ')} and ${cols.length - 3} more`
    steps.push(`Focused on ${listed} in your dataset.`)
  }

  // Step 2 — what operation was performed
  const op = (trace?.operation || interp?.intent || '').toLowerCase()
  const methodMap: [string, string][] = [
    ['correlation',   'Measured the statistical relationship between columns.'],
    ['regression',    'Ran a regression to find how one factor relates to another.'],
    ['groupby',       'Grouped records by category and calculated totals or averages per group.'],
    ['aggregation',   'Summed, averaged, or counted values across the relevant records.'],
    ['trend',         'Examined how values change over time.'],
    ['ranking',       'Ranked categories from highest to lowest.'],
    ['distribution',  'Analysed how values are spread across the dataset.'],
    ['anomaly',       'Scanned for records that fall outside the normal range.'],
    ['comparison',    'Compared values across groups or time periods.'],
    ['missing',       'Checked for missing or incomplete data.'],
    ['forecast',      'Projected future values based on historical patterns.'],
    ['feature',       'Ranked which factors most influence the target.'],
    ['segment',       'Compared performance across different segments.'],
    ['filter',        'Filtered the dataset to records matching your criteria.'],
  ]
  const match = methodMap.find(([k]) => op.includes(k))
  if (match) steps.push(match[1])

  // Step 3 — the plain explanation from trace (already human-readable)
  if (trace?.plain_explanation) {
    steps.push(trace.plain_explanation)
  }

  // Step 4 — interpretation confidence note
  if (interp && interp.confidence < 0.7) {
    steps.push(`Note: query confidence was ${(interp.confidence * 100).toFixed(0)}% — the system made a reasonable interpretation but may not have captured the exact intent.`)
  }

  return steps
}

function QueryMethodLabel(qr: QueryResult): string {
  const op = (qr.trace?.operation || qr.interpretation?.intent || '').toLowerCase()
  const labels: [string, string][] = [
    ['random_forest', 'Random Forest'], ['kmeans', 'K-Means'],
    ['isolation',     'Anomaly Detection'], ['forecast', 'Forecasting'],
    ['correlation',   'Correlation'], ['groupby', 'Group-by Aggregation'],
    ['regression',    'Regression'], ['ranking', 'Ranking'],
    ['trend',         'Trend Analysis'],
  ]
  const match = labels.find(([k]) => op.includes(k))
  return match?.[1] ?? 'Statistical Analysis'
}

// ─── Pill component ────────────────────────────────────────────────────────

function Pill({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 text-[11px] rounded-full px-2.5 py-1 border ${color}`}>
      <span className="text-[10px] opacity-70">{label}</span>
      <span className="font-semibold">{value}</span>
    </span>
  )
}

// ─── How-generated dropdown ────────────────────────────────────────────────

function HowGenerated({ qr }: { qr: QueryResult }) {
  const [open, setOpen] = useState(false)
  const steps  = buildQueryExplanation(qr)
  const method = QueryMethodLabel(qr)
  const conf   = qr.interpretation?.confidence

  if (steps.length === 0 && !conf) return null

  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-[11px] text-[#52525B] hover:text-[#A1A1AA] transition-colors cursor-pointer group w-full"
      >
        <Info size={10} />
        <span>How this was generated</span>
        <span className="ml-auto flex items-center gap-0.5 group-hover:text-[#A1A1AA]">
          <span className="text-[10px]">{open ? 'hide' : 'show'}</span>
          {open ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
        </span>
      </button>

      {open && (
        <div className="bg-[#111111] rounded-xl p-3 mt-1.5 space-y-2.5">
          {steps.length > 0 && (
            <ol className="space-y-1.5">
              {steps.map((step, i) => (
                <li key={i} className="flex items-start gap-2 text-[11px] text-[#A1A1AA]">
                  <span className="text-[#3A3A3A] font-mono flex-shrink-0 w-4 text-right select-none">{i + 1}.</span>
                  <span className="leading-relaxed">{step}</span>
                </li>
              ))}
            </ol>
          )}
          <div className="flex flex-wrap gap-1.5 pt-2 border-t border-[#1A1A1A]">
            <Pill label="Method" value={method} color="bg-purple-900/20 border-purple-500/20 text-purple-300" />
            {conf != null && (
              <Pill
                label="Confidence"
                value={`${(conf * 100).toFixed(0)}%`}
                color={conf >= 0.7
                  ? 'bg-emerald-900/20 border-emerald-500/20 text-emerald-300'
                  : 'bg-amber-900/20 border-amber-500/20 text-amber-300'}
              />
            )}
            {qr.reliability_warning && (
              <Pill label="Warning" value={qr.reliability_warning.warning_type.replace(/_/g, ' ')}
                color="bg-red-900/20 border-red-500/20 text-red-300" />
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Feedback bar ─────────────────────────────────────────────────────────

type FeedbackState = 'idle' | 'positive' | 'negative' | 'loading'

interface FeedbackBarProps {
  qr: QueryResult
  question: string
}

function FeedbackBar({ qr, question }: FeedbackBarProps) {
  const [state, setState] = useState<FeedbackState>('idle')

  const submit = useCallback(async (value: 'positive' | 'negative') => {
    if (state !== 'idle') return
    setState('loading')
    try {
      await submitFeedback({
        query_id: qr.query_id,
        session_id: qr.session_id,
        question,
        intent: qr.interpretation?.intent ?? 'unknown',
        columns_used: qr.interpretation?.mapped_columns ?? [],
        plain_summary: qr.plain_summary ?? '',
        feedback: value,
      })
      setState(value)
    } catch {
      setState('idle')   // silently reset on network error
    }
  }, [state, qr, question])

  if (state === 'positive' || state === 'negative') {
    return (
      <div className="flex items-center gap-1.5 mt-2 pt-2 border-t border-[#1E1E1E]">
        <Check size={11} className="text-emerald-400" />
        <span className="text-[11px] text-[#52525B]">
          {state === 'positive' ? 'Marked as helpful — thanks!' : 'Marked as not helpful — we\'ll try harder next time.'}
        </span>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2 mt-2 pt-2 border-t border-[#1E1E1E]">
      <span className="text-[11px] text-[#3A3A3A] flex-1">Was this answer useful?</span>
      <button
        disabled={state === 'loading'}
        onClick={() => submit('positive')}
        title="Yes, this was useful"
        className="flex items-center gap-1 text-[11px] px-2 py-0.5 rounded border border-[#2A2A2A] bg-[#111111] text-[#52525B] hover:border-emerald-500/50 hover:text-emerald-400 disabled:opacity-40 transition-colors cursor-pointer"
      >
        <ThumbsUp size={11} />
        <span>Yes</span>
      </button>
      <button
        disabled={state === 'loading'}
        onClick={() => submit('negative')}
        title="No, this was not useful"
        className="flex items-center gap-1 text-[11px] px-2 py-0.5 rounded border border-[#2A2A2A] bg-[#111111] text-[#52525B] hover:border-red-500/50 hover:text-red-400 disabled:opacity-40 transition-colors cursor-pointer"
      >
        <ThumbsDown size={11} />
        <span>No</span>
      </button>
    </div>
  )
}

// ─── ChatMessage ───────────────────────────────────────────────────────────

interface ChatMessageProps {
  message: ChatMessageType
  onFollowUp: (question: string) => void
}

export default function ChatMessage({ message, onFollowUp }: ChatMessageProps) {
  // User bubble
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="bg-purple-600 text-white rounded-2xl rounded-br-sm px-4 py-2.5 text-sm max-w-[80%] leading-relaxed">
          {message.content}
        </div>
      </div>
    )
  }

  // Error with no queryResult
  if (message.role === 'error' && !message.queryResult) {
    return (
      <div className="flex justify-start">
        <div className="bg-amber-900/20 border border-amber-500/30 rounded-xl p-3 max-w-[95%] flex items-start gap-2">
          <AlertCircle size={14} className="text-amber-400 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-amber-100">{message.content}</p>
        </div>
      </div>
    )
  }

  const qr = message.queryResult

  // Plain assistant message with no queryResult
  if (!qr) {
    return (
      <div className="flex justify-start">
        <div className="bg-[#242424] border border-[#2A2A2A] rounded-2xl rounded-bl-sm p-4 max-w-[95%]">
          <p className="text-sm text-white">{message.content}</p>
        </div>
      </div>
    )
  }

  // Ambiguous query
  if (qr.error?.error_type === 'ambiguity') {
    return (
      <div className="flex justify-start">
        <div className="bg-[#242424] border border-[#2A2A2A] rounded-xl p-3 max-w-[95%]">
          <div className="flex items-center gap-2 mb-2">
            <HelpCircle size={14} className="text-amber-400" />
            <p className="text-sm text-white">Did you mean one of these?</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {qr.error.ambiguity_options.map((option, i) => (
              <button
                key={i}
                onClick={() => onFollowUp(option.display_label)}
                className="bg-[#1A1A1A] border border-[#2A2A2A] hover:border-purple-500 rounded-lg px-3 py-1 text-xs text-[#A1A1AA] hover:text-white cursor-pointer transition-colors"
              >
                {option.display_label}
              </button>
            ))}
          </div>
        </div>
      </div>
    )
  }

  // Error status
  if (qr.status === 'error') {
    return (
      <div className="flex justify-start">
        <div className="bg-amber-900/20 border border-amber-500/30 rounded-xl p-3 max-w-[95%] flex items-start gap-2">
          <AlertCircle size={14} className="text-amber-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm text-amber-100">{qr.error?.message || message.content}</p>
            {qr.error?.suggestions && qr.error.suggestions.length > 0 && (
              <ul className="mt-2 space-y-1">
                {qr.error.suggestions.map((s, i) => (
                  <li key={i} className="flex items-center gap-1 text-xs text-amber-200">
                    <ChevronRight size={11} />{s}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    )
  }

  // ── Success (and low_confidence / ambiguous-without-error) ────────────────
  const interpretationText = buildInterpretationText(qr)
  const aiPlanned = wasAIPlanned(qr)

  return (
    <div className="flex flex-col gap-3">
      {/* Text bubble */}
      <div className="flex justify-start">
        <div className="bg-[#242424] border border-[#2A2A2A] rounded-2xl rounded-bl-sm p-4 max-w-[95%] w-full">

          {/* Subtle interpretation line + optional AI Planner badge */}
          {interpretationText && (
            <div className="flex items-center gap-2 mb-2.5 flex-wrap">
              <p className="text-[11px] text-[#52525B] italic leading-none">
                {interpretationText}
              </p>
              {aiPlanned && (
                <span className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-purple-900/30 border border-purple-500/25 text-purple-400 leading-none flex-shrink-0">
                  <svg width="8" height="8" viewBox="0 0 8 8" fill="currentColor" className="opacity-80">
                    <circle cx="4" cy="4" r="3" fillOpacity="0.4" />
                    <circle cx="4" cy="4" r="1.5" />
                  </svg>
                  AI Planner
                </span>
              )}
            </div>
          )}

          {/* Main answer */}
          {qr.plain_summary && (
            <p className="text-sm text-white leading-relaxed">{qr.plain_summary}</p>
          )}

          {/* Purple highlighted key takeaway strip */}
          {qr.key_takeaway && (
            <div className="mt-3 flex items-start gap-2 bg-purple-900/20 border-l-2 border-purple-500/70 rounded-r-lg px-3 py-2">
              <Lightbulb size={12} className="text-purple-400 flex-shrink-0 mt-0.5" />
              <span className="text-xs text-purple-200 leading-relaxed">{qr.key_takeaway}</span>
            </div>
          )}

          {/* Follow-up suggestions */}
          {qr.suggested_follow_ups && qr.suggested_follow_ups.length > 0 && (
            <div className="flex gap-1.5 flex-wrap mt-3">
              {qr.suggested_follow_ups.map((fu) => (
                <button
                  key={fu.followup_id}
                  onClick={() => onFollowUp(fu.question_text)}
                  className="bg-[#1A1A1A] border border-[#333333] hover:border-purple-500/50 rounded-full px-3 py-1 text-xs text-[#A1A1AA] hover:text-purple-300 cursor-pointer flex items-center gap-1 transition-all duration-150"
                >
                  <ArrowRight size={10} />{fu.question_text}
                </button>
              ))}
            </div>
          )}

          {/* How this was generated */}
          <HowGenerated qr={qr} />

          {/* Feedback — only on successful answers; raw_query is the user's original question */}
          <FeedbackBar qr={qr} question={qr.raw_query ?? ''} />
        </div>
      </div>

      {/* Chart card — separate from the text bubble, centered */}
      {qr.chart && (
        <div className="w-full">
          <ChartCard chart={qr.chart} />
        </div>
      )}
    </div>
  )
}
