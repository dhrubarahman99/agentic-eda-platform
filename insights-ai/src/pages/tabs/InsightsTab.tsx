import { useState, useRef } from 'react'
import { MessageSquare, X } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useSessionStore } from '@/stores/sessionStore'
import DatasetSummaryCard from '@/components/dashboard/DatasetSummaryCard'
import InsightFeed from '@/components/dashboard/InsightFeed'
import ChatPanel, { type PendingChatMessage } from '@/components/dashboard/ChatPanel'
import ChartsPanel from '@/components/dashboard/ChartsPanel'



interface InsightsTabProps {
  onSendToChat: (question: string) => void
}

export default function InsightsTab({ onSendToChat: _onSendToChat }: InsightsTabProps) {
  const insights           = useSessionStore((s) => s.insights)
  const profile            = useSessionStore((s) => s.profile)
  const dashboardData      = useSessionStore((s) => s.dashboardData)
  const setActiveTab       = useSessionStore((s) => s.setActiveTab)
  const setQueuedQuestion  = useSessionStore((s) => s.setQueuedQuestion)

  const [pendingMsg, setPendingMsg]         = useState<PendingChatMessage | null>(null)
  const [mobileChatOpen, setMobileChatOpen] = useState(false)
  const seqRef = useRef(0)

  if (!profile || !dashboardData) return null

  function handleFollowUp(question: string) {
    seqRef.current += 1
    setPendingMsg({ text: question, seq: seqRef.current })

    // Also queue the question so the full Chat tab can pick it up
    setQueuedQuestion({ text: question, seq: seqRef.current })
    setActiveTab('chat')
  }

  return (
    <div className="flex h-[calc(100vh-3.5rem)] overflow-hidden min-w-0">

      {/*
        ── 3-panel area ──────────────────────────────────────────────────
        All three panels share the same top edge.
        Layout:
          <lg  : left column full-width  (chat = floating button)
          lg   : [left column flex-1]  |  [chat 340px]
          xl   : [left column flex-1]  |  [chat 340px]  |  [charts 220px]
      */}

      {/* ── Left column: summary card + insight feed ───────────────────── */}
      <div className="flex-1 min-w-0 overflow-y-auto">
        <div className="px-4 pt-4 pb-4">
          <DatasetSummaryCard profile={profile} dashboardData={dashboardData} />
        </div>
        <InsightFeed insights={insights} onFollowUp={handleFollowUp} />
      </div>

      {/* ── Desktop chat panel (lg+) ───────────────────────────────────── */}
      {/*
        This panel is ALWAYS mounted (even on mobile, just CSS-hidden).
        It is the only instance that receives pendingMsg, so follow-up chips
        never produce duplicate submissions regardless of screen size.
      */}
      <div className="hidden lg:flex flex-col w-[340px] flex-shrink-0">
        <ChatPanel
          pendingMessage={pendingMsg}
          onPendingMessageConsumed={() => setPendingMsg(null)}
        />
      </div>

      {/* ── Charts panel (xl+) ─────────────────────────────────────────── */}
      <div className="hidden xl:flex flex-col w-[220px] flex-shrink-0">
        <ChartsPanel />
      </div>

      {/* ── Mobile: floating chat button (<lg) ─────────────────────────── */}
      <button
        onClick={() => setMobileChatOpen(true)}
        className="lg:hidden fixed bottom-6 right-6 w-14 h-14 rounded-full bg-purple-600 shadow-lg flex items-center justify-center z-40 hover:bg-purple-700 transition-colors"
        aria-label="Open chat"
      >
        <MessageSquare size={24} className="text-white" />
      </button>

      {/* ── Mobile: full-screen chat overlay ───────────────────────────── */}
      {/*
        This ChatPanel does NOT receive pendingMsg — the always-mounted desktop
        panel above handles submission. The overlay just shows the shared message
        history from chatStore so the user can see the response.
      */}
      <AnimatePresence>
        {mobileChatOpen && (
          <motion.div
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
            className="fixed inset-0 z-50 bg-[#0F0F0F] flex flex-col"
          >
            <div className="p-4 border-b border-[#2A2A2A] flex items-center justify-between flex-shrink-0">
              <span className="text-white font-semibold text-sm">Chat</span>
              <button
                onClick={() => setMobileChatOpen(false)}
                className="text-[#A1A1AA] hover:text-white transition-colors cursor-pointer"
                aria-label="Close chat"
              >
                <X size={20} />
              </button>
            </div>
            <div className="flex-1 overflow-hidden">
              {/* No pendingMessage — submission is handled by the desktop panel */}
              <ChatPanel />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
