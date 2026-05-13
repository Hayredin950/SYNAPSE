'use client'

import React, { useState, useCallback, useRef, useEffect } from 'react'
import Link from 'next/link'
import { useRouter, usePathname } from 'next/navigation'
import { useTheme } from 'next-themes'
import { Search, Sun, Moon, Bell, Menu, LogOut, Settings, User, Check, Trash2, CreditCard, Zap, Command, MessageSquare } from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/utils/api'
import { OrgSwitcher } from '@/components/layout/OrgSwitcher'
import { useNotificationSocket } from '@/hooks/useNotificationSocket'
import { Tooltip } from '@/components/ui/Tooltip'

// ── Plan Badge ────────────────────────────────────────────────────────────────

const PLAN_BADGE: Record<string, { label: string; cls: string }> = {
  free:       { label: 'FREE',       cls: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400' },
  pro:        { label: 'PRO',        cls: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300' },
  enterprise: { label: 'ENTERPRISE', cls: 'bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300' },
}

function PlanBadge() {
  const { data } = useQuery({
    queryKey: ['billing-subscription'],
    queryFn: () => api.get('/billing/subscription/').then(r => r.data),
    staleTime: 5 * 60_000,
    retry: false,
  })
  const plan  = data?.plan ?? 'free'
  const badge = PLAN_BADGE[plan] ?? PLAN_BADGE.free
  return (
    <Link
      href="/billing"
      className={`hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold tracking-wide transition-opacity hover:opacity-80 ${badge.cls}`}
      title="Manage billing"
    >
      {plan === 'free' && <Zap size={10} />}
      {plan !== 'free' && <CreditCard size={10} />}
      {badge.label}
    </Link>
  )
}

interface NavbarProps {
  onMobileMenuClick: () => void
  onSearchClick?: () => void      // TASK-402-4: trigger command palette
  onAIPanelToggle?: () => void    // TASK-403-2: toggle AI assistant panel
  aiPanelOpen?: boolean
}

// ── Types ─────────────────────────────────────────────────────────────────────

interface Notification {
  id: string
  title: string
  message: string
  notif_type: string
  is_read: boolean
  created_at: string
  metadata: Record<string, unknown>
}

// ── API helpers ───────────────────────────────────────────────────────────────

function extractList<T>(raw: unknown): T[] {
  if (Array.isArray(raw)) return raw as T[]
  if (raw && typeof raw === 'object') {
    const obj = raw as Record<string, unknown>
    if (Array.isArray(obj['data'])) return obj['data'] as T[]
    if (Array.isArray(obj['results'])) return obj['results'] as T[]
  }
  return []
}

const fetchUnreadCount = async (): Promise<number> => {
  try {
    const { data } = await api.get('/notifications/unread-count/')
    if (!data || typeof data !== 'object') return 0
    const obj = data as Record<string, unknown>

    // Flat: { unread_count: N }
    if (typeof obj['unread_count'] === 'number') return obj['unread_count']
    if (typeof obj['unread_count'] === 'string') return parseInt(obj['unread_count'], 10) || 0

    // Wrapped: { success: true, data: { unread_count: N } }
    if (obj['data'] && typeof obj['data'] === 'object') {
      const inner = obj['data'] as Record<string, unknown>
      if (typeof inner['unread_count'] === 'number') return inner['unread_count']
      if (typeof inner['unread_count'] === 'string') return parseInt(inner['unread_count'], 10) || 0
    }
    return 0
  } catch {
    return 0
  }
}

const fetchRecentNotifications = async (): Promise<Notification[]> => {
  const { data } = await api.get('/notifications/?is_read=false')
  // Unwrap custom wrapper first: { success, data: { results: [...] } } or { success, data: [...] }
  const unwrapped =
    data && typeof data === 'object' && !Array.isArray(data) && 'data' in data
      ? (data as Record<string, unknown>)['data']
      : data
  return extractList<Notification>(unwrapped).slice(0, 8)
}

const markAllRead = async () => {
  await api.post('/notifications/read-all/')
}

const markOneRead = async (id: string) => {
  await api.post(`/notifications/${id}/read/`)
}

const deleteNotification = async (id: string) => {
  await api.delete(`/notifications/${id}/`)
}

// ── NotifType icon/colour map ─────────────────────────────────────────────────

const NOTIF_STYLES: Record<string, { icon: string; colour: string }> = {
  workflow_complete: { icon: '⚙️', colour: 'text-indigo-600 dark:text-indigo-400' },
  info:             { icon: 'ℹ️', colour: 'text-blue-600 dark:text-blue-400' },
  warning:          { icon: '⚠️', colour: 'text-yellow-400' },
  error:            { icon: '❌', colour: 'text-red-400' },
  success:          { icon: '✅', colour: 'text-green-600 dark:text-green-400' },
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diff / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

// ── Notification Dropdown ─────────────────────────────────────────────────────

const NotificationDropdown = React.memo(function NotificationDropdown({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient()
  const router = useRouter()

  const { data: notifications = [], isLoading } = useQuery({
    queryKey: ['navbar-notifications'],
    queryFn: fetchRecentNotifications,
    staleTime: 30_000,
  })

  const markAllMutation = useMutation({
    mutationFn: markAllRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['unread-count'] })
      queryClient.invalidateQueries({ queryKey: ['navbar-notifications'] })
    },
  })

  const markOneMutation = useMutation({
    mutationFn: markOneRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['unread-count'] })
      queryClient.invalidateQueries({ queryKey: ['navbar-notifications'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteNotification,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['unread-count'] })
      queryClient.invalidateQueries({ queryKey: ['navbar-notifications'] })
    },
  })

  return (
    <div className="absolute right-0 top-full mt-2 w-[calc(100vw-2rem)] sm:w-96 max-w-sm bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl shadow-card-hover overflow-hidden z-50">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 dark:border-slate-700">
        <h3 className="text-sm font-semibold text-slate-900 dark:text-white">Notifications</h3>
        <div className="flex items-center gap-2">
          {notifications.length > 0 && (
            <button
              onClick={() => markAllMutation.mutate()}
              disabled={markAllMutation.isPending}
              className="text-xs text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 transition-colors disabled:opacity-50 flex items-center gap-1"
            >
              <Check size={12} />
              Mark all read
            </button>
          )}
          <button
            onClick={() => { router.push('/notifications'); onClose() }}
            className="text-xs text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
          >
            See all
          </button>
        </div>
      </div>

      {/* List */}
      <div className="max-h-[360px] overflow-y-auto">
        {isLoading && (
          <div className="px-4 py-8 text-center text-slate-500 dark:text-slate-400 text-sm animate-pulse">
            Loading…
          </div>
        )}
        {!isLoading && notifications.length === 0 && (
          <div className="px-4 py-10 text-center">
            <p className="text-2xl mb-2">🔔</p>
            <p className="text-slate-500 dark:text-slate-400 text-sm">You're all caught up!</p>
          </div>
        )}
        {notifications.map((n) => {
          const style = NOTIF_STYLES[n.notif_type] ?? NOTIF_STYLES['info']
          return (
            <div
              key={n.id}
              className={`flex items-start gap-3 px-4 py-3 border-b border-slate-100 dark:border-slate-700/50 hover:bg-slate-700/40 transition-colors group ${
                !n.is_read ? 'bg-indigo-50 dark:bg-indigo-500/5' : ''
              }`}
            >
              {/* Unread dot */}
              <div className="mt-1 flex-shrink-0">
                {!n.is_read ? (
                  <div className="w-2 h-2 rounded-full bg-indigo-500" />
                ) : (
                  <div className="w-2 h-2" />
                )}
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm font-medium text-slate-900 dark:text-white truncate">
                    <span className="mr-1">{style.icon}</span>
                    {n.title}
                  </p>
                  <span className="text-xs text-slate-400 dark:text-slate-500 flex-shrink-0 mt-0.5">
                    {timeAgo(n.created_at)}
                  </span>
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 line-clamp-2">{n.message}</p>
              </div>

              {/* Actions (appear on hover) */}
              <div className="flex-shrink-0 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity mt-0.5">
                {!n.is_read && (
                  <button
                    onClick={(e) => { e.stopPropagation(); markOneMutation.mutate(n.id) }}
                    className="p-1 hover:bg-green-50 dark:hover:bg-slate-600 rounded text-slate-400 hover:text-green-600 dark:hover:text-green-400 transition-colors"
                    title="Mark as read"
                  >
                    <Check size={12} />
                  </button>
                )}
                <button
                  onClick={(e) => { e.stopPropagation(); deleteMutation.mutate(n.id) }}
                  className="p-1 hover:bg-red-50 dark:hover:bg-slate-600 rounded text-slate-400 hover:text-red-500 dark:hover:text-red-400 transition-colors"
                  title="Delete"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            </div>
          )
        })}
      </div>

      {/* Footer */}
      <div className="px-4 py-2.5 border-t border-slate-100 dark:border-slate-700">
        <button
          onClick={() => { router.push('/notifications'); onClose() }}
          className="w-full text-center text-xs text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 transition-colors py-1"
        >
          View all notifications →
        </button>
      </div>
    </div>
  )
})

