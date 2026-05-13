'use client';

/**
 * HorizontalScroller — YouTube/Netflix-style horizontal card slider.
 *
 * Features:
 *  - Left / right arrow buttons (visible on hover or when scrollable)
 *  - Mouse drag-to-scroll (pointer events)
 *  - Touch swipe support (native overflow-x: scroll)
 *  - Scroll-snap on each card
 *  - Dot indicators when there are multiple pages
 *  - Fully accessible (keyboard-navigable children, aria-label on buttons)
 */

import React, { useRef, useState, useCallback, useEffect } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '@/utils/helpers';

interface HorizontalScrollerProps {
  children: React.ReactNode;
  /** Width of each card — used to calculate scroll distance. Default 280 */
  cardWidth?: number;
  /** Gap between cards in px. Default 16 */
  gap?: number;
  className?: string;
}

export function HorizontalScroller({
  children,
  cardWidth = 280,
  gap = 16,
  className,
}: HorizontalScrollerProps) {
  const trackRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft,  setCanScrollLeft]  = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);
  const [activeDot, setActiveDot] = useState(0);
  const [dotCount,  setDotCount]  = useState(0);

  // ── Drag state ──────────────────────────────────────────────────────────────
  const isDragging   = useRef(false);
  const startX       = useRef(0);
  const startScroll  = useRef(0);
  const hasDragged   = useRef(false);
  const pointerDownTime = useRef(0);

  // ── Sync scroll state ───────────────────────────────────────────────────────
  const syncState = useCallback(() => {
    const el = trackRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 4);
    setCanScrollRight(el.scrollLeft < el.scrollWidth - el.clientWidth - 4);
    // Dot calculation
    const pages = Math.ceil(el.scrollWidth / el.clientWidth);
    setDotCount(pages > 1 ? pages : 0);
    setActiveDot(Math.round(el.scrollLeft / el.clientWidth));
  }, []);

  useEffect(() => {
    const el = trackRef.current;
    if (!el) return;
    syncState();
    el.addEventListener('scroll', syncState, { passive: true });
    const ro = new ResizeObserver(syncState);
    ro.observe(el);
    return () => { el.removeEventListener('scroll', syncState); ro.disconnect(); };
  }, [syncState]);

  // ── Arrow scroll ────────────────────────────────────────────────────────────
  const scroll = useCallback((dir: 'left' | 'right') => {
    const el = trackRef.current;
    if (!el) return;
    const step = (cardWidth + gap) * 2; // scroll 2 cards at a time
    el.scrollBy({ left: dir === 'left' ? -step : step, behavior: 'smooth' });
  }, [cardWidth, gap]);

  // ── Dot click ───────────────────────────────────────────────────────────────
  const scrollToDot = useCallback((idx: number) => {
    const el = trackRef.current;
    if (!el) return;
    el.scrollTo({ left: idx * el.clientWidth, behavior: 'smooth' });
  }, []);

  // ── Drag handlers ───────────────────────────────────────────────────────────
  const onMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return; // left button only
    const el = trackRef.current;
    if (!el) return;
    isDragging.current      = true;
    hasDragged.current      = false;
    startX.current          = e.clientX;
    startScroll.current     = el.scrollLeft;
    pointerDownTime.current = Date.now();
    // Prevent text selection during drag
    e.preventDefault();
  }, []);

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isDragging.current) return;
    const el = trackRef.current;
    if (!el) return;
    const dx = e.clientX - startX.current;
    // Only count as drag if moved >10px AND held for >100ms
    if (Math.abs(dx) > 10 && Date.now() - pointerDownTime.current > 100) {
      hasDragged.current = true;
      el.style.cursor = 'grabbing';
      el.scrollLeft = startScroll.current - dx;
    }
  }, []);

  const onMouseUp = useCallback(() => {
    isDragging.current = false;
    const el = trackRef.current;
    if (el) el.style.cursor = '';
    // Clear hasDragged after a brief delay so the click event fires first
    setTimeout(() => { hasDragged.current = false; }, 50);
  }, []);

  // Suppress click only after a real drag (not a tap/click)
  const onClickCapture = useCallback((e: React.MouseEvent) => {
    if (hasDragged.current) {
      e.stopPropagation();
      e.preventDefault();
    }
  }, []);

  return (
    <div className={cn('relative group/scroller', className)}>

      {/* ── Left arrow ──────────────────────────────────────────────────────── */}
      <button
        onClick={() => scroll('left')}
        aria-label="Scroll left"
        className={cn(
          'absolute left-0 top-1/2 -translate-y-1/2 z-10 -translate-x-3',
          'w-9 h-9 rounded-full bg-white dark:bg-slate-800 shadow-lg border border-slate-200 dark:border-slate-700',
          'flex items-center justify-center text-slate-600 dark:text-slate-300',
          'hover:bg-indigo-50 dark:hover:bg-indigo-900/40 hover:text-indigo-600 dark:hover:text-indigo-400',
          'transition-all duration-200',
          canScrollLeft
            ? 'opacity-0 group-hover/scroller:opacity-100 scale-90 group-hover/scroller:scale-100'
            : 'opacity-0 pointer-events-none',
        )}
      >
        <ChevronLeft size={18} />
      </button>

      {/* ── Scrollable track ────────────────────────────────────────────────── */}
      <div
        ref={trackRef}
        className="flex overflow-x-auto gap-4 pb-3 scroll-smooth scrollbar-hide"
        style={{
          scrollSnapType: 'x mandatory',
          WebkitOverflowScrolling: 'touch',
        }}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
        onClickCapture={onClickCapture}
      >
        {/* Each direct child gets snap alignment + fixed min-width */}
        {React.Children.map(children, (child) =>
          child ? (
            <div
              style={{ scrollSnapAlign: 'start', flexShrink: 0, width: cardWidth }}
            >
              {child}
            </div>
          ) : null
        )}
        {/* Right breathing room so the last card shadow isn't clipped */}
        <div style={{ flexShrink: 0, width: 4 }} />
      </div>

      {/* ── Right arrow ─────────────────────────────────────────────────────── */}
      <button
        onClick={() => scroll('right')}
        aria-label="Scroll right"
        className={cn(
          'absolute right-0 top-1/2 -translate-y-1/2 z-10 translate-x-3',
          'w-9 h-9 rounded-full bg-white dark:bg-slate-800 shadow-lg border border-slate-200 dark:border-slate-700',
          'flex items-center justify-center text-slate-600 dark:text-slate-300',
          'hover:bg-indigo-50 dark:hover:bg-indigo-900/40 hover:text-indigo-600 dark:hover:text-indigo-400',
          'transition-all duration-200',
          canScrollRight
            ? 'opacity-0 group-hover/scroller:opacity-100 scale-90 group-hover/scroller:scale-100'
            : 'opacity-0 pointer-events-none',
        )}
      >
        <ChevronRight size={18} />
      </button>

      {/* ── Dot indicators ──────────────────────────────────────────────────── */}
      {dotCount > 1 && (
        <div className="flex justify-center gap-1.5 mt-2">
          {Array.from({ length: dotCount }).map((_, i) => (
            <button
              key={i}
              onClick={() => scrollToDot(i)}
              aria-label={`Go to page ${i + 1}`}
              className={cn(
                'rounded-full transition-all duration-200',
                i === activeDot
                  ? 'w-5 h-1.5 bg-indigo-500'
                  : 'w-1.5 h-1.5 bg-slate-300 dark:bg-slate-600 hover:bg-indigo-400',
              )}
            />
          ))}
        </div>
      )}
    </div>
  );
}
