'use client';

/**
 * TASK-402: CommandPalette — ⌘K / Ctrl+K global search
 *
 * Features:
 *  - ⌘K (Mac) / Ctrl+K (Win/Linux) to open, Esc to close
 *  - Debounced (200ms) search via GET /api/search/?q=…&limit=5
 *  - Results grouped: Recent pages → Content matches → Quick Actions → Navigation
 *  - ↑↓ arrows + Enter to navigate, type-icon per content type
 *  - Renders via portal into #modal-root
 */

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { useRouter } from 'next/navigation';
import {
  Search, Loader2, FileText, BookOpen, GitBranch, Youtube,
  MessageSquare, Bot, Zap, Settings, CreditCard, Home,
  Newspaper, TrendingUp, Twitter, X, ArrowRight, Clock,
} from 'lucide-react';
import { api } from '@/utils/api';

// ── Types ──────────────────────────────────────────────────────────────────────

interface CommandItem {
  id:       string;
  label:    string;
  subtitle?: string;
  icon:     React.ElementType;
  iconColor?: string;
  group:    string;
  href:     string;
}

// ── Static items ──────────────────────────────────────────────────────────────

const QUICK_ACTIONS: CommandItem[] = [
  { id: 'new-chat',   label: 'New Chat',        subtitle: 'Start a new AI conversation',   icon: MessageSquare, iconColor: 'text-sky-500',    group: 'Actions', href: '/chat' },
  { id: 'new-agent',  label: 'New Agent Task',  subtitle: 'Run an autonomous AI agent',    icon: Bot,           iconColor: 'text-pink-500',   group: 'Actions', href: '/agents' },
  { id: 'new-doc',    label: 'New Document',    subtitle: 'Generate a PDF or report',      icon: FileText,      iconColor: 'text-orange-500', group: 'Actions', href: '/documents' },
  { id: 'new-auto',   label: 'New Automation',  subtitle: 'Create a workflow',             icon: Zap,           iconColor: 'text-yellow-500', group: 'Actions', href: '/automation' },
];

// ── Prefix-mode AI commands (type "> " to activate) ───────────────────────────
const AI_COMMANDS: CommandItem[] = [
  { id: 'ai-research',   label: '> Research Brief',    subtitle: 'Generate a research brief on a topic',      icon: BookOpen,     iconColor: 'text-violet-500', group: 'AI Commands', href: '/chat?q=research+brief' },
  { id: 'ai-summarize',  label: '> Summarize Article', subtitle: 'Paste URL to get AI summary',              icon: FileText,     iconColor: 'text-cyan-500',   group: 'AI Commands', href: '/chat?q=summarize' },
  { id: 'ai-debate',     label: '> Debate Mode',       subtitle: 'Get pro/con on any topic',                 icon: MessageSquare, iconColor: 'text-pink-500',  group: 'AI Commands', href: '/chat?q=debate' },
  { id: 'ai-translate',  label: '> Translate',         subtitle: 'Translate content to another language',    icon: TrendingUp,   iconColor: 'text-emerald-500',group: 'AI Commands', href: '/chat?q=translate' },
  { id: 'ai-catchup',    label: '> Catch Me Up',       subtitle: 'Brief on what you missed',                 icon: Zap,          iconColor: 'text-amber-500',  group: 'AI Commands', href: '/?catchup=1' },
  { id: 'ai-analytics',  label: '> View Analytics',    subtitle: 'See your reading stats',                   icon: Clock,        iconColor: 'text-indigo-500', group: 'AI Commands', href: '/analytics' },
];

