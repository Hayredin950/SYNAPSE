'use client'

/**
 * /settings — App settings page
 * Covers: notifications, theme, API keys, account danger zone, MFA
 */

import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { useTheme } from 'next-themes'
import { useAuthStore } from '@/store/authStore'
import { api } from '@/utils/api'
import toast from 'react-hot-toast'
import { useRouter } from 'next/navigation'
import { GoogleDriveSection } from './GoogleDriveSection'
import { MFASection } from './MFASection'
import { DigestSection } from './DigestSection'
import { GitHubSection } from './GitHubSection'
import { optOut, optIn } from '@/utils/analytics'
import { AccentThemePicker } from '@/components/ui/AccentTheme'
import { SourceQualityManager } from '@/components/ui/SourceQuality'
import {
  Settings,
  Bell,
  Palette,
  Key,
  Shield,
  Trash2,
  Sun,
  Moon,
  Monitor,
  ChevronRight,
  Save,
  Loader2,
  Eye,
  EyeOff,
  LogOut,
  Cpu,
  Mail,
  Github,
  Plus,
  X,
  Copy,
  Check,
  Code,
  ExternalLink,
} from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import Link from 'next/link'

// ── Section wrapper ───────────────────────────────────────────────────────────

function Section({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-2xl overflow-hidden">
      <div className="flex items-center gap-3 px-6 py-4 border-b border-slate-200 dark:border-slate-700">
        <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400">{icon}</div>
        <h2 className="text-base font-semibold text-slate-800 dark:text-white">{title}</h2>
      </div>
      <div className="p-6 space-y-4">{children}</div>
    </div>
  )
}

function Toggle({ label, description, checked, onChange }: { label: string; description?: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div>
        <p className="text-sm font-medium text-slate-800 dark:text-white">{label}</p>
        {description && <p className="text-xs text-slate-500 mt-0.5">{description}</p>}
      </div>
      <button
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${
          checked ? 'bg-indigo-600' : 'bg-slate-300 dark:bg-slate-700'
        }`}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
            checked ? 'translate-x-6' : 'translate-x-1'
          }`}
        />
      </button>
    </div>
  )
}

// ── AI Keys form ──────────────────────────────────────────────────────────────

