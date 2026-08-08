'use client'

import React, { useState, useEffect, useRef } from 'react'
import { useSearchParams } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import {
  Search, FileText, GitBranch, BookOpen, Loader2, Sparkles,
  TrendingUp, Clock, X, Youtube, Twitter,
} from 'lucide-react'
import api from '@/utils/api'
import { useDebounce } from '@/hooks/useDebounce'
import { ArticleCard } from '@/components/cards/ArticleCard'
import { RepositoryCard } from '@/components/cards/RepositoryCard'
import { PaperCard } from '@/components/cards/PaperCard'
import { TweetCard } from '@/components/cards/TweetCard'
import { VideoCard, type Video } from '@/components/cards/VideoCard'
import { VideoPlayerModal } from '@/components/modals/VideoPlayerModal'
import { cn } from '@/utils/helpers'
import { motion, AnimatePresence } from 'framer-motion'

type TabType = 'all' | 'articles' | 'repos' | 'papers' | 'videos' | 'tweets'

const TABS: { id: TabType; label: string; icon: React.ElementType; colour: string }[] = [
  { id: 'all',      label: 'All',      icon: Search,    colour: 'text-indigo-600 dark:text-indigo-400'   },
  { id: 'articles', label: 'Articles', icon: FileText,  colour: 'text-cyan-600 dark:text-cyan-400'      },
  { id: 'repos',    label: 'Repos',    icon: GitBranch, colour: 'text-emerald-600 dark:text-emerald-400' },
  { id: 'papers',   label: 'Papers',   icon: BookOpen,  colour: 'text-violet-600 dark:text-violet-400'   },
  { id: 'videos',   label: 'Videos',   icon: Youtube,   colour: 'text-red-400'                           },
  { id: 'tweets',   label: 'X / Tweets', icon: Twitter, colour: 'text-sky-500 dark:text-sky-400'         },
]

const TRENDING_SEARCHES = [
  'LLM fine-tuning', 'Next.js 15', 'Rust async', 'RAG pipeline',
  'TypeScript 5', 'AI agents', 'vector database', 'open source LLM',
]

const MAX_HISTORY = 8
const HISTORY_KEY = 'synapse_search_history'

function getHistory(): string[] {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]') } catch { return [] }
}
function addHistory(q: string) {
  const prev = getHistory().filter(s => s !== q)
  localStorage.setItem(HISTORY_KEY, JSON.stringify([q, ...prev].slice(0, MAX_HISTORY)))
}
function clearHistory() { localStorage.removeItem(HISTORY_KEY) }

