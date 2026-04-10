'use client';

import React from 'react';
import { ExternalLink, FileText, GitBranch, BookOpen, Newspaper } from 'lucide-react';
import { ChatSource } from '@/types';
import { cn } from '@/utils/helpers';

interface SourceCitationCardProps {
  source: ChatSource;
}

function getSourceIcon(contentType: string) {
  switch (contentType) {
    case 'paper':
      return <BookOpen size={13} />;
    case 'repository':
      return <GitBranch size={13} />;
    case 'article':
      return <Newspaper size={13} />;
    default:
      return <FileText size={13} />;
  }
}

function getSourceColor(contentType: string) {
  switch (contentType) {
    case 'paper':
      return 'text-violet-400 bg-violet-900/30 border-violet-800/50';
    case 'repository':
      return 'text-emerald-400 bg-emerald-900/30 border-emerald-800/50';
    case 'article':
      return 'text-cyan-400 bg-cyan-900/30 border-cyan-800/50';
    default:
      return 'text-slate-400 bg-slate-100 dark:bg-slate-800 border-slate-700';
  }
}

export function SourceCitationCard({ source }: SourceCitationCardProps) {
  const handleClick = () => {
    if (source.url) window.open(source.url, '_blank', 'noopener,noreferrer');
  };

  return (
    <button
      onClick={handleClick}
      className={cn(
        'flex flex-col gap-1.5 p-2.5 rounded-lg border text-left w-full transition-all',
        'hover:brightness-110 hover:scale-[1.01]',
        getSourceColor(source.content_type)
      )}
    >
      {/* Type badge */}
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide opacity-80">
          {getSourceIcon(source.content_type)}
          {source.content_type}
        </span>
        <ExternalLink size={11} className="opacity-60 flex-shrink-0" />
      </div>

      {/* Title */}
      <p className="text-xs font-medium text-slate-700 dark:text-slate-200 line-clamp-2 leading-tight">
        {source.title}
      </p>

      {/* Snippet */}
      {source.snippet && (
        <p className="text-[11px] text-slate-400 line-clamp-2 leading-snug">
          {source.snippet}
        </p>
      )}
    </button>
  );
}
