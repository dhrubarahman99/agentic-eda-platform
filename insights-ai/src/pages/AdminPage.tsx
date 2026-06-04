/**
 * AdminPage.tsx
 * Admin dashboard — system overview, user management, session management,
 * and feedback log with per-user clear functionality.
 *
 * Access: admin users only (is_admin=true in stored session).
 * All API calls require the Bearer token and fail with 403 for non-admins.
 */

import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Sparkles, LogOut, Users, Database, MessageSquare,
  BarChart3, Trash2, ShieldAlert, ThumbsUp, ThumbsDown,
  RefreshCw, ChevronDown, ChevronUp, AlertTriangle,
} from 'lucide-react'
import { getStoredUser, logout } from '@/api/auth'
import {
  fetchAdminStats,
  fetchAdminUsers,
  deleteAdminUser,
  fetchAdminSessions,
  deleteAdminSession,
  fetchAdminFeedback,
  clearUserFeedback,
} from '@/api/admin'
import type { AdminStats, AdminUser, AdminSession, AdminFeedbackGroup } from '@/api/types'

// ---------------------------------------------------------------------------
// Tab type
// ---------------------------------------------------------------------------

type Tab = 'overview' | 'users' | 'sessions' | 'feedback'

// ---------------------------------------------------------------------------
// Small shared components
// ---------------------------------------------------------------------------

function StatCard({
  icon,
  label,
  value,
  color,
}: {
  icon: React.ReactNode
  label: string
  value: number | string
  color: string
}) {
  return (
    <div
      className="rounded-xl p-5 flex items-center gap-4"
      style={{ background: '#111111', border: '1px solid #2A2A2A' }}
    >
      <div
        className="w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0"
        style={{ background: color + '22' }}
      >
        <span style={{ color }}>{icon}</span>
      </div>
      <div>
        <p className="text-2xl font-bold text-white leading-none">{value}</p>
        <p className="text-[12px] text-[#71717a] mt-1">{label}</p>
      </div>
    </div>
  )
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className="px-4 py-2 rounded-lg text-sm font-medium transition-all"
      style={
        active
          ? {
              background: 'rgba(124,58,237,0.18)',
              color: '#a78bfa',
              border: '1px solid rgba(124,58,237,0.35)',
            }
          : {
              background: 'transparent',
              color: '#71717a',
              border: '1px solid transparent',
            }
      }
    >
      {children}
    </button>
  )
}

function ConfirmButton({
  label,
  confirmLabel,
  onConfirm,
  disabled,
  variant = 'danger',
}: {
  label: string
  confirmLabel: string
  onConfirm: () => Promise<void>
  disabled?: boolean
  variant?: 'danger' | 'warning'
}) {
  const [step, setStep] = useState<'idle' | 'confirm' | 'loading'>('idle')

  async function handleConfirm() {
    setStep('loading')
    try {
      await onConfirm()
    } finally {
      setStep('idle')
    }
  }

  const color = variant === 'danger' ? '#ef4444' : '#f59e0b'

  if (step === 'confirm') {
    return (
      <div className="flex items-center gap-1.5">
        <button
          onClick={handleConfirm}
          className="px-2.5 py-1 rounded-lg text-xs font-semibold text-white transition-all"
          style={{ background: color + 'cc' }}
        >
          {confirmLabel}
        </button>
        <button
          onClick={() => setStep('idle')}
          className="px-2.5 py-1 rounded-lg text-xs text-[#71717a] hover:text-white transition-colors"
          style={{ background: '#1A1A1A' }}
        >
          Cancel
        </button>
      </div>
    )
  }

  return (
    <button
      onClick={() => !disabled && setStep('confirm')}
      disabled={disabled || step === 'loading'}
      className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all disabled:opacity-30 disabled:cursor-not-allowed"
      style={{
        background: '#1A1A1A',
        color: disabled ? '#52525b' : color,
        border: `1px solid ${disabled ? '#2A2A2A' : color + '44'}`,
      }}
    >
      {step === 'loading' ? (
        <RefreshCw size={11} className="animate-spin" />
      ) : (
        <Trash2 size={11} />
      )}
      {step === 'loading' ? 'Deleting…' : label}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Tab panels
// ---------------------------------------------------------------------------

function OverviewTab({ stats }: { stats: AdminStats | null }) {
  if (!stats) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 animate-pulse">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-20 rounded-xl" style={{ background: '#111111' }} />
        ))}
      </div>
    )
  }
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <StatCard icon={<Users size={20} />}         label="Total users"    value={stats.total_users}    color="#a78bfa" />
      <StatCard icon={<Database size={20} />}       label="Total sessions" value={stats.total_sessions} color="#60a5fa" />
      <StatCard icon={<MessageSquare size={20} />}  label="Feedback items" value={stats.total_feedback} color="#34d399" />
      <StatCard icon={<BarChart3 size={20} />}      label="Total queries"  value={stats.total_queries}  color="#fb923c" />
    </div>
  )
}

