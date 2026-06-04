'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import { api } from '@/utils/api';

// ── Types ─────────────────────────────────────────────────────────────────────

interface DailyRun { date: string; success: number; failed: number; total: number; }
interface ActionCount { action: string; count: number; label: string; }
interface TopWorkflow {
  workflow_id: string; name: string;
  total: number; success: number; failed: number; success_rate: number;
}
interface TotalStats {
  total_workflows: number; active_workflows: number;
  total_runs: number; success_runs: number; failed_runs: number;
  success_rate: number; avg_duration_seconds: number | null;
}
interface Analytics {
  period_days: number;
  total_stats: TotalStats;
  runs_over_time: DailyRun[];
  action_distribution: ActionCount[];
  top_workflows: TopWorkflow[];
}

// ── Constants ─────────────────────────────────────────────────────────────────

const PERIOD_OPTIONS = [
  { label: '7d', days: 7 },
  { label: '14d', days: 14 },
  { label: '30d', days: 30 },
  { label: '90d', days: 90 },
];

const ACTION_COLORS: Record<string, string> = {
  collect_news:      '#6366f1',
  summarize_content: '#8b5cf6',
  generate_pdf:      '#06b6d4',
  send_email:        '#10b981',
  upload_to_drive:   '#f59e0b',
  ai_digest:         '#ec4899',
};
const FALLBACK_COLORS = ['#6366f1', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ec4899', '#14b8a6'];

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDate(dateStr: string) {
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function StatCard({ label, value, sub, color = 'text-slate-900 dark:text-white' }: { label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl p-4">
      <p className="text-xs text-slate-400 mb-1">{label}</p>
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      {sub && <p className="text-xs text-slate-500 mt-0.5">{sub}</p>}
    </div>
  );
}

// ── Custom Tooltip ────────────────────────────────────────────────────────────

function RunsTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ name: string; value: number; color: string }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-3 shadow-xl text-xs">
      <p className="text-slate-700 dark:text-slate-300 font-medium mb-2">{label ? formatDate(label) : ''}</p>
      {payload.map(p => (
        <p key={p.name} style={{ color: p.color }} className="mb-0.5">
          {p.name}: <span className="font-bold">{p.value}</span>
        </p>
      ))}
    </div>
  );
}

function PieTooltip({ active, payload }: { active?: boolean; payload?: Array<{ name: string; value: number }> }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-3 shadow-xl text-xs">
      <p className="text-slate-600 dark:text-slate-300">{payload[0].name}: <span className="font-bold text-slate-900 dark:text-white">{payload[0].value}</span></p>
    </div>
  );
}

// ── AnalyticsModal ─────────────────────────────────────────────────────────────

