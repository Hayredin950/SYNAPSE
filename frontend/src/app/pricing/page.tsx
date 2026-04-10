'use client'

/**
 * /pricing — Public pricing page
 * TASK-003-F1
 *
 * 3-column cards: Free / Pro ($19/mo) / Enterprise ($99/mo)
 * Monthly/Annual toggle (20% annual discount)
 * CTA: Free → Register | Pro/Ent → Checkout
 */

import React, { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuthStore } from '@/store/authStore'
import { api } from '@/utils/api'
import toast from 'react-hot-toast'
import {
  Check,
  X,
  Zap,
  Building2,
  Star,
  Loader2,
  ArrowRight,
} from 'lucide-react'

// ── Plan data ─────────────────────────────────────────────────────────────────

const PLANS = [
  {
    key:         'free',
    name:        'Free',
    icon:        Star,
    monthlyPrice: 0,
    annualPrice:  0,
    description: 'Perfect for exploring AI-powered tech research.',
    cta:         'Get Started Free',
    ctaVariant:  'outline' as const,
    highlighted: false,
    features: [
      { label: '50 AI queries / month',          included: true  },
      { label: '10 documents / month',           included: true  },
      { label: 'Tech feed (last 7 days)',         included: true  },
      { label: 'GitHub radar (public repos)',     included: true  },
      { label: 'Basic search',                   included: true  },
      { label: '5 automation workflows',         included: true  },
      { label: 'Semantic search',                included: false },
      { label: 'Google Drive + S3 integration',  included: false },
      { label: 'Unlimited AI queries',           included: false },
      { label: 'Priority support',               included: false },
    ],
  },
  {
    key:         'pro',
    name:        'Pro',
    icon:        Zap,
    monthlyPrice: 19,
    annualPrice:  15,   // ~$182/yr vs $228/yr — 20% off
    description: 'Unlimited AI power for serious developers & researchers.',
    cta:         'Start 14-Day Free Trial',
    ctaVariant:  'primary' as const,
    highlighted: true,
    badge:       'Most Popular',
    features: [
      { label: 'Unlimited AI queries',            included: true },
      { label: 'Unlimited documents',             included: true },
      { label: 'Full tech feed history',          included: true },
      { label: 'GitHub radar (private repos)',     included: true },
      { label: 'Semantic search',                 included: true },
      { label: 'Unlimited automation workflows',  included: true },
      { label: 'Google Drive + S3 integration',   included: true },
      { label: 'Priority support',                included: true },
      { label: 'Team workspaces',                 included: false },
      { label: 'SSO / SAML',                      included: false },
    ],
  },
  {
    key:         'enterprise',
    name:        'Enterprise',
    icon:        Building2,
    monthlyPrice: 99,
    annualPrice:  79,
    description: 'Custom AI, SSO, and dedicated support for your team.',
    cta:         'Start 14-Day Free Trial',
    ctaVariant:  'outline' as const,
    highlighted: false,
    features: [
      { label: 'Everything in Pro',               included: true },
      { label: 'Team workspaces',                 included: true },
      { label: 'SSO / SAML',                      included: true },
      { label: 'Custom AI model fine-tuning',     included: true },
      { label: 'Dedicated Slack support',         included: true },
      { label: '99.9% uptime SLA',               included: true },
      { label: 'Custom integrations',             included: true },
      { label: 'Audit logs',                      included: true },
      { label: 'Advanced analytics',              included: true },
      { label: 'Invoice billing',                 included: true },
    ],
  },
]

// ── Main Component ────────────────────────────────────────────────────────────

