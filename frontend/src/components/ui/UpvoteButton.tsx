'use client'

/**
 * Feature #20: Community Upvotes
 * Upvote any article/paper/repo. Count shown inline.
 */

import React, { useState, useEffect } from 'react'
import { ThumbsUp } from 'lucide-react'
import { api } from '@/utils/api'
import toast from 'react-hot-toast'
import { cn } from '@/utils/helpers'

interface Props {
  articleId:    string
  contentType?: string
  initialCount?: number
  size?:         'sm' | 'md'
}

export function UpvoteButton({ articleId, contentType = 'article', initialCount = 0, size = 'sm' }: Props) {
  const [count,   setCount]   = useState(initialCount)
  const [voted,   setVoted]   = useState(false)
  const [loading, setLoading] = useState(false)

  // Load initial state from localStorage for instant feedback
  useEffect(() => {
    if (typeof window === 'undefined') return
    const key = `synapse_upvote_${articleId}`
    setVoted(localStorage.getItem(key) === '1')
  }, [articleId])

  const handleClick = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (loading) return
    setLoading(true)

    // Optimistic update
    const newVoted = !voted
    setVoted(newVoted)
    setCount(c => c + (newVoted ? 1 : -1))

    try {
      const { data } = await api.post('/social/upvote/', { article_id: articleId, content_type: contentType })
      setCount(data.upvote_count ?? count)
      setVoted(data.user_upvoted ?? newVoted)
      if (typeof window !== 'undefined') {
        const key = `synapse_upvote_${articleId}`
        newVoted ? localStorage.setItem(key, '1') : localStorage.removeItem(key)
      }
    } catch {
      // Revert optimistic update
      setVoted(!newVoted)
      setCount(c => c + (newVoted ? -1 : 1))
      toast.error('Failed to upvote')
    } finally {
      setLoading(false)
    }
  }

  const isSmall = size === 'sm'

  return (
    <button
      onClick={handleClick}
      disabled={loading}
      title={voted ? 'Remove upvote' : 'Upvote'}
      className={cn(
        'flex items-center gap-1 rounded-lg border font-medium transition-all',
        isSmall ? 'px-2 py-1 text-xs' : 'px-3 py-1.5 text-sm',
        voted
          ? 'bg-indigo-50 dark:bg-indigo-900/30 border-indigo-300 dark:border-indigo-700 text-indigo-600 dark:text-indigo-400'
          : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-500 dark:text-slate-400 hover:border-indigo-300 hover:text-indigo-500',
        loading && 'opacity-60 cursor-wait',
      )}
    >
      <ThumbsUp size={isSmall ? 12 : 14} className={voted ? 'fill-current' : ''} />
      <span>{count}</span>
    </button>
  )
}
