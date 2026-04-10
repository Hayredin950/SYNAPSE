'use client'

/**
 * ActivityHeatmap — GitHub-style activity heatmap component.
 * Phase 7.1 — Design System & Animations (Week 19)
 *
 * Renders a 52-week × 7-day grid of coloured cells showing activity intensity.
 */

import React, { useMemo } from 'react'
import { motion } from 'framer-motion'
import { clsx } from 'clsx'

interface ActivityDay {
  date:  string   // ISO date YYYY-MM-DD
  count: number
}

interface ActivityHeatmapProps {
  data?:      ActivityDay[]
  className?: string
  title?:     string
  /** Number of weeks to show (default 26 = 6 months) */
  weeks?:     number
}

// intensity level 0–4
function getLevel(count: number, max: number): number {
  if (count === 0) return 0
  if (max === 0)   return 0
  const ratio = count / max
  if (ratio < 0.25) return 1
  if (ratio < 0.5)  return 2
  if (ratio < 0.75) return 3
  return 4
}

const LEVEL_CLASSES = [
  'bg-slate-100 dark:bg-slate-800',
  'bg-indigo-200 dark:bg-indigo-900/60',
  'bg-indigo-400 dark:bg-indigo-700',
  'bg-indigo-500 dark:bg-indigo-500',
  'bg-indigo-600 dark:bg-indigo-400',
]

const DAY_LABELS = ['Sun', 'Mon', '', 'Wed', '', 'Fri', '']

// Generate dummy data for demo
function generateDemoData(weeks: number): ActivityDay[] {
  const days: ActivityDay[] = []
  const today = new Date()
  for (let i = weeks * 7 - 1; i >= 0; i--) {
    const d = new Date(today)
    d.setDate(d.getDate() - i)
    days.push({
      date: d.toISOString().split('T')[0],
      count: Math.random() < 0.3 ? 0 : Math.floor(Math.random() * 12),
    })
  }
  return days
}

export function ActivityHeatmap({
  data,
  className,
  title = 'Activity',
  weeks = 26,
}: ActivityHeatmapProps) {
  const days = useMemo(() => data ?? generateDemoData(weeks), [data, weeks])
  const max  = useMemo(() => Math.max(...days.map((d) => d.count), 1), [days])

  // Build weeks × days matrix
  const grid: ActivityDay[][] = useMemo(() => {
    const cols: ActivityDay[][] = []
    for (let w = 0; w < weeks; w++) {
      cols.push(days.slice(w * 7, w * 7 + 7))
    }
    return cols
  }, [days, weeks])

  return (
    <div className={clsx('w-full', className)}>
      {title && (
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-3">{title}</h3>
      )}
      <div className="flex gap-0.5 overflow-x-auto pb-1">
        {/* Day labels */}
        <div className="flex flex-col gap-0.5 mr-1 flex-shrink-0">
          {DAY_LABELS.map((label, i) => (
            <div key={i} className="h-3 flex items-center">
              <span className="text-[9px] text-slate-400 dark:text-slate-600 w-6">{label}</span>
            </div>
          ))}
        </div>

        {/* Week columns */}
        {grid.map((week, wi) => (
          <div key={wi} className="flex flex-col gap-0.5 flex-shrink-0">
            {week.map((day, di) => {
              const level = getLevel(day.count, max)
              return (
                <motion.div
                  key={di}
                  title={`${day.date}: ${day.count} activities`}
                  initial={{ opacity: 0, scale: 0.5 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: (wi * 7 + di) * 0.001, duration: 0.2 }}
                  className={clsx(
                    'w-3 h-3 rounded-sm cursor-default transition-all hover:ring-1 hover:ring-indigo-400',
                    LEVEL_CLASSES[level],
                  )}
                />
              )
            })}
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-1.5 mt-2">
        <span className="text-xs text-slate-400 mr-1">Less</span>
        {LEVEL_CLASSES.map((cls, i) => (
          <div key={i} className={clsx('w-3 h-3 rounded-sm', cls)} />
        ))}
        <span className="text-xs text-slate-400 ml-1">More</span>
      </div>
    </div>
  )
}

export default ActivityHeatmap
