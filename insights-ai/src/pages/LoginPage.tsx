import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Sparkles, ArrowRight, Mail, Lock, User } from 'lucide-react'
import { motion, useAnimation } from 'framer-motion'
import { login, signup } from '@/api/auth'
import { useSessionStore } from '@/stores/sessionStore'

type Mode = 'login' | 'signup'

function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2.5 group w-fit">
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
    </Link>
  )
}

interface FieldProps {
  icon: React.ReactNode
  type: string
  placeholder: string
  value: string
  onChange: (v: string) => void
  onKeyDown?: (e: React.KeyboardEvent<HTMLInputElement>) => void
  autoFocus?: boolean
  error?: boolean
}

function Field({ icon, type, placeholder, value, onChange, onKeyDown, autoFocus, error }: FieldProps) {
  return (
    <div
      className="rounded-xl p-[1px]"
      style={{
        background: error
          ? 'linear-gradient(135deg, #ef4444, #ef4444)'
          : 'linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%)',
      }}
    >
      <div className="flex items-center rounded-[11px] px-4 gap-3" style={{ background: '#0e0a1c' }}>
        <span className="text-[#4a4a5a] flex-shrink-0">{icon}</span>
        <input
          type={type}
          autoFocus={autoFocus}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={placeholder}
          className="w-full py-3 text-white text-sm placeholder:text-[#4a4a5a] outline-none bg-transparent"
        />
      </div>
    </div>
  )
}

