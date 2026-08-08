'use client'

/**
 * Button — reusable button component with variants and sizes.
 *
 * Phase 7.1 — Design System & Animations (Week 19)
 *
 * Variants: primary | secondary | ghost | destructive | outline
 * Sizes:    sm | md | lg
 */

import React from 'react'
import { motion, HTMLMotionProps } from 'framer-motion'
import { Loader2 } from 'lucide-react'
import { clsx } from 'clsx'

// ── Types ──────────────────────────────────────────────────────────────────────

type Variant = 'primary' | 'secondary' | 'ghost' | 'destructive' | 'outline'
type Size    = 'sm' | 'md' | 'lg'

interface ButtonProps extends Omit<HTMLMotionProps<'button'>, 'children'> {
  variant?:  Variant
  size?:     Size
  loading?:  boolean
  leftIcon?: React.ReactNode
  rightIcon?: React.ReactNode
  children:  React.ReactNode
  fullWidth?: boolean
}

// ── Style maps ─────────────────────────────────────────────────────────────────

const VARIANT_CLASSES: Record<Variant, string> = {
  primary:
    'bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white shadow-sm hover:shadow-glow-indigo border border-indigo-700/50',
  secondary:
    'bg-cyan-600 hover:bg-cyan-700 active:bg-cyan-800 text-white shadow-sm border border-cyan-700/50',
  ghost:
    'bg-transparent hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 border border-transparent',
  destructive:
    'bg-red-600 hover:bg-red-700 active:bg-red-800 text-white shadow-sm hover:shadow-glow-red border border-red-700/50',
  outline:
    'bg-transparent border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/60',
}

const SIZE_CLASSES: Record<Size, string> = {
  sm: 'px-3 py-1.5 text-xs gap-1.5 rounded-lg',
  md: 'px-4 py-2 text-sm gap-2 rounded-xl',
  lg: 'px-6 py-3 text-base gap-2.5 rounded-xl',
}

// ── Component ──────────────────────────────────────────────────────────────────

export function Button({
  variant  = 'primary',
  size     = 'md',
  loading  = false,
  leftIcon,
  rightIcon,
  children,
  fullWidth = false,
  className,
  disabled,
  ...props
}: ButtonProps) {
  const isDisabled = disabled || loading

  return (
    <motion.button
      whileHover={!isDisabled ? { scale: 1.02 } : {}}
      whileTap={!isDisabled ? { scale: 0.97 } : {}}
      transition={{ type: 'spring', stiffness: 400, damping: 25 }}
      disabled={isDisabled}
      className={clsx(
        'inline-flex items-center justify-center font-medium transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-slate-900 select-none',
        VARIANT_CLASSES[variant],
        SIZE_CLASSES[size],
        fullWidth && 'w-full',
        isDisabled && 'opacity-50 cursor-not-allowed pointer-events-none',
        className,
      )}
      {...props}
    >
      {loading ? (
        <Loader2 className="animate-spin flex-shrink-0" size={size === 'sm' ? 13 : size === 'lg' ? 18 : 15} />
      ) : (
        leftIcon && <span className="flex-shrink-0">{leftIcon}</span>
      )}
      <span>{children}</span>
      {!loading && rightIcon && <span className="flex-shrink-0">{rightIcon}</span>}
    </motion.button>
  )
}

export default Button
