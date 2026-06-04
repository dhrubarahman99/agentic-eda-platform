import { motion } from 'framer-motion'
import { Upload, Cpu, TrendingUp, MessagesSquare } from 'lucide-react'

const steps = [
  {
    number: '01',
    icon: Upload,
    title: 'Upload CSV',
    description: 'Drag and drop any spreadsheet. We handle messy headers, dates, encodings.',
  },
  {
    number: '02',
    icon: Cpu,
    title: 'AI profiles your data',
    description: 'Statistical analysis + ML models run in seconds, ranked by impact.',
  },
  {
    number: '03',
    icon: TrendingUp,
    title: 'Get ranked insights',
    description: 'Charts, takeaways, reliability scores — explained step-by-step.',
  },
  {
    number: '04',
    icon: MessagesSquare,
    title: 'Ask follow-ups',
    description: 'Chat with your data. Refine, drill down, export, share.',
  },
]

export default function HowItWorksSection() {
  return (
    <section id="how-it-works" className="bg-[#0A0A0A] py-24 px-6">
      <div className="max-w-5xl mx-auto">
        {/* Heading */}
        <motion.h2
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="text-3xl font-bold text-white text-center mb-20"
        >
          —— From CSV to{' '}
          <span className="bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
            clarity
          </span>
          , in 4 steps.
        </motion.h2>

        {/* Steps */}
        <div className="relative">
          {/* Vertical connector line */}
          <div className="absolute left-1/2 top-0 bottom-0 w-px border-l border-dashed border-[#2A2A2A] hidden lg:block" />

          <div className="flex flex-col gap-16">
            {steps.map((step, i) => {
              const Icon = step.icon
              const isLeft = i % 2 === 0

              return (
                <motion.div
                  key={step.number}
                  initial={{ opacity: 0, x: isLeft ? -30 : 30 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.6, delay: 0.1, ease: 'easeOut' }}
                  className={`flex items-center gap-8 ${isLeft ? 'lg:flex-row' : 'lg:flex-row-reverse'} flex-col`}
                >
                  {/* Card side */}
                  <div className="flex-1 flex justify-center">
                    <div className="bg-[#1A1A1A] border border-[#2A2A2A] rounded-2xl p-8 max-w-sm w-full hover:border-purple-500/30 transition-colors duration-300">
                      <div className="flex items-center gap-2 mb-4">
                        <div className="w-8 h-8 rounded-lg bg-purple-900/30 border border-purple-500/20 flex items-center justify-center">
                          <Icon className="w-4 h-4 text-purple-400" />
                        </div>
                        <span className="text-purple-400 text-[10px] font-mono font-semibold tracking-widest uppercase">
                          Step {step.number}
                        </span>
                      </div>
                      <h3 className="text-white font-bold text-xl mb-2">{step.title}</h3>
                      <p className="text-[#A1A1AA] text-sm leading-relaxed">{step.description}</p>
                    </div>
                  </div>

                  {/* Number side */}
                  <div className="flex-1 flex justify-center items-center relative">
                    <span
                      className="text-[120px] font-black select-none leading-none"
                      style={{ color: '#1A1A1A', WebkitTextStroke: '1px #2A2A2A' }}
                    >
                      {i + 1}
                    </span>
                  </div>
                </motion.div>
              )
            })}
          </div>
        </div>
      </div>
    </section>
  )
}