export default function SearchPage() {
  const searchParams = useSearchParams()
  const initialQuery = searchParams?.get('q') || ''
  const [query, setQuery] = useState(initialQuery)
  const [activeTab, setActiveTab] = useState<TabType>('all')
  const [inputFocused, setInputFocused] = useState(false)
  const [history, setHistory] = useState<string[]>([])
  const [playingVideo, setPlayingVideo] = useState<Video | null>(null)
  const debouncedQuery = useDebounce(query, 350)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { setHistory(getHistory()) }, [])
  useEffect(() => { setQuery(searchParams?.get('q') || '') }, [searchParams])

  // ── Main search query ───────────────────────────────────────────────────────
  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['search', debouncedQuery],
    queryFn: async () => {
      addHistory(debouncedQuery)
      setHistory(getHistory())
      const r = await api.get('/search/', { params: { q: debouncedQuery, limit: 30 } })
      return r.data
    },
    enabled: debouncedQuery.length >= 2,
    staleTime: 30_000,
  })

  // ── Semantic search query (POST — backend expects JSON body) ───────────────
  const { data: semanticData, isFetching: semanticFetching } = useQuery({
    queryKey: ['semantic-search', debouncedQuery],
    queryFn: () =>
      api.post('/search/semantic/', {
        query: debouncedQuery,
        limit: 5,
        content_types: ['articles', 'papers', 'repos', 'videos', 'tweets'],
      }).then(r => r.data),
    enabled: debouncedQuery.length >= 4,
    staleTime: 60_000,
  })

  const articles = data?.data?.articles || []
  const repos    = data?.data?.repos    || []
  const papers   = data?.data?.papers   || []
  const videos   = data?.data?.videos   || []
  const tweets   = data?.data?.tweets   || []
  const total    = (articles.length + repos.length + papers.length + videos.length + tweets.length) || data?.meta?.total || 0
  const semanticResults: any[] = semanticData?.data?.results || semanticData?.results || []

  const showLoading  = (isLoading || isFetching) && debouncedQuery.length >= 2
  const hasResults   = total > 0
  const showDropdown = inputFocused && !debouncedQuery && (history.length > 0 || TRENDING_SEARCHES.length > 0)

  const handleSelect = (q: string) => { setQuery(q); setInputFocused(false); inputRef.current?.blur() }
  const handleClear  = () => { setQuery(''); inputRef.current?.focus() }

  const tabCounts: Record<TabType, number> = {
    all:      total,
    articles: articles.length,
    repos:    repos.length,
    papers:   papers.length,
    videos:   videos.length,
    tweets:   tweets.length,
  }

  return (
    <div className="flex-1 overflow-y-auto bg-slate-50 dark:bg-slate-950 p-4 sm:p-6">
      <VideoPlayerModal video={playingVideo} onClose={() => setPlayingVideo(null)} />
      <div className="max-w-4xl mx-auto space-y-4 sm:space-y-6 pb-10">

        {/* ── Header ── */}
        <div>
          <h1 className="text-2xl sm:text-3xl font-black text-slate-900 dark:text-white tracking-tight">Search</h1>
          <p className="text-slate-400 text-xs sm:text-sm mt-0.5">
            Search across articles, repositories, research papers &amp; videos
          </p>
        </div>

        {/* ── Search Input + Dropdown ── */}
        <div className="relative">
          <div className={cn(
            'flex items-center gap-3 px-4 py-3 sm:py-4 bg-slate-100 dark:bg-slate-800/90 border rounded-2xl transition-all duration-200',
            inputFocused
              ? 'border-indigo-400 dark:border-indigo-500/80 shadow-lg shadow-indigo-500/10 ring-1 ring-indigo-400/30 dark:ring-indigo-500/30'
              : 'border-slate-300 dark:border-slate-700 hover:border-slate-400 dark:hover:border-slate-600'
          )}>
            <Search size={18} className="text-slate-500 shrink-0" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              onFocus={() => setInputFocused(true)}
              onBlur={() => setTimeout(() => setInputFocused(false), 150)}
              onKeyDown={e => e.key === 'Escape' && handleClear()}
              placeholder="Search articles, papers, repos, videos…"
              autoFocus
              className="flex-1 bg-transparent text-slate-800 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none text-sm sm:text-base min-w-0"
            />
            {showLoading
              ? <Loader2 size={16} className="text-indigo-600 dark:text-indigo-400 animate-spin shrink-0" />
              : query
              ? <button onClick={handleClear} className="text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-200 transition-colors shrink-0 p-0.5 rounded">
                  <X size={16} />
                </button>
              : null
            }
          </div>

          {/* Dropdown — history + trending */}
          <AnimatePresence>
            {showDropdown && (
              <motion.div
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.12 }}
                className="absolute top-full mt-2 w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl shadow-2xl overflow-hidden z-20"
              >
                {history.length > 0 && (
                  <div className="p-3 border-b border-slate-200 dark:border-slate-700/60">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide flex items-center gap-1.5">
                        <Clock size={11} /> Recent
                      </span>
                      <button
                        onClick={() => { clearHistory(); setHistory([]) }}
                        className="text-xs text-slate-600 hover:text-slate-400 transition-colors"
                      >
                        Clear
                      </button>
                    </div>
                    <div className="space-y-0.5">
                      {history.map(h => (
                        <button
                          key={h}
                          onMouseDown={() => handleSelect(h)}
                          className="w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700/60 text-left transition-colors"
                        >
                          <Clock size={13} className="text-slate-600 shrink-0" />
                          <span className="text-sm text-slate-600 dark:text-slate-300 truncate">{h}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                <div className="p-3">
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide flex items-center gap-1.5 mb-2">
                    <TrendingUp size={11} /> Trending
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {TRENDING_SEARCHES.map(t => (
                      <button
                        key={t}
                        onMouseDown={() => handleSelect(t)}
                        className="px-2.5 py-1 rounded-full bg-slate-200 dark:bg-slate-700/70 hover:bg-indigo-100 dark:hover:bg-indigo-600/30 border border-slate-300 dark:border-slate-600/50 hover:border-indigo-400 dark:hover:border-indigo-500/50 text-xs text-slate-600 dark:text-slate-300 hover:text-indigo-600 dark:hover:text-indigo-300 transition-all"
                      >
                        {t}
                      </button>
                    ))}
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* ── Semantic AI Results ── */}
        <AnimatePresence>
          {semanticResults.length > 0 && debouncedQuery.length >= 4 && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="bg-gradient-to-r from-indigo-900/30 to-violet-900/20 border border-indigo-500/25 rounded-2xl p-4"
            >
              <div className="flex items-center gap-2 mb-3">
                <Sparkles size={14} className="text-indigo-600 dark:text-indigo-400 shrink-0" />
                <span className="text-xs font-bold text-indigo-700 dark:text-indigo-300 uppercase tracking-widest">AI Semantic Match</span>
                {semanticFetching && <Loader2 size={12} className="animate-spin text-indigo-600 dark:text-indigo-400" />}
              </div>
              <div className="space-y-2">
                {semanticResults.slice(0, 3).map((r: any, i: number) => (
                  <a
                    key={i}
                    href={r.url || r.content_url || '#'}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-start gap-3 p-2.5 rounded-xl hover:bg-indigo-500/10 transition-colors group"
                  >
                    <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 mt-1.5 shrink-0" />
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-slate-700 dark:text-slate-200 group-hover:text-indigo-300 transition-colors truncate">
                        {r.title || r.name || 'Untitled'}
                      </p>
                      {r.summary && (
                        <p className="text-xs text-slate-500 line-clamp-1 mt-0.5">{r.summary}</p>
                      )}
                    </div>
                  </a>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Results header + Tabs ── */}
        {debouncedQuery.length >= 2 && !showLoading && hasResults && (
          <div className="flex flex-col xs:flex-row xs:items-center justify-between gap-3">
            <p className="text-slate-400 text-xs sm:text-sm shrink-0">
              <span className="text-slate-900 dark:text-white font-bold">{total}</span> results for{' '}
              <span className="text-indigo-600 dark:text-indigo-400 font-semibold">"{debouncedQuery}"</span>
            </p>
            {/* Tabs — scrollable */}
            <div className="flex gap-1 bg-slate-100 dark:bg-slate-800/80 rounded-xl p-1 overflow-x-auto scrollbar-hide shrink-0">
              {TABS.map(tab => {
                const count = tabCounts[tab.id]
                if (tab.id !== 'all' && count === 0) return null
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={cn(
                      'flex items-center gap-1 sm:gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-lg text-xs font-semibold transition-all whitespace-nowrap shrink-0',
                      activeTab === tab.id
                        ? 'bg-indigo-600 text-white shadow-sm'
                        : 'text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-white'
                    )}
                  >
                    <tab.icon size={12} className={activeTab === tab.id ? 'text-slate-900 dark:text-white' : tab.colour} />
                    {tab.label}
                    {tab.id !== 'all' && count > 0 && (
                      <span className="opacity-60 text-[10px]">({count})</span>
                    )}
                  </button>
                )
              })}
            </div>
          </div>
        )}

        {/* ── Results ── */}
        {debouncedQuery.length < 2 ? (
          <div className="text-center py-20">
            <div className="w-16 h-16 rounded-2xl bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 flex items-center justify-center mx-auto mb-4">
              <Search size={28} className="text-slate-600" />
            </div>
            <p className="text-slate-400 text-base font-medium mb-1">What are you looking for?</p>
            <p className="text-slate-600 text-sm">Type at least 2 characters to start searching</p>
            {/* Quick trending pills */}
            <div className="flex flex-wrap justify-center gap-2 mt-6">
              {TRENDING_SEARCHES.slice(0, 6).map(t => (
                <button
                  key={t}
                  onClick={() => handleSelect(t)}
                  className="px-3 py-1.5 rounded-full bg-slate-100 dark:bg-slate-800 hover:bg-indigo-50 dark:hover:bg-indigo-600/20 border border-slate-200 dark:border-slate-700 hover:border-indigo-400 dark:hover:border-indigo-500/50 text-xs text-slate-500 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-300 transition-all"
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
        ) : showLoading ? (
          <div className="flex flex-col items-center justify-center py-24 gap-3">
            <Loader2 size={32} className="animate-spin text-indigo-600 dark:text-indigo-400" />
            <p className="text-slate-500 text-sm">Searching…</p>
          </div>
        ) : !hasResults ? (
          <div className="text-center py-20 bg-slate-100 dark:bg-slate-900/50 rounded-2xl border border-slate-200 dark:border-slate-700">
            <Search size={40} className="mx-auto text-slate-600 mb-3" />
            <p className="text-slate-700 dark:text-slate-300 font-semibold mb-1">No results found</p>
            <p className="text-slate-500 text-sm">Try different keywords or broaden your search</p>
            <div className="flex flex-wrap justify-center gap-2 mt-5">
              {TRENDING_SEARCHES.slice(0, 4).map(t => (
                <button
                  key={t}
                  onClick={() => handleSelect(t)}
                  className="px-3 py-1.5 rounded-full bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs text-slate-500 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-300 hover:border-indigo-400 dark:hover:border-indigo-500/50 transition-all"
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="space-y-8 sm:space-y-10"
            >
              {/* Articles */}
              {(activeTab === 'all' || activeTab === 'articles') && articles.length > 0 && (
                <section>
                  <h2 className="text-sm sm:text-base font-bold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                    <FileText size={16} className="text-cyan-400 shrink-0" />
                    Articles
                    <span className="text-xs text-slate-500 font-normal">({articles.length})</span>
                  </h2>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
                    {articles.map((a: any) => <ArticleCard key={a.id} article={a} />)}
                  </div>
                </section>
              )}

              {/* Repositories */}
              {(activeTab === 'all' || activeTab === 'repos') && repos.length > 0 && (
                <section>
                  <h2 className="text-sm sm:text-base font-bold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                    <GitBranch size={16} className="text-emerald-400 shrink-0" />
                    Repositories
                    <span className="text-xs text-slate-500 font-normal">({repos.length})</span>
                  </h2>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
                    {repos.map((r: any) => <RepositoryCard key={r.id} repo={r} />)}
                  </div>
                </section>
              )}

              {/* Papers */}
              {(activeTab === 'all' || activeTab === 'papers') && papers.length > 0 && (
                <section>
                  <h2 className="text-sm sm:text-base font-bold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                    <BookOpen size={16} className="text-violet-400 shrink-0" />
                    Research Papers
                    <span className="text-xs text-slate-500 font-normal">({papers.length})</span>
                  </h2>
                  <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3 sm:gap-4">
                    {papers.map((p: any) => <PaperCard key={p.id} paper={p} />)}
                  </div>
                </section>
              )}

              {/* Videos */}
              {(activeTab === 'all' || activeTab === 'videos') && videos.length > 0 && (
                <section>
                  <h2 className="text-sm sm:text-base font-bold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                    <Youtube size={16} className="text-red-400 shrink-0" />
                    Videos
                    <span className="text-xs text-slate-500 font-normal">({videos.length})</span>
                  </h2>
                  <div className="grid grid-cols-1 xs:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
                    {videos.map((v: any) => <VideoCard key={v.id} video={v} onPlay={(vid) => setPlayingVideo(vid)} />)}
                  </div>
                </section>
              )}

              {/* Tweets */}
              {(activeTab === 'all' || activeTab === 'tweets') && tweets.length > 0 && (
                <section>
                  <h2 className="text-sm sm:text-base font-bold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                    <Twitter size={16} className="text-sky-400 shrink-0" />
                    X / Tweets
                    <span className="text-xs text-slate-500 font-normal">({tweets.length})</span>
                  </h2>
                  <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3 sm:gap-4">
                    {tweets.map((t: any) => <TweetCard key={t.id} tweet={t} />)}
                  </div>
                </section>
              )}
            </motion.div>
          </AnimatePresence>
        )}
      </div>
    </div>
  )
}
