'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Mail, ArrowLeft, ArrowRight, Loader2, AlertCircle, CheckCircle2 } from 'lucide-react'
import { authApi } from '@/utils/api'

const schema = z.object({ email: z.string().email('Invalid email address') })
type FormData = z.infer<typeof schema>

export default function ForgotPasswordPage() {
  const [isLoading, setIsLoading] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [error, setError]         = useState<string | null>(null)

  const { register, handleSubmit, formState: { errors }, getValues } = useForm<FormData>({
    resolver: zodResolver(schema),
  })

  const onSubmit = async (data: FormData) => {
    setIsLoading(true)
    setError(null)
    try {
      await authApi.post('/auth/password-reset/', { email: data.email })
      setSubmitted(true)
    } catch {
      setError('Something went wrong. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  if (submitted) {
    return (
      <div className="text-center">
        <div className="flex items-center justify-center w-14 h-14 rounded-2xl mx-auto mb-5
          bg-green-50 border border-green-200 dark:bg-green-500/10 dark:border-green-500/20">
          <CheckCircle2 size={28} className="text-green-500 dark:text-green-400" />
        </div>
        <h2 className="text-2xl font-black mb-2 tracking-tight text-slate-900 dark:text-white">Check your inbox</h2>
        <p className="text-sm mb-2 text-slate-500 dark:text-slate-400">We sent a password reset link to</p>
        <p className="font-semibold text-sm mb-6 text-indigo-600 dark:text-indigo-400">{getValues('email')}</p>
        <p className="text-xs mb-8 text-slate-400 dark:text-slate-500">
          Didn't get it? Check your spam folder or wait a few minutes. The link expires in 1 hour.
        </p>
        <Link href="/login"
          className="flex items-center justify-center gap-2 w-full py-3 rounded-xl text-sm font-medium transition-all duration-200
            border border-slate-200 hover:border-indigo-300 bg-white/50 hover:bg-indigo-50 text-slate-600 hover:text-indigo-700
            dark:border-white/10 dark:hover:border-white/20 dark:bg-white/5 dark:hover:bg-white/10 dark:text-slate-300 dark:hover:text-white">
          <ArrowLeft size={14} /> Back to Sign In
        </Link>
      </div>
    )
  }

  return (
    <div>
      <div className="mb-8">
        <div className="flex items-center justify-center w-12 h-12 rounded-2xl mb-5 mx-auto
          bg-indigo-50 border border-indigo-200 dark:bg-indigo-500/10 dark:border-indigo-500/20">
          <Mail size={22} className="text-indigo-600 dark:text-indigo-400" />
        </div>
        <h2 className="text-2xl font-black mb-1.5 tracking-tight text-center text-slate-900 dark:text-white">Forgot password?</h2>
        <p className="text-sm text-center text-slate-500 dark:text-slate-400">
          Enter your email and we'll send you a reset link
        </p>
      </div>

      {error && (
        <div className="mb-6 flex items-start gap-3 p-4 rounded-xl bg-red-50 border border-red-200 dark:bg-red-500/10 dark:border-red-500/20">
          <AlertCircle size={16} className="text-red-500 dark:text-red-400 shrink-0 mt-0.5" />
          <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
        </div>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
        <div className="space-y-1.5">
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            Email address
          </label>
          <div className="relative group">
            <Mail size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none transition-colors
              text-slate-400 group-focus-within:text-indigo-500 dark:text-slate-500 dark:group-focus-within:text-indigo-400" />
            <input {...register('email')} type="email" autoComplete="email" placeholder="you@example.com"
              className="auth-input w-full pl-10 pr-4 py-3 rounded-xl text-sm" />
          </div>
          {errors.email && <p className="text-xs flex items-center gap-1 mt-1 text-red-500 dark:text-red-400"><AlertCircle size={11} />{errors.email.message}</p>}
        </div>

        <button type="submit" disabled={isLoading}
          className="relative w-full group overflow-hidden rounded-xl font-bold text-sm py-3.5 transition-all duration-200
            bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500
            disabled:opacity-60 disabled:cursor-not-allowed text-white
            shadow-lg shadow-indigo-500/25 hover:shadow-indigo-500/40 hover:scale-[1.01] active:scale-[0.99]
            flex items-center justify-center gap-2">
          <span className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-700" />
          {isLoading ? <><Loader2 size={16} className="animate-spin" /> Sending…</> : <>Send Reset Link <ArrowRight size={16} className="group-hover:translate-x-0.5 transition-transform" /></>}
        </button>
      </form>

      <div className="flex items-center gap-3 my-6">
        <div className="flex-1 h-px bg-slate-200 dark:bg-white/15" />
        <span className="text-xs text-slate-400 dark:text-slate-400">Remember it?</span>
        <div className="flex-1 h-px bg-slate-200 dark:bg-white/15" />
      </div>

      <Link href="/login"
        className="flex items-center justify-center gap-2 w-full py-3 rounded-xl text-sm font-medium transition-all duration-200
          border border-slate-200 hover:border-indigo-300 bg-white/50 hover:bg-indigo-50 text-slate-600 hover:text-indigo-700
          dark:border-white/10 dark:hover:border-white/20 dark:bg-white/5 dark:hover:bg-white/10 dark:text-slate-300 dark:hover:text-white">
        <ArrowLeft size={14} /> Back to Sign In
      </Link>
    </div>
  )
}
