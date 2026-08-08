'use client';

import React, { memo, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  MessageSquare, Heart, Repeat2, Eye, Bookmark,
  Clock, ExternalLink, BadgeCheck,
} from 'lucide-react';
import { Tweet } from '@/types';
import { formatRelativeTime, formatNumber, cn } from '@/utils/helpers';
import { BookmarkButton } from '@/components/BookmarkButton';

const getTopicColor = (topic: string) => {
  const colors: Record<string, string> = {
    'AI':         'bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300 border border-violet-200 dark:border-violet-800/40',
    'Web Dev':    'bg-cyan-100 dark:bg-cyan-900/30 text-cyan-700 dark:text-cyan-300 border border-cyan-200 dark:border-cyan-800/40',
    'Security':   'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-800/40',
    'Cloud':      'bg-sky-100 dark:bg-sky-900/30 text-sky-700 dark:text-sky-300 border border-sky-200 dark:border-sky-800/40',
    'Research':   'bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800/40',
    'Programming':'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800/40',
    'Tech':       'bg-slate-100 dark:bg-slate-700/60 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-600/40',
  };
  return colors[topic] || colors['Tech'];
};

interface TweetCardProps {
  tweet: Tweet;
}

export const TweetCard = memo(function TweetCard({ tweet }: TweetCardProps) {
  const router = useRouter();

  const handleCardClick = useCallback(() => {
    if (tweet.url) window.open(tweet.url, '_blank');
  }, [tweet.url]);

  const handleAskAI = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    const q = encodeURIComponent(`Explain this tweet: "${tweet.text.slice(0, 200)}"`);
    router.push(`/chat?q=${q}`);
  }, [tweet.text, router]);

  const handleProfileClick = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    window.open(`https://x.com/${tweet.author_username}`, '_blank');
  }, [tweet.author_username]);

  // Highlight hashtags and mentions in the tweet text
  const renderText = useCallback((text: string) => {
    return text.split(/(\s+)/).map((word, i) => {
      if (word.startsWith('#') || word.startsWith('@')) {
        return (
          <span key={i} className="text-sky-500 dark:text-sky-400 font-medium">
            {word}
          </span>
        );
      }
      // URLs
      if (word.startsWith('http://') || word.startsWith('https://')) {
        return (
          <a
            key={i}
            href={word}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="text-sky-500 dark:text-sky-400 hover:underline"
          >
            {word.length > 40 ? word.slice(0, 40) + '...' : word}
          </a>
        );
      }
      return word + ' ';
    });
  }, []);

  return (
    <div
      onClick={handleCardClick}
      style={{ contain: 'layout style' }}
      className={cn(
        'group relative bg-white dark:bg-slate-800/90 rounded-2xl border border-slate-200 dark:border-slate-700/60',
        'p-4 sm:p-5 cursor-pointer transition-all duration-200 overflow-hidden',
        'hover:shadow-xl hover:shadow-sky-500/10 hover:border-sky-400/50 dark:hover:border-sky-500/50',
        'hover:-translate-y-0.5 active:scale-[0.99]'
      )}
    >
      {/* Subtle gradient accent top bar */}
      <div className="absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r from-sky-500 via-blue-500 to-indigo-500 opacity-0 group-hover:opacity-100 transition-opacity rounded-t-2xl" />

      {/* Author row */}
      <div className="flex items-center gap-3 mb-3">
        <button onClick={handleProfileClick} className="shrink-0">
          {tweet.author_profile_image ? (
            <img
              src={tweet.author_profile_image.replace('_normal', '_200x200')}
              alt={tweet.author_username}
              className="w-10 h-10 rounded-full object-cover ring-2 ring-slate-100 dark:ring-slate-700"
            />
          ) : (
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-sky-400 to-blue-600 flex items-center justify-center text-white font-bold text-sm">
              {tweet.author_username.charAt(0).toUpperCase()}
            </div>
          )}
        </button>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <button
              onClick={handleProfileClick}
              className="font-semibold text-sm text-slate-900 dark:text-white truncate hover:underline"
            >
              {tweet.author_display_name || tweet.author_username}
            </button>
            {tweet.author_verified && (
              <BadgeCheck size={14} className="text-sky-500 shrink-0" />
            )}
          </div>
          <div className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
            <span>@{tweet.author_username}</span>
            {tweet.author_followers > 0 && (
              <>
                <span>·</span>
                <span>{formatNumber(tweet.author_followers)} followers</span>
              </>
            )}
          </div>
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          {tweet.topic && (
            <span className={cn('text-xs font-semibold px-2 py-0.5 rounded-full', getTopicColor(tweet.topic))}>
              {tweet.topic}
            </span>
          )}
          <span className="flex items-center gap-1 text-xs text-slate-400 dark:text-slate-500 whitespace-nowrap">
            <Clock size={11} />
            {formatRelativeTime(tweet.posted_at || tweet.scraped_at)}
          </span>
        </div>
      </div>

      {/* Tweet text */}
      <div className="mb-3">
        <p className="text-sm sm:text-base text-slate-800 dark:text-slate-200 leading-relaxed whitespace-pre-wrap break-words">
          {renderText(tweet.text)}
        </p>
      </div>

      {/* Media preview — normalize Nitter proxy URLs to Twitter CDN */}
      {tweet.media_urls.length > 0 && (() => {
        // Convert Nitter proxy URLs to direct Twitter CDN URLs
        const rawUrl = tweet.media_urls[0];
        let imgSrc = rawUrl;

        // Pattern: nitter.*/pic/media%2F{id}.jpg → pbs.twimg.com/media/{id}
        const nitterMatch = rawUrl.match(/\/pic\/media%2F([^?&%]+)/i);
        if (nitterMatch) {
          const mediaId = decodeURIComponent(nitterMatch[1]);
          imgSrc = `https://pbs.twimg.com/media/${mediaId}`;
        }

        return (
          <div className="mb-3 rounded-xl overflow-hidden border border-slate-200 dark:border-slate-700">
            <img
              src={imgSrc}
              alt="Tweet media"
              className="w-full max-h-48 object-cover"
              loading="lazy"
              onError={(e) => {
                const img = e.target as HTMLImageElement;
                // Try original URL as fallback if CDN failed
                if (img.src !== rawUrl && !img.dataset.triedOriginal) {
                  img.dataset.triedOriginal = '1';
                  img.src = rawUrl;
                } else {
                  // Both failed — hide container
                  const container = img.parentElement;
                  if (container) container.style.display = 'none';
                }
              }}
            />
          </div>
        );
      })()}

      {/* Hashtags */}
      {tweet.hashtags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {tweet.hashtags.slice(0, 5).map((tag) => (
            <span
              key={tag}
              className="text-xs px-2 py-0.5 rounded-full font-medium bg-sky-50 dark:bg-sky-900/20 text-sky-600 dark:text-sky-400 truncate max-w-[120px]"
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Engagement metrics row */}
      <div className="flex items-center justify-between gap-2 pt-3 border-t border-slate-100 dark:border-slate-700/50 flex-wrap">
        <div className="flex items-center gap-4">
          {tweet.reply_count > 0 && (
            <span className="flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400" title="Replies">
              <MessageSquare size={13} />
              {formatNumber(tweet.reply_count)}
            </span>
          )}
          {tweet.retweet_count > 0 && (
            <span className="flex items-center gap-1 text-xs text-emerald-500 dark:text-emerald-400" title="Retweets">
              <Repeat2 size={13} />
              {formatNumber(tweet.retweet_count)}
            </span>
          )}
          {tweet.like_count > 0 && (
            <span className="flex items-center gap-1 text-xs text-pink-500 dark:text-pink-400" title="Likes">
              <Heart size={13} />
              {formatNumber(tweet.like_count)}
            </span>
          )}
          {tweet.view_count > 0 && (
            <span className="flex items-center gap-1 text-xs text-slate-400 dark:text-slate-500" title="Views">
              <Eye size={13} />
              {formatNumber(tweet.view_count)}
            </span>
          )}
          {tweet.bookmark_count > 0 && (
            <span className="flex items-center gap-1 text-xs text-amber-500 dark:text-amber-400" title="Bookmarks">
              <Bookmark size={13} />
              {formatNumber(tweet.bookmark_count)}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={handleAskAI}
            title="Ask AI about this tweet"
            className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-semibold text-indigo-500 dark:text-indigo-400 hover:text-white hover:bg-indigo-600 transition-all border border-indigo-400/30 hover:border-indigo-500 whitespace-nowrap"
          >
            <MessageSquare size={11} />
            <span className="hidden xs:inline">Ask AI</span>
          </button>
          <a
            href={tweet.url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            title="Open on X"
            className="p-1.5 rounded-lg text-slate-400 hover:text-sky-500 hover:bg-sky-50 dark:hover:bg-sky-900/20 transition-all"
          >
            <ExternalLink size={13} />
          </a>
          <BookmarkButton contentType="tweet" objectId={tweet.id} size={15} />
        </div>
      </div>
    </div>
  );
});
