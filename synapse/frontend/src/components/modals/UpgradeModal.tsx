'use client'

/**
 * UpgradeModal — shown when user hits a plan limit (403 plan_limit_exceeded).
 * TASK-003-F3
 *
 * Usage:
 *   const { openUpgradeModal } = useUpgradeModal()
 *   openUpgradeModal({ resource: 'ai_queries', used: 50, limit: 50, plan: 'free' })
 */

import React, { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/utils/api'
import toast from 'react-hot-toast'
import {
  Zap,
  X,
  Check,
  ArrowUpRight,
  Loader2,
} from 'lucide-react'

// ── Types ─────────────────────────────────────────────────────────────────────

export interface UpgradeContext {
  resource?: string
  used?: number
  limit?: number
  plan?: string
  message?: string
}

interface UpgradeModalContextValue {
  openUpgradeModal: (ctx?: UpgradeContext) => void
  closeUpgradeModal: () => void
}

// ── Context ───────────────────────────────────────────────────────────────────

const UpgradeModalContext = createContext<UpgradeModalContextValue>({
  openUpgradeModal:  () => {},
  closeUpgradeModal: () => {},
})

export function useUpgradeModal() {
  return useContext(UpgradeModalContext)
}

// ── Resource labels ────────────────────────────────────────────────────────────

const RESOURCE_LABELS: Record<string, string> = {
  ai_queries:  'AI queries',
  agent_runs:  'agent runs',
  automations: 'automation workflows',
  documents:   'document generations',
  bookmarks:   'bookmarks',
}

const PRO_HIGHLIGHTS = [
  'Unlimited AI queries',
  'Unlimited document generations',
  'Unlimited automation workflows',
  'Semantic search',
  'Google Drive + S3 integration',
  'Priority support',
]

// ── Modal UI ──────────────────────────────────────────────────────────────────

function UpgradeModalUI({
  ctx,
  onClose,
}: {
  ctx: UpgradeContext
  onClose: () => void
}) {
  const router = useRouter()
  const [loading, setLoading] = useState(false)

  const resourceLabel = ctx.resource
    ? RESOURCE_LABELS[ctx.resource] ?? ctx.resource.replace(/_/g, ' ')
    : 'this feature'

  const handleUpgrade = async () => {
    setLoading(true)
    try {
      const { data } = await api.post('/billing/checkout/', { plan: 'pro' })
      window.location.href = data.checkout_url
    } catch {
      toast.error('Could not start checkout. Please try again.')
      setLoading(false)
    }
  }

  const handleViewPlans = () => {
    onClose()
    router.push('/pricing')
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div
          className="pointer-events-auto w-full max-w-md bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-700 overflow-hidden"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Top gradient bar */}
          <div className="h-1 bg-gradient-to-r from-indigo-500 via-violet-500 to-cyan-500" />

          <div className="p-6">
            {/* Header */}
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-indigo-100 dark:bg-indigo-900/40 text-indigo-600 dark:text-indigo-400">
                  <Zap size={20} />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-slate-900 dark:text-white">Upgrade to Pro</h2>
                  <p className="text-sm text-slate-500 dark:text-slate-400">Unlock unlimited access</p>
                </div>
              </div>
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              >
                <X size={16} />
              </button>
            </div>

            {/* Limit hit message */}
            <div className="p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800/40 rounded-xl mb-5">
              <p className="text-sm text-amber-800 dark:text-amber-300 font-medium">
                {ctx.message ?? (
                  ctx.limit
                    ? `You've used ${ctx.used ?? ctx.limit}/${ctx.limit} ${resourceLabel} on the Free plan.`
                    : `You've reached the Free plan limit for ${resourceLabel}.`
                )}
              </p>
            </div>

            {/* Pro highlights */}
            <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-3">
              Pro includes
            </p>
            <ul className="space-y-2 mb-6">
              {PRO_HIGHLIGHTS.map((feat) => (
                <li key={feat} className="flex items-center gap-2.5">
                  <Check size={14} className="text-emerald-500 flex-shrink-0" />
                  <span className="text-sm text-slate-700 dark:text-slate-200">{feat}</span>
                </li>
              ))}
            </ul>

            {/* Price */}
            <div className="flex items-baseline gap-1 mb-5">
              <span className="text-3xl font-black text-slate-900 dark:text-white">$19</span>
              <span className="text-slate-400 text-sm">/month</span>
              <span className="ml-2 px-2 py-0.5 bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 text-xs rounded-full font-semibold">
                14-day free trial
              </span>
            </div>

            {/* CTA */}
            <div className="flex gap-2">
              <button
                onClick={handleUpgrade}
                disabled={loading}
                className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-bold rounded-xl transition-colors shadow-lg shadow-indigo-500/25"
              >
                {loading
                  ? <Loader2 size={15} className="animate-spin" />
                  : <ArrowUpRight size={15} />
                }
                Start Free Trial
              </button>
              <button
                onClick={handleViewPlans}
                className="px-4 py-2.5 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 text-sm font-medium rounded-xl transition-colors"
              >
                Compare Plans
              </button>
            </div>

            <p className="text-center text-xs text-slate-400 mt-3">
              No credit card required · Cancel anytime
            </p>
          </div>
        </div>
      </div>
    </>
  )
}

// ── Provider ──────────────────────────────────────────────────────────────────

export function UpgradeModalProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen]   = useState(false)
  const [ctx,  setCtx]    = useState<UpgradeContext>({})

  const openUpgradeModal = useCallback((context?: UpgradeContext) => {
    setCtx(context ?? {})
    setOpen(true)
  }, [])

  const closeUpgradeModal = useCallback(() => {
    setOpen(false)
  }, [])

  // Listen for the custom DOM event fired by api.ts interceptor
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail as Record<string, unknown> | undefined
      openUpgradeModal({
        resource: detail?.resource as string | undefined,
        used:     detail?.usage as number | undefined,
        limit:    detail?.limit as number | undefined,
        plan:     detail?.plan as string | undefined,
        message:  detail?.error as string | undefined,
      })
    }
    window.addEventListener('synapse:plan_limit_exceeded', handler)
    return () => window.removeEventListener('synapse:plan_limit_exceeded', handler)
  }, [openUpgradeModal])

  return (
    <UpgradeModalContext.Provider value={{ openUpgradeModal, closeUpgradeModal }}>
      {children}
      {open && <UpgradeModalUI ctx={ctx} onClose={closeUpgradeModal} />}
    </UpgradeModalContext.Provider>
  )
}
