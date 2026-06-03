'use client'

/**
 * /profile — User profile page
 * Shows avatar, name, email, bio, stats and lets the user update their info.
 */

import React, { useState, useEffect } from 'react'
import { useAuthStore } from '@/store/authStore'
import { api } from '@/utils/api'
import toast from 'react-hot-toast'
import {
  User,
  Mail,
  Calendar,
  BookOpen,
  Bookmark,
  MessageSquare,
  FileText,
  Edit3,
  Save,
  X,
  Loader2,
  Shield,
  TrendingUp,
} from 'lucide-react'

interface ProfileStats {
  articles_bookmarked: number
  papers_bookmarked: number
  repos_bookmarked: number
  chat_sessions: number
  documents_generated: number
  agent_tasks: number
}

interface ProfileData {
  id: string
  username: string
  first_name: string
  last_name: string
  email: string
  bio: string
  role: string
  avatar_url: string
  created_at: string          // ISO datetime from UserProfileSerializer
  last_login: string | null
  preferences: Record<string, unknown>
  stats: ProfileStats
}

function StatCard({ icon, label, value, colour }: { icon: React.ReactNode; label: string; value: number; colour: string }) {
  return (
    <div className="bg-slate-100 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 rounded-xl p-4 flex items-center gap-3">
      <div className={`p-2 rounded-lg ${colour}`}>{icon}</div>
      <div>
        <p className="text-2xl font-bold text-slate-900 dark:text-white">{value.toLocaleString()}</p>
        <p className="text-xs text-slate-500 dark:text-slate-400">{label}</p>
      </div>
    </div>
  )
}

