'use client'

/**
 * Feature #2: Topic Watchlist with Alerts
 * Watch keywords → get notified when new content matches.
 */

import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { Bell, Plus, X, Loader2, AlertCircle } from 'lucide-react'
import { api } from '@/utils/api'
import toast from 'react-hot-toast'
import Link from 'next/link'

interface WatchItem {
  id:               string
  keyword:          string
  notify_frequency: string
  created_at:       string
}

interface Alert {
  keyword:   string
  new_count: number
}

export function TopicWatchlist() {
  const [newKw, setNewKw] = useState('')
  const [open,  setOpen]  = useState(false)
  const qc = useQueryClient()

  const { data, isLoading } = useQuery<{ watchlist: WatchItem[]; alerts: Alert[] }>({
    queryKey: ['watchlist'],
    queryFn: () => api.get('/social/watchlist/').then(r => r.data),
    staleTime: 60000,
  })

  const addMutation = useMutation({
    mutationFn: (keyword: string) => api.post('/social/watchlist/', { keyword }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['watchlist'] }); setNewKw(''); toast.success('Watching!') },
    onError: (e: any) => toast.error(e?.response?.data?.error || 'Already watching'),
  })

  const removeMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/social/watchlist/${id}/`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['watchlist'] }),
  })

  const items  = data?.watchlist ?? []
  const alerts = data?.alerts ?? []
  const alertCount = alerts.length

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="relative flex items-center gap-2 px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm text-slate-600 dark:text-slate-300 hover:border-indigo-400 transition-colors"
      >
        <Bell size={15} />
        <span>Watchlist</span>
        {alertCount > 0 && (
          <span className="absolute -top-1.5 -right-1.5 w-5 h-5 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center">
            {alertCount}
          </span>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <>
            <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: -8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="absolute right-0 top-full mt-2 w-80 bg-white dark:bg-slate-800 rounded-2xl shadow-xl border border-slate-200 dark:border-slate-700 z-40 overflow-hidden"
            >
              <div className="p-4">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-semibold text-sm text-slate-800 dark:text-slate-100 flex items-center gap-2">
                    <Bell size={14} className="text-indigo-500" /> Topic Watchlist
                  </h3>
                  <button onClick={() => setOpen(false)}><X size={15} className="text-slate-400" /></button>
                </div>

                {/* Alerts */}
                {alertCount > 0 && (
                  <div className="mb-3 space-y-1.5">
                    {alerts.map(a => (
                      <div key={a.keyword} className="flex items-center gap-2 p-2 bg-amber-50 dark:bg-amber-900/20 rounded-lg text-xs">
                        <AlertCircle size={12} className="text-amber-500 flex-shrink-0" />
                        <span className="text-amber-700 dark:text-amber-300 font-medium">{a.new_count} new</span>
                        <Link href={`/search?q=${encodeURIComponent(a.keyword)}`} className="text-amber-600 dark:text-amber-400 hover:underline truncate" onClick={() => setOpen(false)}>
                          "{a.keyword}"
                        </Link>
                      </div>
                    ))}
                  </div>
                )}

                {/* Add form */}
                <div className="flex gap-2 mb-3">
                  <input
                    value={newKw}
                    onChange={e => setNewKw(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter' && newKw.trim()) addMutation.mutate(newKw.trim()) }}
                    placeholder="Add keyword…"
                    className="flex-1 px-3 py-1.5 text-sm border border-slate-200 dark:border-slate-600 rounded-lg bg-slate-50 dark:bg-slate-700 text-slate-800 dark:text-slate-200 focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  />
                  <button
                    onClick={() => newKw.trim() && addMutation.mutate(newKw.trim())}
                    disabled={!newKw.trim() || addMutation.isPending}
                    className="px-3 py-1.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
                  >
                    {addMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
                  </button>
                </div>

                {/* List */}
                {isLoading ? (
                  <div className="py-4 flex justify-center"><Loader2 size={20} className="animate-spin text-slate-400" /></div>
                ) : items.length === 0 ? (
                  <p className="text-xs text-slate-400 text-center py-3">No keywords yet.<br />Add topics to track!</p>
                ) : (
                  <div className="space-y-1.5 max-h-48 overflow-y-auto">
                    {items.map(item => (
                      <div key={item.id} className="flex items-center gap-2 p-2 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 group">
                        <Bell size={12} className="text-slate-400 flex-shrink-0" />
                        <Link
                          href={`/search?q=${encodeURIComponent(item.keyword)}`}
                          className="flex-1 text-sm text-slate-700 dark:text-slate-200 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors truncate"
                          onClick={() => setOpen(false)}
                        >
                          {item.keyword}
                        </Link>
                        <span className="text-[10px] text-slate-400 capitalize">{item.notify_frequency}</span>
                        <button
                          onClick={() => removeMutation.mutate(item.id)}
                          className="opacity-0 group-hover:opacity-100 p-0.5 hover:text-red-500 transition-all"
                        >
                          <X size={12} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}
