/**
 * analytics.ts — PostHog client-side analytics (privacy-first).
 *
 * Phase 9.2 — Monitoring & Analytics
 *
 * Industry best practices:
 *  ✓ Lazy initialisation (only loads PostHog when user has consented / not opted out)
 *  ✓ Respects Do Not Track header
 *  ✓ No PII in event properties (email/name excluded)
 *  ✓ Type-safe event names and properties
 *  ✓ Server-side rendering safe (window checks)
 */

// ── Types ──────────────────────────────────────────────────────────────────────

type EventName =
  | 'page_viewed'
  | 'search_performed'
  | 'article_viewed'
  | 'paper_viewed'
  | 'repo_viewed'
  | 'video_viewed'
  | 'bookmark_toggled'
  | 'ai_chat_sent'
  | 'agent_task_submitted'
  | 'document_generated'
  | 'automation_created'
  | 'automation_triggered'
  | 'drive_connected'
  | 'drive_upload_clicked'
  | 's3_upload_clicked'
  | 'mfa_setup_started'
  | 'mfa_enabled'
  | 'signup_started'
  | 'signup_completed'
  | 'login_completed'

type EventProperties = Record<string, string | number | boolean | null | undefined>

// ── Config ─────────────────────────────────────────────────────────────────────

const POSTHOG_KEY  = process.env.NEXT_PUBLIC_POSTHOG_KEY  || ''
const POSTHOG_HOST = process.env.NEXT_PUBLIC_POSTHOG_HOST || 'https://app.posthog.com'

// ── Initialisation ─────────────────────────────────────────────────────────────

let _initialised = false

function shouldTrack(): boolean {
  if (typeof window === 'undefined') return false
  if (!POSTHOG_KEY) return false
  // Respect Do Not Track
  if (navigator.doNotTrack === '1') return false
  // Respect user opt-out stored in localStorage
  if (localStorage.getItem('analytics_optout') === 'true') return false
  return true
}

export async function initAnalytics(): Promise<void> {
  if (_initialised || !shouldTrack()) return

  try {
    const posthog = (await import('posthog-js')).default
    posthog.init(POSTHOG_KEY, {
      api_host:                  POSTHOG_HOST,
      capture_pageview:          false,   // manual page view tracking
      capture_pageleave:         true,
      autocapture:               false,   // privacy-first: no auto-capture
      disable_session_recording: true,    // opt-in only
      persistence:               'localStorage',
      opt_out_capturing_by_default: false,
      sanitize_properties: (properties: Record<string, unknown>) => {
        // Remove any accidental PII
        const safe = { ...properties }
        delete safe['email']
        delete safe['name']
        delete safe['phone']
        return safe
      },
    })
    _initialised = true
  } catch (err) {
    console.warn('[Analytics] PostHog init failed:', err)
  }
}

// ── Core tracking functions ────────────────────────────────────────────────────

export function track(event: EventName, properties?: EventProperties): void {
  if (!shouldTrack()) return
  try {
    // Dynamic import to avoid SSR issues
    import('posthog-js').then(({ default: posthog }) => {
      posthog.capture(event, properties)
    }).catch((err) => {
      console.warn('[Analytics] track() failed to load posthog-js:', err)
    })
  } catch (err) {
    console.warn('[Analytics] track() error:', err)
  }
}

export function identifyUser(userId: string, properties?: {
  plan?: string
  role?: string
  created_at?: string
}): void {
  if (!shouldTrack()) return
  try {
    import('posthog-js').then(({ default: posthog }) => {
      posthog.identify(userId, properties)
    }).catch((err) => {
      console.warn('[Analytics] identifyUser() failed to load posthog-js:', err)
    })
  } catch (err) {
    console.warn('[Analytics] identifyUser() error:', err)
  }
}

export function resetUser(): void {
  if (!shouldTrack()) return
  try {
    import('posthog-js').then(({ default: posthog }) => {
      posthog.reset()
    }).catch((err) => {
      console.warn('[Analytics] resetUser() failed to load posthog-js:', err)
    })
  } catch (err) {
    console.warn('[Analytics] resetUser() error:', err)
  }
}

export function optOut(): void {
  if (typeof window === 'undefined') return
  localStorage.setItem('analytics_optout', 'true')
  try {
    import('posthog-js').then(({ default: posthog }) => {
      posthog.opt_out_capturing()
    }).catch((err) => {
      console.warn('[Analytics] optOut() failed to load posthog-js:', err)
    })
  } catch (err) {
    console.warn('[Analytics] optOut() error:', err)
  }
}

export function optIn(): void {
  if (typeof window === 'undefined') return
  localStorage.removeItem('analytics_optout')
  try {
    import('posthog-js').then(({ default: posthog }) => {
      posthog.opt_in_capturing()
    }).catch((err) => {
      console.warn('[Analytics] optIn() failed to load posthog-js:', err)
    })
  } catch (err) {
    console.warn('[Analytics] optIn() error:', err)
  }
}

// ── Page view tracking hook helper ─────────────────────────────────────────────

export function trackPageView(path: string): void {
  track('page_viewed', { path, url: typeof window !== 'undefined' ? window.location.href : path })
}

// ── Typed event helpers ────────────────────────────────────────────────────────

export const Analytics = {
  search:     (query: string, type: 'keyword' | 'semantic', results: number) =>
    track('search_performed', { query: query.slice(0, 100), type, results }),

  articleView: (id: string, source: string) =>
    track('article_viewed', { article_id: id, source }),

  paperView:   (id: string) =>
    track('paper_viewed', { paper_id: id }),

  repoView:    (id: string) =>
    track('repo_viewed', { repo_id: id }),

  videoView:   (id: string) =>
    track('video_viewed', { video_id: id }),

  bookmark:    (contentType: string, action: 'add' | 'remove') =>
    track('bookmark_toggled', { content_type: contentType, action }),

  aiChat:      (messageLength: number) =>
    track('ai_chat_sent', { message_length: messageLength }),

  agentTask:   (taskLength: number) =>
    track('agent_task_submitted', { task_length: taskLength }),

  docGenerate: (docType: string) =>
    track('document_generated', { doc_type: docType }),

  driveUpload: () =>
    track('drive_upload_clicked'),

  s3Upload:    () =>
    track('s3_upload_clicked'),

  mfaSetup:    () =>
    track('mfa_setup_started'),

  mfaEnabled:  () =>
    track('mfa_enabled'),
}
