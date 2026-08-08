'use client'

import { useEffect, useCallback, useRef } from 'react'
import { useRouter } from 'next/navigation'

export interface ShortcutDef {
  keys: string
  description: string
  category: string
}

export const ALL_SHORTCUTS: ShortcutDef[] = [
  // General
  { keys: '?',   description: 'Show keyboard shortcuts',     category: 'General'    },
  { keys: '/',   description: 'Open search / command palette', category: 'General'  },
  { keys: 'Esc', description: 'Close dialog / go back',      category: 'General'    },
  // Navigation (g-prefix)
  { keys: 'g h', description: 'Go to Home',                  category: 'Navigation' },
  { keys: 'g f', description: 'Go to Tech Feed',             category: 'Navigation' },
  { keys: 'g r', description: 'Go to Research',              category: 'Navigation' },
  { keys: 'g v', description: 'Go to Videos',                category: 'Navigation' },
  { keys: 'g t', description: 'Go to Trends',                category: 'Navigation' },
  { keys: 'g c', description: 'Go to AI Chat',               category: 'Navigation' },
  { keys: 'g a', description: 'Go to AI Agents',             category: 'Navigation' },
  { keys: 'g l', description: 'Go to Library',               category: 'Navigation' },
  { keys: 'g g', description: 'Go to GitHub Radar',          category: 'Navigation' },
  { keys: 'g x', description: 'Go to X (Twitter) Feed',      category: 'Navigation' },
  { keys: 'g s', description: 'Go to Settings',              category: 'Navigation' },
  // Actions
  { keys: 'n',   description: 'New AI Chat',                 category: 'Actions'    },
  { keys: 'j',   description: 'Scroll down / next item',     category: 'Actions'    },
  { keys: 'k',   description: 'Scroll up / previous item',   category: 'Actions'    },
  // Display
  { keys: 'T',   description: 'Toggle dark / light mode',    category: 'Display'    },
]

const G_NAV_MAP: Record<string, string> = {
  h: '/',
  f: '/feed',
  r: '/research',
  v: '/videos',
  t: '/trends',
  c: '/chat',
  a: '/agents',
  l: '/library',
  g: '/github',
  x: '/tweets',
  s: '/settings',
  n: '/notifications',
}

interface Options {
  onCommandPalette: () => void
  onShortcutsHelp: () => void
  onThemeToggle?: () => void
}

export function useKeyboardShortcuts({
  onCommandPalette,
  onShortcutsHelp,
  onThemeToggle,
}: Options) {
  const router = useRouter()
  const gActive = useRef(false)
  const gTimer  = useRef<ReturnType<typeof setTimeout>>()

  const handle = useCallback((e: KeyboardEvent) => {
    // Don't hijack shortcuts when typing in form fields
    const target = e.target as HTMLElement
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return
    if (target.isContentEditable) return
    // Don't conflict with browser / OS shortcuts
    if (e.metaKey || e.ctrlKey || e.altKey) return

    const key = e.key

    // ── Handle g-prefix sequences ─────────────────────────────────────────
    if (gActive.current) {
      gActive.current = false
      clearTimeout(gTimer.current)
      const dest = G_NAV_MAP[key]
      if (dest) {
        e.preventDefault()
        router.push(dest)
      }
      return
    }

    switch (key) {
      case '?':
        e.preventDefault()
        onShortcutsHelp()
        break
      case '/':
        e.preventDefault()
        onCommandPalette()
        break
      case 'g':
        // Start g-prefix sequence — wait up to 800 ms for second key
        gActive.current = true
        gTimer.current = setTimeout(() => { gActive.current = false }, 800)
        break
      case 'n':
        e.preventDefault()
        router.push('/chat')
        break
      case 'T':
        e.preventDefault()
        onThemeToggle?.()
        break
      case 'j':
        // Scroll down by one "screen unit"
        window.scrollBy({ top: 200, behavior: 'smooth' })
        break
      case 'k':
        window.scrollBy({ top: -200, behavior: 'smooth' })
        break
      default:
        break
    }
  }, [router, onCommandPalette, onShortcutsHelp, onThemeToggle])

  useEffect(() => {
    window.addEventListener('keydown', handle)
    return () => {
      window.removeEventListener('keydown', handle)
      clearTimeout(gTimer.current)
    }
  }, [handle])
}
