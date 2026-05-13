'use client';

/**
 * TASK-306-F1: Prompt Library page
 * Route: /prompts
 *
 * Features:
 *  - Category filter tabs: All / Research / Coding / Writing / Analysis / Business / Creative
 *  - Sort: Popular / Newest / My Prompts
 *  - Prompt card: title, description, author, use count, upvote button
 *  - "Use Prompt" → opens agent runner or chat with prompt pre-filled
 *  - "Add Prompt" modal to create new prompts
 */

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  BookOpen, ThumbsUp, Zap, Plus, Search, X, ChevronDown,
  Loader2, MessageSquare, Bot, User, Clock, TrendingUp, Check,
} from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api } from '@/utils/api';
import toast from 'react-hot-toast';

// ── Types ─────────────────────────────────────────────────────────────────────
interface Prompt {
  id: string;
  title: string;
  description: string;
  category: string;
  author_name: string;
  use_count: number;
  upvotes: number;
  has_upvoted: boolean;
  created_at: string;
  content?: string;
}

// ── Constants ─────────────────────────────────────────────────────────────────
const CATEGORIES = [
  { value: 'all',      label: 'All',      emoji: '✨' },
  { value: 'research', label: 'Research', emoji: '🔬' },
  { value: 'coding',   label: 'Coding',   emoji: '💻' },
  { value: 'writing',  label: 'Writing',  emoji: '✍️' },
  { value: 'analysis', label: 'Analysis', emoji: '📊' },
  { value: 'business', label: 'Business', emoji: '💼' },
  { value: 'creative', label: 'Creative', emoji: '🎨' },
];

const SORT_OPTIONS = [
  { value: 'popular', label: 'Popular',    icon: TrendingUp },
  { value: 'newest',  label: 'Newest',     icon: Clock },
  { value: 'my',      label: 'My Prompts', icon: User },
];

const CATEGORY_COLOURS: Record<string, string> = {
  research: 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300',
  coding:   'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
  writing:  'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
  analysis: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  business: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300',
  creative: 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300',
};