export default function ProfilePage() {
  const { user, fetchUser } = useAuthStore()
  const [profile, setProfile] = useState<ProfileData | null>(null)
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({ first_name: '', last_name: '', bio: '' })

  useEffect(() => {
    const load = async () => {
      try {
        // GET /api/v1/auth/me/ — returns user data directly (no wrapper)
        const { data } = await api.get('/auth/me/')
        // Fetch activity counts (non-critical — ignore if endpoint missing)
        const stats: ProfileStats = { articles_bookmarked: 0, papers_bookmarked: 0, repos_bookmarked: 0, chat_sessions: 0, documents_generated: 0, agent_tasks: 0 }
        try {
          const [convRes, agentRes] = await Promise.allSettled([
            api.get('/conversations/?limit=1'),
            api.get('/agents/tasks/?limit=1'),
          ])
          if (convRes.status === 'fulfilled') {
            const d = convRes.value.data
            stats.chat_sessions = d?.meta?.total ?? d?.count ?? 0
          }
          if (agentRes.status === 'fulfilled') {
            const d = agentRes.value.data
            stats.agent_tasks = d?.meta?.total ?? d?.count ?? 0
          }
        } catch { /* non-critical */ }
        const p: ProfileData = { ...data, stats }
        setProfile(p)
        setForm({ first_name: p.first_name || '', last_name: p.last_name || '', bio: p.bio || '' })
      } catch {
        toast.error('Failed to load profile.')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const handleSave = async () => {
    setSaving(true)
    try {
      // PATCH /api/v1/auth/me/ — returns {success, data: {...}}
      const { data } = await api.patch('/auth/me/', form)
      const updated: ProfileData = data?.data ?? data
      setProfile(prev => ({ ...(prev ?? {} as ProfileData), ...updated }))
      await fetchUser()
      toast.success('Profile updated!')
      setEditing(false)
    } catch {
      toast.error('Failed to save profile.')
    } finally {
      setSaving(false)
    }
  }

  const initials = profile
    ? (profile.first_name?.[0] ?? '') + (profile.last_name?.[0] ?? '') || profile.username?.[0]?.toUpperCase() || '?'
    : '?'

  const roleBadge: Record<string, string> = {
    user: 'bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300',
    admin: 'bg-indigo-100 dark:bg-indigo-600/30 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-500/40',
    moderator: 'bg-amber-100 dark:bg-amber-600/30 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-500/40',
  }

  return (
    <div className="flex-1 overflow-y-auto bg-slate-50 dark:bg-slate-950">
      <div className="max-w-4xl mx-auto px-4 py-8 pb-24 lg:pb-8">

        {/* Page header */}
        <div className="flex items-center gap-3 mb-6 sm:mb-8">
          <div className="p-2.5 sm:p-3 rounded-2xl bg-indigo-100 dark:bg-indigo-600/20 border border-indigo-200 dark:border-indigo-500/30 shrink-0">
            <User size={20} className="text-indigo-600 dark:text-indigo-400 sm:size-6" />
          </div>
          <div className="min-w-0">
            <h1 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-white truncate">My Profile</h1>
            <p className="text-slate-500 dark:text-slate-400 text-xs sm:text-sm">Manage your account details and preferences</p>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20 text-slate-500">
            <Loader2 size={28} className="animate-spin mr-3" /> Loading profile…
          </div>
        ) : !profile ? (
          <div className="text-center py-20 text-slate-400">
            <User size={48} className="mx-auto mb-3 opacity-30" />
            <p>Could not load profile. Please refresh.</p>
          </div>
        ) : (
          <div className="space-y-6">

            {/* Avatar + info card */}
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-2xl p-4 sm:p-6">
              <div className="flex items-start gap-3 sm:gap-5 flex-wrap">
                {/* Avatar */}
                <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-2xl bg-gradient-to-br from-indigo-500 to-cyan-500 flex items-center justify-center flex-shrink-0 shadow-lg shadow-indigo-500/20">
                  <span className="text-slate-900 dark:text-white font-black text-xl sm:text-2xl">{initials}</span>
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  {editing ? (
                    <div className="space-y-3">
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div>
                          <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">First Name</label>
                          <input
                            value={form.first_name}
                            onChange={e => setForm(f => ({ ...f, first_name: e.target.value }))}
                            className="w-full bg-slate-100 dark:bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">Last Name</label>
                          <input
                            value={form.last_name}
                            onChange={e => setForm(f => ({ ...f, last_name: e.target.value }))}
                            className="w-full bg-slate-100 dark:bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                          />
                        </div>
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">Bio</label>
                        <textarea
                          value={form.bio}
                          onChange={e => setForm(f => ({ ...f, bio: e.target.value }))}
                          rows={3}
                          placeholder="Tell us about yourself…"
                          className="w-full bg-slate-100 dark:bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-800 dark:text-white resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        />
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={handleSave}
                          disabled={saving}
                          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm rounded-lg transition-colors font-medium"
                        >
                          {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                          Save Changes
                        </button>
                        <button
                          onClick={() => setEditing(false)}
                          className="flex items-center gap-2 px-4 py-2 bg-slate-200 hover:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-300 text-sm rounded-lg transition-colors"
                        >
                          <X size={14} /> Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <h2 className="text-lg sm:text-xl font-bold text-slate-900 dark:text-white truncate">
                          {profile.first_name} {profile.last_name}
                        </h2>
                        <span className={`text-xs px-2.5 py-0.5 rounded-full font-semibold capitalize shrink-0 ${roleBadge[profile.role] ?? roleBadge.user}`}>
                          {profile.role}
                        </span>
                      </div>
                      <p className="text-slate-500 dark:text-slate-400 text-xs sm:text-sm mb-1 truncate">@{profile.username}</p>
                      {profile.bio && <p className="text-slate-700 dark:text-slate-300 text-sm mb-3 leading-relaxed">{profile.bio}</p>}
                      <div className="flex flex-wrap gap-2 sm:gap-4 text-xs text-slate-500 mb-4">
                        <span className="flex items-center gap-1.5 min-w-0">
                          <Mail size={12} className="text-slate-500 dark:text-slate-600 shrink-0" />
                          <span className="truncate max-w-[180px] sm:max-w-none">{profile.email}</span>
                        </span>
                        <span className="flex items-center gap-1.5 whitespace-nowrap">
                          <Calendar size={12} className="text-slate-500 dark:text-slate-600 shrink-0" />
                          Joined {new Date(profile.created_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long' })}
                        </span>
                      </div>
                      <button
                        onClick={() => setEditing(true)}
                        className="flex items-center gap-2 px-3 sm:px-4 py-2 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300 text-xs sm:text-sm rounded-xl transition-colors"
                      >
                        <Edit3 size={13} /> Edit Profile
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* Stats grid */}
            {profile.stats && (
              <div>
                <h3 className="text-sm font-semibold text-slate-600 dark:text-slate-400 mb-3 flex items-center gap-2">
                  <TrendingUp size={14} className="text-indigo-600 dark:text-indigo-400" />
                  Activity Stats
                </h3>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  <StatCard icon={<Bookmark size={16} className="text-amber-600 dark:text-amber-400" />} label="Bookmarks" value={(profile.stats.articles_bookmarked || 0) + (profile.stats.papers_bookmarked || 0) + (profile.stats.repos_bookmarked || 0)} colour="bg-amber-100 dark:bg-amber-500/10" />
                  <StatCard icon={<MessageSquare size={16} className="text-sky-600 dark:text-sky-400" />} label="Chat Sessions" value={profile.stats.chat_sessions || 0} colour="bg-sky-100 dark:bg-sky-500/10" />
                  <StatCard icon={<FileText size={16} className="text-violet-600 dark:text-violet-400" />} label="Documents" value={profile.stats.documents_generated || 0} colour="bg-violet-100 dark:bg-violet-500/10" />
                  <StatCard icon={<BookOpen size={16} className="text-emerald-600 dark:text-emerald-400" />} label="Papers Bookmarked" value={profile.stats.papers_bookmarked || 0} colour="bg-emerald-100 dark:bg-emerald-500/10" />
                  <StatCard icon={<Shield size={16} className="text-indigo-600 dark:text-indigo-400" />} label="Agent Tasks" value={profile.stats.agent_tasks || 0} colour="bg-indigo-500/10" />
                </div>
              </div>
            )}

            {/* Account info */}
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-2xl p-6">
              <h3 className="text-sm font-semibold text-slate-800 dark:text-white mb-4">Account Information</h3>
              <div className="space-y-3">
                {[
                  { label: 'Username', value: profile.username },
                  { label: 'Email', value: profile.email },
                  { label: 'Role', value: profile.role?.charAt(0).toUpperCase() + profile.role?.slice(1) },
                  { label: 'Member since', value: new Date(profile.created_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }) },
                  { label: 'Last login', value: profile.last_login ? new Date(profile.last_login).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }) : 'N/A' },
                ].map(({ label, value }) => (
                  <div key={label} className="flex items-center justify-between py-2 border-b border-slate-100 dark:border-slate-800 last:border-0">
                    <span className="text-sm text-slate-400">{label}</span>
                    <span className="text-sm text-slate-800 dark:text-white font-medium">{value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