// ── Main Navbar ───────────────────────────────────────────────────────────────

export const Navbar = React.memo(function Navbar({ onMobileMenuClick, onSearchClick, onAIPanelToggle, aiPanelOpen }: NavbarProps) {
  // Real-time WebSocket notifications — connects once per session
  useNotificationSocket()

  const router = useRouter()
  const pathname = usePathname()
  const { theme, setTheme } = useTheme()
  const { user, logout, isAuthenticated } = useAuthStore()
  const [searchQuery, setSearchQuery] = useState('')
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false)
  const [isNotifOpen, setIsNotifOpen] = useState(false)
  const notifRef = useRef<HTMLDivElement>(null)
  const queryClient = useQueryClient()

  // ── Poll unread count every 60 seconds ──────────────────────────────────────
  // Use accessToken from localStorage directly to avoid Zustand hydration delay
  const hasToken = typeof window !== 'undefined'
    ? !!localStorage.getItem('synapse_access_token')
    : isAuthenticated

  const { data: unreadCount = 0 } = useQuery({
    queryKey: ['unread-count'],
    queryFn: fetchUnreadCount,
    refetchInterval: 60_000,
    staleTime: 30_000,
    enabled: hasToken,         // token in localStorage = user is logged in
    retry: false,
  })

  // ── Close dropdown when clicking outside ────────────────────────────────────
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setIsNotifOpen(false)
      }
    }
    if (isNotifOpen) document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [isNotifOpen])

  // ── Page title ───────────────────────────────────────────────────────────────
  const getPageTitle = () => {
    const routeTitles: Record<string, string> = {
      '/': 'Dashboard',
      '/feed': 'Tech Feed',
      '/github': 'GitHub Radar',
      '/research': 'Research',
      '/videos': 'Videos',
      '/trends': 'Technology Trends',
      '/chat': 'AI Chat',
      '/automation': 'Automation',
      '/agents': 'AI Agents',
      '/documents': 'Document Studio',
      '/library': 'Library',
      '/notifications': 'Notifications',
      '/search': 'Search',
      '/profile': 'My Profile',
      '/settings': 'Settings',
    }
    return (pathname && routeTitles[pathname]) || 'SYNAPSE'
  }

  const handleSearch = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter' && searchQuery.trim()) {
        router.push(`/search?q=${encodeURIComponent(searchQuery.trim())}`)
        setSearchQuery('')
      }
    },
    [searchQuery, router]
  )

  const handleLogout = () => {
    logout()
    router.push('/login')
    setIsUserMenuOpen(false)
  }

  const handleBellClick = () => {
    setIsNotifOpen((prev) => {
      if (!prev) {
        // Pre-fetch when opening
        queryClient.prefetchQuery({
          queryKey: ['navbar-notifications'],
          queryFn: fetchRecentNotifications,
        })
      }
      return !prev
    })
    setIsUserMenuOpen(false)
  }

  return (
    <nav className="sticky top-0 z-30 bg-white/90 dark:bg-slate-900/90 backdrop-blur border-b border-slate-300 dark:border-slate-700/60">
      <div className="flex items-center justify-between h-16 px-3 sm:px-6 gap-2">

        {/* Left: Mobile menu */}
        <div className="flex items-center gap-2 sm:gap-3 min-w-0">
          <button
            onClick={onMobileMenuClick}
            className="inline-flex md:!hidden p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-white shrink-0"
            aria-label="Open sidebar"
          >
            <Menu size={20} />
          </button>
        </div>

        {/* Center: Search — TASK-402-4: pill triggers ⌘K command palette */}
        <div className="hidden md:flex flex-1 max-w-md mx-4 lg:mx-8">
          <button
            onClick={onSearchClick}
            className="w-full flex items-center gap-2 px-3 py-2 bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-400 dark:text-slate-500 hover:border-indigo-300 dark:hover:border-indigo-700 hover:bg-white dark:hover:bg-slate-700/60 transition-colors text-sm"
            aria-label="Open search (⌘K)"
          >
            <Search size={16} className="flex-shrink-0" />
            <span className="flex-1 text-left truncate">Search articles, papers, repos…</span>
            <kbd className="hidden lg:inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded border border-slate-200 dark:border-slate-700 text-[11px] font-mono text-slate-400 dark:text-slate-500 flex-shrink-0">
              <Command size={10} />K
            </kbd>
          </button>
        </div>

        {/* Right: Org Switcher, Theme, Bell, User */}
        <div className="flex items-center gap-1 sm:gap-2 shrink-0">

          {/* Mobile-only search trigger (the full search bar above is md+) */}
          {onSearchClick && (
            <button
              onClick={onSearchClick}
              className="md:hidden p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-white"
              aria-label="Open search"
            >
              <Search size={20} />
            </button>
          )}

          {/* Organization Switcher — hidden on the smallest phones to save room */}
          <div className="hidden sm:block">
            <OrgSwitcher />
          </div>

          {/* AI Assistant panel toggle — TASK-403-2 (xl screens only) */}
          {onAIPanelToggle && (
            <button
              onClick={onAIPanelToggle}
              className={`hidden xl:flex p-2 rounded-lg transition-colors ${
                aiPanelOpen
                  ? 'bg-indigo-100 dark:bg-indigo-900/40 text-indigo-600 dark:text-indigo-400'
                  : 'text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800'
              }`}
              title={aiPanelOpen ? 'Close AI Assistant' : 'Open AI Assistant'}
            >
              <MessageSquare size={20} />
            </button>
          )}

          {/* Dark mode toggle */}
          <button
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-white"
            title="Toggle dark mode"
          >
            {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
          </button>

          {/* Notification bell */}
          <div ref={notifRef} className="relative">
            <button
              onClick={handleBellClick}
              className={`relative p-2 rounded-lg transition-colors text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 ${
                isNotifOpen ? 'bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-white' : ''
              }`}
              title=""
              aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ''}`}
            >
              <Bell size={20} />
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 min-w-[20px] h-[20px] bg-red-500 text-white text-[11px] font-black rounded-full flex items-center justify-center px-1 ring-2 ring-white dark:ring-slate-900 z-10 shadow-lg">
                  {unreadCount > 99 ? '99+' : unreadCount}
                </span>
              )}
            </button>

            {isNotifOpen && (
              <NotificationDropdown onClose={() => setIsNotifOpen(false)} />
            )}
          </div>

          {/* Plan badge */}
          <PlanBadge />

          {/* User menu */}
          <div className="relative">
            <button
              onClick={() => { setIsUserMenuOpen(!isUserMenuOpen); setIsNotifOpen(false) }}
              className="flex items-center gap-2 p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
            >
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-cyan-500 flex items-center justify-center">
                <span className="text-white dark:text-white font-bold text-xs">
                  {user?.first_name?.[0]}{user?.last_name?.[0]}
                </span>
              </div>
              <span className="hidden sm:inline text-sm text-slate-600 dark:text-slate-300">{user?.first_name}</span>
            </button>

            {isUserMenuOpen && (
              <div className="absolute right-0 mt-2 w-48 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl shadow-card overflow-hidden z-50">
                <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-700">
                  <p className="text-sm font-medium text-slate-800 dark:text-white">
                    {user?.first_name} {user?.last_name}
                  </p>
                  <p className="text-xs text-slate-400">{user?.email}</p>
                </div>
                <Link
                  href="/profile"
                  onClick={() => setIsUserMenuOpen(false)}
                  className="flex items-center gap-3 px-4 py-2 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
                >
                  <User size={16} /><span className="text-sm">Profile</span>
                </Link>
                <Link
                  href="/settings"
                  onClick={() => setIsUserMenuOpen(false)}
                  className="flex items-center gap-3 px-4 py-2 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
                >
                  <Settings size={16} /><span className="text-sm">Settings</span>
                </Link>
                <Link
                  href="/billing"
                  onClick={() => setIsUserMenuOpen(false)}
                  className="flex items-center gap-3 px-4 py-2 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
                >
                  <CreditCard size={16} /><span className="text-sm">Billing</span>
                </Link>
                <button
                  onClick={handleLogout}
                  className="w-full flex items-center gap-3 px-4 py-2 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors border-t border-slate-700"
                >
                  <LogOut size={16} /><span className="text-sm">Logout</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </nav>
  )
})
