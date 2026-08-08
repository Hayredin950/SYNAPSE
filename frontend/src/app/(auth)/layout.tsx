'use client'

import React from 'react'
import Link from 'next/link'
import { Zap, Brain, TrendingUp, Shield, Twitter } from 'lucide-react'

const features = [
  { icon: Brain,      title: 'AI-Powered Insights',   desc: 'Intelligent summaries from thousands of tech sources daily' },
  { icon: TrendingUp, title: 'Real-time Trends',       desc: 'Stay ahead with live signals from GitHub, arXiv, X & HN' },
  { icon: Twitter,    title: 'X (Twitter) Feed',       desc: 'Curated tweets on AI, programming, security and tech' },
  { icon: Zap,        title: 'Workflow Automation',    desc: 'Build AI agents that research and report automatically' },
  { icon: Shield,     title: 'Enterprise Ready',       desc: 'SOC2 compliant with SSO, audit logs and team controls' },
]

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex relative
      bg-gradient-to-br from-indigo-50 via-violet-50 to-slate-100
      dark:from-indigo-950 dark:via-violet-950 dark:to-slate-950">

      {/* Glow blobs — visible in dark, subtle in light */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-0 w-[600px] h-[600px] rounded-full blur-[120px] animate-pulse
          bg-indigo-300/30 dark:bg-indigo-600/20" />
        <div className="absolute bottom-0 right-0 w-[500px] h-[500px] rounded-full blur-[100px] animate-pulse
          bg-violet-300/30 dark:bg-violet-600/20" style={{ animationDelay: '1s' }} />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[400px] h-[400px] rounded-full blur-[80px] animate-pulse
          bg-cyan-200/20 dark:bg-cyan-600/10" style={{ animationDelay: '2s' }} />
      </div>

      {/* Grid overlay */}
      <div className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage: 'linear-gradient(rgba(99,102,241,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(99,102,241,0.06) 1px, transparent 1px)',
          backgroundSize: '60px 60px'
        }} />

      {/* ── Left Panel ── */}
      <div className="hidden lg:flex lg:w-1/2 xl:w-3/5 relative flex-col justify-between p-12 overflow-hidden">

        {/* Logo */}
        <div className="relative z-10">
          <Link href="/" className="inline-flex items-center gap-3 group">
            <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-indigo-500 via-violet-500 to-cyan-500 flex items-center justify-center shadow-2xl shadow-indigo-500/30 group-hover:scale-105 transition-transform">
              <span className="text-white font-black text-xl">S</span>
            </div>
            <span className="text-2xl font-black tracking-tight text-indigo-900 dark:text-white">SYNAPSE</span>
          </Link>
        </div>

        {/* Hero text */}
        <div className="relative z-10 space-y-6">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold
            bg-indigo-100 border border-indigo-200 text-indigo-700
            dark:bg-white/5 dark:border-white/10 dark:text-cyan-400">
            <span className="w-1.5 h-1.5 rounded-full animate-pulse bg-indigo-500 dark:bg-cyan-400" />
            Trusted by 10,000+ engineers worldwide
          </div>
          <h2 className="text-4xl xl:text-5xl font-black leading-[1.1] text-slate-900 dark:text-white">
            The intelligence layer<br />
            <span className="bg-gradient-to-r from-indigo-500 via-violet-500 to-cyan-500 bg-clip-text text-transparent">
              for tech builders.
            </span>
          </h2>
          <p className="text-slate-600 dark:text-slate-400 text-lg max-w-md leading-relaxed">
            AI agents that scan, summarise and surface what matters across GitHub, arXiv, X/Twitter, HackerNews and more — so you never miss a breakthrough.
          </p>

          {/* Feature list */}
          <div className="grid grid-cols-1 gap-3 pt-4">
            {features.map(({ icon: Icon, title, desc }) => (
              <div key={title} className="flex items-start gap-3 p-3.5 rounded-xl transition-colors
                bg-white/50 border border-indigo-100 hover:bg-white/70
                dark:bg-white/[0.04] dark:border-white/[0.06] dark:hover:bg-white/[0.07]">
                <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0
                  bg-indigo-100 border border-indigo-200
                  dark:bg-gradient-to-br dark:from-indigo-500/30 dark:to-violet-500/30 dark:border-indigo-500/20">
                  <Icon size={15} className="text-indigo-600 dark:text-indigo-400" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-800 dark:text-white">{title}</p>
                  <p className="text-xs mt-0.5 text-slate-500 dark:text-slate-500">{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Testimonial */}
        <div className="relative z-10">
          <div className="p-5 rounded-2xl
            bg-white/60 border border-indigo-100
            dark:bg-white/[0.04] dark:border-white/[0.08]">
            <p className="text-sm leading-relaxed italic text-slate-600 dark:text-slate-300">
              "SYNAPSE cut my research time by 80%. I get everything I need to know about AI/ML in one feed, every morning."
            </p>
            <div className="flex items-center gap-3 mt-4">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-400 to-violet-400 flex items-center justify-center text-white text-xs font-bold">AK</div>
              <div>
                <p className="text-xs font-semibold text-slate-800 dark:text-white">Alex Kim</p>
                <p className="text-xs text-slate-500">Staff Engineer, Scale AI</p>
              </div>
              <div className="ml-auto flex gap-0.5">
                {[...Array(5)].map((_, i) => <span key={i} className="text-yellow-400 text-xs">★</span>)}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Right Panel ── */}
      <div className="w-full lg:w-1/2 xl:w-2/5 flex flex-col items-center justify-center p-6 sm:p-10 relative">

        {/* Mobile logo */}
        <div className="lg:hidden mb-10 text-center">
          <div className="inline-flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-indigo-500 via-violet-500 to-cyan-500 flex items-center justify-center shadow-lg shadow-indigo-500/30">
              <span className="text-white font-black text-lg">S</span>
            </div>
            <span className="text-2xl font-black tracking-tight text-indigo-900 dark:text-white">SYNAPSE</span>
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400">AI-Powered Technology Intelligence</p>
        </div>

        {/* Form card */}
        <div className="relative w-full max-w-sm">
          <div className="absolute -inset-[1px] rounded-2xl bg-gradient-to-br from-indigo-500/40 via-violet-500/20 to-cyan-500/30" />
          <div className="relative rounded-2xl p-8 backdrop-blur-sm
            bg-white/70 border border-indigo-100/80
            dark:bg-white/[0.03] dark:border-white/[0.1]">
            {children}
          </div>
        </div>

        {/* Footer */}
        <p className="relative mt-8 text-xs text-slate-400 dark:text-slate-500">
          © {new Date().getFullYear()} SYNAPSE ·{' '}
          <Link href="/" className="hover:text-indigo-600 dark:hover:text-white transition-colors">Home</Link>
        </p>
      </div>
    </div>
  )
}
