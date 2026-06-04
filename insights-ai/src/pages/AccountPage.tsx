/**
 * AccountPage.tsx
 * Change credentials page — name, email, password.
 *
 * Design matches LoginPage: dark glass card, purple/pink gradient glows,
 * gradient-border inputs, shake animation on error.
 *
 * Flow:
 *  1. User edits any subset of: name, email, new password.
 *  2. Current password is always required to authorise the change.
 *  3. On success the server invalidates the token; we clear local storage
 *     and navigate to /login with a success banner.
 */

import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Sparkles, ArrowLeft, ArrowRight,
  User, Mail, Lock, Eye, EyeOff,
  ShieldCheck, CheckCircle2,
} from 'lucide-react'
import { motion, useAnimation } from 'framer-motion'
import { getStoredUser } from '@/api/auth'
import { updateCredentials } from '@/api/auth'
import { useChatStore } from '@/stores/chatStore'
import { useSessionStore } from '@/stores/sessionStore'

// ---------------------------------------------------------------------------
// Reusable field component (same style as LoginPage)
// ---------------------------------------------------------------------------

interface FieldProps {
  icon:        React.ReactNode
  type:        string
  placeholder: string
  value:       string
  onChange:    (v: string) => void
  error?:      boolean
  disabled?:   boolean
  rightSlot?:  React.ReactNode
}

function Field({ icon, type, placeholder, value, onChange, error, disabled, rightSlot }: FieldProps) {
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
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          disabled={disabled}
          className="w-full py-3 text-white text-sm placeholder:text-[#4a4a5a] outline-none bg-transparent disabled:opacity-40 disabled:cursor-not-allowed flex-1"
        />
        {rightSlot}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Section label
// ---------------------------------------------------------------------------

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[11px] font-semibold text-[#52525b] uppercase tracking-widest mb-2 mt-5 first:mt-0">
      {children}
    </p>
  )
}

// ---------------------------------------------------------------------------
// AccountPage
// ---------------------------------------------------------------------------

