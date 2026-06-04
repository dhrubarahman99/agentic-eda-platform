import React from 'react'
import {
  LayoutGrid, Database, Columns2, Target,
  CircleDashed, Copy, Hash, Type, CalendarDays,
  CheckCircle2, AlertCircle, XCircle,
  AlertTriangle, Info, MinusCircle,
  ExternalLink,
} from 'lucide-react'
import { PieChart, Pie, Cell, Tooltip } from 'recharts'
import { useQuery } from '@tanstack/react-query'
import { useSessionStore } from '@/stores/sessionStore'
import { getPreview } from '@/api/dashboard'
import type { DatasetProfile, DashboardResponse } from '@/api/types'

// ─── Colour tokens ─────────────────────────────────────────────────────────

const C = {
  purple:  '#7C3AED',
  blue:    '#3B82F6',
  green:   '#10B981',
  teal:    '#06B6D4',
  orange:  '#F59E0B',
  red:     '#EF4444',
  redPink: '#FF4363',
  gray:    '#6B7280',
}

// ─── QualityBadge ──────────────────────────────────────────────────────────

function QualityBadge({ status }: { status: string }) {
  if (status === 'good') {
    return (
      <span className="bg-emerald-900/30 border border-emerald-500/30 text-emerald-400 rounded-xl px-2.5 py-1 text-xs flex items-center gap-1 flex-shrink-0">
        <CheckCircle2 size={11} />
        <span className="font-semibold">Good</span>
      </span>
    )
  }
  if (status === 'fair') {
    return (
      <span className="bg-amber-900/30 border border-amber-500/30 text-amber-400 rounded-xl px-2.5 py-1 text-xs flex items-center gap-1 flex-shrink-0">
        <AlertCircle size={11} />
        <span className="font-semibold">Fair</span>
      </span>
    )
  }
  return (
    <span className="bg-red-900/30 border border-red-500/30 text-red-400 rounded-xl px-2.5 py-1 text-xs flex items-center gap-1 flex-shrink-0">
      <XCircle size={11} />
      <span className="font-semibold">Poor</span>
    </span>
  )
}

// ─── TopCard ───────────────────────────────────────────────────────────────
// `large` renders the value in a bigger, bolder font (for Rows / Columns).

interface TopCardProps {
  iconColor: string
  icon: React.ReactNode
  label: string
  children: React.ReactNode
  large?: boolean
}

function TopCard({ iconColor, icon, label, children, large = false }: TopCardProps) {
  return (
    <div className="bg-[#0F0F0F] border border-[#1E1E1E] rounded-xl p-4 flex items-start gap-3 flex-1 min-w-[120px]">
      <div
        className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
        style={{ backgroundColor: iconColor + '20', border: `1px solid ${iconColor}40` }}
      >
        <span style={{ color: iconColor }}>{icon}</span>
      </div>
      <div className="min-w-0 flex-1 overflow-hidden">
        <p className="text-[#52525B] text-[10px] uppercase tracking-widest mb-1 font-medium">{label}</p>
        <div className={large
          ? 'text-white text-2xl font-bold leading-none'
          : 'text-white text-sm font-semibold min-w-0 overflow-hidden'
        }>
          {children}
        </div>
      </div>
    </div>
  )
}

// ─── MetricCard ────────────────────────────────────────────────────────────

interface MetricCardProps {
  icon: React.ReactNode
  iconColor: string
  label: string
  value: string | number
  valueColor: string
  subtitle: string
  barColor: string
  barPct: number
}

