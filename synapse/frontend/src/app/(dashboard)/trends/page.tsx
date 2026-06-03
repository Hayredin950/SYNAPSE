'use client'

/**
 * /trends — Technology Trend Radar
 * Premium UI: live data, category filters, trend bars, sparklines, stats
 */

import React, { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import {
  TrendingUp, Loader2, BarChart2, Zap,
  Cpu, Globe, GitBranch, Brain, Box, ChevronUp, ChevronDown,
  Minus, Activity, Flame, Award, Layers, LineChart as LineChartIcon,
} from 'lucide-react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip as ReTooltip,
  Legend as ReLegend, ResponsiveContainer,
} from 'recharts'
import { api } from '@/utils/api'
import { cn } from '@/utils/helpers'
import dynamic from 'next/dynamic'

// Lazy-load recharts-based charts — avoids loading ~200KB of recharts
// on pages that don't use charts (sidebar navigation is instant).
const TrendRadar = dynamic(
  () => import('@/components/charts/TrendRadar').then(m => ({ default: m.TrendRadar })),
  { ssr: false, loading: () => <div className="h-64 bg-slate-100 dark:bg-slate-700 rounded-2xl animate-pulse" /> },
)
const TopicPieChart = dynamic(
  () => import('@/components/charts/TopicPieChart').then(m => ({ default: m.TopicPieChart })),
  { ssr: false, loading: () => <div className="h-48 bg-slate-100 dark:bg-slate-700 rounded-2xl animate-pulse" /> },
)

// ── Types ─────────────────────────────────────────────────────────────────────

interface TechnologyTrend {
  id: string
  technology_name: string
  date: string
  mention_count: number
  trend_score: number
  category: string
  sources: string[]
}

// ── Constants ─────────────────────────────────────────────────────────────────

const CATEGORY_CONFIG: Record<string, {
  label: string; colour: string; bg: string; border: string;
  activeBg: string; icon: React.ElementType;
}> = {
  all:      { label: 'All',       colour: 'text-slate-700 dark:text-white',        bg: 'bg-slate-200 dark:bg-slate-700',       border: 'border-slate-400 dark:border-slate-500',   activeBg: 'bg-slate-300 dark:bg-slate-600',       icon: Layers },
  language: { label: 'Languages', colour: 'text-cyan-600 dark:text-cyan-400',     bg: 'bg-cyan-500/15',     border: 'border-cyan-500/40', activeBg: 'bg-cyan-500/25',     icon: Cpu },
  ai_ml:    { label: 'AI / ML',   colour: 'text-violet-600 dark:text-violet-400',   bg: 'bg-violet-500/15',   border: 'border-violet-500/40', activeBg: 'bg-violet-500/25', icon: Brain },
  devops:   { label: 'DevOps',    colour: 'text-emerald-600 dark:text-emerald-400',  bg: 'bg-emerald-500/15',  border: 'border-emerald-500/40', activeBg: 'bg-emerald-500/25', icon: Box },
  web:      { label: 'Web',       colour: 'text-amber-600 dark:text-amber-400',    bg: 'bg-amber-500/15',    border: 'border-amber-500/40', activeBg: 'bg-amber-500/25',   icon: Globe },
  general:  { label: 'General',   colour: 'text-slate-500 dark:text-slate-400',    bg: 'bg-slate-500/15',    border: 'border-slate-500/40', activeBg: 'bg-slate-500/25',   icon: GitBranch },
}

// ── API ───────────────────────────────────────────────────────────────────────

interface TrendHistory {
  technologies: string[]
  dates: string[]
  series: { name: string; data: (number | null)[] }[]
}

const fetchTrends = async (): Promise<TechnologyTrend[]> => {
  const { data } = await api.get('/trends/?ordering=-trend_score&limit=100')
  if (Array.isArray(data?.results)) return data.results
  if (Array.isArray(data?.data))    return data.data
  if (Array.isArray(data))          return data
  return []
}

const fetchTrendHistory = async (): Promise<TrendHistory> => {
  const { data } = await api.get('/trends/history/?top=8&days=30')
  return data
}

const triggerAnalysis = async () => {
  await api.post('/trends/trigger/')
}

