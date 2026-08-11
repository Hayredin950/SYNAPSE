'use client'

/**
 * /account — Usage & Referrals
 *
 * SYNAPSE is free to use. This page shows the quota you have left and your
 * referral link, which raises your monthly ceiling for each person who signs up.
 */

import React, { useState, useEffect, useCallback } from 'react'
import { api } from '@/utils/api'
import toast from 'react-hot-toast'
import {
  Gift,
  Zap,
  Copy,
  Check,
  Loader2,
  RefreshCw,
  Users,
} from 'lucide-react'

// ── Types ─────────────────────────────────────────────────────────────────────

interface QuotaWindow {
  used: number
  limit: number
  unlimited: boolean
  percent: number
}

type UsageData = Record<string, Record<string, QuotaWindow>>

interface ReferralData {
  code: string
  uses: number
  max_uses: number
  referral_url: string
  reward: string
  bonus_referrals_counted: number
  bonus_referrals_max: number
}

const RESOURCE_LABELS: Record<string, string> = {
  ai_queries: 'AI queries',
  agent_runs: 'Agent runs',
  documents: 'Documents',
  repositories: 'Repositories',
  api_calls: 'API calls',
  scheduled_tasks: 'Scheduled tasks',
}

function barColor(percent: number): string {
  if (percent >= 90) return 'bg-red-500'
  if (percent >= 70) return 'bg-amber-500'
  return 'bg-emerald-500'
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function AccountPage() {
  const [usage, setUsage] = useState<UsageData | null>(null)
  const [referral, setReferral] = useState<ReferralData | null>(null)
  const [loading, setLoading] = useState(true)
  const [copied, setCopied] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [usageRes, refRes] = await Promise.all([
        api.get('/growth/usage/'),
        api.get('/growth/referral/'),
      ])
      setUsage(usageRes.data?.usage ?? null)
      setReferral(refRes.data ?? null)
    } catch {
      toast.error('Could not load your usage. Try again in a moment.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const copyLink = async () => {
    if (!referral?.referral_url) return
    try {
      await navigator.clipboard.writeText(referral.referral_url)
      setCopied(true)
      toast.success('Referral link copied')
      setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.error('Could not copy to clipboard')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="animate-spin text-neutral-400" size={28} aria-label="Loading" />
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-4xl space-y-8 p-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Usage &amp; Referrals</h1>
          <p className="mt-1 text-sm text-neutral-500">
            SYNAPSE is free. Quotas keep shared AI capacity available for everyone.
          </p>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-2 rounded-lg border border-neutral-300 px-3 py-2 text-sm hover:bg-neutral-50 dark:border-neutral-700 dark:hover:bg-neutral-800"
        >
          <RefreshCw size={14} aria-hidden="true" />
          Refresh
        </button>
      </header>

      {/* ── Quota meters ───────────────────────────────────────────────── */}
      <section aria-labelledby="quota-heading" className="space-y-4">
        <h2 id="quota-heading" className="flex items-center gap-2 text-lg font-medium">
          <Zap size={18} className="text-amber-500" aria-hidden="true" />
          Your quota
        </h2>

        {!usage || Object.keys(usage).length === 0 ? (
          <p className="text-sm text-neutral-500">No usage recorded yet.</p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {Object.entries(usage).map(([resource, windows]) => (
              <div
                key={resource}
                className="rounded-xl border border-neutral-200 p-4 dark:border-neutral-800"
              >
                <h3 className="mb-3 text-sm font-medium">
                  {RESOURCE_LABELS[resource] ?? resource.replace(/_/g, ' ')}
                </h3>
                <div className="space-y-3">
                  {Object.entries(windows).map(([period, w]) => (
                    <div key={period}>
                      <div className="mb-1 flex justify-between text-xs text-neutral-500">
                        <span className="capitalize">{period}</span>
                        <span>
                          {w.unlimited ? 'Unlimited' : `${w.used} / ${w.limit}`}
                        </span>
                      </div>
                      {!w.unlimited && (
                        <div
                          className="h-1.5 w-full overflow-hidden rounded-full bg-neutral-200 dark:bg-neutral-700"
                          role="progressbar"
                          aria-valuenow={w.percent}
                          aria-valuemin={0}
                          aria-valuemax={100}
                          aria-label={`${resource} ${period} usage`}
                        >
                          <div
                            className={`h-full rounded-full transition-all ${barColor(w.percent)}`}
                            style={{ width: `${w.percent}%` }}
                          />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ── Referrals ──────────────────────────────────────────────────── */}
      {referral?.code && (
        <section
          aria-labelledby="referral-heading"
          className="rounded-xl border border-neutral-200 p-5 dark:border-neutral-800"
        >
          <h2
            id="referral-heading"
            className="flex items-center gap-2 text-lg font-medium"
          >
            <Gift size={18} className="text-violet-500" aria-hidden="true" />
            Invite others, get more quota
          </h2>
          <p className="mt-1 text-sm text-neutral-500">{referral.reward}</p>

          <div className="mt-4 flex items-center gap-2">
            <label htmlFor="referral-link" className="sr-only">
              Your referral link
            </label>
            <input
              id="referral-link"
              readOnly
              value={referral.referral_url}
              onFocus={(e) => e.currentTarget.select()}
              className="flex-1 rounded-lg border border-neutral-300 bg-neutral-50 px-3 py-2 font-mono text-sm dark:border-neutral-700 dark:bg-neutral-900"
            />
            <button
              onClick={copyLink}
              className="flex items-center gap-2 rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800 dark:bg-white dark:text-neutral-900 dark:hover:bg-neutral-200"
            >
              {copied ? <Check size={14} aria-hidden="true" /> : <Copy size={14} aria-hidden="true" />}
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>

          <div className="mt-4 flex items-center gap-2 text-sm text-neutral-500">
            <Users size={14} aria-hidden="true" />
            <span>
              {referral.uses} {referral.uses === 1 ? 'signup' : 'signups'} so far
              {referral.bonus_referrals_max > 0 && (
                <>
                  {' '}— {referral.bonus_referrals_counted} of{' '}
                  {referral.bonus_referrals_max} counted toward bonus quota
                </>
              )}
            </span>
          </div>
        </section>
      )}
      </div>
    </div>
  )
}
