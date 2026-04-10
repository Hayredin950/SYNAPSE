'use client';

/**
 * TASK-604-F1: Automation Marketplace page
 * Route: /marketplace
 *
 * Features:
 *  - Featured / Popular / Newest / Free tabs
 *  - Filter sidebar: trigger type, free/paid
 *  - Template card: title, description, author, downloads, upvotes, price, Install button
 *  - "Publish My Workflow" flow
 *  - Template detail modal
 */

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Store, Download, ThumbsUp, Zap, Search, X, Plus,
  Loader2, Star, Check, ArrowUpRight, Tag, User,
  Calendar, RefreshCw, Settings,
} from 'lucide-react';
import Link from 'next/link';
import toast from 'react-hot-toast';
import { api } from '@/utils/api';

// ── Types ──────────────────────────────────────────────────────────────────────

interface MarketplaceTemplate {
  id: string;
  title: string;
  description: string;
  author: string;
  download_count: number;
  upvotes: number;
  price_cents: number;
  trigger_type: string;
  created_at: string;
  actions?: any[];
}

// ── Constants ──────────────────────────────────────────────────────────────────

const TRIGGER_LABELS: Record<string, { label: string; color: string }> = {
  schedule: { label: 'Scheduled',  color: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300' },
  event:    { label: 'Event-based',color: 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300' },
  manual:   { label: 'Manual',     color: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400' },
};

const SORT_TABS = [
  { value: '',        label: '⭐ Featured' },
  { value: 'popular', label: '🔥 Popular'  },
  { value: 'newest',  label: '🆕 Newest'   },
  { value: 'free',    label: '🆓 Free'     },
];


// ── TemplateCard ──────────────────────────────────────────────────────────────

function TemplateCard({
  template, onInstall, onUpvote, onViewDetail, installing,
}: {
  template: MarketplaceTemplate;
  onInstall: (id: string) => void;
  onUpvote: (id: string) => void;
  onViewDetail: (t: MarketplaceTemplate) => void;
  installing: string | null;
}) {
  const triggerCfg = TRIGGER_LABELS[template.trigger_type] ?? TRIGGER_LABELS.manual;
  const isFree     = template.price_cents === 0;

  return (
    <div className="bg-white dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 rounded-2xl p-5 flex flex-col gap-3 hover:shadow-md hover:border-indigo-200 dark:hover:border-indigo-700/40 transition-all">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${triggerCfg.color}`}>
              {triggerCfg.label}
            </span>
            {isFree ? (
              <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">
                Free
              </span>
            ) : (
              <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                ${(template.price_cents / 100).toFixed(2)}
              </span>
            )}
          </div>
          <h3
            className="font-bold text-slate-800 dark:text-slate-100 text-sm leading-snug cursor-pointer hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors"
            onClick={() => onViewDetail(template)}
          >
            {template.title}
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 line-clamp-2 leading-relaxed">
            {template.description || 'No description provided.'}
          </p>
        </div>
      </div>

      {/* Meta */}
      <div className="flex items-center gap-3 text-xs text-slate-400 dark:text-slate-500">
        <span className="flex items-center gap-1"><User size={11} />{template.author}</span>
        <span className="flex items-center gap-1"><Download size={11} />{template.download_count.toLocaleString()}</span>
        <span className="flex items-center gap-1"><Calendar size={11} />{new Date(template.created_at).toLocaleDateString()}</span>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 mt-auto pt-2 border-t border-slate-100 dark:border-slate-700/40">
        {/* Upvote */}
        <button
          onClick={() => onUpvote(template.id)}
          className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium text-slate-500 dark:text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 dark:hover:bg-indigo-900/20 transition-colors"
        >
          <ThumbsUp size={12} />
          {template.upvotes}
        </button>

        <div className="flex-1" />

        {/* View details */}
        <button
          onClick={() => onViewDetail(template)}
          className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
        >
          <ArrowUpRight size={12} />
          Details
        </button>

        {/* Install */}
        <button
          onClick={() => onInstall(template.id)}
          disabled={installing === template.id}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-500 hover:bg-indigo-600 disabled:opacity-60 text-white text-xs font-medium transition-colors"
        >
          {installing === template.id
            ? <Loader2 size={12} className="animate-spin" />
            : <Download size={12} />
          }
          Install
        </button>
      </div>
    </div>
  );
}

// ── Detail Modal ──────────────────────────────────────────────────────────────

function DetailModal({
  template, onClose, onInstall, installing,
}: {
  template: MarketplaceTemplate;
  onClose: () => void;
  onInstall: (id: string) => void;
  installing: string | null;
}) {
  const { data } = useQuery({
    queryKey: ['marketplace-detail', template.id],
    queryFn:  () => api.get(`/automation/marketplace/${template.id}/`).then(r => r.data?.data),
    staleTime: 60_000,
    initialData: template,
  });
  const detail = data ?? template;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl w-full max-w-lg border border-slate-200 dark:border-slate-700 flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="flex items-start justify-between p-6 border-b border-slate-200 dark:border-slate-700">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${(TRIGGER_LABELS[detail.trigger_type] ?? TRIGGER_LABELS.manual).color}`}>
                {(TRIGGER_LABELS[detail.trigger_type] ?? TRIGGER_LABELS.manual).label}
              </span>
              {detail.price_cents === 0 && (
                <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">Free</span>
              )}
            </div>
            <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100">{detail.title}</h2>
            <p className="text-xs text-slate-400 mt-0.5">by {detail.author}</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
            <X size={18} className="text-slate-500" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
            {detail.description || 'No description provided.'}
          </p>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: 'Downloads', value: detail.download_count.toLocaleString(), icon: Download },
              { label: 'Upvotes',   value: detail.upvotes,                         icon: ThumbsUp },
              { label: 'Price',     value: detail.price_cents === 0 ? 'Free' : `$${(detail.price_cents / 100).toFixed(2)}`, icon: Tag },
            ].map(s => (
              <div key={s.label} className="bg-slate-50 dark:bg-slate-800 rounded-xl p-3 text-center">
                <s.icon size={14} className="mx-auto mb-1 text-slate-400" />
                <div className="text-sm font-bold text-slate-700 dark:text-slate-200">{s.value}</div>
                <div className="text-xs text-slate-400">{s.label}</div>
              </div>
            ))}
          </div>

          {/* Actions preview */}
          {(detail as any).actions?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-2">
                Workflow Steps ({(detail as any).actions.length})
              </p>
              <div className="space-y-1.5">
                {(detail as any).actions.map((action: any, i: number) => (
                  <div key={i} className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300 bg-slate-50 dark:bg-slate-800 rounded-lg px-3 py-2">
                    <span className="w-4 h-4 rounded-full bg-indigo-100 dark:bg-indigo-900/40 text-indigo-600 dark:text-indigo-400 flex items-center justify-center text-[10px] font-bold flex-shrink-0">{i + 1}</span>
                    <span className="font-mono text-[11px]">{action.type}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 p-6 border-t border-slate-200 dark:border-slate-700">
          <button onClick={onClose} className="px-4 py-2 text-sm text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors">
            Close
          </button>
          <button
            onClick={() => { onInstall(detail.id); onClose(); }}
            disabled={installing === detail.id}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-500 hover:bg-indigo-600 disabled:opacity-60 text-white text-sm font-medium rounded-lg transition-colors"
          >
            {installing === detail.id ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
            Install Workflow
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Publish Modal ─────────────────────────────────────────────────────────────

function PublishModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ workflow_id: '', title: '', description: '' });

  // Fetch user's workflows
  const { data: workflows } = useQuery({
    queryKey: ['my-workflows'],
    queryFn:  () => api.get('/automation/workflows/').then(r => r.data?.results ?? r.data?.data ?? []),
  });

  const publishMutation = useMutation({
    mutationFn: (data: typeof form) =>
      api.post(`/automation/marketplace/${data.workflow_id}/publish/`, {
        title: data.title, description: data.description,
      }),
    onSuccess: () => {
      toast.success('Workflow published to marketplace!');
      queryClient.invalidateQueries({ queryKey: ['marketplace'] });
      onClose();
    },
    onError: () => toast.error('Failed to publish workflow'),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl w-full max-w-md border border-slate-200 dark:border-slate-700">
        <div className="flex items-center justify-between p-6 border-b border-slate-200 dark:border-slate-700">
          <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100">Publish to Marketplace</h2>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
            <X size={18} className="text-slate-500" />
          </button>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-600 dark:text-slate-300 mb-1.5">Select Workflow *</label>
            <select
              className="w-full px-3 py-2 text-sm border border-slate-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-400"
              value={form.workflow_id}
              onChange={e => setForm(f => ({ ...f, workflow_id: e.target.value }))}
            >
              <option value="">— Choose a workflow —</option>
              {(workflows as any[])?.map((w: any) => (
                <option key={w.id} value={w.id}>{w.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-600 dark:text-slate-300 mb-1.5">Marketplace Title *</label>
            <input
              className="w-full px-3 py-2 text-sm border border-slate-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-400"
              placeholder="e.g. Daily AI News Digest"
              value={form.title}
              onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-600 dark:text-slate-300 mb-1.5">Description</label>
            <textarea
              className="w-full px-3 py-2 text-sm border border-slate-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-400 resize-none"
              rows={3}
              placeholder="What does this workflow do? Who is it for?"
              value={form.description}
              onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
            />
          </div>
        </div>
        <div className="flex justify-end gap-3 px-6 pb-6">
          <button onClick={onClose} className="px-4 py-2 text-sm text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors">Cancel</button>
          <button
            onClick={() => publishMutation.mutate(form)}
            disabled={publishMutation.isPending || !form.workflow_id || !form.title}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-500 hover:bg-indigo-600 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
          >
            {publishMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <ArrowUpRight size={14} />}
            Publish
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function MarketplacePage() {
  const queryClient   = useQueryClient();
  const [sort, setSort]           = useState('');
  const [search, setSearch]       = useState('');
  const [freeOnly, setFreeOnly]   = useState(false);
  const [triggerFilter, setTriggerFilter] = useState('');
  const [detailTemplate, setDetailTemplate] = useState<MarketplaceTemplate | null>(null);
  const [showPublish, setShowPublish] = useState(false);
  const [installing, setInstalling] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['marketplace', sort, freeOnly, triggerFilter],
    queryFn:  () => api.get('/automation/marketplace/', {
      params: {
        ...(sort ? { sort } : {}),
        ...(freeOnly ? { free: 'true' } : {}),
        ...(triggerFilter ? { trigger_type: triggerFilter } : {}),
      },
    }).then(r => r.data?.data as MarketplaceTemplate[]),
    staleTime: 2 * 60_000,
  });

  const templates = data ?? [];
  const filtered  = search
    ? templates.filter(t =>
        t.title.toLowerCase().includes(search.toLowerCase()) ||
        t.description?.toLowerCase().includes(search.toLowerCase())
      )
    : templates;

  // Install mutation
  const installMutation = useMutation({
    mutationFn: (id: string) => api.post(`/automation/marketplace/${id}/install/`),
    onMutate:   (id) => setInstalling(id),
    onSuccess:  (data, id) => {
      setInstalling(null);
      const cloneName = data.data?.data?.name ?? 'workflow';
      toast.success(`"${cloneName}" added to your automation workspace!`);
      queryClient.invalidateQueries({ queryKey: ['marketplace'] });
    },
    onError: () => { setInstalling(null); toast.error('Install failed'); },
  });

  // Upvote mutation
  const upvoteMutation = useMutation({
    mutationFn: (id: string) => api.post(`/automation/marketplace/${id}/upvote/`),
    onSuccess:  () => queryClient.invalidateQueries({ queryKey: ['marketplace'] }),
    onError:    () => toast.error('Failed to upvote'),
  });

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="pb-12">

        {/* ── Header ── */}
        <div className="px-6 pt-8 pb-6 border-b border-slate-200 dark:border-slate-800 bg-gradient-to-br from-indigo-50/60 via-white to-white dark:from-indigo-950/20 dark:via-slate-950 dark:to-slate-950">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h1 className="text-3xl font-black text-slate-900 dark:text-white tracking-tight flex items-center gap-2">
                <Store size={28} className="text-indigo-500" />
                Automation Marketplace
              </h1>
              <p className="text-slate-500 dark:text-slate-400 mt-1 text-sm">
                Community-built workflow templates. Install in one click, customise in minutes.
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Link
                href="/automation"
                className="flex items-center gap-1.5 px-3 py-2 text-sm text-slate-600 dark:text-slate-300 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
              >
                <Settings size={14} />
                My Workflows
              </Link>
              <button
                onClick={() => setShowPublish(true)}
                className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white bg-indigo-500 hover:bg-indigo-600 rounded-xl transition-colors shadow-sm"
              >
                <Plus size={14} />
                Publish Workflow
              </button>
            </div>
          </div>

          {/* Search + stats row */}
          <div className="flex items-center gap-4 mt-5 flex-wrap">
            <div className="relative max-w-sm flex-1">
              <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                className="w-full pl-9 pr-8 py-2 text-sm border border-slate-200 dark:border-slate-700 rounded-xl bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-400"
                placeholder="Search templates…"
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
              {search && (
                <button onClick={() => setSearch('')} className="absolute right-2.5 top-1/2 -translate-y-1/2">
                  <X size={13} className="text-slate-400 hover:text-slate-600" />
                </button>
              )}
            </div>
            {!isLoading && (
              <span className="text-sm text-slate-400">
                {filtered.length} template{filtered.length !== 1 ? 's' : ''}
              </span>
            )}
          </div>
        </div>

        <div className="flex gap-0 min-h-0">

          {/* ── Sidebar filters ── */}
          <div className="hidden md:block w-56 flex-shrink-0 border-r border-slate-200 dark:border-slate-800 p-5 space-y-6">
            {/* Sort tabs */}
            <div>
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Sort by</p>
              <div className="space-y-1">
                {SORT_TABS.map(tab => (
                  <button
                    key={tab.value}
                    onClick={() => setSort(tab.value)}
                    className={`w-full text-left px-3 py-1.5 rounded-lg text-sm transition-colors ${
                      sort === tab.value
                        ? 'bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 font-medium'
                        : 'text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800'
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Trigger filter */}
            <div>
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Trigger Type</p>
              <div className="space-y-1">
                {[{ value: '', label: 'All types' }, ...Object.entries(TRIGGER_LABELS).map(([v, c]) => ({ value: v, label: c.label }))].map(opt => (
                  <button
                    key={opt.value}
                    onClick={() => setTriggerFilter(opt.value)}
                    className={`w-full text-left px-3 py-1.5 rounded-lg text-sm transition-colors ${
                      triggerFilter === opt.value
                        ? 'bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 font-medium'
                        : 'text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Free only */}
            <div>
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Price</p>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={freeOnly}
                  onChange={e => setFreeOnly(e.target.checked)}
                  className="rounded border-slate-300 text-indigo-500 focus:ring-indigo-400"
                />
                <span className="text-sm text-slate-600 dark:text-slate-300">Free only</span>
              </label>
            </div>
          </div>

          {/* ── Template grid ── */}
          <div className="flex-1 p-6">
            {/* Mobile sort tabs */}
            <div className="flex gap-1.5 mb-5 md:hidden overflow-x-auto pb-1">
              {SORT_TABS.map(tab => (
                <button key={tab.value} onClick={() => setSort(tab.value)}
                  className={`flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    sort === tab.value
                      ? 'bg-indigo-500 text-white'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300'
                  }`}>
                  {tab.label}
                </button>
              ))}
            </div>

            {isLoading ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div key={i} className="bg-slate-100 dark:bg-slate-800 rounded-2xl h-52 animate-pulse" />
                ))}
              </div>
            ) : filtered.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <Store size={48} className="text-slate-300 dark:text-slate-700 mb-4" />
                <p className="text-slate-500 dark:text-slate-400 font-medium">
                  {search ? `No templates matching "${search}"` : 'No templates yet'}
                </p>
                <p className="text-sm text-slate-400 dark:text-slate-500 mt-1">
                  Be the first — publish your workflow to the marketplace!
                </p>
                <button
                  onClick={() => setShowPublish(true)}
                  className="mt-4 flex items-center gap-2 px-4 py-2 bg-indigo-500 hover:bg-indigo-600 text-white text-sm font-medium rounded-xl transition-colors"
                >
                  <Plus size={14} /> Publish Workflow
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {filtered.map(template => (
                  <TemplateCard
                    key={template.id}
                    template={template}
                    onInstall={id => installMutation.mutate(id)}
                    onUpvote={id => upvoteMutation.mutate(id)}
                    onViewDetail={setDetailTemplate}
                    installing={installing}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Detail modal */}
      {detailTemplate && (
        <DetailModal
          template={detailTemplate}
          onClose={() => setDetailTemplate(null)}
          onInstall={id => installMutation.mutate(id)}
          installing={installing}
        />
      )}

      {/* Publish modal */}
      {showPublish && <PublishModal onClose={() => setShowPublish(false)} />}
    </div>
  );
}
