'use client'

/**
 * EmptyState — Reusable empty state component for all list pages.
 *
 * Phase 7.2 — Mobile & Performance (Week 20)
 */

import React from 'react'
import { motion } from 'framer-motion'
import { clsx } from 'clsx'

interface EmptyStateProps {
  icon?:        React.ReactNode
  title:        string
  description?: string
  action?:      React.ReactNode
  className?:   string
  /** Visual size: sm | md | lg */
  size?:        'sm' | 'md' | 'lg'
}

const SIZE = {
  sm: { icon: 'w-10 h-10', iconSize: 'w-5 h-5', title: 'text-sm', desc: 'text-xs' },
  md: { icon: 'w-14 h-14', iconSize: 'w-7 h-7', title: 'text-base', desc: 'text-sm' },
  lg: { icon: 'w-20 h-20', iconSize: 'w-10 h-10', title: 'text-xl', desc: 'text-base' },
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
  size = 'md',
}: EmptyStateProps) {
  const s = SIZE[size]

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={clsx(
        'flex flex-col items-center justify-center py-16 px-6 text-center',
        className,
      )}
    >
      {icon && (
        <div
          className={clsx(
            'rounded-2xl bg-slate-100 dark:bg-slate-800/80 flex items-center justify-center mb-4 text-slate-400 dark:text-slate-500',
            s.icon,
          )}
        >
          <span className={s.iconSize}>{icon}</span>
        </div>
      )}

      <h3 className={clsx('font-semibold text-slate-800 dark:text-slate-200 mb-1', s.title)}>
        {title}
      </h3>

      {description && (
        <p className={clsx('text-slate-500 dark:text-slate-400 max-w-xs mb-5', s.desc)}>
          {description}
        </p>
      )}

      {action}
    </motion.div>
  )
}

// ── Preset empties for common list pages ──────────────────────────────────────

export function EmptyFeed({ onClearFilters }: { onClearFilters?: () => void }) {
  return (
    <EmptyState
      icon={<span className="text-2xl">📰</span>}
      title="No articles found"
      description="Try adjusting your filters or check back later for new content."
      action={
        onClearFilters && (
          <button
            onClick={onClearFilters}
            className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium transition-colors"
          >
            Clear filters
          </button>
        )
      }
    />
  )
}

export function EmptySearch({ query }: { query: string }) {
  return (
    <EmptyState
      icon={<span className="text-2xl">🔍</span>}
      title={`No results for "${query}"`}
      description="Try different keywords or broaden your search terms."
    />
  )
}

export function EmptyBookmarks() {
  return (
    <EmptyState
      icon={<span className="text-2xl">🔖</span>}
      title="No bookmarks yet"
      description="Save articles, repositories, and papers to access them later."
    />
  )
}

export function EmptyDocuments() {
  return (
    <EmptyState
      icon={<span className="text-2xl">📄</span>}
      title="No documents yet"
      description="Use the AI Agent to generate reports, presentations, and more."
    />
  )
}

export function EmptyNotifications() {
  return (
    <EmptyState
      icon={<span className="text-2xl">🔔</span>}
      title="You're all caught up!"
      description="No new notifications. Check back later."
    />
  )
}

export default EmptyState
