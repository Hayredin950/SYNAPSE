/**
 * useInfiniteScroll — IntersectionObserver-based infinite scroll hook.
 *
 * Works like Facebook / X / Pinterest: as the user scrolls near the bottom
 * sentinel element, the next page is automatically fetched and appended.
 *
 * Usage:
 *   const { items, sentinelRef, isFetchingNextPage, hasNextPage, reset } =
 *     useInfiniteScroll({ fetchPage, pageSize });
 *
 *   return (
 *     <>
 *       {items.map(item => <Card key={item.id} {...item} />)}
 *       <ScrollSentinel ref={sentinelRef} ... />   ← place at the bottom
 *     </>
 *   );
 */

import { useState, useRef, useCallback, useEffect } from 'react';

export interface InfiniteScrollOptions<T> {
  /** Called with page number (1-based). Must return { items: T[], total: number } */
  fetchPage: (page: number) => Promise<{ items: T[]; total: number }>;
  /** Dependencies that should reset the list (e.g. search query, sort order) */
  deps?: unknown[];
}

export interface InfiniteScrollResult<T> {
  items: T[];
  sentinelRef: (node: HTMLElement | null) => void;
  isFetchingNextPage: boolean;
  isLoading: boolean;
  hasNextPage: boolean;
  total: number;
  error: string | null;
  /** Manually reset and reload from page 1 */
  reset: () => void;
}

export function useInfiniteScroll<T>({
  fetchPage,
  deps = [],
}: InfiniteScrollOptions<T>): InfiniteScrollResult<T> {
  const [items,              setItems]              = useState<T[]>([]);
  const [total,              setTotal]              = useState(0);
  const [isLoading,          setIsLoading]          = useState(true);
  const [isFetchingNextPage, setIsFetchingNextPage] = useState(false);
  const [error,              setError]              = useState<string | null>(null);

  // Use refs for values read inside the IntersectionObserver callback
  // to avoid stale closure issues.
  const nextPageRef  = useRef(1);
  const totalRef     = useRef(0);
  const itemsRef     = useRef<T[]>([]);
  const isFetching   = useRef(false);
  const observer     = useRef<IntersectionObserver | null>(null);

  // ── Core fetch ─────────────────────────────────────────────────────────────
  const doFetch = useCallback(async (pageNum: number, replace: boolean) => {
    if (isFetching.current) return;
    isFetching.current = true;
    if (pageNum === 1) setIsLoading(true);
    else setIsFetchingNextPage(true);
    setError(null);

    try {
      const result = await fetchPage(pageNum);
      const newItems = replace ? result.items : [...itemsRef.current, ...result.items];
      itemsRef.current = newItems;
      totalRef.current = result.total;
      nextPageRef.current = pageNum + 1;
      setTotal(result.total);
      setItems(newItems);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load more items');
    } finally {
      isFetching.current = false;
      setIsLoading(false);
      setIsFetchingNextPage(false);
    }
  // fetchPage identity changes when deps change — that's intentional
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchPage]);

  // ── Reset when deps change (search, sort, filter) ─────────────────────────
  const reset = useCallback(() => {
    observer.current?.disconnect();
    itemsRef.current  = [];
    totalRef.current  = 0;
    nextPageRef.current = 1;
    isFetching.current  = false;
    setItems([]);
    setTotal(0);
    setError(null);
    doFetch(1, true);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doFetch, ...deps]);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { reset(); }, deps);

  // ── Sentinel ref (IntersectionObserver) ───────────────────────────────────
  const sentinelRef = useCallback((node: HTMLElement | null) => {
    observer.current?.disconnect();
    if (!node) return;

    observer.current = new IntersectionObserver(
      (entries) => {
        if (
          entries[0].isIntersecting &&
          !isFetching.current &&
          itemsRef.current.length < totalRef.current
        ) {
          doFetch(nextPageRef.current, false);
        }
      },
      { rootMargin: '400px' }, // Start fetching 400px before reaching the bottom
    );
    observer.current.observe(node);
  }, [doFetch]);

  // Cleanup observer on unmount
  useEffect(() => () => { observer.current?.disconnect(); }, []);

  return {
    items,
    sentinelRef,
    isFetchingNextPage,
    isLoading,
    hasNextPage: items.length < total,
    total,
    error,
    reset,
  };
}
