'use client'

/**
 * Feature #18: Focus Mode
 * Distraction-free reader mode — dims sidebar and header, expands content.
 * Triggered via keyboard shortcut F or button.
 */

import React, { useEffect, useState, createContext, useContext, useCallback } from 'react'
import { Minimize2, Maximize2 } from 'lucide-react'

interface FocusCtx {
  focusMode: boolean
  toggleFocus: () => void
}

const FocusContext = createContext<FocusCtx>({ focusMode: false, toggleFocus: () => {} })

export function FocusModeProvider({ children }: { children: React.ReactNode }) {
  const [focusMode, setFocusMode] = useState(false)

  const toggleFocus = useCallback(() => setFocusMode(f => !f), [])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      if (e.key === 'f' || e.key === 'F') toggleFocus()
      if (e.key === 'Escape' && focusMode) setFocusMode(false)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [focusMode, toggleFocus])

  useEffect(() => {
    if (focusMode) {
      document.documentElement.classList.add('focus-mode')
    } else {
      document.documentElement.classList.remove('focus-mode')
    }
  }, [focusMode])

  return (
    <FocusContext.Provider value={{ focusMode, toggleFocus }}>
      {children}
    </FocusContext.Provider>
  )
}

export function useFocusMode() {
  return useContext(FocusContext)
}

export function FocusModeButton({ className = '' }: { className?: string }) {
  const { focusMode, toggleFocus } = useFocusMode()
  return (
    <button
      onClick={toggleFocus}
      title={`${focusMode ? 'Exit' : 'Enter'} focus mode (F)`}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-xs font-medium text-slate-600 dark:text-slate-300 hover:border-indigo-400 hover:text-indigo-600 transition-colors ${className}`}
    >
      {focusMode ? <Minimize2 size={12} /> : <Maximize2 size={12} />}
      {focusMode ? 'Exit Focus' : 'Focus Mode'}
    </button>
  )
}