function UsersTab({
  users,
  onDelete,
}: {
  users: AdminUser[] | null
  onDelete: (id: number) => Promise<void>
}) {
  if (!users) {
    return <div className="text-[#52525b] text-sm py-8 text-center">Loading…</div>
  }
  if (users.length === 0) {
    return <div className="text-[#52525b] text-sm py-8 text-center">No users found.</div>
  }
  return (
    <div className="rounded-xl overflow-hidden" style={{ border: '1px solid #2A2A2A' }}>
      <table className="w-full text-sm">
        <thead>
          <tr style={{ background: '#111111', borderBottom: '1px solid #2A2A2A' }}>
            <th className="px-4 py-3 text-left text-[11px] text-[#52525b] uppercase tracking-wider font-semibold">User</th>
            <th className="px-4 py-3 text-left text-[11px] text-[#52525b] uppercase tracking-wider font-semibold">Role</th>
            <th className="px-4 py-3 text-left text-[11px] text-[#52525b] uppercase tracking-wider font-semibold">Sessions</th>
            <th className="px-4 py-3 text-left text-[11px] text-[#52525b] uppercase tracking-wider font-semibold">Queries</th>
            <th className="px-4 py-3 text-left text-[11px] text-[#52525b] uppercase tracking-wider font-semibold">Joined</th>
            <th className="px-4 py-3 text-right text-[11px] text-[#52525b] uppercase tracking-wider font-semibold"></th>
          </tr>
        </thead>
        <tbody>
          {users.map((u, i) => (
            <tr
              key={u.id}
              style={{
                background: i % 2 === 0 ? '#0A0A0A' : '#0D0D0D',
                borderBottom: '1px solid #1A1A1A',
              }}
            >
              <td className="px-4 py-3">
                <p className="text-white font-medium">{u.name}</p>
                <p className="text-[#52525b] text-xs">{u.email}</p>
              </td>
              <td className="px-4 py-3">
                {u.is_admin ? (
                  <span
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold"
                    style={{ background: 'rgba(124,58,237,0.18)', color: '#a78bfa' }}
                  >
                    <ShieldAlert size={10} /> Admin
                  </span>
                ) : (
                  <span className="text-[#52525b] text-xs">User</span>
                )}
              </td>
              <td className="px-4 py-3 text-[#a1a1aa]">{u.session_count}</td>
              <td className="px-4 py-3 text-[#a1a1aa]">{u.query_count}</td>
              <td className="px-4 py-3 text-[#52525b] text-xs">
                {u.created_at ? u.created_at.slice(0, 10) : '—'}
              </td>
              <td className="px-4 py-3 text-right">
                <ConfirmButton
                  label="Delete"
                  confirmLabel="Yes, delete"
                  disabled={u.is_admin}
                  onConfirm={() => onDelete(u.id)}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function SessionsTab({
  sessions,
  onDelete,
}: {
  sessions: AdminSession[] | null
  onDelete: (id: string) => Promise<void>
}) {
  if (!sessions) {
    return <div className="text-[#52525b] text-sm py-8 text-center">Loading…</div>
  }
  if (sessions.length === 0) {
    return <div className="text-[#52525b] text-sm py-8 text-center">No sessions found.</div>
  }
  return (
    <div className="rounded-xl overflow-hidden" style={{ border: '1px solid #2A2A2A' }}>
      <table className="w-full text-sm">
        <thead>
          <tr style={{ background: '#111111', borderBottom: '1px solid #2A2A2A' }}>
            <th className="px-4 py-3 text-left text-[11px] text-[#52525b] uppercase tracking-wider font-semibold">File</th>
            <th className="px-4 py-3 text-left text-[11px] text-[#52525b] uppercase tracking-wider font-semibold">Owner</th>
            <th className="px-4 py-3 text-left text-[11px] text-[#52525b] uppercase tracking-wider font-semibold">Size</th>
            <th className="px-4 py-3 text-left text-[11px] text-[#52525b] uppercase tracking-wider font-semibold">Analysis</th>
            <th className="px-4 py-3 text-left text-[11px] text-[#52525b] uppercase tracking-wider font-semibold">Created</th>
            <th className="px-4 py-3 text-right text-[11px] text-[#52525b] uppercase tracking-wider font-semibold"></th>
          </tr>
        </thead>
        <tbody>
          {sessions.map((s, i) => (
            <tr
              key={s.session_id}
              style={{
                background: i % 2 === 0 ? '#0A0A0A' : '#0D0D0D',
                borderBottom: '1px solid #1A1A1A',
              }}
            >
              <td className="px-4 py-3">
                <p className="text-white font-medium max-w-[180px] truncate">{s.filename}</p>
                <p className="text-[#52525b] text-[11px] font-mono">{s.session_id.slice(0, 12)}…</p>
              </td>
              <td className="px-4 py-3 text-[#a1a1aa] text-xs">{s.user_email ?? '—'}</td>
              <td className="px-4 py-3 text-[#a1a1aa] text-xs">
                {s.row_count.toLocaleString()} × {s.col_count}
              </td>
              <td className="px-4 py-3">
                {s.has_analysis ? (
                  <span className="text-[#34d399] text-xs">{s.total_insights} insights</span>
                ) : (
                  <span className="text-[#52525b] text-xs">None</span>
                )}
              </td>
              <td className="px-4 py-3 text-[#52525b] text-xs">
                {s.created_at ? s.created_at.slice(0, 10) : '—'}
              </td>
              <td className="px-4 py-3 text-right">
                <ConfirmButton
                  label="Delete"
                  confirmLabel="Yes, delete"
                  onConfirm={() => onDelete(s.session_id)}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function FeedbackTab({
  groups,
  onClear,
}: {
  groups: AdminFeedbackGroup[] | null
  onClear: (userId: number) => Promise<void>
}) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  function toggle(key: string) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  if (!groups) {
    return <div className="text-[#52525b] text-sm py-8 text-center">Loading…</div>
  }
  if (groups.length === 0) {
    return <div className="text-[#52525b] text-sm py-8 text-center">No feedback recorded yet.</div>
  }

  return (
    <div className="flex flex-col gap-3">
      {groups.map((g) => {
        const key        = String(g.user_id ?? 'anon')
        const isExpanded = expanded.has(key)
        return (
          <div
            key={key}
            className="rounded-xl overflow-hidden"
            style={{ border: '1px solid #2A2A2A' }}
          >
            {/* Header row */}
            <div
              className="flex items-center justify-between px-4 py-3 cursor-pointer select-none"
              style={{ background: '#111111' }}
              onClick={() => toggle(key)}
            >
              <div className="flex items-center gap-3">
                <div
                  className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{ background: 'rgba(124,58,237,0.18)' }}
                >
                  <Users size={14} className="text-purple-400" />
                </div>
                <div>
                  <p className="text-white text-sm font-medium">
                    {g.user_name ?? g.user_email ?? 'Anonymous'}
                  </p>
                  {g.user_email && g.user_name && (
                    <p className="text-[#52525b] text-xs">{g.user_email}</p>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-3">
                {/* Sentiment pills */}
                <span
                  className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px]"
                  style={{ background: 'rgba(52,211,153,0.12)', color: '#34d399' }}
                >
                  <ThumbsUp size={10} /> {g.positive}
                </span>
                <span
                  className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px]"
                  style={{ background: 'rgba(239,68,68,0.12)', color: '#f87171' }}
                >
                  <ThumbsDown size={10} /> {g.negative}
                </span>
                <span className="text-[#52525b] text-xs mr-2">{g.total_feedback} total</span>

                {/* Clear button — only shown when user_id is present */}
                {g.user_id !== null && (
                  <ConfirmButton
                    label="Clear"
                    confirmLabel="Yes, clear all"
                    variant="warning"
                    onConfirm={async () => {
                      await onClear(g.user_id!)
                    }}
                  />
                )}

                {isExpanded ? (
                  <ChevronUp size={14} className="text-[#52525b]" />
                ) : (
                  <ChevronDown size={14} className="text-[#52525b]" />
                )}
              </div>
            </div>

            {/* Expanded entries */}
            <AnimatePresence initial={false}>
              {isExpanded && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.22, ease: 'easeInOut' }}
                  style={{ overflow: 'hidden' }}
                >
                  <div style={{ borderTop: '1px solid #1A1A1A' }}>
                    {g.entries.map((e) => (
                      <div
                        key={e.id}
                        className="px-4 py-3 flex items-start gap-3"
                        style={{ borderBottom: '1px solid #141414' }}
                      >
                        <div className="mt-0.5 flex-shrink-0">
                          {e.feedback === 'positive' ? (
                            <ThumbsUp size={13} className="text-[#34d399]" />
                          ) : (
                            <ThumbsDown size={13} className="text-[#f87171]" />
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-[#a1a1aa] text-xs leading-relaxed">{e.question}</p>
                          <p className="text-[#3f3f46] text-[11px] mt-1">
                            {e.intent} · {e.created_at ? e.created_at.slice(0, 16) : '—'}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )
      })}
    </div>
  )
}

// ---------------------------------------------------------------------------
// AdminPage
// ---------------------------------------------------------------------------

export default function AdminPage() {
  const navigate = useNavigate()
  const user     = getStoredUser()

  async function handleSignOut() {
    await logout()
    navigate('/login', { replace: true })
  }

  const [tab,      setTab]      = useState<Tab>('overview')
  const [stats,    setStats]    = useState<AdminStats | null>(null)
  const [users,    setUsers]    = useState<AdminUser[] | null>(null)
  const [sessions, setSessions] = useState<AdminSession[] | null>(null)
  const [feedback, setFeedback] = useState<AdminFeedbackGroup[] | null>(null)
  const [error,    setError]    = useState<string | null>(null)

  // Redirect non-admins immediately
  useEffect(() => {
    if (!user?.is_admin) {
      navigate('/app', { replace: true })
    }
  }, [user, navigate])

  // Load data for active tab
  useEffect(() => {
    setError(null)
    async function load() {
      try {
        if (tab === 'overview' && !stats) {
          setStats(await fetchAdminStats())
        } else if (tab === 'users' && !users) {
          setUsers(await fetchAdminUsers())
        } else if (tab === 'sessions' && !sessions) {
          setSessions(await fetchAdminSessions())
        } else if (tab === 'feedback' && !feedback) {
          setFeedback(await fetchAdminFeedback())
        }
      } catch (err: unknown) {
        const msg = extractApiError(err)
        setError(msg)
      }
    }
    load()
  }, [tab]) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleDeleteUser(id: number) {
    await deleteAdminUser(id)
    setUsers((prev) => prev?.filter((u) => u.id !== id) ?? null)
  }

  async function handleDeleteSession(id: string) {
    await deleteAdminSession(id)
    setSessions((prev) => prev?.filter((s) => s.session_id !== id) ?? null)
    // Update stats count
    setStats((prev) => prev ? { ...prev, total_sessions: prev.total_sessions - 1 } : null)
  }

  async function handleClearFeedback(userId: number) {
    const result = await clearUserFeedback(userId)
    setFeedback((prev) =>
      prev?.map((g) =>
        g.user_id === userId
          ? { ...g, entries: [], total_feedback: 0, positive: 0, negative: 0 }
          : g,
      ) ?? null,
    )
    // Update stats count
    setStats((prev) =>
      prev ? { ...prev, total_feedback: prev.total_feedback - result.deleted_count } : null,
    )
  }

  if (!user?.is_admin) return null

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.35 }}
      className="min-h-screen flex flex-col"
      style={{ background: '#080808' }}
    >
      {/* Background grid */}
      <div
        className="fixed inset-0 pointer-events-none"
        style={{
          backgroundImage:
            'linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px)',
          backgroundSize: '44px 44px',
        }}
      />

      {/* Purple glow */}
      <div
        className="fixed pointer-events-none"
        style={{
          width: '600px',
          height: '600px',
          top: '0',
          left: '50%',
          transform: 'translateX(-50%)',
          background:
            'radial-gradient(circle, rgba(88,28,235,0.18) 0%, transparent 65%)',
          filter: 'blur(60px)',
        }}
      />

      {/* Top bar */}
      <div className="relative z-10 px-6 py-4 flex items-center justify-between" style={{ borderBottom: '1px solid #1A1A1A' }}>
        <Link to="/app" className="flex items-center gap-2.5 group">
          <div
            className="w-8 h-8 rounded-xl flex items-center justify-center"
            style={{
              background: 'linear-gradient(135deg, #7c3aed 0%, #3b82f6 100%)',
              boxShadow: '0 0 12px rgba(124,58,237,0.4)',
            }}
          >
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold text-white text-base tracking-tight">
            Insights<span className="text-purple-400">.ai</span>
          </span>
        </Link>

        <div className="flex items-center gap-3">
          <span
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold"
            style={{ background: 'rgba(124,58,237,0.18)', color: '#a78bfa', border: '1px solid rgba(124,58,237,0.3)' }}
          >
            <ShieldAlert size={11} /> Admin
          </span>
          <button
            onClick={handleSignOut}
            className="flex items-center gap-1.5 text-[#71717a] hover:text-red-400 text-sm transition-colors"
          >
            <LogOut size={14} />
            Sign out
          </button>
        </div>
      </div>

      {/* Main content */}
      <div className="relative z-10 flex-1 max-w-6xl mx-auto w-full px-6 py-8">
        {/* Page title */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-white">Admin Panel</h1>
          <p className="text-[#52525b] text-sm mt-1">System overview and management tools.</p>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-2 mb-6">
          <TabButton active={tab === 'overview'}  onClick={() => setTab('overview')}>Overview</TabButton>
          <TabButton active={tab === 'users'}     onClick={() => setTab('users')}>Users</TabButton>
          <TabButton active={tab === 'sessions'}  onClick={() => setTab('sessions')}>Sessions</TabButton>
          <TabButton active={tab === 'feedback'}  onClick={() => setTab('feedback')}>Feedback</TabButton>
        </div>

        {/* Error banner */}
        {error && (
          <div
            className="flex items-center gap-2.5 px-4 py-3 rounded-xl mb-6 text-sm text-[#f87171]"
            style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)' }}
          >
            <AlertTriangle size={14} className="flex-shrink-0" />
            {error}
          </div>
        )}

        {/* Tab content */}
        <AnimatePresence mode="wait">
          <motion.div
            key={tab}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
          >
            {tab === 'overview' && <OverviewTab stats={stats} />}
            {tab === 'users'    && <UsersTab    users={users}    onDelete={handleDeleteUser} />}
            {tab === 'sessions' && <SessionsTab sessions={sessions} onDelete={handleDeleteSession} />}
            {tab === 'feedback' && <FeedbackTab groups={feedback} onClear={handleClearFeedback} />}
          </motion.div>
        </AnimatePresence>
      </div>
    </motion.div>
  )
}

// ---------------------------------------------------------------------------
// Error extractor
// ---------------------------------------------------------------------------

function extractApiError(err: unknown): string {
  if (err && typeof err === 'object' && 'response' in err) {
    const res = (err as { response?: { data?: { detail?: string } } }).response
    const detail = res?.data?.detail
    if (typeof detail === 'string') return detail
  }
  return 'Something went wrong. Please try again.'
}
