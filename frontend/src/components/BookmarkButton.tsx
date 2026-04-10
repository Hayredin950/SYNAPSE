'use client'

import React, { useState } from 'react'
import { Heart } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/utils/api'
import { useAuthStore } from '@/store/authStore'
import { cn } from '@/utils/helpers'
import toast from 'react-hot-toast'

interface BookmarkButtonProps {
  contentType: 'article' | 'repository' | 'researchpaper' | 'tweet'
  objectId: string
  initialBookmarked?: boolean
  className?: string
  size?: number
}

export function BookmarkButton({
  contentType,
  objectId,
  initialBookmarked = false,
  className,
  size = 18,
}: BookmarkButtonProps) {
  const { isAuthenticated } = useAuthStore()
  const [isBookmarked, setIsBookmarked] = useState(initialBookmarked)
  const queryClient = useQueryClient()

  const { mutate, isPending } = useMutation({
    mutationFn: () =>
      api.post(`/bookmarks/${contentType}/${objectId}/`).then(r => r.data),
    onMutate: () => {
      // Optimistic update
      setIsBookmarked(prev => !prev)
    },
    onSuccess: (data) => {
      const bookmarked = data?.data?.bookmarked
      setIsBookmarked(bookmarked)
      toast.success(bookmarked ? 'Bookmarked!' : 'Bookmark removed', {
        style: { background: '#1e293b', color: '#f1f5f9' },
        duration: 1500,
      })
      queryClient.invalidateQueries({ queryKey: ['bookmarks'] })
    },
    onError: () => {
      // Revert optimistic update
      setIsBookmarked(prev => !prev)
      toast.error('Failed to update bookmark', {
        style: { background: '#1e293b', color: '#f1f5f9' },
      })
    },
  })

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (!isAuthenticated) {
      toast.error('Please log in to bookmark', {
        style: { background: '#1e293b', color: '#f1f5f9' },
      })
      return
    }
    mutate()
  }

  return (
    <button
      onClick={handleClick}
      disabled={isPending}
      className={cn(
        'p-1.5 rounded-full transition-all duration-200',
        isBookmarked
          ? 'text-rose-500 hover:text-rose-400'
          : 'text-slate-400 hover:text-rose-400',
        isPending && 'opacity-50 cursor-not-allowed',
        className
      )}
      title={isBookmarked ? 'Remove bookmark' : 'Add bookmark'}
    >
      <Heart
        size={size}
        className={cn('transition-all', isBookmarked && 'fill-current')}
      />
    </button>
  )
}
