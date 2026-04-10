'use client';

/**
 * TASK-602-F1: GitHub Intelligence Dashboard — fully overhauled
 *
 * Sections:
 *  1. Trending Now        — repos sorted by 7d star velocity + sparklines
 *  2. Rising Stars        — repos < 6 months old, high velocity
 *  3. Ecosystem Health    — language cards with growth indicators
 *  4. Tech Radar          — trending topics/frameworks via TrendRadar component
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  GitBranch, Star, TrendingUp, ExternalLink,
  ArrowUp, ArrowDown, Minus, Globe,
  Flame, Sparkles, Activity, Search,
} from 'lucide-react';
import { api } from '@/utils/api';
import dynamic from 'next/dynamic';

// Lazy-load recharts-based chart components — recharts is ~200KB and only
// needed when the user actually visits this page (not on initial dashboard load).
const StarSparkline = dynamic(
  () => import('@/components/charts/StarSparkline').then(m => ({ default: m.StarSparkline })),
  { ssr: false, loading: () => <div className="h-8 w-24 bg-slate-100 dark:bg-slate-700 rounded animate-pulse" /> },
)
const TrendRadar = dynamic(
  () => import('@/components/charts/TrendRadar').then(m => ({ default: m.TrendRadar })),
  { ssr: false, loading: () => <div className="h-64 bg-slate-100 dark:bg-slate-700 rounded-2xl animate-pulse" /> },
)

// ── Types ──────────────────────────────────────────────────────────────────────

interface Repo {
  id: string;
  full_name: string;
  url: string;
  description: string;
  language: string;
  stars: number;
  forks: number;
  stars_7d_delta: number;
  velocity_7d: number;
  trend_class: 'rising_star' | 'stable' | 'declining';
  is_rising_star: boolean;
  star_history: { date: string; stars: number }[];
  topics: string[];
}

interface EcosystemData {
  language: string;
  total_repos: number;
  total_stars: number;
  avg_velocity_7d: number;
  rising_star_count: number;
  top_repos: { full_name: string; url: string; stars: number; velocity_7d: number }[];
}

// ── Constants ──────────────────────────────────────────────────────────────────

const LANGUAGES = ['All', 'Python', 'TypeScript', 'Rust', 'Go', 'JavaScript', 'Java', 'C++'];

// Language SVG icons (inline — no external dependency needed)
const LANG_ICONS: Record<string, React.ReactNode> = {
  Python: (
    <svg viewBox="0 0 24 24" className="w-3.5 h-3.5 shrink-0" fill="none">
      <path d="M11.914 0C5.82 0 6.2 2.656 6.2 2.656l.007 2.752h5.814v.826H3.89S0 5.789 0 11.969c0 6.18 3.403 5.96 3.403 5.96h2.03v-2.867s-.109-3.4 3.345-3.4h5.762s3.236.052 3.236-3.13V3.26S18.28 0 11.914 0zm-3.2 1.874a1.049 1.049 0 1 1 0 2.098 1.049 1.049 0 0 1 0-2.098z" fill="#3776AB"/>
      <path d="M12.086 24c6.094 0 5.714-2.656 5.714-2.656l-.007-2.752h-5.814v-.826h8.131S24 18.211 24 12.031c0-6.18-3.403-5.96-3.403-5.96h-2.03v2.867s.109 3.4-3.345 3.4H9.46s-3.236-.052-3.236 3.13V20.74S5.72 24 12.086 24zm3.2-1.874a1.049 1.049 0 1 1 0-2.098 1.049 1.049 0 0 1 0 2.098z" fill="#FFD43B"/>
    </svg>
  ),
  TypeScript: (
    <svg viewBox="0 0 24 24" className="w-3.5 h-3.5 shrink-0" fill="#3178C6">
      <path d="M0 12v12h24V0H0zm19.341-.956c.61.152 1.074.423 1.501.865.221.236.549.666.575.768.008.03-1.036.73-1.668 1.123-.023.015-.115-.084-.217-.236-.31-.45-.633-.644-1.128-.678-.728-.05-1.196.331-1.192.967a.88.88 0 0 0 .102.45c.16.331.458.53 1.39.933 1.719.74 2.454 1.227 2.911 1.92.51.773.625 2.008.278 2.926-.38.998-1.325 1.676-2.655 1.9-.411.073-1.386.062-1.828-.018-.964-.172-1.878-.648-2.442-1.273-.221-.243-.652-.88-.625-.925.011-.016.11-.077.22-.141.108-.061.511-.294.892-.515l.69-.4.145.214c.202.308.643.731.91.872.766.404 1.817.347 2.335-.118a.883.883 0 0 0 .313-.72c0-.278-.035-.4-.18-.61-.186-.266-.567-.49-1.649-.96-1.238-.533-1.771-.864-2.259-1.39a3.165 3.165 0 0 1-.659-1.2c-.091-.339-.114-1.189-.042-1.531.255-1.197 1.158-2.03 2.461-2.278.423-.08 1.406-.05 1.821.054zm-5.634 1.002l.008.983H10.59v8.876H8.38v-8.876H5.258v-.964c0-.534.011-.98.026-.99.012-.016 1.913-.024 4.217-.02l4.195.012z"/>
    </svg>
  ),
  Rust: (
    <svg viewBox="0 0 24 24" className="w-3.5 h-3.5 shrink-0" fill="#CE412B">
      <path d="M23.634 11.639l-1.002-0.619a13.4 13.4 0 0 0-0.029-0.296l0.855-0.766a0.348 0.348 0 0 0-0.08-0.567l-1.097-0.501a13.06 13.06 0 0 0-0.088-0.287l0.682-0.899a0.348 0.348 0 0 0-0.155-0.543l-1.163-0.373a12.473 12.473 0 0 0-0.144-0.268l0.496-1.016a0.348 0.348 0 0 0-0.225-0.502l-1.203-0.237a11.99 11.99 0 0 0-0.196-0.241l0.298-1.112a0.348 0.348 0 0 0-0.288-0.443l-1.218-0.092a11.37 11.37 0 0 0-0.244-0.207l0.096-1.181a0.348 0.348 0 0 0-0.345-0.374 0.35 0.35 0 0 0-0.005 0l-1.208 0.056a10.806 10.806 0 0 0-0.284-0.168l-0.109-1.215a0.348 0.348 0 0 0-0.395-0.314l-1.175 0.203a10.256 10.256 0 0 0-0.317-0.124l-0.311-1.215a0.348 0.348 0 0 0-0.437-0.247l-1.119 0.347a9.738 9.738 0 0 0-0.343-0.077l-0.505-1.167a0.348 0.348 0 0 0-0.47-0.172l-1.041 0.486a9.24 9.24 0 0 0-0.36-0.029l-0.689-1.086a0.348 0.348 0 0 0-0.493-0.089l-0.943 0.619a8.76 8.76 0 0 0-0.369 0.021l-0.86-0.979a0.348 0.348 0 0 0-0.504 0l-0.86 0.979a8.747 8.747 0 0 0-0.369-0.021l-0.943-0.619a0.348 0.348 0 0 0-0.493 0.089l-0.689 1.086a9.24 9.24 0 0 0-0.36 0.029l-1.041-0.486a0.348 0.348 0 0 0-0.47 0.172l-0.505 1.167a9.738 9.738 0 0 0-0.343 0.077l-1.119-0.347a0.348 0.348 0 0 0-0.437 0.247l-0.311 1.215a10.256 10.256 0 0 0-0.317 0.124l-1.175-0.203a0.348 0.348 0 0 0-0.395 0.314l-0.109 1.215a10.806 10.806 0 0 0-0.284 0.168l-1.208-0.056a0.348 0.348 0 0 0-0.35 0.346v0.028l0.096 1.181a11.37 11.37 0 0 0-0.244 0.207l-1.218 0.092a0.348 0.348 0 0 0-0.288 0.443l0.298 1.112a11.99 11.99 0 0 0-0.196 0.241l-1.203 0.237a0.348 0.348 0 0 0-0.225 0.502l0.496 1.016a12.473 12.473 0 0 0-0.144 0.268l-1.163 0.373a0.348 0.348 0 0 0-0.155 0.543l0.682 0.899a13.06 13.06 0 0 0-0.088 0.287l-1.097 0.501a0.348 0.348 0 0 0-0.08 0.567l0.855 0.766a13.4 13.4 0 0 0-0.029 0.296l-1.002 0.619a0.348 0.348 0 0 0 0 0.592l1.002 0.619c0.008 0.099 0.018 0.198 0.029 0.296l-0.855 0.766a0.348 0.348 0 0 0 0.08 0.567l1.097 0.501c0.028 0.096 0.057 0.192 0.088 0.287l-0.682 0.899a0.348 0.348 0 0 0 0.155 0.543l1.163 0.373c0.047 0.09 0.095 0.179 0.144 0.268l-0.496 1.016a0.348 0.348 0 0 0 0.225 0.502l1.203 0.237c0.064 0.081 0.129 0.162 0.196 0.241l-0.298 1.112a0.348 0.348 0 0 0 0.288 0.443l1.218 0.092c0.08 0.071 0.161 0.14 0.244 0.207l-0.096 1.181a0.348 0.348 0 0 0 0.345 0.374h0.005l1.208-0.056c0.093 0.058 0.188 0.114 0.284 0.168l0.109 1.215a0.348 0.348 0 0 0 0.395 0.314l1.175-0.203c0.105 0.043 0.211 0.084 0.317 0.124l0.311 1.215a0.348 0.348 0 0 0 0.437 0.247l1.119-0.347c0.114 0.027 0.228 0.053 0.343 0.077l0.505 1.167a0.348 0.348 0 0 0 0.47 0.172l1.041-0.486c0.12 0.011 0.24 0.02 0.36 0.029l0.689 1.086a0.348 0.348 0 0 0 0.493 0.089l0.943-0.619c0.123 0.008 0.246 0.015 0.369 0.021l0.86 0.979a0.348 0.348 0 0 0 0.504 0l0.86-0.979c0.123-0.006 0.246-0.013 0.369-0.021l0.943 0.619a0.348 0.348 0 0 0 0.493-0.089l0.689-1.086c0.12-0.009 0.24-0.018 0.36-0.029l1.041 0.486a0.348 0.348 0 0 0 0.47-0.172l0.505-1.167c0.115-0.024 0.229-0.05 0.343-0.077l1.119 0.347a0.348 0.348 0 0 0 0.437-0.247l0.311-1.215c0.106-0.04 0.212-0.081 0.317-0.124l1.175 0.203a0.348 0.348 0 0 0 0.395-0.314l0.109-1.215c0.096-0.054 0.191-0.11 0.284-0.168l1.208 0.056h0.005a0.348 0.348 0 0 0 0.345-0.374l-0.096-1.181c0.083-0.067 0.164-0.136 0.244-0.207l1.218-0.092a0.348 0.348 0 0 0 0.288-0.443l-0.298-1.112c0.067-0.079 0.132-0.16 0.196-0.241l1.203-0.237a0.348 0.348 0 0 0 0.225-0.502l-0.496-1.016c0.049-0.089 0.097-0.178 0.144-0.268l1.163-0.373a0.348 0.348 0 0 0 0.155-0.543l-0.682-0.899c0.031-0.095 0.06-0.191 0.088-0.287l1.097-0.501a0.348 0.348 0 0 0 0.08-0.567l-0.855-0.766c0.011-0.098 0.021-0.197 0.029-0.296l1.002-0.619a0.348 0.348 0 0 0 0-0.592z"/>
    </svg>
  ),
  Go: (
    <svg viewBox="0 0 24 24" className="w-3.5 h-3.5 shrink-0" fill="#00ACD7">
      <path d="M1.811 10.231c-.047 0-.058-.023-.035-.059l.246-.315c.023-.035.081-.058.128-.058h4.172c.046 0 .058.035.035.07l-.199.303c-.023.036-.082.07-.117.07zM.047 11.306c-.047 0-.059-.023-.035-.058l.245-.316c.023-.035.082-.058.129-.058h5.328c.047 0 .059.035.047.07l-.093.28c-.012.047-.059.07-.105.07zm2.828 1.075c-.047 0-.059-.035-.035-.07l.163-.292c.023-.035.07-.07.117-.07h2.337c.047 0 .07.035.07.082l-.023.28c0 .047-.047.082-.082.082zm12.129-2.36c-.736.187-1.239.327-1.963.514-.176.046-.187.058-.34-.117-.174-.199-.303-.327-.548-.444-.737-.362-1.45-.257-2.115.175-.795.514-1.204 1.274-1.192 2.22.011.935.654 1.706 1.577 1.835.795.105 1.46-.175 1.987-.771.105-.13.198-.27.315-.434H10.47c-.245 0-.304-.152-.222-.35.152-.362.432-.97.596-1.274a.315.315 0 0 1 .292-.187h4.253c-.023.316-.023.631-.07.947a4.983 4.983 0 0 1-.958 2.29c-.841 1.11-1.94 1.8-3.33 1.986-1.145.152-2.209-.07-3.143-.77-.865-.655-1.356-1.52-1.484-2.595-.152-1.274.222-2.419.993-3.424.83-1.086 1.928-1.776 3.272-2.02 1.098-.2 2.15-.07 3.096.571.62.41 1.063.97 1.356 1.648.07.105.023.164-.117.2zm3.868 6.461c-1.064-.024-2.034-.328-2.852-1.029a3.665 3.665 0 0 1-1.262-2.255c-.21-1.32.152-2.489.947-3.529.853-1.122 1.881-1.706 3.272-1.95 1.192-.21 2.314-.095 3.33.595.923.63 1.496 1.484 1.648 2.605.198 1.578-.257 2.863-1.344 3.962-.771.783-1.718 1.273-2.805 1.495-.315.06-.633.07-.934.106zm2.78-4.72c-.011-.153-.011-.27-.034-.387-.21-1.157-1.274-1.81-2.384-1.554-1.087.245-1.788 1.11-1.847 2.245-.047.912.632 1.799 1.537 1.954.946.165 1.765-.35 2.174-1.32.105-.258.152-.538.21-.806z"/>
    </svg>
  ),
  JavaScript: (
    <svg viewBox="0 0 24 24" className="w-3.5 h-3.5 shrink-0" fill="#F7DF1E">
      <rect width="24" height="24" rx="2" fill="#F7DF1E"/>
      <path d="M6.756 19.515l1.44-.872c.277.492.53.907 1.137.907.582 0 .95-.228.95-.907V13h1.77v5.674c0 1.495-.876 2.174-2.154 2.174-1.152 0-1.822-.597-2.143-1.333zM14.174 19.35l1.44-.838c.38.62.872 1.075 1.743 1.075.733 0 1.2-.367 1.2-.872 0-.606-.48-.82-1.29-1.17l-.44-.19c-1.278-.544-2.126-1.226-2.126-2.668 0-1.328 1.012-2.34 2.593-2.34 1.126 0 1.937.392 2.52 1.42l-1.378.883c-.303-.544-.632-.757-1.142-.757-.52 0-.85.33-.85.757 0 .53.33.744 1.09 1.074l.442.19c1.505.645 2.354 1.303 2.354 2.78 0 1.593-1.252 2.467-2.934 2.467-1.645 0-2.707-.784-3.222-1.81z"/>
    </svg>
  ),
  Java: (
    <svg viewBox="0 0 24 24" className="w-3.5 h-3.5 shrink-0" fill="#ED8B00">
      <path d="M8.851 18.56s-.917.534.653.714c1.902.218 2.874.187 4.969-.211 0 0 .552.346 1.321.646-4.699 2.013-10.633-.118-6.943-1.149M8.276 15.933s-1.028.761.542.924c2.032.209 3.636.227 6.413-.308 0 0 .384.389.987.602-5.679 1.661-12.007.13-7.942-1.218M13.116 11.475c1.158 1.333-.304 2.533-.304 2.533s2.939-1.518 1.589-3.418c-1.261-1.772-2.228-2.652 3.007-5.688 0-.001-8.216 2.051-4.292 6.573M19.33 20.504s.679.559-.747.991c-2.712.822-11.288 1.069-13.669.033-.856-.373.75-.89 1.254-.998.527-.114.828-.093.828-.093-.953-.671-6.156 1.317-2.643 1.887 9.58 1.553 17.462-.7 14.977-1.82M9.292 13.21s-4.362 1.036-1.544 1.412c1.189.159 3.561.123 5.77-.062 1.806-.152 3.618-.477 3.618-.477s-.637.272-1.098.587c-4.429 1.165-12.986.623-10.522-.568 2.082-1.006 3.776-.892 3.776-.892M17.116 17.584c4.503-2.34 2.421-4.589.968-4.285-.355.074-.515.138-.515.138s.132-.207.385-.297c2.875-1.011 5.086 2.981-.928 4.562 0-.001.07-.062.09-.118M14.401 0s2.494 2.494-2.365 6.33c-3.896 3.077-.888 4.832-.001 6.836-2.274-2.053-3.943-3.858-2.824-5.539 1.644-2.469 6.197-3.665 5.19-7.627M9.734 23.924c4.322.277 10.959-.153 11.116-2.198 0 0-.302.775-3.572 1.391-3.688.694-8.239.613-10.937.168 0-.001.553.457 3.393.639"/>
    </svg>
  ),
  'C++': (
    <svg viewBox="0 0 24 24" className="w-3.5 h-3.5 shrink-0" fill="#00599C">
      <path d="M22.394 6c-.167-.29-.398-.543-.652-.69L12.926.22c-.509-.294-1.34-.294-1.848 0L2.26 5.31c-.508.293-.923 1.013-.923 1.6v10.18c0 .294.104.62.271.91.167.29.398.543.652.69l8.816 5.09c.508.293 1.34.293 1.848 0l8.816-5.09c.254-.147.485-.4.652-.69.167-.29.27-.616.27-.91V6.91c.003-.294-.1-.62-.268-.91zM12 19.11c-3.92 0-7.109-3.19-7.109-7.11 0-3.92 3.19-7.11 7.109-7.11a7.133 7.133 0 0 1 6.156 3.553l-3.076 1.78a3.567 3.567 0 0 0-3.08-1.78A3.555 3.555 0 0 0 8.444 12 3.555 3.555 0 0 0 12 15.555a3.57 3.57 0 0 0 3.08-1.778l3.078 1.78A7.135 7.135 0 0 1 12 19.11zm7.11-6.715h-.79v.79h-.79v-.79h-.79v-.79h.79v-.79h.79v.79h.79zm2.962 0h-.79v.79h-.79v-.79h-.79v-.79h.79v-.79h.79v.79h.79z"/>
    </svg>
  ),
};

const TREND_CONFIG = {
  rising_star: { icon: Flame,     color: 'text-orange-500', bg: 'bg-orange-50 dark:bg-orange-950/30',  label: 'Rising Star' },
  stable:      { icon: Minus,     color: 'text-slate-400',  bg: 'bg-slate-50 dark:bg-slate-800/40',    label: 'Stable'      },
  declining:   { icon: ArrowDown, color: 'text-red-500',    bg: 'bg-red-50 dark:bg-red-950/30',        label: 'Declining'   },
};

const LANG_COLORS: Record<string, string> = {
  Python: '#3b82f6', TypeScript: '#f59e0b', Rust: '#f97316',
  Go: '#06b6d4', JavaScript: '#eab308', Java: '#ef4444', 'C++': '#8b5cf6',
};

// ── TrendBadge ─────────────────────────────────────────────────────────────────

function TrendBadge({ trend }: { trend: keyof typeof TREND_CONFIG }) {
  const cfg = TREND_CONFIG[trend] ?? TREND_CONFIG.stable;
  const Icon = cfg.icon;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold ${cfg.bg} ${cfg.color}`}>
      <Icon size={10} />{cfg.label}
    </span>
  );
}

// ── VelocityBadge ──────────────────────────────────────────────────────────────

function VelocityBadge({ delta }: { delta: number }) {
  if (delta === 0) return null;
  const positive = delta > 0;
  return (
    <span className={`inline-flex items-center gap-0.5 text-xs font-semibold ${positive ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-500'}`}>
      {positive ? <ArrowUp size={11} /> : <ArrowDown size={11} />}
      {Math.abs(delta).toLocaleString()}
      <span className="font-normal text-[10px] text-slate-400 ml-0.5">7d</span>
    </span>
  );
}

// ── RepoCard ───────────────────────────────────────────────────────────────────

function RepoCard({ repo }: { repo: Repo }) {
  const langColor = LANG_COLORS[repo.language] || '#6366f1';
  return (
    <div className="bg-white dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 rounded-2xl p-5 hover:shadow-md hover:border-emerald-200 dark:hover:border-emerald-700/40 transition-all flex flex-col gap-3">
      <div className="flex items-start gap-2 min-w-0">
        <div className="min-w-0 flex-1">
          <a href={repo.url} target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-1.5 font-semibold text-slate-800 dark:text-slate-100 text-sm hover:text-emerald-600 dark:hover:text-emerald-400 transition-colors">
            <GitBranch size={13} className="flex-shrink-0 text-slate-400" />
            <span className="truncate">{repo.full_name}</span>
            <ExternalLink size={11} className="flex-shrink-0 text-slate-300 dark:text-slate-600" />
          </a>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 line-clamp-2 leading-relaxed">
            {repo.description || 'No description'}
          </p>
        </div>
      </div>

      {/* Sparkline */}
      {repo.star_history?.length > 1 && (
        <div className="h-10">
          <StarSparkline data={repo.star_history} color={langColor} />
        </div>
      )}

      {/* Stats */}
      <div className="flex items-center gap-3 flex-wrap text-xs text-slate-500 dark:text-slate-400">
        <span className="flex items-center gap-1"><Star size={11} className="text-amber-400" />{repo.stars.toLocaleString()}</span>
        <span className="flex items-center gap-1"><GitBranch size={11} />{repo.forks.toLocaleString()}</span>
        {repo.language && (
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: langColor }} />
            {repo.language}
          </span>
        )}
        <VelocityBadge delta={repo.stars_7d_delta} />
        <span className="text-[11px] text-slate-400">
          {repo.velocity_7d > 0 ? '+' : ''}{repo.velocity_7d.toFixed(1)} ★/day
        </span>
      </div>

      {/* Topics */}
      {repo.topics?.length > 0 && (
        <div className="flex gap-1.5 flex-wrap">
          {repo.topics.slice(0, 4).map(t => (
            <span key={t} className="px-1.5 py-0.5 rounded text-[10px] bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400">
              {t}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}




// ── Main page ──────────────────────────────────────────────────────────────────

const PAGE_STEP = 12; // how many repos to reveal per scroll

export default function GitHubPage() {
  const [language, setLanguage] = useState('All');
  const [section, setSection]   = useState<'trending' | 'rising'>('trending');
  const [visibleCount, setVisibleCount] = useState(PAGE_STEP);
  const [searchQuery, setSearchQuery] = useState('');
  const [showRadar, setShowRadar] = useState(false);
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  const { data: trendingData, isLoading } = useQuery({
    queryKey: ['github-trending-velocity', language],
    queryFn:  () => api.get('/repos/trending-velocity/', {
      params: { limit: 500, ...(language !== 'All' ? { language } : {}) },
    }).then(r => r.data?.data as Repo[]),
    staleTime: 0, // always refetch fresh data
  });

  const repos       = trendingData ?? [];
  const risingStars = repos.filter(r => r.is_rising_star);
  const baseSectionRepos = section === 'rising' ? risingStars : repos;
  
  // Filter by search query
  const allDisplayRepos = searchQuery.trim()
    ? baseSectionRepos.filter(r => {
        const query = searchQuery.toLowerCase();
        return (
          r.full_name.toLowerCase().includes(query) ||
          (r.description?.toLowerCase().includes(query) ?? false) ||
          (r.language?.toLowerCase().includes(query) ?? false)
        );
      })
    : baseSectionRepos;
  
  const displayRepos = allDisplayRepos.slice(0, visibleCount);
  const hasMore = visibleCount < allDisplayRepos.length;

  // Reset visible count when filter/section/search changes
  useEffect(() => { setVisibleCount(PAGE_STEP); }, [language, section, searchQuery]);

  // IntersectionObserver to auto-reveal more repos
  const observerRef = useRef<IntersectionObserver | null>(null);
  const setSentinel = useCallback((node: HTMLDivElement | null) => {
    sentinelRef.current = node;
    if (observerRef.current) observerRef.current.disconnect();
    if (!node) return;
    observerRef.current = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          setVisibleCount(c => c + PAGE_STEP);
        }
      },
      { rootMargin: '300px' },
    );
    observerRef.current.observe(node);
  }, []);
  useEffect(() => () => { observerRef.current?.disconnect(); }, []);

  const radarData = React.useMemo(() => {
    const topicCount: Record<string, number> = {};
    for (const r of repos) for (const t of (r.topics || [])) topicCount[t] = (topicCount[t] || 0) + 1;
    return Object.entries(topicCount)
      .sort((a, b) => b[1] - a[1]).slice(0, 12)
      .map(([name, count]) => ({ topic: name, score: Math.min(count * 8, 100) }));
  }, [repos]);

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="pb-12">

        {/* ── Compact Header (GitHub Radar style) ── */}
        <div className="px-6 pt-6 pb-4 border-b border-slate-200 dark:border-slate-800">
          <div className="flex flex-col sm:flex-row sm:items-center gap-3">
            {/* Title */}
            <div className="flex items-center gap-2.5 shrink-0">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-emerald-500 to-cyan-600 flex items-center justify-center shadow-md shadow-emerald-500/25">
                <GitBranch size={15} className="text-white" />
              </div>
              <div>
                <h1 className="text-base font-bold text-slate-900 dark:text-white leading-none">GitHub Radar</h1>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                  {repos.length > 0 ? `${repos.length.toLocaleString()} repositories tracked` : 'Trending repositories'}
                </p>
              </div>
            </div>

            {/* Search */}
            <div className="relative flex-1 min-w-0">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search repos by name, description, or language…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-8 pr-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 shadow-sm"
              />
            </div>
          </div>

          {/* Language pills with icons */}
          <div className="flex items-center gap-2 mt-3 overflow-x-auto scrollbar-hide pb-0.5">
            {LANGUAGES.map(lang => (
              <button key={lang} onClick={() => setLanguage(lang)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold transition-all whitespace-nowrap shrink-0 ${
                  language === lang
                    ? 'bg-emerald-600 text-white shadow-sm'
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-emerald-50 hover:text-emerald-700 dark:hover:bg-emerald-900/30 dark:hover:text-emerald-300'
                }`}>
                {LANG_ICONS[lang] ?? null}
                {lang}
              </button>
            ))}
          </div>
        </div>

        <div className="px-6 mt-6 space-y-10">

          {/* ── Repo grid ── */}
          <section>

            {isLoading ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {Array.from({ length: 6 }).map((_, i) => <div key={i} className="bg-slate-100 dark:bg-slate-800 rounded-2xl h-48 animate-pulse" />)}
              </div>
            ) : displayRepos.length === 0 ? (
              <div className="text-center py-16 text-slate-400">
                <Sparkles size={40} className="mx-auto mb-4 opacity-30" />
                <p className="font-medium">{section === 'rising' ? 'No rising stars yet' : 'No repos found'}</p>
                <p className="text-sm mt-1">Star velocity is computed daily at 04:00 UTC.</p>
              </div>
            ) : (
              <>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {displayRepos.map((repo) => <RepoCard key={repo.id} repo={repo} />)}
                </div>
                {/* Infinite reveal sentinel */}
                <div ref={setSentinel} className="flex justify-center py-8">
                  {hasMore ? (
                    <div className="flex items-center gap-2 text-slate-400 text-sm">
                      <span className="w-4 h-4 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
                      Loading more repos…
                    </div>
                  ) : allDisplayRepos.length > 0 ? (
                    <p className="text-slate-400 text-sm">✅ All {allDisplayRepos.length} repos shown</p>
                  ) : null}
                </div>
              </>
            )}
          </section>

        </div>
      </div>
    </div>
  );
}
