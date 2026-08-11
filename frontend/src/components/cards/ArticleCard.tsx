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

// Structure-preserving excerpt: the first ~100 words of the article body as
// markdown-ish text (headings, quotes, lists on their own lines). No AI calls.
const ExcerptText = memo(function ExcerptText({ text }: { text: string }) {
  const [expanded, setExpanded] = React.useState(false);
  if (!text) return null;
  const isLong = text.split('\n').length > 5 || text.split(' ').length > 45;
  return (
    <div>
      <p className={cn(
        'text-sm text-slate-600 dark:text-slate-400 leading-relaxed whitespace-pre-line',
        !expanded && 'line-clamp-4'
      )}>
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

const TOPIC_STYLES: Record<string, string> = {
  'AI':          'bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300 border-indigo-200 dark:border-indigo-700/40',
  'Web Dev':     'bg-cyan-100 dark:bg-cyan-900/40 text-cyan-700 dark:text-cyan-300 border-cyan-200 dark:border-cyan-700/40',
  'Security':    'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300 border-red-200 dark:border-red-700/40',
  'Cloud':       'bg-sky-100 dark:bg-sky-900/40 text-sky-700 dark:text-sky-300 border-sky-200 dark:border-sky-700/40',
  'DevOps':      'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-700/40',
  'Research':    'bg-violet-100 dark:bg-violet-900/40 text-violet-700 dark:text-violet-300 border-violet-200 dark:border-violet-700/40',
  'Programming': 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-700/40',
  'Open Source': 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300 border-green-200 dark:border-green-700/40',
  default:       'bg-slate-100 dark:bg-slate-700/60 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-600/50',
};

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

      {/* Top row: timestamp + meaningful topic badge */}
      <div className="flex items-center justify-start gap-2 mb-3 flex-wrap">
        <span className="flex items-center gap-1 text-xs text-slate-400 dark:text-slate-500 whitespace-nowrap shrink-0">
          <Clock size={11} />
          {formatRelativeTime(article.scraped_at)}
        </span>
        {article.topic && article.topic !== 'tech' && article.topic !== 'Technology' && (
          <span className={cn(
            'text-[10px] px-2 py-0.5 rounded-full font-semibold border whitespace-nowrap',
            TOPIC_STYLES[article.topic] || TOPIC_STYLES.default
          )}>
            {article.topic}
          </span>
        )}
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
      ) : article.excerpt ? (
        <div className="mb-3">
          <ExcerptText text={article.excerpt} />
        </div>
      ) : article.topic ? (
        <p className="line-clamp-2 text-sm text-slate-500 dark:text-slate-400 mb-1.5 leading-relaxed">
          A {article.topic} article.
        </p>
      ) : null}

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
