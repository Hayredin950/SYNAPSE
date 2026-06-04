'use client'

/**
 * SkeletonLoader — shimmer loading states for all data-fetching components.
 *
 * Phase 7.1 — Design System & Animations (Week 19)
 *
 * Components:
 *   SkeletonCard       — generic card skeleton
 *   SkeletonText       — text line(s) skeleton
 *   SkeletonAvatar     — circular avatar skeleton
 *   SkeletonChart      — chart area skeleton
 *   SkeletonTable      — table rows skeleton
 */

import React from 'react'
import { clsx } from 'clsx'

// ── Base shimmer class ─────────────────────────────────────────────────────────

const shimmer =
  'animate-shimmer bg-gradient-to-r from-slate-200 via-slate-100 to-slate-200 dark:from-slate-700 dark:via-slate-600 dark:to-slate-700 bg-[length:800px_100%] rounded'

// ── SkeletonText ───────────────────────────────────────────────────────────────

export function SkeletonText({
  lines    = 1,
  className,
  lastLineWidth = '60%',
}: {
  lines?:        number
  className?:    string
  lastLineWidth?: string
}) {
  return (
    <div className={clsx('space-y-2', className)}>
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className={clsx(shimmer, 'h-4')}
          style={{ width: i === lines - 1 && lines > 1 ? lastLineWidth : '100%' }}
        />
      ))}
    </div>
  )
}

// ── SkeletonAvatar ─────────────────────────────────────────────────────────────

export function SkeletonAvatar({ size = 36 }: { size?: number }) {
  return (
    <div
      className={clsx(shimmer, 'rounded-full flex-shrink-0')}
      style={{ width: size, height: size }}
    />
  )
}

// ── SkeletonCard ───────────────────────────────────────────────────────────────

export function SkeletonCard({ className }: { className?: string }) {
  return (
    <div
      className={clsx(
        'bg-white dark:bg-slate-800/80 rounded-2xl border border-slate-200/80 dark:border-slate-700/60 p-5 space-y-3',
        className,
      )}
    >
      <div className="flex items-center gap-3">
        <SkeletonAvatar size={40} />
        <div className="flex-1 space-y-2">
          <div className={clsx(shimmer, 'h-4 w-2/3')} />
          <div className={clsx(shimmer, 'h-3 w-1/3')} />
        </div>
      </div>
      <SkeletonText lines={3} />
      <div className="flex gap-2 pt-1">
        <div className={clsx(shimmer, 'h-3 w-16 rounded-full')} />
        <div className={clsx(shimmer, 'h-3 w-12 rounded-full')} />
        <div className={clsx(shimmer, 'h-3 w-20 rounded-full')} />
      </div>
    </div>
  )
}

// ── SkeletonChart ──────────────────────────────────────────────────────────────

export function SkeletonChart({ height = 200, className }: { height?: number; className?: string }) {
  return (
    <div className={clsx('w-full rounded-xl', shimmer, className)} style={{ height }} />
  )
}

// ── SkeletonTable ──────────────────────────────────────────────────────────────

export function SkeletonTable({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="space-y-2">
      {/* Header */}
      <div className="flex gap-4">
        {Array.from({ length: cols }).map((_, i) => (
          <div key={i} className={clsx(shimmer, 'h-4 flex-1 rounded')} />
        ))}
      </div>
      {/* Rows */}
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex gap-4">
          {Array.from({ length: cols }).map((_, c) => (
            <div
              key={c}
              className={clsx(shimmer, 'h-8 flex-1 rounded-lg')}
              style={{ opacity: 1 - r * 0.1 }}
            />
          ))}
        </div>
      ))}
    </div>
  )
}

// ── SkeletonGrid ───────────────────────────────────────────────────────────────

export function SkeletonGrid({ count = 6, cols = 3 }: { count?: number; cols?: number }) {
  return (
    <div
      className="grid gap-4"
      style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}
    >
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  )
}
