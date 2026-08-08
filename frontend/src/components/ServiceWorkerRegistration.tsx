'use client'

/**
 * ServiceWorkerRegistration — registers the PWA service worker.
 * Drop into RootLayout (client-side only, no SSR).
 *
 * Phase 7.2 — PWA (Week 20)
 */

import { useEffect } from 'react'

export function ServiceWorkerRegistration() {
  useEffect(() => {
    if ('serviceWorker' in navigator && process.env.NODE_ENV === 'production') {
      navigator.serviceWorker
        .register('/sw.js', { scope: '/' })
        .then((reg) => {
          console.log('[SW] Registered:', reg.scope)
        })
        .catch((err) => {
          console.warn('[SW] Registration failed:', err)
        })
    }
  }, [])

  return null
}

export default ServiceWorkerRegistration
