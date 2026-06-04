import ChatPanel from '@/components/dashboard/ChatPanel'

export default function ChatTab() {
  return (
    <div className="h-[calc(100vh-3.5rem)]">
      <ChatPanel fullWidth={true} showQuickActions={true} />
    </div>
  )
}
