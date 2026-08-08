'use client';

export const dynamic = 'force-dynamic';

import React, { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { BarChart3, BookOpen, GitBranch, Youtube, Zap, ArrowRight, TrendingUp, Bookmark, MessageSquare, FileText, Twitter, Sun, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react';
import Link from 'next/link';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import api from '@/utils/api';
import { ArticleCard, RepositoryCard, PaperCard, TweetCard } from '@/components/cards';
import { HorizontalScroller } from '@/components/ui/HorizontalScroller';
import { ActivityHeatmap } from '@/components/ui/ActivityHeatmap';
import { VideoCard, type Video } from '@/components/cards/VideoCard';
import { VideoPlayerModal } from '@/components/modals/VideoPlayerModal';
import { ArticleSkeleton, RepositorySkeleton, PaperSkeleton } from '@/components/cards/SkeletonCard';
import { CatchMeUp } from '@/components/ui/CatchMeUp';
import { ReadingGoals } from '@/components/ui/ReadingGoals';
import { TopicWatchlist } from '@/components/ui/TopicWatchlist';
import { NetworkReading } from '@/components/ui/NetworkReading';
import { InterestProfileBuilder, useInterestProfile } from '@/components/ui/InterestProfileBuilder';

const StatCard = ({ icon: Icon, label, value, gradient, href }: any) => (
  <Link href={href || '#'} className="group">
    <div className={`rounded-2xl p-4 sm:p-5 text-white relative overflow-hidden transition-all duration-200 group-hover:scale-[1.02] group-hover:shadow-xl ${gradient}`}>
      <div className="absolute inset-0 opacity-10" style={{backgroundImage: 'radial-gradient(circle at 80% 20%, white 1px, transparent 1px)', backgroundSize: '20px 20px'}} />
      <div className="relative flex items-center justify-between">
        <div className="min-w-0">
          <p className="text-xs sm:text-sm font-medium opacity-80 truncate">{label}</p>
          <p className="text-2xl sm:text-3xl font-black mt-0.5 truncate">{value?.toLocaleString?.() ?? value}</p>
        </div>
        <div className="w-10 h-10 sm:w-12 sm:h-12 bg-white/20 rounded-xl flex items-center justify-center backdrop-blur-sm flex-shrink-0">
          <Icon className="w-5 h-5 sm:w-6 sm:h-6" />
        </div>
      </div>
      <div className="relative mt-3 flex items-center gap-1 text-[10px] sm:text-xs font-medium opacity-70 group-hover:opacity-100 transition-opacity">
        <span>View all</span>
        <ArrowRight size={12} className="group-hover:translate-x-0.5 transition-transform" />
      </div>
    </div>
  </Link>
);

// ── TrendStrip — top 6 trending technologies ──────────────────────────────────
const CATEGORY_COLOUR: Record<string, string> = {
  language: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30',
  ai_ml:    'bg-violet-500/15 text-violet-400 border-violet-500/30',
  devops:   'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  web:      'bg-amber-500/15 text-amber-400 border-amber-500/30',
  general:  'bg-slate-500/15 text-slate-400 border-slate-500/30',
}

function TrendStrip() {
  const { data } = useQuery({
    queryKey: ['trends-strip'],
    queryFn: async () => {
      const { data } = await api.get('/trends/?ordering=-trend_score&limit=6')
      // Normalize: backend returns {success, count, results: [...]}
      const items: any[] = Array.isArray(data?.results) ? data.results
        : Array.isArray(data?.data) ? data.data
        : Array.isArray(data) ? data : []
      return items
    },
    staleTime: 5 * 60_000,    // 5 min — trends don't change fast
  })
  const trends: any[] = Array.isArray(data) ? data : []
  if (!trends.length) return null
  const maxScore = Math.max(...trends.map((t: any) => t.trend_score), 1)

  return (
    <div className="mb-6 bg-white dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 rounded-2xl p-4 shadow-card dark:shadow-none">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <TrendingUp size={15} className="text-amber-500 dark:text-amber-400" />
          <span className="text-sm font-bold text-slate-800 dark:text-white">🔥 Trending Technologies</span>
        </div>
        <Link href="/trends" className="text-xs text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 font-semibold flex items-center gap-1 transition-colors">
          View all <ArrowRight size={11} />
        </Link>
      </div>
      <div className="flex flex-wrap gap-2">
        {trends.map((t: any) => {
          const pct = Math.round((t.trend_score / maxScore) * 100)
          const colour = CATEGORY_COLOUR[t.category] ?? CATEGORY_COLOUR.general
          return (
            <Link key={t.id} href="/trends" className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl border text-xs font-semibold transition-all hover:scale-105 ${colour}`}>
              <span className="truncate max-w-[80px]">{t.technology_name}</span>
              <span className="opacity-60 text-[10px] font-bold">{pct}%</span>
            </Link>
          )
        })}
      </div>
    </div>
  )
}

// ── TASK-305-F1: Today's Brief card ──────────────────────────────────────────
function TodayBriefCard() {
  const [expanded, setExpanded] = useState(false);
  const { data, isLoading, isError } = useQuery({
    queryKey: ['briefing', 'today'],
    queryFn: () => api.get('/briefing/today/').then(r => r.data?.data),
    staleTime: 2 * 60_000,    // 2 min — briefing updates after workflow
    retry: false,
  });

  const greeting = (() => {
    const h = new Date().getHours();
    if (h < 12) return 'Good morning';
    if (h < 17) return 'Good afternoon';
    return 'Good evening';
  })();

  if (isLoading) {
    return (
      <div className="rounded-2xl border border-amber-200 dark:border-amber-800/40 bg-gradient-to-br from-amber-50 to-orange-50 dark:from-amber-950/30 dark:to-orange-950/20 p-6 animate-pulse">
        <div className="h-5 w-48 bg-amber-200/60 dark:bg-amber-700/40 rounded mb-3" />
        <div className="h-4 w-full bg-amber-100/80 dark:bg-amber-800/30 rounded mb-2" />
        <div className="h-4 w-3/4 bg-amber-100/80 dark:bg-amber-800/30 rounded" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="rounded-2xl border border-slate-200 dark:border-slate-700/60 bg-slate-50 dark:bg-slate-800/40 p-6 flex items-center gap-4">
        <div className="w-10 h-10 rounded-xl bg-amber-100 dark:bg-amber-900/40 flex items-center justify-center flex-shrink-0">
          <Sun size={20} className="text-amber-500" />
        </div>
        <div>
          <p className="font-semibold text-slate-700 dark:text-slate-200">{greeting}! Your daily brief couldn't load.</p>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">Check your connection or try again in a moment.</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="rounded-2xl border border-slate-200 dark:border-slate-700/60 bg-slate-50 dark:bg-slate-800/40 p-6 flex items-center gap-4">
        <div className="w-10 h-10 rounded-xl bg-amber-100 dark:bg-amber-900/40 flex items-center justify-center flex-shrink-0">
          <Sun size={20} className="text-amber-500" />
        </div>
        <div>
          <p className="font-semibold text-slate-700 dark:text-slate-200">{greeting}! Your daily brief isn't ready yet.</p>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">Briefings are generated automatically when content is available.</p>
        </div>
      </div>
    );
  }

  const sources: any[] = Array.isArray(data.sources) ? data.sources : [];
  const topics: string[] = data.topic_summary?.topics ?? [];

  return (
    <div className="rounded-2xl border border-amber-200 dark:border-amber-800/40 bg-gradient-to-br from-amber-50 via-orange-50 to-yellow-50 dark:from-amber-950/30 dark:via-orange-950/20 dark:to-yellow-950/10 overflow-hidden">
      {/* Header */}
      <div className="px-6 pt-5 pb-3 flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center shadow-sm flex-shrink-0">
            <Sun size={20} className="text-white" />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-amber-600 dark:text-amber-400">
              Today's Brief · {new Date(data.date).toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}
            </p>
            <p className="text-base font-bold text-slate-800 dark:text-slate-100 mt-0.5">
              {greeting}! Here's what's happening in tech
              {topics.length > 0 ? ` — ${topics.slice(0, 3).join(', ')}` : ''}.
            </p>
          </div>
        </div>
        <button
          onClick={() => setExpanded(e => !e)}
          className="flex-shrink-0 flex items-center gap-1 text-xs font-medium text-amber-600 dark:text-amber-400 hover:text-amber-800 dark:hover:text-amber-200 transition-colors mt-1"
        >
          {expanded ? <><ChevronUp size={14} /> Collapse</> : <><ChevronDown size={14} /> Expand</>}
        </button>
      </div>

      {/* Content with Markdown Rendering */}
      <div className="px-6 pb-4">
        <div className={`prose prose-sm prose-slate dark:prose-invert max-w-none ${expanded ? '' : 'line-clamp-4'}`}>
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              h1: ({children}) => <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100 mt-4 mb-2">{children}</h1>,
              h2: ({children}) => <h2 className="text-lg font-bold text-slate-700 dark:text-slate-200 mt-3 mb-2">{children}</h2>,
              h3: ({children}) => <h3 className="text-base font-semibold text-slate-700 dark:text-slate-200 mt-2 mb-1">{children}</h3>,
              p: ({children}) => <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed mb-2">{children}</p>,
              ul: ({children}) => <ul className="list-disc list-inside text-sm text-slate-700 dark:text-slate-300 mb-2 ml-2">{children}</ul>,
              ol: ({children}) => <ol className="list-decimal list-inside text-sm text-slate-700 dark:text-slate-300 mb-2 ml-2">{children}</ol>,
              li: ({children}) => <li className="mb-1">{children}</li>,
              blockquote: ({children}) => (
                <blockquote className="border-l-4 border-amber-400 pl-3 italic text-slate-600 dark:text-slate-400 my-2">
                  {children}
                </blockquote>
              ),
              table: ({children}) => (
                <div className="overflow-x-auto my-3">
                  <table className="min-w-full text-xs border-collapse border border-slate-200 dark:border-slate-700 rounded-lg">
                    {children}
                  </table>
                </div>
              ),
              thead: ({children}) => <thead className="bg-slate-100 dark:bg-slate-800">{children}</thead>,
              th: ({children}) => (
                <th className="px-3 py-2 text-left font-semibold text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700">{children}</th>
              ),
              td: ({children}) => (
                <td className="px-3 py-2 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700">{children}</td>
              ),
              hr: () => <hr className="border-slate-200 dark:border-slate-700 my-3" />,
              a: ({href, children}) => (
                <a href={href} className="text-amber-600 dark:text-amber-400 hover:underline" target="_blank" rel="noopener noreferrer">
                  {children}
                </a>
              ),
            }}
          >
            {data.content}
          </ReactMarkdown>
        </div>

        {/* Sources */}
        {sources.length > 0 && expanded && (
          <div className="mt-4 pt-3 border-t border-amber-200/60 dark:border-amber-800/30">
            <p className="text-xs font-semibold uppercase tracking-wider text-amber-600 dark:text-amber-400 mb-2">Sources</p>
            <ol className="space-y-1">
              {sources.slice(0, 10).map((src: any, i: number) => (
                <li key={i} className="flex items-start gap-2 text-xs text-slate-600 dark:text-slate-400">
                  <span className="font-bold text-amber-500 flex-shrink-0">[{i + 1}]</span>
                  {src.url ? (
                    <a
                      href={src.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:text-amber-600 dark:hover:text-amber-300 transition-colors flex items-center gap-1 underline underline-offset-2"
                    >
                      {src.title || src.url}
                      <ExternalLink size={10} />
                    </a>
                  ) : (
                    <span>{src.title}</span>
                  )}
                  <span className="text-slate-400 dark:text-slate-600 ml-auto flex-shrink-0 capitalize">{src.type}</span>
                </li>
              ))}
            </ol>
          </div>
        )}

        {/* Footer actions */}
        <div className="mt-4 flex items-center gap-3">
          <Link
            href={`/chat?brief=${data.date}`}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-amber-700 dark:text-amber-300 bg-amber-100 dark:bg-amber-900/40 hover:bg-amber-200 dark:hover:bg-amber-800/50 px-3 py-1.5 rounded-lg transition-colors"
          >
            <MessageSquare size={12} />
            Ask follow-up
          </Link>
          {!expanded && sources.length > 0 && (
            <span className="text-xs text-slate-400 dark:text-slate-500">
              {sources.length} source{sources.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

const SectionHeader = ({ title, subtitle, href }: { title: string; subtitle?: string; href?: string }) => (
  <div className="flex items-center justify-between mb-5">
    <div>
      <h2 className="text-xl font-bold text-slate-900 dark:text-white">{title}</h2>
      {subtitle && <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">{subtitle}</p>}
    </div>
    {href && (
      <Link href={href} className="flex items-center gap-1 text-sm font-medium text-indigo-500 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors group">
        View all <ArrowRight size={14} className="group-hover:translate-x-0.5 transition-transform" />
      </Link>
    )}
  </div>
);

export default function Dashboard() {
  const [playingVideo, setPlayingVideo] = useState<Video | null>(null);
  const queryClient = useQueryClient();
  const { needsBuild } = useInterestProfile();
  const [showProfileBuilder, setShowProfileBuilder] = useState(false);
  useEffect(() => {
    if (needsBuild) {
      const t = setTimeout(() => setShowProfileBuilder(true), 4000);
      return () => clearTimeout(t);
    }
  }, [needsBuild]);

  // When a workflow completes, invalidate home content queries so new data appears.
  useEffect(() => {
    const invalidateHome = () => {
      // Only invalidate home content queries — count badges derive from these
      queryClient.invalidateQueries({ queryKey: ['articles', 'home'] });
      queryClient.invalidateQueries({ queryKey: ['repos', 'home'] });
      queryClient.invalidateQueries({ queryKey: ['papers', 'home'] });
      queryClient.invalidateQueries({ queryKey: ['videos', 'home'] });
      queryClient.invalidateQueries({ queryKey: ['tweets', 'home'] });
      queryClient.invalidateQueries({ queryKey: ['briefing', 'today'] });
    };

    // Same-page event
    window.addEventListener('synapse:workflow-complete', invalidateHome);

    // Cross-tab: workflow completed on automation page then user navigated here
    const onStorage = (e: StorageEvent) => {
      if (e.key === 'synapse:workflow-complete-at' && e.newValue) invalidateHome();
    };
    window.addEventListener('storage', onStorage);

    return () => {
      window.removeEventListener('synapse:workflow-complete', invalidateHome);
      window.removeEventListener('storage', onStorage);
    };
  }, [queryClient]);

  // Latest content for the home sections — ordered by scraped_at so newly
  // fetched items always appear at the top immediately after a workflow run.
  const { data: articles, isLoading: articlesLoading } = useQuery({
    queryKey: ['articles', 'home'],
    queryFn: () => api.get('/articles/', { params: { page_size: 12, ordering: '-scraped_at' } }).then(r => r.data),
    staleTime: 2 * 60_000,     // 2 min — don't re-fetch constantly
    gcTime:   10 * 60_000,
  });

  const { data: repos, isLoading: reposLoading } = useQuery({
    queryKey: ['repos', 'home'],
    queryFn: () => api.get('/repos/', { params: { page_size: 3, ordering: '-scraped_at' } }).then(r => r.data),
    staleTime: 2 * 60_000,
    gcTime:   10 * 60_000,
  });

  const { data: papers, isLoading: papersLoading } = useQuery({
    queryKey: ['papers', 'home'],
    queryFn: () => api.get('/papers/', { params: { page_size: 10, ordering: '-fetched_at' } }).then(r => r.data),
    staleTime: 2 * 60_000,
    gcTime:   10 * 60_000,
  });

  const { data: videosData, isLoading: videosLoading } = useQuery({
    queryKey: ['videos', 'home'],
    queryFn: () => api.get('/videos/', { params: { page_size: 12, ordering: '-fetched_at' } }).then(r => r.data),
    staleTime: 2 * 60_000,
    gcTime:   10 * 60_000,
  });

  const { data: tweetsData, isLoading: tweetsLoading } = useQuery({
    queryKey: ['tweets', 'home'],
    queryFn: () => api.get('/tweets/', { params: { page_size: 12, ordering: '-scraped_at' } }).then(r => r.data),
    staleTime: 2 * 60_000,
    gcTime:   10 * 60_000,
  });

  // Derive counts from content queries — no extra network requests needed
  const articleCount = articles;
  const paperCount   = papers;
  const repoCount    = repos;
  const videoCount   = videosData;
  const tweetCount   = tweetsData;

  const extractList = (d: any, n: number) =>
    Array.isArray(d?.results) ? d.results.slice(0, n)
    : Array.isArray(d?.data) ? d.data.slice(0, n)
    : Array.isArray(d) ? (d as any[]).slice(0, n) : [];

  const trendingArticles = extractList(articles, 12);
  const trendingRepos    = extractList(repos, 3);
  const trendingPapers   = extractList(papers, 10);
  const trendingVideos   = extractList(videosData, 12);
  const trendingTweets   = extractList(tweetsData, 12);

  return (
    <div className="flex-1 overflow-y-auto">
      <VideoPlayerModal video={playingVideo} onClose={() => setPlayingVideo(null)} />
      <div className="pb-10">

        {/* ── Interest Profile Builder (first-run prompt) ─────────── */}
        {showProfileBuilder && <InterestProfileBuilder onClose={() => setShowProfileBuilder(false)} />}

        {/* ── Hero Banner ──────────────────────────────────────────── */}
        <div className="relative bg-gradient-to-br from-indigo-50 via-white to-violet-50 dark:from-slate-900 dark:via-indigo-950/80 dark:to-slate-900 px-4 sm:px-6 pt-6 sm:pt-8 pb-10 sm:pb-12 overflow-hidden border-b border-indigo-100 dark:border-transparent">
          <div className="absolute inset-0 bg-grid-pattern opacity-10 dark:opacity-20" />
          <div className="absolute top-0 right-0 w-80 h-80 bg-indigo-200/40 dark:bg-indigo-600/20 rounded-full blur-3xl -translate-y-1/2 translate-x-1/4" />
          <div className="absolute bottom-0 left-1/3 w-56 h-56 bg-violet-200/30 dark:bg-cyan-600/15 rounded-full blur-3xl translate-y-1/2" />
          <div className="relative">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-100 dark:bg-indigo-500/20 border border-indigo-200 dark:border-indigo-500/30 text-indigo-600 dark:text-indigo-300 text-xs font-semibold mb-4">
              <Zap size={10} className="fill-indigo-500 text-indigo-500 dark:fill-indigo-400 dark:text-indigo-400" />
              AI-Powered Tech Intelligence
            </span>
            <h1 className="text-3xl md:text-5xl font-black text-slate-900 dark:text-white mb-2 tracking-tight leading-tight">
              Welcome to <span className="gradient-text">SYNAPSE</span>
            </h1>
            <p className="text-slate-500 dark:text-slate-400 text-sm sm:text-base max-w-lg mb-5">
              Your personal AI-curated feed of articles, papers, repos, and videos — all searchable and summarized.
            </p>
            {/* ── Action row: CatchMeUp + Watchlist ─────────────────── */}
            <div className="flex items-center gap-3 flex-wrap">
              <CatchMeUp />
              <TopicWatchlist />
              <Link href="/analytics" className="flex items-center gap-2 px-4 py-2.5 bg-white/80 dark:bg-slate-800/80 backdrop-blur-sm border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 rounded-xl text-sm font-medium hover:border-indigo-400 transition-colors shadow-sm">
                <BarChart3 size={15} className="text-emerald-500" /> Analytics
              </Link>
            </div>
          </div>
        </div>

        <div className="px-4 sm:px-6 space-y-10 mt-6">

          {/* ── TASK-305-F1: Today's Brief ────────────────────────── */}
          <TodayBriefCard />

          {/* ── Stats Row ─────────────────────────────────────────── */}
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
            <StatCard icon={BarChart3} label="Articles"      value={articleCount?.meta?.total ?? 0} gradient="bg-gradient-to-br from-indigo-500 to-indigo-700"  href="/feed"     />
            <StatCard icon={BookOpen}  label="Papers"        value={paperCount?.meta?.total ?? 0}   gradient="bg-gradient-to-br from-violet-500 to-violet-700"   href="/research" />
            <StatCard icon={GitBranch} label="Repositories"  value={repoCount?.meta?.total ?? 0}    gradient="bg-gradient-to-br from-emerald-500 to-emerald-700" href="/github"   />
            <StatCard icon={Youtube}   label="Videos"        value={videoCount?.meta?.total ?? 0}   gradient="bg-gradient-to-br from-red-500 to-red-700"         href="/videos"   />
            <StatCard icon={Twitter}   label="Tweets"        value={tweetCount?.meta?.total ?? 0}   gradient="bg-gradient-to-br from-sky-500 to-sky-700"         href="/tweets"   />
          </div>

          {/* ── Latest Articles + GitHub ───────────────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-2">
              {/* ── Top Trends strip ── */}
              <TrendStrip />

              <SectionHeader title="Latest from Tech Feed" subtitle="Curated articles from around the web" href="/feed" />
              {articlesLoading ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {Array.from({ length: 6 }).map((_, i) => <ArticleSkeleton key={i} />)}
                </div>
              ) : trendingArticles.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {trendingArticles.slice(0, 6).map((article: any) => (
                    <ArticleCard key={article.id} article={article} />
                  ))}
                </div>
              ) : (
                <div className="text-center py-12 bg-slate-50 dark:bg-slate-800/40 rounded-2xl border border-slate-200 dark:border-slate-700/60">
                  <p className="text-slate-500 dark:text-slate-400">No articles yet</p>
                </div>
              )}
            </div>

            <div className="space-y-6">
              <SectionHeader title="Trending on GitHub" subtitle="Hot repos today" href="/github" />
              {reposLoading ? (
                <div className="space-y-4">
                  {Array.from({ length: 3 }).map((_, i) => <RepositorySkeleton key={i} />)}
                </div>
              ) : trendingRepos.length > 0 ? (
                <div className="space-y-4">
                  {trendingRepos.map((repo: any) => (
                    <RepositoryCard key={repo.id} repo={repo} />
                  ))}
                </div>
              ) : (
                <div className="text-center py-12 bg-slate-50 dark:bg-slate-800/40 rounded-2xl border border-slate-200 dark:border-slate-700/60">
                  <p className="text-slate-500 dark:text-slate-400">No repos yet</p>
                </div>
              )}

              {/* ── Reading Goals Widget ─────────────────────────────── */}
              <ReadingGoals />

              {/* ── What My Network Is Reading ───────────────────────── */}
              <div className="bg-white dark:bg-slate-800 rounded-2xl border border-slate-200 dark:border-slate-700 p-4">
                <NetworkReading />
              </div>
            </div>
          </div>

          {/* ── Videos ───────────────────────────────────────────── */}
          <div>
            <SectionHeader title="Latest Videos" subtitle="AI-curated tech & ML videos" href="/videos" />
            {videosLoading ? (
              <HorizontalScroller cardWidth={280}>
                {Array.from({ length: 6 }).map((_, i) => (
                  <div key={i} className="bg-slate-100 dark:bg-slate-800 rounded-xl animate-pulse" style={{ aspectRatio: '16/9' }} />
                ))}
              </HorizontalScroller>
            ) : trendingVideos.length > 0 ? (
              <HorizontalScroller cardWidth={280}>
                {trendingVideos.map((video: any) => (
                  <VideoCard key={video.id} video={video} onPlay={(v) => setPlayingVideo(v)} />
                ))}
              </HorizontalScroller>
            ) : (
              <div className="text-center py-12 bg-slate-50 dark:bg-slate-800/40 rounded-2xl border border-slate-200 dark:border-slate-700/60">
                <p className="text-slate-500 dark:text-slate-400">No videos yet</p>
              </div>
            )}
          </div>

          {/* ── Research Papers ───────────────────────────────────── */}
          <div>
            <SectionHeader title="Latest Research Papers" subtitle="New papers from arXiv (cs.AI, cs.LG, cs.CL)" href="/research" />
            {papersLoading ? (
              <HorizontalScroller cardWidth={340}>
                {Array.from({ length: 4 }).map((_, i) => <PaperSkeleton key={i} />)}
              </HorizontalScroller>
            ) : trendingPapers.length > 0 ? (
              <HorizontalScroller cardWidth={340}>
                {trendingPapers.map((paper: any) => (
                  <PaperCard key={paper.id} paper={paper} />
                ))}
              </HorizontalScroller>
            ) : (
              <div className="text-center py-12 bg-slate-50 dark:bg-slate-800/40 rounded-2xl border border-slate-200 dark:border-slate-700/60">
                <p className="text-slate-500 dark:text-slate-400">No papers yet</p>
              </div>
            )}
          </div>

          {/* ── X/Tweets ───────────────────────────────────────────── */}
          <div>
            <SectionHeader title="Latest from X (Twitter)" subtitle="Curated tweets on AI, programming & tech" href="/tweets" />
            {tweetsLoading ? (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div key={i} className="bg-slate-100 dark:bg-slate-800 rounded-xl animate-pulse h-48" />
                ))}
              </div>
            ) : trendingTweets.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {trendingTweets.map((tweet: any) => (
                  <TweetCard key={tweet.id} tweet={tweet} />
                ))}
              </div>
            ) : (
              <div className="text-center py-12 bg-slate-50 dark:bg-slate-800/40 rounded-2xl border border-slate-200 dark:border-slate-700/60">
                <p className="text-slate-500 dark:text-slate-400">No tweets yet</p>
              </div>
            )}
          </div>

          {/* ── Reading Activity Heatmap ─────────────────────────── */}
          <ActivityHeatmap />

        </div>
      </div>
    </div>
  );
}