const NAV_ITEMS: CommandItem[] = [
  { id: 'nav-home',   label: 'Home',           icon: Home,         iconColor: 'text-indigo-500', group: 'Navigation', href: '/' },
  { id: 'nav-feed',   label: 'Tech Feed',      icon: Newspaper,    iconColor: 'text-cyan-500',   group: 'Navigation', href: '/feed' },
  { id: 'nav-github', label: 'GitHub Radar',   icon: GitBranch,    iconColor: 'text-emerald-500',group: 'Navigation', href: '/github' },
  { id: 'nav-res',    label: 'Research',       icon: BookOpen,     iconColor: 'text-violet-500', group: 'Navigation', href: '/research' },
  { id: 'nav-vids',   label: 'Videos',         icon: Youtube,      iconColor: 'text-red-500',    group: 'Navigation', href: '/videos' },
  { id: 'nav-tweets', label: 'X Feed',         icon: Twitter,      iconColor: 'text-sky-400',    group: 'Navigation', href: '/tweets' },
  { id: 'nav-trends', label: 'Trends',         icon: TrendingUp,   iconColor: 'text-amber-500',  group: 'Navigation', href: '/trends' },
  { id: 'nav-chat',   label: 'AI Chat',        icon: MessageSquare,iconColor: 'text-sky-500',    group: 'Navigation', href: '/chat' },
  { id: 'nav-agents', label: 'AI Agents',      icon: Bot,          iconColor: 'text-pink-500',   group: 'Navigation', href: '/agents' },
  { id: 'nav-docs',   label: 'Documents',      icon: FileText,     iconColor: 'text-orange-500', group: 'Navigation', href: '/documents' },
  { id: 'nav-prompts',label: 'Prompt Library', icon: BookOpen,     iconColor: 'text-indigo-400', group: 'Navigation', href: '/prompts' },
  { id: 'nav-sets',   label: 'Settings',       icon: Settings,     iconColor: 'text-slate-500',  group: 'Navigation', href: '/settings' },
  { id: 'nav-bill',   label: 'Billing',        icon: CreditCard,   iconColor: 'text-amber-500',  group: 'Navigation', href: '/billing' },
];

const TYPE_ICON: Record<string, { icon: React.ElementType; color: string }> = {
  article:    { icon: Newspaper,  color: 'text-cyan-500'    },
  paper:      { icon: BookOpen,   color: 'text-violet-500'  },
  repository: { icon: GitBranch,  color: 'text-emerald-500' },
  video:      { icon: Youtube,    color: 'text-red-500'     },
  tweet:      { icon: Twitter,    color: 'text-sky-400'     },
};

const TYPE_HREF: Record<string, string> = {
  article:    '/feed',
  paper:      '/research',
  repository: '/github',
  video:      '/videos',
  tweet:      '/tweets',
};

// ── Debounce hook ─────────────────────────────────────────────────────────────

function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

// ── Group header ─────────────────────────────────────────────────────────────

function GroupLabel({ label }: { label: string }) {
  return (
    <div className="px-4 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
      {label}
    </div>
  );
}

// ── Single result row ─────────────────────────────────────────────────────────