function MetricCard({
  icon, iconColor, label, value, valueColor, subtitle, barColor, barPct,
}: MetricCardProps) {
  return (
    <div className="relative bg-[#0F0F0F] border border-[#1E1E1E] rounded-xl p-4 flex-1 min-w-[110px] overflow-hidden">
      <div className="flex items-center gap-1.5 mb-2.5" style={{ color: iconColor }}>
        {icon}
        <span className="text-[10px] uppercase tracking-widest font-medium text-[#52525B]">{label}</span>
      </div>
      <div className="text-2xl font-bold leading-none mb-1.5" style={{ color: valueColor }}>
        {value}
      </div>
      <div className="text-[#52525B] text-[11px] leading-snug">{subtitle}</div>
      {/* Accent bar */}
      <div className="absolute bottom-0 left-0 right-0 h-[3px] bg-[#1A1A1A]">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{
            width: `${Math.min(Math.max(barPct, 0), 100)}%`,
            backgroundColor: barColor,
          }}
        />
      </div>
    </div>
  )
}

// ─── DonutChart ────────────────────────────────────────────────────────────

interface DonutEntry { name: string; value: number; color: string }

interface DonutChartProps {
  data: DonutEntry[]
  centerMain: string
  centerSub: string
  totalForLegend: number
}

