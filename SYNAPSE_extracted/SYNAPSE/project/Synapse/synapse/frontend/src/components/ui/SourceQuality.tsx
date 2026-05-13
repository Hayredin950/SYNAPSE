'use client'

/**
 * Feature #22: Source Quality Scores
 * Rate sources, see quality badges, block low-quality sources.
 */

import React, { useState, useEffect } from 'react'
import { Star, Shield, ShieldAlert, ShieldCheck } from 'lucide-react'
import { cn } from '@/utils/helpers'

const QUALITY_SCORES: Record<string, { score: number; label: string }> = {
  hackernews: { score: 92, label: 'High Signal' },
  arxiv:      { score: 96, label: 'Academic'   },
  github:     { score: 88, label: 'Technical'  },
  reddit:     { score: 65, label: 'Mixed'      },
  youtube:    { score: 72, label: 'Visual'     },
  twitter:    { score: 60, label: 'Mixed'      },
  default:    { score: 75, label: 'Unknown'    },
}

function getSourceScore(source: string) {
  const key = (source || '').toLowerCase()
  return QUALITY_SCORES[key] || QUALITY_SCORES.default
}

interface Props {
  source: string
  size?:  'sm' | 'md'
}

export function SourceQualityBadge({ source, size = 'sm' }: Props) {
  const { score, label } = getSourceScore(source)
  const icon = score >= 85 ? ShieldCheck : score >= 70 ? Shield : ShieldAlert
  const Icon = icon
  const colour = score >= 85 ? 'text-emerald-500' : score >= 70 ? 'text-amber-500' : 'text-red-500'

  if (size === 'sm') {
    return (
      <span title={`Source quality: ${score}/100 (${label})`} className={cn('flex items-center gap-0.5 text-[10px] font-medium', colour)}>
        <Icon size={11} /> {score}
      </span>
    )
  }

  return (
    <div className="flex items-center gap-2 text-sm">
      <Icon size={16} className={colour} />
      <span className="font-medium text-slate-700 dark:text-slate-300">{label}</span>
      <span className={cn('font-bold', colour)}>{score}/100</span>
    </div>
  )
}

// ── Source Rating Manager (for settings) ─────────────────────────────────────

interface RatingEntry {
  source:   string
  rating:   number  // user rating 1-5
  blocked:  boolean
}

export function SourceQualityManager() {
  const [ratings, setRatings] = useState<RatingEntry[]>([])
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
    try { setRatings(JSON.parse(localStorage.getItem('synapse_source_ratings') || '[]')) }
    catch { setRatings([]) }
  }, [])

  const save = (r: RatingEntry[]) => {
    setRatings(r)
    localStorage.setItem('synapse_source_ratings', JSON.stringify(r))
  }

  const rate = (source: string, rating: number) => {
    const existing = ratings.find(r => r.source === source)
    if (existing) {
      save(ratings.map(r => r.source === source ? { ...r, rating } : r))
    } else {
      save([...ratings, { source, rating, blocked: false }])
    }
  }

  const toggleBlock = (source: string) => {
    const existing = ratings.find(r => r.source === source)
    if (existing) {
      save(ratings.map(r => r.source === source ? { ...r, blocked: !r.blocked } : r))
    } else {
      save([...ratings, { source, rating: 3, blocked: true }])
    }
  }

  if (!mounted) return null

  const sources = ['hackernews', 'arxiv', 'github', 'reddit', 'youtube', 'twitter']

  return (
    <div className="space-y-3">
      {sources.map(src => {
        const info     = getSourceScore(src)
        const userRating = ratings.find(r => r.source === src)
        const blocked  = userRating?.blocked ?? false
        return (
          <div key={src} className={cn('flex items-center gap-3 p-3 rounded-xl border transition-all', blocked ? 'border-red-200 dark:border-red-800 opacity-60' : 'border-slate-200 dark:border-slate-700')}>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-slate-700 dark:text-slate-200 capitalize">{src}</span>
                <SourceQualityBadge source={src} />
              </div>
            </div>
            {/* Stars */}
            <div className="flex items-center gap-0.5">
              {[1,2,3,4,5].map(n => (
                <button key={n} onClick={() => rate(src, n)}>
                  <Star size={14} className={cn('transition-colors', (userRating?.rating ?? 0) >= n ? 'text-amber-400 fill-current' : 'text-slate-300 dark:text-slate-600')} />
                </button>
              ))}
            </div>
            <button
              onClick={() => toggleBlock(src)}
              className={cn('text-xs px-2 py-1 rounded-lg border font-medium transition-colors', blocked ? 'bg-red-100 dark:bg-red-900/30 border-red-300 text-red-600 hover:bg-red-50' : 'border-slate-200 dark:border-slate-700 text-slate-400 hover:text-red-500 hover:border-red-300')}
            >
              {blocked ? 'Unblock' : 'Block'}
            </button>
          </div>
        )
      })}
    </div>
  )
}
