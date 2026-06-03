'use client'

/**
 * Feature #23: Reading Timer / Estimated Read Time
 * Shows estimated reading time and elapsed time while reading.
 */

import React, { useState, useEffect, useRef } from 'react'
import { Clock, Play, Pause, RotateCcw } from 'lucide-react'
import { cn } from '@/utils/helpers'

interface Props {
  wordCount?: number
  wpm?: number
  compact?: boolean
  className?: string
}

function estimateReadTime(words: number, wpm: number): string {
  const minutes = Math.ceil(words / wpm)
  if (minutes < 1) return '< 1 min'
  if (minutes === 1) return '1 min'
  return `${minutes} min`
}

export function ReadingTimer({ wordCount = 0, wpm = 250, compact = false, className = '' }: Props) {
  const [elapsed, setElapsed]   = useState(0)
  const [running, setRunning]   = useState(false)
  const intervalRef             = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (running) {
      intervalRef.current = setInterval(() => setElapsed(e => e + 1), 1000)
    } else {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [running])

  const fmt = (s: number) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`

  const estimated = wordCount > 0 ? estimateReadTime(wordCount, wpm) : null

  if (compact) {
    return (
      <span className={cn('flex items-center gap-1 text-xs text-slate-400 dark:text-slate-500', className)}>
        <Clock size={11} />
        {estimated ?? '? min'}
      </span>
    )
  }

  return (
    <div className={cn('flex items-center gap-3', className)}>
      {estimated && (
        <span className="flex items-center gap-1 text-xs text-slate-400 dark:text-slate-500">
          <Clock size={12} /> {estimated} read
        </span>
      )}
      <div className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-100 dark:bg-slate-800 rounded-lg">
        <span className="text-xs font-mono text-slate-700 dark:text-slate-300 w-10">{fmt(elapsed)}</span>
        <button
          onClick={() => setRunning(r => !r)}
          className="text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 transition-colors"
        >
          {running ? <Pause size={12} /> : <Play size={12} />}
        </button>
        <button
          onClick={() => { setRunning(false); setElapsed(0) }}
          className="text-slate-400 hover:text-slate-600 transition-colors"
        >
          <RotateCcw size={11} />
        </button>
      </div>
    </div>
  )
}
