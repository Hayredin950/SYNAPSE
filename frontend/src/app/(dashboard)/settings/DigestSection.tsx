'use client'

/**
 * DigestSection — Weekly AI Digest email preferences
 *
 * TASK-201: Allows users to enable/disable the weekly digest and choose
 * their preferred delivery day. Persists to GET/PATCH /api/v1/auth/me/digest/
 */

import React, { useState, useEffect } from 'react'
import { api } from '@/utils/api'
import toast from 'react-hot-toast'
import { Loader2, Save, Mail } from 'lucide-react'

const DAYS = [
  { value: 'monday',    label: 'Mon' },
  { value: 'tuesday',   label: 'Tue' },
  { value: 'wednesday', label: 'Wed' },
  { value: 'thursday',  label: 'Thu' },
  { value: 'friday',    label: 'Fri' },
  { value: 'saturday',  label: 'Sat' },
  { value: 'sunday',    label: 'Sun' },
]

interface DigestPrefs {
  digest_enabled: boolean
  digest_day: string
}

export function DigestSection() {
  const [prefs, setPrefs]     = useState<DigestPrefs>({ digest_enabled: true, digest_day: 'monday' })
  const [loaded, setLoaded]   = useState(false)
  const [saving, setSaving]   = useState(false)
  const [dirty, setDirty]     = useState(false)

  // ── Load current preferences ──────────────────────────────────────────────
  useEffect(() => {
    const controller = new AbortController()
    api.get<DigestPrefs>('/users/me/digest/', { signal: controller.signal })
      .then(({ data }) => {
        setPrefs(data)
        setLoaded(true)
      })
      .catch((e) => {
        if (!e?.name?.includes('Cancel') && !e?.message?.includes('canceled')) {
          // Non-fatal — show defaults if API fails
          setLoaded(true)
        }
      })
    return () => controller.abort()
  }, [])

  const update = (patch: Partial<DigestPrefs>) => {
    setPrefs(p => ({ ...p, ...patch }))
    setDirty(true)
  }

  // ── Save ──────────────────────────────────────────────────────────────────
  const handleSave = async () => {
    setSaving(true)
    try {
      const { data } = await api.patch<DigestPrefs>('/users/me/digest/', prefs)
      setPrefs(data)
      setDirty(false)
      toast.success('Digest preferences saved!')
    } catch {
      toast.error('Failed to save digest preferences.')
    } finally {
      setSaving(false)
    }
  }

  // ── Loading skeleton ──────────────────────────────────────────────────────
  if (!loaded) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="h-5 w-48 bg-slate-200 dark:bg-slate-700 rounded" />
        <div className="h-9 w-full bg-slate-100 dark:bg-slate-800 rounded-lg" />
        <div className="h-9 w-32 bg-indigo-100 dark:bg-indigo-900/50 rounded-lg" />
      </div>
    )
  }

  return (
    <div className="space-y-5">
      {/* Enable toggle */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 p-1.5 rounded-lg bg-indigo-500/10">
            <Mail size={14} className="text-indigo-400" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-800 dark:text-white">
              Weekly AI Digest
            </p>
            <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">
              Receive a curated email with the top articles, research papers, and
              repositories from the past week — delivered on your chosen day.
            </p>
          </div>
        </div>

        {/* Toggle switch */}
        <button
          role="switch"
          aria-checked={prefs.digest_enabled}
          onClick={() => update({ digest_enabled: !prefs.digest_enabled })}
          className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 ${
            prefs.digest_enabled
              ? 'bg-indigo-600'
              : 'bg-slate-300 dark:bg-slate-700'
          }`}
        >
          <span
            className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
              prefs.digest_enabled ? 'translate-x-6' : 'translate-x-1'
            }`}
          />
        </button>
      </div>

      {/* Delivery day picker — only shown when enabled */}
      {prefs.digest_enabled && (
        <div className="pl-8">
          <p className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-2">
            Delivery day
          </p>
          <div className="flex flex-wrap gap-2">
            {DAYS.map(({ value, label }) => (
              <button
                key={value}
                onClick={() => update({ digest_day: value })}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                  prefs.digest_day === value
                    ? 'border-indigo-500 bg-indigo-600/20 text-indigo-700 dark:text-indigo-300'
                    : 'border-slate-300 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:border-slate-400 dark:hover:border-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <p className="text-xs text-slate-500 mt-2">
            Your digest arrives every{' '}
            <span className="font-semibold text-slate-700 dark:text-slate-300 capitalize">
              {prefs.digest_day}
            </span>{' '}
            at 08:00 UTC.
          </p>
        </div>
      )}

      {/* Save button — only shown when changes are pending */}
      {dirty && (
        <div className="pl-8">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm rounded-lg transition-colors font-medium"
          >
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            Save Preferences
          </button>
        </div>
      )}
    </div>
  )
}
