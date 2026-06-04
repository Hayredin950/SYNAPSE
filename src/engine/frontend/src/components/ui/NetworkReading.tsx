'use client'

/**
 * Feature #33: "What My Network Is Reading"
 * Shows top upvoted/trending content as social reading feed.
 */

import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Users, TrendingUp, ExternalLink, ThumbsUp, Loader2 } from 'lucide-react'
import { api } from '@/utils/api'
import Link from 'next/link'

interface NetworkArticle {
  id:          string
  title:       string
  url:         string
  summary?:    string
  upvotes:     number
  source_type?: string
  scraped_at?: string
}

export function NetworkReading() {
  const { data, isLoading } = useQuery({
    queryKey: ['network-reading'],
    queryFn: () => api.get('/social/network-reading/').then(r => r.data?.articles ?? []),
    staleTime: 2 * 60000,
  })

  const articles: NetworkArticle[] = Array.isArray(data) ? data : []

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Users size={16} className="text-indigo-500" />
        <h3 className="font-semibold text-sm text-slate-700 dark:text-slate-200">Trending in Community</h3>
        <span className="text-[10px] bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 px-2 py-0.5 rounded-full font-medium">Live</span>
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 py-4 text-sm text-slate-400">
          <Loader2 size={14} className="animate-spin" /> Loading…
        </div>
      ) : articles.length === 0 ? (
        <p className="text-sm text-slate-400 py-4 text-center">No trending content yet. Upvote articles to show them here!</p>
      ) : (
        <div className="space-y-2">
          {articles.slice(0, 8).map((a, i) => (
            <motion.a
              key={a.id}
              href={a.url}
              target="_blank"
              rel="noopener noreferrer"
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.04 }}
              className="group flex items-start gap-3 p-2.5 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors"
            >
              <div className="w-6 h-6 rounded-full bg-gradient-to-br from-indigo-400 to-violet-500 flex items-center justify-center text-white text-[10px] font-black flex-shrink-0">
                {i + 1}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-slate-700 dark:text-slate-200 line-clamp-2 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
                  {a.title}
                </p>
                <div className="flex items-center gap-2 mt-0.5">
                  {a.source_type && <span className="text-[9px] text-slate-400 capitalize">{a.source_type}</span>}
                  {a.upvotes > 0 && (
                    <span className="flex items-center gap-0.5 text-[9px] text-slate-400">
                      <ThumbsUp size={9} /> {a.upvotes}
                    </span>
                  )}
                </div>
              </div>
              <ExternalLink size={11} className="text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 mt-0.5" />
            </motion.a>
          ))}
        </div>
      )}
    </div>
  )
}
