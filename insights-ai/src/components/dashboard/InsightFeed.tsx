import { Inbox } from 'lucide-react'
import type { InsightResult } from '@/api/types'
import InsightCard from './InsightCard'

interface InsightFeedProps {
  insights: InsightResult[]
  onFollowUp: (question: string) => void
}

export default function InsightFeed({ insights, onFollowUp }: InsightFeedProps) {
  if (insights.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64">
        <Inbox size={40} className="text-[#2A2A2A]" />
        <p className="text-white mt-4">No insights found</p>
        <p className="text-[#52525B] text-sm mt-1">Try uploading a different dataset</p>
      </div>
    )
  }

  return (
    <div className="p-4 space-y-4 min-w-0">
      {insights.map((insight, i) => (
        <InsightCard
          key={insight.insight_id}
          insight={insight}
          index={i}
          onFollowUp={onFollowUp}
        />
      ))}
    </div>
  )
}
