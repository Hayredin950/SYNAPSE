'use client'

/**
 * Feature #23: "Catch Me Up" Mode
 * AI brief on what you missed — with day range selection.
 */

import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Zap, Loader2, X, ChevronDown } from 'lucide-react'
import { api } from '@/utils/api'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export function CatchMeUp() {
  const [open,    setOpen]    = useState(false)
  const [days,    setDays]    = useState(3)
  const [loading, setLoading] = useState(false)
  const [brief,   setBrief]   = useState<string>('')
  const [stats,   setStats]   = useState<any>(null)
  const [error,   setError]   = useState('')

  const handleFetch = async () => {
    setLoading(true)
    setError('')
    setBrief('')
    setStats(null)
    try {
      const { data } = await api.get(`/ai/catch-up/?days=${days}`)
      setBrief(data.brief || '')
      setStats(data.stats || null)
    } catch (e: any) {
      setError(e?.response?.data?.error || 'Failed to generate brief')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      {/* Trigger button */}
      <button
        onClick={() => { setOpen(true); if (!brief) handleFetch() }}
        className="group flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-violet-600 to-indigo-600 text-white rounded-xl text-sm font-semibold hover:from-violet-700 hover:to-indigo-700 transition-all shadow-md hover:shadow-lg active:scale-95"
      >
        <Zap size={15} className="group-hover:animate-pulse" />
        Catch Me Up
        <ChevronDown size={14} />
      </button>

      {/* Modal */}
      <AnimatePresence>
        {open && (
          <motion.div
            className="fixed inset-0 z-50 flex items-start justify-center pt-16 px-4 bg-black/60 backdrop-blur-sm"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={e => { if (e.target === e.currentTarget) setOpen(false) }}
          >
            <motion.div
              className="bg-white dark:bg-slate-800 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col"
              initial={{ scale: 0.95, y: -20 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.95, y: -20 }}
            >
              {/* Header */}
              <div className="flex items-center justify-between p-5 border-b border-slate-100 dark:border-slate-700 flex-shrink-0">
                <div>
                  <h2 className="font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
                    <Zap size={18} className="text-violet-500" /> Catch Me Up
                  </h2>
                  <p className="text-xs text-slate-400 mt-0.5">AI-generated brief on what you missed</p>
                </div>
                <div className="flex items-center gap-3">
                  {/* Day selector */}
                  <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-700 rounded-lg p-1">
                    {[1, 3, 7].map(d => (
                      <button
                        key={d}
                        onClick={() => { setDays(d); setBrief(''); setStats(null) }}
                        className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${days === d ? 'bg-white dark:bg-slate-600 shadow text-indigo-600 dark:text-indigo-400' : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'}`}
                      >
                        {d}d
                      </button>
                    ))}
                  </div>
                  <button onClick={() => { setOpen(false); setBrief(''); setStats(null) }} className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700">
                    <X size={18} />
                  </button>
                </div>
              </div>

              {/* Stats bar */}
              {stats && (
                <div className="flex items-center gap-4 px-5 py-3 bg-slate-50 dark:bg-slate-700/50 text-xs text-slate-500 dark:text-slate-400 border-b border-slate-100 dark:border-slate-700 flex-shrink-0">
                  <span>📰 {stats.articles} articles</span>
                  <span>📄 {stats.papers} papers</span>
                  <span>⭐ {stats.repos} repos</span>
                  <span className="ml-auto">Last {stats.days} day{stats.days !== 1 ? 's' : ''}</span>
                </div>
              )}

              {/* Content */}
              <div className="flex-1 overflow-y-auto p-5">
                {loading ? (
                  <div className="flex flex-col items-center justify-center py-16 gap-3">
                    <Loader2 size={32} className="animate-spin text-violet-500" />
                    <p className="text-sm text-slate-500">Analyzing {days} day{days !== 1 ? 's' : ''} of content…</p>
                  </div>
                ) : error ? (
                  <div className="text-center py-8">
                    <p className="text-red-500 text-sm">{error}</p>
                    <button onClick={handleFetch} className="mt-3 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm hover:bg-indigo-700 transition-colors">
                      Retry
                    </button>
                  </div>
                ) : brief ? (
                  <div className="prose prose-sm dark:prose-invert max-w-none prose-headings:font-bold prose-a:text-indigo-600">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{brief}</ReactMarkdown>
                  </div>
                ) : null}
              </div>

              {/* Footer */}
              {brief && (
                <div className="flex items-center justify-between p-4 border-t border-slate-100 dark:border-slate-700 flex-shrink-0">
                  <button onClick={() => { setBrief(''); setStats(null); handleFetch() }} className="text-sm text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 flex items-center gap-1">
                    <Zap size={14} /> Regenerate
                  </button>
                  <button onClick={() => setOpen(false)} className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors">
                    Got it
                  </button>
                </div>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
