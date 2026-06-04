'use client'

/**
 * FeedbackWidget — in-app NPS survey + feedback form.
 *
 * Phase 9.3 — Growth & Iteration
 *
 * Shows automatically after user has been active for 5 minutes (once per 30 days).
 * Also available as a standalone button anywhere.
 *
 * Features:
 *  - NPS score (0–10) with emoji sentiment labels
 *  - Optional free-text follow-up
 *  - Dismissible, remembers via localStorage (30-day cooldown)
 *  - POST to /api/v1/billing/feedback/
 */

import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, MessageSquare, Send, Loader2, CheckCircle2 } from 'lucide-react'
import { api } from '@/utils/api'
import { cn } from '@/utils/helpers'

// ── Constants ──────────────────────────────────────────────────────────────────

const STORAGE_KEY       = 'synapse_feedback_last_shown'
const COOLDOWN_DAYS     = 30
const AUTO_SHOW_MS      = 5 * 60 * 1000   // 5 minutes

// ── NPS labels ─────────────────────────────────────────────────────────────────

const NPS_LABELS: Record<number, string> = {
  0: '😣', 1: '😣', 2: '😟', 3: '😟', 4: '😐',
  5: '😐', 6: '🙂', 7: '🙂', 8: '😊', 9: '😄', 10: '🤩',
}

function getNPSCategory(score: number): { label: string; color: string } {
  if (score <= 6) return { label: 'Detractor', color: 'text-red-500' }
  if (score <= 8) return { label: 'Passive',   color: 'text-yellow-500' }
  return              { label: 'Promoter',   color: 'text-green-500' }
}

// ── Types ──────────────────────────────────────────────────────────────────────

interface FeedbackWidgetProps {
  /** Render as always-visible button (e.g. in sidebar) */
  alwaysShow?: boolean
  className?:  string
}

// ── Component ──────────────────────────────────────────────────────────────────

export function FeedbackWidget({ alwaysShow = false, className }: FeedbackWidgetProps) {
  const [open,      setOpen]      = useState(false)
  const [step,      setStep]      = useState<'nps' | 'text' | 'done'>('nps')
  const [npsScore,  setNpsScore]  = useState<number | null>(null)
  const [message,   setMessage]   = useState('')
  const [loading,   setLoading]   = useState(false)

  // Auto-show logic (once per 30 days, after 5 min)
  useEffect(() => {
    if (alwaysShow) return
    const last = localStorage.getItem(STORAGE_KEY)
    if (last) {
      const daysSince = (Date.now() - Number(last)) / (1000 * 60 * 60 * 24)
      if (daysSince < COOLDOWN_DAYS) return
    }
    const timer = setTimeout(() => setOpen(true), AUTO_SHOW_MS)
    return () => clearTimeout(timer)
  }, [alwaysShow])

  const handleClose = () => {
    setOpen(false)
    localStorage.setItem(STORAGE_KEY, String(Date.now()))
  }

  const handleNpsSelect = (score: number) => {
    setNpsScore(score)
    setStep('text')
  }

  const handleSubmit = async () => {
    setLoading(true)
    try {
      await api.post('/api/v1/billing/feedback/', {
        type:      'nps',
        nps_score: npsScore,
        message:   message.trim(),
        page_url:  window.location.href,
      })
      setStep('done')
      setTimeout(() => handleClose(), 2500)
    } catch {
      // Silently fail — don't block UX
      setStep('done')
      setTimeout(() => handleClose(), 2500)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      {/* Trigger button */}
      {alwaysShow && (
        <button
          onClick={() => { setOpen(true); setStep('nps'); setNpsScore(null); setMessage('') }}
          className={cn(
            'flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium',
            'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400',
            'hover:bg-indigo-50 dark:hover:bg-indigo-900/20 hover:text-indigo-600 dark:hover:text-indigo-400',
            'transition-colors',
            className,
          )}
        >
          <MessageSquare size={13} />
          Feedback
        </button>
      )}

      {/* Widget */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 24, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 24, scale: 0.95 }}
            transition={{ type: 'spring', stiffness: 300, damping: 26 }}
            className="fixed bottom-20 lg:bottom-6 right-4 lg:right-6 z-50 w-80 bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-700 overflow-hidden"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <MessageSquare size={14} className="text-indigo-500" />
                <span className="text-sm font-semibold text-slate-800 dark:text-white">Quick feedback</span>
              </div>
              <button
                onClick={handleClose}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
              >
                <X size={14} />
              </button>
            </div>

            {/* Steps */}
            <div className="px-4 py-4">
              <AnimatePresence mode="wait">

                {/* NPS Step */}
                {step === 'nps' && (
                  <motion.div key="nps" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                    <p className="text-sm text-slate-700 dark:text-slate-300 mb-3 leading-snug">
                      How likely are you to recommend SYNAPSE to a colleague?
                    </p>
                    <div className="flex gap-1 flex-wrap justify-center mb-2">
                      {Array.from({ length: 11 }, (_, i) => (
                        <button
                          key={i}
                          onClick={() => handleNpsSelect(i)}
                          className={cn(
                            'w-7 h-7 rounded-lg text-xs font-bold transition-all',
                            npsScore === i
                              ? 'bg-indigo-600 text-white scale-110'
                              : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-indigo-100 dark:hover:bg-indigo-900/30',
                          )}
                        >
                          {i}
                        </button>
                      ))}
                    </div>
                    <div className="flex justify-between text-xs text-slate-400 mt-1">
                      <span>Not likely</span>
                      <span>Very likely</span>
                    </div>
                  </motion.div>
                )}

                {/* Text Step */}
                {step === 'text' && (
                  <motion.div key="text" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}>
                    <div className="flex items-center gap-2 mb-3">
                      <span className="text-2xl">{NPS_LABELS[npsScore ?? 5]}</span>
                      <div>
                        <p className="text-sm font-semibold text-slate-800 dark:text-white">
                          Score: {npsScore}/10
                        </p>
                        <p className={cn('text-xs', getNPSCategory(npsScore ?? 5).color)}>
                          {getNPSCategory(npsScore ?? 5).label}
                        </p>
                      </div>
                    </div>
                    <textarea
                      value={message}
                      onChange={(e) => setMessage(e.target.value)}
                      placeholder="What could we do better? (optional)"
                      rows={3}
                      maxLength={500}
                      className="w-full text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/60 text-slate-900 dark:text-white placeholder-slate-400 px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500/40 mb-3"
                    />
                    <button
                      onClick={handleSubmit}
                      disabled={loading}
                      className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium transition-colors disabled:opacity-60"
                    >
                      {loading ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                      {loading ? 'Sending…' : 'Send feedback'}
                    </button>
                  </motion.div>
                )}

                {/* Done Step */}
                {step === 'done' && (
                  <motion.div
                    key="done"
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="flex flex-col items-center py-4 gap-2"
                  >
                    <CheckCircle2 className="w-10 h-10 text-green-500" />
                    <p className="text-sm font-semibold text-slate-800 dark:text-white">Thank you! 🙌</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400 text-center">
                      Your feedback helps us build a better SYNAPSE.
                    </p>
                  </motion.div>
                )}

              </AnimatePresence>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}

export default FeedbackWidget
