'use client'

/**
 * Feature #14: Research Brief Generator
 * Generate a structured research brief on any topic.
 */

import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Brain, Loader2, X, Copy, Check } from 'lucide-react'
import { api } from '@/utils/api'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import toast from 'react-hot-toast'

export function ResearchBrief() {
  const [open,    setOpen]    = useState(false)
  const [topic,   setTopic]   = useState('')
  const [depth,   setDepth]   = useState<'overview' | 'detailed'>('overview')
  const [loading, setLoading] = useState(false)
  const [brief,   setBrief]   = useState('')
  const [copied,  setCopied]  = useState(false)

  const generate = async () => {
    if (!topic.trim()) { toast.error('Enter a topic first'); return }
    setLoading(true)
    setBrief('')
    try {
      const { data } = await api.post('/ai/research/', { topic, depth })
      setBrief(data.brief || '')
    } catch {
      toast.error('Failed to generate research brief')
    } finally {
      setLoading(false)
    }
  }

  const copy = () => {
    navigator.clipboard.writeText(brief)
    setCopied(true)
    toast.success('Brief copied!')
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-violet-600 to-indigo-600 text-white rounded-xl text-sm font-semibold hover:from-violet-700 hover:to-indigo-700 transition-all shadow-md hover:shadow-lg"
      >
        <Brain size={15} /> Research Brief
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={e => { if (e.target === e.currentTarget) setOpen(false) }}
          >
            <motion.div
              className="bg-white dark:bg-slate-800 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col"
              initial={{ scale: 0.9, y: 20 }} animate={{ scale: 1, y: 0 }}
            >
              <div className="flex items-center justify-between p-5 border-b border-slate-100 dark:border-slate-700 flex-shrink-0">
                <h2 className="font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
                  <Brain size={18} className="text-violet-500" /> Research Brief Generator
                </h2>
                <button onClick={() => setOpen(false)} className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700"><X size={18} /></button>
              </div>

              <div className="p-5 space-y-4 flex-shrink-0">
                <div className="flex gap-3">
                  <input
                    value={topic}
                    onChange={e => setTopic(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') generate() }}
                    placeholder="Enter research topic… (e.g. 'Transformer architecture improvements 2024')"
                    className="flex-1 px-4 py-2.5 border border-slate-200 dark:border-slate-600 rounded-xl bg-slate-50 dark:bg-slate-700 text-slate-800 dark:text-slate-200 focus:ring-2 focus:ring-indigo-500 focus:outline-none text-sm"
                  />
                  <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-700 rounded-xl p-1">
                    {(['overview', 'detailed'] as const).map(d => (
                      <button key={d} onClick={() => setDepth(d)} className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-colors ${depth === d ? 'bg-white dark:bg-slate-600 shadow text-indigo-600 dark:text-indigo-400' : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'}`}>
                        {d}
                      </button>
                    ))}
                  </div>
                </div>
                <button onClick={generate} disabled={!topic.trim() || loading} className="w-full flex items-center justify-center gap-2 py-2.5 bg-violet-600 text-white rounded-xl font-medium hover:bg-violet-700 disabled:opacity-60 transition-colors">
                  {loading ? <><Loader2 size={16} className="animate-spin" /> Generating…</> : <><Brain size={16} /> Generate Brief</>}
                </button>
              </div>

              {(loading || brief) && (
                <div className="flex-1 overflow-y-auto px-5 pb-5">
                  {loading ? (
                    <div className="flex flex-col items-center justify-center py-10 gap-3">
                      <Loader2 size={28} className="animate-spin text-violet-500" />
                      <p className="text-sm text-slate-500">Researching "{topic}"…</p>
                    </div>
                  ) : (
                    <>
                      <div className="prose prose-sm dark:prose-invert max-w-none">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{brief}</ReactMarkdown>
                      </div>
                      <div className="flex justify-end mt-4">
                        <button onClick={copy} className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 text-white rounded-xl text-sm hover:bg-indigo-700 transition-colors">
                          {copied ? <Check size={14} /> : <Copy size={14} />} {copied ? 'Copied!' : 'Copy Brief'}
                        </button>
                      </div>
                    </>
                  )}
                </div>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
