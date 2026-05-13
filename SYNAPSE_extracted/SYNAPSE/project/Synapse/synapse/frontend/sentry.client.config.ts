/**
 * Sentry client-side configuration — Next.js App Router
 *
 * TASK-204: Sentry error monitoring — frontend.
 *
 * This file is loaded by Next.js in the browser. It initialises Sentry for
 * client-side error tracking, session replay, and performance monitoring.
 *
 * Best practices applied:
 *  ✓ DSN read from NEXT_PUBLIC_SENTRY_DSN env var (never hardcoded)
 *  ✓ Conditional init — no-ops silently when DSN is absent (dev/CI)
 *  ✓ Low sample rates in production — tune via env vars
 *  ✓ No PII sent (send_default_pii = false)
 *  ✓ integrations array kept minimal for bundle size
 */
import * as Sentry from '@sentry/nextjs'

const SENTRY_DSN = process.env.NEXT_PUBLIC_SENTRY_DSN

if (SENTRY_DSN) {
  Sentry.init({
    dsn: SENTRY_DSN,

    // Capture 10 % of transactions for performance monitoring.
    // Increase in production once baseline is established.
    tracesSampleRate: parseFloat(
      process.env.NEXT_PUBLIC_SENTRY_TRACES_RATE ?? '0.1'
    ),

    // Session replay: capture 1 % of all sessions, 10 % of error sessions.
    replaysSessionSampleRate: parseFloat(
      process.env.NEXT_PUBLIC_SENTRY_REPLAY_RATE ?? '0.01'
    ),
    replaysOnErrorSampleRate: parseFloat(
      process.env.NEXT_PUBLIC_SENTRY_REPLAY_ERROR_RATE ?? '0.1'
    ),

    integrations: [
      Sentry.replayIntegration({
        // Mask all text and block all media by default (privacy-first)
        maskAllText:   true,
        blockAllMedia: true,
      }),
    ],

    environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT ?? 'production',

    // Never send personally identifiable information
    sendDefaultPii: false,

    // Ignore common noisy errors that are not actionable
    ignoreErrors: [
      'ResizeObserver loop limit exceeded',
      'Non-Error promise rejection captured',
      /^Network Error$/,
      /^Request failed with status code 4/,
      /^Loading chunk \d+ failed/,
    ],
  })
}
