'use client'

/**
 * Feature #34: Discussion Threads
 * In-app comments on any article/paper/repo.
 */

import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { MessageSquare, Send, Loader2, Trash2, ChevronDown, ChevronUp } from 'lucide-react'
import { api } from '@/utils/api'
import { cn } from '@/utils/helpers'
import toast from 'react-hot-toast'

interface Comment {
  id:         string
  user_id:    string
  username:   string
  text:       string
  created_at: string
  upvotes:    number
}

interface Props {
  articleId: string
}

function timeAgo(iso: string) {
  const sec = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (sec < 60) return 'just now'
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`
  return `${Math.floor(sec / 86400)}d ago`
}

export function CommentsSection({ articleId }: Props) {
  const [open,  setOpen]  = useState(false)
  const [text,  setText]  = useState('')
  const qc = useQueryClient()

  const { data, isLoading } = useQuery<{ comments: Comment[]; count: number }>({
    queryKey: ['comments', articleId],
    queryFn: () => api.get(`/social/comments/?article_id=${articleId}`).then(r => r.data),
    enabled: open,
    staleTime: 30000,
  })

  const postMutation = useMutation({
    mutationFn: (text: string) => api.post('/social/comments/', { article_id: articleId, text }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['comments', articleId] })
      setText('')
      toast.success('Comment posted!')
    },
    onError: () => toast.error('Failed to post comment'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/social/comments/${id}/?article_id=${articleId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['comments', articleId] }),
    onError: () => toast.error('Failed to delete comment'),
  })

  const comments = data?.comments ?? []
  const count    = data?.count ?? 0

  return (
    <div className="border-t border-slate-100 dark:border-slate-700 mt-4 pt-3">
      {/* Toggle */}
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
      >
        <MessageSquare size={14} />
        <span>{count || (open && comments.length) || 0} comment{count !== 1 ? 's' : ''}</span>
        {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <div className="pt-3 space-y-3">
              {/* Input */}
              <div className="flex gap-2">
                <input
                  value={text}
                  onChange={e => setText(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && text.trim()) { e.preventDefault(); postMutation.mutate(text.trim()) }}}
                  placeholder="Add a comment… (Enter to send)"
                  maxLength={500}
                  className="flex-1 px-3 py-2 text-sm border border-slate-200 dark:border-slate-600 rounded-lg bg-slate-50 dark:bg-slate-700 text-slate-800 dark:text-slate-200 focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                />
                <button
                  onClick={() => text.trim() && postMutation.mutate(text.trim())}
                  disabled={!text.trim() || postMutation.isPending}
                  className="px-3 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
                >
                  {postMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                </button>
              </div>

              {/* List */}
              {isLoading ? (
                <div className="py-4 text-center"><Loader2 size={20} className="animate-spin text-slate-400 mx-auto" /></div>
              ) : comments.length === 0 ? (
                <p className="text-xs text-slate-400 py-2">No comments yet. Be the first!</p>
              ) : (
                <div className="space-y-2 max-h-60 overflow-y-auto">
                  {comments.map(c => (
                    <div key={c.id} className="flex gap-2 group">
                      <div className="w-7 h-7 rounded-full bg-indigo-100 dark:bg-indigo-900/40 flex items-center justify-center text-xs font-bold text-indigo-600 dark:text-indigo-400 flex-shrink-0 uppercase">
                        {c.username.slice(0, 1)}
                      </div>
                      <div className="flex-1 bg-slate-50 dark:bg-slate-700/50 rounded-xl px-3 py-2">
                        <div className="flex items-center gap-2 mb-0.5">
                          <span className="text-xs font-semibold text-slate-700 dark:text-slate-200">{c.username}</span>
                          <span className="text-[10px] text-slate-400">{timeAgo(c.created_at)}</span>
                          <button
                            onClick={() => deleteMutation.mutate(c.id)}
                            className="ml-auto opacity-0 group-hover:opacity-100 p-1 hover:text-red-500 transition-all"
                          >
                            <Trash2 size={11} />
                          </button>
                        </div>
                        <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">{c.text}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
