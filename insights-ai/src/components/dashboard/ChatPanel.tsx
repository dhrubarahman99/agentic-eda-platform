import { useRef, useEffect, useState } from 'react'
import { MessageSquare, RotateCcw, Sparkles, Send, Zap } from 'lucide-react'
import { useChatStore } from '@/stores/chatStore'
import { useSessionStore } from '@/stores/sessionStore'
import { askQuestion } from '@/api/query'
import ChatMessage from './ChatMessage'
import ThinkingIndicator from './ThinkingIndicator'


/** A pending message sent programmatically (e.g. from a follow-up chip).
 *  The `seq` counter ensures clicking the same question twice always fires the effect. */
export interface PendingChatMessage {
  text: string
  seq: number
}

interface ChatPanelProps {
  fullWidth?: boolean
  showQuickActions?: boolean
  pendingMessage?: PendingChatMessage | null
  onPendingMessageConsumed?: () => void
}

export default function ChatPanel({
  fullWidth = false,
  showQuickActions = false,
  pendingMessage,
  onPendingMessageConsumed,
}: ChatPanelProps) {
  const sessionId         = useSessionStore((s) => s.sessionId)
  const profile           = useSessionStore((s) => s.profile)
  const queuedQuestion    = useSessionStore((s) => s.queuedQuestion)
  const setQueuedQuestion = useSessionStore((s) => s.setQueuedQuestion)

  const { getMessages, isThinking, addMessage, setThinking, clearSession } = useChatStore()

  // Derive session-specific messages
  const messages = getMessages(sessionId)

  const [inputValue, setInputValue] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Mutable ref keeps submitQuestion always-current, avoiding stale closures in effects
  const submitRef = useRef<(q: string) => void>((_q) => {})
  submitRef.current = async (question: string) => {
    if (!question.trim() || isThinking || !sessionId) return
    addMessage(sessionId, { id: crypto.randomUUID(), role: 'user', content: question, timestamp: new Date() })
    setThinking(true)
    try {
      const result = await askQuestion(sessionId, question)
      addMessage(sessionId, {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: result.plain_summary ?? '',
        queryResult: result,
        timestamp: new Date(),
      })
    } catch {
      addMessage(sessionId, {
        id: crypto.randomUUID(),
        role: 'error',
        content: 'Something went wrong. Please try again.',
        timestamp: new Date(),
      })
    } finally {
      setThinking(false)
    }
  }

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (!pendingMessage?.text) return
    const text = pendingMessage.text
    onPendingMessageConsumed?.()
    const t = setTimeout(() => submitRef.current(text), 50)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingMessage?.seq])

  // When rendered as full-width Chat tab, consume any queued question
  // sent from the Insights tab follow-up chips
  useEffect(() => {
    if (!fullWidth || !queuedQuestion) return
    const text = queuedQuestion.text
    setQueuedQuestion(null)
    const t = setTimeout(() => submitRef.current(text), 80)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fullWidth, queuedQuestion?.seq])

  function handleSubmit() {
    const question = inputValue.trim()
    if (!question || isThinking || !sessionId) return
    setInputValue('')
    submitRef.current(question)
  }

  function handleFollowUp(question: string) {
    submitRef.current(question)
  }

  function handleClear() {
    if (sessionId) clearSession(sessionId)
  }

  return (
    <div
      className={`flex flex-col ${
        fullWidth ? 'h-[calc(100vh-3.5rem)] bg-[#0F0F0F]' : 'h-full border-l border-[#2A2A2A]'
      }`}
    >
      {/* Header */}
      <div className="p-4 border-b border-[#2A2A2A] flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-2">
          <MessageSquare size={16} className="text-purple-400" />
          <span className="text-white font-semibold text-sm">Ask Anything</span>
        </div>
        <button onClick={handleClear} className="cursor-pointer">
          <RotateCcw size={14} className="text-[#52525B] hover:text-white transition-colors" />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && !isThinking ? (
          <div className="flex flex-col items-center justify-center h-full">
            <Sparkles size={32} className="text-[#2A2A2A]" />
            <p className="text-[#52525B] text-sm mt-3">Ask anything about your data</p>
          </div>
        ) : (
          messages.map((message) => (
            <ChatMessage key={message.id} message={message} onFollowUp={handleFollowUp} />
          ))
        )}
        {isThinking && <ThinkingIndicator />}
        <div ref={messagesEndRef} />
      </div>

      {/* Quick-actions container — full Chat tab only */}
      {showQuickActions && profile && profile.quick_actions.length > 0 && (
        <div className="px-3 pt-2 pb-1 border-t border-[#2A2A2A] flex-shrink-0">
          <div className="bg-[#1A1A1A] border border-[#2A2A2A] rounded-xl px-3 py-2">
            <div className="flex items-center gap-1.5 mb-2">
              <Zap size={11} className="text-purple-400" />
              <span className="text-[10px] text-[#52525B] uppercase tracking-wider font-semibold">Quick actions</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {profile.quick_actions.slice(0, 8).map((qa) => (
                <button
                  key={qa.action_id}
                  onClick={() => submitRef.current(qa.label)}
                  disabled={isThinking || !sessionId}
                  className="bg-[#242424] border border-[#333333] hover:border-purple-500/50 hover:bg-purple-900/10 rounded-full px-3 py-1 text-xs text-[#A1A1AA] hover:text-purple-300 cursor-pointer transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {qa.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Input */}
      <div className="p-3 border-t border-[#2A2A2A] flex-shrink-0">
        <div className="flex items-center gap-2 bg-[#1A1A1A] border border-[#2A2A2A] rounded-xl px-3 py-2 focus-within:border-purple-500/50 transition-colors">
          <textarea
            className="flex-1 bg-transparent text-sm text-white placeholder-[#52525B] outline-none resize-none"
            placeholder="Ask anything about your data..."
            rows={1}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSubmit()
              }
            }}
          />
          <button
            onClick={handleSubmit}
            disabled={!inputValue.trim() || isThinking}
            className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 transition-colors ${
              inputValue.trim() && !isThinking
                ? 'bg-purple-600 hover:bg-purple-700 text-white cursor-pointer'
                : 'bg-[#2A2A2A] text-[#52525B] cursor-not-allowed'
            }`}
          >
            <Send size={15} />
          </button>
        </div>
      </div>
    </div>
  )
}
