'use client'

import React, { memo } from 'react'
import { Play, Eye, ThumbsUp, Clock, Youtube } from 'lucide-react'
import { formatRelativeTime } from '@/utils/helpers'
import { cn } from '@/utils/helpers'

export interface Video {
  id: string
  youtube_id: string
  title: string
  description: string
  summary: string
  channel_name: string
  url: string
  thumbnail_url: string
  duration_seconds: number
  view_count: number
  like_count: number
  published_at: string
  fetched_at: string
  topics: string[] | string
}

function formatViews(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${m}:${String(s).padStart(2, '0')}`
}

function parseTopics(topics: string[] | string): string[] {
  if (Array.isArray(topics)) return topics
  if (typeof topics === 'string') {
    try {
      const parsed = JSON.parse(topics.replace(/'/g, '"'))
      return Array.isArray(parsed) ? parsed : []
    } catch {
      return topics ? [topics] : []
    }
  }
  return []
}

interface VideoCardProps {
  video: Video
  onPlay: (video: Video) => void
}

export const VideoCard = memo(function VideoCard({ video, onPlay }: VideoCardProps) {
  const topics   = parseTopics(video.topics)
  const duration = formatDuration(video.duration_seconds)
  const views    = formatViews(video.view_count)
  const likes    = formatViews(video.like_count)
  const ago      = formatRelativeTime(video.fetched_at || null)

  return (
    <div
      style={{ contain: 'layout style' }}
      className={cn(
        'group relative bg-white dark:bg-slate-800/90 rounded-2xl border border-slate-200 dark:border-slate-700/60',
        'overflow-hidden transition-all duration-200',
        'hover:shadow-xl hover:shadow-red-500/10 hover:border-red-300/60 dark:hover:border-red-500/40',
        'hover:-translate-y-0.5',
      )}
    >
      {/* Thumbnail */}
      <button
        onClick={() => onPlay(video)}
        aria-label={`Play: ${video.title}`}
        className="block w-full relative overflow-hidden text-left focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2"
      >
        {video.thumbnail_url ? (
          <img
            src={video.thumbnail_url}
            alt={video.title}
            loading="lazy"
            decoding="async"
            className="w-full aspect-video object-cover group-hover:scale-105 transition-transform duration-500"
          />
        ) : (
          <div className="w-full aspect-video bg-slate-200 dark:bg-slate-700 flex items-center justify-center">
            <Youtube size={40} className="text-red-500 opacity-60" />
          </div>
        )}
        <div className="absolute bottom-2 right-2 bg-black/80 backdrop-blur-sm text-white text-xs font-mono px-1.5 py-0.5 rounded-md">
          {duration}
        </div>
        <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/20">
          <div className="bg-red-600/95 rounded-full p-3 sm:p-4 shadow-2xl shadow-red-500/40 scale-90 group-hover:scale-100 transition-transform">
            <Play size={20} className="text-white fill-white ml-0.5" />
          </div>
        </div>
      </button>

      {/* Content */}
      <div className="p-3 sm:p-4">
        <button
          onClick={() => onPlay(video)}
          className="block w-full text-left font-semibold text-slate-900 dark:text-white hover:text-red-600 dark:hover:text-red-400 transition-colors line-clamp-2 text-sm leading-snug mb-1.5"
        >
          {video.title}
        </button>

        <p className="text-xs text-red-600 dark:text-red-400 font-semibold mb-2 truncate">
          {video.channel_name}
        </p>

        {video.summary && (
          <p className="text-xs text-slate-600 dark:text-slate-400 line-clamp-2 mb-2.5 leading-relaxed">
            {video.summary}
          </p>
        )}

        {topics.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-2.5">
            {topics.slice(0, 3).map((t) => (
              <span key={t} className="text-xs bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 px-2 py-0.5 rounded-full font-medium capitalize border border-red-100 dark:border-red-800/30 truncate max-w-[90px]">
                {t}
              </span>
            ))}
          </div>
        )}

        <div className="flex items-center flex-wrap gap-x-3 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
          <span className="flex items-center gap-1 whitespace-nowrap"><Eye size={11} /> {views}</span>
          {video.like_count > 0 && <span className="flex items-center gap-1 whitespace-nowrap"><ThumbsUp size={11} /> {likes}</span>}
          <span className="flex items-center gap-1 whitespace-nowrap"><Clock size={11} /> {ago}</span>
        </div>
      </div>
    </div>
  )
})

export function VideoSkeleton() {
  return (
    <div className="bg-white dark:bg-slate-800/90 rounded-2xl border border-slate-200 dark:border-slate-700/60 overflow-hidden animate-pulse">
      <div className="w-full aspect-video bg-slate-200 dark:bg-slate-700" />
      <div className="p-3 sm:p-4 space-y-2.5">
        <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded-lg w-5/6" />
        <div className="h-3 bg-slate-200 dark:bg-slate-700 rounded-lg w-2/5" />
        <div className="h-3 bg-slate-200 dark:bg-slate-700 rounded-lg w-full" />
        <div className="h-3 bg-slate-200 dark:bg-slate-700 rounded-lg w-3/4" />
        <div className="flex gap-2">
          <div className="h-5 bg-slate-200 dark:bg-slate-700 rounded-full w-16" />
          <div className="h-5 bg-slate-200 dark:bg-slate-700 rounded-full w-16" />
        </div>
      </div>
    </div>
  )
}
