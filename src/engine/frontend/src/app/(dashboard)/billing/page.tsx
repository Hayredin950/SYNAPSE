'use client'

/**
 * /billing — Billing & Subscription management page
 * TASK-003-F2
 *
 * Sections:
 *  - Current plan + status badge
 *  - Usage meters (progress bars)
 *  - Invoice history table
 *  - Upgrade / Cancel / Manage buttons
 */

import React, { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { api } from '@/utils/api'
import toast from 'react-hot-toast'
import {
  CreditCard,
  Zap,
  FileText,
  CheckCircle,
  XCircle,
  AlertTriangle,
  ExternalLink,
  Loader2,
  TrendingUp,
  Download,
  ArrowUpRight,
  RefreshCw,
} from 'lucide-react'

// ── Types ─────────────────────────────────────────────────────────────────────

interface SubscriptionData {
  plan: string
  status: string
  is_active: boolean
  is_pro: boolean
  cancel_at_period_end: boolean
  current_period_end: string | null
  trial_end: string | null
}

interface UsageItem {
  used: number
  limit: number
  unlimited: boolean
  percent: number
}

interface UsageData {
  plan: string
  usage: Record<string, UsageItem>
}

interface Invoice {
  id: string
  stripe_invoice_id: string
  amount: number
  amount_display: string
  currency: string
  status: string
  pdf_url: string
  hosted_url: string
  period_start: string | null
  period_end: string | null
  created_at: string
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const PLAN_COLORS: Record<string, string> = {
  free:       'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  pro:        'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300',
  enterprise: 'bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300',
}

const STATUS_COLORS: Record<string, string> = {
  active:   'text-emerald-500',
  trialing: 'text-sky-500',
  past_due: 'text-amber-500',
  canceled: 'text-red-500',
  unpaid:   'text-red-500',
}

const RESOURCE_LABELS: Record<string, string> = {
  ai_queries:  'AI Queries',
  agent_runs:  'Agent Runs',
  automations: 'Automations',
  documents:   'Documents',
  bookmarks:   'Bookmarks',
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

// ── Sub-components ────────────────────────────────────────────────────────────

function UsageMeter({ label, used, limit, unlimited, percent }: UsageItem & { label: string }) {
  const barColor = percent >= 90 ? 'bg-red-500' : percent >= 70 ? 'bg-amber-500' : 'bg-indigo-500'
  return (
    <div>
      <div className="flex justify-between items-center mb-1">
        <span className="text-xs font-medium text-slate-600 dark:text-slate-400">{label}</span>
        <span className="text-xs text-slate-500 dark:text-slate-500">
          {unlimited ? '∞ Unlimited' : `${used} / ${limit}`}
        </span>
      </div>
      <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-1.5">
        <div
          className={`h-1.5 rounded-full transition-all duration-500 ${unlimited ? 'bg-emerald-500 w-full opacity-30' : barColor}`}
          style={{ width: unlimited ? '100%' : `${percent}%` }}
        />
      </div>
    </div>
  )
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'active' || status === 'trialing') return <CheckCircle size={14} className="text-emerald-500" />
  if (status === 'past_due' || status === 'unpaid')  return <AlertTriangle size={14} className="text-amber-500" />
  return <XCircle size={14} className="text-red-500" />
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function BillingPage() {
  const router = useRouter()

  const [sub,       setSub]       = useState<SubscriptionData | null>(null)
  const [usage,     setUsage]     = useState<UsageData | null>(null)
  const [invoices,  setInvoices]  = useState<Invoice[]>([])
  const [loading,   setLoading]   = useState(true)
  const [upgrading, setUpgrading] = useState(false)
  const [canceling, setCanceling] = useState(false)
  const [opening,   setOpening]   = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [subRes, usageRes, invRes] = await Promise.all([
        api.get('/billing/subscription/'),
        api.get('/billing/usage/'),
        api.get('/billing/invoices/'),
      ])
      setSub(subRes.data)
      setUsage(usageRes.data)
      setInvoices(invRes.data.invoices || [])
    } catch {
      toast.error('Failed to load billing info.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleUpgrade = async (plan: 'pro' | 'enterprise') => {
    setUpgrading(true)
    try {
      const { data } = await api.post('/billing/checkout/', { plan })
      window.location.href = data.checkout_url
    } catch {
      toast.error('Could not start checkout. Please try again.')
      setUpgrading(false)
    }
  }

  const handleManagePortal = async () => {
    setOpening(true)
    try {
      const { data } = await api.post('/billing/portal/')
      window.location.href = data.portal_url
    } catch {
      toast.error('Could not open billing portal.')
      setOpening(false)
    }
  }

  const handleCancel = async () => {
    if (!confirm('Are you sure you want to cancel? You keep access until the end of your billing period.')) return
    setCanceling(true)
    try {
      await api.post('/billing/cancel/')
      toast.success('Subscription will cancel at end of billing period.')
      load()
    } catch (err: unknown) {
      const errData = (err as { response?: { data?: { error?: string | { message?: string } } } })?.response?.data?.error
      const msg = typeof errData === 'string' 
        ? errData 
        : (errData as { message?: string })?.message ?? 'Failed to cancel.'
      toast.error(msg)
    } finally {
      setCanceling(false)
    }
  }

  if (loading) {
    return (
      <div className="flex-1 overflow-y-auto bg-slate-50 dark:bg-slate-950 flex items-center justify-center">
        <Loader2 size={32} className="animate-spin text-indigo-500" />
      </div>
    )
  }

  const plan   = sub?.plan ?? 'free'
  const isPro  = plan === 'pro' || plan === 'enterprise'

  return (
    <div className="flex-1 overflow-y-auto bg-slate-50 dark:bg-slate-950">
      <div className="max-w-3xl mx-auto px-4 py-8 pb-24 lg:pb-8 space-y-6">

        {/* Header */}
        <div className="flex items-center justify-between gap-3 mb-2">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-2xl bg-indigo-600/20 border border-indigo-500/30 shrink-0">
              <CreditCard size={20} className="text-indigo-400" />
            </div>
            <div>
              <h1 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-white">Billing</h1>
              <p className="text-slate-400 text-xs sm:text-sm">Manage your subscription and usage</p>
            </div>
          </div>
          <button
            onClick={load}
            className="p-2 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            title="Refresh"
          >
            <RefreshCw size={16} />
          </button>
        </div>

        {/* Current Plan */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-2xl overflow-hidden">
          <div className="flex items-center gap-3 px-6 py-4 border-b border-slate-200 dark:border-slate-700">
            <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400"><CreditCard size={16} /></div>
            <h2 className="text-base font-semibold text-slate-800 dark:text-white">Current Plan</h2>
          </div>
          <div className="p-6">
            <div className="flex flex-wrap items-center gap-3 mb-4">
              <span className={`px-3 py-1 rounded-full text-sm font-bold uppercase tracking-wide ${PLAN_COLORS[plan] ?? PLAN_COLORS.free}`}>
                {plan}
              </span>
              <div className="flex items-center gap-1.5">
                <StatusIcon status={sub?.status ?? 'active'} />
                <span className={`text-sm font-medium capitalize ${STATUS_COLORS[sub?.status ?? 'active'] ?? 'text-slate-400'}`}>
                  {sub?.status ?? 'active'}
                </span>
              </div>
              {sub?.cancel_at_period_end && (
                <span className="flex items-center gap-1 px-2 py-0.5 bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 text-xs rounded-full font-medium">
                  <AlertTriangle size={11} /> Cancels {formatDate(sub.current_period_end)}
                </span>
              )}
            </div>

            {sub?.current_period_end && !sub.cancel_at_period_end && (
              <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
                Next billing date: <span className="text-slate-700 dark:text-slate-200 font-medium">{formatDate(sub.current_period_end)}</span>
              </p>
            )}
            {sub?.trial_end && (
              <p className="text-sm text-sky-600 dark:text-sky-400 mb-4">
                Free trial ends: <span className="font-medium">{formatDate(sub.trial_end)}</span>
              </p>
            )}

            <div className="flex flex-wrap gap-2 mt-2">
              {!isPro && (
                <button
                  onClick={() => handleUpgrade('pro')}
                  disabled={upgrading}
                  className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm rounded-xl font-semibold transition-colors"
                >
                  {upgrading ? <Loader2 size={14} className="animate-spin" /> : <ArrowUpRight size={14} />}
                  Upgrade to Pro — $19/mo
                </button>
              )}
              {isPro && (
                <>
                  <button
                    onClick={handleManagePortal}
                    disabled={opening}
                    className="flex items-center gap-2 px-4 py-2 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 text-sm rounded-xl font-semibold transition-colors border border-slate-200 dark:border-slate-700"
                  >
                    {opening ? <Loader2 size={14} className="animate-spin" /> : <ExternalLink size={14} />}
                    Manage Billing
                  </button>
                  {!sub?.cancel_at_period_end && (
                    <button
                      onClick={handleCancel}
                      disabled={canceling}
                      className="flex items-center gap-2 px-4 py-2 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 text-sm rounded-xl font-medium transition-colors border border-red-200 dark:border-red-900/30"
                    >
                      {canceling ? <Loader2 size={14} className="animate-spin" /> : <XCircle size={14} />}
                      Cancel Subscription
                    </button>
                  )}
                </>
              )}
              <Link
                href="/pricing"
                className="flex items-center gap-1.5 px-4 py-2 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-900/20 text-sm rounded-xl font-medium transition-colors border border-indigo-200 dark:border-indigo-800/40"
              >
                <TrendingUp size={14} /> View All Plans
              </Link>
            </div>
          </div>
        </div>

        {/* Usage Meters */}
        {usage && (
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-2xl overflow-hidden">
            <div className="flex items-center gap-3 px-6 py-4 border-b border-slate-200 dark:border-slate-700">
              <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400"><Zap size={16} /></div>
              <h2 className="text-base font-semibold text-slate-800 dark:text-white">Usage This Month</h2>
            </div>
            <div className="p-6 space-y-5">
              {Object.entries(usage.usage).map(([key, val]) => (
                <UsageMeter
                  key={key}
                  label={RESOURCE_LABELS[key] ?? key}
                  {...val}
                />
              ))}
              {!isPro && (
                <div className="mt-2 p-3 bg-indigo-50 dark:bg-indigo-900/20 rounded-xl border border-indigo-200 dark:border-indigo-800/40">
                  <p className="text-xs text-indigo-700 dark:text-indigo-300 font-medium">
                    ✨ Upgrade to Pro for unlimited AI queries, documents, automations, and more.
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Invoices */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-2xl overflow-hidden">
          <div className="flex items-center gap-3 px-6 py-4 border-b border-slate-200 dark:border-slate-700">
            <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400"><FileText size={16} /></div>
            <h2 className="text-base font-semibold text-slate-800 dark:text-white">Invoice History</h2>
          </div>
          <div className="p-6">
            {invoices.length === 0 ? (
              <p className="text-sm text-slate-400 dark:text-slate-500 text-center py-4">
                No invoices yet. They'll appear here after your first payment.
              </p>
            ) : (
              <div className="overflow-x-auto -mx-2">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs font-semibold text-slate-500 dark:text-slate-500 uppercase tracking-wide border-b border-slate-100 dark:border-slate-800">
                      <th className="pb-2 px-2">Date</th>
                      <th className="pb-2 px-2">Amount</th>
                      <th className="pb-2 px-2">Status</th>
                      <th className="pb-2 px-2 text-right">PDF</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {invoices.map((inv) => (
                      <tr key={inv.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors">
                        <td className="py-3 px-2 text-slate-600 dark:text-slate-300 whitespace-nowrap">{formatDate(inv.created_at)}</td>
                        <td className="py-3 px-2 font-semibold text-slate-800 dark:text-white">{inv.amount_display}</td>
                        <td className="py-3 px-2">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                            inv.status === 'paid'
                              ? 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400'
                              : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400'
                          }`}>
                            {inv.status === 'paid' ? <CheckCircle size={10} /> : <XCircle size={10} />}
                            {inv.status}
                          </span>
                        </td>
                        <td className="py-3 px-2 text-right">
                          {inv.pdf_url ? (
                            <a
                              href={inv.pdf_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 text-indigo-600 dark:text-indigo-400 hover:underline text-xs font-medium"
                            >
                              <Download size={12} /> PDF
                            </a>
                          ) : inv.hosted_url ? (
                            <a
                              href={inv.hosted_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 text-indigo-600 dark:text-indigo-400 hover:underline text-xs font-medium"
                            >
                              <ExternalLink size={12} /> View
                            </a>
                          ) : <span className="text-slate-400">—</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  )
}
