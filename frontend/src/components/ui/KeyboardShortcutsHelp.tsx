'use client'

/**
 * Feature #21: Global Keyboard Shortcuts Help Modal
 * Press ? to open. Lists all shortcuts.
 */

import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Keyboard, X } from 'lucide-react'

const SHORTCUTS = [
  { keys: ['⌘', 'K'], description: 'Open command palette' },
  { keys: ['F'],        description: 'Toggle focus mode' },
  { keys: ['?'],        description: 'Show keyboard shortcuts' },
  { keys: ['Esc'],      description: 'Close modal / palette' },
  { keys: ['/'],        description: 'Search articles' },
  { keys: ['J'],        description: 'Next article' },
  { keys: ['K'],        description: 'Previous article' },
  { keys: ['B'],        description: 'Bookmark selected' },
  { keys: ['O'],        description: 'Open selected link' },
  { keys: ['R'],        description: 'Refresh feed' },
  { keys: ['G', 'H'],   description: 'Go to Home' },
  { keys: ['G', 'F'],   description: 'Go to Feed' },
  { keys: ['G', 'R'],   description: 'Go to Research' },
  { keys: ['G', 'L'],   description: 'Go to Library' },
  { keys: ['G', 'A'],   description: 'Go to Analytics' },
]

export function KeyboardShortcutsHelp() {
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      if (e.key === '?') setOpen(o => !o)
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  return (
    <>
      {/* Trigger button */}
      <button
        onClick={() => setOpen(true)}
        title="Keyboard shortcuts (?)"
        className="fixed bottom-4 right-4 z-50 w-9 h-9 rounded-full bg-slate-800 dark:bg-slate-700 text-white flex items-center justify-center shadow-lg hover:bg-indigo-600 transition-colors text-xs font-bold"
      >
        ?
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            className="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={e => { if (e.target === e.currentTarget) setOpen(false) }}
          >
            <motion.div
              className="bg-white dark:bg-slate-800 rounded-2xl shadow-2xl w-full max-w-md max-h-[80vh] overflow-y-auto"
              initial={{ scale: 0.9, y: 20 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.9, y: 20 }}
            >
              <div className="flex items-center justify-between p-5 border-b border-slate-100 dark:border-slate-700">
                <h2 className="font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
                  <Keyboard size={18} className="text-indigo-500" /> Keyboard Shortcuts
                </h2>
                <button onClick={() => setOpen(false)} className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700">
                  <X size={18} />
                </button>
              </div>
              <div className="p-4 space-y-1.5">
                {SHORTCUTS.map((s, i) => (
                  <div key={i} className="flex items-center justify-between py-1.5 px-2 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700/50">
                    <span className="text-sm text-slate-600 dark:text-slate-300">{s.description}</span>
                    <div className="flex items-center gap-1">
                      {s.keys.map((k, ki) => (
                        <span key={ki} className="inline-flex items-center justify-center px-2 py-0.5 bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-md text-xs font-mono font-medium border border-slate-200 dark:border-slate-600">
                          {k}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              <div className="px-5 py-3 border-t border-slate-100 dark:border-slate-700">
                <p className="text-xs text-slate-400 text-center">Press <kbd className="px-1.5 py-0.5 bg-slate-100 dark:bg-slate-700 rounded font-mono">?</kbd> anytime to toggle this</p>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
