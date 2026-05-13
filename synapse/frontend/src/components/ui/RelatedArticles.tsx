'use client'

/**
 * Feature #5: Related Articles Panel
 * Shows similar articles based on topic/tags below the reader.
 */

import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { BookOpen, ExternalLink, Loader2 } from 'lucide-react'
import { api } from '@/utils/api'
import Link from 'next/link'

interface Article {
  id:         string
  title:      string
  url:        string
  summary?:   string
  scraped_at: string
  source_type?: string
}

interface Props {
  articleId: string
  onOpen?:   (a: Article) => void
}

export function RelatedArticles({ articleId, onOpen }: Props) {
  const { data, isLoading } = useQuery({
    queryKey: ['related', articleId],
    queryFn: () => api.get(`/ai/related/?article_id=${articleId}&limit=4`).then(r => r.data?.articles ?? []),
    enabled: !!articleId,
    staleTime: 5 * 60000,
  })

  const articles: Article[] = Array.isArray(data) ? data : []

  if (isLoading) {
    return (
      <div className="py-4 flex items-center gap-2 text-xs text-slate-400">
        <Loader2 size={14} className="animate-spin" /> Finding related articles…
      </div>
    )
  }

  if (articles.length === 0) return null

  return (
    <div className="mt-5 border-t border-slate-100 dark:border-slate-700 pt-4">
      <h4 className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-3 flex items-center gap-1.5">
        <BookOpen size={12} /> Related Articles
      </h4>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {articles.slice(0, 4).map((a, i) => (
          <motion.div
            key={a.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
            className="group flex gap-2 p-3 rounded-xl border border-slate-100 dark:border-slate-700 hover:border-indigo-300 dark:hover:border-indigo-700 bg-white dark:bg-slate-800 cursor-pointer transition-all"
            onClick={() => onOpen?.(a)}
          >
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-slate-700 dark:text-slate-200 line-clamp-2 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
                {a.title}
              </p>
              {a.source_type && (
                <span className="text-[10px] text-slate-400 capitalize mt-0.5 block">{a.source_type}</span>
              )}
            </div>
            <a
              href={a.url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={e => e.stopPropagation()}
              className="flex-shrink-0 text-slate-400 hover:text-indigo-500 transition-colors pt-0.5"
            >
              <ExternalLink size={12} />
            </a>
          </motion.div>
        ))}
      </div>
    </div>
  )
}
