'use client'

/**
 * Feature #33: "Trending in Community"
 * Shows top upvoted/trending content as a social reading feed.
 *
 * Full-width panel: header + responsive grid of ranked cards so the strip
 * fills the horizontal space of the dashboard between the main columns and
 * the video rail.
 */

import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Users, TrendingUp, ExternalLink, ThumbsUp, Loader2 } from 'lucide-react'
import { api } from '@/utils/api'
import { cn } from '@/utils/helpers'

interface NetworkArticle {
  id:          string
  title:       string
  url:         string
  summary?:    string
  upvotes:     number
  source_type?: string
  scraped_at?: string
}

const RANK_BADGES = [
  'bg-gradient-to-br from-amber-400 to-orange-500 text-white shadow-sm',
  'bg-gradient-to-br from-slate-400 to-slate-500 text-white shadow-sm',
  'bg-gradient-to-br from-amber-700 to-amber-900 text-white shadow-sm',
]

export function NetworkReading() {
  const { data, isLoading } = useQuery({
    queryKey: ['network-reading'],
    queryFn: () => api.get('/social/network-reading/').then(r => r.data?.articles ?? []),
    staleTime: 2 * 60000,
  })

  const articles: NetworkArticle[] = Array.isArray(data) ? data : []

  return (
    <div className="rounded-2xl border border-slate-200 dark:border-slate-700/60 bg-white dark:bg-slate-800/80 p-4 sm:p-5 shadow-card dark:shadow-none">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-indigo-100 dark:bg-indigo-900/40 flex items-center justify-center">
            <Users size={15} className="text-indigo-600 dark:text-indigo-400" />
          </div>
          <div>
            <h3 className="font-semibold text-sm sm:text-base text-slate-800 dark:text-slate-100 flex items-center gap-2">
              Trending in Community
              <span className="text-[10px] bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 px-2 py-0.5 rounded-full font-medium flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" /> Live
              </span>
            </h3>
            <p className="text-xs text-slate-400 dark:text-slate-500">What your network is upvoting</p>
          </div>
        </div>
        {articles.length > 0 && (
          <span className="hidden sm:flex items-center gap-1 text-xs text-slate-400 dark:text-slate-500">
            <TrendingUp size={13} className="text-rose-500" />
            Updated live
          </span>
        )}
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="rounded-xl border border-slate-100 dark:border-slate-700/60 p-3 animate-pulse">
              <div className="w-6 h-6 rounded-lg bg-slate-200 dark:bg-slate-700 mb-2" />
              <div className="h-3 bg-slate-200 dark:bg-slate-700 rounded mb-1.5" />
              <div className="h-3 bg-slate-200 dark:bg-slate-700 rounded w-3/4" />
              <div className="h-2.5 bg-slate-100 dark:bg-slate-700/50 rounded mt-2 w-1/2" />
            </div>
          ))}
        </div>
      ) : articles.length === 0 ? (
        <p className="text-sm text-slate-400 py-8 text-center">
          No trending content yet. Upvote articles to show them here!
        </p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {articles.slice(0, 8).map((a, i) => (
            <motion.a
              key={a.id}
              href={a.url}
              target="_blank"
              rel="noopener noreferrer"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.04 }}
              className="group flex items-start gap-3 p-3 rounded-xl border border-slate-100 dark:border-slate-700/60 bg-white dark:bg-slate-800 hover:border-indigo-300 dark:hover:border-indigo-600/60 hover:shadow-lg hover:shadow-indigo-500/5 hover:-translate-y-0.5 transition-all duration-200"
            >
              {/* Rank */}
              <div className={cn(
                'w-7 h-7 rounded-lg flex items-center justify-center text-xs font-black flex-shrink-0',
                RANK_BADGES[i] ?? 'bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-300'
              )}>
                {i + 1}
              </div>

              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-slate-700 dark:text-slate-200 line-clamp-2 leading-snug group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
                  {a.title}
                </p>
                <div className="flex items-center gap-2 mt-1.5">
                  {a.source_type && (
                    <span className="text-[9px] uppercase tracking-wide text-slate-400 capitalize">{a.source_type}</span>
                  )}
                  {a.upvotes > 0 && (
                    <span className="flex items-center gap-0.5 text-[9px] font-medium text-slate-400 dark:text-slate-500">
                      <ThumbsUp size={9} className="text-indigo-400" /> {a.upvotes}
                    </span>
                  )}
                  <ExternalLink size={10} className="text-slate-300 dark:text-slate-600 ml-auto opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
              </div>
            </motion.a>
          ))}
        </div>
      )}
    </div>
  )
}
