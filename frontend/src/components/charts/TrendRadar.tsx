'use client'

/**
 * TrendRadar — Trending topics bar chart (replaces spider chart).
 *
 * The old RadarChart formed a circle when all scores were equal.
 * This uses a clean horizontal bar chart for clear comparison.
 *
 * Props:
 *   data — array of { topic: string; score: number; prevScore?: number }
 */

import React from 'react'
import { SkeletonChart } from '@/components/ui/SkeletonLoader'
import { clsx } from 'clsx'

interface RadarDataPoint {
  topic:      string
  score:      number
  prevScore?: number
}

interface TrendRadarProps {
  data?:      RadarDataPoint[]
  height?:    number
  className?: string
  loading?:   boolean
  title?:     string
}

const DEFAULT_DATA: RadarDataPoint[] = [
  { topic: 'AI/ML',       score: 95, prevScore: 80 },
  { topic: 'Web Dev',     score: 78, prevScore: 82 },
  { topic: 'DevOps',      score: 70, prevScore: 65 },
  { topic: 'Security',    score: 60, prevScore: 55 },
  { topic: 'Data Eng.',   score: 72, prevScore: 60 },
  { topic: 'Mobile',      score: 55, prevScore: 58 },
  { topic: 'Blockchain',  score: 38, prevScore: 50 },
]

const BAR_COLORS = [
  '#6366f1', '#8b5cf6', '#06b6d4', '#10b981',
  '#f59e0b', '#ef4444', '#ec4899', '#f97316',
  '#3b82f6', '#14b8a6', '#a855f7', '#84cc16',
]

export function TrendRadar({
  data    = DEFAULT_DATA,
  height,
  className,
  loading = false,
  title   = 'Technology Trend Radar',
}: TrendRadarProps) {
  if (loading) return <SkeletonChart height={height || 200} className={className} />

  // Sort by score descending, take top 12
  const sorted = [...data].sort((a, b) => b.score - a.score).slice(0, 12)
  const maxScore = sorted[0]?.score || 1

  return (
    <div className={clsx('w-full', className)}>
      {title && (
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">{title}</h3>
      )}
      <div className="space-y-2">
        {sorted.map((d, i) => {
          const pct     = Math.round((d.score / maxScore) * 100)
          const prevPct = d.prevScore != null ? Math.round((d.prevScore / maxScore) * 100) : null
          const delta   = d.prevScore != null ? d.score - d.prevScore : null
          const color   = BAR_COLORS[i % BAR_COLORS.length]

          return (
            <div key={d.topic} className="flex items-center gap-3 group">
              {/* Topic label */}
              <div className="w-24 sm:w-28 shrink-0 text-right">
                <span className="text-xs font-semibold text-slate-600 dark:text-slate-300 truncate block">
                  {d.topic}
                </span>
              </div>

              {/* Bar track */}
              <div className="flex-1 relative h-6 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                {/* Previous period bar (background) */}
                {prevPct != null && (
                  <div
                    className="absolute inset-y-0 left-0 rounded-full opacity-30"
                    style={{ width: `${prevPct}%`, backgroundColor: color }}
                  />
                )}
                {/* Current period bar */}
                <div
                  className="absolute inset-y-0 left-0 rounded-full transition-all duration-500"
                  style={{ width: `${pct}%`, backgroundColor: color }}
                />
                {/* Score label inside bar */}
                <span className="absolute right-2 inset-y-0 flex items-center text-[10px] font-bold text-slate-500 dark:text-slate-400">
                  {d.score}
                </span>
              </div>

              {/* Delta badge */}
              {delta != null && (
                <div className={clsx(
                  'shrink-0 text-[10px] font-bold px-1.5 py-0.5 rounded-full w-12 text-center',
                  delta > 0
                    ? 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400'
                    : delta < 0
                    ? 'bg-red-100 dark:bg-red-900/30 text-red-500 dark:text-red-400'
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-400',
                )}>
                  {delta > 0 ? '+' : ''}{delta}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Legend */}
      {data.some(d => d.prevScore != null) && (
        <div className="flex items-center gap-4 mt-4 text-[10px] text-slate-400">
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-2 rounded-full bg-indigo-500 opacity-100 inline-block" /> Current
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-2 rounded-full bg-indigo-500 opacity-30 inline-block" /> Previous
          </span>
        </div>
      )}
    </div>
  )
}

export default TrendRadar
