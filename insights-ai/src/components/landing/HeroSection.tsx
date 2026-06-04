import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, ChevronRight } from 'lucide-react'

const promptChips = ['Sales analysis', 'Customer trends', 'Financial review']

export default function HeroSection() {
  return (
    <section className="min-h-screen bg-[#0A0A0A] flex flex-col items-center justify-center pt-24 pb-16 px-6 relative overflow-hidden">
      {/* Subtle radial glow behind hero */}
      <div
        className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[400px] rounded-full pointer-events-none"
        style={{
          background: 'radial-gradient(ellipse, rgba(124,58,237,0.12) 0%, transparent 70%)',
        }}
      />

      <div className="relative z-10 flex flex-col items-center text-center max-w-4xl mx-auto w-full">
        {/* Announcement pill */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="mb-8 inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-[#2A2A2A] bg-[#111111] text-[#A1A1AA] text-sm"
        >
          <span className="text-purple-400">✦</span>
          <span>Now in private beta · Free for early users</span>
        </motion.div>

        {/* Main headline */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="mb-6"
        >
          <h1 className="font-black leading-[1.05] tracking-tight">
            <span className="block text-6xl md:text-7xl text-white">
              Turn Your Data
            </span>
            <span className="block text-6xl md:text-7xl">
              Into{' '}
              <span
                className="bg-gradient-to-r from-purple-400 via-pink-400 to-amber-400 bg-clip-text text-transparent"
              >
                Decisions
              </span>
            </span>
          </h1>
        </motion.div>

        {/* Subtitle */}
        <motion.p
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="text-[#A1A1AA] text-lg max-w-xl mx-auto mt-2 mb-10 leading-relaxed"
        >
          Upload any CSV and get AI-powered insights, charts, and answers — no technical skills required.
        </motion.p>

        {/* Interactive prompt card */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.4 }}
          className="w-full max-w-2xl bg-[#1A1A1A] rounded-2xl border border-[#2A2A2A] p-5 mb-8"
        >
          {/* Input row */}
          <div className="flex items-center gap-3 mb-4">
            <div className="flex-1 bg-[#111111] border border-[#2A2A2A] rounded-xl px-4 py-3 text-left">
              <span className="text-[#52525B] text-sm">What would you like to analyse?</span>
            </div>
            <div className="w-10 h-10 rounded-xl bg-purple-600/20 border border-purple-500/30 flex items-center justify-center flex-shrink-0">
              <ChevronRight className="w-4 h-4 text-purple-400" />
            </div>
          </div>

          {/* Chips row */}
          <div className="flex flex-wrap gap-2 mb-4">
            {promptChips.map((chip) => (
              <button
                key={chip}
                type="button"
                className="px-3 py-1.5 rounded-full border border-[#2A2A2A] hover:border-purple-500/50 text-[#A1A1AA] text-xs transition-colors duration-200 bg-[#111111] hover:bg-purple-950/20"
              >
                {chip}
              </button>
            ))}
          </div>

          {/* Caption */}
          <p className="text-[#52525B] text-xs text-center">
            Drop a CSV or describe your dataset — Insights handles the rest
          </p>
        </motion.div>

        {/* CTA buttons */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.5 }}
          className="flex flex-col sm:flex-row items-center gap-4 mb-6"
        >
          <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
            <Link
              to="/login"
              className="inline-flex items-center gap-2 bg-gradient-to-r from-purple-600 to-pink-600 text-white font-medium px-8 py-3 rounded-full shadow-[0_0_30px_rgba(124,58,237,0.3)] hover:shadow-[0_0_40px_rgba(124,58,237,0.45)] transition-shadow duration-300"
            >
              Start Analysing Free
              <ArrowRight className="w-4 h-4" />
            </Link>
          </motion.div>

          <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
            <a
              href="#how-it-works"
              className="inline-flex items-center gap-2 border border-white/20 text-white font-medium px-8 py-3 rounded-full hover:bg-white/10 transition-colors duration-200"
            >
              See how it works
            </a>
          </motion.div>
        </motion.div>

        {/* Trust line */}
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6, delay: 0.65 }}
          className="text-[#52525B] text-xs"
        >
          Trusted by analysts at finance, retail, and SaaS teams worldwide
        </motion.p>
      </div>
    </section>
  )
}
