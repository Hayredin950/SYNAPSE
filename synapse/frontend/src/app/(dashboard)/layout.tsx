'use client'

import React, { useState, useEffect, useCallback } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import dynamic from 'next/dynamic'
import { useTheme } from 'next-themes'
import { Sidebar, MobileBottomNav } from '@/components/layout/Sidebar'
import { Navbar } from '@/components/layout/Navbar'
import { AIAssistantPanel } from '@/components/layout/AIAssistantPanel'
import { useAuthStore } from '@/store/authStore'
import { OrganizationProvider } from '@/contexts/OrganizationContext'
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts'
import { useLiveContent } from '@/hooks/useLiveContent'
import { useReaderStore } from '@/store/readerStore'
import { useAccentTheme } from '@/components/ui/AccentTheme'

// ── Lazy-loaded overlays — only downloaded when needed ────────────────────────
const CommandPalette = dynamic(
  () => import('@/components/ui/CommandPalette').then(m => ({ default: m.CommandPalette })),
  { ssr: false },
)
const KeyboardShortcutsModal = dynamic(
  () => import('@/components/ui/KeyboardShortcutsModal').then(m => ({ default: m.KeyboardShortcutsModal })),
  { ssr: false },
)
const ContentReaderModal = dynamic(
  () => import('@/components/modals/ContentReaderModal').then(m => ({ default: m.ContentReaderModal })),
  { ssr: false },
)

function LiveContentWatcher() {
  useLiveContent()
  return null
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router      = useRouter()
  const pathname    = usePathname()
  const { setTheme, resolvedTheme } = useTheme()
  const { isAuthenticated } = useAuthStore()

  const [isCollapsed,   setIsCollapsed]   = useState(false)
  const [mobileOpen,    setMobileOpen]    = useState(false)
  const [cmdOpen,       setCmdOpen]       = useState(false)
  const [shortcutsOpen, setShortcutsOpen] = useState(false)
  const [aiPanelOpen,   setAiPanelOpen]   = useState(false)
  const [hydrated,      setHydrated]      = useState(false)

  // Reader modal state via Zustand
  const { article: readerArticle, close: closeReader } = useReaderStore()

  // Feature #28: Initialize accent theme from localStorage on mount
  useAccentTheme()

  // ── Theme toggle ──────────────────────────────────────────────────────────
  const handleThemeToggle = useCallback(() => {
    setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')
  }, [setTheme, resolvedTheme])

  // ── Global ⌘K / Ctrl+K listener ──────────────────────────────────────────
  const handleGlobalKey = useCallback((e: KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault()
      setCmdOpen(prev => !prev)
    }
  }, [])

  useEffect(() => {
    window.addEventListener('keydown', handleGlobalKey)
    return () => window.removeEventListener('keydown', handleGlobalKey)
  }, [handleGlobalKey])

  // ── Vim-style keyboard shortcuts ──────────────────────────────────────────
  useKeyboardShortcuts({
    onCommandPalette: () => setCmdOpen(true),
    onShortcutsHelp:  () => setShortcutsOpen(true),
    onThemeToggle:    handleThemeToggle,
  })

  // ── Auth hydration guard ──────────────────────────────────────────────────
  useEffect(() => {
    const hasToken = !!localStorage.getItem('synapse_access_token')
    if (hasToken || useAuthStore.persist.hasHydrated()) {
      setHydrated(true)
      return
    }
    const unsub   = useAuthStore.persist.onFinishHydration(() => setHydrated(true))
    const timeout = setTimeout(() => setHydrated(true), 800)
    return () => { unsub(); clearTimeout(timeout) }
  }, [])

  useEffect(() => {
    if (hydrated && !isAuthenticated) router.push('/login')
  }, [hydrated, isAuthenticated, router])

  // Close mobile sidebar on route change
  useEffect(() => { setMobileOpen(false) }, [pathname])

  if (!hydrated) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/30 animate-pulse">
            <span className="text-white font-black text-base">S</span>
          </div>
          <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return null
  }

  return (
    <OrganizationProvider>
      {/* Live content SSE watcher — only when authenticated */}
      <LiveContentWatcher />

      {/* A11y: skip-to-main-content */}
      <a href="#main-content" className="skip-to-content">Skip to main content</a>

      <div className="flex h-screen bg-slate-50 dark:bg-slate-950 overflow-hidden">
        {/* Mobile backdrop */}
        {mobileOpen && (
          <div
            className="fixed inset-0 z-40 bg-black/50 md:hidden"
            onClick={() => setMobileOpen(false)}
          />
        )}

        <Sidebar
          isCollapsed={isCollapsed}
          onToggle={() => setIsCollapsed(c => !c)}
          mobileOpen={mobileOpen}
          onMobileClose={() => setMobileOpen(false)}
        />

        <div className={`flex-1 flex flex-col overflow-hidden transition-[margin] duration-200 ${
          isCollapsed ? 'md:ml-[72px]' : 'md:ml-64'
        }`}>
          <Navbar
            onMobileMenuClick={() => setMobileOpen(true)}
            onSearchClick={() => setCmdOpen(true)}
            onAIPanelToggle={pathname !== '/chat' ? () => setAiPanelOpen(p => !p) : undefined}
            aiPanelOpen={aiPanelOpen}
          />

          <div className="flex-1 flex overflow-hidden min-h-0">
            <main id="main-content" className="flex-1 overflow-hidden flex flex-col min-h-0 relative">
              {children}
            </main>

            {pathname !== '/chat' && (
              <AIAssistantPanel
                isOpen={aiPanelOpen}
                onToggle={() => setAiPanelOpen(p => !p)}
              />
            )}
          </div>
        </div>
      </div>

      {/* ── Global overlays ────────────────────────────────────────────── */}
      {cmdOpen       && <CommandPalette open={cmdOpen} onClose={() => setCmdOpen(false)} />}
      {shortcutsOpen && <KeyboardShortcutsModal open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />}
      {readerArticle && <ContentReaderModal article={readerArticle} onClose={closeReader} />}

      {/* Keyboard hint — bottom-right corner */}
      <button
        onClick={() => setShortcutsOpen(true)}
        title="Keyboard shortcuts (?)"
        className="fixed bottom-20 md:bottom-6 right-4 md:right-6 z-30 hidden sm:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm text-xs font-mono text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 hover:border-slate-300 dark:hover:border-slate-600 transition-all hover:shadow-md"
      >
        <kbd className="font-sans">?</kbd>
        <span className="font-sans text-[10px]">shortcuts</span>
      </button>

      <MobileBottomNav />
    </OrganizationProvider>
  )
}
