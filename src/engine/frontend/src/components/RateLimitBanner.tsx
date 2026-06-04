'use client';

/**
 * TASK-501-F1: RateLimitBanner
 *
 * Listens for the 'synapse:rate_limit_exceeded' custom event dispatched by api.ts
 * when a 429 response is received. Shows a dismissable banner with:
 *  - Error message from server
 *  - Live countdown to reset time
 *  - "Upgrade Plan" CTA → /pricing
 */

import React, { useEffect, useState, useRef } from 'react';
import { Zap, X, Clock } from 'lucide-react';
import Link from 'next/link';

interface RateLimitDetail {
  resetAt:    string | null;   // ISO datetime string
  upgradeUrl: string;
  message:    string;
}

function useCountdown(resetAt: string | null): string {
  const [display, setDisplay] = useState('');

  useEffect(() => {
    if (!resetAt) return;
    const end = new Date(resetAt).getTime();

    const tick = () => {
      const remaining = Math.max(0, end - Date.now());
      if (remaining === 0) { setDisplay('now'); return; }
      const h = Math.floor(remaining / 3_600_000);
      const m = Math.floor((remaining % 3_600_000) / 60_000);
      const s = Math.floor((remaining % 60_000) / 1_000);
      if (h > 0) setDisplay(`${h}h ${m}m`);
      else if (m > 0) setDisplay(`${m}m ${s}s`);
      else setDisplay(`${s}s`);
    };

    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [resetAt]);

  return display;
}

export function RateLimitBanner() {
  const [detail, setDetail] = useState<RateLimitDetail | null>(null);
  const countdown = useCountdown(detail?.resetAt ?? null);

  useEffect(() => {
    const handler = (e: Event) => {
      const ce = e as CustomEvent<RateLimitDetail>;
      setDetail(ce.detail);
    };
    window.addEventListener('synapse:rate_limit_exceeded', handler);
    return () => window.removeEventListener('synapse:rate_limit_exceeded', handler);
  }, []);

  if (!detail) return null;

  return (
    <div
      role="alert"
      aria-live="polite"
      className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[110] w-full max-w-md mx-auto px-4"
    >
      <div className="flex items-start gap-3 bg-amber-50 dark:bg-amber-950/80 border border-amber-200 dark:border-amber-700/60 rounded-2xl p-4 shadow-xl backdrop-blur">
        {/* Icon */}
        <div className="flex-shrink-0 w-9 h-9 rounded-xl bg-amber-100 dark:bg-amber-900/50 flex items-center justify-center">
          <Zap size={18} className="text-amber-600 dark:text-amber-400" />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-amber-800 dark:text-amber-200">
            Rate Limit Reached
          </p>
          <p className="text-xs text-amber-700 dark:text-amber-300 mt-0.5 leading-relaxed">
            {detail.message}
          </p>
          {detail.resetAt && countdown && (
            <p className="text-xs text-amber-600 dark:text-amber-400 mt-1 flex items-center gap-1">
              <Clock size={11} />
              Resets in <span className="font-mono font-semibold ml-0.5">{countdown}</span>
            </p>
          )}
          <Link
            href={detail.upgradeUrl ?? '/pricing'}
            className="inline-flex items-center gap-1.5 mt-2 px-3 py-1 rounded-lg bg-amber-500 hover:bg-amber-600 text-white text-xs font-semibold transition-colors"
          >
            <Zap size={11} />
            Upgrade Plan
          </Link>
        </div>

        {/* Dismiss */}
        <button
          onClick={() => setDetail(null)}
          className="flex-shrink-0 p-1 rounded-lg hover:bg-amber-100 dark:hover:bg-amber-900/50 transition-colors"
          aria-label="Dismiss"
        >
          <X size={15} className="text-amber-600 dark:text-amber-400" />
        </button>
      </div>
    </div>
  );
}

export default RateLimitBanner;
