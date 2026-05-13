'use client'

/**
 * ApiKeyWarningBanner — shows dismissible alerts when API keys are missing
 * and the app is running on fallbacks (e.g. unauthenticated GitHub API,
 * Nitter instead of Twitter API, no AI keys at all).
 *
 * Fetched once on mount; re-checked when the user navigates to /settings
 * (via query invalidation).
 */

import React, { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import Link from 'next/link'
import { AlertTriangle, Info, X, Settings, AlertCircle } from 'lucide-react'
import { api } from '@/utils/api'

interface KeyWarning {
  key: string
  label: string
  severity: 'error' | 'warning' | 'info'
  message: string
}

export function ApiKeyWarningBanner() {
  const queryClient = useQueryClient()
  const [dismissed, setDismissed] = useState<Set<string>>(new Set())

  const { data } = useQuery({
    queryKey: ['ai-keys-warnings'],
    queryFn: () =>
      api.get('/users/ai-keys/').then(r => r.data as { warnings?: KeyWarning[] }),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  })

  const warnings = (data?.warnings ?? []).filter(w => !dismissed.has(w.key))

  if (warnings.length === 0) return null

  const severityStyles = {
    error: {
      bg: 'bg-red-50 dark:bg-red-950/30',
      border: 'border-red-300 dark:border-red-800/60',
      icon: 'text-red-500 dark:text-red-400',
      text: 'text-red-700 dark:text-red-300',
      btn: 'text-red-600 dark:text-red-400',
    },
    warning: {
      bg: 'bg-amber-50 dark:bg-amber-950/30',
      border: 'border-amber-300 dark:border-amber-800/60',
      icon: 'text-amber-500 dark:text-amber-400',
      text: 'text-amber-700 dark:text-amber-300',
      btn: 'text-amber-600 dark:text-amber-400',
    },
    info: {
      bg: 'bg-blue-50 dark:bg-blue-950/30',
      border: 'border-blue-300 dark:border-blue-800/60',
      icon: 'text-blue-500 dark:text-blue-400',
      text: 'text-blue-700 dark:text-blue-300',
      btn: 'text-blue-600 dark:text-blue-400',
    },
  }

  const SeverityIcon = {
    error: AlertCircle,
    warning: AlertTriangle,
    info: Info,
  }

  return (
    <div className="px-4 pt-3 space-y-2">
      {warnings.map(w => {
        const s = severityStyles[w.severity]
        const Icon = SeverityIcon[w.severity]
        return (
          <div
            key={w.key}
            className={`flex items-start gap-3 px-4 py-3 rounded-xl border ${s.bg} ${s.border}`}
          >
            <Icon size={18} className={`shrink-0 mt-0.5 ${s.icon}`} />
            <div className="flex-1 min-w-0">
              <p className={`text-sm font-medium ${s.text}`}>
                {w.label}
              </p>
              <p className={`text-xs mt-0.5 ${s.text} opacity-80`}>
                {w.message}
              </p>
              <Link
                href="/settings"
                className={`inline-flex items-center gap-1 text-xs font-medium mt-1.5 ${s.btn} hover:underline`}
                onClick={() => queryClient.invalidateQueries({ queryKey: ['ai-keys-warnings'] })}
              >
                <Settings size={11} /> Configure in Settings
              </Link>
            </div>
            <button
              onClick={() => setDismissed(prev => new Set(prev).add(w.key))}
              className={`shrink-0 p-1 rounded-lg hover:bg-black/5 dark:hover:bg-white/5 ${s.btn}`}
            >
              <X size={14} />
            </button>
          </div>
        )
      })}
    </div>
  )
}
