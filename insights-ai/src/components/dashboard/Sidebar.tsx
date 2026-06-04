import { FileSpreadsheet, History, Inbox, Plus, Trash2, Loader2, ShieldAlert } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useState, useMemo } from 'react'
import { useSessionStore } from '@/stores/sessionStore'
import { useChatStore } from '@/stores/chatStore'
import { useToastStore } from '@/stores/toastStore'
import { listSessions, deleteSession } from '@/api/sessions'
import { getDashboard } from '@/api/dashboard'
import { logout, getStoredUser } from '@/api/auth'

export default function Sidebar() {
  const navigate          = useNavigate()
  const queryClient       = useQueryClient()

  const sessionId         = useSessionStore((s) => s.sessionId)
  const userName          = useSessionStore((s) => s.userName)
  const switchSession     = useSessionStore((s) => s.switchSession)
  const resetSession      = useSessionStore((s) => s.resetSession)
  const isMenuOpen        = useSessionStore((s) => s.isMenuOpen)
  const setMenuOpen       = useSessionStore((s) => s.setMenuOpen)

  const clearAllSessions  = useChatStore((s) => s.clearAllSessions)
  const clearChatSession  = useChatStore((s) => s.clearSession)
  const addToast          = useToastStore((s) => s.addToast)

  const [loadingSid, setLoadingSid]   = useState<string | null>(null)
  const [deletingSid, setDeletingSid] = useState<string | null>(null)

  const currentUser = getStoredUser()

  const { data: rawSessions, isLoading } = useQuery({
    queryKey: ['sessions'],
    queryFn: listSessions,
    staleTime: 30_000,          // keep data fresh for 30s to avoid stale flash
    refetchInterval: false,
    refetchOnWindowFocus: false,  // don't refetch just because user switched tabs
  })

  // Guard: ensure each session_id appears at most once (backend already
  // guarantees uniqueness, but this protects against any future race condition
  // or React Query cache edge case that could produce duplicate entries).
  const sessions = useMemo(() => {
    if (!rawSessions) return rawSessions
    const seen = new Set<string>()
    return rawSessions.filter((s) => {
      if (seen.has(s.session_id)) return false
      seen.add(s.session_id)
      return true
    })
  }, [rawSessions])

  async function handleSessionClick(sid: string, filename: string) {
    if (sid === sessionId || loadingSid) return
    setLoadingSid(sid)
    try {
      const dash = await getDashboard(sid)
      // switchSession synthesises a DatasetProfile from dashboardData so that
      // components guarding on profile !== null (InsightsTab, ColumnsTab) always
      // receive valid data and never render a black/empty screen.
      switchSession(sid, filename, dash)
      setMenuOpen(false)
    } catch {
      // Session data is gone (server restarted) — remove stale entry from list
      addToast('error', `Session for "${filename}" is no longer available.`)
      queryClient.invalidateQueries({ queryKey: ['sessions'] })
    } finally {
      setLoadingSid(null)
    }
  }

  async function handleDelete(e: React.MouseEvent, sid: string) {
    e.stopPropagation()
    if (deletingSid) return
    setDeletingSid(sid)
    try {
      await deleteSession(sid)
      clearChatSession(sid)
      // If we deleted the active session, return to welcome screen
      if (sid === sessionId) resetSession()
      queryClient.invalidateQueries({ queryKey: ['sessions'] })
    } catch {
      // ignore
    } finally {
      setDeletingSid(null)
    }
  }

  function handleNewAnalysis() {
    resetSession()
    setMenuOpen(false)
  }

  async function handleLogout() {
    await logout()
    clearAllSessions()
    resetSession()
    navigate('/login')
  }

  const initial = (userName[0] ?? 'U').toUpperCase()

  return (
    <>
      {/* Backdrop overlay — mobile only */}
      {isMenuOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/60 lg:hidden"
          onClick={() => setMenuOpen(false)}
        />
      )}

      <aside
        className={`
          fixed left-0 top-14 bottom-0 z-30
          bg-[#0F0F0F] border-r border-[#2A2A2A]
          flex flex-col
          transition-transform duration-300 ease-in-out
          w-60
          lg:translate-x-0 lg:w-14
          xl:w-60
          ${isMenuOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        {/* ── New Analysis ─────────────────────────────────────────────── */}
        <div className="p-4 lg:p-2 xl:p-4 border-b border-[#2A2A2A]">
          <button
            onClick={handleNewAnalysis}
            title="New Analysis"
            className="w-full bg-purple-600 hover:bg-purple-700 text-white py-2 text-sm font-medium flex items-center justify-center gap-2 transition-colors duration-150 rounded-xl lg:rounded-full xl:rounded-xl"
          >
            <Plus size={16} />
            <span className="block lg:hidden xl:inline">New Analysis</span>
          </button>
        </div>

        {/* ── Session list ─────────────────────────────────────────────── */}
        <div className="flex-1 overflow-y-auto p-4 lg:p-2 xl:p-4">
          <div className="flex items-center gap-1.5 text-[#52525B] text-xs font-medium uppercase tracking-wider mb-3 lg:hidden xl:flex">
            <History size={12} />
            Previous Sessions
          </div>

          {isLoading && (
            <div className="space-y-2">
              {[0, 1, 2].map((i) => (
                <div key={i} className="bg-[#1A1A1A] animate-pulse rounded-xl h-10" />
              ))}
            </div>
          )}

          {!isLoading && (!sessions || sessions.length === 0) && (
            <div className="flex flex-col items-center justify-center gap-2 mt-8">
              <Inbox size={20} className="text-[#2A2A2A]" />
              <span className="text-[#52525B] text-xs block lg:hidden xl:block">
                No previous sessions
              </span>
            </div>
          )}

          {!isLoading && sessions && sessions.map((session) => {
            const isActive   = session.session_id === sessionId
            const isLoading_ = loadingSid === session.session_id
            const isDeleting = deletingSid === session.session_id

            return (
              <div
                key={session.session_id}
                className={`group w-full flex items-center gap-2 p-2 rounded-xl cursor-pointer hover:bg-[#1A1A1A] transition-colors mb-1
                  lg:justify-center lg:gap-0
                  xl:justify-start xl:gap-2
                  ${isActive ? 'bg-[#1A1A1A] border border-purple-500/30' : 'border border-transparent'}
                  ${isLoading_ ? 'opacity-60 cursor-wait' : ''}
                `}
                onClick={() => handleSessionClick(session.session_id, session.filename)}
                title={session.filename}
              >
                {/* Icon / spinner */}
                {isLoading_ ? (
                  <Loader2 size={16} className="text-purple-400 flex-shrink-0 animate-spin" />
                ) : (
                  <FileSpreadsheet size={16} className={`flex-shrink-0 ${isActive ? 'text-purple-400' : 'text-[#52525B]'}`} />
                )}

                {/* Name + rows */}
                <div className="flex-1 min-w-0 lg:hidden xl:block overflow-hidden">
                  <p className="text-sm text-[#A1A1AA] truncate leading-tight">{session.filename}</p>
                  <p className="text-xs text-[#52525B] leading-tight">{session.row_count.toLocaleString()} rows</p>
                </div>

                {/* Status dot */}
                <div
                  className={`w-2 h-2 rounded-full flex-shrink-0 block lg:hidden xl:block ${
                    session.has_analysis ? 'bg-emerald-400' : 'bg-[#2A2A2A]'
                  }`}
                />

                {/* Delete button — shows on hover (xl only) */}
                <button
                  onClick={(e) => handleDelete(e, session.session_id)}
                  disabled={!!deletingSid}
                  title="Delete session"
                  className="hidden xl:flex opacity-0 group-hover:opacity-100 transition-opacity items-center justify-center w-5 h-5 rounded text-[#52525B] hover:text-red-400 hover:bg-red-400/10 flex-shrink-0 disabled:cursor-not-allowed"
                >
                  {isDeleting ? (
                    <Loader2 size={12} className="animate-spin" />
                  ) : (
                    <Trash2 size={12} />
                  )}
                </button>
              </div>
            )
          })}
        </div>

        {/* ── User section ─────────────────────────────────────────────── */}
        <div className="p-4 lg:p-2 xl:p-4 border-t border-[#2A2A2A] flex items-center gap-3 lg:justify-center xl:justify-start">
          <div
            className="w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-bold flex-shrink-0 cursor-pointer hover:ring-2 hover:ring-purple-500/60 transition-all"
            title="Account settings"
            onClick={() => navigate('/account')}
            style={{ background: 'linear-gradient(to bottom right, #7c3aed, #ec4899)' }}
          >
            {initial}
          </div>
          <div className="flex flex-col flex-1 min-w-0 lg:hidden xl:flex overflow-hidden">
            <span
              className="text-sm text-white font-medium truncate block cursor-pointer hover:text-purple-300 transition-colors"
              onClick={() => navigate('/account')}
              title="Account settings"
            >
              {userName}
            </span>
            <div className="flex items-center gap-2 mt-0.5">
              <button
                onClick={handleLogout}
                className="text-xs text-[#52525B] hover:text-red-400 transition-colors text-left"
              >
                Sign out
              </button>
              {currentUser?.is_admin && (
                <>
                  <span className="text-[#2A2A2A]">·</span>
                  <button
                    onClick={() => navigate('/admin')}
                    className="flex items-center gap-1 text-xs text-purple-500 hover:text-purple-400 transition-colors"
                  >
                    <ShieldAlert size={10} />
                    Admin
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </aside>
    </>
  )
}
