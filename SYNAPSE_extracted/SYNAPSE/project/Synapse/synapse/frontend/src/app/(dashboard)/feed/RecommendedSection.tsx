'use client';

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/utils/api';
import { ArticleCard, PaperCard } from '@/components/cards';

export default function RecommendedSection() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['recommendations'],
    queryFn: () => api.get('/recommendations/').then(r => r.data),
  });

  const articles = data?.data?.articles || [];
  const papers = data?.data?.papers || [];
  // Repos UI could be added later; minimal path focuses on content consumption (articles/papers)

  if (isLoading || isError) return null;
  if (articles.length === 0 && papers.length === 0) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-slate-900 dark:text-white">✨ Recommended for You</h2>
      </div>

      {/* Articles row */}
      {articles.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {articles.slice(0, 6).map((a: any) => (
            <ArticleCard key={a.id} article={a} />
          ))}
        </div>
      )}

      {/* Papers row */}
      {papers.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {papers.slice(0, 4).map((p: any) => (
            <PaperCard key={p.id} paper={p} />
          ))}
        </div>
      )}
    </div>
  );
}
