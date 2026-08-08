'use client'

/**
 * GitHubSection — GitHub OAuth connection management
 *
 * TASK-202-2: Shows connection status, links to GitHub profile, and provides
 * a disconnect button. Reads github_username from the /api/v1/auth/me/ endpoint.
 *
 * States:
 *   loading    — skeleton while fetching user
 *   connected  — green badge, avatar, profile link, disconnect button
 *   disconnected — "Connect GitHub" button → redirects to OAuth flow
 */

import React, { useState, useEffect } from 'react'
import { api } from '@/utils/api'
import toast from 'react-hot-toast'
import { Loader2, ExternalLink, Unlink, Github } from 'lucide-react'

interface MeResponse {
  github_username?: string | null
  has_usable_password?: boolean
}

export function GitHubSection() {
  const [githubUsername, setGithubUsername] = useState<string | null>(null)
  const [hasPassword, setHasPassword]       = useState(true)
  const [loaded, setLoaded]                 = useState(false)
  const [disconnecting, setDisconnecting]   = useState(false)

  // ── Load current user ──────────────────────────────────────────────────────
  useEffect(() => {
    const controller = new AbortController()
    api.get<MeResponse>('/users/me/', { signal: controller.signal })
      .then(({ data }) => {
        setGithubUsername(data.github_username ?? null)
        setHasPassword(data.has_usable_password ?? true)
        setLoaded(true)
      })
      .catch((e) => {
        if (!e?.name?.includes('Cancel') && !e?.message?.includes('canceled')) {
          setLoaded(true)
        }
      })
    return () => controller.abort()
  }, [])

  // ── Connect — redirect to backend OAuth initiation ─────────────────────────
  const handleConnect = () => {
    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? ''
    window.location.href = `${apiBase}/api/v1/auth/github/`
  }

  // ── Disconnect ─────────────────────────────────────────────────────────────
  const handleDisconnect = async () => {
    if (!hasPassword) {
      toast.error(
        'Set a password before disconnecting GitHub — otherwise you won\'t be able to log in.',
        { duration: 6000 }
      )
      return
    }

    const confirmed = window.confirm(
      'Disconnect your GitHub account? You can reconnect at any time.'
    )
    if (!confirmed) return

    setDisconnecting(true)
    try {
      await api.delete('/users/github/disconnect/')
      setGithubUsername(null)
      toast.success('GitHub account disconnected.')
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { error?: string } } })?.response?.data?.error
        ?? 'Failed to disconnect GitHub.'
      toast.error(msg)
    } finally {
      setDisconnecting(false)
    }
  }

  // ── Loading skeleton ───────────────────────────────────────────────────────
  if (!loaded) {
    return (
      <div className="flex items-center gap-4 animate-pulse">
        <div className="w-9 h-9 rounded-full bg-slate-200 dark:bg-slate-700" />
        <div className="flex-1 space-y-2">
          <div className="h-4 w-32 bg-slate-200 dark:bg-slate-700 rounded" />
          <div className="h-3 w-48 bg-slate-100 dark:bg-slate-800 rounded" />
        </div>
        <div className="h-8 w-24 bg-slate-200 dark:bg-slate-700 rounded-lg" />
      </div>
    )
  }

  // ── Connected state ────────────────────────────────────────────────────────
  if (githubUsername) {
    const avatarUrl = `https://github.com/${githubUsername}.png?size=72`
    const profileUrl = `https://github.com/${githubUsername}`

    return (
      <div className="flex items-center gap-4">
        {/* Avatar */}
        <a
          href={profileUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="shrink-0"
          title={`github.com/${githubUsername}`}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={avatarUrl}
            alt={`@${githubUsername}`}
            width={36}
            height={36}
            className="rounded-full border-2 border-green-500/40 hover:border-green-400 transition-colors"
          />
        </a>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-slate-800 dark:text-white truncate">
              @{githubUsername}
            </span>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium
              bg-green-100 dark:bg-green-500/15 text-green-700 dark:text-green-400
              border border-green-200 dark:border-green-500/30">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
              Connected
            </span>
          </div>
          <a
            href={profileUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-slate-400 hover:text-indigo-400 transition-colors flex items-center gap-1 mt-0.5 w-fit"
          >
            github.com/{githubUsername}
            <ExternalLink size={10} />
          </a>
          <p className="text-xs text-slate-500 mt-1">
            Starred repositories are synced to your SYNAPSE knowledge base.
          </p>
        </div>

        {/* Disconnect */}
        <button
          onClick={handleDisconnect}
          disabled={disconnecting}
          className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
            border border-red-300 dark:border-red-500/40 text-red-600 dark:text-red-400
            hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors disabled:opacity-50"
          title={!hasPassword ? 'Set a password before disconnecting' : 'Disconnect GitHub'}
        >
          {disconnecting
            ? <Loader2 size={12} className="animate-spin" />
            : <Unlink size={12} />
          }
          Disconnect
        </button>
      </div>
    )
  }

  // ── Disconnected state ─────────────────────────────────────────────────────
  return (
    <div className="flex items-center justify-between gap-4">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 p-2 rounded-lg bg-slate-200 dark:bg-slate-800">
          <Github size={16} className="text-slate-600 dark:text-slate-300" />
        </div>
        <div>
          <p className="text-sm font-medium text-slate-800 dark:text-white">Connect GitHub</p>
          <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">
            Sign in with GitHub to sync your starred repositories into your SYNAPSE
            knowledge base and enable one-click login.
          </p>
        </div>
      </div>

      <button
        onClick={handleConnect}
        className="shrink-0 flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium
          bg-slate-900 hover:bg-slate-700 dark:bg-slate-800 dark:hover:bg-slate-700
          text-white border border-slate-700 dark:border-slate-600 transition-colors shadow-sm"
      >
        <Github size={15} />
        Connect
      </button>
    </div>
  )
}
