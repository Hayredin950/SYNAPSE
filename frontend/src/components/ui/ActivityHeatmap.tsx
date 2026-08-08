'use client'

import React, { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/utils/api'
import { cn } from '@/utils/helpers'
import { Flame } from 'lucide-react'

const WEEKS = 16
const DAY_LABELS = ['', 'Mon', '', 'Wed', '', 'Fri', '']

function getColor(count: number): string {
  if (count === 0) return 'bg-slate-100 dark:bg-slate-800/80 hover:bg-slate-200 dark:hover:bg-slate-700'
  if (count < 3)  return 'bg-indigo-200 dark:bg-indigo-900 hover:bg-indigo-300 dark:hover:bg-indigo-800'
  if (count < 6)  return 'bg-indigo-400 dark:bg-indigo-700 hover:bg-indigo-500 dark:hover:bg-indigo-600'
  if (count < 10) return 'bg-indigo-500 dark:bg-indigo-500 hover:bg-indigo-600 dark:hover:bg-indigo-400'
  return 'bg-indigo-700 dark:bg-indigo-400 hover:bg-indigo-800 dark:hover:bg-indigo-300'
}

interface Cell {
  date:  string
  count: number
  col:   number
  row:   number
}

export function ActivityHeatmap() {
  const { data, isLoading } = useQuery({
    queryKey: ['user-activity-heatmap'],
    queryFn:  async () => {
      try {
        const { data } = await api.get('/users/activity/?days=120&page_size=500')
        return data
      } catch {
        return null
      }
    },
    staleTime: 5 * 60_000,
    retry: false,
  })

  // Build date → count map
  const countMap = useMemo<Record<string, number>>(() => {
    const map: Record<string, number> = {}
    const activities =
      Array.isArray(data?.results) ? data.results :
      Array.isArray(data?.data)    ? data.data    :
      Array.isArray(data)          ? data          : []

    for (const a of activities) {
      const day = (a.date || a.created_at || '').slice(0, 10)
      if (!day) continue
      // Support both pre-aggregated {date, count} and raw activity objects
      if (typeof a.count === 'number') {
        map[day] = (map[day] || 0) + a.count
      } else {
        map[day] = (map[day] || 0) + 1
      }
    }
    return map
  }, [data])

  // Build grid: WEEKS × 7 days
  const grid = useMemo<Cell[]>(() => {
    const today = new Date()
    const cells: Cell[] = []
    for (let w = WEEKS - 1; w >= 0; w--) {
      for (let d = 0; d < 7; d++) {
        const date = new Date(today)
        date.setDate(today.getDate() - (w * 7 + (6 - d)))
        const dateStr = date.toISOString().slice(0, 10)
        cells.push({ date: dateStr, count: countMap[dateStr] ?? 0, col: WEEKS - 1 - w, row: d })
      }
    }
    return cells
  }, [countMap])

  const totalActivity = useMemo(
    () => Object.values(countMap).reduce((s, c) => s + c, 0),
    [countMap]
  )

  const streak = useMemo(() => {
    let s = 0
    const today = new Date()
    for (let i = 0; i < 365; i++) {
      const d = new Date(today)
      d.setDate(today.getDate() - i)
      const ds = d.toISOString().slice(0, 10)
      if ((countMap[ds] ?? 0) > 0) s++
      else if (i > 0) break
    }
    return s
  }, [countMap])

  if (isLoading) {
    return (
      <div className="bg-white dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 rounded-2xl p-5 animate-pulse">
        <div className="h-4 w-40 bg-slate-200 dark:bg-slate-700 rounded mb-4" />
        <div className="h-24 bg-slate-100 dark:bg-slate-700/50 rounded-xl" />
      </div>
    )
  }

  return (
    <div className="bg-white dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 rounded-2xl p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-bold text-slate-800 dark:text-white flex items-center gap-2">
          <span>Reading Activity</span>
        </h3>
        <div className="flex items-center gap-4 text-xs">
          <span className="text-slate-500 dark:text-slate-400">
            <strong className="text-slate-700 dark:text-slate-200">{totalActivity}</strong> items read
          </span>
          {streak > 0 && (
            <span className="flex items-center gap-1 font-semibold text-indigo-600 dark:text-indigo-400">
              <Flame size={13} className="text-orange-500" />
              {streak}-day streak
            </span>
          )}
        </div>
      </div>

      {/* Grid */}
      <div className="flex gap-1">
        {/* Day labels */}
        <div className="flex flex-col gap-1 mr-1 justify-around">
          {DAY_LABELS.map((label, i) => (
            <span key={i} className="text-[9px] text-slate-400 dark:text-slate-600 leading-none w-5 text-right">
              {label}
            </span>
          ))}
        </div>

        {/* Heatmap cells */}
        <div
          className="grid gap-1 flex-1"
          style={{
            gridTemplateColumns: `repeat(${WEEKS}, minmax(0, 1fr))`,
            gridTemplateRows:    'repeat(7, minmax(0, 1fr))',
          }}
        >
          {grid.map(cell => (
            <div
              key={cell.date}
              title={`${cell.date}: ${cell.count} item${cell.count !== 1 ? 's' : ''}`}
              className={cn(
                'aspect-square rounded-[3px] cursor-default transition-colors',
                getColor(cell.count)
              )}
              style={{ gridColumn: cell.col + 1, gridRow: cell.row + 1 }}
            />
          ))}
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center justify-end gap-1.5 mt-3">
        <span className="text-[10px] text-slate-400 dark:text-slate-500">Less</span>
        {[0, 2, 5, 8, 12].map(c => (
          <div key={c} className={cn('w-3 h-3 rounded-[3px]', getColor(c).split(' ')[0])} />
        ))}
        <span className="text-[10px] text-slate-400 dark:text-slate-500">More</span>
      </div>
    </div>
  )
}
