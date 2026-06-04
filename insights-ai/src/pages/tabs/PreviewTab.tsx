import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Table2, Info, AlertTriangle, ArrowUpDown, ChevronLeft, ChevronRight } from 'lucide-react'
import { useSessionStore } from '@/stores/sessionStore'
import { getPreview } from '@/api/dashboard'

const PAGE_SIZE = 100

export default function PreviewTab() {
  const sessionId    = useSessionStore((s) => s.sessionId)
  const setActiveTab = useSessionStore((s) => s.setActiveTab)

  const [page, setPage] = useState(0)

  const offset = page * PAGE_SIZE

  const { data, isLoading, isError } = useQuery({
    queryKey: ['preview', sessionId, page],
    queryFn: () => getPreview(sessionId!, PAGE_SIZE, offset),
    enabled: !!sessionId,
    // Keep previous page data visible while fetching next page
    placeholderData: (prev) => prev,
  })

  const totalRows  = data?.total_rows_in_dataset ?? 0
  const totalPages = Math.max(1, Math.ceil(totalRows / PAGE_SIZE))
  const startRow   = offset + 1
  const endRow     = Math.min(offset + (data?.preview_rows_shown ?? 0), totalRows)

  function goToPage(p: number) {
    setPage(Math.max(0, Math.min(p, totalPages - 1)))
  }

  return (
    <div className="h-[calc(100vh-3.5rem)] overflow-auto p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Table2 size={16} className="text-purple-400" />
          <span className="text-white font-semibold">Data Preview</span>
        </div>
        {data && (
          <div className="flex items-center gap-1.5">
            <Info size={12} className="text-[#52525B]" />
            <span className="text-[#52525B] text-xs">
              {totalRows.toLocaleString()} total rows &middot; {data.columns.length} columns
            </span>
          </div>
        )}
      </div>

      {/* Loading skeleton */}
      {isLoading && !data && (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="bg-[#1A1A1A] animate-pulse rounded-xl h-10 w-full" />
          ))}
        </div>
      )}

      {/* Error */}
      {isError && (
        <div className="flex flex-col items-center justify-center h-64 gap-3">
          <AlertTriangle size={32} className="text-red-400" />
          <p className="text-[#A1A1AA]">Failed to load preview</p>
        </div>
      )}

      {/* Table */}
      {data && (
        <>
          <div className={`overflow-x-auto rounded-2xl border border-[#2A2A2A] transition-opacity duration-150 ${isLoading ? 'opacity-60' : 'opacity-100'}`}>
            <table className="w-full border-collapse">
              <thead className="bg-[#1A1A1A] sticky top-0">
                <tr>
                  {/* Row number column */}
                  <th className="px-3 py-3 text-left text-xs font-medium text-[#3A3A3A] uppercase tracking-wider whitespace-nowrap border-b border-[#2A2A2A] w-12">
                    #
                  </th>
                  {data.columns.map((col) => (
                    <th
                      key={col}
                      onClick={() => setActiveTab('columns')}
                      className="px-4 py-3 text-left text-xs font-medium text-[#52525B] uppercase tracking-wider whitespace-nowrap border-b border-[#2A2A2A] cursor-pointer hover:text-[#A1A1AA] transition-colors"
                    >
                      <span className="flex items-center">
                        {col}
                        <ArrowUpDown size={11} className="ml-1 text-[#2A2A2A]" />
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row, rowIdx) => {
                  const absoluteRow = offset + rowIdx + 1
                  return (
                    <tr
                      key={rowIdx}
                      className={`${
                        rowIdx % 2 === 0 ? 'bg-[#0F0F0F]' : 'bg-[#111111]'
                      } hover:bg-[#1A1A1A] transition-colors`}
                    >
                      {/* Row number */}
                      <td className="px-3 py-2.5 text-xs text-[#3A3A3A] border-b border-[#2A2A2A]/50 tabular-nums">
                        {absoluteRow}
                      </td>
                      {data.columns.map((col) => {
                        const value = row[col]
                        const isNull = value === null || value === undefined || value === ''
                        return (
                          <td
                            key={col}
                            className="px-4 py-2.5 text-sm text-[#A1A1AA] whitespace-nowrap border-b border-[#2A2A2A]/50 max-w-[200px] truncate"
                            title={isNull ? undefined : String(value)}
                          >
                            {isNull ? (
                              <span className="text-[#52525B] italic">—</span>
                            ) : (
                              String(value)
                            )}
                          </td>
                        )
                      })}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* ── Pagination bar ─────────────────────────────────────────────── */}
          <div className="flex items-center justify-between mt-4 flex-wrap gap-3">
            {/* Row range info */}
            <p className="text-xs text-[#52525B]">
              Showing rows <span className="text-[#A1A1AA]">{startRow.toLocaleString()}–{endRow.toLocaleString()}</span>{' '}
              of <span className="text-[#A1A1AA]">{totalRows.toLocaleString()}</span>
            </p>

            {/* Page controls — only shown when more than one page */}
            {totalPages > 1 && (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => goToPage(page - 1)}
                  disabled={page === 0}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-[#2A2A2A] text-xs text-[#71717A] hover:text-white hover:border-[#3A3A3A] disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                >
                  <ChevronLeft size={13} /> Prev
                </button>

                {/* Page number pills — show up to 7 pages around current */}
                <div className="flex items-center gap-1">
                  {Array.from({ length: totalPages }, (_, i) => i)
                    .filter((i) => {
                      if (totalPages <= 7) return true
                      if (i === 0 || i === totalPages - 1) return true
                      return Math.abs(i - page) <= 2
                    })
                    .reduce<(number | 'ellipsis')[]>((acc, i, idx, arr) => {
                      if (idx > 0 && (i as number) - (arr[idx - 1] as number) > 1) {
                        acc.push('ellipsis')
                      }
                      acc.push(i)
                      return acc
                    }, [])
                    .map((item, idx) =>
                      item === 'ellipsis' ? (
                        <span key={`e-${idx}`} className="text-[#3A3A3A] text-xs px-1">…</span>
                      ) : (
                        <button
                          key={item}
                          onClick={() => goToPage(item as number)}
                          className={`w-7 h-7 rounded-lg text-xs transition-all ${
                            item === page
                              ? 'bg-purple-600 text-white font-semibold'
                              : 'border border-[#2A2A2A] text-[#71717A] hover:text-white hover:border-[#3A3A3A]'
                          }`}
                        >
                          {(item as number) + 1}
                        </button>
                      ),
                    )}
                </div>

                <button
                  onClick={() => goToPage(page + 1)}
                  disabled={page >= totalPages - 1}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-[#2A2A2A] text-xs text-[#71717A] hover:text-white hover:border-[#3A3A3A] disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                >
                  Next <ChevronRight size={13} />
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
