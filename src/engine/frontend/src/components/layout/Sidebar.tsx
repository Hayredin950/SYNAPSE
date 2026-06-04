'use client'

import React, { memo, useMemo } from 'react'
import { Tooltip } from '@/components/ui/Tooltip'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard, Newspaper, GitBranch, BookOpen,
  MessageSquare, Zap, Library, LogOut, User as UserIcon,
  ChevronLeft, ChevronRight, Bot, Youtube, TrendingUp, Twitter, CreditCard, Building2, BarChart3,
} from 'lucide-react'
import { useAuthStore } from '@/store/authStore'

interface SidebarProps {
  isCollapsed: boolean
  onToggle: () => void
  mobileOpen: boolean
  onMobileClose: () => void
}

const NAV_LINKS = [
  { href: '/',           label: 'Home',         icon: LayoutDashboard, accent: '#6366f1' },
  { href: '/feed',       label: 'Tech Feed',     icon: Newspaper,       accent: '#06b6d4' },
  { href: '/github',     label: 'GitHub Radar',  icon: GitBranch,       accent: '#22c55e' },
  { href: '/research',   label: 'Research',      icon: BookOpen,        accent: '#8b5cf6' },
  { href: '/videos',     label: 'Videos',        icon: Youtube,         accent: '#ef4444' },
  { href: '/tweets',     label: 'X Feed',        icon: Twitter,         accent: '#1d9bf0' },
  { href: '/trends',     label: 'Trends',        icon: TrendingUp,      accent: '#f59e0b' },
  { href: '/chat',       label: 'AI Chat',       icon: MessageSquare,   accent: '#0ea5e9' },
  { href: '/automation', label: 'Automation',    icon: Zap,             accent: '#eab308' },
  { href: '/agents',     label: 'AI Agents',     icon: Bot,             accent: '#ec4899' },
  { href: '/library',    label: 'Library',       icon: Library,         accent: '#14b8a6' },
  { href: '/analytics',  label: 'Analytics',     icon: BarChart3,       accent: '#10b981' },
  { href: '/billing',        label: 'Billing',        icon: CreditCard,  accent: '#f59e0b' },
  { href: '/organizations',  label: 'Organizations',  icon: Building2,   accent: '#8b5cf6' },
]