function CommandRow({
  item, isActive, onSelect,
}: { item: CommandItem; isActive: boolean; onSelect: () => void }) {
  const Icon = item.icon;
  return (
    <button
      onMouseDown={(e) => { e.preventDefault(); onSelect(); }}
      className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors ${
        isActive
          ? 'bg-indigo-50 dark:bg-indigo-900/30'
          : 'hover:bg-slate-50 dark:hover:bg-slate-800/60'
      }`}
    >
      <div className={`flex-shrink-0 ${item.iconColor ?? 'text-slate-400'}`}>
        <Icon size={16} />
      </div>
      <div className="flex-1 min-w-0">
        <span className={`text-sm font-medium ${isActive ? 'text-indigo-600 dark:text-indigo-400' : 'text-slate-800 dark:text-slate-100'}`}>
          {item.label}
        </span>
        {item.subtitle && (
          <span className="ml-2 text-xs text-slate-400 dark:text-slate-500 truncate">{item.subtitle}</span>
        )}
      </div>
      {isActive && <ArrowRight size={14} className="flex-shrink-0 text-indigo-500" />}
    </button>
  );
}

// ── Main CommandPalette ───────────────────────────────────────────────────────

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
}

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const router        = useRouter();
  const inputRef      = useRef<HTMLInputElement>(null);
  const [query, setQuery]       = useState('');
  const [activeIdx, setActiveIdx] = useState(0);
  const [results, setResults]   = useState<CommandItem[]>([]);
  const [loading, setLoading]   = useState(false);
  // debouncedQuery kept for backwards compat — search now uses debouncedSearchQ below
  const _debouncedQueryUnused = useDebounce(query, 200);

  // Focus input when opened
  useEffect(() => {
    if (open) {
      setQuery('');
      setResults([]);
      setActiveIdx(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  // Fetch search results — also handles @articles prefix mode
  const searchQ = useMemo(() => {
    const q = query.trimStart()
    if (q.startsWith('@')) return q.slice(1).trimStart()
    if (q.startsWith('>') || q.startsWith('#')) return ''
    return query
  }, [query])
  const debouncedSearchQ = useDebounce(searchQ, 220)

  useEffect(() => {
    if (!debouncedSearchQ.trim() || debouncedSearchQ.length < 2) {
      setResults([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    const params: Record<string,string|number> = { q: debouncedSearchQ, limit: 5 }
    if (query.trimStart().startsWith('@')) params['content_type'] = 'article'
    api.get('/search/', { params })
      .then(r => {
        const hits: any[] = r.data?.results ?? r.data?.data ?? [];
        const mapped: CommandItem[] = hits.map((h: any) => {
          const type   = h.type ?? 'article';
          const config = TYPE_ICON[type] ?? TYPE_ICON.article;
          return {
            id:       h.id,
            label:    h.title || h.full_name || h.name || 'Untitled',
            subtitle: h.summary || h.description || h.abstract || '',
            icon:     config.icon,
            iconColor: config.color,
            group:    'Content',
            href:     h.url ?? TYPE_HREF[type] ?? '/',
          };
        });
        setResults(mapped);
      })
      .catch(() => setResults([]))
      .finally(() => setLoading(false));
  }, [debouncedSearchQ, query]);

  // Detect prefix mode
  const prefixMode = useMemo(() => {
    const q = query.trimStart()
    if (q.startsWith('>')) return 'ai'
    if (q.startsWith('@')) return 'articles'
    if (q.startsWith('#')) return 'topics'
    return null
  }, [query])

  const bareQuery = useMemo(() => {
    if (!prefixMode) return query
    return query.trimStart().slice(1).trimStart()
  }, [query, prefixMode])

  // Build visible items list
  const items = useMemo<CommandItem[]>(() => {
    // AI prefix mode
    if (prefixMode === 'ai') {
      if (!bareQuery) return AI_COMMANDS
      return AI_COMMANDS.filter(c => c.label.toLowerCase().includes(bareQuery.toLowerCase()) || c.subtitle?.toLowerCase().includes(bareQuery.toLowerCase()))
    }

    // Topic prefix mode
    if (prefixMode === 'topics') {
      if (!bareQuery) return NAV_ITEMS.map(n => ({ ...n, group: 'Topics' }))
      return NAV_ITEMS.filter(n => n.label.toLowerCase().includes(bareQuery.toLowerCase())).map(n => ({ ...n, group: 'Topics' }))
    }

    // Article prefix mode or regular search
    if (bareQuery.trim().length >= 2 || (prefixMode === 'articles' && bareQuery.trim().length >= 2)) {
      if (results.length === 0 && !loading) return [];
      return results;
    }
    // Empty query — show quick actions + nav
    const filtered = query
      ? [...QUICK_ACTIONS, ...NAV_ITEMS].filter(i =>
          i.label.toLowerCase().includes(query.toLowerCase())
        )
      : [...QUICK_ACTIONS, ...NAV_ITEMS];
    return filtered;
  }, [query, bareQuery, prefixMode, results, loading]);

  // Keyboard nav
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIdx(i => Math.min(i + 1, items.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIdx(i => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const item = items[activeIdx];
      if (item) { router.push(item.href); onClose(); }
    } else if (e.key === 'Escape') {
      onClose();
    }
  }, [items, activeIdx, router, onClose]);

  // Reset active on items change
  useEffect(() => { setActiveIdx(0); }, [items]);

  if (!open) return null;

  // Group items for display
  const grouped: Record<string, CommandItem[]> = {};
  for (const item of items) {
    if (!grouped[item.group]) grouped[item.group] = [];
    grouped[item.group].push(item);
  }

  let globalIdx = 0;
  const groupEntries = Object.entries(grouped);

  const content = (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh] px-4"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />

      {/* Panel */}
      <div className="relative w-full max-w-xl bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-700/60 overflow-hidden animate-scale-in">

        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-100 dark:border-slate-800">
          {loading
            ? <Loader2 size={18} className="flex-shrink-0 text-slate-400 animate-spin" />
            : <Search size={18} className="flex-shrink-0 text-slate-400" />
          }
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search… or type > AI  @ Articles  # Topics"
            className="flex-1 bg-transparent text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 text-sm focus:outline-none"
          />
          {query && (
            <button onClick={() => setQuery('')} className="flex-shrink-0 p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
              <X size={14} className="text-slate-400" />
            </button>
          )}
          <kbd className="hidden sm:inline-flex items-center px-1.5 py-0.5 rounded border border-slate-200 dark:border-slate-700 text-[11px] text-slate-400 font-mono ml-1">
            Esc
          </kbd>
        </div>

        {/* Results */}
        <div className="max-h-[420px] overflow-y-auto py-1">
          {loading && query.length >= 2 && (
            <div className="px-4 py-8 text-center text-sm text-slate-400">
              Searching…
            </div>
          )}

          {!loading && query.length >= 2 && results.length === 0 && (
            <div className="px-4 py-8 text-center text-sm text-slate-400">
              No results for <span className="font-medium text-slate-600 dark:text-slate-300">"{query}"</span>
            </div>
          )}

          {groupEntries.map(([group, groupItems]) => (
            <div key={group}>
              <GroupLabel label={group} />
              {groupItems.map(item => {
                const idx = globalIdx++;
                return (
                  <CommandRow
                    key={item.id}
                    item={item}
                    isActive={idx === activeIdx}
                    onSelect={() => { router.push(item.href); onClose(); }}
                  />
                );
              })}
            </div>
          ))}

          {items.length === 0 && !loading && query.length < 2 && (
            <div className="px-4 py-8 text-center text-sm text-slate-400">
              Type to search articles, papers, repos…
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center gap-3 px-4 py-2.5 border-t border-slate-100 dark:border-slate-800 text-[11px] text-slate-400 dark:text-slate-500 flex-wrap">
          <span className="flex items-center gap-1"><kbd className="font-mono px-1 py-0.5 rounded border border-slate-200 dark:border-slate-700">↑↓</kbd> Nav</span>
          <span className="flex items-center gap-1"><kbd className="font-mono px-1 py-0.5 rounded border border-slate-200 dark:border-slate-700">↵</kbd> Open</span>
          <span className="flex items-center gap-1"><kbd className="font-mono px-1 py-0.5 rounded border border-slate-200 dark:border-slate-700">Esc</kbd> Close</span>
          <span className="ml-auto flex items-center gap-2">
            <span className="px-1.5 py-0.5 bg-violet-100 dark:bg-violet-900/30 text-violet-600 dark:text-violet-400 rounded font-mono font-bold">&gt;</span> AI
            <span className="px-1.5 py-0.5 bg-cyan-100 dark:bg-cyan-900/30 text-cyan-600 dark:text-cyan-400 rounded font-mono font-bold">@</span> Articles
            <span className="px-1.5 py-0.5 bg-amber-100 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400 rounded font-mono font-bold">#</span> Topics
          </span>
        </div>
      </div>
    </div>
  );

  if (typeof document === 'undefined') return null;
  const modalRoot = document.getElementById('modal-root');
  return modalRoot ? createPortal(content, modalRoot) : content;
}

export default CommandPalette;
