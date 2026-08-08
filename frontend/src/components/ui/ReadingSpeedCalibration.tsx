'use client'

/**
 * Feature #25: Reading Speed Calibration
 * Measures your WPM to give accurate reading time estimates.
 */

import React, { useState, useRef, useEffect, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Zap, Check, Timer } from 'lucide-react'

const CALIBRATION_TEXT = `
The history of computing began long before the digital age. Early mechanical devices
like the abacus helped humans calculate faster. In the 20th century, the first
electronic computers filled entire rooms and consumed enormous amounts of power.
The invention of the transistor changed everything, enabling computers to shrink
dramatically while becoming exponentially more powerful. Today, smartphones hold
more computing power than the machines that guided rockets to the moon.

Modern software engineering has similarly evolved. The open-source movement
democratized access to powerful tools and libraries. Cloud computing eliminated
the need to manage physical servers. And now, artificial intelligence is
transforming how we write, debug, and reason about code. The next decade
promises even more radical changes, with quantum computing on the horizon
and large language models reshaping every domain of knowledge work.
`.trim()

const WORD_COUNT = CALIBRATION_TEXT.split(/\s+/).length  // ~150 words

function saveWPM(wpm: number) {
  if (typeof window === 'undefined') return
  const stats = JSON.parse(localStorage.getItem('synapse_reading_stats') || '{}')
  localStorage.setItem('synapse_reading_stats', JSON.stringify({ ...stats, wpm }))
}

interface Props { onClose: () => void }

export function ReadingSpeedCalibration({ onClose }: Props) {
  const [phase, setPhase] = useState<'intro' | 'reading' | 'done'>('intro')
  const [elapsed, setElapsed] = useState(0)
  const [wpm, setWpm] = useState(0)
  const startRef = useRef<number>(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const [mounted, setMounted] = useState(false)
  useEffect(() => { setMounted(true); return () => { if (timerRef.current) clearInterval(timerRef.current) } }, [])

  const startReading = () => {
    setPhase('reading')
    startRef.current = Date.now()
    timerRef.current = setInterval(() => setElapsed(Math.floor((Date.now() - startRef.current) / 1000)), 200)
  }

  const finishReading = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current)
    const seconds = (Date.now() - startRef.current) / 1000
    const calculatedWpm = Math.round((WORD_COUNT / seconds) * 60)
    setWpm(calculatedWpm)
    saveWPM(calculatedWpm)
    setPhase('done')
  }, [])

  if (!mounted) return null

  const modal = (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        onClick={e => { if (e.target === e.currentTarget) onClose() }}
      >
        <motion.div
          className="bg-white dark:bg-slate-800 rounded-2xl shadow-2xl w-full max-w-lg"
          initial={{ scale: 0.9, y: 20 }} animate={{ scale: 1, y: 0 }}
        >
          <div className="flex items-center justify-between p-5 border-b border-slate-100 dark:border-slate-700">
            <h2 className="font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
              <Zap size={18} className="text-indigo-500" /> Reading Speed Calibration
            </h2>
            <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors">
              <X size={18} />
            </button>
          </div>

          <div className="p-6">
            {phase === 'intro' && (
              <div className="text-center space-y-4">
                <div className="text-5xl">📖</div>
                <div>
                  <h3 className="font-semibold text-slate-800 dark:text-slate-100">Calibrate your reading speed</h3>
                  <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Read the passage naturally, then click "Done" when finished.
                    We'll calculate your WPM and adjust reading time estimates.
                  </p>
                </div>
                <div className="text-sm text-slate-400">{WORD_COUNT} words · ~{Math.round(WORD_COUNT / 250)} min at average speed</div>
                <button onClick={startReading} className="px-6 py-2.5 bg-indigo-600 text-white rounded-xl font-medium hover:bg-indigo-700 transition-colors">
                  Start Reading
                </button>
              </div>
            )}

            {phase === 'reading' && (
              <div className="space-y-4">
                <div className="flex items-center justify-between text-sm text-slate-500">
                  <span className="flex items-center gap-1"><Timer size={14} /> {elapsed}s elapsed</span>
                  <span>{WORD_COUNT} words</span>
                </div>
                <div className="bg-slate-50 dark:bg-slate-900 rounded-xl p-4 text-sm leading-relaxed text-slate-700 dark:text-slate-300 max-h-48 overflow-y-auto">
                  {CALIBRATION_TEXT}
                </div>
                <button onClick={finishReading} className="w-full px-6 py-2.5 bg-emerald-600 text-white rounded-xl font-medium hover:bg-emerald-700 transition-colors flex items-center justify-center gap-2">
                  <Check size={18} /> Done Reading
                </button>
              </div>
            )}

            {phase === 'done' && (
              <div className="text-center space-y-4">
                <div className="text-5xl">🎉</div>
                <div>
                  <div className="text-4xl font-black text-indigo-600">{wpm} WPM</div>
                  <p className="text-sm text-slate-500 mt-1">
                    {wpm < 200 ? 'Methodical reader — you absorb every detail'
                     : wpm < 300 ? 'Average reading speed — well calibrated'
                     : wpm < 400 ? 'Above average — great comprehension'
                     : 'Speed reader — impressive!'}
                  </p>
                </div>
                <div className="text-sm text-slate-400 bg-slate-50 dark:bg-slate-700 rounded-xl p-3">
                  Reading time estimates will now be personalized to your {wpm} WPM reading speed.
                </div>
                <button onClick={onClose} className="px-6 py-2.5 bg-indigo-600 text-white rounded-xl font-medium hover:bg-indigo-700 transition-colors">
                  Save & Close
                </button>
              </div>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )

  return createPortal(modal, document.body)
}
