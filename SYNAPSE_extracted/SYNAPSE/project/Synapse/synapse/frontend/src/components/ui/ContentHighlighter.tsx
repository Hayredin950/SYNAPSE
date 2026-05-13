'use client'

/**
 * Feature #25: Content Highlighter / Annotations
 * Allows users to highlight text in articles and save highlights.
 */

import React, { useState, useCallback, useEffect } from 'react'
import { Highlighter, Save, X } from 'lucide-react'
import toast from 'react-hot-toast'

interface Highlight {
  id:    string
  text:  string
  color: string
  note?: string
  createdAt: number
}

const COLORS = [
  { name: 'Yellow', value: 'bg-yellow-200/70 dark:bg-yellow-700/40',   border: 'border-yellow-400' },
  { name: 'Green',  value: 'bg-emerald-200/70 dark:bg-emerald-700/40', border: 'border-emerald-400' },
  { name: 'Blue',   value: 'bg-blue-200/70 dark:bg-blue-700/40',       border: 'border-blue-400'    },
  { name: 'Pink',   value: 'bg-pink-200/70 dark:bg-pink-700/40',       border: 'border-pink-400'    },
]

const LS_KEY = 'synapse_highlights'

function loadHighlights(articleId: string): Highlight[] {
  try {
    const all = JSON.parse(localStorage.getItem(LS_KEY) || '{}')
    return all[articleId] ?? []
  } catch { return [] }
}

function saveHighlights(articleId: string, highlights: Highlight[]) {
  try {
    const all = JSON.parse(localStorage.getItem(LS_KEY) || '{}')
    all[articleId] = highlights
    localStorage.setItem(LS_KEY, JSON.stringify(all))
  } catch {}
}

interface Props {
  articleId: string
}

export function ContentHighlighter({ articleId }: Props) {
  const [highlights, setHighlights] = useState<Highlight[]>([])
  const [selected, setSelected]     = useState<{ text: string; color: string } | null>(null)
  const [showPanel, setShowPanel]   = useState(false)

  useEffect(() => {
    setHighlights(loadHighlights(articleId))
  }, [articleId])

  const addHighlight = useCallback((color: string) => {
    const sel = window.getSelection()
    const text = sel?.toString().trim()
    if (!text) { toast.error('Select some text first'); return }
    const h: Highlight = {
      id:        Date.now().toString(),
      text,
      color,
      createdAt: Date.now(),
    }
    const next = [...highlights, h]
    setHighlights(next)
    saveHighlights(articleId, next)
    sel?.removeAllRanges()
    toast.success('Highlight saved')
  }, [highlights, articleId])

  const removeHighlight = (id: string) => {
    const next = highlights.filter(h => h.id !== id)
    setHighlights(next)
    saveHighlights(articleId, next)
  }

  return (
    <>
      {/* Trigger */}
      <button
        onClick={() => setShowPanel(s => !s)}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-xs font-medium text-slate-600 dark:text-slate-300 hover:border-amber-400 hover:text-amber-600 transition-colors"
      >
        <Highlighter size={12} /> Highlights {highlights.length > 0 && `(${highlights.length})`}
      </button>

      {showPanel && (
        <div className="fixed bottom-20 right-4 z-50 w-80 bg-white dark:bg-slate-800 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-700 p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-bold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
              <Highlighter size={14} className="text-amber-500" /> Highlighter
            </span>
            <button onClick={() => setShowPanel(false)} className="p-1 hover:bg-slate-100 dark:hover:bg-slate-700 rounded">
              <X size={14} />
            </button>
          </div>

          <div className="mb-4">
            <p className="text-xs text-slate-500 mb-2">Select text in the article, then pick a color:</p>
            <div className="flex gap-2">
              {COLORS.map(c => (
                <button
                  key={c.name}
                  onClick={() => addHighlight(c.value)}
                  title={`Highlight in ${c.name}`}
                  className={`w-7 h-7 rounded-full ${c.value} border-2 ${c.border} hover:scale-110 transition-transform`}
                />
              ))}
            </div>
          </div>

          {highlights.length > 0 ? (
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {highlights.map(h => (
                <div key={h.id} className={`p-2 rounded-lg ${h.color} flex items-start gap-2`}>
                  <span className="flex-1 text-xs text-slate-700 dark:text-slate-300 line-clamp-2">"{h.text}"</span>
                  <button onClick={() => removeHighlight(h.id)} className="text-slate-400 hover:text-red-500 flex-shrink-0 mt-0.5">
                    <X size={11} />
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-400 text-center py-4">No highlights yet</p>
          )}
        </div>
      )}
    </>
  )
}
