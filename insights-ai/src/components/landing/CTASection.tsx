import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight } from 'lucide-react'

export default function CTASection() {
  return (
    <section className="bg-[#0A0A0A] py-24 px-6">
      <motion.div
        initial={{ opacity: 0, scale: 0.96 }}
        whileInView={{ opacity: 1, scale: 1 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6, ease: 'easeOut' }}
        className="max-w-2xl mx-auto text-center"
      >
        {/* Subtle glow */}
        <div
          className="absolute left-1/2 -translate-x-1/2 w-96 h-40 pointer-events-none"
          style={{ background: 'radial-gradient(ellipse, rgba(124,58,237,0.1) 0%, transparent 70%)' }}
        />

        <h2 className="text-4xl font-bold text-white mb-4 relative">
          Ready to talk to your data?
        </h2>
        <p className="text-[#A1A1AA] mb-10 relative">
          Join thousands using Insights.ai to make smarter decisions, faster.
        </p>

        <motion.div
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          className="relative inline-block"
        >
          <Link
            to="/login"
            className="inline-flex items-center gap-2 bg-gradient-to-r from-purple-600 to-pink-600 text-white font-medium px-10 py-4 rounded-full shadow-[0_0_40px_rgba(124,58,237,0.35)] hover:shadow-[0_0_60px_rgba(124,58,237,0.5)] transition-shadow duration-300 text-base"
          >
            Get started — It&apos;s free
            <ArrowRight className="w-4 h-4" />
          </Link>
        </motion.div>
      </motion.div>
    </section>
  )
}