export default function LoginPage() {
  const navigate         = useNavigate()
  const cardControls     = useAnimation()
  const refreshUserName  = useSessionStore((s) => s.refreshUserName)

  const [mode, setMode] = useState<Mode>('login')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errorMsg, setErrorMsg] = useState('')
  const [loading, setLoading] = useState(false)

  function clearErrors() {
    if (errorMsg) setErrorMsg('')
  }

  async function shakeCard() {
    await cardControls.start({
      x: [0, -8, 8, -8, 8, 0],
      transition: { duration: 0.4, ease: 'easeInOut' },
    })
  }

  async function handleSubmit() {
    setErrorMsg('')

    if (mode === 'signup' && !name.trim()) {
      setErrorMsg('Please enter your name.')
      shakeCard()
      return
    }
    if (!email.trim()) {
      setErrorMsg('Please enter your email.')
      shakeCard()
      return
    }
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(email.trim())) {
      setErrorMsg('Please enter a valid email address.')
      shakeCard()
      return
    }
    if (!password) {
      setErrorMsg('Please enter your password.')
      shakeCard()
      return
    }
    if (mode === 'signup' && password.length < 6) {
      setErrorMsg('Password must be at least 6 characters.')
      shakeCard()
      return
    }

    setLoading(true)
    try {
      let user
      if (mode === 'login') {
        user = await login(email.trim(), password)
      } else {
        user = await signup(name.trim(), email.trim(), password)
      }
      refreshUserName()
      navigate(user.is_admin ? '/admin' : '/app')
    } catch (err: unknown) {
      const msg = extractErrorMessage(err)
      setErrorMsg(msg)
      shakeCard()
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') handleSubmit()
  }

  function toggleMode() {
    setMode((m) => (m === 'login' ? 'signup' : 'login'))
    setErrorMsg('')
    setName('')
    setEmail('')
    setPassword('')
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
      className="min-h-screen flex flex-col relative overflow-hidden"
      style={{ background: '#080808' }}
    >
      {/* Grid pattern */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage:
            'linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px)',
          backgroundSize: '44px 44px',
        }}
      />

      {/* Purple/blue glow */}
      <div
        className="absolute pointer-events-none"
        style={{
          width: '700px',
          height: '700px',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          background:
            'radial-gradient(circle, rgba(88,28,235,0.28) 0%, rgba(59,130,246,0.14) 40%, transparent 70%)',
          filter: 'blur(70px)',
        }}
      />

      {/* Pink accent glow */}
      <div
        className="absolute pointer-events-none"
        style={{
          width: '420px',
          height: '420px',
          top: '55%',
          left: '58%',
          background:
            'radial-gradient(circle, rgba(236,72,153,0.22) 0%, transparent 68%)',
          filter: 'blur(60px)',
        }}
      />

      {/* Top-left logo */}
      <div className="relative z-10 p-6">
        <Logo />
      </div>

      {/* Centred card */}
      <div className="flex-1 flex items-center justify-center px-4 pb-12 relative z-10">
        <motion.div
          animate={cardControls}
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: 'easeOut' }}
          className="w-full max-w-[420px] rounded-2xl px-8 py-10"
          style={{
            background: 'rgba(12, 8, 24, 0.72)',
            backdropFilter: 'blur(24px)',
            WebkitBackdropFilter: 'blur(24px)',
            border: '1px solid rgba(255,255,255,0.07)',
            boxShadow: '0 0 70px rgba(88,28,235,0.18), 0 24px 64px rgba(0,0,0,0.55)',
          }}
        >
          {/* Icon */}
          <div className="flex justify-center mb-7">
            <div
              className="w-[60px] h-[60px] rounded-[18px] flex items-center justify-center"
              style={{
                background: 'linear-gradient(135deg, #7c3aed 0%, #3b82f6 100%)',
                boxShadow: '0 0 32px rgba(109,40,217,0.55)',
              }}
            >
              <Sparkles className="w-7 h-7 text-white" />
            </div>
          </div>

          {/* Title */}
          <h1 className="text-[1.6rem] font-bold text-white text-center leading-tight mb-2">
            {mode === 'login' ? 'Welcome back' : 'Create account'}
          </h1>
          <p className="text-[#71717a] text-sm text-center mb-8">
            {mode === 'login'
              ? 'Sign in to your Insights.ai account.'
              : 'Start analysing your data in seconds.'}
          </p>

          {/* Form fields */}
          <div className="flex flex-col gap-3">
            {mode === 'signup' && (
              <Field
                icon={<User size={15} />}
                type="text"
                placeholder="Your name"
                value={name}
                onChange={(v) => { setName(v); clearErrors() }}
                onKeyDown={handleKeyDown}
                autoFocus
                error={!!errorMsg && !name.trim()}
              />
            )}

            <Field
              icon={<Mail size={15} />}
              type="email"
              placeholder="Email address"
              value={email}
              onChange={(v) => { setEmail(v); clearErrors() }}
              onKeyDown={handleKeyDown}
              autoFocus={mode === 'login'}
              error={!!errorMsg && !email.trim()}
            />

            <Field
              icon={<Lock size={15} />}
              type="password"
              placeholder="Password"
              value={password}
              onChange={(v) => { setPassword(v); clearErrors() }}
              onKeyDown={handleKeyDown}
              error={!!errorMsg && !password}
            />
          </div>

          {/* Error message */}
          {errorMsg && (
            <motion.p
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
              className="text-red-400 text-xs mt-3 text-center"
            >
              {errorMsg}
            </motion.p>
          )}

          {/* Submit button */}
          <motion.button
            type="button"
            onClick={handleSubmit}
            disabled={loading}
            whileHover={{ scale: 1.015, opacity: 0.92 }}
            whileTap={{ scale: 0.97 }}
            className="w-full mt-5 py-3.5 rounded-xl text-white font-semibold text-sm flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
            style={{
              background: 'linear-gradient(to right, #6366f1, #7c3aed, #ec4899)',
              boxShadow: '0 4px 24px rgba(124,58,237,0.45)',
            }}
          >
            {loading
              ? mode === 'login' ? 'Signing in…' : 'Creating account…'
              : mode === 'login' ? 'Sign in' : 'Create account'}
            {!loading && <ArrowRight className="w-4 h-4" />}
          </motion.button>

          {/* Toggle mode */}
          <p className="text-[#52525b] text-xs text-center mt-5">
            {mode === 'login' ? "Don't have an account?" : 'Already have an account?'}{' '}
            <button
              type="button"
              onClick={toggleMode}
              className="text-purple-400 hover:text-purple-300 font-medium transition-colors cursor-pointer"
            >
              {mode === 'login' ? 'Sign up' : 'Sign in'}
            </button>
          </p>
        </motion.div>
      </div>
    </motion.div>
  )
}

// ── Error extraction helper ────────────────────────────────────────────────

function extractErrorMessage(err: unknown): string {
  if (err && typeof err === 'object' && 'response' in err) {
    const res = (err as { response?: { data?: { detail?: unknown } } }).response
    const detail = res?.data?.detail

    // Plain string detail (most API errors)
    if (typeof detail === 'string') return detail

    // Pydantic validation error array (e.g. invalid EmailStr)
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as Record<string, unknown>
      const loc = (first.loc as string[]) ?? []
      const field = loc[loc.length - 1] ?? ''
      if (field === 'email') return 'Please enter a valid email address.'
      if (field === 'name')  return 'Name is required.'
      if (field === 'password') return 'Please enter a valid password.'
      const msg = first.msg
      if (typeof msg === 'string') return msg
    }

    // Object-style detail with a message key
    if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
      const msg = (detail as Record<string, unknown>).message
      if (typeof msg === 'string') return msg
    }
  }
  return 'Something went wrong. Please try again.'
}
