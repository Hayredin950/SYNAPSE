/**
 * GoogleSignInButton
 * ~~~~~~~~~~~~~~~~~~
 * "Continue with Google" button using Google Identity Services (GSI).
 *
 * The free GSI flow is entirely frontend-driven:
 *   1. Load https://accounts.google.com/gsi/client (dynamic, no npm dep)
 *   2. Render the branded button with NEXT_PUBLIC_GOOGLE_CLIENT_ID
 *   3. On credential callback → POST the id_token to /auth/google/
 *   4. Store JWT tokens, refresh the user, route to /home (or /wizard if new)
 *
 * Requires NEXT_PUBLIC_GOOGLE_CLIENT_ID to be set (Vercel env var). When it's
 * missing the button renders a small disabled hint instead of a broken button.
 */
'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import toast from 'react-hot-toast'
import { Loader2 } from 'lucide-react'
import { useAuthStore } from '@/store/authStore'

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: Record<string, unknown>) => void
          renderButton: (el: HTMLElement, options: Record<string, unknown>) => void
        }
      }
    }
  }
}

export function GoogleSignInButton() {
  const router = useRouter()
  const buttonRef = useRef<HTMLDivElement>(null)
  const [status, setStatus] = useState<'loading' | 'ready' | 'missing' | 'error'>('loading')
  const { googleAuth } = useAuthStore()

  const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || ''

  useEffect(() => {
    if (!clientId) {
      setStatus('missing')
      return
    }

    let cancelled = false

    const render = () => {
      if (cancelled || !window.google?.accounts?.id || !buttonRef.current) return
      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: async (resp: { credential?: string }) => {
          const credential = resp?.credential
          if (!credential) {
            toast.error('Google sign-in was cancelled.')
            return
          }
          try {
            const user = await googleAuth(credential)
            toast.success('Welcome!')
            if (user?.is_onboarded) {
              router.replace('/home')
            } else {
              router.replace('/wizard')
            }
          } catch (err) {
            toast.error(err instanceof Error ? err.message : 'Google sign-in failed.')
          }
        },
      })
      window.google.accounts.id.renderButton(buttonRef.current, {
        type: 'standard',
        theme: 'outline',
        size: 'large',
        width: 380,
        text: 'continue_with',
        shape: 'pill',
      })
      if (!cancelled) setStatus('ready')
    }

    // Load GSI script if not already present
    if (window.google?.accounts?.id) {
      render()
      return () => { cancelled = true }
    }

    const script = document.createElement('script')
    script.src = 'https://accounts.google.com/gsi/client'
    script.async = true
    script.defer = true
    script.onload = render
    script.onerror = () => { if (!cancelled) setStatus('error') }
    document.head.appendChild(script)

    return () => {
      cancelled = true
      script.remove()
    }
  }, [clientId, googleAuth, router])

  if (status === 'missing') {
    return (
      <div className="w-full text-center text-xs text-slate-400 py-2 rounded-xl border border-dashed border-slate-300 dark:border-white/15">
        Google sign-in is not configured (set NEXT_PUBLIC_GOOGLE_CLIENT_ID)
      </div>
    )
  }

  if (status === 'error') {
    return (
      <div className="w-full text-center text-xs text-red-500 py-2 rounded-xl border border-dashed border-red-300 dark:border-red-500/30">
        Could not load Google sign-in. Please try again later.
      </div>
    )
  }

  return (
    <div className="w-full flex justify-center">
      {status === 'loading' ? (
        <div className="flex items-center justify-center gap-2 w-full py-3 rounded-xl text-sm text-slate-400">
          <Loader2 size={16} className="animate-spin" /> Loading Google sign-in…
        </div>
      ) : (
        <div ref={buttonRef} className="scale-90 origin-center" />
      )}
    </div>
  )
}
