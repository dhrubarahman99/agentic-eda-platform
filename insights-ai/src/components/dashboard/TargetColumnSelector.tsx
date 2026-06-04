/**
 * TargetColumnSelector.tsx
 *
 * Full-screen interstitial shown after CSV upload and before analysis begins.
 * Lets the user explicitly choose the target column (the outcome they care about).
 * They can also skip to use the auto-detected column.
 */

import { useState, useMemo } from 'react'
import { motion } from 'framer-motion'
import {
  Sparkles,
  Target,
  Hash,
  Tag,
  Calendar,
  ToggleLeft,
  AlignLeft,
  Search,
  ArrowRight,
  SkipForward,
  FileSpreadsheet,
  Lightbulb,
} from 'lucide-react'
import type { ColumnProfile, DType, UploadResponse } from '@/api/types'

// ---------------------------------------------------------------------------
// TopBar
// ---------------------------------------------------------------------------

function TopBar() {
  return (
    <header className="h-14 flex items-center px-6 border-b border-[#2A2A2A] bg-[#0A0A0A]/95 backdrop-blur-md flex-shrink-0">
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
    </header>
  )
}

// ---------------------------------------------------------------------------
// Dtype helpers
// ---------------------------------------------------------------------------

interface DTypeStyle {
  bg: string
  border: string
  text: string
  icon: React.ReactNode
  label: string
}

function getDTypeStyle(dtype: DType): DTypeStyle {
  switch (dtype) {
    case 'numeric':
      return {
        bg: 'bg-blue-900/25', border: 'border-blue-500/30',
        text: 'text-blue-400', icon: <Hash size={10} />, label: 'numeric',
      }
    case 'categorical':
      return {
        bg: 'bg-green-900/25', border: 'border-green-500/30',
        text: 'text-green-400', icon: <Tag size={10} />, label: 'categorical',
      }
    case 'datetime':
      return {
        bg: 'bg-purple-900/25', border: 'border-purple-500/30',
        text: 'text-purple-400', icon: <Calendar size={10} />, label: 'datetime',
      }
    case 'boolean':
      return {
        bg: 'bg-amber-900/25', border: 'border-amber-500/30',
        text: 'text-amber-400', icon: <ToggleLeft size={10} />, label: 'boolean',
      }
    default:
      return {
        bg: 'bg-slate-800/25', border: 'border-slate-500/30',
        text: 'text-slate-400', icon: <AlignLeft size={10} />, label: dtype,
      }
  }
}

// ---------------------------------------------------------------------------
// ColumnRow — single selectable row in the list
// ---------------------------------------------------------------------------

interface ColumnRowProps {
  col: ColumnProfile
  isSelected: boolean
  isAutoDetected: boolean
  onClick: () => void
}

