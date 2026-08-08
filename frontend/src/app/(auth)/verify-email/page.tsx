'use client'

import React, { useState, useEffect, Suspense } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { Loader2, CheckCircle2, AlertCircle, Mail, ArrowRight, RefreshCw } from 'lucide-react'
import { authApi } from '@/utils/api'
import { useAuthStore } from '@/store/authStore'

function VerifyEmailContent() {
  const router      = useRouter()
  const params      = useSearchParams()
  const token       = params.get('token')
  const { setTokens, fetchUser } = useAuthStore()

  const [status, setStatus]   = useState<'loading' | 'success' | 'error' | 'pending'>('pending')
  const [message, setMessage] = useState('')
  const [resendEmail, setResendEmail]   = useState('')
  const [resendLoading, setResendLoading] = useState(false)
  const [resendDone, setResendDone]     = useState(false)

  useEffect(() => {
    if (token) {
      setStatus('loading')
      authApi.get(`/auth/verify-email/?token=${token}`)
        .then(async (res) => {
          const { tokens } = res.data
          if (tokens) {
            setTokens(tokens.access, tokens.refresh)
            await fetchUser()
          }
          setStatus('success')
          // Route new users to onboarding wizard; returning users go to /home
          const { user: currentUser } = useAuthStore.getState()
          const isOnboarded = (currentUser as any)?.is_onboarded ?? false
          setTimeout(() => router.push(isOnboarded ? '/home' : '/wizard'), 2500)
        })
        .catch((err) => {
          setMessage(err?.response?.data?.error || 'Invalid or expired verification link.')
          setStatus('error')
        })
    }
  }, [token])

  const handleResend = async () => {
    if (!resendEmail) return
    setResendLoading(true)
    try {
      await authApi.post('/auth/verify-email/resend/', { email: resendEmail })
      setResendDone(true)
    } finally {
      setResendLoading(false)
    }
  }

  // Token in URL — verifying
  if (token) {
    if (status === 'loading') return (
      <div className="text-center">
        <Loader2 size={40} className="animate-spin mx-auto mb-4 text-indigo-500 dark:text-indigo-400" />
        <h2 className="text-xl font-black text-slate-900 dark:text-white mb-2">Verifying your email…</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400">Just a moment please.</p>
      </div>
    )

    if (status === 'success') return (
      <div className="text-center">
        <div className="flex items-center justify-center w-14 h-14 rounded-2xl mx-auto mb-5
          bg-green-50 border border-green-200 dark:bg-green-500/10 dark:border-green-500/20">
          <CheckCircle2 size={28} className="text-green-500 dark:text-green-400" />
        </div>
        <h2 className="text-2xl font-black mb-2 tracking-tight text-slate-900 dark:text-white">Email verified! 🎉</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400 mb-2">Welcome to SYNAPSE. Redirecting you now…</p>
        <Loader2 size={16} className="animate-spin mx-auto text-indigo-400" />
      </div>
    )

    if (status === 'error') return (
      <div className="text-center">
        <div className="flex items-center justify-center w-14 h-14 rounded-2xl mx-auto mb-5
          bg-red-50 border border-red-200 dark:bg-red-500/10 dark:border-red-500/20">
          <AlertCircle size={28} className="text-red-500 dark:text-red-400" />
        </div>
        <h2 className="text-2xl font-black mb-2 text-slate-900 dark:text-white">Verification failed</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400 mb-8">{message}</p>
        <p className="text-xs text-slate-400 dark:text-slate-500 mb-4">Enter your email to get a new link:</p>
        <div className="flex gap-2">
          <input value={resendEmail} onChange={e => setResendEmail(e.target.value)}
            type="email" placeholder="you@example.com"
            className="auth-input flex-1 pl-3 pr-3 py-2.5 rounded-xl text-sm" />
          <button onClick={handleResend} disabled={resendLoading || !resendEmail}
            className="px-4 py-2.5 rounded-xl font-semibold text-sm text-white bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 transition-all">
            {resendLoading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          </button>
        </div>
        {resendDone && <p className="text-xs text-green-500 mt-3">New verification email sent!</p>}
      </div>
    )
  }

  // No token — "check your inbox" page (shown right after registration)
  return (
    <div className="text-center">
      <div className="flex items-center justify-center w-14 h-14 rounded-2xl mx-auto mb-5
        bg-indigo-50 border border-indigo-200 dark:bg-indigo-500/10 dark:border-indigo-500/20">
        <Mail size={28} className="text-indigo-600 dark:text-indigo-400" />
      </div>
      <h2 className="text-2xl font-black mb-2 tracking-tight text-slate-900 dark:text-white">Check your email</h2>
      <p className="text-sm text-slate-500 dark:text-slate-400 mb-6">
        We sent a verification link to your email address. Click it to activate your account.
      </p>
      <div className="p-4 rounded-xl mb-6
        bg-amber-50 border border-amber-200 dark:bg-amber-500/10 dark:border-amber-500/20">
        <p className="text-xs text-amber-700 dark:text-amber-400">
          Didn't get it? Check your spam folder or request a new link below.
        </p>
      </div>

      {resendDone ? (
        <p className="text-sm text-green-600 dark:text-green-400 font-medium mb-4">✓ New verification email sent!</p>
      ) : (
        <div className="space-y-3 mb-6">
          <input value={resendEmail} onChange={e => setResendEmail(e.target.value)}
            type="email" placeholder="your@email.com"
            className="auth-input w-full pl-4 pr-4 py-3 rounded-xl text-sm" />
          <button onClick={handleResend} disabled={resendLoading || !resendEmail}
            className="relative w-full group overflow-hidden rounded-xl font-bold text-sm py-3 transition-all duration-200
              bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500
              disabled:opacity-50 text-white flex items-center justify-center gap-2">
            {resendLoading ? <><Loader2 size={15} className="animate-spin" /> Sending…</> : <><RefreshCw size={15} /> Resend verification email</>}
          </button>
        </div>
      )}

      <Link href="/login"
        className="flex items-center justify-center gap-2 w-full py-3 rounded-xl text-sm font-medium transition-all
          border border-slate-200 hover:border-indigo-300 bg-white/50 hover:bg-indigo-50 text-slate-600 hover:text-indigo-700
          dark:border-white/10 dark:hover:border-white/20 dark:bg-white/5 dark:hover:bg-white/10 dark:text-slate-300 dark:hover:text-white">
        Back to Sign In <ArrowRight size={14} />
      </Link>
    </div>
  )
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center py-12">
        <Loader2 size={24} className="animate-spin text-indigo-500 dark:text-indigo-400" />
      </div>
    }>
      <VerifyEmailContent />
    </Suspense>
  )
}
