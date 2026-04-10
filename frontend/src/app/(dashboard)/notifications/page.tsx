'use client'

import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { toast } from 'react-hot-toast'
import {
  Bell, Check, Trash2, CheckCheck, Loader2, Settings,
  Zap, Info, AlertTriangle, AlertCircle, CheckCircle2, X,
} from 'lucide-react'
import Link from 'next/link'
import { api } from '@/utils/api'
import { cn } from '@/utils/helpers'

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

type FilterType = 'all' | 'unread' | 'read'

// ── Helpers ───────────────────────────────────────────────────────────────────

function extractList<T>(raw: unknown): T[] {
  if (Array.isArray(raw)) return raw as T[]
  if (raw && typeof raw === 'object') {
    const obj = raw as Record<string, unknown>
    const inner = obj['data'] ?? obj
    if (Array.isArray(inner)) return inner as T[]
    if (inner && typeof inner === 'object') {
      const obj2 = inner as Record<string, unknown>
      if (Array.isArray(obj2['results'])) return obj2['results'] as T[]
      if (Array.isArray(obj2['data'])) return obj2['data'] as T[]
    }
  }
  return []
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diff / 60000)
  if (m < 1)  return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.floor(h / 24)
  if (d < 7)  return `${d}d ago`
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}

// ── Config ────────────────────────────────────────────────────────────────────

const NOTIF_CONFIG: Record<string, {
  icon: React.ElementType; iconBg: string; iconColour: string;
  borderColour: string; label: string;
}> = {
  workflow_complete: { icon: Zap,           iconBg: 'bg-indigo-500/15', iconColour: 'text-indigo-600 dark:text-indigo-400', borderColour: 'border-indigo-500/30', label: 'Workflow' },
  success:          { icon: CheckCircle2,   iconBg: 'bg-emerald-500/15',iconColour: 'text-emerald-600 dark:text-emerald-400',borderColour: 'border-emerald-500/30',label: 'Success' },
  info:             { icon: Info,           iconBg: 'bg-blue-500/15',   iconColour: 'text-blue-600 dark:text-blue-400',   borderColour: 'border-blue-500/30',   label: 'Info' },
  warning:          { icon: AlertTriangle,  iconBg: 'bg-amber-500/15',  iconColour: 'text-amber-600 dark:text-amber-400',  borderColour: 'border-amber-500/30',  label: 'Warning' },
  error:            { icon: AlertCircle,    iconBg: 'bg-red-500/15',    iconColour: 'text-red-400',    borderColour: 'border-red-500/30',    label: 'Error' },
}
const DEFAULT_CONFIG = NOTIF_CONFIG.info

// ── NotificationCard ──────────────────────────────────────────────────────────