export function AnalyticsModal({ onClose }: { onClose: () => void }) {
  const [days, setDays] = useState(30);

  const { data, isLoading, error } = useQuery<Analytics>({
    queryKey: ['workflow-analytics', days],
    queryFn: async () => {
      const { data } = await api.get(`/automation/analytics/?days=${days}`);
      return data;
    },
    staleTime: 60_000,
  });

  const stats = data?.total_stats;
  const runsData = (data?.runs_over_time ?? []).filter(r => r.total > 0 || r.date > new Date(Date.now() - 7 * 86400_000).toISOString().slice(0, 10));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl w-full max-w-4xl shadow-2xl flex flex-col max-h-[90vh]">

        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-200 dark:border-slate-700">
          <div>
            <h2 className="text-lg font-semibold text-slate-800 dark:text-white">📊 Workflow Analytics</h2>
            <p className="text-xs text-slate-400 mt-0.5">Run performance, action usage, and top workflows.</p>
          </div>
          <div className="flex items-center gap-3">
            {/* Period selector */}
            <div className="flex bg-white dark:bg-slate-900 rounded-lg p-0.5 border border-slate-200 dark:border-slate-700">
              {PERIOD_OPTIONS.map(opt => (
                <button key={opt.days} onClick={() => setDays(opt.days)}
                  className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                    days === opt.days ? 'bg-indigo-600 text-white' : 'text-slate-600 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-300'
                  }`}>
                  {opt.label}
                </button>
              ))}
            </div>
            <button onClick={onClose} className="text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-white text-xl transition-colors">✕</button>
          </div>
        </div>

        {/* Body */}
        <div className="overflow-y-auto flex-1 p-5 space-y-6">

          {isLoading && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[...Array(4)].map((_, i) => <div key={i} className="h-20 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl animate-pulse" />)}
            </div>
          )}

          {error && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-red-400 text-sm">
              ⚠️ Could not load analytics. Please try again.
            </div>
          )}

          {data && (
            <>
              {/* Stat cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <StatCard label="Total Runs" value={stats?.total_runs ?? 0} sub={`Last ${days} days`} />
                <StatCard
                  label="Success Rate"
                  value={`${stats?.success_rate ?? 0}%`}
                  sub={`${stats?.success_runs} ✅  ${stats?.failed_runs} ❌`}
                  color={
                    (stats?.success_rate ?? 0) >= 80 ? 'text-green-600 dark:text-green-400'
                    : (stats?.success_rate ?? 0) >= 50 ? 'text-yellow-400'
                    : 'text-red-400'
                  }
                />
                <StatCard label="Active Workflows" value={`${stats?.active_workflows ?? 0} / ${stats?.total_workflows ?? 0}`} />
                <StatCard
                  label="Avg Duration"
                  value={stats?.avg_duration_seconds != null ? `${stats.avg_duration_seconds.toFixed(1)}s` : '—'}
                  sub="Per run"
                />
              </div>

              {/* Runs over time chart */}
              <div className="bg-white/80 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-700 rounded-xl p-4">
                <p className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-4">Runs Over Time</p>
                {runsData.length === 0 ? (
                  <div className="h-48 flex items-center justify-center text-slate-500 text-sm">No runs in this period.</div>
                ) : (
                  <ResponsiveContainer width="100%" height={200}>
                    <AreaChart data={runsData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                      <defs>
                        <linearGradient id="successGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="failedGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                      <XAxis dataKey="date" tickFormatter={formatDate} tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} interval={Math.ceil(runsData.length / 7)} />
                      <YAxis tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} allowDecimals={false} />
                      <Tooltip content={<RunsTooltip />} />
                      <Legend wrapperStyle={{ fontSize: '11px', color: '#94a3b8' }} />
                      <Area type="monotone" dataKey="success" name="Success" stroke="#10b981" strokeWidth={2} fill="url(#successGrad)" />
                      <Area type="monotone" dataKey="failed" name="Failed" stroke="#ef4444" strokeWidth={2} fill="url(#failedGrad)" />
                    </AreaChart>
                  </ResponsiveContainer>
                )}
              </div>

              {/* Bottom row: Action distribution + Top workflows */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

                {/* Action distribution pie */}
                <div className="bg-white/80 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-700 rounded-xl p-4">
                  <p className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-3">Action Distribution</p>
                  {data.action_distribution.length === 0 ? (
                    <div className="h-48 flex items-center justify-center text-slate-500 text-sm">No actions configured.</div>
                  ) : (
                    <div className="flex items-center gap-4">
                      <ResponsiveContainer width="55%" height={180}>
                        <PieChart>
                          <Pie
                            data={data.action_distribution}
                            dataKey="count"
                            nameKey="label"
                            cx="50%" cy="50%"
                            innerRadius={45} outerRadius={75}
                            paddingAngle={2}
                          >
                            {data.action_distribution.map((entry, i) => (
                              <Cell key={entry.action} fill={ACTION_COLORS[entry.action] ?? FALLBACK_COLORS[i % FALLBACK_COLORS.length]} />
                            ))}
                          </Pie>
                          <Tooltip content={<PieTooltip />} />
                        </PieChart>
                      </ResponsiveContainer>
                      <div className="flex-1 space-y-1.5">
                        {data.action_distribution.map((entry, i) => (
                          <div key={entry.action} className="flex items-center gap-2">
                            <div className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                              style={{ backgroundColor: ACTION_COLORS[entry.action] ?? FALLBACK_COLORS[i % FALLBACK_COLORS.length] }} />
                            <span className="text-xs text-slate-400 flex-1 truncate">{entry.label}</span>
                            <span className="text-xs font-medium text-slate-800 dark:text-white">{entry.count}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Top workflows bar */}
                <div className="bg-white/80 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-700 rounded-xl p-4">
                  <p className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-3">Top Workflows by Runs</p>
                  {data.top_workflows.length === 0 ? (
                    <div className="h-48 flex items-center justify-center text-slate-500 text-sm">No runs yet.</div>
                  ) : (
                    <>
                      <ResponsiveContainer width="100%" height={150}>
                        <BarChart data={data.top_workflows} layout="vertical" margin={{ top: 0, right: 10, left: 0, bottom: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#334155" horizontal={false} />
                          <XAxis type="number" tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} allowDecimals={false} />
                          <YAxis type="category" dataKey="name" width={0} tick={false} axisLine={false} tickLine={false} />
                          <Tooltip formatter={(v, n) => [v, n === 'success' ? '✅ Success' : '❌ Failed']}
                            contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8, fontSize: 12 }}
                            labelStyle={{ color: '#cbd5e1' }} />
                          <Bar dataKey="success" name="success" stackId="a" fill="#10b981" radius={[0, 0, 0, 0]} />
                          <Bar dataKey="failed" name="failed" stackId="a" fill="#ef4444" radius={[0, 4, 4, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                      <div className="mt-3 space-y-1.5">
                        {data.top_workflows.map((wf, i) => (
                          <div key={wf.workflow_id} className="flex items-center gap-2">
                            <span className="text-xs text-slate-500 w-4">{i + 1}.</span>
                            <span className="text-xs text-slate-600 dark:text-slate-300 flex-1 truncate">{wf.name}</span>
                            <span className="text-xs text-slate-500">{wf.total} runs</span>
                            <span className={`text-xs font-medium ${wf.success_rate >= 80 ? 'text-green-600 dark:text-green-400' : wf.success_rate >= 50 ? 'text-yellow-400' : 'text-red-400'}`}>
                              {wf.success_rate}%
                            </span>
                          </div>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
