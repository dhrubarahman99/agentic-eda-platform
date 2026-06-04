import type { ReactNode } from 'react'
import TopBar from './TopBar'
import Sidebar from './Sidebar'

interface DashboardLayoutProps {
  children: ReactNode
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  return (
    <div className="min-h-screen bg-theme-base">
      <TopBar />
      <Sidebar />
      {/*
        Main area margins match sidebar widths:
          <1024px : ml-0  (sidebar is hidden overlay)
          1024–1279px : ml-14 (sidebar collapsed w-14)
          ≥1280px : ml-60 (sidebar full w-60)
      */}
      <main className="ml-0 lg:ml-14 xl:ml-60 pt-14 min-h-screen">
        {children}
      </main>
    </div>
  )
}