// ── PromptCard component ──────────────────────────────────────────────────────
function PromptCard({ prompt, onUse, onUpvote }: {
  prompt: Prompt;
  onUse: (p: Prompt) => void;
  onUpvote: (id: string) => void;
}) {
  const catEmoji = CATEGORIES.find(c => c.value === prompt.category)?.emoji ?? '✨';
  const catColour = CATEGORY_COLOURS[prompt.category] ?? 'bg-slate-100 text-slate-600';

  return (
    <div className="bg-white dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 rounded-2xl p-5 flex flex-col gap-3 hover:shadow-md transition-shadow">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${catColour}`}>
              {catEmoji} {prompt.category}
            </span>
          </div>
          <h3 className="font-semibold text-slate-800 dark:text-slate-100 text-sm leading-snug line-clamp-2">
            {prompt.title}
          </h3>
        </div>
      </div>

      {/* Description */}
      {prompt.description && (
        <p className="text-xs text-slate-500 dark:text-slate-400 line-clamp-2 leading-relaxed">
          {prompt.description}
        </p>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between mt-auto pt-2 border-t border-slate-100 dark:border-slate-700/40">
        <div className="flex items-center gap-3 text-xs text-slate-400 dark:text-slate-500">
          <span className="flex items-center gap-1">
            <User size={11} />
            {prompt.author_name}
          </span>
          <span className="flex items-center gap-1">
            <Zap size={11} />
            {prompt.use_count.toLocaleString()} uses
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* Upvote */}
          <button
            onClick={() => onUpvote(prompt.id)}
            className={`flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium transition-colors ${
              prompt.has_upvoted
                ? 'bg-indigo-100 text-indigo-600 dark:bg-indigo-900/40 dark:text-indigo-400'
                : 'text-slate-400 hover:text-indigo-500 hover:bg-indigo-50 dark:hover:bg-indigo-900/20'
            }`}
          >
            <ThumbsUp size={12} className={prompt.has_upvoted ? 'fill-indigo-500' : ''} />
            {prompt.upvotes}
          </button>

          {/* Use */}
          <button
            onClick={() => onUse(prompt)}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-indigo-500 hover:bg-indigo-600 text-white text-xs font-medium transition-colors"
          >
            <Zap size={11} />
            Use
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Add Prompt modal ──────────────────────────────────────────────────────────
function AddPromptModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [form, setForm] = useState({ title: '', description: '', content: '', category: 'research', is_public: true });
  const mutation = useMutation({
    mutationFn: (data: typeof form) => api.post('/agents/prompts/', data),
    onSuccess: () => { toast.success('Prompt created!'); onCreated(); onClose(); },
    onError:   () => toast.error('Failed to create prompt'),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
      <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl w-full max-w-lg border border-slate-200 dark:border-slate-700">
        <div className="flex items-center justify-between p-6 border-b border-slate-200 dark:border-slate-700">
          <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100">Add New Prompt</h2>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
            <X size={18} className="text-slate-500" />
          </button>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-600 dark:text-slate-300 mb-1.5">Title *</label>
            <input
              className="w-full px-3 py-2 text-sm border border-slate-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-400"
              placeholder="e.g. Summarise research paper"
              value={form.title}
              onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-600 dark:text-slate-300 mb-1.5">Description</label>
            <input
              className="w-full px-3 py-2 text-sm border border-slate-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-400"
              placeholder="Short description of what this prompt does"
              value={form.description}
              onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-600 dark:text-slate-300 mb-1.5">Category *</label>
            <select
              className="w-full px-3 py-2 text-sm border border-slate-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-400"
              value={form.category}
              onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
            >
              {CATEGORIES.filter(c => c.value !== 'all').map(c => (
                <option key={c.value} value={c.value}>{c.emoji} {c.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-600 dark:text-slate-300 mb-1.5">Prompt Content *</label>
            <textarea
              className="w-full px-3 py-2 text-sm border border-slate-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-400 resize-none"
              rows={5}
              placeholder="Enter the prompt text here…"
              value={form.content}
              onChange={e => setForm(f => ({ ...f, content: e.target.value }))}
            />
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="is_public"
              checked={form.is_public}
              onChange={e => setForm(f => ({ ...f, is_public: e.target.checked }))}
              className="rounded border-slate-300"
            />
            <label htmlFor="is_public" className="text-xs text-slate-600 dark:text-slate-300">Make public (visible to all users)</label>
          </div>
        </div>
        <div className="flex justify-end gap-3 px-6 pb-6">
          <button onClick={onClose} className="px-4 py-2 text-sm text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors">
            Cancel
          </button>
          <button
            onClick={() => mutation.mutate(form)}
            disabled={mutation.isPending || !form.title || !form.content}
            className="px-4 py-2 text-sm font-medium text-white bg-indigo-500 hover:bg-indigo-600 disabled:opacity-50 rounded-lg transition-colors flex items-center gap-2"
          >
            {mutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
            Create Prompt
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function PromptsPage() {
  const router        = useRouter();
  const queryClient   = useQueryClient();
  const [category, setCategory] = useState('all');
  const [sort, setSort]         = useState('popular');
  const [search, setSearch]     = useState('');
  const [showAdd, setShowAdd]   = useState(false);

  const endpoint = sort === 'my' ? '/agents/prompts/my/' : '/agents/prompts/';
  const params   = sort === 'my' ? {} : { category: category === 'all' ? '' : category, sort };

  const { data, isLoading } = useQuery({
    queryKey: ['prompts', category, sort],
    queryFn:  () => api.get(endpoint, { params }).then(r => r.data),
    staleTime: 30_000,
  });

  const prompts: Prompt[] = (() => {
    const raw = data?.data ?? data?.results ?? [];
    if (!search.trim()) return raw;
    const q = search.toLowerCase();
    return raw.filter((p: Prompt) =>
      p.title.toLowerCase().includes(q) || p.description?.toLowerCase().includes(q)
    );
  })();

  // Upvote mutation
  const upvoteMutation = useMutation({
    mutationFn: (id: string) => api.post(`/agents/prompts/${id}/upvote/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['prompts'] }),
    onError:   () => toast.error('Failed to upvote'),
  });

  // Use prompt — navigate to chat with content pre-filled
  const handleUse = async (prompt: Prompt) => {
    try {
      const resp = await api.post(`/agents/prompts/${prompt.id}/use/`);
      const content = resp.data?.data?.content ?? prompt.content ?? '';
      router.push(`/chat?prompt=${encodeURIComponent(content)}`);
    } catch {
      toast.error('Failed to load prompt');
    }
  };

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="pb-10">

        {/* ── Header ── */}
        <div className="px-6 pt-8 pb-6 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-black text-slate-900 dark:text-white tracking-tight flex items-center gap-2">
                <BookOpen size={28} className="text-indigo-500" />
                Prompt Library
              </h1>
              <p className="text-slate-500 dark:text-slate-400 mt-1 text-sm">
                Community-curated prompts for research, coding, writing and more.
              </p>
            </div>
            <button
              onClick={() => setShowAdd(true)}
              className="flex items-center gap-2 px-4 py-2.5 bg-indigo-500 hover:bg-indigo-600 text-white text-sm font-medium rounded-xl transition-colors shadow-sm"
            >
              <Plus size={16} />
              Add Prompt
            </button>
          </div>

          {/* Search */}
          <div className="relative mt-4 max-w-md">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              className="w-full pl-9 pr-4 py-2 text-sm border border-slate-200 dark:border-slate-700 rounded-xl bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-400 placeholder-slate-400"
              placeholder="Search prompts…"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
            {search && (
              <button onClick={() => setSearch('')} className="absolute right-3 top-1/2 -translate-y-1/2">
                <X size={14} className="text-slate-400 hover:text-slate-600" />
              </button>
            )}
          </div>
        </div>

        <div className="px-6 mt-6">
          {/* ── Category tabs + Sort ── */}
          <div className="flex items-center justify-between gap-4 flex-wrap mb-6">
            <div className="flex items-center gap-1.5 flex-wrap">
              {CATEGORIES.map(cat => (
                <button
                  key={cat.value}
                  onClick={() => { setCategory(cat.value); setSort(s => s === 'my' ? 'popular' : s); }}
                  className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-colors ${
                    category === cat.value && sort !== 'my'
                      ? 'bg-indigo-500 text-white shadow-sm'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
                  }`}
                >
                  {cat.emoji} {cat.label}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-1.5">
              {SORT_OPTIONS.map(opt => (
                <button
                  key={opt.value}
                  onClick={() => setSort(opt.value)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium transition-colors ${
                    sort === opt.value
                      ? 'bg-slate-800 dark:bg-slate-200 text-white dark:text-slate-900'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
                  }`}
                >
                  <opt.icon size={12} />
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* ── Grid ── */}
          {isLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="bg-slate-100 dark:bg-slate-800 rounded-2xl animate-pulse h-44" />
              ))}
            </div>
          ) : prompts.length === 0 ? (
            <div className="text-center py-20 text-slate-400 dark:text-slate-500">
              <BookOpen size={48} className="mx-auto mb-4 opacity-30" />
              <p className="font-medium">No prompts found</p>
              <p className="text-sm mt-1">
                {sort === 'my' ? 'You haven\'t created any prompts yet.' : 'Try a different category or search term.'}
              </p>
              {sort === 'my' && (
                <button
                  onClick={() => setShowAdd(true)}
                  className="mt-4 px-4 py-2 bg-indigo-500 hover:bg-indigo-600 text-white text-sm font-medium rounded-xl transition-colors inline-flex items-center gap-2"
                >
                  <Plus size={14} /> Add your first prompt
                </button>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {prompts.map((p: Prompt) => (
                <PromptCard
                  key={p.id}
                  prompt={p}
                  onUse={handleUse}
                  onUpvote={id => upvoteMutation.mutate(id)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Add Prompt modal */}
      {showAdd && (
        <AddPromptModal
          onClose={() => setShowAdd(false)}
          onCreated={() => queryClient.invalidateQueries({ queryKey: ['prompts'] })}
        />
      )}
    </div>
  );
}
