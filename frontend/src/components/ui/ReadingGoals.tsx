'use client'

/**
 * Feature #10: Reading Goals — daily article goal + streaks
 * Uses localStorage for persistence. Works offline.
 */

import React, { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import { Target, Flame, CheckCircle2, Plus, Minus, BookOpen, Calendar } from 'lucide-react'

interface GoalData {
  daily:    number   // target articles per day
  read:     number   // read today
  streak:   number   // consecutive days
  lastDate: string   // ISO date of last read
  history:  Record<string, number>  // date -> count
}

const DEFAULT_GOAL: GoalData = { daily: 5, read: 0, streak: 0, lastDate: '', history: {} }

function loadGoal(): GoalData {
  if (typeof window === 'undefined') return DEFAULT_GOAL
  try { return { ...DEFAULT_GOAL, ...JSON.parse(localStorage.getItem('synapse_goal') || '{}') } }
  catch { return DEFAULT_GOAL }
}

function saveGoal(g: GoalData) {
  if (typeof window === 'undefined') return
  localStorage.setItem('synapse_goal', JSON.stringify(g))
  // Also update stats for analytics
  const today = new Date().toISOString().slice(0, 10)
  const history = g.history || {}
  const totalRead = Object.values(history).reduce((a: number, b: any) => a + b, 0)
  const stats = JSON.parse(localStorage.getItem('synapse_reading_stats') || '{}')
  localStorage.setItem('synapse_reading_stats', JSON.stringify({ ...stats, streak: g.streak, totalRead }))
}

interface Props {
  embedded?: boolean  // true = no outer card wrapper
  onArticleRead?: () => void
}

export function ReadingGoals({ embedded = false, onArticleRead }: Props) {
  const [goal, setGoal] = useState<GoalData>(DEFAULT_GOAL)
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    const g = loadGoal()
    const today = new Date().toISOString().slice(0, 10)

    // Reset daily count if new day
    if (g.lastDate && g.lastDate !== today) {
      const yesterday = new Date(); yesterday.setDate(yesterday.getDate() - 1)
      const yStr = yesterday.toISOString().slice(0, 10)
      // Update streak
      const metYesterday = (g.history?.[yStr] ?? 0) >= g.daily
      const newStreak = metYesterday ? g.streak + 1 : 0
      const updated = { ...g, read: 0, streak: newStreak, lastDate: today }
      setGoal(updated)
      saveGoal(updated)
    } else {
      setGoal({ ...g, lastDate: today })
    }
    setMounted(true)
  }, [])

  const recordRead = useCallback(() => {
    const today = new Date().toISOString().slice(0, 10)
    setGoal(prev => {
      const newRead = prev.read + 1
      const history = { ...prev.history, [today]: newRead }
      // Check streak
      let streak = prev.streak
      if (newRead === prev.daily) {
        streak = prev.streak + (prev.lastDate !== today ? 0 : 0) // streak updated at day rollover
      }
      const updated = { ...prev, read: newRead, lastDate: today, history, streak }
      saveGoal(updated)
      return updated
    })
    onArticleRead?.()
  }, [onArticleRead])

  const setTarget = (delta: number) => {
    setGoal(prev => {
      const updated = { ...prev, daily: Math.max(1, Math.min(20, prev.daily + delta)) }
      saveGoal(updated)
      return updated
    })
  }

  if (!mounted) return null

  const pct = Math.min(100, Math.round((goal.read / goal.daily) * 100))
  const met = goal.read >= goal.daily

  const weekDays = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(); d.setDate(d.getDate() - 6 + i)
    const key = d.toISOString().slice(0, 10)
    const count = goal.history?.[key] ?? 0
    return { key, count, met: count >= goal.daily, day: d.toLocaleDateString('en', { weekday: 'short' }) }
  })

  const content = (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
          <Target size={16} className="text-indigo-500" /> Reading Goals
        </h3>
        <div className="flex items-center gap-1 bg-orange-100 dark:bg-orange-900/30 text-orange-600 dark:text-orange-400 px-2 py-1 rounded-lg text-xs font-bold">
          <Flame size={12} /> {goal.streak}d streak
        </div>
      </div>

      {/* Progress ring */}
      <div className="flex items-center gap-4">
        <div className="relative w-20 h-20 flex-shrink-0">
          <svg viewBox="0 0 80 80" className="w-full h-full -rotate-90">
            <circle cx="40" cy="40" r="34" fill="none" stroke="currentColor" strokeWidth="8" className="text-slate-100 dark:text-slate-700" />
            <circle
              cx="40" cy="40" r="34" fill="none"
              stroke={met ? '#10b981' : '#6366f1'} strokeWidth="8"
              strokeLinecap="round"
              strokeDasharray={`${2 * Math.PI * 34}`}
              strokeDashoffset={`${2 * Math.PI * 34 * (1 - pct / 100)}`}
              className="transition-all duration-500"
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            {met
              ? <CheckCircle2 size={24} className="text-emerald-500" />
              : <>
                  <span className="text-lg font-black text-slate-800 dark:text-slate-100">{goal.read}</span>
                  <span className="text-[10px] text-slate-400">/{goal.daily}</span>
                </>
            }
          </div>
        </div>

        <div className="flex-1 space-y-2">
          <div>
            <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
              {met ? '🎉 Goal complete!' : `${goal.daily - goal.read} more to go`}
            </p>
            <p className="text-xs text-slate-400">Daily target: {goal.daily} articles</p>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => setTarget(-1)} className="w-7 h-7 rounded-lg bg-slate-100 dark:bg-slate-700 flex items-center justify-center hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors">
              <Minus size={14} />
            </button>
            <span className="text-sm font-semibold text-slate-700 dark:text-slate-200 w-6 text-center">{goal.daily}</span>
            <button onClick={() => setTarget(1)} className="w-7 h-7 rounded-lg bg-slate-100 dark:bg-slate-700 flex items-center justify-center hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors">
              <Plus size={14} />
            </button>
            <button onClick={recordRead} className="ml-1 flex items-center gap-1 px-3 py-1.5 bg-indigo-600 text-white rounded-lg text-xs font-medium hover:bg-indigo-700 transition-colors">
              <BookOpen size={12} /> +1 Read
            </button>
          </div>
        </div>
      </div>

      {/* Week strip */}
      <div>
        <p className="text-xs text-slate-400 mb-2 flex items-center gap-1"><Calendar size={11} /> This week</p>
        <div className="flex gap-1">
          {weekDays.map(d => (
            <div key={d.key} className="flex-1 flex flex-col items-center gap-1">
              <div className={`w-full aspect-square rounded-md text-center flex items-center justify-center text-[10px] font-bold transition-colors ${
                d.met ? 'bg-indigo-500 text-white' : d.count > 0 ? 'bg-indigo-200 dark:bg-indigo-900/50 text-indigo-600 dark:text-indigo-300' : 'bg-slate-100 dark:bg-slate-700 text-slate-300 dark:text-slate-500'
              }`}>
                {d.count || ''}
              </div>
              <span className="text-[9px] text-slate-400">{d.day.slice(0, 1)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )

  if (embedded) return content
  return (
    <div className="bg-white dark:bg-slate-800 rounded-2xl border border-slate-200 dark:border-slate-700 p-5">
      {content}
    </div>
  )
}

export { loadGoal, saveGoal }