export default function PricingPage() {
  const router = useRouter()
  const { isAuthenticated } = useAuthStore()
  const [annual,   setAnnual]   = useState(false)
  const [loading,  setLoading]  = useState<string | null>(null)

  const handleCTA = async (planKey: string) => {
    if (planKey === 'free') {
      router.push(isAuthenticated ? '/home' : '/register')
      return
    }

    if (!isAuthenticated) {
      router.push(`/register?plan=${planKey}`)
      return
    }

    setLoading(planKey)
    try {
      const { data } = await api.post('/billing/checkout/', { plan: planKey })
      window.location.href = data.checkout_url
    } catch {
      toast.error('Could not start checkout. Please try again.')
      setLoading(null)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      {/* Nav */}
      <header className="sticky top-0 z-20 border-b border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-950/80 backdrop-blur">
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
              <span className="text-white font-black text-xs">S</span>
            </div>
            <span className="font-black text-slate-900 dark:text-white tracking-tight">SYNAPSE</span>
          </Link>
          <div className="flex items-center gap-3">
            {isAuthenticated ? (
              <Link href="/home" className="text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white">
                Dashboard →
              </Link>
            ) : (
              <>
                <Link href="/login" className="text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white">
                  Sign in
                </Link>
                <Link href="/register" className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold rounded-lg transition-colors">
                  Get Started
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-16">
        {/* Hero */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 rounded-full text-xs font-semibold mb-4">
            <Zap size={12} /> No credit card required for free tier
          </div>
          <h1 className="text-4xl sm:text-5xl font-black text-slate-900 dark:text-white mb-4 tracking-tight">
            Simple, transparent pricing
          </h1>
          <p className="text-lg text-slate-500 dark:text-slate-400 max-w-xl mx-auto">
            Start free. Upgrade when you need more AI power, unlimited search, and automation.
          </p>

          {/* Billing toggle */}
          <div className="flex items-center justify-center gap-3 mt-8">
            <span className={`text-sm font-medium ${!annual ? 'text-slate-900 dark:text-white' : 'text-slate-400'}`}>Monthly</span>
            <button
              onClick={() => setAnnual(a => !a)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${annual ? 'bg-indigo-600' : 'bg-slate-300 dark:bg-slate-700'}`}
            >
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${annual ? 'translate-x-6' : 'translate-x-1'}`} />
            </button>
            <span className={`text-sm font-medium ${annual ? 'text-slate-900 dark:text-white' : 'text-slate-400'}`}>
              Annual
              <span className="ml-1.5 px-1.5 py-0.5 bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 text-xs rounded-full font-semibold">
                Save 20%
              </span>
            </span>
          </div>
        </div>

        {/* Plan cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-start">
          {PLANS.map((plan) => {
            const Icon  = plan.icon
            const price = annual ? plan.annualPrice : plan.monthlyPrice
            const isLoading = loading === plan.key

            return (
              <div
                key={plan.key}
                className={`relative rounded-2xl border overflow-hidden ${
                  plan.highlighted
                    ? 'border-indigo-500 shadow-xl shadow-indigo-500/10 bg-white dark:bg-slate-900'
                    : 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900'
                }`}
              >
                {/* Top accent for highlighted */}
                {plan.highlighted && (
                  <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-indigo-500 via-violet-500 to-cyan-500" />
                )}

                {plan.badge && (
                  <div className="absolute top-4 right-4">
                    <span className="px-2 py-0.5 bg-indigo-600 text-white text-xs font-bold rounded-full">
                      {plan.badge}
                    </span>
                  </div>
                )}

                <div className="p-6">
                  {/* Plan header */}
                  <div className="flex items-center gap-2 mb-3">
                    <div className={`p-1.5 rounded-lg ${plan.highlighted ? 'bg-indigo-600/20 text-indigo-400' : 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400'}`}>
                      <Icon size={16} />
                    </div>
                    <h2 className="text-base font-bold text-slate-900 dark:text-white">{plan.name}</h2>
                  </div>

                  {/* Price */}
                  <div className="mb-2">
                    <div className="flex items-end gap-1">
                      <span className="text-4xl font-black text-slate-900 dark:text-white">${price}</span>
                      {price > 0 && <span className="text-slate-400 text-sm mb-1.5">/{annual ? 'mo, billed annually' : 'mo'}</span>}
                      {price === 0 && <span className="text-slate-400 text-sm mb-1.5">forever free</span>}
                    </div>
                    {annual && price > 0 && (
                      <p className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">
                        Save ${(plan.monthlyPrice - price) * 12}/year vs monthly
                      </p>
                    )}
                  </div>

                  <p className="text-sm text-slate-500 dark:text-slate-400 mb-6 min-h-[40px]">{plan.description}</p>

                  {/* CTA Button */}
                  <button
                    onClick={() => handleCTA(plan.key)}
                    disabled={isLoading}
                    className={`w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-bold transition-all ${
                      plan.ctaVariant === 'primary'
                        ? 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-500/25'
                        : 'border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800'
                    } disabled:opacity-50`}
                  >
                    {isLoading ? <Loader2 size={15} className="animate-spin" /> : <ArrowRight size={15} />}
                    {plan.cta}
                  </button>

                  {plan.key === 'pro' && (
                    <p className="text-center text-xs text-slate-400 mt-2">No credit card required for trial</p>
                  )}

                  {/* Features */}
                  <div className="mt-6 space-y-3">
                    {plan.features.map((feat) => (
                      <div key={feat.label} className="flex items-start gap-2.5">
                        {feat.included
                          ? <Check size={15} className="text-emerald-500 flex-shrink-0 mt-0.5" />
                          : <X size={15} className="text-slate-300 dark:text-slate-600 flex-shrink-0 mt-0.5" />
                        }
                        <span className={`text-sm ${feat.included ? 'text-slate-700 dark:text-slate-200' : 'text-slate-400 dark:text-slate-600 line-through'}`}>
                          {feat.label}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )
          })}
        </div>

        {/* FAQ / Trust */}
        <div className="mt-16 text-center">
          <p className="text-sm text-slate-400 mb-4">
            All plans include 14-day free trial on paid tiers · Cancel anytime · Payments secured by Stripe
          </p>
          <p className="text-sm text-slate-400">
            Questions?{' '}
            <a href="mailto:support@synapse.ai" className="text-indigo-600 dark:text-indigo-400 hover:underline">
              support@synapse.ai
            </a>
          </p>
        </div>
      </main>
    </div>
  )
}
