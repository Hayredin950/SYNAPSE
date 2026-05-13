'use client'

import React, { useState, useEffect, useRef } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import {
  Zap, Search, GitBranch, Bot, Workflow, BookOpen,
  Star, TrendingUp, FileText, ChevronRight, Check,
  Menu, X, ArrowRight, Sparkles, Shield, Clock,
  BarChart3, MessageSquare, Brain, Twitter
} from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import { api } from '@/utils/api'

// ─── Types ───────────────────────────────────────────────────────────────────

interface TrendingItem {
  id: string
  title: string
  source_type?: string
  source?: { name: string }
  stars?: number
  topic?: string
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function useScrolled(threshold = 20) {
  const [scrolled, setScrolled] = useState(false)
  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > threshold)
    window.addEventListener('scroll', fn, { passive: true })
    return () => window.removeEventListener('scroll', fn)
  }, [threshold])
  return scrolled
}

function useInView(ref: React.RefObject<HTMLElement>) {
  const [inView, setInView] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) setInView(true) }, { threshold: 0.15 })
    obs.observe(el)
    return () => obs.disconnect()
  }, [ref])
  return inView
}

function AnimatedNumber({ target, suffix = '' }: { target: number; suffix?: string }) {
  const [val, setVal] = useState(0)
  const ref = useRef<HTMLSpanElement>(null)
  const inView = useInView(ref as React.RefObject<HTMLElement>)
  useEffect(() => {
    if (!inView) return
    let start = 0
    const steps = 40
    const inc = target / steps
    const timer = setInterval(() => {
      start += inc
      if (start >= target) { setVal(target); clearInterval(timer) }
      else setVal(Math.floor(start))
    }, 30)
    return () => clearInterval(timer)
  }, [inView, target])
  return <span ref={ref}>{val.toLocaleString()}{suffix}</span>
}

// ─── Navbar ───────────────────────────────────────────────────────────────────

