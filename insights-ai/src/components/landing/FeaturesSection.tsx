import { motion, type Variants } from 'framer-motion'
import { Brain, BarChart3, MessageSquare, ShieldCheck, GitBranch, Lightbulb } from 'lucide-react'
import { cn } from '@/lib/utils'

const features = [
  {
    icon: Brain,
    title: 'Automated Insights',
    description: 'ML models surface what matters — trends, anomalies, drivers — without configuration.',
  },
  {
    icon: BarChart3,
    title: 'Beautiful Charts',
    description: 'Auto-generated visualisations tuned to your data. Save, share, export anywhere.',
  },
  {
    icon: MessageSquare,
    title: 'Natural language Q&A',
    description: 'Ask questions in plain English. Get answers with sources, code, and reasoning.',
  },
  {
    icon: ShieldCheck,
    title: 'Data quality warnings',
    description: 'Detects missing values, outliers, and biases before they become wrong conclusions.',
  },
  {
    icon: GitBranch,
    title: 'Explainable steps',
    description: 'See every transformation, model, and metric. No black boxes — full transparency.',
  },
  {
    icon: Lightbulb,
    title: 'Guided prompts',
    description: 'Curated suggestions help non-technical users explore data like a pro analyst.',
  },
]

const cardVariants: Variants = {
  hidden: { opacity: 0, y: 24 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, delay: i * 0.08, ease: 'easeOut' as const },
  }),
}

export default function FeaturesSection() {
  return (
    <section id="features" className="bg-[#111111] py-24 px-6">
      <div className="max-w-7xl mx-auto">
        {/* Label */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="flex justify-center mb-6"
        >
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border border-purple-500/30 bg-purple-500/10 text-purple-400 text-xs font-medium">
            <span>✦</span> Built for non-technical teams
          </span>
        </motion.div>

        {/* Headline */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="text-center mb-4"
        >
          <h2 className="text-4xl font-bold text-white leading-tight">
            Everything you need.
          </h2>
          <h2 className="text-4xl font-bold text-white leading-tight">
            Nothing you don&apos;t.
          </h2>
        </motion.div>

        <motion.p
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.15 }}
          className="text-[#A1A1AA] text-center max-w-2xl mx-auto mb-16"
        >
          A full analytics workflow powered by AI — from raw CSV to executive-ready insights in minutes.
        </motion.p>

        {/* Features grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {features.map((feature, i) => {
            const Icon = feature.icon
            return (
              <motion.div
                key={feature.title}
                custom={i}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true }}
                variants={cardVariants}
                whileHover={{ borderColor: 'rgba(124,58,237,0.5)' }}
                className={cn(
                  'bg-[#1A1A1A] rounded-2xl border border-[#2A2A2A] p-6',
                  'transition-colors duration-300 cursor-default'
                )}
              >
                <div className="w-10 h-10 rounded-lg bg-purple-900/30 border border-purple-500/20 flex items-center justify-center mb-4">
                  <Icon className="w-5 h-5 text-purple-400" />
                </div>
                <h3 className="text-white font-semibold text-base mb-2">{feature.title}</h3>
                <p className="text-[#A1A1AA] text-sm leading-relaxed">{feature.description}</p>
              </motion.div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
