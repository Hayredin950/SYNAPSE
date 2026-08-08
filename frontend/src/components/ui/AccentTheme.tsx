'use client'

/**
 * Feature #28: Custom Accent Color / Theme Settings
 * Lets users pick their accent color from a palette.
 * Writes to CSS custom property + localStorage.
 */

import React, { useState, useEffect } from 'react'
import { Palette, Check } from 'lucide-react'
import { cn } from '@/utils/helpers'

const ACCENT_PRESETS = [
  { name: 'Indigo',   value: '#6366f1', css: '99 102 241' },
  { name: 'Violet',   value: '#8b5cf6', css: '139 92 246' },
  { name: 'Cyan',     value: '#06b6d4', css: '6 182 212' },
  { name: 'Emerald',  value: '#10b981', css: '16 185 129' },
  { name: 'Rose',     value: '#f43f5e', css: '244 63 94' },
  { name: 'Amber',    value: '#f59e0b', css: '245 158 11' },
  { name: 'Pink',     value: '#ec4899', css: '236 72 153' },
  { name: 'Slate',    value: '#64748b', css: '100 116 139' },
]

function applyAccent(preset: typeof ACCENT_PRESETS[0]) {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  root.style.setProperty('--accent-hex', preset.value)
  root.style.setProperty('--accent-rgb', preset.css)
  localStorage.setItem('synapse_accent', JSON.stringify(preset))
}

export function useAccentTheme() {
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('synapse_accent') || 'null')
      if (saved) applyAccent(saved)
    } catch {}
  }, [])
}

interface Props {
  compact?: boolean
}

export function AccentThemePicker({ compact = false }: Props) {
  const [current, setCurrent] = useState<string>('#6366f1')
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
    try {
      const saved = JSON.parse(localStorage.getItem('synapse_accent') || 'null')
      if (saved) { setCurrent(saved.value); applyAccent(saved) }
    } catch {}
  }, [])

  const pick = (preset: typeof ACCENT_PRESETS[0]) => {
    setCurrent(preset.value)
    applyAccent(preset)
  }

  if (!mounted) return null

  if (compact) {
    return (
      <div className="flex items-center gap-2 flex-wrap">
        {ACCENT_PRESETS.map(p => (
          <button
            key={p.value}
            onClick={() => pick(p)}
            title={p.name}
            className={cn(
              'w-6 h-6 rounded-full transition-all border-2',
              current === p.value ? 'border-white scale-125 shadow-lg' : 'border-transparent hover:scale-110',
            )}
            style={{ backgroundColor: p.value }}
          />
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Palette size={14} className="text-slate-400" />
        <span className="text-sm font-medium text-slate-700 dark:text-slate-200">Accent Color</span>
      </div>
      <div className="flex flex-wrap gap-3">
        {ACCENT_PRESETS.map(p => (
          <button
            key={p.value}
            onClick={() => pick(p)}
            title={p.name}
            className={cn(
              'relative w-8 h-8 rounded-full transition-all border-2',
              current === p.value ? 'border-white scale-110 shadow-lg' : 'border-transparent hover:scale-105',
            )}
            style={{ backgroundColor: p.value }}
          >
            {current === p.value && <Check size={14} className="absolute inset-0 m-auto text-white" />}
          </button>
        ))}
      </div>
      <p className="text-xs text-slate-400">
        Currently: {ACCENT_PRESETS.find(p => p.value === current)?.name ?? 'Indigo'}
      </p>
    </div>
  )
}
