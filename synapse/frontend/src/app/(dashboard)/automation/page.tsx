'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';
import Link from 'next/link';
import { api } from '@/utils/api';
import { useAuthStore } from '@/store/authStore';
// TASK-104-2: Modals moved to global /components/modals/ for reusability
import { EditWorkflowModal } from '@/components/modals/EditWorkflowModal';
import { TemplatesModal } from '@/components/modals/TemplatesModal';
import { ScheduleModal } from '@/components/modals/ScheduleModal';
import { AnalyticsModal } from '@/components/modals/AnalyticsModal';

// ── Types ─────────────────────────────────────────────────────────────────────

type ActionType = 'scrape_videos' | 'scrape_tweets' | 'collect_news' | 'summarize_content' | 'generate_pdf' | 'send_email' | 'upload_to_drive' | 'ai_digest';
type TriggerType = 'schedule' | 'event' | 'manual';
type EventType = 'new_article' | 'trending_spike' | 'new_paper' | 'new_repo';

interface ActionParamField {
  type: 'text' | 'textarea' | 'number' | 'select' | 'multiselect';
  label: string;
  default: string | number | string[];
  options?: string[];
  min?: number;
  max?: number;
  help?: string;
}

interface ActionSchema {
  [paramKey: string]: ActionParamField;
}

interface ActionSchemas {
  [actionType: string]: ActionSchema;
}

interface WorkflowAction {
  type: ActionType;
  params?: Record<string, unknown>;
}

interface EventConfig {
  event_type?: EventType;
  filter?: { topic?: string };
  cooldown_minutes?: number;
}

interface Workflow {
  id: string;
  name: string;
  description: string;
  trigger_type: TriggerType;
  cron_expression: string;
  event_config: EventConfig;
  actions: WorkflowAction[];
  is_active: boolean;
  status: 'active' | 'paused' | 'failed';
  last_run_at: string | null;
  next_run_at: string | null;
  run_count: number;
  created_at: string;
  runs_count: number;
  last_run_status: string | null;
  last_run_id: string | null;
}

interface WorkflowRun {
  id: string;
  workflow: string;
  status: 'pending' | 'running' | 'success' | 'failed';
  celery_task_id: string;
  trigger_event: Record<string, unknown>;
  started_at: string;
  completed_at: string | null;
  result: Record<string, unknown>;
  error_message: string;
  duration_seconds: number | null;
}

// ── API helpers ───────────────────────────────────────────────────────────────

function extractList<T>(raw: unknown): T[] {
  if (Array.isArray(raw)) return raw as T[];
  if (raw && typeof raw === 'object') {
    const obj = raw as Record<string, unknown>;
    if (Array.isArray(obj['data'])) return obj['data'] as T[];
    if (Array.isArray(obj['results'])) return obj['results'] as T[];
  }
  return [];
}

const fetchWorkflows = async (): Promise<Workflow[]> => {
  const { data } = await api.get('/automation/workflows/');
  const list = extractList<Workflow>(data);
  if (Array.isArray(data)) return data as Workflow[];
  return list;
};

const fetchRuns = async (workflowId: string): Promise<WorkflowRun[]> => {
  const { data } = await api.get(`/automation/workflows/${workflowId}/runs/`);
  return extractList<WorkflowRun>(data);
};

const fetchRunStatus = async (runId: string): Promise<WorkflowRun> => {
  const { data } = await api.get(`/automation/runs/${runId}/status/`);
  return data as WorkflowRun;
};

// Static fallback schemas — shown immediately while API loads (or if offline)
const STATIC_ACTION_SCHEMAS: ActionSchemas = {
  scrape_tweets: {
    queries:     { type: 'textarea',     label: 'Search Queries (one per line)',  default: 'AI machine learning\nPython programming\nWeb development trends\nCybersecurity news\nCloud computing\nDevOps automation', help: 'Each line is a separate X/Twitter search query. Leave blank to use defaults.' },
    max_results: { type: 'number',       label: 'Max Tweets to Fetch',            default: 100, min: 10, max: 500 },
    topics:      { type: 'multiselect',  label: 'Topic Categories',               default: ['AI','Web Dev','Security','Cloud','Research','Programming','Tech'], options: ['AI','Web Dev','Security','Cloud','Research','Programming','Tech'] },
  },
  scrape_videos: {
    queries:     { type: 'textarea',     label: 'Search Queries (one per line)',  default: 'machine learning tutorial\nAI agents explained\nLLM fine-tuning\nPython data science', help: 'Each line is a separate YouTube search query. Leave blank to use defaults.' },
    max_results: { type: 'number',       label: 'Max Videos to Fetch',            default: 20, min: 5, max: 100 },
    days_back:   { type: 'number',       label: 'Days Back (recency filter)',      default: 30, min: 1, max: 365 },
    categories:  { type: 'multiselect',  label: 'Topic Categories',               default: ['AI / ML','Programming'], options: ['AI / ML','Programming','DevOps','Data Science','Web Dev','Security','Cloud','Open Source'] },
  },
  collect_news: {
    sources:          { type: 'multiselect', label: 'Sources',                              default: ['hackernews','github','arxiv','youtube','twitter'], options: ['hackernews','github','arxiv','youtube','twitter'] },
    items_per_source: { type: 'number',      label: 'Items per source (1–500)',             default: 100, min: 1, max: 500 },
    days_back:        { type: 'number',      label: 'Days back (1–30)',                     default: 7, min: 1, max: 30 },
    story_type:       { type: 'select',      label: 'HN Story Type',                        default: 'top', options: ['top','new','best'] },
    youtube_queries:  { type: 'textarea',    label: 'YouTube Search Queries (one per line)', default: '', help: 'Optional — only used when YouTube is selected.' },
    twitter_queries:  { type: 'textarea',    label: 'X/Twitter Search Queries (one per line)', default: '', help: 'Optional — only used when X/Twitter is selected.' },
  },
  summarize_content: {
    batch_size: { type: 'number', label: 'Batch size', default: 20, min: 1, max: 200 },
  },
  generate_pdf: {
    title:         { type: 'text',   label: 'Report Title',            default: 'SYNAPSE Report' },
    subtitle:      { type: 'text',   label: 'Subtitle',                default: 'Auto-generated by SYNAPSE' },
    author:        { type: 'text',   label: 'Author',                  default: 'SYNAPSE Automation' },
    topic:         { type: 'text',   label: 'Topic Filter (optional)', default: '' },
    article_limit: { type: 'number', label: 'Max articles to include', default: 5, min: 1, max: 20 },
  },
  send_email: {
    subject: { type: 'text',     label: 'Email Subject', default: '' },
    body:    { type: 'textarea', label: 'Email Body',    default: '' },
  },
  upload_to_drive: {
    file_path:   { type: 'text', label: 'File Path',         default: '' },
    folder_name: { type: 'text', label: 'Drive Folder Name', default: 'SYNAPSE' },
  },
  ai_digest: {
    topic: { type: 'text', label: 'Research Topic', default: 'latest AI research and tech news' },
  },
};

const fetchActionSchemas = async (): Promise<ActionSchemas> => {
  const { data } = await api.get('/automation/action-schemas/');
  return data as ActionSchemas;
};

const createWorkflow = async (payload: unknown) => {
  const { data } = await api.post('/automation/workflows/', payload);
  return data;
};