export const Sidebar = memo(function Sidebar({
  isCollapsed, onToggle, mobileOpen, onMobileClose,
}: SidebarProps) {
  const pathname = usePathname()
  const { user, logout } = useAuthStore()

  const initials = useMemo(() => {
    if (user?.first_name) return (user.first_name[0] + (user.last_name?.[0] || '')).toUpperCase()
    return (user?.email?.[0] || 'U').toUpperCase()
  }, [user])

  const displayName = useMemo(() =>
    user?.first_name ? `${user.first_name} ${user.last_name || ''}`.trim() : user?.username || '',
  [user])

  return (
    <aside className={`
      fixed left-0 top-0 h-screen flex flex-col z-50
      transition-all duration-300 ease-in-out
      bg-white dark:bg-slate-950
      border-r border-slate-300 dark:border-slate-800/60
      ${isCollapsed ? 'w-[72px]' : 'w-64'}
      md:translate-x-0
      ${mobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
    `}>
      {/* Top accent line */}
      <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-indigo-500 via-violet-500 to-cyan-500" />

      {/* Header */}
      <div className="flex items-center justify-between h-16 px-4 border-b border-slate-300 dark:border-slate-800/60">
        {!isCollapsed && (
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl animated-gradient flex items-center justify-center flex-shrink-0 shadow-glow-indigo">
              <span className="text-white dark:text-white font-black text-sm">S</span>
            </div>
            <h1 className="text-base font-black gradient-text tracking-tight">SYNAPSE</h1>
          </div>
        )}
        {isCollapsed && (
          <div className="w-9 h-9 rounded-xl animated-gradient flex items-center justify-center mx-auto shadow-glow-indigo">
            <span className="text-white dark:text-white font-black text-sm">S</span>
          </div>
        )}

        {!isCollapsed && (
          <button
            onClick={onToggle}
            className="hidden md:flex p-1.5 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors text-slate-500 hover:text-slate-700 dark:hover:text-slate-200"
            title="Collapse sidebar"
          >
            <ChevronLeft size={16} />
          </button>
        )}
        <button
          onClick={onMobileClose}
          className="md:hidden p-1.5 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors text-slate-500 hover:text-slate-700 dark:hover:text-slate-200"
          title="Close sidebar"
        >
          <ChevronLeft size={16} />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto scrollbar-hide py-3 px-2 space-y-0.5">
        {isCollapsed && (
          <Tooltip content="Expand sidebar" side="right">
            <button
              onClick={onToggle}
              className="w-full flex items-center justify-center p-2.5 mb-2 rounded-xl text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 dark:hover:bg-slate-800 transition-all"
            >
              <ChevronRight size={18} />
            </button>
          </Tooltip>
        )}

        {NAV_LINKS.map(({ href, label, icon: Icon, accent }) => {
          const active = pathname === href
          const linkEl = (
            <Link
              href={href}
              prefetch={true}
              className={`
                flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-150 group relative
                ${active
                  ? 'bg-indigo-50 dark:bg-indigo-600/15 text-indigo-700 dark:text-white'
                  : 'text-slate-700 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/60 hover:text-slate-900 dark:hover:text-slate-100'
                }
                ${isCollapsed ? 'justify-center' : ''}
              `}
            >
              {active && (
                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-indigo-500 rounded-r-full" />
              )}
              <Icon
                size={18}
                className="flex-shrink-0 transition-colors"
                style={{ color: active ? accent : undefined }}
              />
              {!isCollapsed && (
                <span className={`text-sm font-medium truncate ${active ? 'font-semibold' : ''}`}>
                  {label}
                </span>
              )}
            </Link>
          )
          return isCollapsed ? (
            <Tooltip key={href} content={label} side="right">
              {linkEl}
            </Tooltip>
          ) : (
            <React.Fragment key={href}>
              {linkEl}
            </React.Fragment>
          )
        })}
      </nav>

      {/* User Section */}
      <div className="border-t border-slate-300 dark:border-slate-800/60 p-3">
        {isCollapsed ? (
          <div className="flex flex-col items-center gap-2">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-500 flex items-center justify-center flex-shrink-0 shadow-glow-indigo">
              <span className="text-white dark:text-white font-bold text-xs">{initials}</span>
            </div>
            <Tooltip content="Logout" side="right">
              <button
                onClick={logout}
                className="p-2 rounded-lg text-slate-500 hover:bg-red-50 dark:hover:bg-red-900/20 hover:text-red-600 dark:hover:text-red-500 transition-colors"
              >
                <LogOut size={15} />
              </button>
            </Tooltip>
          </div>
        ) : (
          <div className="flex items-center justify-between gap-2 px-1">
            <div className="flex items-center gap-2.5 min-w-0 flex-1">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-500 flex items-center justify-center flex-shrink-0 shadow-glow-indigo">
                <span className="text-white dark:text-white font-bold text-xs">{initials}</span>
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-slate-900 dark:text-white truncate leading-tight">{displayName}</p>
                <p className="text-xs text-slate-600 dark:text-slate-500 truncate">{user?.email}</p>
              </div>
            </div>
            <button
              onClick={logout}
              className="p-2 rounded-lg text-slate-500 hover:bg-red-50 dark:hover:bg-red-900/20 hover:text-red-600 dark:hover:text-red-500 transition-colors flex-shrink-0"
              title="Logout"
            >
              <LogOut size={15} />
            </button>
          </div>
        )}
      </div>
    </aside>
  )
})

// ── TASK-404-1: Mobile Bottom Navigation Bar ──────────────────────────────────
// Shown only on < md screens; replaces sidebar for mobile users.

const MOBILE_BOTTOM_TABS = [
  { href: '/',       label: 'Home',    icon: LayoutDashboard, accent: '#6366f1' },
  { href: '/feed',   label: 'Feed',    icon: Newspaper,       accent: '#06b6d4' },
  { href: '/chat',   label: 'Chat',    icon: MessageSquare,   accent: '#0ea5e9' },
  { href: '/agents', label: 'Agents',  icon: Bot,             accent: '#ec4899' },
  { href: '/profile',label: 'Profile', icon: UserIcon,        accent: '#8b5cf6' },
] as const

export function MobileBottomNav() {
  const pathname = usePathname()

  return (
    <nav
      className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-white/95 dark:bg-slate-900/95 backdrop-blur border-t border-slate-200 dark:border-slate-800 safe-bottom"
      aria-label="Mobile navigation"
    >
      <div className="flex items-center justify-around h-16 px-2">
        {MOBILE_BOTTOM_TABS.map(({ href, label, icon: Icon, accent }) => {
          const active = pathname === href || (href !== '/' && pathname?.startsWith(href))
          return (
            <Link
              key={href}
              href={href}
              prefetch={true}
              className={`flex flex-col items-center gap-1 px-3 py-2 rounded-xl transition-colors ${
                active ? 'text-indigo-600 dark:text-indigo-400' : 'text-slate-500 dark:text-slate-400'
              }`}
            >
              <Icon
                size={20}
                style={{ color: active ? accent : undefined }}
                className={active ? 'drop-shadow-sm' : ''}
              />
              <span className={`text-[10px] font-medium ${active ? 'font-semibold' : ''}`}>
                {label}
              </span>
            </Link>
          )
        })}
      </div>
    </nav>
  )
}
