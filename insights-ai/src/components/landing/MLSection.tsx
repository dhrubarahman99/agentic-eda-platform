import { motion } from 'framer-motion'
import { TrendingUp, Target, AlertTriangle, Layers, Check } from 'lucide-react'

const models = [
  {
    icon: TrendingUp,
    name: 'Time-series forecasting',
    subtitle: null,
    badge: 'Active',
    badgeColor: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  },
  {
    icon: Target,
    name: 'Driver analysis',
    subtitle: null,
    badge: 'Active',
    badgeColor: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  },
  {
    icon: AlertTriangle,
    name: 'Anomaly detection',
    subtitle: 'Identified 3 records',
    badge: '3 Found',
    badgeColor: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
  },
  {
    icon: Layers,
    name: 'Segmentation & clustering',
    subtitle: '4 Rows · 2ms',
    badge: 'Active',
    badgeColor: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  },
]

const bullets = [
  'Reliability scores on every insight',
  'Full audit trail of every transformation',
  'Source code generated for reproducibility',
]

export default function MLSection() {
  return (
    <section className="bg-[#0A0A0A] py-24 px-6">
      <div className="max-w-7xl mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
          {/* Left — text */}
          <motion.div
            initial={{ opacity: 0, x: -30 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, ease: 'easeOut' }}
          >
            <p className="text-purple-400 text-xs font-mono font-semibold tracking-widest uppercase mb-4">
              Real ML, not LLM guesswork
            </p>
            <h2 className="text-4xl font-bold leading-tight mb-6">
              <span className="text-white">Powered by </span>
              <span className="bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
                proven ML models
              </span>
              <span className="text-white">, explained in plain English.</span>
            </h2>
            <p className="text-[#A1A1AA] leading-relaxed mb-8">
              We don&apos;t just ask an LLM to guess. Insights.ai runs real statistical tests and machine
              learning models, then translates the results into clear, actionable insights you can trust
              and explain.
            </p>
            <ul className="space-y-3">
              {bullets.map((bullet) => (
                <li key={bullet} className="flex items-center gap-3">
                  <div className="w-5 h-5 rounded-full bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center flex-shrink-0">
                    <Check className="w-3 h-3 text-emerald-400" />
                  </div>
                  <span className="text-[#A1A1AA] text-sm">{bullet}</span>
                </li>
              ))}
            </ul>
          </motion.div>

          {/* Right — model panel */}
          <motion.div
            initial={{ opacity: 0, x: 30 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, ease: 'easeOut', delay: 0.1 }}
          >
            <div className="bg-[#1A1A1A] rounded-2xl border border-[#2A2A2A] p-6">
              <p className="text-[#52525B] text-xs font-mono mb-4 uppercase tracking-widest">
                Active models
              </p>
              <div className="space-y-0">
                {models.map((model, i) => {
                  const Icon = model.icon
                  return (
                    <div key={model.name}>
                      <div className="flex items-center justify-between py-4">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-lg bg-[#111111] border border-[#2A2A2A] flex items-center justify-center flex-shrink-0">
                            <Icon className="w-4 h-4 text-purple-400" />
                          </div>
                          <div>
                            <p className="text-white text-sm font-medium">{model.name}</p>
                            {model.subtitle && (
                              <p className="text-[#52525B] text-xs mt-0.5">{model.subtitle}</p>
                            )}
                          </div>
                        </div>
                        <span
                          className={`text-xs font-medium px-2.5 py-1 rounded-full border ${model.badgeColor}`}
                        >
                          {model.badge}
                        </span>
                      </div>
                      {i < models.length - 1 && (
                        <div className="h-px bg-[#2A2A2A]" />
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  )
}