const deleteWorkflow = async (id: string) => {
  await api.delete(`/automation/workflows/${id}/`);
};

const triggerWorkflow = async (id: string): Promise<{ celery_task_id: string; workflow_id: string; run_id: string }> => {
  const { data } = await api.post(`/automation/workflows/${id}/trigger/`);
  return data;
};

const toggleWorkflow = async (id: string) => {
  const { data } = await api.post(`/automation/workflows/${id}/toggle/`);
  return data;
};

// ── Constants ─────────────────────────────────────────────────────────────────

const ACTION_LABELS: Record<string, string> = {
  collect_news:      '📰 Collect News',
  scrape_hackernews: '🔶 Scrape HackerNews',
  scrape_github:     '🐙 Scrape GitHub',
  scrape_arxiv:      '📜 Scrape arXiv',
  scrape_videos:     '🎬 Scrape Videos',
  scrape_tweets:     '🐦 Scrape Tweets',
  summarize_content: '🤖 Summarize Content',
  generate_pdf:      '📄 Generate PDF',
  send_email:        '📧 Send Email',
  upload_to_drive:   '☁️ Upload to Drive',
  ai_digest:         '🧠 AI Digest',
};

const STATUS_STYLES: Record<string, string> = {
  active:  'bg-green-500/20 text-green-400 border border-green-500/30',
  paused:  'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30',
  failed:  'bg-red-500/20 text-red-400 border border-red-500/30',
  success: 'bg-green-500/20 text-green-400 border border-green-500/30',
  running: 'bg-blue-500/20 text-blue-400 border border-blue-500/30 animate-pulse',
  pending: 'bg-slate-500/20 text-slate-400 border border-slate-500/30',
};

const CRON_PRESETS = [
  { label: 'Every 30 minutes', value: '*/30 * * * *' },
  { label: 'Every hour',       value: '0 * * * *' },
  { label: 'Every 6 hours',    value: '0 */6 * * *' },
  { label: 'Daily at midnight',value: '0 0 * * *' },
  { label: 'Daily at 8am',     value: '0 8 * * *' },
  { label: 'Every Monday 9am', value: '0 9 * * 1' },
  { label: 'Custom',           value: '' },
];

const EVENT_TYPE_OPTIONS: { value: EventType; label: string }[] = [
  { value: 'new_article',    label: '📰 New Article Published' },
  { value: 'trending_spike', label: '📈 Trending Topic Spike' },
  { value: 'new_paper',      label: '🔬 New Research Paper' },
  { value: 'new_repo',       label: '💻 New Repository Trending' },
];

const ACTION_TYPES = Object.keys(ACTION_LABELS) as ActionType[];

