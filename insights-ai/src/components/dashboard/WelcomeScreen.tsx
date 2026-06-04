import { useRef, useState } from 'react'
import { Sparkles, Sunrise, Sun, Moon, CloudUpload, Info, AlertCircle } from 'lucide-react'
import { motion } from 'framer-motion'
import { useSessionStore } from '@/stores/sessionStore'

// ---------------------------------------------------------------------------
// TopBar — logo only, no theme toggle on the upload/welcome page
// ---------------------------------------------------------------------------

function TopBar() {
  return (
    <header className="h-14 flex items-center px-6 border-b border-[#2A2A2A] bg-[#0A0A0A]/95 backdrop-blur-md flex-shrink-0">
      <div className="flex items-center gap-2.5">
        <div
          className="w-8 h-8 rounded-xl flex items-center justify-center"
          style={{
            background: 'linear-gradient(135deg, #7c3aed 0%, #3b82f6 100%)',
            boxShadow: '0 0 12px rgba(124,58,237,0.5)',
          }}
        >
          <Sparkles className="w-4 h-4 text-white" />
        </div>
        <span className="font-bold text-white text-base tracking-tight">
          Insights<span className="text-purple-400">.ai</span>
        </span>
      </div>
    </header>
  )
}

// ---------------------------------------------------------------------------
// Greeting helpers
// ---------------------------------------------------------------------------

function getGreeting() {
  const hour = new Date().getHours()
  if (hour >= 5 && hour < 12) {
    return { period: 'morning', icon: <Sunrise size={36} className="text-amber-400" /> }
  }
  if (hour >= 12 && hour < 18) {
    return { period: 'afternoon', icon: <Sun size={36} className="text-amber-400" /> }
  }
  return { period: 'evening', icon: <Moon size={36} className="text-purple-400" /> }
}

// ---------------------------------------------------------------------------
// WelcomeScreen
// ---------------------------------------------------------------------------

interface WelcomeScreenProps {
  onFileSelect: (file: File) => void
  /** When true, the component is rendered inside DashboardLayout — skip the
   *  standalone TopBar and full-page wrapper so it fits as a content panel. */
  embedded?: boolean
  /** Error message returned from a failed upload attempt. */
  uploadError?: string
}

export default function WelcomeScreen({ onFileSelect, embedded = false, uploadError }: WelcomeScreenProps) {
  const userName = useSessionStore((s) => s.userName)
  const [isDragOver, setIsDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { period, icon } = getGreeting()

  function handleDragOver(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setIsDragOver(true)
  }

  function handleDragLeave() {
    setIsDragOver(false)
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setIsDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) onFileSelect(file)
  }

  function handleClick() {
    fileInputRef.current?.click()
  }

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) onFileSelect(file)
  }

  return (
    <div className={embedded ? 'flex flex-col bg-theme-base' : 'min-h-screen flex flex-col bg-theme-base'}>
      {/* Only render the standalone TopBar when NOT embedded inside DashboardLayout */}
      {!embedded && <TopBar />}

      {/* Main content */}
      <motion.main
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className={`flex-1 flex flex-col items-center justify-center gap-8 px-4 py-12 ${
          embedded ? 'min-h-[calc(100vh-3.5rem)]' : ''
        }`}
      >
        {/* Greeting */}
        <div className="flex flex-col items-center text-center">
          <div className="mb-3">{icon}</div>
          <h1 className="text-4xl font-bold text-white">
            Good {period}, {userName}
          </h1>
          <p className="text-[#A1A1AA] text-base mt-2">
            Upload a CSV file to get started with your analysis
          </p>
        </div>

        {/* Upload zone */}
        <div
          onClick={handleClick}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`max-w-xl w-full bg-[#1A1A1A] rounded-2xl border-2 border-dashed p-12 cursor-pointer transition-all duration-200 ${
            isDragOver
              ? 'border-purple-500 scale-[1.01]'
              : uploadError
              ? 'border-red-500/50 hover:border-red-500/70'
              : 'border-[#2A2A2A] hover:border-purple-500/50'
          }`}
          style={
            isDragOver
              ? { boxShadow: '0 0 0 4px rgba(124,58,237,0.15)' }
              : undefined
          }
        >
          <div className="flex flex-col items-center text-center">
            <CloudUpload size={48} className={uploadError ? 'text-red-400' : 'text-purple-400'} />
            <p className="text-white font-semibold text-lg mt-4">
              Drag and drop your CSV file here
            </p>
            <p className="text-[#A1A1AA] text-sm mt-1">or click to browse</p>

            <div className="w-full h-px bg-[#2A2A2A] mt-6" />

            <div className="flex items-center gap-1.5 mt-4">
              <Info size={14} className="text-[#52525B]" />
              <span className="text-xs text-[#52525B]">
                Supports CSV files up to 10MB
              </span>
            </div>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={handleInputChange}
          />
        </div>

        {/* Upload error message — shown inline below the upload zone */}
        {uploadError && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25 }}
            className="max-w-xl w-full flex items-start gap-2.5 bg-red-500/10 border border-red-500/30 rounded-xl px-4 py-3"
          >
            <AlertCircle size={15} className="text-red-400 flex-shrink-0 mt-0.5" />
            <p className="text-red-400 text-sm leading-snug">{uploadError}</p>
          </motion.div>
        )}

      </motion.main>
    </div>
  )
}
