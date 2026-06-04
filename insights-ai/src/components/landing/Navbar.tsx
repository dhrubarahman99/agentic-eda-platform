import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Sparkles } from 'lucide-react'
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'

const navLinks = [
  { label: 'Features', href: '#features' },
  { label: 'How it works', href: '#how-it-works' },
  { label: 'Compare', href: '#compare' },
]

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 10)
    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  return (
    <motion.nav
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5, ease: 'easeOut' }}
      className={cn(
        'fixed top-0 left-0 right-0 z-50 border-b border-[#2A2A2A] transition-all duration-300',
        scrolled
          ? 'bg-[#0A0A0A]/95 backdrop-blur-xl shadow-[0_4px_24px_rgba(0,0,0,0.4)]'
          : 'bg-[#0A0A0A]/80 backdrop-blur-md'
      )}
    >
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2 group">
          <div className="w-8 h-8 rounded-lg bg-purple-600/20 flex items-center justify-center border border-purple-500/30 group-hover:border-purple-500/60 transition-colors">
            <Sparkles className="w-4 h-4 text-purple-400" />
          </div>
          <span className="font-bold text-white text-lg tracking-tight">
            Insights<span className="text-purple-400">.ai</span>
          </span>
        </Link>

        {/* Center nav links */}
        <div className="hidden md:flex items-center gap-8">
          {navLinks.map((link) => (
            <a
              key={link.label}
              href={link.href}
              className="text-[#A1A1AA] hover:text-white transition-colors duration-200 text-sm font-medium"
            >
              {link.label}
            </a>
          ))}
        </div>

        {/* Right actions */}
        <div className="flex items-center gap-4">
          <Link
            to="/login"
            className="text-[#A1A1AA] hover:text-white transition-colors duration-200 text-sm font-medium"
          >
            Login
          </Link>
          <motion.div whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}>
            <Link
              to="/login"
              className="bg-purple-600 hover:bg-purple-700 text-white text-sm font-medium px-5 py-2 rounded-full transition-colors duration-200"
            >
              Get Started
            </Link>
          </motion.div>
        </div>
      </div>
    </motion.nav>
  )
}
