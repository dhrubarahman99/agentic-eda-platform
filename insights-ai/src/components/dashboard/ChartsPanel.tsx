import { useState, useMemo } from 'react'
import { BarChart2, BarChart3, TrendingUp, PieChart, Crosshair } from 'lucide-react'
import { motion } from 'framer-motion'
import { useSessionStore } from '@/stores/sessionStore'
import { useChatStore } from '@/stores/chatStore'
import type { ChartSpec, ChartType } from '@/api/types'
import { ExpandedChartModal } from './ChartCard'

// ─── Helpers ───────────────────────────────────────────────────────────────

function chartTypeIcon(type: ChartType) {
  switch (type) {
    case 'line':    return <TrendingUp size={11} className="text-blue-400" />
    case 'pie':     return <PieChart   size={11} className="text-amber-400" />
    case 'scatter': return <Crosshair  size={11} className="text-green-400" />
    default:        return <BarChart3  size={11} className="text-purple-400" />
  }
}

function chartTypeLabel(type: ChartType): string {
  switch (type) {
    case 'line':      return 'Line'
    case 'pie':       return 'Pie'
    case 'scatter':   return 'Scatter'
    case 'histogram': return 'Histogram'
    default:          return 'Bar'
  }
}

// ─── Types ─────────────────────────────────────────────────────────────────

interface SessionChart {
  id: string
  chart: ChartSpec
  source: 'insight' | 'chat'
}

// ─── ChartsPanel ───────────────────────────────────────────────────────────

export default function ChartsPanel() {
  const sessionId   = useSessionStore((s) => s.sessionId)
  const insights    = useSessionStore((s) => s.insights)
  const getMessages = useChatStore((s) => s.getMessages)

  const [expandedChart, setExpandedChart] = useState<ChartSpec | null>(null)

  const charts: SessionChart[] = useMemo(() => {
    const result: SessionChart[] = []

    insights.forEach((ins) => {
      if (ins.chart) {
        result.push({ id: `insight-${ins.insight_id}`, chart: ins.chart, source: 'insight' })
      }
    })

    getMessages(sessionId).forEach((msg) => {
      if (msg.queryResult?.chart) {
        result.push({ id: `chat-${msg.id}`, chart: msg.queryResult.chart, source: 'chat' })
      }
    })

    return result
  }, [insights, sessionId, getMessages])

  return (
    <div className="flex flex-col h-full border-l border-[#2A2A2A] bg-[#0F0F0F]">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[#2A2A2A] flex items-center gap-2 flex-shrink-0">
        <BarChart2 size={14} className="text-purple-400" />
        <span className="text-white font-semibold text-sm">Charts</span>
        {charts.length > 0 && (
          <span className="ml-auto text-[11px] text-[#52525B] bg-[#1A1A1A] border border-[#2A2A2A] rounded-full px-2 py-0.5">
            {charts.length}
          </span>
        )}
      </div>

      {/* Chart list */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {charts.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-2 text-center px-2">
            <BarChart2 size={28} className="text-[#2A2A2A]" />
            <p className="text-[#52525B] text-xs leading-relaxed">
              Charts from insights and queries will appear here
            </p>
          </div>
        ) : (
          charts.map((item) => (
            <motion.button
              key={item.id}
              initial={{ opacity: 0, x: 8 }}
              animate={{ opacity: 1, x: 0 }}
              onClick={() => setExpandedChart(item.chart)}
              className="w-full text-left bg-[#1A1A1A] hover:bg-[#222222] border border-[#2A2A2A] hover:border-purple-500/30 rounded-xl p-3 transition-all duration-150 cursor-pointer group"
            >
              <p className="text-xs text-[#A1A1AA] group-hover:text-white transition-colors leading-snug line-clamp-2 mb-2">
                {item.chart.title || 'Untitled chart'}
              </p>
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1 text-[10px] text-[#52525B]">
                  {chartTypeIcon(item.chart.chart_type)}
                  {chartTypeLabel(item.chart.chart_type)}
                </span>
                <span className={`text-[10px] rounded-full px-2 py-0.5 border ${
                  item.source === 'insight'
                    ? 'bg-purple-900/20 border-purple-500/20 text-purple-400'
                    : 'bg-blue-900/20 border-blue-500/20 text-blue-400'
                }`}>
                  {item.source === 'insight' ? 'Auto' : 'Query'}
                </span>
              </div>
            </motion.button>
          ))
        )}
      </div>

      {/* Expanded chart modal — full 70vw overlay */}
      {expandedChart && (
        <ExpandedChartModal
          chart={expandedChart}
          onClose={() => setExpandedChart(null)}
        />
      )}
    </div>
  )
}
