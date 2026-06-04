import { useState, useRef } from 'react'
import {
  TrendingUp, GitMerge, PieChart as PieChartIcon,
  AlertTriangle, Trophy, BarChart2, CircleDashed,
  Cpu, BarChart3,
  ShieldAlert,
  Info, ChevronDown, ChevronUp,
  ArrowRight, Download, Maximize2,
  CheckCircle2, Zap, Check,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import type { InsightResult, InsightType } from '@/api/types'
import InsightChart from './InsightChart'
import { downloadChartAsPng, ExpandedChartModal } from './ChartCard'

// ─── Title simplification ─────────────────────────────────────────────────

function stripTechnical(text: string): string {
  let t = text
    .replace(/^Using\s+[\w\s-]+(analysis|model|algorithm|method|test),?\s+/i, '')
    .replace(/^(A|An|The)\s+[\w\s-]+(model|analysis|test)\s+(shows?|reveals?|indicates?|finds?):?\s+/i, '')
    .replace(/^Based on\s+[\w\s-]+,\s+/i, '')
    .split(/\.\s+/)[0]
    .replace(/,?\s+accounting for\s+[\d.]+%[^)]*(\([^)]*\))?/gi, '')
    .replace(/\s*\(model\s+R²?\s*=\s*[\d.]+\)/gi, '')
    .replace(/\s*\(p\s*[<>=]{1,2}\s*[\d.]+\)/gi, '')
    .replace(/\s*\(r\s*=\s*[-\d.]+\)/gi, '')
    .replace(/\s*\(n\s*=\s*[\d,]+\)/gi, '')
    .replace(/'([^']+)'/g, '$1')
    .replace(/"([^"]+)"/g, '$1')
    .replace(/[.,]$/, '')
    .trim()
  return t.charAt(0).toUpperCase() + t.slice(1)
}

function getInsightTitle(insight: InsightResult): string {
  const kt = insight.key_takeaway?.trim()
  if (kt && kt.length >= 10 && kt.length <= 160) {
    return stripTechnical(kt.split(/\.\s+/)[0].replace(/\.$/, ''))
  }
  return stripTechnical(insight.plain_summary)
}

// ─── Badge helpers ─────────────────────────────────────────────────────────

interface BadgeStyle { bg: string; border: string; text: string; icon: React.ReactNode; label: string }

function getTypeBadge(type: InsightType): BadgeStyle {
  switch (type) {
    case 'trend':       return { bg: 'bg-blue-900/30',   border: 'border-blue-500/30',   text: 'text-blue-400',   icon: <TrendingUp  size={10} />, label: 'Trend' }
    case 'correlation': return { bg: 'bg-purple-900/30', border: 'border-purple-500/30', text: 'text-purple-400', icon: <GitMerge    size={10} />, label: 'Correlation' }
    case 'segment':     return { bg: 'bg-green-900/30',  border: 'border-green-500/30',  text: 'text-green-400',  icon: <PieChartIcon size={10} />, label: 'Segment' }
    case 'anomaly':     return { bg: 'bg-red-900/30',    border: 'border-red-500/30',    text: 'text-red-400',    icon: <AlertTriangle size={10} />, label: 'Anomaly' }
    case 'ranking':     return { bg: 'bg-amber-900/30',  border: 'border-amber-500/30',  text: 'text-amber-400',  icon: <Trophy      size={10} />, label: 'Ranking' }
    case 'distribution':return { bg: 'bg-slate-800/30',  border: 'border-slate-600/40',  text: 'text-slate-400',  icon: <BarChart2   size={10} />, label: 'Distribution' }
    case 'missing_data':return { bg: 'bg-orange-900/30', border: 'border-orange-500/30', text: 'text-orange-400', icon: <CircleDashed size={10} />, label: 'Missing Data' }
    default:            return { bg: 'bg-slate-800/30',  border: 'border-slate-600/40',  text: 'text-slate-400',  icon: <BarChart3   size={10} />, label: 'Summary' }
  }
}

