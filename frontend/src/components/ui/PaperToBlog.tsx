'use client'

/**
 * Feature #13: Paper-to-Blog AI Converter
 * Turn research papers into readable blog posts.
 */

import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { FileText, Loader2, X, Copy, Check, Download } from 'lucide-react'
import { api } from '@/utils/api'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import toast from 'react-hot-toast'

interface Props {
  paperId:   string
  title:     string
  abstract?: string
  url:       string
}

export function PaperToBlog({ paperId, title, abstract, url }: Props) {
  const [open,    setOpen]    = useState(false)
  const [loading, setLoading] = useState(false)
  const [blog,    setBlog]    = useState('')
  const [copied,  setCopied]  = useState(false)
  const [tone,    setTone]    = useState<'casual' | 'technical' | 'educational'>('casual')

  const generate = async () => {
    setLoading(true)
    setBlog('')
    try {
      const { data } = await api.post('/ai/paper-to-blog/', {
        paper_id:  paperId,
        title,
        abstract:  abstract || '',
        url,
        tone,
      })
      setBlog(data.blog_post || '')
    } catch {
      toast.error('Failed to convert paper')
    } finally {
      setLoading(false)
    }
  }

  const copy = () => {
    navigator.clipboard.writeText(blog)
    setCopied(true)
    toast.success('Blog post copied!')
    setTimeout(() => setCopied(false), 2000)
  }

  const download = () => {
    const blob = new Blob([`# ${title}\n\n${blog}`], { type: 'text/markdown' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href     = url
    a.download = `${title.slice(0, 40).replace(/\s+/g, '-').toLowerCase()}-blog.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <>
      <button
        onClick={() => { setOpen(true); if (!blog) generate() }}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-xs font-medium text-slate-600 dark:text-slate-300 hover:border-indigo-400 hover:text-indigo-600 transition-colors"
      >
        <FileText size={12} /> Blog Post
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
                  <FileText size={18} className="text-indigo-500" /> Paper → Blog Post
                </h2>
                <div className="flex items-center gap-2">
                  {/* Tone selector */}
                  <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-700 rounded-lg p-0.5">
                    {(['casual','technical','educational'] as const).map(t => (
                      <button key={t} onClick={() => { setTone(t); setBlog('') }} className={`px-2 py-1 rounded-md text-xs font-medium capitalize transition-colors ${tone === t ? 'bg-white dark:bg-slate-600 shadow text-indigo-600 dark:text-indigo-400' : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'}`}>
                        {t}
                      </button>
                    ))}
                  </div>
                  <button onClick={() => setOpen(false)} className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700">
                    <X size={18} />
                  </button>
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-5">
                {loading ? (
                  <div className="flex flex-col items-center justify-center py-16 gap-3">
                    <Loader2 size={32} className="animate-spin text-indigo-500" />
                    <p className="text-sm text-slate-500">Converting paper to blog post…</p>
                  </div>
                ) : blog ? (
                  <div className="prose prose-sm dark:prose-invert max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{blog}</ReactMarkdown>
                  </div>
                ) : null}
              </div>

              {blog && (
                <div className="flex items-center gap-2 p-4 border-t border-slate-100 dark:border-slate-700 flex-shrink-0">
                  <button onClick={() => generate()} className="text-sm text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 flex items-center gap-1">
                    <FileText size={14} /> Regenerate ({tone})
                  </button>
                  <div className="ml-auto flex items-center gap-2">
                    <button onClick={download} className="flex items-center gap-1.5 px-3 py-1.5 border border-slate-200 dark:border-slate-700 rounded-lg text-sm text-slate-600 dark:text-slate-300 hover:border-indigo-400 transition-colors">
                      <Download size={14} /> .md
                    </button>
                    <button onClick={copy} className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 text-white rounded-lg text-sm hover:bg-indigo-700 transition-colors">
                      {copied ? <Check size={14} /> : <Copy size={14} />}
                      {copied ? 'Copied!' : 'Copy'}
                    </button>
                  </div>
                </div>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
