import {
  ResponsiveContainer,
  BarChart, Bar, Cell, LabelList,
  AreaChart, Area,
  ScatterChart, Scatter,
  PieChart, Pie,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, Label,
} from 'recharts'
import type { ChartSpec, ChartType } from '@/api/types'

// ─── Colour palette ────────────────────────────────────────────────────────
const CHART_COLORS = [
  '#818CF8', '#34D399', '#F59E0B', '#60A5FA', '#F472B6',
  '#A78BFA', '#2DD4BF', '#FB923C', '#4ADE80', '#E879F9',
]

// ─── Shared style tokens ───────────────────────────────────────────────────
const TOOLTIP_STYLE: React.CSSProperties = {
  backgroundColor: '#1A1A1A',
  border: '1px solid #333333',
  borderRadius: '12px',
  color: '#F4F4F5',
  fontSize: '12px',
  padding: '10px 14px',
  boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
}

const TOOLTIP_LABEL_STYLE: React.CSSProperties = {
  color: '#E4E4E7',
  marginBottom: 6,
  fontWeight: 700,
  fontSize: 12,
}

const TOOLTIP_ITEM_STYLE: React.CSSProperties = {
  color: '#E4E4E7',
  fontWeight: 500,
}

const TICK_STYLE = { fill: '#71717A', fontSize: 11, fontFamily: 'inherit' }

const PIE_MARGIN   = { top: 4,  right: 8,  bottom: 4,  left: 8  }
const SCAT_MARGIN  = { top: 12, right: 16, bottom: 48, left: 78 }

// ─── Helpers ───────────────────────────────────────────────────────────────
export function formatValue(v: number): string {
  if (!isFinite(v) || isNaN(v)) return '—'
  const abs = Math.abs(v)
  if (abs === 0) return '0'
  if (abs >= 1_000) {
    return v.toLocaleString('en-US', { maximumFractionDigits: 2 })
  }
  if (abs >= 1) {
    return Number.isInteger(v)
      ? v.toLocaleString('en-US')
      : v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  }
  if (abs >= 0.001)         return v.toFixed(4)
  return v.toFixed(6)
}

export function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n) + '…' : s
}

function formatAxisPart(value: string): string {
  const trimmed = value.trim()
  if (/^[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?$/i.test(trimmed)) {
    return formatValue(Number(trimmed))
  }
  return trimmed
}

export function formatAxisLabel(value: unknown): string {
  const raw = String(value ?? '').trim()
  if (!raw) return ''

  const parts = raw.split(/\s*(?:â€“|–|—)\s*|\s+-\s+/)
  if (parts.length === 2 && parts.every(Boolean)) {
    return `${formatAxisPart(parts[0])} - ${formatAxisPart(parts[1])}`
  }

  return formatAxisPart(raw)
}

// Infer a better chart type when the backend sends a generic 'bar'.
function resolveChartType(chart: ChartSpec): ChartType {
  const t = chart.chart_type
  if (t === 'scatter' || t === 'pie' || t === 'line') return t
  if (t === 'histogram') return 'histogram'

  const title  = (chart.title           || '').toLowerCase()
  const xLabel = (chart.x_axis_label    || '').toLowerCase()
  const first  = String(chart.data[0]?.label ?? '')

  const timeWords = [
    'trend', 'over time', 'forecast', 'monthly', 'yearly', 'quarterly',
    'weekly', 'daily', 'growth', 'period', 'by month', 'by year', 'by week',
    'history', 'timeline',
  ]
  if (timeWords.some(w => title.includes(w) || xLabel.includes(w))) return 'line'

  const looksLikeDate =
    /^\d{4}[-/]/.test(first) ||
    /^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)/i.test(first) ||
    /^q[1-4]\b/i.test(first)

  if (looksLikeDate && chart.data.length > 3) return 'line'

  return 'bar'
}

// ─── Axis label helper ────────────────────────────────────────────────────
function AxisLabel({ value, angle, position, offset }: {
  value: string; angle?: number; position: string; offset?: number
}) {
  return (
    <Label
      value={value}
      angle={angle}
      position={position as 'insideBottom' | 'insideLeft'}
      offset={offset ?? 0}
      style={{ fill: '#52525B', fontSize: 11 }}
    />
  )
}