function getConfidenceBadge(score: number, sourceModule: string): BadgeStyle {
  if (sourceModule === 'ml_module') {
    return { bg: 'bg-violet-900/30', border: 'border-violet-500/40', text: 'text-violet-300', icon: <Cpu size={10} />, label: 'ML Insight' }
  }
  if (score >= 0.75) {
    return { bg: 'bg-emerald-900/30', border: 'border-emerald-500/30', text: 'text-emerald-300', icon: <CheckCircle2 size={10} />, label: 'High Confidence' }
  }
  if (score >= 0.5) {
    return { bg: 'bg-amber-900/30', border: 'border-amber-500/30', text: 'text-amber-300', icon: <Zap size={10} />, label: 'Medium Confidence' }
  }
  return { bg: 'bg-red-900/30', border: 'border-red-500/30', text: 'text-red-300', icon: <AlertTriangle size={10} />, label: 'Low Confidence' }
}

// ─── Analyst-friendly explanation builder ─────────────────────────────────

function buildAnalystSteps(insight: InsightResult): string[] {
  const steps: string[] = []
  const cols = insight.columns_used
  const type = insight.insight_type
  const src  = insight.source_module
  const trace = insight.trace
  const op   = (trace?.operation || '').toLowerCase()

  if (cols.length > 0) {
    const listed =
      cols.length <= 4
        ? cols.join(', ')
        : `${cols.slice(0, 3).join(', ')}, and ${cols.length - 3} other column${cols.length - 3 > 1 ? 's' : ''}`
    steps.push(`Examined ${listed} across your dataset.`)
  }

  if (src === 'ml_module') {
    if      (op.includes('random_forest') || op.includes('feature'))
      steps.push('Used a Random Forest model to rank which factors most influence the target variable.')
    else if (op.includes('kmeans') || op.includes('cluster'))
      steps.push('Applied K-Means clustering to group similar records together and identify natural segments.')
    else if (op.includes('isolation') || op.includes('anomaly'))
      steps.push('Ran an Isolation Forest anomaly detection model to flag records that fall outside normal patterns.')
    else if (op.includes('forecast') || op.includes('smooth') || op.includes('exponential'))
      steps.push('Applied exponential smoothing (Holt-Winters) to model historical trends and project future values.')
    else
      steps.push('Applied a machine learning model to identify patterns not visible to simple statistics.')
  } else {
    const methodMap: [string, string][] = [
      ['correlation', 'Calculated the statistical correlation to measure how strongly two columns move together.'],
      ['regression',  'Ran a regression analysis to understand how changes in one factor relate to another.'],
      ['groupby',     'Grouped records by category and aggregated values to compare performance across segments.'],
      ['trend',       'Analysed how values change over time to detect direction and magnitude of trends.'],
      ['distribution','Examined how values are spread across the dataset to understand the typical range.'],
      ['ranking',     'Ranked all categories from highest to lowest to surface the top and bottom performers.'],
      ['missing',     'Scanned every column for missing, null, or incomplete values.'],
    ]
    const match = methodMap.find(([k]) => op.includes(k))
    if (match) steps.push(match[1])
  }

  if (trace?.plain_explanation) {
    steps.push(trace.plain_explanation)
  }

  const conclusionMap: Partial<Record<InsightType, string>> = {
    correlation:  'Measured the direction and strength of the relationship and assessed statistical significance.',
    ranking:      'Identified the top performers and any significant gaps between categories.',
    trend:        'Determined whether the pattern is consistently growing, declining, or flat.',
    segment:      'Highlighted which groups perform above or below the overall average.',
    anomaly:      'Flagged the records that deviate significantly from the expected range.',
    distribution: 'Characterised the spread of values and identified any concentration or skew.',
  }
  if (conclusionMap[type]) steps.push(conclusionMap[type]!)

  return steps
}

