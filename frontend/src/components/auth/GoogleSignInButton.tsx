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
  // The container div is ALWAYS mounted (even while loading) so the ref is
  // available the moment the GSI script finishes loading — rendering the
  // button into a not-yet-mounted node was the "stuck loading" bug.
  const buttonRef = useRef<HTMLDivElement>(null)
  const [status, setStatus] = useState<'loading' | 'ready' | 'missing' | 'error'>('loading')
  const { googleAuth } = useAuthStore()

  const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || ''

  // ── Step 1: load GSI script + initialize (one-time) ─────────────────────────
  useEffect(() => {
    if (!clientId) {
      setStatus('missing')
      return
    }

    let cancelled = false

    const init = () => {
      if (cancelled || !window.google?.accounts?.id) return
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
      if (!cancelled) setStatus('ready')
    }

    if (window.google?.accounts?.id) {
      init()
      return () => { cancelled = true }
    }

    // Fail visibly if the GSI script can't load within a reasonable window
    // (ad-blockers, strict networks, or Google being unreachable). A silently
    // dropped connection may never fire onload OR onerror, which would leave
    // the button on "Loading Google sign-in…" forever.
    const timeout = window.setTimeout(() => {
      if (!cancelled && !window.google?.accounts?.id) setStatus('error')
    }, 8000)

    const script = document.createElement('script')
    script.src = 'https://accounts.google.com/gsi/client'
    script.async = true
    script.defer = true
    script.onload = () => { window.clearTimeout(timeout); init() }
    script.onerror = () => { window.clearTimeout(timeout); if (!cancelled) setStatus('error') }
    document.head.appendChild(script)

    return () => {
      cancelled = true
      window.clearTimeout(timeout)
      script.remove()
    }
  }, [clientId, googleAuth, router])

  // ── Step 2: render the branded button once both script + DOM are ready ──────
  useEffect(() => {
    if (status !== 'ready' || !buttonRef.current || !window.google?.accounts?.id) return
    try {
      // Match the container width so it works on mobile and desktop.
      const width = Math.max(buttonRef.current.clientWidth, 300)
      window.google.accounts.id.renderButton(buttonRef.current, {
        type: 'standard',
        theme: 'outline',
        size: 'large',
        width,
        text: 'continue_with',
        shape: 'pill',
      })
    } catch {
      // e.g. the origin is not in the Google client's authorized JS origins
      setStatus('error')
    }
  }, [status])

  return (
    <div className="w-full flex justify-center">
      <div
        ref={buttonRef}
        className="w-full min-h-[44px] flex items-center justify-center"
      >
        {status === 'loading' && (
          <div className="flex items-center justify-center gap-2 w-full py-3 rounded-xl text-sm text-slate-400">
            <Loader2 size={16} className="animate-spin" /> Loading Google sign-in…
          </div>
        )}
        {status === 'missing' && (
          <div className="w-full text-center text-xs text-slate-400 py-2 rounded-xl border border-dashed border-slate-300 dark:border-white/15">
            Google sign-in is not configured (set NEXT_PUBLIC_GOOGLE_CLIENT_ID)
          </div>
        )}
        {status === 'error' && (
          <div className="w-full text-center text-xs text-red-500 py-2 rounded-xl border border-dashed border-red-300 dark:border-red-500/30">
            Could not load Google sign-in. Please try again later.
          </div>
        )}
      </div>
    </div>
  )
}
