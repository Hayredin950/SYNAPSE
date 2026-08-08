import { NextResponse } from 'next/server'

/**
 * GET /api/health
 *
 * Liveness probe for the Next.js container. The Dockerfile and compose
 * healthchecks hit this path — without it the frontend container is reported
 * unhealthy forever and dependent services never start.
 *
 * Deliberately does NOT check the backend: this answers "is this process
 * serving requests", not "is the whole system up". Coupling them would make
 * the frontend restart whenever the API had a blip.
 */
export const dynamic = 'force-dynamic'

export async function GET() {
  return NextResponse.json(
    {
      status: 'ok',
      service: 'synapse-frontend',
      timestamp: new Date().toISOString(),
    },
    { status: 200 },
  )
}