export default function AccountPage() {
  const navigate      = useNavigate()
  const cardControls  = useAnimation()
  const resetSession  = useSessionStore((s) => s.resetSession)
  const clearChats    = useChatStore((s) => s.clearAllSessions)

  const currentUser   = getStoredUser()

  // Form state
  const [name,            setName]            = useState(currentUser?.name ?? '')
  const [email,           setEmail]           = useState(currentUser?.email ?? '')
  const [newPassword,     setNewPassword]     = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [currentPassword, setCurrentPassword] = useState('')
  const [showCurrent,     setShowCurrent]     = useState(false)
  const [showNew,         setShowNew]         = useState(false)
  const [showConfirm,     setShowConfirm]     = useState(false)

  const [errorMsg,  setErrorMsg]  = useState('')
  const [fieldErrs, setFieldErrs] = useState<Set<string>>(new Set())
  const [loading,   setLoading]   = useState(false)
  const [success,   setSuccess]   = useState(false)

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  async function shake() {
    await cardControls.start({
      x: [0, -8, 8, -8, 8, 0],
      transition: { duration: 0.4, ease: 'easeInOut' },
    })
  }

  function fail(msg: string, ...fields: string[]) {
    setErrorMsg(msg)
    setFieldErrs(new Set(fields))
    shake()
  }

  function isValidEmail(v: string) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim())
  }

  // ---------------------------------------------------------------------------
  // Submit
  // ---------------------------------------------------------------------------

  async function handleSubmit() {
    setErrorMsg('')
    setFieldErrs(new Set())

    // ── Validate ─────────────────────────────────────────────────────────────

    const trimName  = name.trim()
    const trimEmail = email.trim().toLowerCase()

    if (!trimName) {
      fail('Name cannot be empty.', 'name')
      return
    }

    if (!trimEmail) {
      fail('Email address cannot be empty.', 'email')
      return
    }

    if (!isValidEmail(trimEmail)) {
      fail('Please enter a valid email address.', 'email')
      return
    }

    if (newPassword && newPassword.length < 6) {
      fail('New password must be at least 6 characters.', 'new_password')
      return
    }

    if (newPassword && newPassword !== confirmPassword) {
      fail('New passwords do not match.', 'new_password', 'confirm_password')
      return
    }

    if (!currentPassword) {
      fail('Current password is required to save changes.', 'current_password')
      return
    }

    // Detect if anything actually changed
    const nameChanged     = trimName  !== (currentUser?.name ?? '')
    const emailChanged    = trimEmail !== (currentUser?.email ?? '')
    const passwordChanged = !!newPassword

    if (!nameChanged && !emailChanged && !passwordChanged) {
      fail('No changes detected — update at least one field.', '')
      return
    }

    // ── Submit ────────────────────────────────────────────────────────────────

    setLoading(true)
    try {
      await updateCredentials({
        current_password: currentPassword,
        name:         nameChanged     ? trimName  : undefined,
        email:        emailChanged    ? trimEmail : undefined,
        new_password: passwordChanged ? newPassword : undefined,
      })

      // Show brief success state, then log out and go to login
      setSuccess(true)
      clearChats()
      resetSession()

      setTimeout(() => {
        navigate('/login', { state: { credentialsUpdated: true } })
      }, 1800)
    } catch (err: unknown) {
      const msg = extractApiError(err)
      if (msg.toLowerCase().includes('current password')) {
        fail(msg, 'current_password')
      } else if (msg.toLowerCase().includes('email')) {
        fail(msg, 'email')
      } else {
        fail(msg)
      }
    } finally {
      setLoading(false)
    }
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

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

      {/* Purple glow */}
      <div
        className="absolute pointer-events-none"
        style={{
          width: '700px', height: '700px',
          top: '50%', left: '50%',
          transform: 'translate(-50%, -50%)',
          background: 'radial-gradient(circle, rgba(88,28,235,0.28) 0%, rgba(59,130,246,0.14) 40%, transparent 70%)',
          filter: 'blur(70px)',
        }}
      />

      {/* Pink accent */}
      <div
        className="absolute pointer-events-none"
        style={{
          width: '420px', height: '420px',
          top: '55%', left: '58%',
          background: 'radial-gradient(circle, rgba(236,72,153,0.22) 0%, transparent 68%)',
          filter: 'blur(60px)',
        }}
      />

      {/* Top bar */}
      <div className="relative z-10 p-6 flex items-center justify-between">
        {/* Logo */}
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

        {/* Back button */}
        <button
          onClick={() => navigate('/app')}
          className="flex items-center gap-1.5 text-[#71717a] hover:text-white text-sm transition-colors"
        >
          <ArrowLeft size={14} />
          Back to dashboard
        </button>
      </div>

      {/* Card */}
      <div className="flex-1 flex items-start justify-center px-4 pb-16 pt-4 relative z-10">
        <motion.div
          animate={cardControls}
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: 'easeOut' }}
          className="w-full max-w-[460px] rounded-2xl px-8 py-10"
          style={{
            background: 'rgba(12, 8, 24, 0.72)',
            backdropFilter: 'blur(24px)',
            WebkitBackdropFilter: 'blur(24px)',
            border: '1px solid rgba(255,255,255,0.07)',
            boxShadow: '0 0 70px rgba(88,28,235,0.18), 0 24px 64px rgba(0,0,0,0.55)',
          }}
        >
          {/* Success state */}
          {success ? (
            <motion.div
              initial={{ opacity: 0, scale: 0.92 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.4 }}
              className="flex flex-col items-center text-center py-4"
            >
              <div
                className="w-16 h-16 rounded-2xl flex items-center justify-center mb-5"
                style={{
                  background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                  boxShadow: '0 0 32px rgba(16,185,129,0.45)',
                }}
              >
                <CheckCircle2 className="w-8 h-8 text-white" />
              </div>
              <h2 className="text-xl font-bold text-white mb-2">Credentials updated!</h2>
              <p className="text-[#71717a] text-sm">
                Signing you out so you can log in with your new details…
              </p>
            </motion.div>
          ) : (
            <>
              {/* Icon + title */}
              <div className="flex justify-center mb-6">
                <div
                  className="w-[56px] h-[56px] rounded-[16px] flex items-center justify-center"
                  style={{
                    background: 'linear-gradient(135deg, #7c3aed 0%, #3b82f6 100%)',
                    boxShadow: '0 0 28px rgba(109,40,217,0.5)',
                  }}
                >
                  <ShieldCheck className="w-6 h-6 text-white" />
                </div>
              </div>

              <h1 className="text-[1.5rem] font-bold text-white text-center leading-tight mb-1">
                Account settings
              </h1>
              <p className="text-[#71717a] text-sm text-center mb-7">
                Update your name, email, or password below.
              </p>

              {/* ── Profile section ─────────────────────────────────────── */}
              <SectionLabel>Profile</SectionLabel>

              <div className="flex flex-col gap-3">
                <Field
                  icon={<User size={15} />}
                  type="text"
                  placeholder="Your name"
                  value={name}
                  onChange={(v) => { setName(v); setErrorMsg(''); setFieldErrs(new Set()) }}
                  error={fieldErrs.has('name')}
                  disabled={loading}
                />
                <Field
                  icon={<Mail size={15} />}
                  type="email"
                  placeholder="Email address"
                  value={email}
                  onChange={(v) => { setEmail(v); setErrorMsg(''); setFieldErrs(new Set()) }}
                  error={fieldErrs.has('email')}
                  disabled={loading}
                />
              </div>

              {/* ── New password section ─────────────────────────────────── */}
              <SectionLabel>New password <span className="normal-case text-[#3a3a4a]">(leave blank to keep current)</span></SectionLabel>

              <div className="flex flex-col gap-3">
                <Field
                  icon={<Lock size={15} />}
                  type={showNew ? 'text' : 'password'}
                  placeholder="New password"
                  value={newPassword}
                  onChange={(v) => { setNewPassword(v); setErrorMsg(''); setFieldErrs(new Set()) }}
                  error={fieldErrs.has('new_password')}
                  disabled={loading}
                  rightSlot={
                    <button
                      type="button"
                      tabIndex={-1}
                      onClick={() => setShowNew((s) => !s)}
                      className="text-[#4a4a5a] hover:text-white transition-colors flex-shrink-0"
                    >
                      {showNew ? <EyeOff size={14} /> : <Eye size={14} />}
                    </button>
                  }
                />
                <Field
                  icon={<Lock size={15} />}
                  type={showConfirm ? 'text' : 'password'}
                  placeholder="Confirm new password"
                  value={confirmPassword}
                  onChange={(v) => { setConfirmPassword(v); setErrorMsg(''); setFieldErrs(new Set()) }}
                  error={fieldErrs.has('confirm_password')}
                  disabled={loading}
                  rightSlot={
                    <button
                      type="button"
                      tabIndex={-1}
                      onClick={() => setShowConfirm((s) => !s)}
                      className="text-[#4a4a5a] hover:text-white transition-colors flex-shrink-0"
                    >
                      {showConfirm ? <EyeOff size={14} /> : <Eye size={14} />}
                    </button>
                  }
                />
              </div>

              {/* ── Authorisation section ───────────────────────────────── */}
              <SectionLabel>Confirm your identity</SectionLabel>

              <div
                className="rounded-xl p-3 mb-1 flex items-start gap-2.5"
                style={{ background: 'rgba(124,58,237,0.08)', border: '1px solid rgba(124,58,237,0.18)' }}
              >
                <ShieldCheck size={14} className="text-purple-400 mt-0.5 flex-shrink-0" />
                <p className="text-[11px] text-[#a1a1aa] leading-relaxed">
                  Enter your <span className="text-white font-medium">current password</span> to authorise any changes. You will be signed out and asked to log in again.
                </p>
              </div>

              <div className="mt-3">
                <Field
                  icon={<Lock size={15} />}
                  type={showCurrent ? 'text' : 'password'}
                  placeholder="Current password"
                  value={currentPassword}
                  onChange={(v) => { setCurrentPassword(v); setErrorMsg(''); setFieldErrs(new Set()) }}
                  error={fieldErrs.has('current_password')}
                  disabled={loading}
                  rightSlot={
                    <button
                      type="button"
                      tabIndex={-1}
                      onClick={() => setShowCurrent((s) => !s)}
                      className="text-[#4a4a5a] hover:text-white transition-colors flex-shrink-0"
                    >
                      {showCurrent ? <EyeOff size={14} /> : <Eye size={14} />}
                    </button>
                  }
                />
              </div>

              {/* Error */}
              {errorMsg && (
                <motion.p
                  key={errorMsg}
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2 }}
                  className="text-red-400 text-xs mt-3 text-center"
                >
                  {errorMsg}
                </motion.p>
              )}

              {/* Submit */}
              <motion.button
                type="button"
                onClick={handleSubmit}
                disabled={loading}
                whileHover={{ scale: 1.015, opacity: 0.92 }}
                whileTap={{ scale: 0.97 }}
                className="w-full mt-6 py-3.5 rounded-xl text-white font-semibold text-sm flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
                style={{
                  background: 'linear-gradient(to right, #6366f1, #7c3aed, #ec4899)',
                  boxShadow: '0 4px 24px rgba(124,58,237,0.45)',
                }}
              >
                {loading ? 'Saving changes…' : 'Save changes'}
                {!loading && <ArrowRight className="w-4 h-4" />}
              </motion.button>

              {/* Cancel */}
              <p className="text-[#52525b] text-xs text-center mt-4">
                Changed your mind?{' '}
                <button
                  type="button"
                  onClick={() => navigate('/app')}
                  className="text-purple-400 hover:text-purple-300 font-medium transition-colors cursor-pointer"
                >
                  Go back
                </button>
              </p>
            </>
          )}
        </motion.div>
      </div>
    </motion.div>
  )
}

// ---------------------------------------------------------------------------
// Error extractor (same pattern as LoginPage)
// ---------------------------------------------------------------------------

function extractApiError(err: unknown): string {
  if (err && typeof err === 'object' && 'response' in err) {
    const res = (err as { response?: { data?: { detail?: string } } }).response
    const detail = res?.data?.detail
    if (typeof detail === 'string') return detail
  }
  return 'Something went wrong. Please try again.'
}
