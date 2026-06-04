'use client'

/**
 * Feature #21b: Global Navigation Keyboard Shortcuts
 * G+H = /home, G+F = /feed, G+R = /research, G+L = /library, G+A = /analytics
 * J/K = scroll articles, B = bookmark, O = open
 */

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

const NAV_SHORTCUTS: Record<string, string> = {
  'g+h': '/home',
  'g+f': '/feed',
  'g+r': '/research',
  'g+l': '/library',
  'g+a': '/analytics',
  'g+c': '/chat',
  'g+t': '/trends',
  'g+v': '/videos',
}

export function GlobalNavShortcuts() {
  const router = useRouter()

  useEffect(() => {
    let lastKey = ''
    let timer: ReturnType<typeof setTimeout> | null = null

    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || e.metaKey || e.ctrlKey || e.altKey) return
      if (e.key === '?') return  // handled by KeyboardShortcutsHelp

      const key = e.key.toLowerCase()
      const combo = lastKey ? `${lastKey}+${key}` : key

      if (NAV_SHORTCUTS[combo]) {
        router.push(NAV_SHORTCUTS[combo])
        lastKey = ''
        if (timer) clearTimeout(timer)
        return
      }

      if (key === 'g') {
        lastKey = 'g'
        if (timer) clearTimeout(timer)
        timer = setTimeout(() => { lastKey = '' }, 800)
      } else {
        lastKey = ''
        if (timer) clearTimeout(timer)
      }
    }

    window.addEventListener('keydown', handler)
    return () => {
      window.removeEventListener('keydown', handler)
      if (timer) clearTimeout(timer)
    }
  }, [router])

  return null
}
