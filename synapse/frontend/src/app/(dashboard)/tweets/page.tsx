'use client';

import React, { useState, useCallback } from 'react';
import { Twitter, Search, RefreshCw, ChevronDown } from 'lucide-react';
import { api } from '@/utils/api';
import { TweetCard } from '@/components/cards';
import { cn } from '@/utils/helpers';
import { useInfiniteScroll } from '@/hooks/useInfiniteScroll';
import { ScrollSentinel } from '@/components/ui/ScrollSentinel';

const TOPICS = ['All', 'AI', 'Web Dev', 'Security', 'Cloud', 'Research', 'Programming', 'Tech'];

const SORT_OPTIONS = [
  { label: '🕐 Latest', value: '-posted_at' },
  { label: '🔥 Trending', value: '-trending_score' },
  { label: '❤️ Most Liked', value: '-like_count' },
  { label: '🔁 Most Retweeted', value: '-retweet_count' },
];

const TOP_ACCOUNTS = [
  { handle: 'OpenAI', label: 'OpenAI' },
  { handle: 'GoogleAI', label: 'Google AI' },
  { handle: 'AnthropicAI', label: 'Anthropic' },
  { handle: 'elonmusk', label: 'Elon Musk' },
  { handle: 'ylecun', label: 'Yann LeCun' },
  { handle: 'kaboroevich', label: 'Karpathy' },
];