function getMethodLabel(insight: InsightResult): string {
  const op = (insight.trace?.operation || '').toLowerCase()
  if (insight.source_module === 'ml_module') {
    if (op.includes('random_forest') || op.includes('feature')) return 'Random Forest'
    if (op.includes('kmeans') || op.includes('cluster'))         return 'K-Means'
    if (op.includes('isolation') || op.includes('anomaly'))      return 'Isolation Forest'
    if (op.includes('forecast') || op.includes('smooth'))        return 'Forecasting'
    return 'ML Model'
  }
  const labels: Partial<Record<InsightType, string>> = {
    trend: 'Trend Analysis', correlation: 'Correlation', segment: 'Segmentation',
    anomaly: 'Anomaly Detection', ranking: 'Ranking', distribution: 'Distribution',
    missing_data: 'Data Quality', summary: 'Statistical Summary',
  }
  return labels[insight.insight_type] || 'Statistical Analysis'
}

function getEvidencePillColor(level?: string | null): string {
  switch ((level || '').toLowerCase()) {
    case 'strong':
      return 'bg-emerald-900/20 border-emerald-500/20 text-emerald-300'
    case 'moderate':
      return 'bg-amber-900/20 border-amber-500/20 text-amber-300'
    default:
      return 'bg-slate-800/30 border-slate-600/30 text-slate-300'
  }
}

// ─── Metric pill ──────────────────────────────────────────────────────────

