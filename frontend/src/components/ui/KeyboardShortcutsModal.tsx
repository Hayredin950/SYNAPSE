'use client'

import React from 'react'
import { createPortal } from 'react-dom'
import { X, Keyboard } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { ALL_SHORTCUTS } from '@/hooks/useKeyboardShortcuts'

interface Props {
  open: boolean
  onClose: () => void
}

export function KeyboardShortcutsModal({ open, onClose }: Props) {
  const grouped = ALL_SHORTCUTS.reduce<Record<string, typeof ALL_SHORTCUTS>>(
    (acc, s) => { (acc[s.category] ??= []).push(s); return acc },
    {}
  )

  if (typeof window === 'undefined') return null

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          key="shortcuts-backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
          onClick={onClose}
        >
          <motion.div
            key="shortcuts-panel"
            initial={{ scale: 0.95, opacity: 0, y: 8 }}
            animate={{ scale: 1,    opacity: 1, y: 0 }}
            exit={{ scale: 0.95,    opacity: 0, y: 8 }}
            transition={{ type: 'spring', damping: 26, stiffness: 320 }}
            className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-700 shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col overflow-hidden"
            onClick={e => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-700 flex-shrink-0">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-xl bg-indigo-100 dark:bg-indigo-900/40 flex items-center justify-center">
                  <Keyboard size={16} className="text-indigo-600 dark:text-indigo-400" />
                </div>
                <div>
                  <h2 className="text-sm font-bold text-slate-900 dark:text-white">Keyboard Shortcuts</h2>
                  <p className="text-xs text-slate-400">Speed up your workflow</p>
                </div>
              </div>
              <button
                onClick={onClose}
                className="w-8 h-8 flex items-center justify-center rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
              >
                <X size={15} />
              </button>
            </div>

            {/* Body */}
            <div className="overflow-y-auto p-6 flex-1">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-8">
                {Object.entries(grouped).map(([category, items]) => (
                  <div key={category}>
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-3">
                      {category}
                    </h3>
                    <div className="space-y-2.5">
                      {items.map(s => (
                        <div key={s.keys} className="flex items-center justify-between gap-3">
                          <span className="text-sm text-slate-600 dark:text-slate-400">{s.description}</span>
                          <div className="flex items-center gap-1 shrink-0">
                            {s.keys.split(' ').map((k, i, arr) => (
                              <React.Fragment key={i}>
                                <kbd className="px-2 py-0.5 text-xs font-mono font-semibold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 border border-slate-300 dark:border-slate-600 rounded-md shadow-[0_1px_0_0] shadow-slate-300 dark:shadow-slate-600">
                                  {k}
                                </kbd>
                                {i < arr.length - 1 && (
                                  <span className="text-[10px] text-slate-400">then</span>
                                )}
                              </React.Fragment>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-6 pt-4 border-t border-slate-200 dark:border-slate-700 text-center">
                <p className="text-xs text-slate-400 dark:text-slate-500">
                  Press{' '}
                  <kbd className="px-1.5 py-0.5 text-xs font-mono bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-600 rounded">
                    ?
                  </kbd>{' '}
                  anytime to open this panel
                </p>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body
  )
}