function AiKeysForm() {
  const [geminiKey, setGeminiKey]           = useState('');
  const [openrouterKey, setOpenrouterKey]   = useState('');
  const [scitelyKey, setScitelyKey]         = useState('');
  const [githubToken, setGithubToken]       = useState('');
  const [xApiKey, setXApiKey]               = useState('');
  const [showGemini, setShowGemini]         = useState(false);
  const [showOpenrouter, setShowOpenrouter] = useState(false);
  const [showScitely, setShowScitely]       = useState(false);
  const [showGithub, setShowGithub]         = useState(false);
  const [showXApi, setShowXApi]             = useState(false);
  const [saving, setSaving]                 = useState(false);
  const [loaded, setLoaded]                 = useState(false);

  const [geminiConfigured, setGeminiConfigured]         = useState(false);
  const [openrouterConfigured, setOpenrouterConfigured] = useState(false);
  const [scitelyConfigured, setScitelyConfigured]       = useState(false);
  const [githubConfigured, setGithubConfigured]         = useState(false);
  const [xApiConfigured, setXApiConfigured]             = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    api.get('/users/ai-keys/', { signal: controller.signal }).then(({ data }) => {
      setGeminiConfigured(!!data.gemini_configured);
      setOpenrouterConfigured(!!data.openrouter_configured);
      setScitelyConfigured(!!data.scitely_configured);
      setGithubConfigured(!!data.github_configured);
      setXApiConfigured(!!data.x_api_configured);
      setGeminiKey(data.gemini_configured ? '••••••••••••••••' : '');
      setOpenrouterKey(data.openrouter_configured ? '••••••••••••••••' : '');
      setScitelyKey(data.scitely_configured ? '••••••••••••••••' : '');
      setGithubToken(data.github_configured ? '••••••••••••••••' : '');
      setXApiKey(data.x_api_configured ? '••••••••••••••••' : '');
      setLoaded(true);
    }).catch((e) => { if (!axios.isCancel(e)) setLoaded(true); });
    return () => controller.abort();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload: Record<string, string> = {};
      if (geminiKey && !geminiKey.startsWith('•'))         payload.gemini_api_key = geminiKey;
      if (openrouterKey && !openrouterKey.startsWith('•')) payload.openrouter_api_key = openrouterKey;
      if (scitelyKey && !scitelyKey.startsWith('•'))       payload.scitely_api_key = scitelyKey;
      if (githubToken && !githubToken.startsWith('•'))     payload.github_token = githubToken;
      if (xApiKey && !xApiKey.startsWith('•'))             payload.x_api_key = xApiKey;
      if (!Object.keys(payload).length) { toast.error('No new keys to save.'); setSaving(false); return; }
      await api.post('/users/ai-keys/', payload);
      toast.success('Keys saved! AI, GitHub and X/Twitter scrapers now use your keys.');
      if (payload.gemini_api_key)     { setGeminiKey('••••••••••••••••');     setGeminiConfigured(true); }
      if (payload.openrouter_api_key) { setOpenrouterKey('••••••••••••••••'); setOpenrouterConfigured(true); }
      if (payload.scitely_api_key)    { setScitelyKey('••••••••••••••••');    setScitelyConfigured(true); }
      if (payload.github_token)       { setGithubToken('••••••••••••••••');   setGithubConfigured(true); }
      if (payload.x_api_key)          { setXApiKey('••••••••••••••••');       setXApiConfigured(true); }
    } catch {
      toast.error('Failed to save keys.');
    } finally {
      setSaving(false);
    }
  };

  const fieldClass = 'w-full bg-slate-100 dark:bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 pr-10 text-sm text-slate-800 dark:text-white font-mono placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500';

  if (!loaded) return (
    <div className="space-y-4 animate-pulse">
      <div className="h-4 w-48 bg-slate-200 dark:bg-slate-700 rounded" />
      <div className="h-10 bg-slate-100 dark:bg-slate-800 rounded-lg" />
      <div className="h-4 w-48 bg-slate-200 dark:bg-slate-700 rounded" />
      <div className="h-10 bg-slate-100 dark:bg-slate-800 rounded-lg" />
      <div className="h-9 w-32 bg-indigo-100 dark:bg-indigo-900/50 rounded-lg" />
    </div>
  );

  return (
    <div className="space-y-4">
      {/* Scitely — Primary AI Provider */}
      <div>
        <label className="block text-xs font-medium text-slate-400 mb-1 flex items-center gap-2">
          Scitely API Key
          <span className="text-cyan-600 dark:text-cyan-400 text-xs font-normal">50+ models · GPT-5 / Claude / DeepSeek / Flux</span>
          {loaded && (scitelyConfigured
            ? <span className="text-xs px-1.5 py-0.5 rounded-full bg-emerald-900/50 text-emerald-400 font-semibold">✓ Saved</span>
            : <span className="text-xs px-1.5 py-0.5 rounded-full bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-400">Recommended</span>
          )}
        </label>
        <div className="relative">
          <input
            type={showScitely ? 'text' : 'password'}
            value={scitelyKey}
            onChange={(e) => setScitelyKey(e.target.value)}
            placeholder="sk-scitely-..."
            className={fieldClass}
          />
          <button type="button" onClick={() => setShowScitely(s => !s)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
            {showScitely ? <EyeOff size={14} /> : <Eye size={14} />}
          </button>
        </div>
        <p className="text-xs text-slate-600 mt-1">
          Get from <a href="https://scitely.com" target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:text-indigo-500 dark:text-indigo-400 dark:hover:text-indigo-300">Scitely</a> — 50+ models, image/video generation, unlimited access
        </p>
      </div>

      {/* Gemini */}
      <div>
        <label className="block text-xs font-medium text-slate-400 mb-1 flex items-center gap-2">
          Google Gemini API Key
          <span className="text-indigo-600 dark:text-indigo-400 text-xs font-normal">gemini-1.5-flash / gemini-2.0</span>
          {loaded && (geminiConfigured
            ? <span className="text-xs px-1.5 py-0.5 rounded-full bg-emerald-900/50 text-emerald-400 font-semibold">✓ Saved</span>
            : <span className="text-xs px-1.5 py-0.5 rounded-full bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-400">Not set</span>
          )}
        </label>
        <div className="relative">
          <input
            type={showGemini ? 'text' : 'password'}
            value={geminiKey}
            onChange={(e) => setGeminiKey(e.target.value)}
            placeholder="AIza..."
            className={fieldClass}
          />
          <button type="button" onClick={() => setShowGemini(s => !s)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
            {showGemini ? <EyeOff size={14} /> : <Eye size={14} />}
          </button>
        </div>
        <p className="text-xs text-slate-600 mt-1">
          Get from <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:text-indigo-500 dark:text-indigo-400 dark:hover:text-indigo-300">Google AI Studio</a>
        </p>
      </div>

      {/* OpenRouter */}
      <div>
        <label className="block text-xs font-medium text-slate-400 mb-1 flex items-center gap-2">
          OpenRouter API Key
          <span className="text-violet-600 dark:text-violet-400 text-xs font-normal">Fallback / GPT-4o / Claude</span>
          {loaded && (openrouterConfigured
            ? <span className="text-xs px-1.5 py-0.5 rounded-full bg-emerald-900/50 text-emerald-400 font-semibold">✓ Saved</span>
            : <span className="text-xs px-1.5 py-0.5 rounded-full bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-400">Not set</span>
          )}
        </label>
        <div className="relative">
          <input
            type={showOpenrouter ? 'text' : 'password'}
            value={openrouterKey}
            onChange={(e) => setOpenrouterKey(e.target.value)}
            placeholder="sk-or-..."
            className={fieldClass}
          />
          <button type="button" onClick={() => setShowOpenrouter(s => !s)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
            {showOpenrouter ? <EyeOff size={14} /> : <Eye size={14} />}
          </button>
        </div>
        <p className="text-xs text-slate-600 mt-1">
          Get from <a href="https://openrouter.ai/keys" target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:text-indigo-500 dark:text-indigo-400 dark:hover:text-indigo-300">OpenRouter</a> — 200+ models available
        </p>
      </div>

      {/* Divider */}
      <div className="border-t border-slate-200 dark:border-slate-700 pt-2">
        <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-3">Scraper API Keys</p>
      </div>

      {/* GitHub Token */}
      <div>
        <label className="block text-xs font-medium text-slate-400 mb-1 flex items-center gap-2">
          GitHub Personal Access Token
          <span className="text-emerald-600 dark:text-emerald-400 text-xs font-normal">5,000 req/hr vs 60 without</span>
          {loaded && (githubConfigured
            ? <span className="text-xs px-1.5 py-0.5 rounded-full bg-emerald-900/50 text-emerald-400 font-semibold">✓ Saved</span>
            : <span className="text-xs px-1.5 py-0.5 rounded-full bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-400">Optional</span>
          )}
        </label>
        <div className="relative">
          <input
            type={showGithub ? 'text' : 'password'}
            value={githubToken}
            onChange={(e) => setGithubToken(e.target.value)}
            placeholder="ghp_..."
            className={fieldClass}
          />
          <button type="button" onClick={() => setShowGithub(s => !s)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
            {showGithub ? <EyeOff size={14} /> : <Eye size={14} />}
          </button>
        </div>
        <p className="text-xs text-slate-600 mt-1">
          Get from <a href="https://github.com/settings/tokens" target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:text-indigo-500 dark:text-indigo-400 dark:hover:text-indigo-300">GitHub → Settings → Developer settings → Personal access tokens</a>. Only needs <code className="text-xs bg-slate-200 dark:bg-slate-700 px-1 rounded">public_repo</code> scope.
        </p>
      </div>

      {/* X/Twitter Bearer Token */}
      <div>
        <label className="block text-xs font-medium text-slate-400 mb-1 flex items-center gap-2">
          X (Twitter) API Bearer Token
          <span className="text-sky-500 dark:text-sky-400 text-xs font-normal">Required for tweet scraping</span>
          {loaded && (xApiConfigured
            ? <span className="text-xs px-1.5 py-0.5 rounded-full bg-emerald-900/50 text-emerald-400 font-semibold">✓ Saved</span>
            : <span className="text-xs px-1.5 py-0.5 rounded-full bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-400">Not set</span>
          )}
        </label>
        <div className="relative">
          <input
            type={showXApi ? 'text' : 'password'}
            value={xApiKey}
            onChange={(e) => setXApiKey(e.target.value)}
            placeholder="AAAA..."
            className={fieldClass}
          />
          <button type="button" onClick={() => setShowXApi(s => !s)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
            {showXApi ? <EyeOff size={14} /> : <Eye size={14} />}
          </button>
        </div>
        <p className="text-xs text-slate-600 mt-1">
          Get from <a href="https://developer.twitter.com/en/portal/dashboard" target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:text-indigo-500 dark:text-indigo-400 dark:hover:text-indigo-300">X Developer Portal</a> — Free tier gives 1,500 tweets/month.
        </p>
      </div>

      <button
        onClick={handleSave}
        disabled={saving}
        className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm rounded-lg transition-colors font-medium"
      >
        {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
        Save Keys
      </button>
    </div>
  );
}

// ── TASK-605-F1: API Keys section ─────────────────────────────────────────────

function ApiKeysSection() {
  const queryClient = useQueryClient()
  const [showCreate, setShowCreate] = React.useState(false)
  const [newKeyName, setNewKeyName] = React.useState('')
  const [newKeyScopes, setNewKeyScopes] = React.useState<string[]>(['read:content'])
  const [revealedKey, setRevealedKey] = React.useState<{ key: string; name: string } | null>(null)
  const [copiedKey, setCopiedKey] = React.useState(false)

  const { data: keysData, isLoading } = useQuery({
    queryKey: ['api-keys'],
    queryFn:  () => api.get('/users/keys/').then(r => r.data?.data ?? []),
    staleTime: 30_000,
  })
  const keys: any[] = keysData ?? []

  const createMutation = useMutation({
    mutationFn: () => api.post('/users/keys/', { name: newKeyName, scopes: newKeyScopes }),
    onSuccess:  (resp) => {
      queryClient.invalidateQueries({ queryKey: ['api-keys'] })
      const raw = resp.data?.data?.key
      if (raw) setRevealedKey({ key: raw, name: newKeyName })
      setNewKeyName('')
      setShowCreate(false)
    },
    onError: () => toast.error('Failed to create API key'),
  })

  const revokeMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/users/keys/${id}/`),
    onSuccess:  () => { queryClient.invalidateQueries({ queryKey: ['api-keys'] }); toast.success('Key revoked') },
    onError:    () => toast.error('Failed to revoke key'),
  })

  const SCOPES = [
    { value: 'read:content', label: 'Read Content' },
    { value: 'write:ai',     label: 'AI Queries'   },
    { value: 'read:trends',  label: 'Trends'        },
    { value: 'write:saves',  label: 'Save Pages'    },
  ]

  const copyKey = (key: string) => {
    navigator.clipboard.writeText(key).then(() => {
      setCopiedKey(true)
      setTimeout(() => setCopiedKey(false), 2000)
    })
  }

  return (
    <div className="space-y-4">
      {/* Revealed key — shown once */}
      {revealedKey && (
        <div className="p-4 bg-amber-50 dark:bg-amber-950/30 border border-amber-300 dark:border-amber-700/60 rounded-xl">
          <p className="text-xs font-semibold text-amber-700 dark:text-amber-400 mb-2">
            ⚠️ Copy your API key now — it will not be shown again!
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-white dark:bg-slate-900 border border-amber-200 dark:border-amber-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-800 dark:text-slate-100 break-all">
              {revealedKey.key}
            </code>
            <button
              onClick={() => copyKey(revealedKey.key)}
              className={`flex items-center gap-1 px-3 py-2 rounded-lg text-xs font-medium transition-colors flex-shrink-0 ${
                copiedKey
                  ? 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400'
                  : 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 hover:bg-amber-200'
              }`}
            >
              {copiedKey ? <><Check size={12} /> Copied!</> : <><Copy size={12} /> Copy</>}
            </button>
          </div>
          <button onClick={() => setRevealedKey(null)} className="mt-2 text-xs text-amber-600 dark:text-amber-500 hover:underline">
            I've copied it — dismiss
          </button>
        </div>
      )}

      {/* Keys table */}
      {isLoading ? (
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <Loader2 size={14} className="animate-spin" /> Loading API keys…
        </div>
      ) : keys.length === 0 ? (
        <p className="text-sm text-slate-500 dark:text-slate-400">
          No API keys yet. Create one to access the Synapse API programmatically.
        </p>
      ) : (
        <div className="rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-700">
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 dark:text-slate-400">Name</th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 dark:text-slate-400">Key</th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 dark:text-slate-400">Last Used</th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 dark:text-slate-400"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {keys.map((k: any) => (
                <tr key={k.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                  <td className="px-4 py-3 font-medium text-slate-800 dark:text-slate-100">{k.name}</td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-500 dark:text-slate-400">
                    {k.key_prefix}…
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-400">
                    {k.last_used ? new Date(k.last_used).toLocaleDateString() : 'Never'}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => { if (confirm(`Revoke "${k.name}"?`)) revokeMutation.mutate(k.id) }}
                      className="text-xs text-red-500 hover:text-red-700 dark:hover:text-red-400 transition-colors"
                    >
                      Revoke
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create key form */}
      {showCreate ? (
        <div className="p-4 bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 rounded-xl space-y-3">
          <div>
            <label className="block text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1">Key Name *</label>
            <input
              className="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="e.g. My App, Python Script, Browser Extension"
              value={newKeyName}
              onChange={e => setNewKeyName(e.target.value)}
              autoFocus
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1">Scopes</label>
            <div className="flex flex-wrap gap-2">
              {SCOPES.map(s => (
                <label key={s.value} className="flex items-center gap-1.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={newKeyScopes.includes(s.value)}
                    onChange={e => setNewKeyScopes(prev =>
                      e.target.checked ? [...prev, s.value] : prev.filter(x => x !== s.value)
                    )}
                    className="rounded border-slate-300 text-indigo-500"
                  />
                  <span className="text-xs text-slate-600 dark:text-slate-300">{s.label}</span>
                </label>
              ))}
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => createMutation.mutate()}
              disabled={createMutation.isPending || !newKeyName}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-500 hover:bg-indigo-600 disabled:opacity-50 text-white text-xs font-medium rounded-lg transition-colors"
            >
              {createMutation.isPending ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
              Create Key
            </button>
            <button
              onClick={() => setShowCreate(false)}
              className="px-3 py-1.5 text-xs text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-1.5 px-3 py-2 bg-indigo-500 hover:bg-indigo-600 text-white text-sm font-medium rounded-lg transition-colors"
          >
            <Plus size={14} /> Create API Key
          </button>
          <Link href="/developers" className="flex items-center gap-1 text-xs text-indigo-500 hover:underline">
            <Code size={12} /> Developer Portal
            <ExternalLink size={10} />
          </Link>
        </div>
      )}
    </div>
  )
}

// ── TASK-607-5: Integrations section ─────────────────────────────────────────

interface IntegrationDef {
  id:           string;
  name:         string;
  description:  string;
  emoji:        string;
  statusUrl:    string;
  connectUrl?:  string;
  disconnectUrl?: string;
  connectType:  'oauth' | 'upload' | 'apikey';
  connectLabel?: string;
}

const INTEGRATIONS: IntegrationDef[] = [
  {
    id: 'google-drive', name: 'Google Drive', emoji: '📁',
    description: 'Export documents and research reports directly to your Drive.',
    statusUrl: '/integrations/drive/status/', connectUrl: '/integrations/drive/connect/',
    disconnectUrl: '/integrations/drive/disconnect/', connectType: 'oauth',
  },
  {
    id: 'notion', name: 'Notion', emoji: '📝',
    description: 'Import Notion pages into your knowledge base and export reports.',
    statusUrl: '/integrations/notion/status/', connectUrl: '/integrations/notion/connect/',
    disconnectUrl: '/integrations/notion/disconnect/', connectType: 'oauth',
  },
  {
    id: 'slack', name: 'Slack', emoji: '💬',
    description: 'Use /synapse in Slack to ask AI questions. Receive weekly digests.',
    statusUrl: '/integrations/slack/status/', connectUrl: '/integrations/slack/connect/',
    disconnectUrl: '/integrations/slack/disconnect/', connectType: 'oauth',
  },
  {
    id: 'obsidian', name: 'Obsidian', emoji: '🔮',
    description: 'Upload your vault to import notes into Synapse knowledge graph.',
    statusUrl: '', connectType: 'upload',
    connectLabel: 'Upload Vault',
  },
  {
    id: 'zotero', name: 'Zotero', emoji: '📚',
    description: 'Import your entire Zotero library (papers + PDFs) into RAG.',
    statusUrl: '/integrations/zotero/status/', disconnectUrl: '/integrations/zotero/disconnect/',
    connectType: 'apikey', connectLabel: 'Connect Zotero',
  },
]

function IntegrationCard({ integration }: { integration: IntegrationDef }) {
  const queryClient = useQueryClient()
  const [loading, setLoading] = React.useState(false)
  const [zoteroKey, setZoteroKey] = React.useState('')
  const [zoteroUserId, setZoteroUserId] = React.useState('')
  const [showZoteroForm, setShowZoteroForm] = React.useState(false)

  const { data: statusData } = useQuery({
    queryKey: ['integration-status', integration.id],
    queryFn:  () => integration.statusUrl
      ? api.get(integration.statusUrl).then(r => r.data?.data)
      : Promise.resolve({ connected: false }),
    staleTime: 60_000,
    enabled: Boolean(integration.statusUrl),
  })
  const connected = statusData?.connected ?? false

  const handleConnect = async () => {
    if (integration.connectType === 'apikey') {
      setShowZoteroForm(true)
      return
    }
    setLoading(true)
    try {
      if (integration.connectUrl) {
        const resp = await api.get(integration.connectUrl)
        const url  = resp.data?.data?.url
        if (url) window.location.href = url
      }
    } catch { toast.error(`Failed to connect ${integration.name}`) }
    finally { setLoading(false) }
  }

  const handleDisconnect = async () => {
    if (!confirm(`Disconnect ${integration.name}?`)) return
    setLoading(true)
    try {
      if (integration.disconnectUrl) await api.post(integration.disconnectUrl)
      queryClient.invalidateQueries({ queryKey: ['integration-status', integration.id] })
      toast.success(`${integration.name} disconnected`)
    } catch { toast.error('Disconnect failed') }
    finally { setLoading(false) }
  }

  const handleZoteroConnect = async () => {
    setLoading(true)
    try {
      await api.post('/integrations/zotero/connect/', { api_key: zoteroKey, user_id: zoteroUserId })
      queryClient.invalidateQueries({ queryKey: ['integration-status', 'zotero'] })
      setShowZoteroForm(false)
      toast.success('Zotero connected! Importing library in background…')
    } catch { toast.error('Invalid Zotero credentials') }
    finally { setLoading(false) }
  }

  return (
    <div className="flex items-start gap-4 p-4 bg-slate-50 dark:bg-slate-800/40 rounded-xl border border-slate-200 dark:border-slate-700">
      <div className="w-10 h-10 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 flex items-center justify-center text-xl flex-shrink-0">
        {integration.emoji}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">{integration.name}</span>
          {connected && (
            <span className="flex items-center gap-1 text-[11px] font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/30 px-1.5 py-0.5 rounded-full">
              <Check size={9} /> Connected
            </span>
          )}
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400">{integration.description}</p>

        {/* Zotero API key form */}
        {showZoteroForm && (
          <div className="mt-3 space-y-2">
            <input className="w-full text-xs bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="Zotero API Key" value={zoteroKey} onChange={e => setZoteroKey(e.target.value)} />
            <input className="w-full text-xs bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="Zotero User ID" value={zoteroUserId} onChange={e => setZoteroUserId(e.target.value)} />
            <div className="flex gap-2">
              <button onClick={handleZoteroConnect} disabled={loading || !zoteroKey || !zoteroUserId}
                className="flex items-center gap-1 px-3 py-1.5 bg-indigo-500 hover:bg-indigo-600 disabled:opacity-50 text-white text-xs font-medium rounded-lg transition-colors">
                {loading ? <Loader2 size={11} className="animate-spin" /> : <Check size={11} />} Connect
              </button>
              <button onClick={() => setShowZoteroForm(false)} className="px-3 py-1.5 text-xs text-slate-500 hover:text-slate-700 transition-colors">Cancel</button>
            </div>
          </div>
        )}
      </div>
      {!showZoteroForm && (
        <button
          onClick={connected ? handleDisconnect : handleConnect}
          disabled={loading}
          className={`flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            connected
              ? 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 hover:bg-red-100'
              : 'bg-indigo-500 hover:bg-indigo-600 text-white'
          }`}
        >
          {loading ? <Loader2 size={12} className="animate-spin" /> : connected ? <X size={12} /> : <Plus size={12} />}
          {connected ? 'Disconnect' : (integration.connectLabel ?? 'Connect')}
        </button>
      )}
    </div>
  )
}

function IntegrationsSection() {
  return (
    <div className="space-y-3">
      <p className="text-xs text-slate-500 dark:text-slate-400">
        Connect external services to expand your knowledge base and automate workflows.
      </p>
      {INTEGRATIONS.map(integration => (
        <IntegrationCard key={integration.id} integration={integration} />
      ))}
    </div>
  )
}

// ── Change Password form ──────────────────────────────────────────────────────

function ChangePasswordForm() {
  const [form, setForm] = useState({ current_password: '', new_password: '', confirm_password: '' })
  const [show, setShow] = useState(false)
  const [saving, setSaving] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (form.new_password !== form.confirm_password) {
      toast.error('New passwords do not match.')
      return
    }
    if (form.new_password.length < 8) {
      toast.error('Password must be at least 8 characters.')
      return
    }
    setSaving(true)
    try {
      await api.post('/users/change-password/', {
        current_password: form.current_password,
        new_password: form.new_password,
      })
      toast.success('Password updated!')
      setForm({ current_password: '', new_password: '', confirm_password: '' })
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { error?: string; detail?: string } } })?.response?.data?.error
        ?? (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Failed to update password.'
      toast.error(msg)
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      {(['current_password', 'new_password', 'confirm_password'] as const).map(field => (
        <div key={field}>
          <label className="block text-xs font-medium text-slate-400 mb-1 capitalize">
            {field.replace(/_/g, ' ')}
          </label>
          <div className="relative">
            <input
              type={show ? 'text' : 'password'}
              value={form[field]}
              onChange={e => setForm(f => ({ ...f, [field]: e.target.value }))}
              className="w-full bg-slate-100 dark:bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 pr-10 text-sm text-slate-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="••••••••"
            />
            <button
              type="button"
              onClick={() => setShow(s => !s)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
            >
              {show ? <EyeOff size={15} /> : <Eye size={15} />}
            </button>
          </div>
        </div>
      ))}
      <button
        type="submit"
        disabled={saving}
        className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm rounded-lg transition-colors font-medium"
      >
        {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
        Update Password
      </button>
    </form>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const { theme, setTheme } = useTheme()
  const { logout } = useAuthStore()
  const router = useRouter()

  // Notification prefs (stored locally — workflow/agent email prefs)
  const [notifPrefs, setNotifPrefs] = useState({
    email_on_workflow_complete: true,
    email_on_agent_complete: true,
    in_app_notifications: true,
  })

  // TASK-203: Analytics opt-out (read from localStorage, persisted client-side)
  const [analyticsEnabled, setAnalyticsEnabled] = useState(() => {
    if (typeof window === 'undefined') return true
    return localStorage.getItem('analytics_optout') !== 'true'
  })

  const handleAnalyticsToggle = (enabled: boolean) => {
    setAnalyticsEnabled(enabled)
    if (enabled) {
      optIn()
      toast.success('Analytics enabled. Thank you! 🙏')
    } else {
      optOut()
      toast.success('Analytics disabled. Your data stays private.')
    }
  }

  // API key visibility
  const [showKey, setShowKey] = useState(false)
  const [apiKey] = useState('sk-synapse-demo-key-xxxxxxxx') // placeholder

  const [deletingAccount, setDeletingAccount] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState('')

  const handleDeleteAccount = async () => {
    if (deleteConfirm !== 'DELETE') {
      toast.error('Type DELETE to confirm.')
      return
    }
    setDeletingAccount(true)
    try {
      await api.delete('/users/account/')
      logout()
      router.push('/login')
      toast.success('Account deleted.')
    } catch {
      toast.error('Failed to delete account. Contact support.')
      setDeletingAccount(false)
    }
  }

  const themeOptions = [
    { value: 'system', icon: Monitor, label: 'System' },
    { value: 'light',  icon: Sun,     label: 'Light'  },
    { value: 'dark',   icon: Moon,    label: 'Dark'   },
  ]

  return (
    <div className="flex-1 overflow-y-auto bg-slate-50 dark:bg-slate-950">
      <div className="max-w-3xl mx-auto px-4 py-8 pb-24 lg:pb-8 space-y-6">

        {/* Page header */}
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2.5 sm:p-3 rounded-2xl bg-indigo-600/20 border border-indigo-500/30 shrink-0">
            <Settings size={20} className="text-indigo-600 dark:text-indigo-400 sm:size-6" />
          </div>
          <div className="min-w-0">
            <h1 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-white truncate">Settings</h1>
            <p className="text-slate-400 text-xs sm:text-sm">Manage your preferences and account</p>
          </div>
        </div>

        {/* Integrations */}
        <Section title="Integrations" icon={<Code size={16} />}>
          <IntegrationsSection />
        </Section>

        {/* GitHub OAuth — TASK-202 */}
        <Section title="GitHub" icon={<Github size={16} />}>
          <GitHubSection />
        </Section>

        {/* Appearance */}
        <Section title="Appearance" icon={<Palette size={16} />}>
          <div className="space-y-6">
            <div>
              <p className="text-sm font-medium text-slate-800 dark:text-white mb-3">Theme</p>
              <div className="flex gap-2 sm:gap-3 flex-wrap">
                {themeOptions.map(({ value, icon: Icon, label }) => (
                  <button
                    key={value}
                    onClick={() => setTheme(value)}
                    className={`flex items-center gap-1.5 sm:gap-2 px-3 sm:px-4 py-2 rounded-xl border text-xs sm:text-sm font-semibold transition-all whitespace-nowrap ${
                      theme === value
                        ? 'border-indigo-500 bg-indigo-600/20 text-indigo-700 dark:text-indigo-300'
                        : 'border-slate-300 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:border-slate-400 dark:hover:border-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
                    }`}
                  >
                    <Icon size={14} />
                    {label}
                  </button>
                ))}
              </div>
            </div>
            <div className="pt-2 border-t border-slate-100 dark:border-slate-800">
              <AccentThemePicker />
            </div>
            <div className="pt-2 border-t border-slate-100 dark:border-slate-800">
              <SourceQualityManager />
            </div>
          </div>
        </Section>

        {/* Notifications */}
        <Section title="Notifications" icon={<Bell size={16} />}>
          <div className="space-y-5 divide-y divide-slate-200 dark:divide-slate-800">
            <Toggle
              label="Email on workflow complete"
              description="Receive an email when an automation workflow finishes"
              checked={notifPrefs.email_on_workflow_complete}
              onChange={v => setNotifPrefs(p => ({ ...p, email_on_workflow_complete: v }))}
            />
            <div className="pt-4">
              <Toggle
                label="Email on agent task complete"
                description="Receive an email when an AI agent task finishes"
                checked={notifPrefs.email_on_agent_complete}
                onChange={v => setNotifPrefs(p => ({ ...p, email_on_agent_complete: v }))}
              />
            </div>
            <div className="pt-4">
              <Toggle
                label="In-app notifications"
                description="Show real-time notifications in the sidebar bell"
                checked={notifPrefs.in_app_notifications}
                onChange={v => setNotifPrefs(p => ({ ...p, in_app_notifications: v }))}
              />
            </div>
          </div>
        </Section>

        {/* Weekly AI Digest — TASK-201 */}
        <Section title="Weekly AI Digest" icon={<Mail size={16} />}>
          <DigestSection />
        </Section>

        {/* Analytics & Privacy — TASK-203 */}
        <Section title="Analytics & Privacy" icon={<Cpu size={16} />}>
          <Toggle
            label="Product analytics"
            description="Help us improve SYNAPSE by sharing anonymous usage data. No PII is ever sent. Respects your browser's Do Not Track setting."
            checked={analyticsEnabled}
            onChange={handleAnalyticsToggle}
          />
          <p className="text-xs text-slate-500 mt-3 leading-relaxed">
            SYNAPSE uses{' '}
            <a href="https://posthog.com" target="_blank" rel="noopener noreferrer"
               className="text-indigo-500 hover:underline">PostHog</a>{' '}
            for privacy-first product analytics. No data is sold to third parties.
            Autocapture and session recording are disabled.
          </p>
        </Section>

        {/* Security */}
        <Section title="Security" icon={<Shield size={16} />}>
          <ChangePasswordForm />

          <div className="pt-4 border-t border-slate-200 dark:border-slate-800">
            <p className="text-sm font-medium text-slate-800 dark:text-white mb-3">Two-Factor Authentication (MFA)</p>
            <MFASection />
          </div>
        </Section>

        {/* AI Engine Keys */}
        <Section title="AI Engine" icon={<Cpu size={16} />}>
          <p className="text-sm text-slate-400 mb-4">
            Configure your personal AI provider keys to power all AI features — 
            <span className="text-indigo-600 dark:text-indigo-400 font-medium"> Chat</span>,{' '}
            <span className="text-indigo-600 dark:text-indigo-400 font-medium">AI Agent</span>,{' '}
            <span className="text-indigo-600 dark:text-indigo-400 font-medium">Documents</span>, and{' '}
            <span className="text-indigo-600 dark:text-indigo-400 font-medium">Automation</span>.
            Your keys are stored server-side and never exposed in the browser.
            Each feature uses your key — you're billed directly by the provider, not by SYNAPSE.
          </p>
          <AiKeysForm />
        </Section>

        {/* API Keys */}
        <Section title="API Keys" icon={<Key size={16} />}>
          <ApiKeysSection />
        </Section>

        {/* Sign out */}
        <Section title="Session" icon={<LogOut size={16} />}>
          <p className="text-sm text-slate-400">Sign out of your current session on this device.</p>
          <button
            onClick={() => { logout(); router.push('/login') }}
            className="flex items-center gap-2 px-4 py-2 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 text-sm rounded-lg transition-colors"
          >
            <LogOut size={14} /> Sign Out
          </button>
        </Section>

        {/* Danger zone */}
        <Section title="Danger Zone" icon={<Trash2 size={16} />}>
          <div className="p-4 bg-red-500/5 border border-red-500/20 rounded-xl">
            <p className="text-sm font-medium text-red-400 mb-1">Delete Account</p>
            <p className="text-xs text-slate-400 mb-4">
              This will permanently delete your account and all associated data. This action cannot be undone.
            </p>
            <div className="space-y-3">
              <input
                value={deleteConfirm}
                onChange={e => setDeleteConfirm(e.target.value)}
                placeholder='Type "DELETE" to confirm'
                className="w-full bg-slate-100 dark:bg-slate-800 border border-red-500/30 rounded-lg px-3 py-2 text-sm text-slate-800 dark:text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-red-500"
              />
              <button
                onClick={handleDeleteAccount}
                disabled={deletingAccount || deleteConfirm !== 'DELETE'}
                className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm rounded-lg transition-colors font-medium"
              >
                {deletingAccount ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                Delete My Account
              </button>
            </div>
          </div>
        </Section>
      </div>
    </div>
  )
}
