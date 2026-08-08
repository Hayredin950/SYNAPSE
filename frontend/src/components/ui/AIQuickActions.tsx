'use client'

/**
 * Feature #22: AI Quick Actions Floating Bar
 * Floats at the bottom of content pages with quick AI actions.
 */

import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Brain, Zap, ChevronUp, Globe, MessageSquare, Sparkles } from 'lucide-react'
import { api } from '@/utils/api'
import toast from 'react-hot-toast'
import { cn } from '@/utils/helpers'

interface Props {
  articleId?: string
  title?: string
  content?: string
  className?: string
}

export function AIQuickActions({ articleId, title = '', content = '', className = '' }: Props) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState<string | null>(null)
  const [result, setResult] = useState('')
  const [resultLabel, setResultLabel] = useState('')

  const run = async (action: string, label: string, endpoint: string, body: object) => {
    setLoading(action)
    setResult('')
    setResultLabel(label)
    setOpen(true)
    try {
      const { data } = await api.post(endpoint, body)
      setResult(
        data.summary || data.translation || data.blog_post ||
        data.debate?.pro?.join('\n') || data.brief || 'Done!'
      )
    } catch {
      toast.error(`Failed: ${label}`)
    } finally {
      setLoading(null)
    }
  }

  const actions = [
    {
      id: 'summarize',
      label: 'Quick Summary',
      icon: Zap,
      color: 'text-amber-500',
      action: () => run('summarize', 'Summary', '/ai/summarize/', { content, title }),
    },
    {
      id: 'deep-dive',
      label: 'Deep Dive',
      icon: Brain,
      color: 'text-violet-500',
      action: () => run('deep-dive', 'Deep Dive', '/ai/deep-dive/', { content, title, article_id: articleId }),
    },
    {
      id: 'translate',
      label: 'Translate',
      icon: Globe,
      color: 'text-cyan-500',
      action: () => run('translate', 'Translation', '/ai/translate/', { content, target_language: 'Spanish' }),
    },
    {
      id: 'debate',
      label: 'Debate It',
      icon: MessageSquare,
      color: 'text-rose-500',
      action: () => run('debate', 'Debate', '/ai/debate/', { content, title }),
    },
  ]

  return (
    <div className={cn('', className)}>
      <AnimatePresence>
        {open && result && (
          <motion.div
            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 10 }}
            className="mb-2 p-4 bg-white dark:bg-slate-800 rounded-2xl border border-slate-200 dark:border-slate-700 shadow-lg max-h-48 overflow-y-auto text-sm text-slate-700 dark:text-slate-300"
          >
            <div className="flex items-center gap-2 mb-2">
              <Sparkles size={13} className="text-indigo-500" />
              <span className="font-semibold text-xs text-indigo-600 dark:text-indigo-400">{resultLabel}</span>
              <button onClick={() => setOpen(false)} className="ml-auto text-slate-400 hover:text-slate-600 text-xs">✕</button>
            </div>
            {result}
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex flex-wrap gap-2">
        {actions.map(a => (
          <button
            key={a.id}
            onClick={a.action}
            disabled={loading !== null}
            className={cn(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700',
              'text-xs font-medium text-slate-600 dark:text-slate-300',
              'hover:border-indigo-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors',
              'disabled:opacity-50 disabled:cursor-not-allowed',
            )}
          >
            {loading === a.id
              ? <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
              : <a.icon size={12} className={a.color} />
            }
            {a.label}
          </button>
        ))}
      </div>
    </div>
  )
}
