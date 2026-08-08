'use client';

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/utils/api';
import { ArticleCard, PaperCard } from '@/components/cards';
import { ArticleSkeleton, PaperSkeleton } from '@/components/cards/SkeletonCard';

export default function TrendingTab() {
  const { data, isLoading } = useQuery({
    queryKey: ['trending'],
    queryFn: () => api.get('/trending/').then(r => r.data),
    staleTime: 60_000,
  });

  const articles = data?.data?.articles || [];
  const papers = data?.data?.papers || [];

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
          {articles.length > 0 && (
            <div>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-2">Trending Articles</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {articles.map((a: any) => (
                  <ArticleCard key={a.id} article={a} />
                ))}
              </div>
            </div>
          )}

          {papers.length > 0 && (
            <div>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-2">Trending Papers</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {papers.map((p: any) => (
                  <PaperCard key={p.id} paper={p} />
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
