'use client'

/**
 * Badge / Tag — reusable pill component.
 *
 * Phase 7.1 — Design System & Animations (Week 19)
 *
 * Colors: default | indigo | cyan | violet | green | yellow | red | orange | pink | slate
 * Sizes:  sm | md
 */

import React from 'react'
import { clsx } from 'clsx'
import { X } from 'lucide-react'

// ── Types ──────────────────────────────────────────────────────────────────────

type BadgeColor =
  | 'default'
  | 'indigo'
  | 'cyan'
  | 'violet'
  | 'green'
  | 'yellow'
  | 'red'
  | 'orange'
  | 'pink'
  | 'slate'

type BadgeSize = 'sm' | 'md'

interface BadgeProps {
  children:    React.ReactNode
  color?:      BadgeColor
  size?:       BadgeSize
  dot?:        boolean         // show a coloured dot prefix
  removable?:  boolean         // show an ✕ button
  onRemove?:   () => void
  className?:  string
  icon?:       React.ReactNode
}

// ── Style map ──────────────────────────────────────────────────────────────────

const COLOR_MAP: Record<BadgeColor, { pill: string; dot: string }> = {
  default: { pill: 'bg-slate-100 dark:bg-slate-700/60 text-slate-600 dark:text-slate-300',         dot: 'bg-slate-400' },
  indigo:  { pill: 'bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400',      dot: 'bg-indigo-500' },
  cyan:    { pill: 'bg-cyan-50 dark:bg-cyan-900/30 text-cyan-600 dark:text-cyan-400',              dot: 'bg-cyan-500' },
  violet:  { pill: 'bg-violet-50 dark:bg-violet-900/30 text-violet-600 dark:text-violet-400',      dot: 'bg-violet-500' },
  green:   { pill: 'bg-green-50 dark:bg-green-900/30 text-green-600 dark:text-green-400',          dot: 'bg-green-500' },
  yellow:  { pill: 'bg-yellow-50 dark:bg-yellow-900/30 text-yellow-600 dark:text-yellow-400',      dot: 'bg-yellow-500' },
  red:     { pill: 'bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-400',                  dot: 'bg-red-500' },
  orange:  { pill: 'bg-orange-50 dark:bg-orange-900/30 text-orange-600 dark:text-orange-400',      dot: 'bg-orange-500' },
  pink:    { pill: 'bg-pink-50 dark:bg-pink-900/30 text-pink-600 dark:text-pink-400',              dot: 'bg-pink-500' },
  slate:   { pill: 'bg-slate-50 dark:bg-slate-800 text-slate-500 dark:text-slate-400',             dot: 'bg-slate-500' },
}

const SIZE_MAP: Record<BadgeSize, string> = {
  sm: 'text-xs px-2 py-0.5 gap-1',
  md: 'text-xs px-2.5 py-1 gap-1.5',
}

// ── Component ──────────────────────────────────────────────────────────────────

export function Badge({
  children,
  color     = 'default',
  size      = 'sm',
  dot       = false,
  removable = false,
  onRemove,
  className,
  icon,
}: BadgeProps) {
  const { pill, dot: dotColor } = COLOR_MAP[color]

  return (
    <span
      className={clsx(
        'inline-flex items-center font-medium rounded-full',
        pill,
        SIZE_MAP[size],
        className,
      )}
    >
      {dot && (
        <span className={clsx('w-1.5 h-1.5 rounded-full flex-shrink-0', dotColor)} />
      )}
      {icon && <span className="flex-shrink-0">{icon}</span>}
      {children}
      {removable && (
        <button
          type="button"
          onClick={onRemove}
          className="flex-shrink-0 ml-0.5 hover:opacity-70 transition-opacity"
          aria-label="Remove"
        >
          <X size={10} />
        </button>
      )}
    </span>
  )
}

export default Badge
