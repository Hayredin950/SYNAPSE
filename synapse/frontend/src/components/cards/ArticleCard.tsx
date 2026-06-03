'use client';

import React, { memo, useCallback, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { MessageSquare, Clock, Sparkles, BookOpen } from 'lucide-react';
import { useReaderStore } from '@/store/readerStore';
import { Article } from '@/types';
import { formatRelativeTime, cn } from '@/utils/helpers';
import { BookmarkButton } from '@/components/BookmarkButton';

const SummaryText = memo(function SummaryText({ text }: { text: string }) {
  const [expanded, setExpanded] = React.useState(false);
  if (!text) return null;
  const isLong = text.split(' ').length > 40;
  return (
    <div>
      <p className={cn('text-sm text-slate-600 dark:text-slate-400 leading-relaxed', !expanded && 'line-clamp-3')}>
        {text}
      </p>
      {isLong && (
        <button
          type="button"
          className="mt-1 text-xs text-indigo-600 dark:text-indigo-400 hover:underline font-medium"
          onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
        >
          {expanded ? 'Show less' : 'Read more'}
        </button>
      )}
    </div>
  );
});

interface ArticleCardProps {
  article: Article;
  onBookmark?: (id: string) => void;
}

const getSourceColor = (sourceType: string) => {
  const colors: Record<string, string> = {
    hackernews: 'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300 border border-orange-200 dark:border-orange-800/40',
    reddit:     'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-800/40',
    github:     'bg-slate-100 dark:bg-slate-700/60 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-600/40',
    blog:       'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800/40',
    news:       'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800/40',
  };
  return colors[sourceType] || 'bg-slate-100 dark:bg-slate-700/60 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-600/40';
};

const getTagColor = (index: number) => {
  const colors = [
    'bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300',
    'bg-cyan-100 dark:bg-cyan-900/30 text-cyan-700 dark:text-cyan-300',
    'bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300',
  ];
  return colors[index % colors.length];
};

export const ArticleCard = memo(function ArticleCard({ article }: ArticleCardProps) {
  const router = useRouter();
  const openReader = useReaderStore(s => s.open);

  const handleCardClick = useCallback(() => window.open(article.url, '_blank'), [article.url]);

  const handleQuickRead = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    openReader({ ...article, content_type: 'article' });
  }, [article, openReader]);

  const handleAskAI = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    const q = encodeURIComponent(`Explain this article: "${article.title}"`);
    router.push(`/chat?q=${q}`);
  }, [article.title, router]);

  const readingTime = useMemo(() => {
    const wordCount = article.summary?.split(' ').length || article.title.split(' ').length;
    return Math.max(1, Math.ceil(wordCount / 200));
  }, [article.summary, article.title]);

  return (
    <div
      onClick={handleCardClick}
      style={{ contain: 'layout style' }}
      className={cn(
        'group relative bg-white dark:bg-slate-800/90 rounded-2xl border border-slate-200 dark:border-slate-700/60',
        'p-4 sm:p-5 cursor-pointer transition-all duration-200 overflow-hidden',
        'hover:shadow-xl hover:shadow-indigo-500/10 hover:border-indigo-400/50 dark:hover:border-indigo-500/50',
        'hover:-translate-y-0.5 active:scale-[0.99]'
      )}
    >
      {/* Subtle gradient accent top bar */}
      <div className="absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r from-indigo-500 via-violet-500 to-purple-500 opacity-0 group-hover:opacity-100 transition-opacity rounded-t-2xl" />

      {/* Top row: timestamp only */}
      <div className="flex items-center justify-start gap-2 mb-3">
        <span className="flex items-center gap-1 text-xs text-slate-400 dark:text-slate-500 whitespace-nowrap shrink-0">
          <Clock size={11} />
          {formatRelativeTime(article.scraped_at)}
        </span>
      </div>

      {/* Title */}
      <h3 className="line-clamp-2 font-semibold text-sm sm:text-base text-slate-900 dark:text-white mb-2.5 leading-snug group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
        {article.title}
      </h3>

      {/* Summary */}
      {article.summary && article.summary !== '__failed__' ? (
        <div className="mb-3">
          <div className="flex items-center gap-1.5 mb-1.5">
            <span className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-700/40">
              <Sparkles size={10} />
              AI Summary
            </span>
          </div>
          <SummaryText text={article.summary} />
        </div>
      ) : !article.summary || article.summary === '' ? (
        <div className="mb-3">
          {article.excerpt ? (
            <p className="line-clamp-2 text-sm text-slate-600 dark:text-slate-400 mb-1.5 leading-relaxed">
              {article.excerpt}
            </p>
          ) : (article.tags?.length > 0 || article.topic) ? (
            <p className="line-clamp-2 text-sm text-slate-500 dark:text-slate-400 mb-1.5 leading-relaxed">
              {[
                article.topic ? `A ${article.topic} article` : null,
                article.tags?.length > 0 ? `covering ${article.tags.slice(0, 3).join(', ')}` : null,
              ].filter(Boolean).join(' ')}.
            </p>
          ) : null}
          {!article.excerpt && (
            <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-700/60 text-slate-400 dark:text-slate-500">
              <svg className="w-2.5 h-2.5 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              AI summarizing…
            </span>
          )}
        </div>
      ) : null}

      {/* Tags */}
      {(article.tags?.length > 0 || article.topic) && (
        <div className="flex flex-wrap gap-1 mb-3">
          {article.tags?.slice(0, 3).map((tag, idx) => (
            <span key={tag} className={cn('text-xs px-2 py-0.5 rounded-full font-medium truncate max-w-[100px]', getTagColor(idx))}>
              {tag}
            </span>
          ))}
          {article.topic && !article.tags?.includes(article.topic) && (
            <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-400 truncate max-w-[100px]">
              {article.topic}
            </span>
          )}
        </div>
      )}

      {/* Bottom row: Quick Read + Ask AI + Bookmark */}
      <div className="flex items-center justify-between gap-1 pt-2.5 border-t border-slate-100 dark:border-slate-700/50">
        <button
          onClick={handleQuickRead}
          title="Open reader view"
          className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-semibold text-violet-600 dark:text-violet-400 hover:text-white hover:bg-violet-600 transition-all border border-violet-400/30 hover:border-violet-500 whitespace-nowrap"
        >
          <BookOpen size={11} />
          <span className="hidden xs:inline">Read</span>
        </button>
        <div className="flex items-center gap-1">
          <button
            onClick={handleAskAI}
            title="Ask AI about this article"
            className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-semibold text-indigo-500 dark:text-indigo-400 hover:text-white hover:bg-indigo-600 transition-all border border-indigo-400/30 hover:border-indigo-500 whitespace-nowrap"
          >
            <MessageSquare size={11} />
            <span className="hidden xs:inline">Ask AI</span>
          </button>
          <BookmarkButton contentType="article" objectId={article.id} size={15} />
        </div>
      </div>
    </div>
  );
});
