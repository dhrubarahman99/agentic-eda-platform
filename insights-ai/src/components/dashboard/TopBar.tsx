import { useState, useEffect, useRef } from 'react'
import {
  Sparkles, FileSpreadsheet, MessageSquare,
  Table2, Columns2, Download, ChevronDown,
  FileDown, FileBarChart, Menu, LogOut,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { useSessionStore } from '@/stores/sessionStore'
import { useChatStore } from '@/stores/chatStore'
import { useToastStore } from '@/stores/toastStore'
import { downloadCleanedDataset, downloadPreprocessingReport } from '@/api/export'
import { logout } from '@/api/auth'

type Tab = 'insights' | 'chat' | 'preview' | 'columns'

interface TabDef {
  id: Tab
  label: string
  icon: React.ReactNode
}

const TABS: TabDef[] = [
  { id: 'insights', label: 'Insights', icon: <Sparkles size={14} /> },
  { id: 'chat',     label: 'Chat',     icon: <MessageSquare size={14} /> },
  { id: 'preview',  label: 'Preview',  icon: <Table2 size={14} /> },
  { id: 'columns',  label: 'Columns',  icon: <Columns2 size={14} /> },
]

export default function TopBar() {
  const navigate       = useNavigate()
  const filename       = useSessionStore((s) => s.filename)
  const dashboardData  = useSessionStore((s) => s.dashboardData)
  const profile        = useSessionStore((s) => s.profile)
  const activeTab      = useSessionStore((s) => s.activeTab)
  const setActiveTab   = useSessionStore((s) => s.setActiveTab)
  const sessionId      = useSessionStore((s) => s.sessionId)
  const resetSession   = useSessionStore((s) => s.resetSession)
  const isMenuOpen     = useSessionStore((s) => s.isMenuOpen)
  const setMenuOpen    = useSessionStore((s) => s.setMenuOpen)
  const clearAllSessions = useChatStore((s) => s.clearAllSessions)
  const addToast       = useToastStore((s) => s.addToast)

  const [isExportOpen, setIsExportOpen] = useState(false)
  const exportRef = useRef<HTMLDivElement>(null)

  const rowCount = dashboardData?.shape.rows ?? profile?.shape.rows ?? 0
  const activeTabLabel = TABS.find((t) => t.id === activeTab)?.label ?? ''

  // Close export dropdown on outside click
  useEffect(() => {
    if (!isExportOpen) return
    function handleClick(e: MouseEvent) {
      if (exportRef.current && !exportRef.current.contains(e.target as Node)) {
        setIsExportOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [isExportOpen])

  async function handleLogout() {
    try {
      await logout()
      clearAllSessions()
      resetSession()
      navigate('/login')
    } catch {
      addToast('error', 'Logout failed. Please try again.')
    }
  }

  return (
    <header className="fixed top-0 left-0 right-0 h-14 z-40 bg-[#0F0F0F]/95 backdrop-blur-md border-b border-[#2A2A2A] flex items-center justify-between px-4">

      {/* ── Left zone ─────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3">
        {/* Hamburger - visible only below lg (1024px) */}
        <button
          onClick={() => setMenuOpen(!isMenuOpen)}
          className="lg:hidden w-8 h-8 flex items-center justify-center rounded-lg text-[#A1A1AA] hover:text-white hover:bg-[#1A1A1A] transition-all duration-150 cursor-pointer"
          aria-label="Toggle menu"
        >
          <Menu size={16} />
        </button>

        <div className="flex items-center gap-1.5">
          <Sparkles size={18} className="text-purple-400" />
          <span className="font-bold text-white text-sm tracking-tight">
            Insights<span className="text-purple-400">.ai</span>
          </span>
        </div>

        {/* Divider + dataset chip — hidden below sm (640px) */}
        <div className="hidden sm:block w-px h-5 bg-[#2A2A2A]" />

        <div className="hidden sm:flex items-center gap-1.5 bg-[#1A1A1A] border border-[#2A2A2A] rounded-full px-3 py-1 text-xs text-[#A1A1AA]">
          <FileSpreadsheet size={12} />
          <span className="truncate max-w-32">{filename}</span>
          <span>·</span>
          <span>{rowCount} rows</span>
        </div>
      </div>

      {/* ── Centre zone ────────────────────────────────────────────────── */}
      {/* Desktop: full tab switcher (md+) */}
      <div className="hidden md:flex items-center">
        <div className="bg-[#1A1A1A] rounded-full p-1 flex gap-1">
          {TABS.map(({ id, label, icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`rounded-full px-4 py-1.5 text-sm font-medium cursor-pointer flex items-center gap-1.5 transition-all duration-150 ${
                activeTab === id
                  ? 'bg-purple-600 text-white'
                  : 'text-[#A1A1AA] hover:text-white'
              }`}
            >
              {icon}
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Mobile: active tab name only (<md) */}
      <span className="md:hidden text-white text-sm font-semibold">{activeTabLabel}</span>

      {/* ── Right zone ────────────────────────────────────────────────── */}
      <div className="flex items-center gap-2 sm:gap-3">

        {/* Export dropdown */}
        <div ref={exportRef} className="relative">
          <button
            onClick={() => setIsExportOpen(!isExportOpen)}
            className="flex items-center gap-1.5 bg-[#1A1A1A] border border-[#2A2A2A] rounded-xl px-2.5 py-1.5 text-sm text-[#A1A1AA] hover:text-white cursor-pointer transition-all duration-150"
          >
            <Download size={14} />
            <span className="hidden sm:inline">Export</span>
            <ChevronDown
              size={12}
              className={`hidden sm:block transition-transform duration-150 ${isExportOpen ? 'rotate-180' : ''}`}
            />
          </button>

          <AnimatePresence>
            {isExportOpen && (
              <motion.div
                initial={{ opacity: 0, y: -8, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -8, scale: 0.97 }}
                transition={{ duration: 0.15 }}
                className="absolute right-0 top-full mt-1 w-56 bg-[#1A1A1A] border border-[#2A2A2A] rounded-xl shadow-2xl p-1 z-50"
              >
                <button
                  onClick={() => {
                    downloadCleanedDataset(sessionId!)
                    addToast('success', 'Download started')
                    setIsExportOpen(false)
                  }}
                  className="w-full flex items-center gap-2.5 px-3 py-2.5 text-sm text-[#A1A1AA] hover:text-white hover:bg-[#242424] rounded-lg cursor-pointer transition-colors"
                >
                  <FileDown size={14} />
                  Download Cleaned Dataset (.csv)
                </button>
                <button
                  onClick={() => {
                    downloadPreprocessingReport(sessionId!)
                    addToast('success', 'Download started')
                    setIsExportOpen(false)
                  }}
                  className="w-full flex items-center gap-2.5 px-3 py-2.5 text-sm text-[#A1A1AA] hover:text-white hover:bg-[#242424] rounded-lg cursor-pointer transition-colors"
                >
                  <FileBarChart size={14} />
                  Download Preprocessing Report
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Logout */}
        <button
          onClick={handleLogout}
          className="w-8 h-8 flex items-center justify-center rounded-lg text-[#A1A1AA] hover:text-red-400 hover:bg-[#1A1A1A] transition-all duration-150"
          aria-label="Logout"
          title="Sign out"
        >
          <LogOut size={16} />
        </button>
      </div>
    </header>
  )
}
