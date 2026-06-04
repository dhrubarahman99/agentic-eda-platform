import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Columns, Hash, Tag, Calendar, ToggleLeft, AlignLeft,
  CheckCircle2, AlertCircle, AlertTriangle, ShieldCheck,
} from 'lucide-react'
import { useSessionStore } from '@/stores/sessionStore'
import type { ColumnProfile, DType } from '@/api/types'
import ColumnDrawer from '@/components/dashboard/ColumnDrawer'

// ---------------------------------------------------------------------------
// Dtype badge helpers
// ---------------------------------------------------------------------------

interface DtypeBadgeConfig {
  bg: string
  border: string
  text: string
  icon: React.ReactNode
  label: string
  sectionColor: string
}

function getDtypeConfig(dtype: DType): DtypeBadgeConfig {
  switch (dtype) {
    case 'numeric':
      return { bg: 'bg-blue-900/30', border: 'border-blue-500/30', text: 'text-blue-400', icon: <Hash size={10} />, label: 'numeric', sectionColor: 'text-blue-400' }
    case 'categorical':
      return { bg: 'bg-green-900/30', border: 'border-green-500/30', text: 'text-green-400', icon: <Tag size={10} />, label: 'categorical', sectionColor: 'text-green-400' }
    case 'datetime':
      return { bg: 'bg-purple-900/30', border: 'border-purple-500/30', text: 'text-purple-400', icon: <Calendar size={10} />, label: 'datetime', sectionColor: 'text-purple-400' }
    case 'boolean':
      return { bg: 'bg-amber-900/30', border: 'border-amber-500/30', text: 'text-amber-400', icon: <ToggleLeft size={10} />, label: 'boolean', sectionColor: 'text-amber-400' }
    default:
      return { bg: 'bg-slate-800/30', border: 'border-slate-500/30', text: 'text-slate-400', icon: <AlignLeft size={10} />, label: dtype, sectionColor: 'text-slate-400' }
  }
}

// ---------------------------------------------------------------------------
// Quality badge
// ---------------------------------------------------------------------------

function getQualityBadge(col: ColumnProfile): { label: string; cls: string } {
  if (col.null_rate > 0.1)  return { label: 'Missing Data', cls: 'text-red-400 bg-red-900/20 border-red-500/20' }
  if (col.has_outliers)     return { label: 'Has Outliers', cls: 'text-amber-400 bg-amber-900/20 border-amber-500/20' }
  if (col.null_rate === 0)  return { label: 'Clean', cls: 'text-emerald-400 bg-emerald-900/20 border-emerald-500/20' }
  return { label: 'OK', cls: 'text-green-400 bg-green-900/20 border-green-500/20' }
}

// ---------------------------------------------------------------------------
// Individual column card
// ---------------------------------------------------------------------------

