'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import toast from 'react-hot-toast'
import { Eye, EyeOff, Loader2, Mail, Lock, User, ArrowRight, AlertCircle } from 'lucide-react'
import { useAuthStore } from '@/store/authStore'

const registerSchema = z.object({
  username:         z.string().min(3, 'Username must be at least 3 characters'),
  email:            z.string().email('Invalid email address'),
  first_name:       z.string().min(1, 'First name is required'),
  last_name:        z.string().min(1, 'Last name is required'),
  password:         z.string().min(6, 'Password must be at least 6 characters'),
  confirm_password: z.string(),
}).refine(d => d.password === d.confirm_password, { message: 'Passwords do not match', path: ['confirm_password'] })

type RegisterFormData = z.infer<typeof registerSchema>

const inputClass = `auth-input w-full pl-10 pr-4 py-2.5 rounded-xl text-sm`
const labelClass = `block text-xs font-semibold uppercase tracking-wider mb-1.5 text-slate-500 dark:text-slate-400`
const iconClass  = `absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none transition-colors text-slate-400 group-focus-within:text-indigo-500 dark:text-slate-500 dark:group-focus-within:text-indigo-400`
const errClass   = `text-xs flex items-center gap-1 mt-1 text-red-500 dark:text-red-400`

export default function RegisterPage() {
  const router = useRouter()
  const { register: registerUser } = useAuthStore()
  const [isLoading, setIsLoading]   = useState(false)
  const [error, setError]           = useState<string | null>(null)
  const [showPassword, setShowPw]   = useState(false)
  const [showConfirm, setShowCf]    = useState(false)

  const { register, handleSubmit, formState: { errors } } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
  })

  const onSubmit = async (data: RegisterFormData) => {
    setIsLoading(true)
    setError(null)
    try {
      await registerUser({
        username: data.username, email: data.email,
        first_name: data.first_name, last_name: data.last_name,
        password: data.password, password2: data.confirm_password,
      })
      const { isAuthenticated } = useAuthStore.getState()
      if (isAuthenticated) {
        toast.success('Account created! Welcome to SYNAPSE')
        router.push('/wizard')
      } else {
        toast.success('Account created! Please check your email to verify your address')
        router.push('/verify-email')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create account')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-2xl font-black mb-1.5 tracking-tight text-slate-900 dark:text-white">Create your account</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400">Join SYNAPSE and explore AI-powered tech intelligence</p>
      </div>

      {error && (
        <div className="mb-5 flex items-start gap-3 p-4 rounded-xl bg-red-50 border border-red-200 dark:bg-red-500/10 dark:border-red-500/20">
          <AlertCircle size={16} className="text-red-500 dark:text-red-400 shrink-0 mt-0.5" />
          <p className="text-sm text-red-600 dark:text-red-400 leading-snug">{error}</p>
        </div>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelClass}>First Name</label>
            <div className="relative group"><User size={15} className={iconClass} />
              <input {...register('first_name')} type="text" placeholder="John" className={inputClass} />
            </div>
            {errors.first_name && <p className={errClass}><AlertCircle size={11} />{errors.first_name.message}</p>}
          </div>
          <div>
            <label className={labelClass}>Last Name</label>
            <div className="relative group"><User size={15} className={iconClass} />
              <input {...register('last_name')} type="text" placeholder="Doe" className={inputClass} />
            </div>
            {errors.last_name && <p className={errClass}><AlertCircle size={11} />{errors.last_name.message}</p>}
          </div>
        </div>

        <div>
          <label className={labelClass}>Username</label>
          <div className="relative group"><User size={15} className={iconClass} />
            <input {...register('username')} type="text" placeholder="johndoe" className={inputClass} />
          </div>
          {errors.username && <p className={errClass}><AlertCircle size={11} />{errors.username.message}</p>}
        </div>

        <div>
          <label className={labelClass}>Email address</label>
          <div className="relative group"><Mail size={15} className={iconClass} />
            <input {...register('email')} type="email" autoComplete="email" placeholder="you@example.com" className={inputClass} />
          </div>
          {errors.email && <p className={errClass}><AlertCircle size={11} />{errors.email.message}</p>}
        </div>

        <div>
          <label className={labelClass}>Password</label>
          <div className="relative group"><Lock size={15} className={iconClass} />
            <input {...register('password')} type={showPassword ? 'text' : 'password'} placeholder="Min 6 characters"
              className={`${inputClass} pr-11`} />
            <button type="button" onClick={() => setShowPw(!showPassword)}
              className="absolute right-3.5 top-1/2 -translate-y-1/2 transition-colors text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300">
              {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
            </button>
          </div>
          {errors.password && <p className={errClass}><AlertCircle size={11} />{errors.password.message}</p>}
        </div>

        <div>
          <label className={labelClass}>Confirm Password</label>
          <div className="relative group"><Lock size={15} className={iconClass} />
            <input {...register('confirm_password')} type={showConfirm ? 'text' : 'password'} placeholder="Confirm password"
              className={`${inputClass} pr-11`} />
            <button type="button" onClick={() => setShowCf(!showConfirm)}
              className="absolute right-3.5 top-1/2 -translate-y-1/2 transition-colors text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300">
              {showConfirm ? <EyeOff size={15} /> : <Eye size={15} />}
            </button>
          </div>
          {errors.confirm_password && <p className={errClass}><AlertCircle size={11} />{errors.confirm_password.message}</p>}
        </div>

        <div className="pt-1">
          <button type="submit" disabled={isLoading}
            className="relative w-full group overflow-hidden rounded-xl font-bold text-sm py-3.5 transition-all duration-200
              bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500
              disabled:opacity-60 disabled:cursor-not-allowed text-white
              shadow-lg shadow-indigo-500/25 hover:shadow-indigo-500/40 hover:scale-[1.01] active:scale-[0.99]
              flex items-center justify-center gap-2">
            <span className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-700" />
            {isLoading ? <><Loader2 size={16} className="animate-spin" /> Creating account…</> : <>Create Account <ArrowRight size={16} className="group-hover:translate-x-0.5 transition-transform" /></>}
          </button>
        </div>
      </form>

      <div className="flex items-center gap-3 my-5">
        <div className="flex-1 h-px bg-slate-200 dark:bg-white/15" />
        <span className="text-xs text-slate-400">or sign up with</span>
        <div className="flex-1 h-px bg-slate-200 dark:bg-white/15" />
      </div>

      <button
        type="button"
        onClick={() => window.location.href = '/api/v1/auth/github/'}
        className="flex items-center justify-center gap-3 w-full py-3 rounded-xl text-sm font-medium transition-all duration-200
          border border-slate-200 hover:border-slate-300 bg-white hover:bg-slate-50 text-slate-700
          dark:border-white/10 dark:hover:border-white/20 dark:bg-white/5 dark:hover:bg-white/10 dark:text-slate-200
          shadow-sm mb-2"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path d="M12 0C5.37 0 0 5.373 0 12c0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 21.795 24 17.298 24 12c0-6.627-5.373-12-12-12z"/>
        </svg>
        Continue with GitHub
      </button>

      <div className="flex items-center gap-3 my-4">
        <div className="flex-1 h-px bg-slate-200 dark:bg-white/15" />
        <span className="text-xs text-slate-400">Already have an account?</span>
        <div className="flex-1 h-px bg-slate-200 dark:bg-white/15" />
      </div>

      <Link href="/login"
        className="flex items-center justify-center gap-2 w-full py-3 rounded-xl text-sm font-medium transition-all duration-200
          border border-slate-200 hover:border-indigo-300 bg-white/50 hover:bg-indigo-50 text-slate-600 hover:text-indigo-700
          dark:border-white/10 dark:hover:border-white/20 dark:bg-white/5 dark:hover:bg-white/10 dark:text-slate-300 dark:hover:text-white">
        Sign in instead <ArrowRight size={14} className="text-slate-400 dark:text-slate-500" />
      </Link>
    </div>
  )
}
