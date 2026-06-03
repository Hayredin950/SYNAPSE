/**
 * SYNAPSE Service Worker — Phase 7.2 PWA
 *
 * Strategy: Network-first for all requests.
 * Vercel CDN handles caching — the SW only provides offline fallback.
 *
 * IMPORTANT: every code path inside `event.respondWith(...)` MUST resolve to
 * a valid Response object. Returning `undefined` (e.g. from a cache miss)
 * causes Chrome to throw `TypeError: Failed to convert value to 'Response'`.
 */

// Bumped from v2 → v3 to invalidate stale clients with the previous broken handler.
const CACHE_NAME = 'synapse-v3'
const OFFLINE_URL = '/offline'

// ── Install ────────────────────────────────────────────────────────────────────
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll([OFFLINE_URL]))
  )
  self.skipWaiting()
})

// ── Activate — delete ALL old caches ───────────────────────────────────────────
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      )
    )
  )
  self.clients.claim()
})

// ── Fetch — Network-first, with safe fallbacks (never returns undefined) ───────
self.addEventListener('fetch', (event) => {
  const { request } = event

  // Skip non-GET and cross-origin
  if (request.method !== 'GET') return
  const url = new URL(request.url)
  if (url.origin !== location.origin) return

  // Skip OAuth-adjacent routes — never want the SW to interfere with auth flows
  // (popups, callbacks, redirects). Let the browser handle these natively.
  if (
    url.pathname.startsWith('/api/v1/auth/') ||
    url.pathname.startsWith('/auth/') ||
    url.pathname.startsWith('/login') ||
    url.pathname.startsWith('/register')
  ) {
    return
  }

  // Navigation requests → network with offline fallback
  if (request.mode === 'navigate') {
    event.respondWith(handleNavigate(request))
    return
  }

  // All other same-origin GET → network-first
  event.respondWith(handleAsset(request))
})

// Always returns a valid Response — never undefined.
async function handleNavigate(request) {
  try {
    return await fetch(request)
  } catch (_) {
    const cached = await caches.match(OFFLINE_URL)
    return cached || new Response(
      '<!doctype html><title>Offline</title><h1>You are offline</h1>',
      { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
    )
  }
}

// Always returns a valid Response — never undefined.
async function handleAsset(request) {
  try {
    return await fetch(request)
  } catch (_) {
    const cached = await caches.match(request)
    return cached || new Response('', {
      status: 504,
      statusText: 'Gateway Timeout (offline)',
    })
  }
}
