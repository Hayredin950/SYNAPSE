'use client'

/**
 * Card — reusable card component with optional hover-lift Framer Motion effect.
 *
 * Phase 7.1 — Design System & Animations (Week 19)
 */

import React from 'react'
import { motion, HTMLMotionProps } from 'framer-motion'
import { clsx } from 'clsx'

// ── Types ──────────────────────────────────────────────────────────────────────

interface CardProps extends Omit<HTMLMotionProps<'div'>, 'children'> {
  children:   React.ReactNode
  /** Enable hover lift + border glow effect */
  hoverable?: boolean
  /** Remove default padding */
  noPadding?: boolean
  /** Extra Tailwind classes */
  className?: string
  /** Click handler (adds cursor-pointer) */
  onClick?:   () => void
}

// ── Component ──────────────────────────────────────────────────────────────────

export function Card({
  children,
  hoverable  = false,
  noPadding  = false,
  className,
  onClick,
  ...props
}: CardProps) {
  return (
    <motion.div
      whileHover={hoverable ? { y: -3, boxShadow: '0 8px 32px rgba(0,0,0,0.12)' } : {}}
      transition={{ type: 'spring', stiffness: 300, damping: 24 }}
      onClick={onClick}
      className={clsx(
        'bg-white dark:bg-slate-800/80',
        'rounded-2xl border border-slate-300 dark:border-slate-700/60',
        'transition-colors duration-200',
        !noPadding && 'p-4 sm:p-5',
        hoverable && 'cursor-pointer hover:border-indigo-400 dark:hover:border-indigo-500/30',
        onClick && 'cursor-pointer',
        'w-full min-w-0',
        className,
      )}
      {...props}
    >
      {children}
    </motion.div>
  )
}

// ── Sub-components ─────────────────────────────────────────────────────────────

export function CardHeader({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={clsx('flex items-center justify-between mb-4', className)}>
      {children}
    </div>
  )
}

export function CardTitle({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <h3 className={clsx('font-semibold text-slate-900 dark:text-white text-base', className)}>
      {children}
    </h3>
  )
}

export function CardContent({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return <div className={clsx('', className)}>{children}</div>
}

export function CardFooter({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <div
      className={clsx(
        'mt-4 pt-4 border-t border-slate-200 dark:border-slate-700/60 flex items-center gap-2',
        className,
      )}
    >
      {children}
    </div>
  )
}

export default Card
