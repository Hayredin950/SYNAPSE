'use client'

/**
 * Feature #32: Share Digest
 * Generate a public shareable reading digest link.
 */

import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Share2, Copy, Check, Loader2, X } from 'lucide-react'
import { api } from '@/utils/api'
import toast from 'react-hot-toast'

interface Article {
  id:      string
  title:   string
  url:     string
  summary?: string
}

interface Props {
  articles: Article[]
  label?:   string
}

export function ShareDigest({ articles, label = 'Share Digest' }: Props) {
  const [open,    setOpen]    = useState(false)
  const [loading, setLoading] = useState(false)
  const [shareId, setShareId] = useState('')
  const [copied,  setCopied]  = useState(false)
  const [title,   setTitle]   = useState(`My SYNAPSE Digest — ${new Date().toLocaleDateString('en', { month: 'long', day: 'numeric', year: 'numeric' })}`)

  const shareUrl = shareId
    ? `${typeof window !== 'undefined' ? window.location.origin : ''}/digest/${shareId}`
    : ''

  const generate = async () => {
    setLoading(true)
    try {
      const { data } = await api.post('/social/digest/share/', {
        title,
        articles: articles.slice(0, 10).map(a => ({ id: a.id, title: a.title, url: a.url, summary: a.summary })),
      })
      setShareId(data.share_id)
    } catch {
      toast.error('Failed to generate digest')
    } finally {
      setLoading(false)
    }
  }

  const copy = () => {
    navigator.clipboard.writeText(shareUrl).then(() => {
      setCopied(true)
      toast.success('Link copied!')
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-2 px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm text-slate-600 dark:text-slate-300 hover:border-indigo-400 transition-colors"
      >
        <Share2 size={14} /> {label}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={e => { if (e.target === e.currentTarget) { setOpen(false); setShareId('') }}}
          >
            <motion.div
              className="bg-white dark:bg-slate-800 rounded-2xl shadow-2xl w-full max-w-md"
              initial={{ scale: 0.9, y: 20 }} animate={{ scale: 1, y: 0 }}
            >
              <div className="flex items-center justify-between p-5 border-b border-slate-100 dark:border-slate-700">
                <h2 className="font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
                  <Share2 size={18} className="text-indigo-500" /> Share Digest
                </h2>
                <button onClick={() => { setOpen(false); setShareId('') }} className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700">
                  <X size={18} />
                </button>
              </div>

              <div className="p-5 space-y-4">
                <div>
                  <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">Digest Title</label>
                  <input
                    value={title}
                    onChange={e => setTitle(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-slate-200 dark:border-slate-600 rounded-lg bg-slate-50 dark:bg-slate-700 text-slate-800 dark:text-slate-200 focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  />
                </div>

                <div className="text-xs text-slate-500 bg-slate-50 dark:bg-slate-700 rounded-lg p-3">
                  Sharing {Math.min(articles.length, 10)} articles · Link valid for 7 days
                </div>

                {!shareId ? (
                  <button
                    onClick={generate}
                    disabled={loading}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-indigo-600 text-white rounded-xl font-medium hover:bg-indigo-700 disabled:opacity-60 transition-colors"
                  >
                    {loading ? <><Loader2 size={16} className="animate-spin" /> Generating…</> : <><Share2 size={16} /> Generate Share Link</>}
                  </button>
                ) : (
                  <div className="space-y-3">
                    <div className="flex items-center gap-2 p-2 bg-emerald-50 dark:bg-emerald-900/20 rounded-xl border border-emerald-200 dark:border-emerald-800">
                      <span className="flex-1 text-xs text-emerald-700 dark:text-emerald-300 truncate font-mono">{shareUrl}</span>
                      <button onClick={copy} className="flex items-center gap-1 px-2.5 py-1.5 bg-emerald-600 text-white rounded-lg text-xs font-medium hover:bg-emerald-700 transition-colors flex-shrink-0">
                        {copied ? <Check size={12} /> : <Copy size={12} />}
                        {copied ? 'Copied!' : 'Copy'}
                      </button>
                    </div>
                    <p className="text-xs text-slate-400 text-center">Anyone with this link can view your digest</p>
                  </div>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
