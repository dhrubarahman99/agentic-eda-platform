import { motion, type Variants } from 'framer-motion'
import { Check, X, Minus } from 'lucide-react'

type Status = 'yes' | 'no' | 'partial'

const rows: { capability: string; insights: Status; chatgpt: Status }[] = [
  { capability: 'Built specifically for CSV/data analysis', insights: 'yes', chatgpt: 'no' },
  { capability: 'Real ML models (not just text generation)', insights: 'yes', chatgpt: 'no' },
  { capability: 'Reliability scores on insights', insights: 'yes', chatgpt: 'no' },
  { capability: 'Data quality warnings', insights: 'yes', chatgpt: 'no' },
  { capability: 'Explainable analysis steps', insights: 'yes', chatgpt: 'partial' },
  { capability: 'General chat & writing', insights: 'partial', chatgpt: 'yes' },
]

function StatusIcon({ status }: { status: Status }) {
  if (status === 'yes') return <Check className="w-5 h-5 text-emerald-500 mx-auto" />
  if (status === 'no') return <X className="w-5 h-5 text-red-500 mx-auto" />
  return <Minus className="w-5 h-5 text-amber-400 mx-auto" />
}

const rowVariants: Variants = {
  hidden: { opacity: 0, x: -16 },
  visible: (i: number) => ({
    opacity: 1,
    x: 0,
    transition: { duration: 0.4, delay: i * 0.07, ease: 'easeOut' as const },
  }),
}

export default function ComparisonSection() {
  return (
    <section id="compare" className="bg-[#111111] py-24 px-6">
      <div className="max-w-3xl mx-auto">
        {/* Heading */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="text-center mb-4"
        >
          <h2 className="text-4xl font-bold text-white">Why not just use ChatGPT?</h2>
        </motion.div>
        <motion.p
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="text-[#A1A1AA] text-center mb-16"
        >
          General assistants weren&apos;t built for serious data work.
        </motion.p>

        {/* Table */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.15 }}
          className="overflow-hidden rounded-2xl border border-[#2A2A2A]"
        >
          {/* Header */}
          <div className="grid grid-cols-3 bg-[#1A1A1A] border-b border-[#2A2A2A] px-6 py-4">
            <span className="text-[#A1A1AA] text-sm font-medium">Capability</span>
            <div className="text-center">
              <span className="text-white text-sm font-semibold border-b-2 border-purple-500 pb-0.5">
                Insights.ai
              </span>
            </div>
            <div className="text-center">
              <span className="text-[#A1A1AA] text-sm font-medium">ChatGPT / Gemini</span>
            </div>
          </div>

          {/* Rows */}
          {rows.map((row, i) => (
            <motion.div
              key={row.capability}
              custom={i}
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true }}
              variants={rowVariants}
              className={`grid grid-cols-3 px-6 py-4 border-b border-[#2A2A2A] last:border-b-0 ${
                i % 2 === 0 ? 'bg-[#111111]' : 'bg-[#0F0F0F]'
              }`}
            >
              <span className="text-[#A1A1AA] text-sm self-center">{row.capability}</span>
              <div className="flex items-center justify-center">
                <StatusIcon status={row.insights} />
              </div>
              <div className="flex items-center justify-center">
                <StatusIcon status={row.chatgpt} />
              </div>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  )
}
