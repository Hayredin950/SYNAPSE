'use client';

import React, { useState } from 'react';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { api } from '@/utils/api';
import { ArticleCard, PaperCard } from '@/components/cards';
import { ArticleSkeleton, PaperSkeleton } from '@/components/cards/SkeletonCard';
import type { Article, ResearchPaper } from '@/types';

// TASK-001-T3: ForYouTab fetches from two sources and merges them:
//   1. Interest-filtered articles  — GET /articles/?for_you=1  (topic/tag matching)
//   2. Vector-based recommendations — GET /recommendations/    (embedding similarity)
// Results are deduplicated by id and displayed together.

interface InterestFeedResponse {
  results?: Article[];
  data?: Article[];
}

interface RecoResponse {
  data?: { articles?: Article[]; papers?: ResearchPaper[] };
  articles?: Article[];
  papers?: ResearchPaper[];
}

export default function ForYouTab() {
  const [offset, setOffset] = useState(0);
  const limit = 12;

  // 1. Interest-filtered articles (TASK-001-T3)
  const { data: interestData, isLoading: interestLoading } = useQuery<InterestFeedResponse>({
    queryKey: ['for-you-interest', offset],
    queryFn: () =>
      api
        .get('/articles/', { params: { for_you: 1, page_size: limit, page: Math.floor(offset / limit) + 1 } })
        .then(r => r.data)
        .catch(() => ({ results: [] })),
    placeholderData: keepPreviousData,
  });

  // 2. Vector-based recommendations (existing)
  const { data: recoData, isLoading: recoLoading, isFetching } = useQuery<RecoResponse>({
    queryKey: ['recommendations', offset],
    queryFn: () => api.get('/recommendations/', { params: { limit, offset } }).then(r => r.data),
    placeholderData: keepPreviousData,
  });

  const isLoading = interestLoading || recoLoading;

  // Merge & deduplicate articles from both sources (interest-filtered first = higher priority)
  const interestArticles: Article[] = interestData?.results ?? interestData?.data ?? [];
  const recoArticles: Article[] = recoData?.data?.articles ?? recoData?.articles ?? [];
  const seenIds = new Set<string>(interestArticles.map(a => a.id));
  const mergedArticles: Article[] = [
    ...interestArticles,
    ...recoArticles.filter(a => !seenIds.has(a.id)),
  ];

  const papers: ResearchPaper[] = recoData?.data?.papers ?? recoData?.papers ?? [];
  const hasMore = (mergedArticles.length + papers.length) >= limit;

  const loadMore = () => {
    setOffset((o) => o + limit);
  };

  return (
    <div className="space-y-6">
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <ArticleSkeleton key={`a-${i}`} />
          ))}
          {Array.from({ length: 4 }).map((_, i) => (
            <PaperSkeleton key={`p-${i}`} />
          ))}
        </div>
      ) : (
        <>
          {mergedArticles.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {mergedArticles.map((a: Article) => (
                <ArticleCard key={a.id} article={a} />
              ))}
            </div>
          )}

          {papers.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {papers.map((p: ResearchPaper) => (
                <PaperCard key={p.id} paper={p} />
              ))}
            </div>
          )}

          {hasMore && (
            <div className="flex justify-center mt-6">
              <button
                onClick={loadMore}
                disabled={isFetching}
                className="px-6 py-3 rounded-lg font-medium bg-indigo-500 hover:bg-indigo-600 text-white disabled:opacity-60"
              >
                {isFetching ? 'Loading...' : 'Load More'}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