function Pill({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 text-[11px] rounded-full px-2.5 py-1 border ${color}`}>
      <span className="text-[10px] opacity-70">{label}</span>
      <span className="font-semibold">{value}</span>
    </span>
  )
}

// ─── InsightCard ───────────────────────────────────────────────────────────

interface InsightCardProps {
  insight: InsightResult
  index: number
  onFollowUp: (question: string) => void
}

export default function InsightCard({ insight, index, onFollowUp }: InsightCardProps) {
  const [isTraceOpen, setIsTraceOpen]     = useState(false)
  const [sentFollowUp, setSentFollowUp]   = useState<string | null>(null)
  const [chartExpanded, setChartExpanded] = useState(false)
  const chartRef = useRef<HTMLDivElement>(null)

  const typeBadge = getTypeBadge(insight.insight_type)
  const confBadge = getConfidenceBadge(insight.confidence_score, insight.source_module)
  const title     = getInsightTitle(insight)
  const steps     = buildAnalystSteps(insight)
  const method    = getMethodLabel(insight)
  const validation = insight.validation

  const safeFilename = (insight.chart?.title ?? `insight-${insight.rank}`)
    .toLowerCase().replace(/[^a-z0-9]+/g, '_').slice(0, 50)

  function handleFollowUp(question: string) {
    setSentFollowUp(question)
    onFollowUp(question)
    setTimeout(() => setSentFollowUp(null), 2000)
  }

  const confPill =
    insight.confidence_score >= 0.75
      ? 'bg-emerald-900/20 border-emerald-500/20 text-emerald-300'
      : insight.confidence_score >= 0.5
        ? 'bg-amber-900/20 border-amber-500/20 text-amber-300'
        : 'bg-red-900/20 border-red-500/20 text-red-300'

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.3 }}
      className="bg-[#1A1A1A] rounded-2xl border border-[#2A2A2A] hover:border-[#3A3A3A] transition-colors overflow-hidden"
    >
      {/* ── Title area ──────────────────────────────────────────────────── */}
      <div className="p-5 pb-4">
        <div className="flex items-center gap-2 flex-wrap mb-3">
          <div className="w-6 h-6 rounded-full bg-purple-600 flex items-center justify-center text-white text-[11px] font-bold flex-shrink-0">
            {insight.rank}
          </div>
          <span className={`rounded-full px-2.5 py-0.5 text-[11px] border flex items-center gap-1 ${confBadge.bg} ${confBadge.border} ${confBadge.text}`}>
            {confBadge.icon}{confBadge.label}
          </span>
          <span className={`rounded-full px-2.5 py-0.5 text-[11px] border flex items-center gap-1 ${typeBadge.bg} ${typeBadge.border} ${typeBadge.text}`}>
            {typeBadge.icon}{typeBadge.label}
          </span>
        </div>
        <h3 className="text-[15px] font-semibold text-white leading-snug">{title}</h3>
        {insight.subtitle && (
          <p className="mt-1.5 text-[13px] text-[#A1A1AA] leading-relaxed">{insight.subtitle}</p>
        )}
      </div>

      {/* ── Chart (inside card) ─────────────────────────────────────────── */}
      {insight.chart && (
        <div className="px-4 pb-3">
          <div className="bg-[#111111] rounded-xl overflow-hidden border border-[#222222]">
            {/* Chart card header */}
            <div className="flex items-center justify-between px-3 py-2 border-b border-[#222222]">
              <span className="text-[10px] font-semibold text-[#52525B] uppercase tracking-wider truncate">
                {insight.chart.title}
              </span>
              <div className="flex items-center gap-1 flex-shrink-0">
                <button
                  onClick={() => downloadChartAsPng(chartRef, safeFilename)}
                  className="flex items-center gap-1 text-[#52525B] hover:text-[#A1A1AA] transition-colors px-1.5 py-1 rounded hover:bg-[#1A1A1A] cursor-pointer"
                  title="Download PNG"
                >
                  <Download size={11} />
                  <span className="text-[10px] hidden sm:inline">PNG</span>
                </button>
                <button
                  onClick={() => setChartExpanded(true)}
                  className="flex items-center justify-center text-[#52525B] hover:text-[#A1A1AA] transition-colors p-1 rounded hover:bg-[#1A1A1A] cursor-pointer"
                  title="Expand chart"
                >
                  <Maximize2 size={11} />
                </button>
              </div>
            </div>
            <div ref={chartRef} style={{ height: 240 }} className="px-2 py-2">
              <InsightChart chart={insight.chart} />
            </div>
          </div>
        </div>
      )}

      {/* ── Lower section ───────────────────────────────────────────────── */}
      <div className="px-5 pb-4 space-y-3">
        {/* Reliability warning */}
        {insight.reliability_warning && (
          <div className="bg-red-900/20 border border-red-500/30 rounded-xl p-3 flex items-start gap-2">
            <ShieldAlert size={13} className="text-red-400 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-200">{insight.reliability_warning.message}</p>
          </div>
        )}

        {/* ── How this insight was generated ────────────────────────────── */}
        <div>
          <button
            onClick={() => setIsTraceOpen(!isTraceOpen)}
            className="w-full flex items-center justify-between py-1.5 text-xs text-[#52525B] hover:text-[#A1A1AA] transition-colors cursor-pointer group"
          >
            <span className="flex items-center gap-1.5">
              <Info size={11} />
              How this insight was generated
            </span>
            <span className="flex items-center gap-1 group-hover:text-[#A1A1AA]">
              <span className="text-[10px]">{isTraceOpen ? 'hide' : 'show'}</span>
              {isTraceOpen ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
            </span>
          </button>

          <AnimatePresence>
            {isTraceOpen && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2 }}
                style={{ overflow: 'hidden' }}
              >
                <div className="bg-[#111111] rounded-xl p-3.5 mt-1.5 space-y-3">
                  {steps.length > 0 && (
                    <ol className="space-y-2">
                      {steps.map((step, i) => (
                        <li key={i} className="flex items-start gap-2.5 text-xs text-[#A1A1AA]">
                          <span className="text-[#3A3A3A] font-mono flex-shrink-0 w-4 text-right select-none">{i + 1}.</span>
                          <span className="leading-relaxed">{step}</span>
                        </li>
                      ))}
                    </ol>
                  )}

                  <div className="flex flex-wrap gap-2 pt-2 border-t border-[#1A1A1A]">
                    <Pill label="Confidence" value={`${(insight.confidence_score * 100).toFixed(0)}%`} color={confPill} />
                    <Pill
                      label="Impact"
                      value={`${(insight.impact_score * 100).toFixed(0)}%`}
                      color="bg-blue-900/20 border-blue-500/20 text-blue-300"
                    />
                    <Pill
                      label="Score"
                      value={insight.composite_score.toFixed(2)}
                      color="bg-slate-800/30 border-slate-600/30 text-slate-300"
                    />
                    <Pill
                      label="Method"
                      value={method}
                      color="bg-purple-900/20 border-purple-500/20 text-purple-300"
                    />
                  </div>

                  {validation && (
                    <div className="rounded-xl border border-[#222222] bg-[#151515] p-3 space-y-3">
                      <div className="flex flex-wrap gap-2">
                        <Pill
                          label="Evidence"
                          value={validation.evidence_level}
                          color={getEvidencePillColor(validation.evidence_level)}
                        />
                        <Pill
                          label="Validation"
                          value={`${(validation.validation_score * 100).toFixed(0)}%`}
                          color="bg-cyan-900/20 border-cyan-500/20 text-cyan-300"
                        />
                        <Pill
                          label="Rows"
                          value={validation.rows_evaluated.toLocaleString()}
                          color="bg-slate-800/30 border-slate-600/30 text-slate-300"
                        />
                        <Pill
                          label="Quality"
                          value={validation.dataset_quality}
                          color="bg-slate-800/30 border-slate-600/30 text-slate-300"
                        />
                      </div>

                      <p className="text-xs text-[#D4D4D8] leading-relaxed">
                        {validation.confidence_reason}
                      </p>

                      {validation.metrics.length > 0 && (
                        <div className="flex flex-wrap gap-2">
                          {validation.metrics.map((metric) => (
                            <Pill
                              key={`${metric.label}-${metric.value}`}
                              label={metric.label}
                              value={metric.value}
                              color="bg-[#101010] border-[#2A2A2A] text-[#C4C4C8]"
                            />
                          ))}
                        </div>
                      )}

                      {validation.supporting_signals.length > 0 && (
                        <div className="space-y-1">
                          {validation.supporting_signals.map((signal) => (
                            <p key={signal} className="text-[11px] text-[#A1A1AA] leading-relaxed">
                              {signal}
                            </p>
                          ))}
                        </div>
                      )}

                      {validation.caveats.length > 0 && (
                        <div className="rounded-lg border border-amber-500/20 bg-amber-950/10 p-2.5 space-y-1">
                          {validation.caveats.map((caveat) => (
                            <p key={caveat} className="text-[11px] text-amber-200 leading-relaxed">
                              {caveat}
                            </p>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {insight.plain_summary && (
                    <details className="group rounded-lg border border-[#2A2A2A] bg-[#171717] px-3 py-2">
                      <summary className="text-[11px] text-[#8B8B95] hover:text-[#D4D4D8] cursor-pointer transition-colors select-none font-medium">
                        Raw technical detail ▸
                      </summary>
                      <p className="mt-2 text-[12px] text-[#B4B4BE] leading-relaxed italic">
                        {insight.plain_summary}
                      </p>
                    </details>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* ── Follow-up chips ───────────────────────────────────────────── */}
        {insight.suggested_follow_ups.length > 0 && (
          <div className="flex gap-2 flex-wrap pt-1">
            {insight.suggested_follow_ups.slice(0, 4).map((fu) => {
              const sent = sentFollowUp === fu.question_text
              return (
                <button
                  key={fu.followup_id}
                  onClick={() => handleFollowUp(fu.question_text)}
                  disabled={sent}
                  className={`border rounded-full px-3 py-1 text-xs cursor-pointer flex items-center gap-1 transition-all duration-150 ${
                    sent
                      ? 'bg-purple-900/30 border-purple-500/40 text-purple-300'
                      : 'bg-[#1A1A1A] border-[#333333] hover:border-purple-500/50 text-[#A1A1AA] hover:text-purple-300'
                  }`}
                >
                  {sent ? <Check size={10} /> : <ArrowRight size={10} />}
                  {fu.question_text}
                </button>
              )
            })}
          </div>
        )}
      </div>

      {/* ── Expanded chart modal ─────────────────────────────────────────── */}
      {chartExpanded && insight.chart && (
        <ExpandedChartModal
          chart={insight.chart}
          onClose={() => setChartExpanded(false)}
        />
      )}
    </motion.div>
  )
}
