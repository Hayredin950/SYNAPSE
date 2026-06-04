'use client';

import { cn } from '@/utils/helpers';

const SkeletonLine = ({ className = '' }: { className?: string }) => (
  <div className={cn('bg-slate-200 dark:bg-slate-700 rounded animate-pulse', className)} />
);

export const ArticleSkeleton = () => (
  <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-4">
    {/* Top row */}
    <div className="flex items-center justify-between mb-3">
      <SkeletonLine className="w-24 h-6" />
      <SkeletonLine className="w-16 h-4" />
    </div>

    {/* Title lines */}
    <div className="space-y-2 mb-3">
      <SkeletonLine className="w-full h-5" />
      <SkeletonLine className="w-3/4 h-5" />
    </div>

    {/* Summary lines */}
    <div className="space-y-2 mb-3">
      <SkeletonLine className="w-full h-4" />
      <SkeletonLine className="w-full h-4" />
      <SkeletonLine className="w-2/3 h-4" />
    </div>

    {/* Tags row */}
    <div className="flex gap-2 mb-3">
      <SkeletonLine className="w-16 h-6" />
      <SkeletonLine className="w-16 h-6" />
      <SkeletonLine className="w-16 h-6" />
    </div>

    {/* Bottom row */}
    <div className="flex items-center justify-between pt-2 border-t border-slate-200 dark:border-slate-700">
      <SkeletonLine className="w-32 h-4" />
      <SkeletonLine className="w-6 h-6" />
    </div>
  </div>
);

export const RepositorySkeleton = () => (
  <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-4">
    {/* Top row */}
    <div className="flex items-center justify-between mb-3">
      <div className="flex items-center gap-2">
        <SkeletonLine className="w-6 h-6" />
        <SkeletonLine className="w-20 h-4" />
      </div>
      <SkeletonLine className="w-20 h-6" />
    </div>

    {/* Repo name */}
    <SkeletonLine className="w-3/4 h-5 mb-2" />

    {/* Description */}
    <div className="space-y-1 mb-3">
      <SkeletonLine className="w-full h-4" />
      <SkeletonLine className="w-4/5 h-4" />
    </div>

    {/* Stats */}
    <div className="flex gap-4 mb-3">
      <SkeletonLine className="w-12 h-4" />
      <SkeletonLine className="w-12 h-4" />
      <SkeletonLine className="w-12 h-4" />
    </div>

    {/* Topics */}
    <div className="flex gap-2 mb-3">
      <SkeletonLine className="w-14 h-6" />
      <SkeletonLine className="w-14 h-6" />
      <SkeletonLine className="w-14 h-6" />
    </div>

    {/* Bottom */}
    <div className="flex items-center justify-between pt-2 border-t border-slate-200 dark:border-slate-700">
      <SkeletonLine className="w-32 h-4" />
      <SkeletonLine className="w-6 h-6" />
    </div>
  </div>
);

export const PaperSkeleton = () => (
  <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-4">
    {/* Top badges */}
    <div className="flex items-center gap-2 mb-3">
      <SkeletonLine className="w-20 h-6" />
      <SkeletonLine className="w-20 h-6" />
    </div>

    {/* Categories */}
    <div className="flex gap-2 mb-3">
      <SkeletonLine className="w-16 h-5" />
      <SkeletonLine className="w-16 h-5" />
    </div>

    {/* Title */}
    <div className="space-y-2 mb-2">
      <SkeletonLine className="w-full h-5" />
      <SkeletonLine className="w-3/4 h-5" />
    </div>

    {/* Authors */}
    <SkeletonLine className="w-2/3 h-4 mb-3" />

    {/* Abstract lines */}
    <div className="space-y-2 mb-3">
      <SkeletonLine className="w-full h-4" />
      <SkeletonLine className="w-full h-4" />
      <SkeletonLine className="w-1/2 h-4" />
    </div>

    {/* Bottom */}
    <div className="flex items-center justify-between pt-3 border-t border-slate-200 dark:border-slate-700">
      <div className="flex gap-2">
        <SkeletonLine className="w-6 h-6" />
        <SkeletonLine className="w-6 h-6" />
      </div>
      <SkeletonLine className="w-6 h-6" />
    </div>
  </div>
);
