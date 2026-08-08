/**
 * Offline page — shown by the service worker when the user is offline.
 *
 * Phase 7.2 — PWA (Week 20)
 */
'use client';

export default function OfflinePage() {
  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center px-6">
      <div className="text-center max-w-sm">
        {/* Animated wifi-off icon */}
        <div className="w-20 h-20 rounded-3xl bg-indigo-900/40 border border-indigo-700/30 flex items-center justify-center mx-auto mb-6">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="40" height="40"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="text-indigo-400"
          >
            <line x1="1" y1="1" x2="23" y2="23" />
            <path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55" />
            <path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39" />
            <path d="M10.71 5.05A16 16 0 0 1 22.56 9" />
            <path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88" />
            <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
            <line x1="12" y1="20" x2="12.01" y2="20" />
          </svg>
        </div>

        <h1 className="text-2xl font-bold text-white mb-2">You&apos;re offline</h1>
        <p className="text-slate-400 text-sm mb-6 leading-relaxed">
          SYNAPSE needs an internet connection to fetch the latest tech intelligence.
          Check your connection and try again.
        </p>

        <button
          onClick={() => window.location.reload()}
          className="px-6 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm transition-colors w-full"
        >
          Try again
        </button>

        <p className="text-slate-600 text-xs mt-4">
          Previously cached content may still be available.
        </p>
      </div>
    </div>
  )
}
