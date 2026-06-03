/**
 * Sentry server-side configuration — Next.js App Router (Node.js runtime)
 *
 * TASK-204: Sentry error monitoring — frontend server.
 *
 * This file runs in the Node.js runtime for Server Components, Route Handlers,
 * and Middleware. Keep it lightweight — no browser APIs available here.
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
