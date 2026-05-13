'use client'

/**
 * AnalyticsProvider — initialises PostHog and tracks page views.
 *
 * Phase 9.2 — Monitoring & Analytics
 *
 * Best practices:
 *  ✓ Dynamic import (PostHog not in critical bundle)
 *  ✓ Respects Do Not Track + user opt-out
 *  ✓ Tracks route changes in Next.js App Router
 *  ✓ Identifies users after login (no PII in events)
 *  ✓ Wrapped in Suspense for Next.js static prerendering
 */

import { Suspense, useEffect, useRef } from 'react'
import { usePathname, useSearchParams } from 'next/navigation'
import { initAnalytics, trackPageView, identifyUser } from '@/utils/analytics'
import { useAuthStore } from '@/store/authStore'

function AnalyticsInner() {
  const pathname     = usePathname()
  const searchParams = useSearchParams()
  const initialised  = useRef(false)
  const user         = useAuthStore((s) => s.user)

  // Initialise PostHog once
  useEffect(() => {
    if (!initialised.current) {
      initAnalytics()
      initialised.current = true
    }
  }, [])

  // Track page views on route change
  useEffect(() => {
    const url = pathname + (searchParams?.toString() ? `?${searchParams}` : '')
    trackPageView(url)
  }, [pathname, searchParams])

  // Identify user when they log in
  useEffect(() => {
    if (user?.id) {
      identifyUser(user.id, {
        plan:       user.role ?? 'user',
        role:       user.role ?? 'user',
        created_at: user.created_at,
      })
    }
  }, [user?.id])

  return null
}

export function AnalyticsProvider() {
  return (
    <Suspense fallback={null}>
      <AnalyticsInner />
    </Suspense>
  )
}

export default AnalyticsProvider