// ── History Chart colors ───────────────────────────────────────────────────────
const HISTORY_COLORS = [
  '#6366f1', '#06b6d4', '#8b5cf6', '#22c55e',
  '#f59e0b', '#ef4444', '#ec4899', '#14b8a6',
]

// ── TrendBar ──────────────────────────────────────────────────────────────────

function TrendBar({ score, maxScore, colour }: { score: number; maxScore: number; colour: string }) {
  const pct = maxScore > 0 ? Math.min(100, Math.round((score / maxScore) * 100)) : 0
  const barColour = colour.replace('text-', 'bg-')
  return (
    <div className="w-full bg-slate-100 dark:bg-slate-800 rounded-full h-1.5 overflow-hidden">
      <motion.div
        className={cn('h-full rounded-full', barColour)}
        initial={{ width: 0 }}
        animate={{ width: `${pct}%` }}
        transition={{ duration: 0.6, ease: 'easeOut' }}
      />
    </div>
  )
}

// ── RankBadge ─────────────────────────────────────────────────────────────────

function RankBadge({ rank }: { rank: number }) {
  if (rank === 1) return (
    <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-amber-400 to-yellow-500 flex items-center justify-center shrink-0 shadow-lg shadow-amber-500/30">
      <Award size={14} className="text-white dark:text-white fill-white" />
    </div>
  )
  if (rank === 2) return (
    <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-slate-300 to-slate-400 flex items-center justify-center shrink-0">
      <span className="text-xs font-black text-slate-800">2</span>
    </div>
  )
  if (rank === 3) return (
    <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-amber-600 to-amber-700 flex items-center justify-center shrink-0">
      <span className="text-xs font-black text-slate-900 dark:text-white">3</span>
    </div>
  )
  return (
    <div className="w-7 h-7 rounded-lg bg-slate-100 dark:bg-slate-800 flex items-center justify-center shrink-0">
      <span className="text-xs font-bold text-slate-400">#{rank}</span>
    </div>
  )
}

// ── MiniSparkline ─────────────────────────────────────────────────────────────

function MiniSparkline({ score, maxScore, colour }: { score: number; maxScore: number; colour: string }) {
  // Simulate a sparkline with 5 bars using score as anchor
  const bars = [0.4, 0.55, 0.45, 0.75, 1.0].map(m => Math.round((score / maxScore) * 100 * m))
  const barColour = colour.replace('text-', 'bg-')
  return (
    <div className="flex items-end gap-0.5 h-6">
      {bars.map((h, i) => (
        <motion.div
          key={i}
          initial={{ height: 0 }}
          animate={{ height: `${Math.max(15, h)}%` }}
          transition={{ duration: 0.4, delay: i * 0.05 }}
          className={cn('w-1 rounded-sm', barColour, 'opacity-70')}
        />
      ))}
    </div>
  )
}

// ── TrendCard ─────────────────────────────────────────────────────────────────