function NotificationCard({
  notif,
  onMarkRead,
  onDelete,
  markingRead,
  deleting,
}: {
  notif: Notification
  onMarkRead: (id: string) => void
  onDelete: (id: string) => void
  markingRead: boolean
  deleting: boolean
}) {
  const cfg = NOTIF_CONFIG[notif.notif_type] ?? DEFAULT_CONFIG
  const Icon = cfg.icon

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: 40, transition: { duration: 0.2 } }}
      className={cn(
        'group relative bg-white dark:bg-slate-800/80 border rounded-2xl p-4 sm:p-5 transition-all duration-200 overflow-hidden shadow-card',
        !notif.is_read
          ? `${cfg.borderColour} hover:shadow-md`
          : 'border-slate-200 dark:border-slate-700/50 opacity-75 hover:opacity-100',
      )}
    >
      {/* Unread left accent */}
      {!notif.is_read && (
        <div className={cn('absolute left-0 top-4 bottom-4 w-0.5 rounded-r-full', cfg.iconColour.replace('text-', 'bg-'))} />
      )}

      <div className="flex items-start gap-3 sm:gap-4">
        {/* Icon */}
        <div className={cn('flex-shrink-0 w-9 h-9 sm:w-10 sm:h-10 rounded-xl flex items-center justify-center', cfg.iconBg)}>
          <Icon size={18} className={cfg.iconColour} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2 flex-wrap mb-0.5">
            <div className="flex items-center gap-2 flex-wrap min-w-0">
              <p className={cn('text-sm font-bold truncate', notif.is_read ? 'text-slate-500 dark:text-slate-300' : 'text-slate-900 dark:text-white')}>
                {notif.title}
              </p>
              <span className={cn('text-[10px] font-semibold px-1.5 py-0.5 rounded-full border shrink-0', cfg.iconBg, cfg.iconColour, cfg.borderColour)}>
                {cfg.label}
              </span>
              {!notif.is_read && (
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 shrink-0" />
              )}
            </div>
            <span className="text-xs text-slate-500 whitespace-nowrap shrink-0">{timeAgo(notif.created_at)}</span>
          </div>

          <p className="text-xs sm:text-sm text-slate-400 leading-relaxed mb-2.5">{notif.message}</p>

          {/* Metadata chips */}
          {notif.metadata && Object.keys(notif.metadata).length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-3">
              {Object.entries(notif.metadata).slice(0, 4).map(([k, v]) => (
                <span key={k} className="text-[10px] bg-slate-100 dark:bg-slate-700/80 border border-slate-300 dark:border-slate-600/50 text-slate-600 dark:text-slate-400 rounded-lg px-2 py-0.5 max-w-[160px] truncate">
                  {k}: {String(v).slice(0, 25)}
                </span>
              ))}
            </div>
          )}

          {/* Action row */}
          <div className="flex items-center gap-2 pt-2 border-t border-slate-200 dark:border-slate-700/50">
            {!notif.is_read && (
              <button
                onClick={() => onMarkRead(notif.id)}
                disabled={markingRead}
                className="flex items-center gap-1 text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:text-indigo-500 dark:hover:text-indigo-300 transition-colors disabled:opacity-50"
              >
                {markingRead ? <Loader2 size={11} className="animate-spin" /> : <Check size={11} />}
                Mark read
              </button>
            )}
            <button
              onClick={() => onDelete(notif.id)}
              disabled={deleting}
              className="flex items-center gap-1 text-xs font-semibold text-slate-500 dark:text-slate-600 hover:text-red-500 dark:hover:text-red-400 transition-colors disabled:opacity-50 ml-auto"
            >
              {deleting ? <Loader2 size={11} className="animate-spin" /> : <Trash2 size={11} />}
              Delete
            </button>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function NotificationsPage() {
  const queryClient = useQueryClient()
  const [filter, setFilter] = useState<FilterType>('all')
  const [markingId, setMarkingId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const { data: rawNotifications = [], isLoading } = useQuery({
    queryKey: ['all-notifications'],
    queryFn: async () => {
      const { data } = await api.get('/notifications/')
      return extractList<Notification>(data)
    },
    refetchInterval: 30_000, // poll every 30s for new notifications
  })

  const markAllMutation = useMutation({
    mutationFn: () => api.post('/notifications/read-all/'),
    onSuccess: () => {
      toast.success('All notifications marked as read')
      queryClient.invalidateQueries({ queryKey: ['all-notifications'] })
      queryClient.invalidateQueries({ queryKey: ['unread-count'] })
    },
  })

  const markOneMutation = useMutation({
    mutationFn: (id: string) => api.post(`/notifications/${id}/read/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['all-notifications'] })
      queryClient.invalidateQueries({ queryKey: ['unread-count'] })
    },
    onSettled: () => setMarkingId(null),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/notifications/${id}/`),
    onSuccess: () => {
      toast.success('Notification deleted')
      queryClient.invalidateQueries({ queryKey: ['all-notifications'] })
      queryClient.invalidateQueries({ queryKey: ['unread-count'] })
    },
    onSettled: () => setDeletingId(null),
  })

  const handleMarkRead = (id: string) => { setMarkingId(id); markOneMutation.mutate(id) }
  const handleDelete   = (id: string) => { setDeletingId(id); deleteMutation.mutate(id) }

  const unreadCount = rawNotifications.filter(n => !n.is_read).length
  const filtered = rawNotifications.filter(n => {
    if (filter === 'unread') return !n.is_read
    if (filter === 'read')   return  n.is_read
    return true
  })

  return (
    <div className="flex-1 overflow-y-auto bg-slate-50 dark:bg-slate-950 p-4 sm:p-6">
      <div className="max-w-2xl mx-auto pb-10 space-y-4 sm:space-y-5">

        {/* ── Header ── */}
        <div className="flex flex-col xs:flex-row xs:items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="relative shrink-0">
              <div className="w-10 h-10 rounded-2xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center">
                <Bell size={18} className="text-indigo-600 dark:text-indigo-400" />
              </div>
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] bg-red-500 text-white text-[10px] font-black rounded-full flex items-center justify-center px-1">
                  {unreadCount > 9 ? '9+' : unreadCount}
                </span>
              )}
            </div>
            <div className="min-w-0">
              <h1 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-white leading-tight">Notifications</h1>
              <p className="text-slate-400 text-xs sm:text-sm">
                {unreadCount > 0
                  ? `${unreadCount} unread notification${unreadCount !== 1 ? 's' : ''}`
                  : 'All caught up! 🎉'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {unreadCount > 0 && (
              <button
                onClick={() => markAllMutation.mutate()}
                disabled={markAllMutation.isPending}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold rounded-xl transition-colors whitespace-nowrap"
              >
                {markAllMutation.isPending
                  ? <Loader2 size={12} className="animate-spin" />
                  : <CheckCheck size={12} />
                }
                Mark all read
              </button>
            )}
            <Link
              href="/settings"
              className="p-2 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-white hover:border-slate-400 dark:hover:border-slate-600 transition-all"
              title="Notification settings"
            >
              <Settings size={15} />
            </Link>
          </div>
        </div>

        {/* ── Filter tabs ── */}
        {rawNotifications.length > 0 && (
          <div className="flex gap-1 bg-slate-100 dark:bg-slate-800/80 rounded-xl p-1 w-fit">
            {(['all', 'unread', 'read'] as FilterType[]).map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={cn(
                  'px-3 py-1.5 rounded-lg text-xs font-semibold transition-all capitalize',
                  filter === f ? 'bg-indigo-600 text-white' : 'text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-white'
                )}
              >
                {f}
                {f === 'unread' && unreadCount > 0 && (
                  <span className="ml-1.5 bg-red-500 text-white text-[9px] font-black px-1.5 py-0.5 rounded-full">
                    {unreadCount}
                  </span>
                )}
              </button>
            ))}
          </div>
        )}

        {/* ── Content ── */}
        {isLoading ? (
          <div className="space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="bg-slate-100 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-2xl p-4 animate-pulse h-[88px]" />
            ))}
          </div>
        ) : rawNotifications.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="w-20 h-20 rounded-2xl bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 flex items-center justify-center mx-auto mb-4">
              <Bell size={32} className="text-slate-500 dark:text-slate-600" />
            </div>
            <h3 className="text-slate-800 dark:text-white font-bold text-lg mb-1">No notifications yet</h3>
            <p className="text-slate-500 text-sm max-w-xs leading-relaxed">
              Notifications appear here when your workflows complete, AI tasks finish, or when there are important updates.
            </p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16 bg-slate-100 dark:bg-slate-900/50 rounded-2xl border border-slate-200 dark:border-slate-700">
            <X size={32} className="mx-auto text-slate-400 dark:text-slate-600 mb-3" />
            <p className="text-slate-400 text-sm">No {filter} notifications</p>
            <button onClick={() => setFilter('all')} className="text-indigo-400 text-xs mt-2 hover:underline">View all</button>
          </div>
        ) : (
          <AnimatePresence mode="popLayout">
            <motion.div className="space-y-2.5 sm:space-y-3">
              {filtered.map(n => (
                <NotificationCard
                  key={n.id}
                  notif={n}
                  onMarkRead={handleMarkRead}
                  onDelete={handleDelete}
                  markingRead={markingId === n.id && markOneMutation.isPending}
                  deleting={deletingId === n.id && deleteMutation.isPending}
                />
              ))}
            </motion.div>
          </AnimatePresence>
        )}
      </div>
    </div>
  )
}
