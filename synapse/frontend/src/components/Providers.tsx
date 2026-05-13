'use client'

/**
 * Providers — global React context providers.
 *
 * Industry best practices:
 *  ✓ QueryClient created with useState (not module-level) → correct for Next.js App Router,
 *    prevents shared state between server renders and fixes HMR.
 *  ✓ Global error handling via QueryCache/MutationCache onError
 *  ✓ Optimised defaults: staleTime 5min, gcTime 10min, retry with exponential backoff
 *  ✓ Structural sharing avoids unnecessary re-renders when data hasn't changed
 */

import React, { useState } from 'react'
import { ThemeProvider } from 'next-themes'
import { UpgradeModalProvider } from '@/components/modals/UpgradeModal'
import { FocusModeProvider } from '@/components/ui/FocusMode'
import {
  QueryClient,
  QueryClientProvider,
  QueryCache,
  MutationCache,
} from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { Toaster } from 'react-hot-toast'
import toast from 'react-hot-toast'
import { normaliseApiError } from '@/utils/api'
import { AnalyticsProvider } from '@/components/AnalyticsProvider'

function makeQueryClient() {
  return new QueryClient({
    queryCache: new QueryCache({
      onError: (error, query) => {
        if (query.state.data !== undefined) {
          const { message } = normaliseApiError(error)
          toast.error(`Sync error: ${message}`, { id: 'bg-error', duration: 4000 })
        }
      },
    }),
    mutationCache: new MutationCache({
      onError: (error) => {
        const { message } = normaliseApiError(error)
        toast.error(message, { duration: 5000 })
      },
    }),
    defaultOptions: {
      queries: {
        staleTime: 5 * 60 * 1000,
        gcTime: 15 * 60 * 1000,
        retry: 1,
        retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 8_000),
        refetchOnWindowFocus: false,
        refetchOnReconnect: true,
        structuralSharing: true,
      },
      mutations: {
        retry: 0,
      },
    },
  })
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => makeQueryClient())

  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="system"
      enableSystem={true}
      disableTransitionOnChange={true}
      storageKey="synapse-theme"
    >
      <QueryClientProvider client={queryClient}>
        <UpgradeModalProvider>
          <AnalyticsProvider />

          {children}

          <Toaster
            position="top-right"
            gutter={8}
            toastOptions={{
              duration: 3500,
              style: {
                background: '#ffffff',
                color: '#0f172a',
                borderRadius: '12px',
                border: '1px solid #e2e8f0',
                fontSize: '13px',
                maxWidth: '380px',
                boxShadow: '0 4px 24px rgba(0,0,0,0.08)',
              },
              success: { iconTheme: { primary: '#22c55e', secondary: '#ffffff' } },
              error: { iconTheme: { primary: '#ef4444', secondary: '#ffffff' }, duration: 5000 },
            }}
          />

          <ReactQueryDevtools initialIsOpen={false} buttonPosition="bottom-left" />
        </UpgradeModalProvider>
      </QueryClientProvider>
    </ThemeProvider>
  )
}

export function ProvidersWithFocus({ children }: { children: React.ReactNode }) {
  return (
    <Providers>
      <FocusModeProvider>
        {children}
      </FocusModeProvider>
    </Providers>
  )
}