function ColumnCard({
  col,
  totalRows,
  onClick,
}: {
  col: ColumnProfile
  totalRows: number
  onClick: () => void
}) {
  const cfg = getDtypeConfig(col.dtype)
  const quality = getQualityBadge(col)
  const nullCount = col.null_count ?? 0

  return (
    <motion.div
      whileHover={{ scale: 1.01 }}
      onClick={onClick}
      className="bg-[#1A1A1A] border border-[#2A2A2A] rounded-2xl p-4 cursor-pointer hover:border-purple-500/40 transition-all"
    >
      {/* Header: name + type badge */}
      <div className="flex items-center justify-between mb-2 gap-2">
        <span className="text-white font-medium text-sm truncate flex-1">{col.name}</span>
        <span className={`text-[10px] rounded-full px-2 py-0.5 border flex items-center gap-1 flex-shrink-0 ${cfg.bg} ${cfg.border} ${cfg.text}`}>
          {cfg.icon}
          {cfg.label}
        </span>
      </div>

      {/* Quality + cardinality row */}
      <div className="flex items-center gap-2 mb-2.5 flex-wrap">
        <span className={`text-[10px] rounded-full px-2 py-0.5 border ${quality.cls}`}>
          {quality.label}
        </span>
        {col.cardinality > 0 && (
          <span className="text-[10px] text-[#52525B]">
            {col.cardinality.toLocaleString()} unique
          </span>
        )}
      </div>

      {/* Missing values bar — shows count/total instead of percentage */}
      <div className="mb-3">
        {nullCount === 0 ? (
          <div className="flex items-center gap-1 text-emerald-400 text-[10px]">
            <CheckCircle2 size={10} />
            No missing values
          </div>
        ) : (
          <>
            <div className="flex items-center text-[10px] text-[#52525B] mb-1 gap-1">
              <AlertCircle size={10} />
              {nullCount.toLocaleString()} / {totalRows.toLocaleString()} missing
            </div>
            <div className="bg-[#242424] rounded-full h-1 overflow-hidden">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${Math.min(col.null_rate * 100, 100)}%`,
                  background: col.null_rate > 0.1 ? '#EF4444' : '#F59E0B',
                }}
              />
            </div>
          </>
        )}
      </div>

      {/* Sample values */}
      {(col.sample_values ?? []).length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {(col.sample_values ?? []).slice(0, 3).map((v, i) => (
            <span
              key={i}
              className="bg-[#242424] rounded px-1.5 py-0.5 text-[10px] text-[#71717A] truncate max-w-[72px]"
            >
              {String(v)}
            </span>
          ))}
        </div>
      )}

      {/* Outlier indicator */}
      {col.has_outliers && (
        <div className="flex items-center gap-1 text-amber-400 text-[10px] mt-1">
          <AlertTriangle size={10} />
          {col.outlier_count ?? 0} outlier{(col.outlier_count ?? 0) !== 1 ? 's' : ''} detected
        </div>
      )}
    </motion.div>
  )
}

// ---------------------------------------------------------------------------
// Section group
// ---------------------------------------------------------------------------

interface SectionProps {
  dtype: DType
  columns: ColumnProfile[]
  icon: React.ReactNode
  title: string
  totalRows: number
  onSelect: (name: string) => void
}

function ColumnSection({ dtype, columns, icon, title, totalRows, onSelect }: SectionProps) {
  const cfg = getDtypeConfig(dtype)
  if (columns.length === 0) return null

  return (
    <div className="mb-8">
      <div className="flex items-center gap-2 mb-3">
        <span className={cfg.sectionColor}>{icon}</span>
        <h2 className={`text-sm font-semibold ${cfg.sectionColor}`}>{title}</h2>
        <span className="text-xs text-[#52525B] bg-[#1A1A1A] border border-[#2A2A2A] rounded-full px-2 py-0.5">
          {columns.length}
        </span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {columns.map((col) => (
          <ColumnCard
            key={col.name}
            col={col}
            totalRows={totalRows}
            onClick={() => onSelect(col.name)}
          />
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// ColumnsTab
// ---------------------------------------------------------------------------

export default function ColumnsTab() {
  const profile = useSessionStore((s) => s.profile)
  const [selectedColumn, setSelectedColumn] = useState<string | null>(null)

  if (!profile) return null

  const totalRows = profile.shape['rows'] ?? 0

  const numeric = profile.columns.filter((c) => c.dtype === 'numeric')

  // Boolean (binary 0/1) columns are grouped with categoricals so users see
  // "No / Yes" distributions alongside other discrete columns.
  const categorical = profile.columns.filter(
    (c) => c.dtype === 'categorical' || c.dtype === 'boolean',
  )
  const datetime = profile.columns.filter((c) => c.dtype === 'datetime')
  const others   = profile.columns.filter(
    (c) => !['numeric', 'categorical', 'boolean', 'datetime'].includes(c.dtype),
  )

  return (
    <div className="h-[calc(100vh-3.5rem)] overflow-auto p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Columns size={16} className="text-purple-400" />
          <span className="text-white font-semibold">Column Explorer</span>
        </div>
        <span className="bg-[#1A1A1A] border border-[#2A2A2A] rounded-full px-3 py-1 text-xs text-[#A1A1AA]">
          {profile.columns.length} columns
        </span>
      </div>

      {/* Grouped sections */}
      <ColumnSection
        dtype="numeric"
        columns={numeric}
        icon={<Hash size={14} />}
        title="Numeric Columns"
        totalRows={totalRows}
        onSelect={setSelectedColumn}
      />
      <ColumnSection
        dtype="categorical"
        columns={categorical}
        icon={<Tag size={14} />}
        title="Categorical Columns"
        totalRows={totalRows}
        onSelect={setSelectedColumn}
      />
      <ColumnSection
        dtype="datetime"
        columns={datetime}
        icon={<Calendar size={14} />}
        title="Date / Time Columns"
        totalRows={totalRows}
        onSelect={setSelectedColumn}
      />
      {others.length > 0 && (
        <ColumnSection
          dtype="boolean"
          columns={others}
          icon={<ShieldCheck size={14} />}
          title="Other Columns"
          totalRows={totalRows}
          onSelect={setSelectedColumn}
        />
      )}

      {/* Column detail drawer */}
      <AnimatePresence>
        <ColumnDrawer
          columnName={selectedColumn}
          onClose={() => setSelectedColumn(null)}
        />
      </AnimatePresence>
    </div>
  )
}