// ── StatusBadge ───────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLES[status] ?? 'bg-slate-200 dark:bg-slate-600 text-slate-700 dark:text-slate-300'}`}>
      {status === 'running' ? '⟳ Running' : status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

// ── Action Parameter Editor ───────────────────────────────────────────────────

function ActionParamEditor({
  action,
  schema,
  onChange,
}: {
  action: WorkflowAction;
  schema: ActionSchema | undefined;
  onChange: (params: Record<string, unknown>) => void;
}) {
  if (!schema) return null;
  const params = action.params || {};

  // Compute before return so it's in scope inside the map callback
  const selectedSources: string[] = Array.isArray(params.sources)
    ? (params.sources as string[])
    : Array.isArray(schema.sources?.default)
    ? (schema.sources.default as string[])
    : [];
  const youtubeSelected = selectedSources.includes('youtube');
  const twitterSelected = selectedSources.includes('twitter');

  return (
    <div className="mt-2 ml-2 pl-3 border-l-2 border-indigo-500/30 space-y-2">
      {Object.entries(schema).map(([key, field]) => {
        // Hide youtube_queries unless youtube is selected in sources
        if (key === 'youtube_queries' && !youtubeSelected) return null;
        // Hide twitter_queries unless twitter is selected in sources
        if (key === 'twitter_queries' && !twitterSelected) return null;
        const val = params[key] ?? field.default;
        const inputClass = "w-full bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-600 rounded px-2 py-1.5 text-slate-800 dark:text-white text-xs focus:outline-none focus:border-indigo-500";

        if (field.type === 'multiselect' && field.options) {
          const selected = (Array.isArray(val) ? val : field.default) as string[];
          return (
            <div key={key}>
              <label className="block text-xs text-slate-400 mb-1">{field.label}</label>
              <div className="flex flex-wrap gap-1.5">
                {field.options.map(opt => (
                  <button
                    key={opt}
                    type="button"
                    onClick={() => {
                      const next = selected.includes(opt)
                        ? selected.filter(s => s !== opt)
                        : [...selected, opt];
                      onChange({ ...params, [key]: next });
                    }}
                    className={`text-xs px-2 py-1 rounded border transition-colors ${
                      selected.includes(opt)
                        ? 'bg-indigo-600 border-indigo-500 text-white'
                        : 'bg-slate-100 dark:bg-slate-700 border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-400 hover:border-slate-400 dark:hover:border-slate-500'
                    }`}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            </div>
          );
        }

        if (field.type === 'select' && field.options) {
          return (
            <div key={key}>
              <label className="block text-xs text-slate-400 mb-1">{field.label}</label>
              <select
                value={val as string}
                onChange={e => onChange({ ...params, [key]: e.target.value })}
                className={inputClass}
              >
                {field.options.map(opt => <option key={opt} value={opt}>{opt}</option>)}
              </select>
            </div>
          );
        }

        if (field.type === 'number') {
          return (
            <div key={key}>
              <label className="block text-xs text-slate-400 mb-1">
                {field.label}
                {field.min !== undefined && field.max !== undefined && (
                  <span className="text-slate-500 ml-1">({field.min}–{field.max})</span>
                )}
              </label>
              <input
                type="number"
                value={val as number}
                min={field.min}
                max={field.max}
                onChange={e => onChange({ ...params, [key]: Number(e.target.value) })}
                className={inputClass}
              />
            </div>
          );
        }

        if (field.type === 'textarea') {
          return (
            <div key={key}>
              <label className="block text-xs text-slate-400 mb-1">{field.label}</label>
              <textarea
                value={val as string}
                rows={3}
                onChange={e => onChange({ ...params, [key]: e.target.value })}
                className={`${inputClass} resize-none`}
              />
            </div>
          );
        }

        // text
        return (
          <div key={key}>
            <label className="block text-xs text-slate-400 mb-1">{field.label}</label>
            <input
              type="text"
              value={val as string}
              onChange={e => onChange({ ...params, [key]: e.target.value })}
              className={inputClass}
            />
          </div>
        );
      })}
    </div>
  );
}

// ── WorkflowCard ──────────────────────────────────────────────────────────────

function WorkflowCard({
  workflow,
  onTrigger,
  onToggle,
  onDelete,
  onEdit,
  onViewRuns,
  liveRunId,
  liveStatus,
}: {
  workflow: Workflow;
  onTrigger: (id: string) => void;
  onToggle: (id: string) => void;
  onDelete: (id: string) => void;
  onEdit: (workflow: Workflow) => void;
  onViewRuns: (workflow: Workflow) => void;
  liveRunId: string | null;
  liveStatus: WorkflowRun | null;
}) {
  // liveStatus is null only in the brief window between startLiveRun() seeding
  // the runId and the first poll response arriving (~2.5 s). We treat that as
  // "running" so the card immediately shows the progress bar.  Once the timer
  // clears (success/failed) liveRunId itself is removed from liveRuns, so this
  // component receives liveRunId=null and we fall back to workflow.status.
  const isRunning = liveRunId !== null && (
    liveStatus === null ||
    liveStatus.status === 'pending' ||
    liveStatus.status === 'running'
  );
  const displayStatus = isRunning
    ? 'running'
    : liveStatus?.status === 'success'
      ? 'active'
      : liveStatus?.status === 'failed'
        ? 'failed'
        : workflow.status;

  return (
    <div className={`group relative bg-white dark:bg-slate-800 border rounded-2xl p-4 sm:p-5 flex flex-col gap-3 transition-all duration-200 overflow-hidden ${isRunning ? 'border-blue-500/50 shadow-blue-500/10 shadow-lg' : 'border-slate-200 dark:border-slate-700 hover:border-indigo-500/50 hover:shadow-lg hover:shadow-indigo-500/5'}`}>
      {/* Accent top bar */}
      <div className={`absolute inset-x-0 top-0 h-0.5 rounded-t-2xl transition-opacity ${isRunning ? 'bg-gradient-to-r from-blue-500 to-indigo-500 opacity-100' : 'bg-gradient-to-r from-indigo-500 to-violet-500 opacity-0 group-hover:opacity-100'}`} />

      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-slate-800 dark:text-white truncate text-sm sm:text-base leading-snug">{workflow.name}</h3>
          {workflow.description && (
            <p className="text-xs sm:text-sm text-slate-400 mt-0.5 line-clamp-2 leading-relaxed">{workflow.description}</p>
          )}
        </div>
        <StatusBadge status={displayStatus} />
      </div>

      {/* Meta pills */}
      <div className="flex flex-wrap gap-1.5 text-xs text-slate-500 dark:text-slate-400">
        <span className="bg-slate-100 dark:bg-slate-700/80 border border-slate-200 dark:border-slate-600/50 rounded-lg px-2 py-0.5 whitespace-nowrap">
          {workflow.trigger_type === 'schedule'
            ? `⏱ ${workflow.cron_expression || 'cron'}`
            : workflow.trigger_type === 'event'
            ? `⚡ ${workflow.event_config?.event_type || 'event'}`
            : '🖐 Manual'}
        </span>
        <span className="bg-slate-100 dark:bg-slate-700/80 border border-slate-200 dark:border-slate-600/50 rounded-lg px-2 py-0.5 whitespace-nowrap">🔄 {workflow.run_count} runs</span>
        {workflow.last_run_at && (
          <span className="bg-slate-100 dark:bg-slate-700/80 border border-slate-200 dark:border-slate-600/50 rounded-lg px-2 py-0.5 whitespace-nowrap">
            Last: {new Date(workflow.last_run_at).toLocaleDateString()}
          </span>
        )}
      </div>

      {/* Action badges */}
      {workflow.actions.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {workflow.actions.map((a, i) => (
            <span key={i} className="text-xs bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-500/20 rounded-lg px-2 py-0.5 whitespace-nowrap">
              {ACTION_LABELS[a.type] ?? a.type}
            </span>
          ))}
        </div>
      )}

      {/* Live progress */}
      {isRunning && (
        <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-1 overflow-hidden">
          <div className="h-full bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full animate-pulse w-full" />
        </div>
      )}
      {liveStatus?.status === 'success' && (
        <p className="text-xs text-emerald-400 font-medium">✅ Completed in {liveStatus.duration_seconds?.toFixed(1)}s</p>
      )}
      {liveStatus?.status === 'failed' && (
        <p className="text-xs text-red-400 line-clamp-1">❌ {liveStatus.error_message || 'Run failed'}</p>
      )}

      {/* Action buttons — responsive wrap on xs */}
      <div className="flex flex-wrap gap-1.5 pt-1">
        <button
          onClick={() => onTrigger(workflow.id)}
          disabled={!workflow.is_active || isRunning}
          className="flex-1 min-w-[80px] bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs sm:text-sm py-1.5 px-3 rounded-xl transition-colors font-semibold whitespace-nowrap"
        >
          {isRunning ? '⟳ Running…' : '▶ Run'}
        </button>
        <div className="flex gap-1.5 shrink-0">
          <button
            onClick={() => onToggle(workflow.id)}
            className="px-2.5 py-1.5 bg-slate-200 hover:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-300 text-sm rounded-xl transition-colors"
            title={workflow.is_active ? 'Pause' : 'Resume'}
          >
            {workflow.is_active ? '⏸' : '▶'}
          </button>
          <button
            onClick={() => onEdit(workflow)}
            className="px-2.5 py-1.5 bg-slate-200 hover:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-300 text-sm rounded-xl transition-colors"
            title="Edit workflow"
          >
            ✏️
          </button>
          <button
            onClick={() => onViewRuns(workflow)}
            className="px-2.5 py-1.5 bg-slate-200 hover:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-300 text-sm rounded-xl transition-colors"
            title="View run history"
          >
            📋
          </button>
          <button
            onClick={() => onDelete(workflow.id)}
            className="px-2.5 py-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 text-sm rounded-xl transition-colors"
            title="Delete workflow"
          >
            🗑
          </button>
        </div>
      </div>
    </div>
  );
}

// ── RunHistoryModal ───────────────────────────────────────────────────────────

function RunHistoryModal({ workflow, onClose }: { workflow: Workflow; onClose: () => void }) {
  const { data: runs = [], isLoading, refetch } = useQuery({
    queryKey: ['workflow-runs', workflow.id],
    queryFn: () => fetchRuns(workflow.id),
    refetchInterval: (query) => {
      const data = query.state.data ?? [];
      return data.some((r: any) => r.status === 'running') ? 4000 : 15_000;
    },
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl w-full max-w-2xl max-h-[80vh] flex flex-col shadow-2xl">
        <div className="flex items-center justify-between p-5 border-b border-slate-200 dark:border-slate-700">
          <div>
            <h2 className="text-lg font-semibold text-slate-800 dark:text-white">
              Run History — <span className="text-indigo-600 dark:text-indigo-400">{workflow.name}</span>
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">Auto-refreshes every 4s while runs are active</p>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => refetch()} className="text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-white text-sm px-2 py-1 rounded bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 border border-slate-200 dark:border-slate-600 transition-colors">↻</button>
            <button onClick={onClose} className="text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-white transition-colors text-xl">✕</button>
          </div>
        </div>
        <div className="overflow-y-auto flex-1 p-5 space-y-2">
          {isLoading && (
            <div className="space-y-2">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="h-20 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl animate-pulse" />
              ))}
            </div>
          )}
          {!isLoading && runs.length === 0 && (
            <div className="text-center py-12">
              <div className="text-4xl mb-3">🔄</div>
              <p className="text-slate-400 text-sm font-medium">No runs yet</p>
              <p className="text-slate-600 text-xs mt-1">Trigger the workflow to see run history here</p>
            </div>
          )}
          {/* Timeline */}
          <div className="relative">
            {runs.length > 1 && (
              <div className="absolute left-[19px] top-6 bottom-6 w-px bg-slate-300 dark:bg-slate-700/60" />
            )}
            {runs.map((run, idx) => {
              const actions = (run.result as any)?.actions ?? []
              const successActions = actions.filter((a: any) => a.status === 'success' || a.status === 'queued' || a.status === 'completed' || a.status === 'notification_created').length
              const failedActions  = actions.filter((a: any) => a.status === 'error' || a.status === 'failed').length
              const isSuccess = run.status === 'success'
              const isFailed  = run.status === 'failed'
              const isRunning = run.status === 'running' || run.status === 'pending'
              return (
                <div key={run.id} className="relative flex gap-3 mb-3">
                  {/* Timeline dot */}
                  <div className={`relative z-10 w-9 h-9 rounded-xl flex items-center justify-center text-sm shrink-0 mt-0.5 border ${
                    isSuccess ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-600 dark:text-emerald-400' :
                    isFailed  ? 'bg-red-500/15 border-red-500/40 text-red-500 dark:text-red-400' :
                    isRunning ? 'bg-blue-500/15 border-blue-500/40 text-blue-500 dark:text-blue-400' :
                    'bg-slate-100 dark:bg-slate-700 border-slate-200 dark:border-slate-600 text-slate-500'
                  }`}>
                    {isSuccess ? '✓' : isFailed ? '✗' : isRunning ? '⟳' : '#'}
                  </div>

                  {/* Card */}
                  <div className={`flex-1 min-w-0 bg-white dark:bg-slate-900 border rounded-xl p-3.5 transition-all hover:border-slate-600 ${
                    isSuccess ? 'border-emerald-500/30' :
                    isFailed  ? 'border-red-500/20' :
                    isRunning ? 'border-blue-500/30 animate-pulse' :
                    'border-slate-200 dark:border-slate-700/80'
                  }`}>
                    <div className="flex items-start justify-between gap-2 flex-wrap mb-1.5">
                      <div className="flex items-center gap-2 flex-wrap">
                        <StatusBadge status={run.status} />
                        {idx === 0 && <span className="text-[10px] font-bold text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded-full border border-amber-500/20">Latest</span>}
                      </div>
                      <span className="text-xs text-slate-500 whitespace-nowrap">{new Date(run.started_at).toLocaleString('en-GB', { day:'numeric', month:'short', hour:'2-digit', minute:'2-digit' })}</span>
                    </div>

                    {/* Stats row */}
                    <div className="flex flex-wrap gap-3 text-xs text-slate-400 mb-2">
                      {run.duration_seconds != null && (
                        <span className="flex items-center gap-1">⏱ {run.duration_seconds.toFixed(1)}s</span>
                      )}
                      {actions.length > 0 && (
                        <span className="flex items-center gap-1">
                          <span className="text-emerald-400 font-semibold">{successActions}✓</span>
                          {failedActions > 0 && <span className="text-red-400 font-semibold ml-1">{failedActions}✗</span>}
                          <span className="text-slate-500">/ {actions.length} actions</span>
                        </span>
                      )}
                      {run.trigger_event && Object.keys(run.trigger_event).length > 0 && (
                        <span className="text-indigo-600 dark:text-indigo-400">⚡ {Object.keys(run.trigger_event)[0]}</span>
                      )}
                    </div>

                    {/* Action mini-progress */}
                    {actions.length > 0 && (
                      <div className="flex gap-1 mb-2">
                        {actions.map((a: any, i: number) => (
                          <div key={i} title={a.action} className={`flex-1 h-1 rounded-full ${
                            a.status === 'success' || a.status === 'queued' || a.status === 'notification_created' ? 'bg-emerald-500' :
                            a.status === 'error' || a.status === 'failed' ? 'bg-red-500' :
                            'bg-slate-600'
                          }`} />
                        ))}
                      </div>
                    )}

                    {run.error_message && (
                      <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-2.5 py-1.5 mb-2 line-clamp-2">{run.error_message}</p>
                    )}

                    <Link href={`/automation/runs/${run.id}`}
                      className="inline-flex items-center gap-1 text-xs text-indigo-600 dark:text-indigo-400 hover:text-indigo-500 dark:hover:text-indigo-300 font-semibold transition-colors">
                      View full detail →
                    </Link>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── DeleteConfirmModal ────────────────────────────────────────────────────────

function DeleteConfirmModal({
  workflow, onConfirm, onCancel, isPending,
}: { workflow: Workflow; onConfirm: () => void; onCancel: () => void; isPending: boolean }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl w-full max-w-md shadow-2xl overflow-hidden">
        <div className="h-1 w-full bg-gradient-to-r from-red-500 to-rose-600" />
        <div className="p-6">
          <div className="flex items-center gap-4 mb-4">
            <div className="w-12 h-12 rounded-full bg-red-500/15 flex items-center justify-center text-2xl">🗑</div>
            <div>
              <h2 className="text-lg font-semibold text-slate-800 dark:text-white">Delete Workflow</h2>
              <p className="text-sm text-slate-400">This action cannot be undone.</p>
            </div>
          </div>
          <div className="bg-slate-100 dark:bg-slate-900/70 border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3 mb-6">
            <p className="text-xs text-slate-400 mb-0.5">Workflow to delete</p>
            <p className="text-slate-800 dark:text-white font-medium truncate">{workflow.name}</p>
          </div>
          <div className="flex gap-3">
            <button onClick={onCancel} disabled={isPending} className="flex-1 py-2.5 bg-slate-100 hover:bg-slate-200 dark:bg-slate-700 dark:hover:bg-slate-600 disabled:opacity-50 text-slate-700 dark:text-slate-300 text-sm rounded-xl transition-colors font-medium">Cancel</button>
            <button onClick={onConfirm} disabled={isPending} className="flex-1 py-2.5 bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white text-sm rounded-xl transition-colors font-medium">
              {isPending ? 'Deleting…' : 'Delete Workflow'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── CreateWorkflowModal ───────────────────────────────────────────────────────

function CreateWorkflowModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();

  const { data: schemas = STATIC_ACTION_SCHEMAS } = useQuery({
    queryKey: ['action-schemas'],
    queryFn: fetchActionSchemas,
    staleTime: Infinity, // schemas rarely change; use static fallback until API responds
    placeholderData: STATIC_ACTION_SCHEMAS,
  });

  // Build default params for an action type from schema
  const schemaDefaults = (type: ActionType): Record<string, unknown> => {
    const schema = schemas[type];
    if (!schema) return {};
    const defaults: Record<string, unknown> = {};
    for (const [key, field] of Object.entries(schema as ActionSchema)) {
      defaults[key] = field.default;
    }
    return defaults;
  };

  const [form, setForm] = useState({
    name: '',
    description: '',
    trigger_type: 'schedule' as TriggerType,
    cron_expression: '0 * * * *',
    event_config: { event_type: 'new_article' as EventType, filter: { topic: '' }, cooldown_minutes: 60 },
    actions: [{ type: 'collect_news' as ActionType, params: {} as Record<string, unknown> }],
  });
  const [cronPreset, setCronPreset] = useState('0 * * * *');
  const [expandedActions, setExpandedActions] = useState<Set<number>>(new Set());

  const mutation = useMutation({
    mutationFn: createWorkflow,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
      toast.success('Workflow created!');
      onClose();
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string; non_field_errors?: string[] } } })
        ?.response?.data?.detail
        ?? (err as { response?: { data?: { non_field_errors?: string[] } } })
          ?.response?.data?.non_field_errors?.[0]
        ?? 'Failed to create workflow.';
      toast.error(msg);
    },
  });

  const addAction = () => {
    const type: ActionType = 'collect_news';
    setForm(f => ({ ...f, actions: [...f.actions, { type, params: schemaDefaults(type) }] }));
  };

  const removeAction = (i: number) => {
    setForm(f => ({ ...f, actions: f.actions.filter((_, idx) => idx !== i) }));
    setExpandedActions(prev => { const n = new Set(prev); n.delete(i); return n; });
  };

  const updateActionType = (i: number, type: ActionType) => {
    setForm(f => {
      const actions = [...f.actions];
      actions[i] = { type, params: schemaDefaults(type) };
      return { ...f, actions };
    });
  };

  const updateActionParams = (i: number, params: Record<string, unknown>) => {
    setForm(f => {
      const actions = [...f.actions];
      actions[i] = { ...actions[i], params };
      return { ...f, actions };
    });
  };

  const toggleExpanded = (i: number) => {
    setExpandedActions(prev => {
      const n = new Set(prev);
      n.has(i) ? n.delete(i) : n.add(i);
      return n;
    });
  };

  const handleCronPreset = (value: string) => {
    setCronPreset(value);
    if (value) setForm(f => ({ ...f, cron_expression: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Merge schema defaults into action params so empty params always have sensible values
    const actionsWithDefaults = form.actions.map(action => ({
      ...action,
      params: { ...schemaDefaults(action.type), ...action.params },
    }));
    const payload = {
      ...form,
      actions: actionsWithDefaults,
      // Clean up unused fields based on trigger type
      cron_expression: form.trigger_type === 'schedule' ? form.cron_expression : '',
      event_config: form.trigger_type === 'event' ? form.event_config : {},
    };
    mutation.mutate(payload);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl w-full max-w-lg shadow-2xl flex flex-col max-h-[90vh]">
        <div className="flex items-center justify-between p-5 border-b border-slate-200 dark:border-slate-700 shrink-0">
          <h2 className="text-lg font-semibold text-slate-800 dark:text-white">Create Workflow</h2>
          <button onClick={onClose} className="text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-white transition-colors text-xl">✕</button>
        </div>

        <form id="create-workflow-form" onSubmit={handleSubmit} className="p-5 space-y-4 overflow-y-auto flex-1">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-slate-600 dark:text-slate-300 mb-1">Workflow Name *</label>
            <input type="text" required value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              placeholder="e.g. Daily Tech Digest"
              className="w-full bg-slate-100 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg px-3 py-2 text-slate-800 dark:text-white text-sm placeholder-slate-500 focus:outline-none focus:border-indigo-500" />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-slate-600 dark:text-slate-300 mb-1">Description</label>
            <textarea value={form.description} rows={2}
              onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
              placeholder="What does this workflow do?"
              className="w-full bg-slate-100 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg px-3 py-2 text-slate-800 dark:text-white text-sm placeholder-slate-500 focus:outline-none focus:border-indigo-500 resize-none" />
          </div>

          {/* Trigger Type */}
          <div>
            <label className="block text-sm font-medium text-slate-600 dark:text-slate-300 mb-1">Trigger Type</label>
            <div className="grid grid-cols-3 gap-2">
              {(['schedule', 'event', 'manual'] as TriggerType[]).map(t => (
                <button key={t} type="button"
                  onClick={() => setForm(f => ({ ...f, trigger_type: t }))}
                  className={`py-2 rounded-lg text-sm font-medium border transition-colors ${
                    form.trigger_type === t
                      ? 'bg-indigo-600 border-indigo-500 text-white'
                      : 'bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-400 hover:border-slate-400'
                  }`}>
                  {t === 'schedule' ? '⏱ Schedule' : t === 'event' ? '⚡ Event' : '🖐 Manual'}
                </button>
              ))}
            </div>
          </div>

          {/* Schedule config */}
          {form.trigger_type === 'schedule' && (
            <div className="space-y-2 p-3 bg-slate-100 dark:bg-slate-900/60 rounded-lg border border-slate-200 dark:border-slate-700">
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">Cron Schedule</label>
              <select value={cronPreset} onChange={e => handleCronPreset(e.target.value)}
                className="w-full bg-slate-100 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg px-3 py-2 text-slate-800 dark:text-white text-sm focus:outline-none focus:border-indigo-500">
                {CRON_PRESETS.map(p => <option key={p.label} value={p.value}>{p.label}</option>)}
              </select>
              <input type="text" value={form.cron_expression}
                onChange={e => setForm(f => ({ ...f, cron_expression: e.target.value }))}
                placeholder="*/30 * * * *"
                className="w-full bg-slate-100 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg px-3 py-2 text-slate-800 dark:text-white text-sm font-mono placeholder-slate-500 focus:outline-none focus:border-indigo-500" />
              <p className="text-xs text-slate-500">Format: minute hour day month weekday</p>
            </div>
          )}

          {/* Event trigger config */}
          {form.trigger_type === 'event' && (
            <div className="space-y-3 p-3 bg-slate-100 dark:bg-slate-900/60 rounded-lg border border-slate-200 dark:border-slate-700">
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">Event Configuration</label>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Event Type *</label>
                <select value={form.event_config.event_type}
                  onChange={e => setForm(f => ({ ...f, event_config: { ...f.event_config, event_type: e.target.value as EventType } }))}
                  className="w-full bg-slate-100 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg px-3 py-2 text-slate-800 dark:text-white text-sm focus:outline-none focus:border-indigo-500">
                  {EVENT_TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Topic Filter <span className="text-slate-500">(optional)</span></label>
                <input type="text" value={form.event_config.filter?.topic || ''}
                  onChange={e => setForm(f => ({ ...f, event_config: { ...f.event_config, filter: { topic: e.target.value } } }))}
                  placeholder="e.g. AI, React, Python — leave blank to match all"
                  className="w-full bg-slate-100 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg px-3 py-2 text-slate-800 dark:text-white text-sm placeholder-slate-500 focus:outline-none focus:border-indigo-500" />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Cooldown (minutes)</label>
                <input type="number" min={1} max={1440} value={form.event_config.cooldown_minutes ?? 60}
                  onChange={e => setForm(f => ({ ...f, event_config: { ...f.event_config, cooldown_minutes: Number(e.target.value) } }))}
                  className="w-full bg-slate-100 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg px-3 py-2 text-slate-800 dark:text-white text-sm focus:outline-none focus:border-indigo-500" />
                <p className="text-xs text-slate-500 mt-1">Minimum minutes between re-fires for the same workflow.</p>
              </div>
            </div>
          )}

          {/* Actions */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Actions *</label>
              <button type="button" onClick={addAction} className="text-xs text-indigo-600 dark:text-indigo-400 hover:text-indigo-500 dark:hover:text-indigo-300 transition-colors">+ Add Action</button>
            </div>
            <div className="space-y-2">
              {form.actions.map((action, i) => (
                <div key={i} className="bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-700 rounded-lg p-3">
                  <div className="flex gap-2 items-center">
                    <select value={action.type} onChange={e => updateActionType(i, e.target.value as ActionType)}
                      className="flex-1 bg-slate-100 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg px-3 py-2 text-slate-800 dark:text-white text-sm focus:outline-none focus:border-indigo-500">
                      {ACTION_TYPES.map(t => <option key={t} value={t}>{ACTION_LABELS[t]}</option>)}
                    </select>
                    {schemas[action.type] && (
                      <button type="button" onClick={() => toggleExpanded(i)}
                        className={`px-2 py-2 rounded-lg text-xs border transition-colors ${
                          expandedActions.has(i)
                            ? 'bg-indigo-600/20 border-indigo-500/50 text-indigo-400'
                            : 'bg-slate-100 dark:bg-slate-800 border-slate-300 dark:border-slate-600 text-slate-500 dark:text-slate-400 hover:border-slate-400 dark:hover:border-slate-500'
                        }`} title="Configure parameters">
                        ⚙️
                      </button>
                    )}
                    {form.actions.length > 1 && (
                      <button type="button" onClick={() => removeAction(i)} className="text-red-400 hover:text-red-300 transition-colors px-2">✕</button>
                    )}
                  </div>
                  {expandedActions.has(i) && (
                    <ActionParamEditor
                      action={action}
                      schema={schemas[action.type]}
                      onChange={params => updateActionParams(i, params)}
                    />
                  )}
                </div>
              ))}
            </div>
            <p className="text-xs text-slate-500 mt-1.5">Click ⚙️ to configure parameters for each action.</p>
          </div>

        </form>

        {/* Sticky footer — always visible */}
        <div className="flex gap-3 p-5 pt-3 border-t border-slate-200 dark:border-slate-700 shrink-0">
          <button type="button" onClick={onClose} className="flex-1 py-2 bg-slate-200 hover:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-300 text-sm rounded-lg transition-colors">Cancel</button>
          <button type="submit" form="create-workflow-form" disabled={mutation.isPending}
            className="flex-1 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm rounded-lg transition-colors font-medium">
            {mutation.isPending ? 'Creating…' : 'Create Workflow'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function AutomationPage() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);
  const [showSchedule, setShowSchedule] = useState(false);
  const [showAnalytics, setShowAnalytics] = useState(false);
  const [workflowToEdit, setWorkflowToEdit] = useState<Workflow | null>(null);
  const [selectedWorkflow, setSelectedWorkflow] = useState<Workflow | null>(null);
  const [workflowToDelete, setWorkflowToDelete] = useState<Workflow | null>(null);

  // Map workflowId → { runId, liveStatus }
  const [liveRuns, setLiveRuns] = useState<Record<string, { runId: string; status: WorkflowRun | null }>>({});

  // Stable ref to per-workflow polling intervals — lives outside React state
  // so it is never stale and never triggers re-renders.
  const pollTimers = useRef<Record<string, ReturnType<typeof setInterval>>>({});

  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  const { data: workflows = [], isLoading, isError, error, refetch } = useQuery({
    queryKey: ['workflows'],
    queryFn: fetchWorkflows,
    refetchInterval: isAuthenticated ? 30_000 : false,
    enabled: isAuthenticated,
    retry: false,
  });

  // ── Event-triggered notification polling ────────────────────────────────────
  // Poll notifications every 15s; when a new workflow_complete notification
  // arrives (from an event-triggered run), show a toast so the user knows.
  const lastNotifIdRef = useRef<string | null>(null);
  useQuery({
    queryKey: ['automation-notif-poll'],
    queryFn: async () => {
      const { data } = await api.get('/notifications/?notif_type=workflow_complete');
      const list: Array<{ id: string; title: string; message: string; is_read: boolean }> =
        Array.isArray(data) ? data : (data?.results ?? []);
      const newest = list[0];
      if (newest && !newest.is_read && newest.id !== lastNotifIdRef.current) {
        lastNotifIdRef.current = newest.id;
        toast.success(`⚡ ${newest.title}`, { duration: 6000, id: newest.id });
        // Invalidate workflows so run_count / last_run_at refresh
        queryClient.invalidateQueries({ queryKey: ['workflows'] });
      }
      return list;
    },
    refetchInterval: isAuthenticated ? 30_000 : false,
    enabled: isAuthenticated,
    retry: false,
  });

  // Maximum time (ms) we will poll a run before giving up and marking it
  // as timed-out on the UI side.  The backend cleanup_stale_runs task handles
  // the DB side after 1 hour; we give up on the UI after 5 minutes so the
  // card doesn't stay "Running…" forever if Celery is down or the task is stuck.
  const POLL_TIMEOUT_MS = 5 * 60 * 1000; // 5 minutes — scrapers need time

  // On mount: clear all stale localStorage keys AND verify any stored
  // liveRuns against actual DB status, clearing those that are no longer running.
  useEffect(() => {
    // 1. Clear all localStorage run-start keys
    Object.keys(localStorage)
      .filter(k => k.startsWith('synapse:run-start:'))
      .forEach(k => localStorage.removeItem(k));

    // 2. Always start fresh — never inherit "running" state from a previous session
    setLiveRuns({});
  }, []);  // empty deps = runs once on mount, clean slate every time

  // Track when each workflow's polling started so we can enforce the timeout.
  const pollStartTimes = useRef<Record<string, number>>({});
  // Track runs that have timed out to prevent auto-restart of polling
  const timedOutRuns = useRef<Set<string>>(new Set());

  // Start live polling for a specific workflow run.
  // Creates a stable setInterval in pollTimers.current (not React state),
  // so adding a new workflow watcher never cancels an existing one.
  const startLiveRun = useCallback((workflowId: string, runId: string) => {
    // Avoid duplicate watchers for the same workflow
    if (pollTimers.current[workflowId]) return;

    // Record when we started polling so we can enforce the timeout.
    // Use localStorage so the clock survives navigation (don't reset on re-attach).
    const lsKey = `synapse:run-start:${workflowId}`;
    // Always reset the start time when a new run is triggered — never reuse stale keys
    localStorage.setItem(lsKey, String(Date.now()));
    pollStartTimes.current[workflowId] = Date.now();

    // Seed state immediately so the card shows "Running" at once
    setLiveRuns(prev => ({ ...prev, [workflowId]: { runId, status: null } }));

    const stopPolling = (workflowId: string) => {
      clearInterval(pollTimers.current[workflowId]);
      delete pollTimers.current[workflowId];
      delete pollStartTimes.current[workflowId];
      localStorage.removeItem(`synapse:run-start:${workflowId}`);
    };

    const tick = async () => {
      // Enforce max poll timeout — if we've been polling too long, give up.
      // Fall back to localStorage so the clock survives page navigation.
      const startTime = (
        pollStartTimes.current[workflowId]
        ?? parseInt(localStorage.getItem(`synapse:run-start:${workflowId}`) ?? '0', 10)
      ) || Date.now();
      const elapsed = Date.now() - startTime;
      if (elapsed > POLL_TIMEOUT_MS) {
        stopPolling(workflowId);
        setLiveRuns(prev => { const n = { ...prev }; delete n[workflowId]; return n; });
        // Mark this run as timed out so we don't auto-restart polling
        timedOutRuns.current.add(runId);
        toast.error('Workflow status check timed out. The worker may be unavailable. Check run history for details.');
        queryClient.invalidateQueries({ queryKey: ['workflows'] });
        return;
      }

      try {
        const data = await fetchRunStatus(runId);
        setLiveRuns(prev => ({ ...prev, [workflowId]: { runId, status: data } }));

        if (data.status === 'success' || data.status === 'failed') {
          // Stop polling
          stopPolling(workflowId);

          // Refresh workflow list so run_count / last_run_at update
          queryClient.invalidateQueries({ queryKey: ['workflows'] });
          queryClient.invalidateQueries({ queryKey: ['workflow-runs', workflowId] });

          if (data.status === 'success') {
            // Check if this was a collect_news workflow — data arrives
            // asynchronously via the scraping queue so we explain the delay.
            const result = data.result as { actions?: Array<{ action?: string }> } | null;
            const hasCollect = result?.actions?.some(a => a.action === 'collect_news');
            // Invalidate all content queries so GitHub, Research, Videos,
            // and Home pages immediately reflect any newly scraped items.
            queryClient.invalidateQueries({ queryKey: ['repos'] });
            queryClient.invalidateQueries({ queryKey: ['papers'] });
            queryClient.invalidateQueries({ queryKey: ['videos'] });
            queryClient.invalidateQueries({ queryKey: ['articles'] });
            queryClient.invalidateQueries({ queryKey: ['tweets'] });
            queryClient.invalidateQueries({ queryKey: ['tweets', 'home'] });
            queryClient.invalidateQueries({ queryKey: ['videos', 'home'] });
            queryClient.invalidateQueries({ queryKey: ['repos', 'list'] });

            if (hasCollect) {
              toast.success(
                '✅ Workflow complete! Scraping jobs queued — new content will appear in your feed within a few minutes.',
                { duration: 8000 },
              );
              // Signal the feed page to start watching for new scraped articles.
              // We use localStorage (cross-page) + a custom event (same-page)
              // so the signal survives navigation to /feed.
              localStorage.setItem('synapse:workflow-complete-at', String(Date.now()));
              window.dispatchEvent(new CustomEvent('synapse:workflow-complete'));
            } else {
              toast.success('Workflow completed successfully!');
            }
          } else {
            toast.error(`Workflow failed: ${data.error_message || 'unknown error'}`);
          }

          // Keep final status visible for 5 s then clear the live banner
          setTimeout(() => {
            setLiveRuns(prev => {
              const next = { ...prev };
              delete next[workflowId];
              return next;
            });
          }, 5000);
        }
      } catch (err: unknown) {
        // On any API error, clear the run so UI doesn't stay stuck in "Running"
        const status = (err as { response?: { status?: number } })?.response?.status;
        if (status === 404 || status === 500 || status === 401) {
          stopPolling(workflowId);
          setLiveRuns(prev => { const n = { ...prev }; delete n[workflowId]; return n; });
        }
        // Other network errors — clear after a few retries to prevent stuck UI
        else {
          stopPolling(workflowId);
          setLiveRuns(prev => { const n = { ...prev }; delete n[workflowId]; return n; });
        }
      }
    };

    // Poll immediately, then every 2.5 s
    tick();
    pollTimers.current[workflowId] = setInterval(tick, 2500);
  }, [queryClient]);

  // Clean up all timers when the page unmounts
  useEffect(() => {
    return () => {
      Object.values(pollTimers.current).forEach(clearInterval);
    };
  }, []);

  // Start polling for any existing pending/running runs when workflows load
  useEffect(() => {
    if (!workflows?.length) return;
    workflows.forEach((w: any) => {
      const latestRun = w.latest_run;
      if (latestRun?.id && (latestRun.status === 'pending' || latestRun.status === 'running')) {
        // Only start if not already polling and hasn't timed out
        if (!pollTimers.current[w.id] && !liveRuns[w.id] && !timedOutRuns.current.has(latestRun.id)) {
          startLiveRun(w.id, latestRun.id);
        }
      }
    });
  }, [workflows, liveRuns, startLiveRun]);

  // Re-attach live polling for any runs that are already in-progress when the
  // workflows list first loads (e.g. page reload, or navigating back to this
  // page while a run was already running).  We fetch the latest run for each
  // workflow that appears to be running and hook into startLiveRun so the card
  // shows the progress bar and stops correctly when the run finishes.
  const didReattach = useRef(false);
  useEffect(() => {
    if (didReattach.current || workflows.length === 0) return;
    didReattach.current = true;

    workflows.forEach(async (workflow) => {
      // Skip if we already have a live watcher for this workflow
      if (pollTimers.current[workflow.id]) return;

      // Clean up any stale localStorage run-start keys for workflows that
      // are no longer actually running (e.g. Celery completed while page was away).
      const lsKey = `synapse:run-start:${workflow.id}`;

      try {
        const runs = await fetchRuns(workflow.id);
        const latest = runs[0]; // runs are ordered by -started_at
        if (
          latest &&
          (latest.status === 'pending' || latest.status === 'running')
        ) {
          // If the run started more than POLL_TIMEOUT_MS ago, it's stale —
          // Celery likely crashed or never picked it up. Don't start polling,
          // just clear the UI key so the card stops showing "Running…".
          const startedAt = latest.started_at ? new Date(latest.started_at).getTime() : 0;
          const ageMs = Date.now() - startedAt;
          if (ageMs > POLL_TIMEOUT_MS) {
            localStorage.removeItem(lsKey);
            // Don't call startLiveRun — leave the card showing the workflow's
            // last_run_status from the list serializer instead.
          } else {
            // Use started_at as the poll-start anchor so the timeout is accurate.
            if (!localStorage.getItem(lsKey)) {
              localStorage.setItem(lsKey, String(startedAt || Date.now()));
            }
            startLiveRun(workflow.id, latest.id);
          }
        } else {
          // Latest run is terminal — clear any stale start-time key
          localStorage.removeItem(lsKey);
        }
      } catch {
        // Silently ignore — not critical
        localStorage.removeItem(lsKey);
      }
    });
  }, [workflows, startLiveRun]);

  const triggerMutation = useMutation({
    mutationFn: triggerWorkflow,
    onSuccess: (data, workflowId) => {
      toast.success('Workflow triggered! Watching for live status…');
      // Clear any previous timeout state for this workflow
      localStorage.removeItem(`synapse:run-start:${workflowId}`);
      // Clear timedOutRuns for any previous run of this workflow
      const prevRunId = liveRuns[workflowId]?.runId;
      if (prevRunId) {
        timedOutRuns.current.delete(prevRunId);
      }
      // Backend now returns run_id directly — no delay or fetchRuns needed
      if (data.run_id) {
        startLiveRun(workflowId, data.run_id);
      }
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    },
    onError: () => toast.error('Failed to trigger workflow.'),
  });

  const toggleMutation = useMutation({
    mutationFn: toggleWorkflow,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['workflows'] }),
    onError: () => toast.error('Failed to toggle workflow.'),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteWorkflow,
    onSuccess: () => {
      toast.success('Workflow deleted.');
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
      setWorkflowToDelete(null);
    },
    onError: () => toast.error('Failed to delete workflow.'),
  });

  const activeCount = workflows.filter(w => w.is_active).length;
  const totalRuns = workflows.reduce((sum, w) => sum + w.run_count, 0);
  const runningCount = Object.values(liveRuns).filter(
    r => r.status === null || r.status.status === 'pending' || r.status.status === 'running'
  ).length;

  return (
    <div className="flex-1 min-h-0 overflow-hidden">
      <div className="h-full overflow-y-auto p-4 sm:p-6 max-w-6xl mx-auto pb-12">

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-start justify-between mb-6 sm:mb-8 gap-3 sm:gap-4">
          <div className="min-w-0">
            <h1 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-white truncate">⚙️ Automation Center</h1>
            <p className="text-slate-400 mt-1 text-xs sm:text-sm">Schedule and automate your tech intelligence workflows.</p>
          </div>
          <div className="flex gap-2 flex-wrap shrink-0">
            <button onClick={() => setShowAnalytics(true)}
              className="bg-slate-100 hover:bg-slate-200 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-200 px-2.5 sm:px-3 py-1.5 sm:py-2 rounded-xl text-xs sm:text-sm font-medium transition-colors border border-slate-300 dark:border-slate-600 whitespace-nowrap">
              📊 <span className="hidden xs:inline">Analytics</span>
            </button>
            <button onClick={() => setShowSchedule(true)}
              className="bg-slate-100 hover:bg-slate-200 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-200 px-2.5 sm:px-3 py-1.5 sm:py-2 rounded-xl text-xs sm:text-sm font-medium transition-colors border border-slate-300 dark:border-slate-600 whitespace-nowrap">
              ⏱ <span className="hidden xs:inline">Schedule</span>
            </button>
            <button onClick={() => setShowTemplates(true)}
              className="bg-slate-100 hover:bg-slate-200 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-200 px-2.5 sm:px-3 py-1.5 sm:py-2 rounded-xl text-xs sm:text-sm font-medium transition-colors border border-slate-300 dark:border-slate-600 whitespace-nowrap">
              📋 <span className="hidden xs:inline">Templates</span>
            </button>
            <button onClick={() => setShowCreate(true)}
              className="bg-indigo-600 hover:bg-indigo-500 text-white px-3 sm:px-4 py-1.5 sm:py-2 rounded-xl text-xs sm:text-sm font-semibold transition-colors shadow-lg shadow-indigo-500/20 whitespace-nowrap">
              + <span className="hidden xs:inline">New </span>Workflow
            </button>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4 mb-6 sm:mb-8">
          {[
            { label: 'Total Workflows', value: workflows.length, icon: '⚙️' },
            { label: 'Active',          value: activeCount,      icon: '✅' },
            { label: 'Total Runs',      value: totalRuns,        icon: '🔄' },
            { label: 'Running Now',     value: runningCount,     icon: '⟳', pulse: runningCount > 0 },
          ].map(stat => (
            <div key={stat.label} className={`bg-slate-100 dark:bg-slate-800/80 border rounded-2xl p-3 sm:p-4 flex items-center gap-2 sm:gap-3 transition-all ${stat.pulse ? 'border-blue-500/40 shadow-blue-500/10 shadow-md' : 'border-slate-700 hover:border-slate-600'}`}>
              <span className={`text-xl sm:text-2xl shrink-0 ${stat.pulse ? 'animate-spin' : ''}`}>{stat.icon}</span>
              <div className="min-w-0">
                <p className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-white leading-tight">{stat.value}</p>
                <p className="text-slate-400 text-xs truncate">{stat.label}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Workflow Grid */}
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5 animate-pulse h-48" />
            ))}
          </div>
        ) : isError ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <div className="text-5xl mb-4">⚠️</div>
            <h3 className="text-slate-800 dark:text-white font-semibold text-lg mb-2">Automation failed to load</h3>
            <p className="text-slate-400 text-sm mb-6 max-w-sm">
              {(error as Error | null)?.message || 'The server did not return workflow data.'}
            </p>
            <button
              onClick={() => refetch()}
              className="bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-2.5 rounded-xl text-sm font-medium transition-colors"
            >
              Retry
            </button>
          </div>
        ) : workflows.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <div className="text-5xl mb-4">⚙️</div>
            <h3 className="text-slate-800 dark:text-white font-semibold text-lg mb-2">No workflows yet</h3>
            <p className="text-slate-400 text-sm mb-6 max-w-sm">
              Create your first workflow to automate content collection, summarization, and more.
            </p>
            <button onClick={() => setShowCreate(true)}
              className="bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-2.5 rounded-xl text-sm font-medium transition-colors">
              + Create Workflow
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {workflows.map(workflow => {
              const live = liveRuns[workflow.id];
              return (
                <WorkflowCard
                  key={workflow.id}
                  workflow={workflow}
                  onTrigger={id => triggerMutation.mutate(id)}
                  onToggle={id => toggleMutation.mutate(id)}
                  onDelete={id => setWorkflowToDelete(workflows.find(w => w.id === id) ?? null)}
                  onEdit={setWorkflowToEdit}
                  onViewRuns={setSelectedWorkflow}
                  liveRunId={live?.runId ?? null}
                  liveStatus={live?.status ?? null}
                />
              );
            })}
          </div>
        )}

        {/* Action Types & Events Legend */}
        <div className="mt-10 grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Action Types */}
          <div className="bg-slate-100 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-3">Available Action Types</h3>
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(ACTION_LABELS).map(([type, label]) => (
                <div key={type} className="bg-white dark:bg-slate-900 rounded-lg p-2.5">
                  <p className="text-sm text-slate-700 dark:text-slate-300">{label}</p>
                  <p className="text-xs text-slate-500 mt-0.5 font-mono">{type}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Event Trigger Types */}
          <div className="bg-slate-100 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-3">Event Trigger Types</h3>
            <div className="space-y-2">
              {EVENT_TYPE_OPTIONS.map(o => (
                <div key={o.value} className="bg-white dark:bg-slate-900 rounded-lg p-2.5 flex items-center gap-2">
                  <span className="text-sm text-slate-700 dark:text-slate-300">{o.label}</span>
                  <span className="ml-auto text-xs text-slate-500 font-mono">{o.value}</span>
                </div>
              ))}
            </div>
            <p className="text-xs text-slate-500 mt-3">
              Event workflows fire automatically when system events occur (new articles scraped, trending spikes, etc.)
            </p>
          </div>
        </div>

      </div>

      {/* Modals */}
      {showCreate && <CreateWorkflowModal onClose={() => setShowCreate(false)} />}
      {showTemplates && <TemplatesModal onClose={() => setShowTemplates(false)} />}
      {showSchedule && <ScheduleModal onClose={() => setShowSchedule(false)} />}
      {showAnalytics && <AnalyticsModal onClose={() => setShowAnalytics(false)} />}
      {workflowToEdit && (
        <EditWorkflowModal
          workflow={workflowToEdit}
          onClose={() => setWorkflowToEdit(null)}
        />
      )}
      {selectedWorkflow && <RunHistoryModal workflow={selectedWorkflow} onClose={() => setSelectedWorkflow(null)} />}
      {workflowToDelete && (
        <DeleteConfirmModal
          workflow={workflowToDelete}
          onConfirm={() => deleteMutation.mutate(workflowToDelete.id)}
          onCancel={() => setWorkflowToDelete(null)}
          isPending={deleteMutation.isPending}
        />
      )}
    </div>
  );
}
