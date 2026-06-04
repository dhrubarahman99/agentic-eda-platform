import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react'
import { useToastStore } from '@/stores/toastStore'
import type { Toast } from '@/stores/toastStore'

// ---------------------------------------------------------------------------
// Per-toast styling
// ---------------------------------------------------------------------------

const CONFIG = {
  success: {
    wrapper: 'bg-emerald-900/90 border-emerald-500/50 text-emerald-100',
    icon: <CheckCircle2 size={16} className="text-emerald-400 flex-shrink-0" />,
  },
  error: {
    wrapper: 'bg-red-900/90 border-red-500/50 text-red-100',
    icon: <AlertCircle size={16} className="text-red-400 flex-shrink-0" />,
  },
  info: {
    wrapper: 'bg-purple-900/90 border-purple-500/50 text-purple-100',
    icon: <Info size={16} className="text-purple-400 flex-shrink-0" />,
  },
} satisfies Record<Toast['type'], { wrapper: string; icon: React.ReactNode }>

// ---------------------------------------------------------------------------
// ToastContainer
// ---------------------------------------------------------------------------

export default function ToastContainer() {
  const { toasts, removeToast } = useToastStore()

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
      <AnimatePresence>
        {toasts.map((toast) => {
          const cfg = CONFIG[toast.type]
          return (
            <motion.div
              key={toast.id}
              initial={{ opacity: 0, x: 64, scale: 0.95 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 64, scale: 0.95 }}
              transition={{ duration: 0.2 }}
              className={`pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-xl border shadow-lg min-w-[240px] max-w-sm ${cfg.wrapper}`}
            >
              {cfg.icon}
              <p className="text-sm flex-1">{toast.message}</p>
              <button
                onClick={() => removeToast(toast.id)}
                className="opacity-60 hover:opacity-100 cursor-pointer transition-opacity"
              >
                <X size={14} />
              </button>
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}
