'use client'

import { useEffect, useRef, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'

const CONTENT_LABELS: Record<string, string> = {
  articles: 'articles',
  repos:    'repositories',
  papers:   'papers',
  videos:   'videos',
  tweets:   'posts',
  trends:   'trends',
}

/**
 * Opens a persistent SSE connection to /api/v1/stream/ and:
 *  1. Toasts when new content arrives
 *  2. Invalidates the relevant TanStack Query keys so data refreshes automatically
 *
 * Reconnects with exponential back-off on error (max 30 s).
 */
export function useLiveContent() {
  const queryClient    = useQueryClient()
  const esRef          = useRef<EventSource | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>()
  const backoff        = useRef(3_000)

  const connect = useCallback(() => {
    if (typeof window === 'undefined') return

    const token = localStorage.getItem('synapse_access_token') ?? ''
    const url   = token
      ? `/api/v1/stream/?token=${encodeURIComponent(token)}`
      : '/api/v1/stream/'

    const es = new EventSource(url)
    esRef.current = es

    es.addEventListener('open', () => {
      backoff.current = 3_000  // reset on successful connection
    })

    es.addEventListener('content_update', (evt: MessageEvent) => {
      try {
        const { changed } = JSON.parse(evt.data) as {
          changed: Record<string, { current: number; previous: number; new: number }>
        }

        for (const [key, info] of Object.entries(changed)) {
          if (info.new <= 0) continue
          const label = CONTENT_LABELS[key] ?? key
          toast.success(`⚡ ${info.new} new ${label}!`, {
            id: `live-${key}`,
            duration: 5_000,
          })
        }

        // Invalidate queries so data auto-refreshes
        if (changed.articles) queryClient.invalidateQueries({ queryKey: ['articles'] })
        if (changed.repos)    queryClient.invalidateQueries({ queryKey: ['repos'] })
        if (changed.papers)   queryClient.invalidateQueries({ queryKey: ['papers'] })
        if (changed.videos)   queryClient.invalidateQueries({ queryKey: ['videos'] })
        if (changed.tweets)   queryClient.invalidateQueries({ queryKey: ['tweets'] })
        if (changed.trends)   queryClient.invalidateQueries({ queryKey: ['trends-strip'] })

        // Always refresh home stats
        queryClient.invalidateQueries({ queryKey: ['articles', 'home'] })
        queryClient.invalidateQueries({ queryKey: ['repos', 'home'] })
      } catch {
        // malformed payload — ignore
      }
    })

    es.onerror = () => {
      es.close()
      esRef.current = null
      // Exponential back-off, cap at 30 s
      backoff.current = Math.min(backoff.current * 1.5, 30_000)
      reconnectTimer.current = setTimeout(connect, backoff.current)
    }
  }, [queryClient])

  useEffect(() => {
    connect()
    return () => {
      esRef.current?.close()
      clearTimeout(reconnectTimer.current)
    }
  }, [connect])
}
