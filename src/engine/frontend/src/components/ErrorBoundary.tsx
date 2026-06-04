'use client'

/**
 * ErrorBoundary — Graceful error UI for failed API calls and runtime errors.
 *
 * Phase 7.2 — Mobile & Performance (Week 20)
 *
 * Usage:
 *   <ErrorBoundary>
 *     <YourComponent />
 *   </ErrorBoundary>
 */

import React, { Component, ErrorInfo, ReactNode } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

interface Props {
  children:   ReactNode
  fallback?:  ReactNode
  onReset?:   () => void
}

interface State {
  hasError: boolean
  error:    Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // In production, send to Sentry here
    console.error('[ErrorBoundary]', error, info.componentStack)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
    this.props.onReset?.()
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback

      return (
        <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
          <div className="w-14 h-14 rounded-2xl bg-red-50 dark:bg-red-900/20 flex items-center justify-center mb-4">
            <AlertTriangle className="w-7 h-7 text-red-500" />
          </div>
          <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-1">
            Something went wrong
          </h3>
          <p className="text-sm text-slate-500 dark:text-slate-400 mb-5 max-w-sm">
            {this.state.error?.message ?? 'An unexpected error occurred. Please try again.'}
          </p>
          <button
            onClick={this.handleReset}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium transition-colors"
          >
            <RefreshCw size={15} />
            Try again
          </button>
        </div>
      )
    }

    return this.props.children
  }
}

// ── Functional wrapper with query error support ────────────────────────────────

interface QueryErrorProps {
  error?:     Error | null
  onRetry?:   () => void
  message?:   string
  className?: string
}

export function QueryError({ error, onRetry, message, className }: QueryErrorProps) {
  if (!error) return null
  return (
    <div className={`flex flex-col items-center justify-center py-12 px-6 text-center ${className ?? ''}`}>
      <div className="w-12 h-12 rounded-2xl bg-red-50 dark:bg-red-900/20 flex items-center justify-center mb-3">
        <AlertTriangle className="w-6 h-6 text-red-500" />
      </div>
      <p className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
        {message ?? 'Failed to load data'}
      </p>
      <p className="text-xs text-slate-400 mb-4">{error.message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-medium transition-colors"
        >
          <RefreshCw size={12} />
          Retry
        </button>
      )}
    </div>
  )
}

export default ErrorBoundary
