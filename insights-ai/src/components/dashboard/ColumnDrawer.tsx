import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ResponsiveContainer,
  BarChart, Bar, Cell, LabelList,
  PieChart, Pie, Legend,
  XAxis, YAxis, CartesianGrid, Tooltip,
} from 'recharts'
import {
  X, AlertCircle, Hash, Tag, AlertTriangle, Calendar,
  ToggleLeft, AlignLeft, ChevronDown, ChevronUp,
  Database, Sparkles,
} from 'lucide-react'
import { useSessionStore } from '@/stores/sessionStore'
import { getColumnDetail } from '@/api/dashboard'
import type { DType } from '@/api/types'
import { formatAxisLabel, formatValue, truncate } from './InsightChart'

// ---------------------------------------------------------------------------
// Local types for the detail payload
// ---------------------------------------------------------------------------

interface DetailStatistics {
  mean: number
  median: number
  std: number
  min: number
  max: number
  q1: number
  q3: number
}

interface HistogramBin {
  bin_label: string
  count: number
}

interface ValueCount {
  value: string
  count: number
  pct: number
}

interface ColumnDetail {
  statistics?: DetailStatistics | null
  histogram?: HistogramBin[]
  value_counts?: ValueCount[]
  null_count?: number
  null_rate?: number
  total_rows?: number
  cardinality?: number
  has_outliers?: boolean
  outlier_count?: number
  outlier_values?: number[]
  outliers?: number[]
  semantic_tag?: string
  is_clean_data?: boolean
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const DRAWER_COLORS = [
  '#7C3AED', '#06B6D4', '#10B981', '#F59E0B', '#EF4444',
  '#8B5CF6', '#3B82F6', '#EC4899', '#14B8A6', '#F97316',
]

const TOOLTIP_STYLE = {
  backgroundColor: '#1A1A1A',
  border: '1px solid #333333',
  borderRadius: '10px',
  color: '#F4F4F5',
  fontSize: '12px',
  padding: '8px 12px',
  boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
}

const TOOLTIP_LABEL_STYLE = {
  color: '#E4E4E7',
  marginBottom: 4,
  fontWeight: 700 as const,
}

const TOOLTIP_ITEM_STYLE = {
  color: '#E4E4E7',
  fontWeight: 500 as const,
}

interface DtypeBadgeConfig {
  bg: string
  border: string
  text: string
  icon: React.ReactNode
  label: string
}

function getDtypeConfig(dtype: DType): DtypeBadgeConfig {
  switch (dtype) {
    case 'numeric':
      return { bg: 'bg-blue-900/30', border: 'border-blue-500/30', text: 'text-blue-400', icon: <Hash size={10} />, label: 'numeric' }
    case 'categorical':
      return { bg: 'bg-green-900/30', border: 'border-green-500/30', text: 'text-green-400', icon: <Tag size={10} />, label: 'categorical' }
    case 'datetime':
      return { bg: 'bg-purple-900/30', border: 'border-purple-500/30', text: 'text-purple-400', icon: <Calendar size={10} />, label: 'datetime' }
    case 'boolean':
      return { bg: 'bg-amber-900/30', border: 'border-amber-500/30', text: 'text-amber-400', icon: <ToggleLeft size={10} />, label: 'boolean' }
    default:
      return { bg: 'bg-slate-800/30', border: 'border-slate-500/30', text: 'text-slate-400', icon: <AlignLeft size={10} />, label: dtype }
  }
}

const STATS_CONFIG = [
  { label: 'Mean',    key: 'mean'   as const },
  { label: 'Median',  key: 'median' as const },
  { label: 'Std Dev', key: 'std'    as const },
  { label: 'Min',     key: 'min'    as const },
  { label: 'Max',     key: 'max'    as const },
  { label: 'Q1',      key: 'q1'     as const },
  { label: 'Q3',      key: 'q3'     as const },
]

// ---------------------------------------------------------------------------
// OutlierValuesList — collapsible dropdown
// ---------------------------------------------------------------------------

function OutlierValuesList({ values }: { values: number[] }) {
  const [open, setOpen] = useState(false)
  if (values.length === 0) return null
  return (
    <div className="mt-1">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 text-[10px] text-[#52525B] hover:text-amber-400 transition-colors cursor-pointer w-full"
      >
        {open ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
        <span>{open ? 'Hide' : 'Show'} outlier values ({values.length})</span>
      </button>
      {open && (
        <div className="mt-1.5 flex flex-wrap gap-1.5 max-h-32 overflow-y-auto pr-1">
          {values.map((v, i) => (
            <span
              key={i}
              className="bg-amber-900/20 border border-amber-500/25 text-amber-300 text-[10px] rounded px-1.5 py-0.5 font-mono"
            >
              {formatValue(v)}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// PanelContent — renders the statistics for one data source (raw or clean)
// ---------------------------------------------------------------------------

interface PanelContentProps {
  detail: ColumnDetail | undefined
  isLoading: boolean
  isClean: boolean
}

function PanelContent({ detail, isLoading, isClean }: PanelContentProps) {
  // Panel header styling: amber for raw, emerald for clean
  const headerBg    = isClean ? 'bg-emerald-900/20' : 'bg-amber-900/20'
  const headerBorder= isClean ? 'border-emerald-500/25' : 'border-amber-500/25'
  const headerText  = isClean ? 'text-emerald-400' : 'text-amber-400'
  const headerIcon  = isClean
    ? <Sparkles size={11} className="text-emerald-400" />
    : <Database size={11} className="text-amber-400" />
  const headerLabel = isClean ? 'Clean Data' : 'Raw Data'

  return (
    <div className="flex-1 min-w-0 flex flex-col overflow-hidden border-r border-[#2A2A2A] last:border-r-0">
      {/* Panel label */}
      <div className={`px-4 py-2 flex items-center gap-1.5 border-b ${headerBorder} ${headerBg} flex-shrink-0`}>
        {headerIcon}
        <span className={`text-[10px] font-semibold uppercase tracking-wider ${headerText}`}>
          {headerLabel}
        </span>
        {isClean && (
          <span className="ml-auto text-[9px] text-emerald-600 italic">after preprocessing</span>
        )}
      </div>

      {/* Scrollable body */}
      <div className="flex-1 overflow-y-auto p-4">
        {/* Loading skeleton */}
        {isLoading && (
          <div className="space-y-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="bg-[#1A1A1A] animate-pulse rounded-xl h-16" />
            ))}
          </div>
        )}

        {/* Clean panel — no analysis run yet */}
        {!isLoading && isClean && !detail?.is_clean_data && (
          <div className="flex flex-col items-center justify-center h-48 gap-3 text-center px-4">
            <Sparkles size={28} className="text-[#3A3A3A]" />
            <p className="text-[#52525B] text-xs leading-relaxed">
              Run analysis first to compare raw and clean data statistics.
            </p>
          </div>
        )}

        {detail && (!isClean || detail.is_clean_data) && (
          <>
            {/* ── Numeric: stats grid + histogram ─────────────────── */}
            {detail.statistics && (
              <>
                <div className="grid grid-cols-2 gap-2 mb-4">
                  {STATS_CONFIG.map(({ label, key }) => (
                    <div key={label} className="bg-[#1A1A1A] rounded-xl p-3 text-center">
                      <p className="text-[#52525B] text-[10px] mb-1">{label}</p>
                      <p className="text-white font-semibold text-sm">
                        {formatValue(detail.statistics![key])}
                      </p>
                    </div>
                  ))}
                </div>

                {detail.histogram && detail.histogram.length > 0 && (
                  <>
                    <p className="text-[#52525B] text-[10px] font-medium mb-2 uppercase tracking-wider">
                      Distribution
                    </p>
                    <ResponsiveContainer width="100%" height={180}>
                      <BarChart
                        data={detail.histogram.map((b) => ({
                          label: b.bin_label,
                          value: b.count,
                        }))}
                        margin={{ top: 18, right: 6, bottom: 38, left: 34 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="#2A2A2A" vertical={false} />
                        <XAxis
                          dataKey="label"
                          stroke="#2A2A2A"
                          tick={{ fontSize: 8, fill: '#71717A' }}
                          tickLine={false}
                          tickFormatter={(v) => truncate(formatAxisLabel(v), 9)}
                          angle={0}
                          textAnchor="middle"
                          height={38}
                          interval={detail.histogram.length > 8 ? 1 : 0}
                        />
                        <YAxis
                          stroke="#2A2A2A"
                          tick={{ fontSize: 8, fill: '#71717A' }}
                          tickLine={false}
                          axisLine={false}
                          tickFormatter={formatValue}
                          width={30}
                        />
                        <Tooltip
                          contentStyle={TOOLTIP_STYLE}
                          labelStyle={TOOLTIP_LABEL_STYLE}
                          itemStyle={TOOLTIP_ITEM_STYLE}
                          formatter={(v: unknown) => [formatValue(Number(v ?? 0)), 'Count']}
                        />
                        <Bar dataKey="value" radius={[3, 3, 0, 0]} maxBarSize={30}>
                          {detail.histogram.map((_, i) => (
                            <Cell
                              key={i}
                              fill={isClean ? '#10B981' : '#F59E0B'}
                              fillOpacity={0.85}
                            />
                          ))}
                          <LabelList
                            dataKey="value"
                            position="top"
                            formatter={(v: unknown) => formatValue(Number(v ?? 0))}
                            style={{ fill: '#A1A1AA', fontSize: 8 }}
                          />
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </>
                )}
              </>
            )}

            {/* ── Categorical / Boolean: pie or bar chart ───────── */}
            {detail.value_counts && detail.value_counts.length > 0 && (
              <>
                <p className="text-[#52525B] text-[10px] font-medium mb-2 uppercase tracking-wider">
                  Category Distribution
                </p>
                {detail.value_counts.length <= 12 ? (
                  <ResponsiveContainer width="100%" height={220}>
                    <PieChart>
                      <Pie
                        data={detail.value_counts.map((v) => ({
                          name: v.value,
                          value: v.count,
                        }))}
                        dataKey="value"
                        nameKey="name"
                        cx="38%"
                        cy="50%"
                        outerRadius={70}
                        innerRadius={30}
                        paddingAngle={2}
                      >
                        {detail.value_counts.map((_, i) => (
                          <Cell key={i} fill={DRAWER_COLORS[i % DRAWER_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={TOOLTIP_STYLE}
                        labelStyle={TOOLTIP_LABEL_STYLE}
                        itemStyle={TOOLTIP_ITEM_STYLE}
                        formatter={(v: unknown, name: unknown) => [
                          formatValue(Number(v ?? 0)),
                          String(name),
                        ]}
                      />
                      <Legend
                        layout="vertical"
                        align="right"
                        verticalAlign="middle"
                        iconType="circle"
                        iconSize={7}
                        formatter={(value) => (
                          <span style={{ color: '#A1A1AA', fontSize: 9 }}>
                            {truncate(String(value), 12)}
                          </span>
                        )}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <ResponsiveContainer
                    width="100%"
                    height={Math.min(detail.value_counts.length * 24 + 16, 260)}
                  >
                    <BarChart
                      layout="vertical"
                      data={detail.value_counts.map((v) => ({
                        name: truncate(v.value, 16),
                        count: v.count,
                      }))}
                      margin={{ top: 4, right: 36, bottom: 4, left: 4 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#2A2A2A" horizontal={false} />
                      <XAxis
                        type="number"
                        stroke="#2A2A2A"
                        tick={{ fontSize: 8, fill: '#71717A' }}
                        tickLine={false}
                        tickFormatter={formatValue}
                      />
                      <YAxis
                        type="category"
                        dataKey="name"
                        stroke="#2A2A2A"
                        tick={{ fontSize: 8, fill: '#71717A' }}
                        width={80}
                        tickLine={false}
                        axisLine={false}
                      />
                      <Tooltip
                        contentStyle={TOOLTIP_STYLE}
                        labelStyle={TOOLTIP_LABEL_STYLE}
                        itemStyle={TOOLTIP_ITEM_STYLE}
                        formatter={(v: unknown) => [formatValue(Number(v ?? 0)), 'Count']}
                      />
                      <Bar dataKey="count" radius={[0, 3, 3, 0]} maxBarSize={16}>
                        {detail.value_counts.map((_, i) => (
                          <Cell key={i} fill={DRAWER_COLORS[i % DRAWER_COLORS.length]} />
                        ))}
                        <LabelList
                          dataKey="count"
                          position="right"
                          formatter={(v: unknown) => formatValue(Number(v ?? 0))}
                          style={{ fill: '#A1A1AA', fontSize: 8 }}
                        />
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </>
            )}

            {/* ── Metadata ─────────────────────────────────────────── */}
            <div className="space-y-2 mt-4 pt-4 border-t border-[#2A2A2A]">
              {/* Null values — show count, not percentage */}
              {detail.null_count !== undefined && (
                <div className="flex items-center justify-between text-xs">
                  <span className="text-[#52525B] flex items-center gap-1">
                    <AlertCircle size={11} />
                    Null values
                  </span>
                  <span className="text-[#A1A1AA]">
                    {(detail.null_count ?? 0).toLocaleString()}
                    {detail.total_rows
                      ? <span className="text-[#52525B]"> / {detail.total_rows.toLocaleString()}</span>
                      : null
                    }
                  </span>
                </div>
              )}

              {detail.cardinality !== undefined && (
                <div className="flex items-center justify-between text-xs">
                  <span className="text-[#52525B] flex items-center gap-1">
                    <Hash size={11} />
                    Cardinality
                  </span>
                  <span className="text-[#A1A1AA]">
                    {detail.cardinality.toLocaleString()}
                  </span>
                </div>
              )}

              {detail.has_outliers && (
                <div className="text-xs">
                  <div className="flex items-center justify-between">
                    <span className="text-[#52525B] flex items-center gap-1">
                      <AlertTriangle size={11} />
                      Outliers
                    </span>
                    <span className="text-amber-400">
                      {detail.outlier_count ?? 0} detected
                    </span>
                  </div>
                  {(() => {
                    const vals = detail.outlier_values ?? detail.outliers ?? []
                    return vals.length > 0 ? <OutlierValuesList values={vals} /> : null
                  })()}
                </div>
              )}

              {detail.semantic_tag && (
                <div className="flex items-center justify-between text-xs">
                  <span className="text-[#52525B] flex items-center gap-1">
                    <Tag size={11} />
                    Semantic tag
                  </span>
                  <span className="text-[#A1A1AA]">{detail.semantic_tag}</span>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// ColumnDrawer
// ---------------------------------------------------------------------------

interface ColumnDrawerProps {
  columnName: string | null
  onClose: () => void
}

export default function ColumnDrawer({ columnName, onClose }: ColumnDrawerProps) {
  const sessionId = useSessionStore((s) => s.sessionId)
  const profile   = useSessionStore((s) => s.profile)
  const col       = profile?.columns.find((c) => c.name === columnName)

  // Raw data query
  const { data: rawData, isLoading: rawLoading } = useQuery({
    queryKey: ['column', sessionId, columnName, 'raw'],
    queryFn:  () => getColumnDetail(sessionId!, columnName!, false),
    enabled:  !!sessionId && !!columnName,
  })

  // Clean data query — runs in parallel; only shows results if backend
  // returns is_clean_data=true (meaning a clean DataFrame exists).
  const { data: cleanData, isLoading: cleanLoading } = useQuery({
    queryKey: ['column', sessionId, columnName, 'clean'],
    queryFn:  () => getColumnDetail(sessionId!, columnName!, true),
    enabled:  !!sessionId && !!columnName,
  })

  const rawDetail   = rawData?.detail   as ColumnDetail | undefined
  const cleanDetail = cleanData?.detail as ColumnDetail | undefined

  return (
    <AnimatePresence>
      {columnName && (
        <motion.div
          key={columnName}
          initial={{ x: '100%' }}
          animate={{ x: 0 }}
          exit={{ x: '100%' }}
          transition={{ type: 'spring', damping: 30, stiffness: 300 }}
          className="fixed right-0 top-14 bottom-0 bg-[#111111] border-l border-[#2A2A2A] z-50 flex flex-col shadow-2xl"
          style={{ width: 'min(760px, 90vw)' }}
        >
          {/* ── Shared header ──────────────────────────────────────────── */}
          <div className="p-4 border-b border-[#2A2A2A] flex items-center justify-between flex-shrink-0">
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-white font-semibold truncate">{columnName}</span>
              {col && (() => {
                const cfg = getDtypeConfig(col.dtype)
                return (
                  <span className={`text-[10px] rounded-full px-2 py-0.5 border flex items-center gap-1 flex-shrink-0 ${cfg.bg} ${cfg.border} ${cfg.text}`}>
                    {cfg.icon}
                    {cfg.label}
                  </span>
                )
              })()}
            </div>
            <button onClick={onClose} className="flex-shrink-0 ml-2 cursor-pointer">
              <X size={18} className="text-[#52525B] hover:text-white transition-colors" />
            </button>
          </div>

          {/* ── Two-panel body ─────────────────────────────────────────── */}
          <div className="flex-1 flex overflow-hidden">
            <PanelContent
              detail={rawDetail}
              isLoading={rawLoading}
              isClean={false}
            />
            <PanelContent
              detail={cleanDetail}
              isLoading={cleanLoading}
              isClean={true}
            />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