function ColumnRow({ col, isSelected, isAutoDetected, onClick }: ColumnRowProps) {
  const style = getDTypeStyle(col.dtype)

  return (
    <button
      onClick={onClick}
      className={`
        w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left
        transition-all duration-150 group
        ${isSelected
          ? 'bg-purple-900/30 border border-purple-500/50 ring-1 ring-purple-500/30'
          : 'border border-transparent hover:bg-[#1A1A1A] hover:border-[#2A2A2A]'
        }
      `}
    >
      {/* Radio indicator */}
      <div
        className={`
          w-4 h-4 rounded-full border-2 flex items-center justify-center flex-shrink-0 transition-all
          ${isSelected ? 'border-purple-500 bg-purple-500' : 'border-[#3A3A3A] group-hover:border-[#555]'}
        `}
      >
        {isSelected && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
      </div>

      {/* Column name */}
      <span className={`flex-1 text-sm font-medium truncate ${isSelected ? 'text-white' : 'text-[#A1A1AA]'}`}>
        {col.name}
      </span>

      {/* Auto-detected badge */}
      {isAutoDetected && (
        <span className="text-[10px] bg-amber-900/30 border border-amber-500/30 text-amber-400 rounded-full px-2 py-0.5 flex-shrink-0">
          auto
        </span>
      )}

      {/* Dtype badge */}
      <span className={`text-[10px] rounded-full px-2 py-0.5 border flex items-center gap-1 flex-shrink-0 ${style.bg} ${style.border} ${style.text}`}>
        {style.icon}
        {style.label}
      </span>
    </button>
  )
}

// ---------------------------------------------------------------------------
// TargetColumnSelector
// ---------------------------------------------------------------------------

interface TargetColumnSelectorProps {
  uploadData: UploadResponse
  onConfirm: (targetColumn: string | null) => void
}

export default function TargetColumnSelector({
  uploadData,
  onConfirm,
}: TargetColumnSelectorProps) {
  const profile = uploadData.profile
  const autoDetected = profile.potential_target ?? null

  const [selected, setSelected] = useState<string | null>(autoDetected)
  const [search, setSearch] = useState('')

  // Only numeric + categorical columns are useful as targets
  // (datetime and boolean are rarely prediction targets)
  const allColumns = profile.columns
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return allColumns
    return allColumns.filter((c) => c.name.toLowerCase().includes(q))
  }, [allColumns, search])

  const hasSelection = selected !== null

  function handleSkip() {
    // Pass null → analysis endpoint uses profiler's auto-detected target (or none)
    onConfirm(null)
  }

  function handleConfirm() {
    onConfirm(selected)
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#0A0A0A]">
      <TopBar />

      <div className="flex-1 flex items-center justify-center px-4 py-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
          className="w-full max-w-lg"
        >
          {/* Card */}
          <div className="bg-[#141414] rounded-2xl border border-[#242424] shadow-2xl overflow-hidden">

            {/* ── Header ─────────────────────────────────────────────────── */}
            <div className="px-6 pt-6 pb-5 border-b border-[#1F1F1F]">
              {/* Filename chip */}
              <div className="inline-flex items-center gap-1.5 bg-purple-900/30 border border-purple-500/30 rounded-full px-3 py-1 mb-4">
                <FileSpreadsheet size={11} className="text-purple-300 flex-shrink-0" />
                <span className="text-purple-300 text-xs truncate max-w-[300px]">{uploadData.filename}</span>
              </div>

              <div className="flex items-start gap-3">
                <div
                  className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 mt-0.5"
                  style={{ background: 'linear-gradient(135deg, #7c3aed 0%, #3b82f6 100%)' }}
                >
                  <Target size={16} className="text-white" />
                </div>
                <div>
                  <h2 className="text-white text-lg font-semibold leading-tight">
                    Choose your target column
                  </h2>
                  <p className="text-[#71717A] text-sm mt-1 leading-relaxed">
                    {profile.shape['cols']} columns · {profile.shape['rows']?.toLocaleString()} rows
                  </p>
                </div>
              </div>

              {/* Explanation box */}
              <div className="mt-4 bg-[#0F0F0F] border border-[#2A2A2A] rounded-xl p-3.5 flex gap-2.5">
                <Lightbulb size={15} className="text-amber-400 flex-shrink-0 mt-0.5" />
                <p className="text-[#A1A1AA] text-xs leading-relaxed">
                  The <span className="text-white font-medium">target column</span> is the main outcome you want to understand — like <span className="text-purple-300">Sales</span>, <span className="text-purple-300">Churn</span>, or <span className="text-purple-300">Price</span>. Choosing one lets the system run smarter ML analysis to find what drives it and surface more focused insights.
                </p>
              </div>
            </div>

            {/* ── Column list ────────────────────────────────────────────── */}
            <div className="px-6 py-4">
              {/* Auto-detected suggestion */}
              {autoDetected && (
                <div className="mb-3 flex items-center gap-2 text-xs text-amber-400/80">
                  <Sparkles size={11} />
                  <span>Auto-detected: <strong className="text-amber-300">{autoDetected}</strong> — pre-selected below</span>
                </div>
              )}

              {/* Search */}
              {allColumns.length > 8 && (
                <div className="relative mb-3">
                  <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#52525B]" />
                  <input
                    type="text"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search columns…"
                    className="w-full bg-[#0F0F0F] border border-[#2A2A2A] rounded-xl pl-8 pr-3 py-2 text-sm text-[#A1A1AA] placeholder-[#3A3A3A] focus:outline-none focus:border-purple-500/50 transition-colors"
                  />
                </div>
              )}

              {/* Scrollable column list */}
              <div
                className="space-y-0.5 overflow-y-auto pr-1"
                style={{ maxHeight: '280px' }}
              >
                {filtered.length === 0 ? (
                  <p className="text-[#52525B] text-xs text-center py-6">No columns match your search.</p>
                ) : (
                  filtered.map((col) => (
                    <ColumnRow
                      key={col.name}
                      col={col}
                      isSelected={selected === col.name}
                      isAutoDetected={col.name === autoDetected}
                      onClick={() => setSelected(col.name === selected ? null : col.name)}
                    />
                  ))
                )}
              </div>

              {/* Selection feedback */}
              <div className="mt-3 h-5">
                {selected && (
                  <motion.p
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="text-xs text-purple-400"
                  >
                    Selected: <strong className="text-purple-300">{selected}</strong>
                  </motion.p>
                )}
              </div>
            </div>

            {/* ── Footer buttons ──────────────────────────────────────────── */}
            <div className="px-6 pb-6 flex gap-3">
              {/* Skip */}
              <button
                onClick={handleSkip}
                className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl border border-[#2A2A2A] text-sm text-[#71717A] hover:text-[#A1A1AA] hover:border-[#3A3A3A] transition-all duration-150"
              >
                <SkipForward size={14} />
                Skip
              </button>

              {/* Start Analysis */}
              <button
                onClick={handleConfirm}
                className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-semibold text-white transition-all duration-150"
                style={{
                  background: hasSelection
                    ? 'linear-gradient(135deg, #7c3aed, #3b82f6)'
                    : 'linear-gradient(135deg, #4B5563, #374151)',
                  boxShadow: hasSelection ? '0 0 20px rgba(124,58,237,0.3)' : 'none',
                }}
              >
                {hasSelection ? (
                  <>Start Analysis <ArrowRight size={15} /></>
                ) : (
                  <>Skip &amp; Auto-detect <ArrowRight size={15} /></>
                )}
              </button>
            </div>
          </div>

          {/* Subtle hint below card */}
          <p className="text-center text-[#3A3A3A] text-xs mt-4">
            You can always explore all columns from the Column Explorer tab after analysis.
          </p>
        </motion.div>
      </div>
    </div>
  )
}
