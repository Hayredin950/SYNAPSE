'use client';

import React, { memo, useCallback } from 'react';
import { Star, GitFork, AlertCircle, TrendingUp } from 'lucide-react';
import { Repository } from '@/types';
import { formatNumber, formatRelativeTime, cn } from '@/utils/helpers';
import { BookmarkButton } from '@/components/BookmarkButton';

interface RepositoryCardProps {
  repo: Repository;
  onBookmark?: (id: string) => void;
}

const languageColors: Record<string, string> = {
  python:     'bg-blue-500',
  javascript: 'bg-yellow-400',
  typescript: 'bg-blue-600',
  rust:       'bg-orange-700',
  go:         'bg-cyan-500',
  java:       'bg-orange-600',
  cpp:        'bg-blue-700',
  c:          'bg-slate-600',
  ruby:       'bg-red-600',
  php:        'bg-purple-600',
};

const getLanguageColor = (language?: string) => {
  if (!language) return 'bg-slate-400';
  return languageColors[language.toLowerCase()] || 'bg-emerald-500';
};

export const RepositoryCard = memo(function RepositoryCard({ repo }: RepositoryCardProps) {
  const handleCardClick = useCallback(() => window.open(repo.url, '_blank'), [repo.url]);

  return (
    <div
      onClick={handleCardClick}
      style={{ contain: 'layout style' }}
      className={cn(
        'group relative bg-white dark:bg-slate-800/90 rounded-2xl border border-slate-200 dark:border-slate-700/60',
        'p-4 sm:p-5 cursor-pointer transition-all duration-200 overflow-hidden',
        'hover:shadow-xl hover:shadow-emerald-500/10 hover:border-emerald-400/40 dark:hover:border-emerald-500/40',
        'hover:-translate-y-0.5 active:scale-[0.99]'
      )}
    >
      {/* Accent bar */}
      <div className="absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r from-emerald-500 via-cyan-500 to-teal-500 opacity-0 group-hover:opacity-100 transition-opacity rounded-t-2xl" />

      {/* Top row: icon + language + trending badge */}
      <div className="flex items-center justify-between gap-2 mb-3 flex-wrap">
        <div className="flex items-center gap-2 min-w-0 shrink">
          <span className="text-base shrink-0">🐙</span>
          {repo.language && (
            <div className="flex items-center gap-1.5 shrink-0">
              <div className={cn('w-2.5 h-2.5 rounded-full shrink-0', getLanguageColor(repo.language))} />
              <span className="text-xs font-semibold text-slate-600 dark:text-slate-300 whitespace-nowrap">
                {repo.language}
              </span>
            </div>
          )}
        </div>
        {repo.is_trending && (
          <span className="flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-full bg-rose-100 dark:bg-rose-900/30 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-700/40 shrink-0 whitespace-nowrap">
            <TrendingUp size={10} />
            Trending
          </span>
        )}
      </div>

      {/* Repo full name */}
      <h3 className="font-bold text-sm sm:text-base text-slate-900 dark:text-white mb-2 leading-snug group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors break-words line-clamp-2">
        {repo.full_name}
      </h3>

      {/* Description */}
      {repo.description && (
        <p className="line-clamp-2 text-sm text-slate-600 dark:text-slate-400 mb-3 leading-relaxed">
          {repo.description}
        </p>
      )}

      {/* Stats row */}
      <div className="flex items-center flex-wrap gap-x-3 gap-y-1 mb-3 text-xs text-slate-500 dark:text-slate-400">
        <span className="flex items-center gap-1 whitespace-nowrap">
          <Star size={13} className="fill-amber-400 text-amber-400" />
          <span className="font-medium text-slate-700 dark:text-slate-300">{formatNumber(repo.stars)}</span>
        </span>
        <span className="flex items-center gap-1 whitespace-nowrap">
          <GitFork size={13} />
          {formatNumber(repo.forks)}
        </span>
        <span className="flex items-center gap-1 whitespace-nowrap">
          <AlertCircle size={13} />
          {formatNumber(repo.open_issues)}
        </span>
      </div>

      {/* Topics */}
      {repo.topics && repo.topics.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {repo.topics.slice(0, 4).map((topic) => (
            <span
              key={topic}
              className="text-xs px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-400 font-medium truncate max-w-[90px]"
            >
              {topic}
            </span>
          ))}
        </div>
      )}

      {/* Bottom row */}
      <div className="flex items-center justify-between gap-2 pt-2.5 border-t border-slate-100 dark:border-slate-700/50 flex-wrap">
        <div className="flex flex-col gap-0.5 min-w-0 shrink">
          {(repo.owner || repo.owner_name) && (
            <span className="text-xs text-slate-500 dark:text-slate-400 truncate max-w-[120px]">
              by {repo.owner || repo.owner_name}
            </span>
          )}
          <span className="text-xs text-slate-400 dark:text-slate-500 whitespace-nowrap">
            {formatRelativeTime(repo.scraped_at || null)}
          </span>
        </div>
        <BookmarkButton contentType="repository" objectId={repo.id} size={15} />
      </div>
    </div>
  );
});
