'use client'

/**
 * Feature #17: Activity Heatmap Calendar (GitHub-style)
 * Shows reading activity across the past 52 weeks.
 * Standalone version — not dependent on ActivityHeatmap.tsx
 */

import React, { useMemo } from 'react'
import { cn } from '@/utils/helpers'

interface DayData {
  date: string
  count: number
}

interface Props {
  data?: DayData[]
  className?: string
}

const DAYS = ['Mon', 'Wed', 'Fri']
const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

function getColor(count: number): string {
  if (count === 0) return 'bg-slate-100 dark:bg-slate-800'
  if (count <= 2)  return 'bg-green-200 dark:bg-green-900'
  if (count <= 5)  return 'bg-green-400 dark:bg-green-700'
  if (count <= 10) return 'bg-green-500 dark:bg-green-600'
  return 'bg-green-600 dark:bg-green-500'
}

function buildGrid(data: DayData[]): { weeks: (DayData | null)[][] } {
  const map = new Map(data.map(d => [d.date, d.count]))
  const today = new Date()
  const start = new Date(today)
  start.setDate(start.getDate() - 52 * 7 + 1)

  // Align to Monday
  while (start.getDay() !== 1) start.setDate(start.getDate() - 1)

  const weeks: (DayData | null)[][] = []
  let week: (DayData | null)[] = []
  const cur = new Date(start)

  while (cur <= today) {
    const iso = cur.toISOString().slice(0, 10)
    week.push({ date: iso, count: map.get(iso) ?? 0 })
    if (week.length === 7) {
      weeks.push(week)
      week = []
    }
    cur.setDate(cur.getDate() + 1)
  }
  if (week.length) {
    while (week.length < 7) week.push(null)
    weeks.push(week)
  }

  return { weeks }
}

export function ActivityHeatmapCalendar({ data = [], className }: Props) {
  const { weeks } = useMemo(() => buildGrid(data), [data])

  // Generate dummy data if none provided (demo mode)
  const displayData = useMemo(() => {
    if (data.length > 0) return data
    const arr: DayData[] = []
    const today = new Date()
    for (let i = 0; i < 365; i++) {
      const d = new Date(today)
      d.setDate(d.getDate() - i)
      arr.push({ date: d.toISOString().slice(0, 10), count: Math.random() < 0.4 ? 0 : Math.floor(Math.random() * 8) })
    }
    return arr
  }, [data])

  const { weeks: displayWeeks } = useMemo(() => buildGrid(displayData), [displayData])

  const totalArticles = useMemo(() => displayData.reduce((s, d) => s + d.count, 0), [displayData])

  return (
    <div className={cn('', className)}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-slate-700 dark:text-slate-200">Reading Activity</span>
        <span className="text-xs text-slate-400">{totalArticles} articles read in the past year</span>
      </div>

      {/* Month labels */}
      <div className="flex gap-px mb-1 ml-8 overflow-hidden">
        {displayWeeks.map((week, wi) => {
          const firstDay = week.find(d => d !== null)
          if (!firstDay) return <div key={wi} className="w-3 shrink-0" />
          const d = new Date(firstDay.date)
          const showMonth = d.getDate() <= 7
          return (
            <div key={wi} className="w-3 shrink-0 text-[8px] text-slate-400 truncate">
              {showMonth ? MONTHS[d.getMonth()] : ''}
            </div>
          )
        })}
      </div>

      <div className="flex gap-1">
        {/* Day labels */}
        <div className="flex flex-col gap-px pr-1">
          {[0,1,2,3,4,5,6].map(i => (
            <div key={i} className="h-3 w-6 text-[8px] text-slate-400 flex items-center">
              {i === 0 ? 'Mon' : i === 2 ? 'Wed' : i === 4 ? 'Fri' : ''}
            </div>
          ))}
        </div>

        {/* Grid */}
        <div className="flex gap-px overflow-x-auto scrollbar-hide">
          {displayWeeks.map((week, wi) => (
            <div key={wi} className="flex flex-col gap-px">
              {week.map((day, di) => (
                <div
                  key={di}
                  title={day ? `${day.date}: ${day.count} articles` : ''}
                  className={cn(
                    'w-3 h-3 rounded-sm transition-all cursor-default',
                    day !== null ? getColor(day.count) : 'bg-transparent',
                  )}
                />
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-1.5 mt-2 ml-8 text-[10px] text-slate-400">
        <span>Less</span>
        {['bg-slate-100 dark:bg-slate-800','bg-green-200 dark:bg-green-900','bg-green-400 dark:bg-green-700','bg-green-500 dark:bg-green-600','bg-green-600 dark:bg-green-500'].map((c, i) => (
          <div key={i} className={cn('w-3 h-3 rounded-sm', c)} />
        ))}
        <span>More</span>
      </div>
    </div>
  )
}
