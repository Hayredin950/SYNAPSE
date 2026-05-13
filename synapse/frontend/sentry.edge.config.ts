/**
 * Sentry edge-runtime configuration — Next.js App Router (Edge runtime)
 *
 * TASK-204: Sentry error monitoring — frontend edge.
 *
 * This file runs in the Edge runtime (Middleware, Edge Route Handlers).
 * The Edge runtime is a restricted environment — only a subset of Web APIs
 * are available and no Node.js built-ins.
 */
import * as Sentry from '@sentry/nextjs'

const SENTRY_DSN = process.env.NEXT_PUBLIC_SENTRY_DSN

if (SENTRY_DSN) {
  Sentry.init({
    dsn: SENTRY_DSN,

    tracesSampleRate: parseFloat(
      process.env.NEXT_PUBLIC_SENTRY_TRACES_RATE ?? '0.1'
    ),

    environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT ?? 'production',

    sendDefaultPii: false,
  })
}
