'use client'

import { useEffect } from 'react'
import { AlertTriangle, RefreshCw, Home } from 'lucide-react'
import Link from 'next/link'

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error('[v0] Dashboard error:', error)
  }, [error])

  return (
    <div className="flex-1 flex items-center justify-center bg-slate-50 dark:bg-slate-950 p-8">
      <div className="max-w-md w-full text-center">
        <div className="mx-auto w-16 h-16 rounded-2xl bg-red-500/10 flex items-center justify-center mb-6">
          <AlertTriangle className="w-8 h-8 text-red-500" />
        </div>
        <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-2">
          Something went wrong
        </h2>
        <p className="text-slate-500 dark:text-slate-400 mb-6">
          An unexpected error occurred. This is often temporary — try refreshing.
        </p>
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <button
            onClick={() => reset()}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Try again
          </button>
          <Link
            href="/home"
            className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-900 dark:text-white font-medium transition-colors"
          >
            <Home className="w-4 h-4" />
            Go home
          </Link>
        </div>
        {error.message && (
          <details className="mt-6 text-left">
            <summary className="text-xs text-slate-400 cursor-pointer hover:text-slate-500">
              Technical details
            </summary>
            <p className="mt-2 text-xs text-slate-400 dark:text-slate-500 font-mono break-all bg-slate-100 dark:bg-slate-900 p-3 rounded-lg">
              {error.message.slice(0, 500)}
            </p>
          </details>
        )}
      </div>
    </div>
  )
}
