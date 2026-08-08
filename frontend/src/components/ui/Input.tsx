'use client'

/**
 * Input — reusable input / textarea component with label + error state.
 *
 * Phase 7.1 — Design System & Animations (Week 19)
 *
 * Types: text | search | email | password | number | textarea
 */

import React, { forwardRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Eye, EyeOff, Search, AlertCircle } from 'lucide-react'
import { clsx } from 'clsx'

// ── Types ──────────────────────────────────────────────────────────────────────

interface BaseProps {
  label?:       string
  error?:       string
  hint?:        string
  leftIcon?:    React.ReactNode
  rightIcon?:   React.ReactNode
  fullWidth?:   boolean
  className?:   string
  wrapperClass?: string
}

export interface InputProps
  extends BaseProps,
    Omit<React.InputHTMLAttributes<HTMLInputElement>, 'className'> {
  as?: 'input'
  type?: 'text' | 'search' | 'email' | 'password' | 'number' | 'url'
}

export interface TextareaProps
  extends BaseProps,
    Omit<React.TextareaHTMLAttributes<HTMLTextAreaElement>, 'className'> {
  as: 'textarea'
  rows?: number
}

type Props = InputProps | TextareaProps

// ── Base classes ───────────────────────────────────────────────────────────────

const BASE =
  'w-full rounded-xl border bg-white dark:bg-slate-800/80 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 placeholder-slate-500 dark:placeholder-slate-500 transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed'

const BORDER_NORMAL = 'border-slate-300 dark:border-slate-700 hover:border-slate-400 dark:hover:border-slate-600'
const BORDER_ERROR  = 'border-red-400 dark:border-red-500 focus:ring-red-400/40 focus:border-red-500'

// ── Component ──────────────────────────────────────────────────────────────────

export const Input = forwardRef<HTMLInputElement | HTMLTextAreaElement, Props>(
  function Input(props, ref) {
    const {
      label,
      error,
      hint,
      leftIcon,
      rightIcon,
      fullWidth = false,
      className,
      wrapperClass,
      ...rest
    } = props

    const [showPassword, setShowPassword] = useState(false)
    const isPassword = (rest as InputProps).type === 'password'
    const isSearch   = (rest as InputProps).type === 'search'
    const isTextarea = (props as TextareaProps).as === 'textarea'

    const inputClass = clsx(
      BASE,
      error ? BORDER_ERROR : BORDER_NORMAL,
      (leftIcon || isSearch) && 'pl-9',
      (rightIcon || isPassword) && 'pr-9',
      className,
    )

    return (
      <div className={clsx('flex flex-col gap-1.5', fullWidth && 'w-full', wrapperClass)}>
        {/* Label */}
        {label && (
          <label className="text-sm font-medium text-slate-900 dark:text-slate-300">
            {label}
          </label>
        )}

        {/* Input wrapper */}
        <div className="relative">
          {/* Left icon */}
          {(leftIcon || isSearch) && (
            <div className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500 dark:text-slate-400 pointer-events-none">
              {isSearch ? <Search size={15} /> : leftIcon}
            </div>
          )}

          {/* Input or Textarea */}
          {isTextarea ? (
            <textarea
              ref={ref as React.Ref<HTMLTextAreaElement>}
              rows={(props as TextareaProps).rows ?? 4}
              className={clsx(inputClass, 'resize-y')}
              {...(rest as React.TextareaHTMLAttributes<HTMLTextAreaElement>)}
            />
          ) : (
            <input
              ref={ref as React.Ref<HTMLInputElement>}
              {...(rest as React.InputHTMLAttributes<HTMLInputElement>)}
              type={isPassword ? (showPassword ? 'text' : 'password') : (rest as InputProps).type}
              className={inputClass}
            />
          )}

          {/* Right icon / password toggle */}
          {isPassword ? (
            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300 transition-colors"
              tabIndex={-1}
            >
              {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
            </button>
          ) : rightIcon ? (
            <div className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 dark:text-slate-400 pointer-events-none">
              {rightIcon}
            </div>
          ) : null}
        </div>

        {/* Error / hint */}
        <AnimatePresence mode="wait">
          {error ? (
            <motion.p
              key="error"
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.15 }}
              className="flex items-center gap-1 text-xs text-red-500 dark:text-red-400"
            >
              <AlertCircle size={11} />
              {error}
            </motion.p>
          ) : hint ? (
            <motion.p
              key="hint"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="text-xs text-slate-600 dark:text-slate-500"
            >
              {hint}
            </motion.p>
          ) : null}
        </AnimatePresence>
      </div>
    )
  }
)

export default Input