function TrendCard({ trend, rank, maxScore }: { trend: TechnologyTrend; rank: number; maxScore: number }) {
  const cfg = CATEGORY_CONFIG[trend.category] ?? CATEGORY_CONFIG.general
  const Icon = cfg.icon

  // Score indicator
  const pct = maxScore > 0 ? (trend.trend_score / maxScore) * 100 : 0
  const isHot  = pct >= 80

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, delay: rank * 0.02 }}
      className={cn(
        'group relative bg-white dark:bg-slate-900/80 border rounded-2xl p-4 sm:p-5 transition-all duration-200 overflow-hidden shadow-sm',
        'hover:shadow-xl hover:-translate-y-0.5',
        isHot
          ? 'border-violet-500/40 hover:border-violet-400/60 hover:shadow-violet-500/10'
          : 'border-slate-200 dark:border-slate-700/60 hover:border-slate-400 dark:hover:border-slate-600'
      )}
    >
      {/* Hot glow accent */}
      {isHot && (
        <div className="absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r from-violet-500 via-indigo-500 to-cyan-500 rounded-t-2xl" />
      )}

      <div className="flex items-start gap-3 sm:gap-4">
        <RankBadge rank={rank} />

        <div className="flex-1 min-w-0">
          {/* Header row */}
          <div className="flex items-start justify-between gap-2 mb-2">
            <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-2 min-w-0">
              <h3 className="font-bold text-slate-900 dark:text-white text-sm sm:text-base leading-tight truncate">
                {trend.technology_name}
              </h3>
              <div className="flex items-center gap-1.5 flex-wrap">
                {isHot && (
                  <span className="flex items-center gap-0.5 text-[9px] sm:text-[10px] font-black text-orange-600 dark:text-orange-400 bg-orange-500/15 border border-orange-500/30 px-1.5 py-0.5 rounded-full shrink-0">
                    <Flame size={9} />HOT
                  </span>
                )}
                <span className={cn(
                  'flex items-center gap-1 text-[10px] sm:text-xs px-2 py-0.5 rounded-full font-semibold border shrink-0',
                  cfg.bg, cfg.colour, cfg.border
                )}>
                  <Icon size={10} />
                  {cfg.label}
                </span>
              </div>
            </div>
            {/* Mini sparkline — hidden on xs */}
            <div className="hidden sm:block shrink-0">
              <MiniSparkline score={trend.trend_score} maxScore={maxScore} colour={cfg.colour} />
            </div>
          </div>

          {/* Trend bar */}
          <TrendBar score={trend.trend_score} maxScore={maxScore} colour={cfg.colour} />

          {/* Stats row */}
          <div className="flex items-center gap-x-3 sm:gap-x-4 gap-y-1 mt-2.5 flex-wrap">
            <span className="flex items-center gap-1 text-[10px] sm:text-xs text-slate-500">
              <Zap size={10} className="text-amber-500 shrink-0" />
              Score: <strong className="text-slate-900 dark:text-slate-200 font-bold">{trend.trend_score.toFixed(1)}</strong>
            </span>
            <span className="flex items-center gap-1 text-[10px] sm:text-xs text-slate-500">
              <BarChart2 size={10} className="text-indigo-600 dark:text-indigo-400 shrink-0" />
              <strong className="text-slate-800 dark:text-slate-300 font-bold">{trend.mention_count}</strong> mentions
            </span>
            <span className="text-[10px] sm:text-xs text-slate-400 font-medium">
              {new Date(trend.date).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
            </span>
            {trend.sources?.length > 0 && (
              <div className="flex gap-1">
                {trend.sources.slice(0, 1).map(s => (
                  <span key={s} className="text-[9px] bg-slate-100 dark:bg-slate-800 text-slate-500 px-1.5 py-0.5 rounded border border-slate-200 dark:border-slate-700">
                    {s}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  )
}

// ── StatCard ──────────────────────────────────────────────────────────────────

function StatCard({ label, value, icon: Icon, colour }: { label: string; value: string | number; icon: React.ElementType; colour: string }) {
  return (
    <div className="bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-700/60 rounded-2xl p-3 sm:p-4 flex items-center gap-2 sm:gap-3 overflow-hidden shadow-sm">
      <div className={cn('p-1.5 sm:p-2 rounded-lg sm:rounded-xl shrink-0', colour.replace('text-', 'bg-').replace('400', '500/15'))}>
        <Icon size={16} className={cn('sm:w-[18px] sm:h-[18px]', colour)} />
      </div>
      <div className="min-w-0">
        <p className="text-sm sm:text-xl font-black text-slate-900 dark:text-white leading-tight truncate">{value}</p>
        <p className="text-[10px] sm:text-xs text-slate-500 truncate">{label}</p>
      </div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function TrendsPage() {
  const [category, setCategory] = useState('all')
  const [sortBy, setSortBy] = useState<'score' | 'mentions'>('score')
  const [isTriggering, setIsTriggering] = useState(false)

  const { data: trends = [], isLoading, isError, refetch } = useQuery<TechnologyTrend[]>({
    queryKey: ['trends'],
    queryFn: fetchTrends,
    staleTime: 60_000,
  })

  const { data: historyData } = useQuery<TrendHistory>({
    queryKey: ['trends-history'],
    queryFn: fetchTrendHistory,
    staleTime: 300_000, // 5 min
  })

  // Convert history series to recharts format: [{date, Tech1: score, Tech2: score, ...}]
  const historyChartData = useMemo(() => {
    if (!historyData?.dates?.length) return []
    return historyData.dates.map((date, di) => {
      const point: Record<string, string | number> = {
        date: date.slice(5), // Show MM-DD
      }
      for (const series of historyData.series) {
        const val = series.data[di]
        if (val !== null && val !== undefined) {
          point[series.name] = val
        }
      }
      return point
    })
  }, [historyData])

  // Deduplicate by technology_name — keep highest score entry per tech
  const deduped = React.useMemo(() => {
    const seen = new Map<string, TechnologyTrend>()
    for (const t of trends) {
      const existing = seen.get(t.technology_name)
      if (!existing || t.trend_score > existing.trend_score) {
        seen.set(t.technology_name, t)
      }
    }
    return Array.from(seen.values())
  }, [trends])

  const maxScore = Math.max(...deduped.map(t => t.trend_score), 1)

  const categoryCounts = deduped.reduce((acc, t) => {
    acc[t.category] = (acc[t.category] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  const filtered = deduped
    .filter(t => category === 'all' || t.category === category)
    .sort((a, b) => sortBy === 'score'
      ? b.trend_score - a.trend_score
      : b.mention_count - a.mention_count
    )

  const handleTrigger = async () => {
    setIsTriggering(true)
    try {
      await triggerAnalysis()
      setTimeout(() => { refetch(); setIsTriggering(false) }, 3000)
    } catch {
      setIsTriggering(false)
    }
  }

  const avgScore = deduped.length
    ? Math.round(deduped.reduce((s, t) => s + t.trend_score, 0) / deduped.length)
    : 0
  const topTech = deduped.sort((a,b) => b.trend_score - a.trend_score)[0]?.technology_name ?? '—'

  // ── Chart data derived from real trends ───────────────────────────────────
  const radarData = useMemo(() => {
    // Group by category, average scores
    const catMap: Record<string, { total: number; count: number }> = {}
    for (const t of deduped) {
      const cat = t.category || 'general'
      if (!catMap[cat]) catMap[cat] = { total: 0, count: 0 }
      catMap[cat].total += t.trend_score
      catMap[cat].count += 1
    }
    const catLabels: Record<string, string> = {
      ai_ml: 'AI / ML', language: 'Languages', devops: 'DevOps',
      web: 'Web', general: 'General', security: 'Security',
    }
    return Object.entries(catMap)
      .map(([cat, { total, count }]) => ({
        topic: catLabels[cat] || cat,
        score: Math.round(total / count),
      }))
      .sort((a, b) => b.score - a.score)
      .slice(0, 8)
  }, [deduped])

  const pieData = useMemo(() => {
    // Top 8 technologies by mention_count for the donut chart
    return [...deduped]
      .sort((a, b) => b.mention_count - a.mention_count)
      .slice(0, 8)
      .map(t => ({ topic: t.technology_name, count: t.mention_count }))
  }, [deduped])

  return (
    <div className="flex-1 overflow-y-auto bg-slate-50 dark:bg-slate-950 p-4 sm:p-6">
      <div className="max-w-4xl mx-auto space-y-4 sm:space-y-6 pb-10">

        {/* ── Hero Header ── */}
        <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-indigo-50 via-violet-50/60 to-white dark:from-violet-900/60 dark:via-indigo-900/40 dark:to-slate-900 border border-violet-500/20 p-5 sm:p-7 shadow-sm">
          {/* Decorative blobs */}
          <div className="absolute top-0 right-0 w-48 h-48 bg-violet-500/10 rounded-full -translate-y-16 translate-x-16 blur-2xl pointer-events-none" />
          <div className="absolute bottom-0 left-0 w-32 h-32 bg-indigo-500/10 rounded-full translate-y-8 -translate-x-8 blur-xl pointer-events-none" />

          <div className="relative flex flex-col sm:flex-row sm:items-center justify-between gap-5">
            <div className="min-w-0">
              <div className="flex items-center gap-2 mb-1.5">
                <Activity size={14} className="text-violet-600 dark:text-violet-400" />
                <span className="text-[10px] font-bold text-violet-400 uppercase tracking-widest">Live Radar</span>
              </div>
              <h1 className="text-xl sm:text-3xl font-black text-slate-900 dark:text-white tracking-tight leading-tight mb-1">
                Technology Trends
              </h1>
              <p className="text-slate-500 dark:text-slate-400 text-[11px] sm:text-sm max-w-lg">
                Daily trend scores mined from articles &amp; repositories — updated every 24h
              </p>
            </div>

            <div className="flex gap-2 shrink-0">
              <button
                onClick={handleTrigger}
                disabled={isTriggering}
                className="flex-1 sm:flex-none flex items-center justify-center gap-1.5 px-4 py-2.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-60 text-white text-xs sm:text-sm font-bold rounded-xl transition-all shadow-lg shadow-violet-500/20 whitespace-nowrap"
              >
                {isTriggering
                  ? <><Loader2 size={13} className="animate-spin" /> Analysing…</>
                  : <><Zap size={13} /> Run Analysis</>
                }
              </button>
            </div>
          </div>
        </div>

        {/* ── Stats Grid ── */}
        {trends.length > 0 && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-3">
            <StatCard label="Technologies tracked" value={deduped.length}                 icon={Cpu}        colour="text-indigo-600 dark:text-indigo-400" />
            <StatCard label="AI / ML entries"      value={categoryCounts['ai_ml'] ?? 0}   icon={Brain}      colour="text-violet-600 dark:text-violet-400" />
            <StatCard label="Avg trend score"       value={avgScore}                       icon={BarChart2}  colour="text-cyan-600 dark:text-cyan-400"   />
            <StatCard label="🏆 Top tech"           value={topTech}                        icon={TrendingUp} colour="text-amber-600 dark:text-amber-400"  />
          </div>
        )}

        {/* ── Category Filter Tabs ── */}
        <div className="flex gap-1.5 sm:gap-2 overflow-x-auto scrollbar-hide pb-0.5">
          {Object.entries(CATEGORY_CONFIG).map(([key, cfg]) => {
            const count = key === 'all' ? trends.length : (categoryCounts[key] ?? 0)
            const active = category === key
            const Icon = cfg.icon
            return (
              <button
                key={key}
                onClick={() => setCategory(key)}
                className={cn(
                  'flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all whitespace-nowrap shrink-0',
                  active
                    ? `${cfg.activeBg} ${cfg.colour} ${cfg.border} shadow-sm`
                    : 'bg-slate-100 dark:bg-slate-800/80 text-slate-500 dark:text-slate-400 border-slate-200 dark:border-slate-700 hover:border-slate-400 dark:hover:border-slate-500 hover:text-slate-700 dark:hover:text-slate-200'
                )}
              >
                <Icon size={12} />
                {cfg.label}
                {count > 0 && (
                  <span className={cn(
                    'px-1.5 py-0.5 rounded-full text-[10px] font-black',
                    active ? 'bg-black/20 text-inherit' : 'bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-400'
                  )}>
                    {count}
                  </span>
                )}
              </button>
            )
          })}
        </div>

        {/* ── Visualizations: Radar + Donut ── */}
        {deduped.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.1 }}
            className="grid grid-cols-1 lg:grid-cols-2 gap-4"
          >
            {/* Radar Chart — category scores */}
            <div className="bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-700/60 rounded-2xl p-4 sm:p-5">
              <div className="flex items-center gap-2 mb-1">
                <Activity size={14} className="text-violet-600 dark:text-violet-400" />
                <h3 className="text-sm font-semibold text-slate-800 dark:text-white">Category Radar</h3>
                <span className="text-xs text-slate-500 ml-auto">avg. trend score by category</span>
              </div>
              <TrendRadar
                data={radarData}
                height={260}
                title=""
                loading={isLoading}
              />
            </div>

            {/* Donut Chart — top technologies by mentions */}
            <div className="bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-700/60 rounded-2xl p-4 sm:p-5">
              <div className="flex items-center gap-2 mb-1">
                <Flame size={14} className="text-amber-600 dark:text-amber-400" />
                <h3 className="text-sm font-semibold text-slate-800 dark:text-white">Most Mentioned</h3>
                <span className="text-xs text-slate-500 ml-auto">top 8 by mention count</span>
              </div>
              <TopicPieChart
                data={pieData}
                height={260}
                title=""
                loading={isLoading}
              />
            </div>
          </motion.div>
        )}

        {/* ── History Chart: Score Over Time ── */}
        {historyChartData.length > 1 && historyData?.series && historyData.series.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.2 }}
            className="bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-700/60 rounded-2xl p-4 sm:p-5"
          >
            <div className="flex items-center gap-2 mb-4">
              <LineChartIcon size={14} className="text-cyan-600 dark:text-cyan-400" />
              <h3 className="text-sm font-semibold text-slate-800 dark:text-white">Score Over Time</h3>
              <span className="text-xs text-slate-500 ml-auto">top 8 technologies · last 30 days</span>
            </div>
            <ResponsiveContainer width="100%" height={240}>
              <AreaChart data={historyChartData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  {historyData.series.map((s, i) => (
                    <linearGradient key={s.name} id={`grad-${i}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={HISTORY_COLORS[i % HISTORY_COLORS.length]} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={HISTORY_COLORS[i % HISTORY_COLORS.length]} stopOpacity={0} />
                    </linearGradient>
                  ))}
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
                <XAxis dataKey="date" tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} axisLine={false} tickLine={false} />
                <ReTooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 12, fontSize: 12 }}
                  labelStyle={{ color: '#94a3b8', marginBottom: 4 }}
                  itemStyle={{ color: '#e2e8f0' }}
                />
                <ReLegend wrapperStyle={{ fontSize: 11, paddingTop: 8 }} iconSize={8} iconType="circle" />
                {historyData.series.map((s, i) => (
                  <Area
                    key={s.name}
                    type="monotone"
                    dataKey={s.name}
                    stroke={HISTORY_COLORS[i % HISTORY_COLORS.length]}
                    fill={`url(#grad-${i})`}
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4 }}
                    connectNulls
                  />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          </motion.div>
        )}

        {/* ── Sort Controls ── */}
        {trends.length > 0 && (
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span className="shrink-0">Sort by:</span>
            <button
              onClick={() => setSortBy('score')}
              className={cn('flex items-center gap-1 px-2.5 py-1 rounded-lg border transition-all font-semibold',
                sortBy === 'score'
                  ? 'bg-indigo-600 text-white border-indigo-500'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-700 hover:border-slate-500'
              )}
            >
              <Zap size={11} /> Trend Score
            </button>
            <button
              onClick={() => setSortBy('mentions')}
              className={cn('flex items-center gap-1 px-2.5 py-1 rounded-lg border transition-all font-semibold',
                sortBy === 'mentions'
                  ? 'bg-indigo-600 text-white border-indigo-500'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-700 hover:border-slate-500'
              )}
            >
              <BarChart2 size={11} /> Mentions
            </button>
          </div>
        )}

        {/* ── Content ── */}
        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-24 text-slate-500 gap-3">
            <Loader2 size={32} className="animate-spin text-violet-400" />
            <p className="text-sm">Loading trend data…</p>
          </div>
        ) : isError ? (
          <div className="text-center py-20 bg-slate-100 dark:bg-slate-900/50 rounded-2xl border border-slate-200 dark:border-slate-700">
            <TrendingUp size={44} className="mx-auto mb-3 opacity-20 text-slate-500" />
            <p className="text-slate-400 text-sm mb-4">Could not load trends data.</p>
            <button
              onClick={() => refetch()}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold rounded-xl transition-colors"
            >
              Try Again
            </button>
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-20 bg-slate-100 dark:bg-slate-900/50 rounded-2xl border border-slate-200 dark:border-slate-700">
            <TrendingUp size={44} className="mx-auto mb-3 opacity-20 text-slate-500" />
            {trends.length === 0 ? (
              <>
                <p className="text-slate-700 dark:text-slate-300 font-semibold mb-1">No trend data yet</p>
                <p className="text-slate-500 text-sm mb-4">Run the analysis to populate trend scores from your articles &amp; repos.</p>
                <button
                  onClick={handleTrigger}
                  disabled={isTriggering}
                  className="flex items-center gap-2 px-5 py-2.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-60 text-white text-sm font-semibold rounded-xl transition-all mx-auto"
                >
                  {isTriggering ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
                  {isTriggering ? 'Analysing…' : 'Run Analysis Now'}
                </button>
              </>
            ) : (
              <p className="text-slate-400 text-sm">No trends in this category.</p>
            )}
          </div>
        ) : (
          <AnimatePresence mode="wait">
            <motion.div
              key={category + sortBy}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="space-y-2.5 sm:space-y-3"
            >
              {filtered.map((trend, i) => (
                <TrendCard key={trend.id} trend={trend} rank={i + 1} maxScore={maxScore} />
              ))}
            </motion.div>
          </AnimatePresence>
        )}
      </div>
    </div>
  )
}
