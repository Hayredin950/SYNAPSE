'use client'

/**
 * Feature #24: Smart Collections
 * Auto-organize bookmarks into AI-suggested folders by topic.
 */

import React, { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Folder, BookOpen, Brain, Loader2, ChevronRight, Tag } from 'lucide-react'
import { api } from '@/utils/api'
import { cn } from '@/utils/helpers'

interface Collection {
  name:     string
  emoji:    string
  count:    number
  articles: string[]  // article titles
}

const COLLECTION_EMOJIS: Record<string, string> = {
  'AI & ML':          '🤖',
  'Web Dev':          '🌐',
  'Security':         '🔒',
  'DevOps':           '☁️',
  'Databases':        '🗄️',
  'Open Source':      '💻',
  'Research':         '📄',
  'Performance':      '⚡',
  'Architecture':     '🏗️',
  'Mobile':           '📱',
  'Blockchain':       '⛓️',
  'Tools':            '🔧',
  'Career':           '🚀',
  'Design':           '🎨',
  'Other':            '📂',
}

function groupByTopic(bookmarks: any[]): Collection[] {
  const groups: Record<string, string[]> = {}

  bookmarks.forEach(bm => {
    const item = bm.article || bm.repository || bm.paper || bm.video
    if (!item) return
    const title   = item.title || item.name || ''
    const topic   = item.topic || item.source_type || 'Other'

    const bucket = (
      title.toLowerCase().match(/\b(ai|ml|gpt|llm|neural|deep.learn|machine.learn|transformer)\b/) ? 'AI & ML'
      : title.toLowerCase().match(/\b(react|vue|next\.?js|frontend|css|html|web|typescript|javascript)\b/) ? 'Web Dev'
      : title.toLowerCase().match(/\b(security|hack|vulnerability|exploit|cve|pentest|crypto)\b/) ? 'Security'
      : title.toLowerCase().match(/\b(docker|kubernetes|k8s|devops|ci.?cd|deploy|cloud|aws|gcp|azure)\b/) ? 'DevOps'
      : title.toLowerCase().match(/\b(sql|postgres|mysql|redis|database|mongo|cassandra)\b/) ? 'Databases'
      : title.toLowerCase().match(/\b(open.source|github|git|open.source|community)\b/) ? 'Open Source'
      : title.toLowerCase().match(/\b(paper|research|arxiv|study|survey|benchmark)\b/) ? 'Research'
      : title.toLowerCase().match(/\b(performance|speed|optimize|latency|throughput)\b/) ? 'Performance'
      : title.toLowerCase().match(/\b(architecture|design.pattern|microservice|system.design)\b/) ? 'Architecture'
      : 'Other'
    )
    groups[bucket] = [...(groups[bucket] || []), title]
  })

  return Object.entries(groups)
    .filter(([, items]) => items.length > 0)
    .sort(([, a], [, b]) => b.length - a.length)
    .map(([name, articles]) => ({
      name,
      emoji: COLLECTION_EMOJIS[name] || '📂',
      count: articles.length,
      articles,
    }))
}

export function SmartCollections() {
  const [expanded, setExpanded] = useState<string | null>(null)

  const { data: bookmarks, isLoading } = useQuery({
    queryKey: ['bookmarks-collections'],
    queryFn: () => api.get('/bookmarks/?limit=200').then(r =>
      Array.isArray(r.data?.results) ? r.data.results : []),
    staleTime: 5 * 60000,
  })

  const collections = React.useMemo(() => {
    if (!Array.isArray(bookmarks) || bookmarks.length === 0) return []
    return groupByTopic(bookmarks)
  }, [bookmarks])

  if (isLoading) return (
    <div className="flex items-center gap-2 py-4 text-sm text-slate-400">
      <Loader2 size={16} className="animate-spin" /> Organizing collections…
    </div>
  )

  if (collections.length === 0) return (
    <div className="text-center py-8 text-slate-400">
      <Folder size={32} className="mx-auto mb-2 opacity-40" />
      <p className="text-sm">No bookmarks yet.<br />Save articles to build your collection.</p>
    </div>
  )

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 mb-3">
        <Brain size={14} className="text-violet-500" />
        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">
          {collections.length} Smart Collections · {bookmarks?.length || 0} bookmarks
        </span>
      </div>
      {collections.map((col, i) => (
        <motion.div
          key={col.name}
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.05 }}
          className="rounded-xl border border-slate-100 dark:border-slate-700 overflow-hidden"
        >
          <button
            onClick={() => setExpanded(expanded === col.name ? null : col.name)}
            className="w-full flex items-center gap-3 px-4 py-3 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors text-left"
          >
            <span className="text-lg flex-shrink-0">{col.emoji}</span>
            <span className="flex-1 font-medium text-sm text-slate-700 dark:text-slate-200">{col.name}</span>
            <span className="text-xs text-slate-400 bg-slate-100 dark:bg-slate-700 px-2 py-0.5 rounded-full">{col.count}</span>
            <ChevronRight size={14} className={cn('text-slate-400 transition-transform', expanded === col.name && 'rotate-90')} />
          </button>
          {expanded === col.name && (
            <div className="bg-slate-50 dark:bg-slate-800/50 border-t border-slate-100 dark:border-slate-700 px-4 py-2 space-y-1.5">
              {col.articles.slice(0, 8).map((title, j) => (
                <div key={j} className="flex items-start gap-2">
                  <BookOpen size={11} className="text-slate-400 flex-shrink-0 mt-0.5" />
                  <span className="text-xs text-slate-600 dark:text-slate-400 line-clamp-1">{title}</span>
                </div>
              ))}
              {col.articles.length > 8 && (
                <p className="text-xs text-slate-400 ml-5">+{col.articles.length - 8} more</p>
              )}
            </div>
          )}
        </motion.div>
      ))}
    </div>
  )
}