function LandingNavbar() {
  const scrolled = useScrolled()
  const [menuOpen, setMenuOpen] = useState(false)
  const [isMounted, setIsMounted] = useState(false)
  const { isAuthenticated, accessToken } = useAuthStore()

  useEffect(() => { setIsMounted(true) }, [])

  const loggedIn = isMounted && isAuthenticated && !!accessToken

  return (
    <nav className={`fixed top-0 inset-x-0 z-50 transition-all duration-300 ${
      scrolled
        ? 'bg-white/80 dark:bg-slate-950/80 backdrop-blur-xl border-b border-slate-200/60 dark:border-slate-800/60 shadow-sm'
        : 'bg-transparent'
    }`}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <div className="flex items-center gap-2.5 shrink-0">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/30">
              <span className="text-white font-black text-sm">S</span>
            </div>
            <span className="font-black text-lg tracking-tight bg-gradient-to-r from-indigo-600 to-violet-600 bg-clip-text text-transparent">
              SYNAPSE
            </span>
          </div>

          {/* Desktop nav */}
          <div className="hidden md:flex items-center gap-8">
            {[['Features', '#features'], ['Pricing', '#pricing'], ['Trending', '#trending']].map(([label, href]) => (
              <a key={label} href={href}
                className="text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors">
                {label}
              </a>
            ))}
          </div>

          {/* Desktop CTAs */}
          <div className="hidden md:flex items-center gap-3">
            {loggedIn ? (
              <Link href="/home"
                className="flex items-center gap-1.5 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white text-sm font-semibold px-4 py-2 rounded-xl shadow-lg shadow-indigo-500/25 transition-all hover:shadow-indigo-500/40 hover:scale-[1.02] active:scale-[0.98]">
                Go to Dashboard <ChevronRight size={14} />
              </Link>
            ) : (
              <>
                <Link href="/login"
                  className="text-sm font-medium text-slate-700 dark:text-slate-300 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors px-3 py-1.5">
                  Log in
                </Link>
                <Link href="/register"
                  className="flex items-center gap-1.5 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white text-sm font-semibold px-4 py-2 rounded-xl shadow-lg shadow-indigo-500/25 transition-all hover:shadow-indigo-500/40 hover:scale-[1.02] active:scale-[0.98]">
                  Get started free <ChevronRight size={14} />
                </Link>
              </>
            )}
          </div>

          {/* Mobile hamburger */}
          <button onClick={() => setMenuOpen(!menuOpen)} className="md:hidden p-2 rounded-lg text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
            {menuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>

        {/* Mobile menu */}
        {menuOpen && (
          <div className="md:hidden pb-4 pt-2 border-t border-slate-200 dark:border-slate-800 mt-1">
            <div className="flex flex-col gap-1">
              {[['Features', '#features'], ['Pricing', '#pricing'], ['Trending', '#trending']].map(([label, href]) => (
                <a key={label} href={href} onClick={() => setMenuOpen(false)}
                  className="px-3 py-2.5 text-sm font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors">
                  {label}
                </a>
              ))}
              <div className="flex gap-2 mt-2 px-1">
                {loggedIn ? (
                  <Link href="/home" className="flex-1 text-center text-sm font-semibold bg-gradient-to-r from-indigo-600 to-violet-600 text-white py-2.5 rounded-xl shadow-lg shadow-indigo-500/25">Go to Dashboard</Link>
                ) : (
                  <>
                    <Link href="/login" className="flex-1 text-center text-sm font-medium border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 py-2.5 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors">Log in</Link>
                    <Link href="/register" className="flex-1 text-center text-sm font-semibold bg-gradient-to-r from-indigo-600 to-violet-600 text-white py-2.5 rounded-xl shadow-lg shadow-indigo-500/25">Get started</Link>
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </nav>
  )
}

// ─── Features ─────────────────────────────────────────────────────────────────

const FEATURES = [
  {
    icon: TrendingUp,
    color: 'from-indigo-500 to-violet-600',
    glow: 'shadow-indigo-500/20',
    title: 'Tech Intelligence Feed',
    desc: 'Real-time aggregation from Hacker News, arXiv, GitHub trending, X/Twitter and YouTube. AI-summarized, filtered by topic, personalized to your interests.',
  },
  {
    icon: MessageSquare,
    color: 'from-violet-500 to-purple-600',
    glow: 'shadow-violet-500/20',
    title: 'AI Chat (RAG)',
    desc: 'Ask anything about tech — SYNAPSE answers grounded in your knowledge base with source citations, not hallucinations. Full conversation history.',
  },
  {
    icon: GitBranch,
    color: 'from-emerald-500 to-teal-600',
    glow: 'shadow-emerald-500/20',
    title: 'GitHub Radar',
    desc: 'Discover trending repositories with star sparklines, language breakdown and topic filters. Bookmark repos and track ecosystem momentum.',
  },
  {
    icon: Twitter,
    color: 'from-sky-500 to-blue-600',
    glow: 'shadow-sky-500/20',
    title: 'X (Twitter) Feed',
    desc: 'Stay updated with curated tweets on AI, programming, cybersecurity and tech. Filter by topic, sort by engagement, ask AI about any tweet.',
  },
  {
    icon: Bot,
    color: 'from-amber-500 to-orange-600',
    glow: 'shadow-amber-500/20',
    title: 'Autonomous AI Agents',
    desc: 'Agents that research, generate PDFs/PPTs/Word docs, scaffold code projects and analyze trends — all from a single natural language command.',
  },
  {
    icon: Workflow,
    color: 'from-cyan-500 to-blue-600',
    glow: 'shadow-cyan-500/20',
    title: 'Automation Center',
    desc: 'No-code workflows: connect triggers (new article, scheduled time, events) to actions (generate doc, send notification, call webhook). Zero friction.',
  },
  {
    icon: BookOpen,
    color: 'from-rose-500 to-pink-600',
    glow: 'shadow-rose-500/20',
    title: 'Research Explorer',
    desc: 'Semantic search across 50K+ arXiv papers with AI-generated summaries, difficulty ratings, citation counts and one-click Ask AI for any paper.',
  },
]

function FeaturesSection() {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref as React.RefObject<HTMLElement>)
  return (
    <section id="features" ref={ref} className="relative py-24 bg-slate-50 dark:bg-slate-900/50">
      <div className="absolute inset-x-0 top-0 h-16 bg-gradient-to-b from-white dark:from-slate-950 to-transparent pointer-events-none" />
      <div className="absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-white dark:from-slate-950 to-transparent pointer-events-none" />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <div className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-indigo-600 dark:text-indigo-400 mb-3">
            <Zap size={12} /> Everything you need
          </div>
          <h2 className="text-4xl sm:text-5xl font-black text-slate-900 dark:text-white mb-4">
            Built for the way tech builders actually work
          </h2>
          <p className="max-w-2xl mx-auto text-lg text-slate-600 dark:text-slate-400">
            Seven tools in one — designed to save you 10+ hours every week so you can focus on building.
          </p>
        </div>
        <div className={`grid sm:grid-cols-2 lg:grid-cols-3 gap-6 transition-all duration-700 ${inView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
          {FEATURES.map(({ icon: Icon, color, glow, title, desc }) => (
            <div key={title} className={`group relative bg-white dark:bg-slate-800/60 rounded-2xl border border-slate-200 dark:border-slate-700/60 p-6 hover:shadow-xl hover:${glow} transition-all duration-300 hover:-translate-y-1 overflow-hidden`}>
              <div className="absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r opacity-0 group-hover:opacity-100 transition-opacity rounded-t-2xl" style={{backgroundImage: `linear-gradient(to right, var(--tw-gradient-stops))`}} />
              <div className={`w-12 h-12 rounded-2xl bg-gradient-to-br ${color} flex items-center justify-center mb-4 shadow-lg shadow-black/10`}>
                <Icon size={22} className="text-white" />
              </div>
              <h3 className="font-bold text-slate-900 dark:text-white text-lg mb-2">{title}</h3>
              <p className="text-slate-600 dark:text-slate-400 text-sm leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ─── Stats Bar ────────────────────────────────────────────────────────────────

const STATS = [
  { icon: FileText, label: 'Articles indexed', value: 50000, suffix: '+' },
  { icon: Clock,    label: 'Refresh interval', value: 30,    suffix: ' min' },
  { icon: Shield,   label: 'Uptime SLA',        value: 99,    suffix: '.9%' },
  { icon: Brain,    label: 'AI tools available', value: 10,   suffix: '+' },
  { icon: BarChart3,label: 'Avg response time',  value: 200,  suffix: 'ms' },
]

function StatsSection() {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref as React.RefObject<HTMLElement>)
  return (
    <section ref={ref} className="relative py-20 bg-white dark:bg-slate-950">
      <div className="absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-slate-50 dark:from-slate-900/50 to-transparent pointer-events-none" />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className={`grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-8 transition-all duration-700 ${inView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-6'}`}>
          {STATS.map(({ icon: Icon, label, value, suffix }) => (
            <div key={label} className="text-center">
              <Icon size={20} className="text-indigo-500 mx-auto mb-2" />
              <div className="text-3xl sm:text-4xl font-black text-slate-900 dark:text-white mb-1">
                {inView ? <AnimatedNumber target={value} suffix={suffix} /> : '—'}
              </div>
              <div className="text-xs text-slate-500 dark:text-slate-500 font-medium">{label}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ─── Pricing ──────────────────────────────────────────────────────────────────

const PLANS = [
  {
    name: 'Free',
    price: '$0',
    period: '/month',
    description: 'Perfect for individuals exploring tech intelligence.',
    cta: 'Get started free',
    href: '/register',
    highlight: false,
    features: [
      '50 AI chat messages / day',
      '10 documents generated',
      '5 automation workflows',
      'Tech feed (7-day history)',
      'Basic keyword search',
      'Bookmark collections',
      '1 AI Agent mode',
    ],
    missing: ['Semantic search', 'Unlimited AI agents', 'SSO / SAML', 'Team workspaces'],
  },
  {
    name: 'Pro',
    price: '$19',
    period: '/month',
    description: 'Everything you need to stay ahead — unlimited AI power.',
    cta: 'Start Pro trial',
    href: '/register?plan=pro',
    highlight: true,
    features: [
      'Unlimited AI chat messages',
      'Unlimited documents',
      'Unlimited automations',
      'Full history (all time)',
      'Semantic + hybrid search',
      'All AI Agents modes',
      'Google Drive & S3 export',
      'Priority support',
    ],
    missing: ['SSO / SAML', 'Team workspaces'],
  },
  {
    name: 'Enterprise',
    price: '$99',
    period: '/month',
    description: 'For high-performance teams with custom requirements.',
    cta: 'Contact sales',
    href: 'mailto:sales@synapse.app',
    highlight: false,
    features: [
      'Everything in Pro',
      'Team workspaces & RBAC',
      'SSO / SAML integration',
      'Custom AI model tuning',
      'White-label licensing',
      'Advanced audit logs',
      'Dedicated support channel',
      'SLA guarantee',
    ],
    missing: [],
  },
]

function PricingSection() {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref as React.RefObject<HTMLElement>)
  return (
    <section id="pricing" ref={ref} className="relative py-24 bg-slate-50 dark:bg-slate-900/50">
      <div className="absolute inset-x-0 top-0 h-16 bg-gradient-to-b from-white dark:from-slate-950 to-transparent pointer-events-none" />
      <div className="absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-indigo-600/20 to-transparent pointer-events-none" />
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <div className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-indigo-600 dark:text-indigo-400 mb-3">
            <Star size={12} /> Pricing
          </div>
          <h2 className="text-4xl sm:text-5xl font-black text-slate-900 dark:text-white mb-4">
            Simple, transparent pricing
          </h2>
          <p className="text-lg text-slate-600 dark:text-slate-400">
            Start free. Upgrade when your team is ready. No surprises.
          </p>
        </div>
        <div className={`grid sm:grid-cols-2 lg:grid-cols-3 gap-6 lg:gap-8 items-stretch transition-all duration-700 ${inView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
          {PLANS.map((plan) => (
            <div key={plan.name} className={`relative flex flex-col rounded-2xl border p-7 ${
              plan.highlight
                ? 'bg-gradient-to-b from-indigo-600 to-violet-700 border-indigo-500 shadow-2xl shadow-indigo-500/30 scale-[1.02]'
                : 'bg-white dark:bg-slate-800/60 border-slate-200 dark:border-slate-700/60'
            }`}>
              {plan.highlight && (
                <div className="absolute -top-3.5 left-1/2 -translate-x-1/2">
                  <span className="bg-amber-400 text-amber-900 text-xs font-black px-3 py-1 rounded-full shadow-lg">
                    ✦ Most Popular
                  </span>
                </div>
              )}
              <div className="mb-6">
                <div className={`text-xs font-bold uppercase tracking-widest mb-1 ${plan.highlight ? 'text-indigo-200' : 'text-slate-500 dark:text-slate-400'}`}>
                  {plan.name}
                </div>
                <div className="flex items-end gap-1 mb-2">
                  <span className={`text-5xl font-black ${plan.highlight ? 'text-white' : 'text-slate-900 dark:text-white'}`}>
                    {plan.price}
                  </span>
                  <span className={`text-sm font-medium mb-2 ${plan.highlight ? 'text-indigo-200' : 'text-slate-500 dark:text-slate-400'}`}>
                    {plan.period}
                  </span>
                </div>
                <p className={`text-sm ${plan.highlight ? 'text-indigo-100' : 'text-slate-600 dark:text-slate-400'}`}>
                  {plan.description}
                </p>
              </div>
              <ul className="space-y-2.5 mb-8 flex-1">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-start gap-2.5 text-sm">
                    <Check size={15} className={`shrink-0 mt-0.5 ${plan.highlight ? 'text-emerald-300' : 'text-emerald-500'}`} />
                    <span className={plan.highlight ? 'text-indigo-50' : 'text-slate-700 dark:text-slate-300'}>{f}</span>
                  </li>
                ))}
                {plan.missing.map((f) => (
                  <li key={f} className="flex items-start gap-2.5 text-sm opacity-40">
                    <X size={15} className="shrink-0 mt-0.5 text-slate-400" />
                    <span className={plan.highlight ? 'text-indigo-200' : 'text-slate-500 dark:text-slate-500'}>{f}</span>
                  </li>
                ))}
              </ul>
              <a href={plan.href}
                className={`w-full text-center font-bold py-3 rounded-xl transition-all text-sm ${
                  plan.highlight
                    ? 'bg-white text-indigo-700 hover:bg-indigo-50 shadow-lg'
                    : 'border border-slate-200 dark:border-slate-600 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700'
                }`}>
                {plan.cta}
              </a>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ─── Live Trending ─────────────────────────────────────────────────────────────

function TrendingSection() {
  const { data: trendingData } = useQuery({
    queryKey: ['landing-trending'],
    queryFn: async () => {
      const res = await api.get('/trending/?limit=8&hours=48')
      return res.data?.data || {}
    },
    staleTime: 10 * 60 * 1000,
    retry: false,
  })

  const { data: tweetsData } = useQuery({
    queryKey: ['landing-tweets'],
    queryFn: async () => {
      const res = await api.get('/tweets/trending/?limit=4')
      return res.data?.data || res.data?.results || []
    },
    staleTime: 10 * 60 * 1000,
    retry: false,
  })

  const tweets: TrendingItem[] = Array.isArray(tweetsData) ? tweetsData.slice(0, 4).map((t: any) => ({
    id: t.id,
    title: t.text?.slice(0, 100) + (t.text?.length > 100 ? '...' : ''),
    source_type: 'twitter',
  })) : []

  const items: TrendingItem[] = [
    ...(trendingData?.articles || []).slice(0, 2),
    ...tweets.slice(0, 2),
    ...(trendingData?.repos || []).slice(0, 2),
    ...(trendingData?.papers || []).slice(0, 2),
  ]

  const FALLBACK: TrendingItem[] = [
    { id: '1', title: 'GPT-4o mini outperforms larger models on coding benchmarks', source_type: 'hackernews' },
    { id: '2', title: 'microsoft/phi-3-mini · 3.8B model with 128K context', source_type: 'github', stars: 12400 },
    { id: '3', title: 'Attention Is All You Need — Revisited with Flash Attention 3', source_type: 'arxiv' },
    { id: '4', title: '🔥 LLMs are now writing 30% of code at major tech companies — the agentic era is here', source_type: 'twitter' },
    { id: '5', title: 'vercel/next.js — Turbopack now default in Next.js 15', source_type: 'github', stars: 118000 },
    { id: '6', title: 'Constitutional AI: Harmlessness from AI Feedback — Anthropic', source_type: 'arxiv' },
  ]

  const displayItems = items.length >= 4 ? items : FALLBACK

  const sourceColor = (type?: string) => {
    const map: Record<string, string> = {
      hackernews: 'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300',
      github:     'bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300',
      arxiv:      'bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300',
      youtube:    'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300',
      twitter:    'bg-sky-100 dark:bg-sky-900/30 text-sky-700 dark:text-sky-300',
    }
    return map[type || ''] || 'bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300'
  }
  const sourceLabel = (type?: string) => ({ hackernews: 'HN', github: 'GitHub', arxiv: 'arXiv', youtube: 'YouTube', twitter: 'X' }[type || ''] || 'Feed')

  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref as React.RefObject<HTMLElement>)

  return (
    <section id="trending" ref={ref} className="relative py-24 bg-white dark:bg-slate-950">
      <div className="absolute inset-x-0 top-0 h-16 bg-gradient-to-b from-slate-50 dark:from-slate-900/50 to-transparent pointer-events-none" />
      <div className="absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-slate-50 dark:from-slate-900/50 to-transparent pointer-events-none" />
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-indigo-600 dark:text-indigo-400 mb-3">
            <TrendingUp size={12} /> Live Trending
          </div>
          <h2 className="text-4xl font-black text-slate-900 dark:text-white mb-3">
            What's trending in tech right now
          </h2>
          <p className="text-slate-600 dark:text-slate-400">Updated every 30 minutes from Hacker News, GitHub, arXiv, X/Twitter and YouTube.</p>
        </div>
        <div className={`grid sm:grid-cols-2 lg:grid-cols-3 gap-4 transition-all duration-700 ${inView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-6'}`}>
          {displayItems.slice(0, 6).map((item, i) => (
            <div key={item.id || i} className="bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 rounded-xl p-4 hover:shadow-md transition-all hover:-translate-y-0.5">
              <div className="flex items-center justify-between gap-2 mb-2">
                <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${sourceColor(item.source_type)}`}>
                  {sourceLabel(item.source_type)}
                </span>
                {item.stars && (
                  <span className="flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400 font-semibold">
                    <Star size={10} className="fill-amber-400 text-amber-400" />
                    {item.stars >= 1000 ? `${(item.stars / 1000).toFixed(1)}k` : item.stars}
                  </span>
                )}
              </div>
              <p className="text-sm font-semibold text-slate-800 dark:text-slate-200 line-clamp-2 leading-snug">
                {item.title}
              </p>
            </div>
          ))}
        </div>
        <div className="text-center mt-8">
          <Link href="/register" className="inline-flex items-center gap-2 text-sm font-semibold text-indigo-600 dark:text-indigo-400 hover:text-indigo-500 dark:hover:text-indigo-300 transition-colors">
            See the full feed after signing up <ArrowRight size={14} />
          </Link>
        </div>
      </div>
    </section>
  )
}

// ─── Final CTA ────────────────────────────────────────────────────────────────

function CTASection() {
  return (
    <section className="py-24 relative overflow-hidden isolate bg-gradient-to-br from-indigo-600 via-violet-700 to-purple-800">
      {/* Dot grid overlay */}
      <div className="absolute inset-0 opacity-20 pointer-events-none" style={{ backgroundImage: 'radial-gradient(circle at 2px 2px, white 1px, transparent 0)', backgroundSize: '32px 32px' }} />
      {/* Top fade from previous section */}
      <div className="absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-slate-50/30 dark:from-slate-900/30 to-transparent pointer-events-none" />
      {/* Bottom fade into footer */}
      <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-slate-950/60 to-transparent pointer-events-none" />
      <div className="relative max-w-3xl mx-auto px-4 sm:px-6 text-center">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white/10 border border-white/20 text-white/90 text-xs font-semibold mb-8">
          <Sparkles size={12} /> No credit card required
        </div>
        <h2 className="text-4xl sm:text-5xl font-black text-white mb-5 leading-tight">
          Ready to discover what's next in tech?
        </h2>
        <p className="text-lg text-indigo-100 mb-10">
          Join thousands of engineers, researchers and founders who use SYNAPSE to stay ahead. Free forever, upgrade anytime.
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link href="/register"
            className="flex items-center gap-2 bg-white text-indigo-700 font-bold px-8 py-4 rounded-2xl shadow-xl hover:bg-indigo-50 transition-all hover:scale-[1.02] active:scale-[0.98] text-base">
            Create your account <ArrowRight size={16} />
          </Link>
          <Link href="/login"
            className="text-white/80 hover:text-white font-medium text-sm transition-colors">
            Already have an account? Sign in →
          </Link>
        </div>
      </div>
    </section>
  )
}

// ─── Footer ───────────────────────────────────────────────────────────────────

function Footer() {
  return (
    <footer className="bg-slate-950 border-t border-slate-800/60 py-12">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
              <span className="text-white font-black text-xs">S</span>
            </div>
            <span className="font-black text-base bg-gradient-to-r from-indigo-400 to-violet-400 bg-clip-text text-transparent">
              SYNAPSE
            </span>
            <span className="text-slate-500 text-sm ml-1">· AI-Powered Tech Intelligence</span>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2">
            {[['Features', '#features'], ['Pricing', '#pricing'], ['Trending', '#trending'], ['Log in', '/login'], ['Register', '/register']].map(([label, href]) => (
              <a key={label} href={href}
                className="text-sm text-slate-500 hover:text-slate-300 transition-colors">
                {label}
              </a>
            ))}
          </div>
        </div>
        <div className="mt-8 pt-6 border-t border-slate-800/60 text-center text-xs text-slate-600">
          © {new Date().getFullYear()} SYNAPSE. All rights reserved. Built with ❤️ for the tech community.
        </div>
      </div>
    </footer>
  )
}

// ─── Hero ─────────────────────────────────────────────────────────────────────

function HeroSection() {
  return (
    <section className="relative min-h-screen flex flex-col items-center justify-center pt-16 pb-24 overflow-hidden bg-white dark:bg-slate-950">
      {/* Background blobs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-[600px] h-[600px] rounded-full bg-gradient-to-br from-indigo-400/20 to-violet-600/20 blur-3xl dark:from-indigo-500/10 dark:to-violet-700/10" />
        <div className="absolute -bottom-40 -left-40 w-[500px] h-[500px] rounded-full bg-gradient-to-tr from-cyan-400/15 to-indigo-400/15 blur-3xl dark:from-cyan-500/8 dark:to-indigo-500/8" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] rounded-full bg-gradient-to-r from-violet-400/5 to-indigo-400/5 blur-3xl" />
      </div>
      {/* Bottom fade into StatsSection */}
      <div className="absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-white dark:from-slate-950 to-transparent pointer-events-none" />

      <div className="max-w-5xl mx-auto px-4 sm:px-6 text-center">
        {/* Badge */}
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-200 dark:border-indigo-500/30 text-indigo-700 dark:text-indigo-300 text-xs font-semibold mb-8 animate-fadeIn">
          <Sparkles size={12} className="text-indigo-500" />
          Now with Autonomous AI Agents · Powered by Gemini + OpenRouter
        </div>

        {/* Headline */}
        <h1 className="text-5xl sm:text-6xl lg:text-7xl font-black tracking-tight text-slate-900 dark:text-white mb-6 leading-[1.05]">
          The AI intelligence platform
          <br />
          <span className="bg-gradient-to-r from-indigo-600 via-violet-600 to-cyan-500 bg-clip-text text-transparent">
            built for tech builders
          </span>
        </h1>

        {/* Subtext */}
        <p className="max-w-2xl mx-auto text-lg sm:text-xl text-slate-600 dark:text-slate-400 leading-relaxed mb-10">
          SYNAPSE aggregates articles, research papers, GitHub repos, X/Twitter posts and videos — 
          then lets AI agents research, summarize, and automate so you 
          <span className="font-semibold text-slate-800 dark:text-slate-200"> never miss a breakthrough</span>.
        </p>

        {/* CTAs */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 mb-16">
          <Link href="/register"
            className="flex items-center gap-2 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-bold px-7 py-3.5 rounded-2xl shadow-xl shadow-indigo-500/30 transition-all hover:shadow-indigo-500/50 hover:scale-[1.02] active:scale-[0.98] text-base">
            Start for free <ArrowRight size={16} />
          </Link>
          <Link href="/login"
            className="flex items-center gap-2 bg-white dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 font-semibold px-7 py-3.5 rounded-2xl hover:bg-slate-50 dark:hover:bg-slate-800 transition-all text-base shadow-sm">
            Sign in to workspace
          </Link>
        </div>

        {/* App mockup */}
        <div className="relative max-w-3xl mx-auto">
          <div className="absolute inset-0 bg-gradient-to-b from-transparent to-slate-50 dark:to-slate-950 z-10 bottom-0 h-24 top-auto rounded-b-2xl" />
          <div className="rounded-2xl border border-slate-200 dark:border-slate-700/60 bg-white dark:bg-slate-900 shadow-2xl shadow-black/10 dark:shadow-black/40 overflow-hidden">
            {/* Mockup titlebar */}
            <div className="flex items-center gap-2 px-4 py-3 bg-slate-50 dark:bg-slate-800/80 border-b border-slate-200 dark:border-slate-700/60">
              <div className="flex gap-1.5">
                <div className="w-3 h-3 rounded-full bg-red-400" />
                <div className="w-3 h-3 rounded-full bg-amber-400" />
                <div className="w-3 h-3 rounded-full bg-emerald-400" />
              </div>
              <div className="flex-1 mx-4">
                <div className="h-5 bg-slate-200 dark:bg-slate-700 rounded-md w-48 mx-auto" />
              </div>
              <div className="flex items-center gap-1.5 text-xs font-mono text-emerald-500 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-200 dark:border-emerald-500/20">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                10 tools ready
              </div>
            </div>
            {/* Mockup content */}
            <div className="p-5 text-left font-mono text-xs sm:text-sm space-y-3 bg-slate-950 dark:bg-slate-950">
              <div className="flex items-start gap-3">
                <div className="flex gap-1 mt-1">
                  <div className="w-2 h-2 rounded-full bg-red-400" />
                  <div className="w-2 h-2 rounded-full bg-amber-400" />
                  <div className="w-2 h-2 rounded-full bg-emerald-400" />
                </div>
                <span className="text-slate-400">synapse-agent ~ general</span>
              </div>
              <div className="pl-6 text-slate-300">
                <span className="text-indigo-400">{'>'} </span>
                <span className="text-white">Fetch the top 5 trending ML papers from arXiv this week and generate a PDF summary report</span>
              </div>
              <div className="pl-6 space-y-1.5 text-slate-400">
                <div className="flex items-center gap-2"><span className="text-emerald-400">✓</span> <span>Searching arXiv for recent ML papers…</span></div>
                <div className="flex items-center gap-2"><span className="text-emerald-400">✓</span> <span>Fetched 5 papers · Summarizing with AI…</span></div>
                <div className="flex items-center gap-2"><span className="text-violet-400">⚙</span> <span className="text-violet-300">Generating PDF report via generate_pdf tool…</span></div>
                <div className="flex items-center gap-2 mt-2">
                  <span className="text-emerald-400">✓</span>
                  <span className="text-emerald-300 font-semibold">Done! <span className="underline">ML_Trends_Week13.pdf</span> ready to download</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function LandingPage() {
  const router = useRouter()
  const { isAuthenticated, accessToken } = useAuthStore()
  const [isMounted, setIsMounted] = useState(false)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  // Only redirect to /home if we have BOTH isAuthenticated AND a real token
  useEffect(() => {
    if (isMounted && isAuthenticated && accessToken) {
      router.replace('/home')
    }
  }, [isMounted, isAuthenticated, accessToken, router])

  // While auth state is rehydrating AND user appears logged in → show blank screen
  // to avoid flashing the full landing page before the redirect fires
  if (!isMounted && isAuthenticated) {
    return <div className="min-h-screen bg-slate-950" />
  }

  // Once mounted: if authenticated with token → return null (redirect is in flight)
  if (isMounted && isAuthenticated && accessToken) {
    return <div className="min-h-screen bg-slate-950 flex items-center justify-center">
      <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
    </div>
  }

  return (
    <div className="min-h-screen bg-white dark:bg-slate-950 text-slate-900 dark:text-white overflow-x-hidden">
      <LandingNavbar />
      <HeroSection />
      <StatsSection />
      <FeaturesSection />
      <TrendingSection />
      <PricingSection />
      <CTASection />
      <Footer />
    </div>
  )
}