export default function TweetsPage() {
  const [selectedTopic, setSelectedTopic] = useState('All');
  const [sortBy, setSortBy] = useState('-posted_at');
  const [showSortDropdown, setShowSortDropdown] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const topicParam = selectedTopic === 'All' ? undefined : selectedTopic;

  const { items: tweets, sentinelRef, isFetchingNextPage, isLoading, hasNextPage, total: totalCount, reset } =
    useInfiniteScroll<any>({
      fetchPage: useCallback(async (page: number) => {
        const r = await api.get('/tweets/', {
          params: {
            page,
            page_size: 20,
            ordering: sortBy,
            ...(topicParam ? { topic: topicParam } : {}),
            ...(searchQuery ? { q: searchQuery } : {}),
          },
        });
        const d = r.data;
        const items: any[] = Array.isArray(d?.data) ? d.data : Array.isArray(d?.results) ? d.results : Array.isArray(d) ? d : [];
        const total = d?.meta?.total ?? d?.count ?? items.length;
        return { items, total };
      }, [topicParam, sortBy, searchQuery]),
      deps: [topicParam, sortBy, searchQuery],
    });

  const currentSortLabel = SORT_OPTIONS.find(o => o.value === sortBy)?.label || 'Latest';

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="pb-8">
        {/* ── Compact header — one row ── */}
        <div className="px-4 sm:px-6 pt-4 pb-3 border-b border-slate-200 dark:border-slate-800/60 bg-white/80 dark:bg-slate-950/80 backdrop-blur-sm sticky top-0 z-10">
          <div className="flex items-center gap-3">
            {/* Icon + title */}
            <div className="flex items-center gap-2 shrink-0">
              <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-sky-400 to-blue-600 flex items-center justify-center shadow-sm">
                <Twitter size={13} className="text-white" />
              </div>
              <div className="hidden sm:block">
                <h1 className="text-sm font-bold text-slate-900 dark:text-white leading-none">X Feed</h1>
                {totalCount > 0 && <p className="text-[10px] text-slate-400 mt-0.5">{totalCount.toLocaleString()} tweets</p>}
              </div>
            </div>

            {/* Search — fills remaining space */}
            <div className="relative flex-1 min-w-0">
              <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search tweets…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-8 pr-3 py-2 text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/60 text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-500/30 focus:border-sky-500/50 transition-all"
              />
            </div>

            {/* Refresh */}
            <button onClick={reset} disabled={isFetchingNextPage}
              className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors disabled:opacity-40">
              <RefreshCw size={11} className={isFetchingNextPage ? 'animate-spin' : ''} />
              <span>Refresh</span>
            </button>
          </div>
        </div>

        <div className="px-4 sm:px-6 pt-4 sm:pt-5 space-y-4 sm:space-y-5">
          {/* Filters row */}
          <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3">
            {/* Topic pills */}
            <div className="flex gap-1.5 sm:gap-2 overflow-x-auto scrollbar-hide pb-0.5 flex-1">
              {TOPICS.map((topic) => (
                <button
                  key={topic}
                  onClick={() => { setSelectedTopic(topic); }}
                  className={cn(
                    'px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-full text-xs sm:text-sm font-semibold whitespace-nowrap transition-all flex-shrink-0',
                    selectedTopic === topic
                      ? 'bg-sky-500 text-white shadow-sm'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
                  )}
                >
                  {topic}
                </button>
              ))}
            </div>

            {/* Sort dropdown */}
            <div className="relative flex-shrink-0">
              <button
                onClick={() => setShowSortDropdown(!showSortDropdown)}
                className="px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-xl text-xs sm:text-sm font-semibold flex items-center gap-1 sm:gap-1.5 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-all whitespace-nowrap"
              >
                {currentSortLabel}
                <ChevronDown size={13} className={cn('transition-transform', showSortDropdown && 'rotate-180')} />
              </button>
              {showSortDropdown && (
                <div className="absolute top-full mt-1 right-0 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl shadow-xl z-20 min-w-[140px] sm:min-w-[160px] overflow-hidden">
                  {SORT_OPTIONS.map((option) => (
                    <button
                      key={option.value}
                      onClick={() => { setSortBy(option.value); setShowSortDropdown(false); }}
                      className={cn(
                        'w-full text-left px-3 sm:px-4 py-2 sm:py-2.5 text-xs sm:text-sm transition-colors',
                        sortBy === option.value
                          ? 'bg-sky-50 dark:bg-sky-900/30 text-sky-700 dark:text-sky-300 font-semibold'
                          : 'text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700/50'
                      )}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Notable accounts */}
          <div className="flex items-center gap-2 overflow-x-auto scrollbar-hide">
            <span className="text-xs text-slate-500 dark:text-slate-400 font-medium shrink-0">Follow:</span>
            {TOP_ACCOUNTS.map((acct) => (
              <a
                key={acct.handle}
                href={`https://x.com/${acct.handle}`}
                target="_blank"
                rel="noopener noreferrer"
                className="px-2.5 py-1 rounded-full text-xs font-medium bg-sky-50 dark:bg-sky-900/20 text-sky-600 dark:text-sky-400 border border-sky-200 dark:border-sky-800/40 hover:bg-sky-100 dark:hover:bg-sky-900/40 transition-colors whitespace-nowrap shrink-0"
              >
                @{acct.handle}
              </a>
            ))}
          </div>

          {/* Content */}
          {isLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="bg-white dark:bg-slate-800/90 rounded-2xl border border-slate-200 dark:border-slate-700/60 p-5 animate-pulse">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 rounded-full bg-slate-200 dark:bg-slate-700" />
                    <div className="flex-1">
                      <div className="h-4 w-24 bg-slate-200 dark:bg-slate-700 rounded mb-1" />
                      <div className="h-3 w-16 bg-slate-200 dark:bg-slate-700 rounded" />
                    </div>
                  </div>
                  <div className="space-y-2 mb-3">
                    <div className="h-3 w-full bg-slate-200 dark:bg-slate-700 rounded" />
                    <div className="h-3 w-3/4 bg-slate-200 dark:bg-slate-700 rounded" />
                  </div>
                  <div className="flex gap-4 pt-3 border-t border-slate-100 dark:border-slate-700/50">
                    <div className="h-3 w-8 bg-slate-200 dark:bg-slate-700 rounded" />
                    <div className="h-3 w-8 bg-slate-200 dark:bg-slate-700 rounded" />
                    <div className="h-3 w-8 bg-slate-200 dark:bg-slate-700 rounded" />
                  </div>
                </div>
              ))}
            </div>
          ) : tweets.length > 0 ? (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {tweets.map((tweet: any) => (
                  <TweetCard key={tweet.id} tweet={tweet} />
                ))}
              </div>
              <ScrollSentinel
                sentinelRef={sentinelRef}
                isFetchingNextPage={isFetchingNextPage}
                hasNextPage={hasNextPage}
                onRetry={reset}
                endLabel={`All ${totalCount} tweets loaded ✨`}
              />
            </>
          ) : (
            <div className="text-center py-16 bg-white dark:bg-slate-800/40 rounded-2xl border border-slate-200 dark:border-slate-700/60">
              <Twitter size={48} className="mx-auto text-slate-300 dark:text-slate-600 mb-3" />
              <p className="text-slate-600 dark:text-slate-400 font-medium">No tweets found</p>
              <p className="text-slate-400 dark:text-slate-500 text-sm mt-1">
                {searchQuery ? 'Try a different search term' : 'Run the X/Twitter scraper to populate this feed'}
              </p>
              <button
                onClick={() => { setSelectedTopic('All'); setSearchQuery(''); }}
                className="mt-3 text-sm text-sky-500 hover:text-sky-600 font-medium"
              >
                Clear filters
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
