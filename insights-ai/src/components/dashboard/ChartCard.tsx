import { useState, useRef } from 'react'
import { Download, Maximize2, X } from 'lucide-react'
import { motion } from 'framer-motion'
import type { ChartSpec } from '@/api/types'
import InsightChart from './InsightChart'

// ─── Shared PNG download helper ────────────────────────────────────────────
export function downloadChartAsPng(
  containerRef: React.RefObject<HTMLDivElement | null>,
  filename: string,
) {
  const container = containerRef.current
  if (!container) return

  const svg = container.querySelector('svg')
  if (!svg) return

  const { width, height } = svg.getBoundingClientRect()
  const w = Math.max(width, 400)
  const h = Math.max(height, 200)

  const cloned = svg.cloneNode(true) as SVGSVGElement
  cloned.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
  cloned.setAttribute('width', String(w))
  cloned.setAttribute('height', String(h))

  const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect')
  bg.setAttribute('width', '100%')
  bg.setAttribute('height', '100%')
  bg.setAttribute('fill', '#141414')
  cloned.insertBefore(bg, cloned.firstChild)

  const svgBlob = new Blob([new XMLSerializer().serializeToString(cloned)], {
    type: 'image/svg+xml;charset=utf-8',
  })
  const url = URL.createObjectURL(svgBlob)

  const scale = 2
  const canvas = document.createElement('canvas')
  canvas.width = w * scale
  canvas.height = h * scale
  const ctx = canvas.getContext('2d')
  if (!ctx) {
    URL.revokeObjectURL(url)
    return
  }
  ctx.scale(scale, scale)

  const img = new Image()
  img.onload = () => {
    ctx.drawImage(img, 0, 0)
    URL.revokeObjectURL(url)
    const a = document.createElement('a')
    a.download = `${filename}.png`
    a.href = canvas.toDataURL('image/png')
    a.click()
  }
  img.onerror = () => URL.revokeObjectURL(url)
  img.src = url
}

// ─── Expanded chart modal (reusable) ──────────────────────────────────────
interface ExpandedModalProps {
  chart: ChartSpec
  onClose: () => void
}

export function ExpandedChartModal({ chart, onClose }: ExpandedModalProps) {
  const expandedRef = useRef<HTMLDivElement>(null)
  const safeFilename = (chart.title || 'chart')
    .toLowerCase().replace(/[^a-z0-9]+/g, '_').slice(0, 50)

  return (
    <div
      className="fixed inset-0 z-[200] bg-black/85 flex items-center justify-center p-6"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 300, damping: 28 }}
        className="bg-[#141414] rounded-2xl border border-[#2A2A2A] overflow-hidden"
        style={{ width: '72vw' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-[#222222] flex-shrink-0">
          <h3 className="text-sm font-semibold text-[#C4C4C8] uppercase tracking-wider truncate">
            {chart.title}
          </h3>
          <div className="flex items-center gap-2 flex-shrink-0 ml-4">
            <button
              onClick={() => downloadChartAsPng(expandedRef, safeFilename)}
              className="flex items-center gap-1.5 text-[#71717A] hover:text-[#A1A1AA] transition-colors text-xs px-3 py-1.5 rounded-lg hover:bg-[#252525] border border-[#333] cursor-pointer"
            >
              <Download size={13} />
              Download PNG
            </button>
            <button
              onClick={onClose}
              className="flex items-center justify-center text-[#52525B] hover:text-white transition-colors p-1.5 rounded-lg hover:bg-[#252525] cursor-pointer"
              title="Close"
            >
              <X size={16} />
            </button>
          </div>
        </div>
        {/* Modal chart body — explicit height so ResponsiveContainer works */}
        <div
          ref={expandedRef}
          className="px-4 py-4"
          style={{ height: '68vh' }}
        >
          <InsightChart chart={chart} />
        </div>
      </motion.div>
    </div>
  )
}

// ─── ChartCard ─────────────────────────────────────────────────────────────

interface ChartCardProps {
  chart: ChartSpec
  className?: string
  /** Pass true inside contexts where an extra expand button would be redundant */
  hideExpand?: boolean
}

export default function ChartCard({ chart, className = '', hideExpand = false }: ChartCardProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [isExpanded, setIsExpanded] = useState(false)

  const safeFilename = (chart.title || 'chart')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .slice(0, 50)

  return (
    <>
      <div
        className={`bg-[#141414] rounded-2xl border border-[#2A2A2A] overflow-hidden ${className}`}
      >
        {/* Card header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#222222]">
          <h3 className="text-xs font-semibold text-[#71717A] uppercase tracking-wider truncate">
            {chart.title}
          </h3>
          <div className="flex items-center gap-1 flex-shrink-0 ml-3">
            <button
              onClick={() => downloadChartAsPng(containerRef, safeFilename)}
              className="flex items-center gap-1.5 text-[#52525B] hover:text-[#A1A1AA] transition-colors text-xs px-2 py-1 rounded-lg hover:bg-[#252525] flex-shrink-0 cursor-pointer"
              title="Download chart as PNG"
            >
              <Download size={12} />
              <span className="hidden sm:inline text-[11px]">PNG</span>
            </button>
            {!hideExpand && (
              <button
                onClick={() => setIsExpanded(true)}
                className="flex items-center justify-center text-[#52525B] hover:text-[#A1A1AA] transition-colors p-1 rounded-lg hover:bg-[#252525] cursor-pointer"
                title="Expand chart"
              >
                <Maximize2 size={12} />
              </button>
            )}
          </div>
        </div>

        {/* Chart body — fixed height */}
        <div ref={containerRef} style={{ height: 268 }} className="px-2 py-3">
          <InsightChart chart={chart} />
        </div>
      </div>

      {/* Expanded modal */}
      {isExpanded && (
        <ExpandedChartModal chart={chart} onClose={() => setIsExpanded(false)} />
      )}
    </>
  )
}