// ─── Component ────────────────────────────────────────────────────────────
interface InsightChartProps {
  chart: ChartSpec
}

export default function InsightChart({ chart }: InsightChartProps) {
  const resolvedType = resolveChartType(chart)
  const xLabel = chart.x_axis_label ?? ''
  const yLabel = chart.y_axis_label ?? ''

  const chartData = chart.data.map((pt) => ({
    label: pt.label,
    value: typeof pt.value === 'number' ? pt.value : Number(pt.value) || 0,
    group: pt.group,
  }))

  const showBarLabels = chartData.length <= 12

  // Detect long labels to decide rotation
  const hasLongLabels =
    chartData.some(d => formatAxisLabel(d.label).length > 12) || chartData.length > 8
  const xTickInterval = chartData.length > 10 ? Math.ceil(chartData.length / 8) : 0
  const barMargin = {
    top: 32,
    right: 20,
    bottom: hasLongLabels ? 66 : 56,
    left: 84,
  }

  // ── Bar / Histogram ──────────────────────────────────────────────────────
  if (resolvedType === 'bar' || resolvedType === 'histogram') {
    return (
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} margin={barMargin} barCategoryGap="30%">
          <CartesianGrid strokeDasharray="2 4" stroke="#1E1E1E" vertical={false} />
          <XAxis
            dataKey="label"
            stroke="#1E1E1E"
            tick={{ ...TICK_STYLE, fontSize: 10 }}
            tickLine={false}
            axisLine={{ stroke: '#2A2A2A' }}
            interval={xTickInterval}
            minTickGap={8}
            tickFormatter={(v) => truncate(formatAxisLabel(v), hasLongLabels ? 12 : 16)}
            angle={0}
            textAnchor="middle"
            height={hasLongLabels ? 48 : 36}
          >
            {xLabel && <AxisLabel value={xLabel} position="insideBottom" offset={hasLongLabels ? -24 : -22} />}
          </XAxis>
          <YAxis
            stroke="#1E1E1E"
            tick={TICK_STYLE}
            tickLine={false}
            axisLine={false}
            tickFormatter={formatValue}
            width={68}
          >
            {yLabel && <AxisLabel value={yLabel} angle={-90} position="insideLeft" offset={0} />}
          </YAxis>
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            cursor={{ fill: 'rgba(129,140,248,0.06)' }}
            formatter={(v: unknown) => [formatValue(Number(v ?? 0)), chart.y_field || 'Value']}
            labelStyle={TOOLTIP_LABEL_STYLE}
            itemStyle={TOOLTIP_ITEM_STYLE}
          />
          <Bar dataKey="value" radius={[5, 5, 0, 0]} maxBarSize={52}>
            {chartData.map((_, i) => (
              <Cell
                key={`cell-${i}`}
                fill={CHART_COLORS[i % CHART_COLORS.length]}
                fillOpacity={0.9}
              />
            ))}
            {showBarLabels && (
              <LabelList
                dataKey="value"
                position="top"
                formatter={(v: unknown) => formatValue(Number(v ?? 0))}
                style={{ fill: '#A1A1AA', fontSize: 10, fontWeight: 600 }}
              />
            )}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    )
  }

  // ── Line / Area ──────────────────────────────────────────────────────────
  if (resolvedType === 'line') {
    const hasLongLineLabels =
      chartData.some(d => formatAxisLabel(d.label).length > 12) || chartData.length > 8
    const lineTickInterval = chartData.length > 10 ? Math.ceil(chartData.length / 8) : 0
    const lineMargin = {
      top: 20,
      right: 20,
      bottom: hasLongLineLabels ? 66 : 56,
      left: 84,
    }
    return (
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={lineMargin}>
          <defs>
            <linearGradient id="areaGradFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#818CF8" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#818CF8" stopOpacity={0}   />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="2 4" stroke="#1E1E1E" vertical={false} />
          <XAxis
            dataKey="label"
            stroke="#1E1E1E"
            tick={{ ...TICK_STYLE, fontSize: 10 }}
            tickLine={false}
            axisLine={{ stroke: '#2A2A2A' }}
            interval={lineTickInterval}
            minTickGap={8}
            tickFormatter={(v) => truncate(formatAxisLabel(v), hasLongLineLabels ? 12 : 14)}
            angle={0}
            textAnchor="middle"
            height={hasLongLineLabels ? 48 : 36}
          >
            {xLabel && <AxisLabel value={xLabel} position="insideBottom" offset={hasLongLineLabels ? -24 : -22} />}
          </XAxis>
          <YAxis
            stroke="#1E1E1E"
            tick={TICK_STYLE}
            tickLine={false}
            axisLine={false}
            tickFormatter={formatValue}
            width={68}
          >
            {yLabel && <AxisLabel value={yLabel} angle={-90} position="insideLeft" offset={0} />}
          </YAxis>
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            formatter={(v: unknown) => [formatValue(Number(v ?? 0)), chart.y_field || 'Value']}
            labelStyle={TOOLTIP_LABEL_STYLE}
            itemStyle={TOOLTIP_ITEM_STYLE}
          />
          <Area
            type="monotone"
            dataKey="value"
            stroke="#818CF8"
            strokeWidth={2.5}
            fill="url(#areaGradFill)"
            dot={{ fill: '#818CF8', strokeWidth: 0, r: 3 }}
            activeDot={{ r: 5, fill: '#A5B4FC', strokeWidth: 2, stroke: '#1A1A1A' }}
          />
        </AreaChart>
      </ResponsiveContainer>
    )
  }

  // ── Scatter ──────────────────────────────────────────────────────────────
  if (resolvedType === 'scatter') {
    const scatterData = chartData.map((pt) => ({
      x: isNaN(Number(pt.label)) ? 0 : Number(pt.label),
      y: pt.value,
      name: String(pt.label),
    }))

    return (
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={SCAT_MARGIN}>
          <CartesianGrid strokeDasharray="2 4" stroke="#1E1E1E" />
          <XAxis
            type="number"
            dataKey="x"
            name={xLabel || chart.x_field}
            stroke="#1E1E1E"
            tick={TICK_STYLE}
            tickLine={false}
            axisLine={{ stroke: '#2A2A2A' }}
            tickFormatter={formatValue}
          >
            {xLabel && <AxisLabel value={xLabel} position="insideBottom" offset={-20} />}
          </XAxis>
          <YAxis
            type="number"
            dataKey="y"
            name={yLabel || chart.y_field || 'Value'}
            stroke="#1E1E1E"
            tick={TICK_STYLE}
            tickLine={false}
            axisLine={false}
            tickFormatter={formatValue}
            width={68}
          >
            {yLabel && <AxisLabel value={yLabel} angle={-90} position="insideLeft" offset={0} />}
          </YAxis>
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            cursor={{ strokeDasharray: '3 3', stroke: '#333333' }}
            formatter={(v: unknown, name: unknown) => [formatValue(Number(v ?? 0)), String(name)]}
            labelStyle={TOOLTIP_LABEL_STYLE}
            itemStyle={TOOLTIP_ITEM_STYLE}
          />
          <Scatter
            data={scatterData}
            fill="#818CF8"
            opacity={0.8}
          />
        </ScatterChart>
      </ResponsiveContainer>
    )
  }

  // ── Pie / Donut ──────────────────────────────────────────────────────────
  if (resolvedType === 'pie') {
    return (
      <ResponsiveContainer width="100%" height="100%">
        <PieChart margin={PIE_MARGIN}>
          <Pie
            data={chartData}
            dataKey="value"
            nameKey="label"
            cx="50%"
            cy="44%"
            outerRadius={88}
            innerRadius={44}
            paddingAngle={3}
            strokeWidth={0}
          >
            {chartData.map((_, i) => (
              <Cell
                key={`cell-${i}`}
                fill={CHART_COLORS[i % CHART_COLORS.length]}
                opacity={0.9}
              />
            ))}
          </Pie>
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            formatter={(v: unknown) => [formatValue(Number(v ?? 0))]}
            labelStyle={TOOLTIP_LABEL_STYLE}
            itemStyle={TOOLTIP_ITEM_STYLE}
          />
          <Legend
            iconType="circle"
            iconSize={8}
            wrapperStyle={{ paddingTop: 8 }}
            formatter={(value) => (
              <span style={{ color: '#A1A1AA', fontSize: 11 }}>
                {truncate(String(value), 22)}
              </span>
            )}
          />
        </PieChart>
      </ResponsiveContainer>
    )
  }

  return null
}
