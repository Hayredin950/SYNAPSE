'use client'

/**
 * StarSparkline — compact star-growth sparkline for GitHub repositories.
 *
 * Phase 7.1 — Design System & Animations (Week 19)
 *
 * Uses Recharts AreaChart / LineChart in a tiny, label-free sparkline style.
 *
 * Props:
 *   data        — array of { date: string; stars: number }
 *   height      — sparkline height (default 48)
 *   color       — stroke colour (default indigo)
 *   showTooltip — whether to show tooltip on hover
 */

import React from 'react'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { clsx } from 'clsx'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

// ── Types ──────────────────────────────────────────────────────────────────────

interface StarDataPoint {
  date:  string
  stars: number
}

interface StarSparklineProps {
  data?:         StarDataPoint[]
  height?:       number
  color?:        string
  showTooltip?:  boolean
  className?:    string
  /** Show the latest value + growth badge */
  showSummary?:  boolean
  totalStars?:   number
}

// ── Custom tooltip ─────────────────────────────────────────────────────────────

function SparkTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1 shadow text-xs">
      <span className="text-slate-500">{payload[0]?.payload?.date}</span>
      <span className="ml-2 font-semibold text-slate-900 dark:text-white">
        ★ {payload[0]?.value?.toLocaleString()}
      </span>
    </div>
  )
}

// ── Component ──────────────────────────────────────────────────────────────────

export function StarSparkline({
  data         = [],
  height       = 48,
  color        = '#6366f1',
  showTooltip  = false,
  className,
  showSummary  = false,
  totalStars,
}: StarSparklineProps) {
  if (!data.length) {
    return (
      <div
        className={clsx('flex items-center justify-center text-xs text-slate-400', className)}
        style={{ height }}
      >
        No data
      </div>
    )
  }

  const first = data[0]?.stars ?? 0
  const last  = data[data.length - 1]?.stars ?? 0
  const delta = last - first
  const pct   = first > 0 ? ((delta / first) * 100).toFixed(1) : '0'

  const TrendIcon = delta > 0 ? TrendingUp : delta < 0 ? TrendingDown : Minus
  const trendColor = delta > 0 ? 'text-green-400' : delta < 0 ? 'text-red-400' : 'text-slate-400'

  return (
    <div className={clsx('flex items-center gap-3', className)}>
      {/* Chart */}
      <div style={{ height, flex: 1, minWidth: 60 }}>
        <ResponsiveContainer width="100%" height={height}>
          <AreaChart data={data} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
            <defs>
              <linearGradient id={`sparkGrad-${color.replace('#', '')}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor={color} stopOpacity={0.3} />
                <stop offset="95%" stopColor={color} stopOpacity={0}   />
              </linearGradient>
            </defs>
            <XAxis dataKey="date" hide />
            <YAxis hide domain={['auto', 'auto']} />
            {showTooltip && <Tooltip content={<SparkTooltip />} />}
            <Area
              type="monotone"
              dataKey="stars"
              stroke={color}
              strokeWidth={1.5}
              fill={`url(#sparkGrad-${color.replace('#', '')})`}
              dot={false}
              activeDot={showTooltip ? { r: 3, fill: color } : false}
              isAnimationActive
              animationDuration={800}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Summary badge */}
      {showSummary && (
        <div className="flex flex-col items-end flex-shrink-0">
          {totalStars !== undefined && (
            <span className="text-sm font-semibold text-slate-900 dark:text-white">
              ★ {totalStars >= 1000 ? `${(totalStars / 1000).toFixed(1)}k` : totalStars}
            </span>
          )}
          <span className={clsx('flex items-center gap-0.5 text-xs font-medium', trendColor)}>
            <TrendIcon size={11} />
            {Math.abs(Number(pct))}%
          </span>
        </div>
      )}
    </div>
  )
}

export default StarSparkline