function DonutChart({ data, centerMain, centerSub, totalForLegend }: DonutChartProps) {
  const pieData = data.filter((d) => d.value > 0)
  const displayData = pieData.length > 0 ? pieData : [{ name: 'empty', value: 1, color: '#1E1E1E' }]

  return (
    <div className="flex items-center gap-5">
      {/* Donut */}
      <div className="relative flex-shrink-0" style={{ width: 140, height: 140 }}>
        <PieChart width={140} height={140}>
          <Pie
            data={displayData}
            cx={70}
            cy={70}
            innerRadius={44}
            outerRadius={65}
            dataKey="value"
            strokeWidth={0}
            paddingAngle={pieData.length > 1 ? 2 : 0}
          >
            {displayData.map((entry, i) => (
              <Cell key={i} fill={entry.color} />
            ))}
          </Pie>
          {pieData.length > 0 && (
            <Tooltip
              contentStyle={{
                background: '#1A1A1A',
                border: '1px solid #2A2A2A',
                borderRadius: 8,
                fontSize: 12,
              }}
              itemStyle={{ color: '#A1A1AA' }}
            />
          )}
        </PieChart>
        {/* Perfectly centered overlay text */}
        <div
          className="absolute flex flex-col items-center justify-center pointer-events-none"
          style={{ inset: 0 }}
        >
          <span className="text-white font-bold text-base leading-none">{centerMain}</span>
          <span className="text-[#71717A] text-[10px] mt-1 leading-none">{centerSub}</span>
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-col gap-2.5 flex-1 min-w-0">
        {data.map((d) => (
          <div key={d.name} className="flex items-center gap-2">
            <span
              className="w-2.5 h-2.5 rounded-full flex-shrink-0"
              style={{ backgroundColor: d.color }}
            />
            <span className="text-[#A1A1AA] text-xs flex-1 min-w-0 truncate">{d.name}</span>
            <span className="text-white text-xs font-semibold flex-shrink-0 tabular-nums">
              {d.value.toLocaleString()}
            </span>
            <span className="text-[#52525B] text-[10px] flex-shrink-0 tabular-nums">
              ({totalForLegend > 0 ? ((d.value / totalForLegend) * 100).toFixed(1) : '0.0'}%)
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── QualityRow ────────────────────────────────────────────────────────────

interface QualityRowProps {
  iconColor: string
  icon: React.ReactNode
  label: string
  description: string
  count: number
}

function QualityRow({ iconColor, icon, label, description, count }: QualityRowProps) {
  return (
    <div className="flex items-center gap-3 py-2.5">
      <div
        className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
        style={{ backgroundColor: iconColor + '20', border: `1px solid ${iconColor}40` }}
      >
        <span style={{ color: iconColor }}>{icon}</span>
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-white text-xs font-medium leading-none mb-0.5">{label}</p>
        <p className="text-[#52525B] text-[11px] leading-snug">{description}</p>
      </div>
      <span
        className="text-xs font-bold px-2.5 py-0.5 rounded-full flex-shrink-0 tabular-nums"
        style={{
          backgroundColor: iconColor + '20',
          color: iconColor,
          border: `1px solid ${iconColor}40`,
          minWidth: '2rem',
          textAlign: 'center',
        }}
      >
        {count}
      </span>
    </div>
  )
}

// ─── Main component ────────────────────────────────────────────────────────

interface DatasetSummaryCardProps {
  profile: DatasetProfile
  dashboardData: DashboardResponse
}

export default function DatasetSummaryCard({ profile, dashboardData }: DatasetSummaryCardProps) {
  const sessionId    = useSessionStore((s) => s.sessionId)
  const setActiveTab = useSessionStore((s) => s.setActiveTab)

  const { data: previewData, isLoading: previewLoading } = useQuery({
    queryKey: ['preview-summary', sessionId],
    queryFn: () => getPreview(sessionId!, 5),
    enabled: !!sessionId,
    staleTime: 60_000,
  })

  const card = profile.summary_card
  const totalCells   = card.row_count * card.col_count
  const missingCells = card.total_missing_cells ?? Math.round(card.missing_rate_overall * totalCells)
  const missingPct   = totalCells > 0
    ? Math.min((missingCells / totalCells) * 100, 100)
    : card.missing_rate_overall * 100

  const colCount       = Math.max(card.col_count, 1)
  const numericPct     = (card.numeric_col_count / colCount) * 100
  const categoricalPct = (card.categorical_col_count / colCount) * 100
  const datetimePct    = (card.datetime_col_count / colCount) * 100

  // Missing value severity color
  const missingColor = missingPct > 10 ? C.red : missingPct > 2 ? C.orange : C.green

  // Donut: Data Types
  const dtypeData: DonutEntry[] = [
    { name: 'Numeric',     value: card.numeric_col_count,     color: C.blue   },
    { name: 'Categorical', value: card.categorical_col_count, color: C.orange },
    { name: 'Date/Time',   value: card.datetime_col_count,    color: C.teal   },
  ]

  // Donut: Missing Values
  const completeCells = Math.max(totalCells - missingCells, 0)
  const missingDonutData: DonutEntry[] = [
    { name: 'Complete', value: completeCells, color: C.green },
    { name: 'Missing',  value: missingCells,  color: C.red   },
  ]

  // Quality counts
  const validCount    = (profile.columns ?? []).filter((c) => c.null_rate < 1.0).length
  const highCardCount = profile.data_quality?.flags?.filter((f) => f.flag_type === 'high_cardinality').length ?? 0
  const lowVarCount   = profile.data_quality?.flags?.filter((f) => f.flag_type === 'low_variance').length ?? 0
  const constantCount = (profile.columns ?? []).filter((c) => c.cardinality === 1).length

  return (
    <div className="bg-[#111111] rounded-2xl border border-[#1E1E1E] p-5 space-y-4">

      {/* ── A. Header ─────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-white font-semibold text-sm">Dataset Summary</h2>
          <p className="text-[#52525B] text-xs mt-0.5">Overview of your dataset at a glance.</p>
        </div>
        <button
          onClick={() => setActiveTab('columns')}
          className="flex items-center gap-1.5 text-purple-400 hover:text-purple-300 text-xs font-medium border border-purple-800/40 rounded-lg px-3 py-1.5 hover:bg-purple-900/20 transition-all duration-150 cursor-pointer flex-shrink-0"
        >
          View Profiling Details
          <ExternalLink size={11} />
        </button>
      </div>

      {/* ── B. Top metric row (4 cards, no File Size) ─────────────────── */}
      <div className="flex flex-wrap gap-2">
        <TopCard iconColor={C.purple} icon={<LayoutGrid size={15} />} label="Dataset">
          <div className="flex items-center gap-2 flex-wrap mt-0.5">
            <span className="truncate max-w-[100px] text-sm font-semibold">{dashboardData.filename}</span>
            <QualityBadge status={card.quality_status} />
          </div>
        </TopCard>

        <TopCard iconColor={C.blue} icon={<Database size={15} />} label="Rows" large>
          {card.row_count.toLocaleString()}
        </TopCard>

        <TopCard iconColor={C.teal} icon={<Columns2 size={15} />} label="Columns" large>
          {card.col_count}
        </TopCard>

        <TopCard iconColor={C.redPink} icon={<Target size={15} />} label="Target Column">
          {card.potential_target_column
            ? <span className="font-semibold" style={{ color: C.redPink }}>{card.potential_target_column}</span>
            : <span className="text-[#52525B]">—</span>
          }
        </TopCard>
      </div>

      {/* ── C. Metric row ─────────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-2">
        <MetricCard
          icon={<CircleDashed size={12} />}
          iconColor={missingColor}
          label="Missing Values"
          value={`${missingPct.toFixed(1)}%`}
          valueColor={missingColor}
          subtitle={`${missingCells.toLocaleString()} / ${totalCells.toLocaleString()} cells`}
          barColor={missingColor}
          barPct={missingPct}
        />
        <MetricCard
          icon={<Copy size={12} />}
          iconColor={card.duplicate_row_count ? C.orange : C.gray}
          label="Duplicate Rows"
          value={(card.duplicate_row_count ?? 0).toLocaleString()}
          valueColor={card.duplicate_row_count ? C.orange : C.gray}
          subtitle={`${card.row_count > 0 ? (((card.duplicate_row_count ?? 0) / card.row_count) * 100).toFixed(1) : '0.0'}% of total`}
          barColor={card.duplicate_row_count ? C.orange : C.gray}
          barPct={card.row_count > 0 ? ((card.duplicate_row_count ?? 0) / card.row_count) * 100 : 0}
        />
        <MetricCard
          icon={<Hash size={12} />}
          iconColor={C.blue}
          label="Numeric Columns"
          value={card.numeric_col_count}
          valueColor={C.blue}
          subtitle={`${numericPct.toFixed(1)}% of total`}
          barColor={C.blue}
          barPct={numericPct}
        />
        <MetricCard
          icon={<Type size={12} />}
          iconColor={C.orange}
          label="Categorical Columns"
          value={card.categorical_col_count}
          valueColor={C.orange}
          subtitle={`${categoricalPct.toFixed(1)}% of total`}
          barColor={C.orange}
          barPct={categoricalPct}
        />
        <MetricCard
          icon={<CalendarDays size={12} />}
          iconColor={C.teal}
          label="Date/Time Columns"
          value={card.datetime_col_count}
          valueColor={C.teal}
          subtitle={`${datetimePct.toFixed(1)}% of total`}
          barColor={C.teal}
          barPct={datetimePct}
        />
      </div>

      {/* ── D. Overview panels ────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-3">

        {/* D1. Data Types */}
        <div className="bg-[#0F0F0F] border border-[#1E1E1E] rounded-xl p-4 flex-1 min-w-[220px]">
          <p className="text-white text-xs font-semibold mb-4">Data Types Overview</p>
          <DonutChart
            data={dtypeData}
            centerMain={String(card.col_count)}
            centerSub="Total"
            totalForLegend={card.col_count}
          />
          <div className="flex items-center gap-1.5 mt-4 text-[#52525B] text-[11px]">
            <Info size={11} />
            Based on profiled data types
          </div>
        </div>

        {/* D2. Missing Values */}
        <div className="bg-[#0F0F0F] border border-[#1E1E1E] rounded-xl p-4 flex-1 min-w-[220px]">
          <p className="text-white text-xs font-semibold mb-4">Missing Values Overview</p>
          <DonutChart
            data={missingDonutData}
            centerMain={`${missingPct.toFixed(1)}%`}
            centerSub="Missing"
            totalForLegend={totalCells}
          />
          <div className="flex items-center gap-1.5 mt-4 text-[#52525B] text-[11px]">
            <Info size={11} />
            Across all cells
          </div>
        </div>

        {/* D3. Column Quality Summary */}
        <div className="bg-[#0F0F0F] border border-[#1E1E1E] rounded-xl p-4 flex-1 min-w-[220px]">
          <p className="text-white text-xs font-semibold mb-1">Column Quality Summary</p>
          <div className="divide-y divide-[#1A1A1A]">
            <QualityRow
              iconColor={C.green}
              icon={<CheckCircle2 size={14} />}
              label="Valid Columns"
              description="No columns with all values missing"
              count={validCount}
            />
            <QualityRow
              iconColor={C.red}
              icon={<AlertTriangle size={14} />}
              label="High Cardinality"
              description="Columns with many unique values"
              count={highCardCount}
            />
            <QualityRow
              iconColor={C.orange}
              icon={<Info size={14} />}
              label="Low Variance"
              description="Columns with low variation in values"
              count={lowVarCount}
            />
            <QualityRow
              iconColor={C.gray}
              icon={<MinusCircle size={14} />}
              label="Constant Columns"
              description="Columns with a single unique value"
              count={constantCount}
            />
          </div>
        </div>
      </div>

      {/* ── E. Dataset Preview ────────────────────────────────────────── */}
      <div className="bg-[#0F0F0F] border border-[#1E1E1E] rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#1E1E1E]">
          <p className="text-white text-xs font-semibold">Dataset Preview (First 3 Rows)</p>
          <button
            onClick={() => setActiveTab('preview')}
            className="flex items-center gap-1.5 text-purple-400 hover:text-purple-300 text-xs font-medium cursor-pointer transition-colors"
          >
            View Full Data
            <ExternalLink size={11} />
          </button>
        </div>

        {/* Skeleton */}
        {previewLoading && !previewData && (
          <div className="p-4 space-y-2 animate-pulse">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-6 bg-[#1E1E1E] rounded-md" />
            ))}
          </div>
        )}

        {/* Table */}
        {previewData && (() => {
          const visibleCols = previewData.columns.slice(0, 8)
          const extraCols   = previewData.columns.length - 8
          const rows        = previewData.rows.slice(0, 3)
          return (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-purple-950/40 border-b border-[#1E1E1E]">
                    <th className="px-3 py-2 text-left text-purple-300 font-semibold whitespace-nowrap border-r border-[#1E1E1E] text-[11px]">
                      Row ID
                    </th>
                    {visibleCols.map((col) => (
                      <th
                        key={col}
                        className="px-3 py-2 text-left text-purple-300 font-semibold whitespace-nowrap border-r border-[#1E1E1E] last:border-r-0 text-[11px] max-w-[140px]"
                      >
                        <span className="block truncate">{col}</span>
                      </th>
                    ))}
                    {extraCols > 0 && (
                      <th className="px-3 py-2 text-left text-[#52525B] font-medium whitespace-nowrap text-[11px]">
                        … +{extraCols} more columns
                      </th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, rowIdx) => (
                    <tr
                      key={rowIdx}
                      className="border-t border-[#1A1A1A] hover:bg-[#141414] transition-colors"
                    >
                      <td className="px-3 py-2 text-[#71717A] font-medium border-r border-[#1A1A1A] tabular-nums">
                        {rowIdx + 1}
                      </td>
                      {visibleCols.map((col) => {
                        const raw = String(row[col] ?? '—')
                        const display = raw.length > 28 ? raw.slice(0, 25) + '…' : raw
                        return (
                          <td
                            key={col}
                            className="px-3 py-2 text-[#A1A1AA] border-r border-[#1A1A1A] last:border-r-0 max-w-[140px]"
                            title={raw}
                          >
                            <span className="block truncate">{display}</span>
                          </td>
                        )
                      })}
                      {extraCols > 0 && <td className="px-3 py-2 text-[#52525B]">…</td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        })()}
      </div>
    </div>
  )
}
