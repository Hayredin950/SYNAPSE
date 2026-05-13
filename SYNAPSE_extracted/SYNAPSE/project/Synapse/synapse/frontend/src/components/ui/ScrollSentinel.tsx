'use client';

/**
 * ScrollSentinel — bottom-of-list loading indicator for infinite scroll.
 *
 * Place this component at the end of your list. It shows:
 *  - A loading spinner while fetching the next page
 *  - "You're all caught up" message when no more pages
 *  - An error message with retry button if fetching failed
 */

import React from 'react';
import { Loader2, CheckCircle2, RefreshCw } from 'lucide-react';

interface ScrollSentinelProps {
  sentinelRef: (node: HTMLElement | null) => void;
  isFetchingNextPage: boolean;
  hasNextPage: boolean;
  error?: string | null;
  onRetry?: () => void;
  /** Label shown when all items are loaded. Default "You're all caught up" */
  endLabel?: string;
}

export function ScrollSentinel({
  sentinelRef,
  isFetchingNextPage,
  hasNextPage,
  error,
  onRetry,
  endLabel = "You're all caught up ✨",
}: ScrollSentinelProps) {
  return (
    <div ref={sentinelRef} className="flex flex-col items-center justify-center py-10 gap-3">
      {isFetchingNextPage && (
        <div className="flex items-center gap-2 text-slate-400 dark:text-slate-500 text-sm">
          <Loader2 className="w-5 h-5 animate-spin text-indigo-500" />
          <span>Loading more…</span>
        </div>
      )}

      {!isFetchingNextPage && !hasNextPage && !error && (
        <div className="flex items-center gap-2 text-slate-400 dark:text-slate-500 text-sm">
          <CheckCircle2 className="w-4 h-4 text-emerald-500" />
          <span>{endLabel}</span>
        </div>
      )}

      {error && (
        <div className="flex flex-col items-center gap-2">
          <p className="text-sm text-red-500 dark:text-red-400">{error}</p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium transition"
            >
              <RefreshCw className="w-4 h-4" /> Retry
            </button>
          )}
        </div>
      )}
    </div>
  );
}
