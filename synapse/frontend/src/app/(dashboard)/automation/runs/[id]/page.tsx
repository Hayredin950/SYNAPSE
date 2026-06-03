'use client';

import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { api } from '@/utils/api';

interface ActionResult {
  action: string;
  status: string;
  error?: string;
  task_ids?: Record<string, string>;
  file_path?: string;
  title?: string;
  answer?: string;
  notification_id?: string;
  file_id?: string;
  web_view_link?: string;
  [key: string]: unknown;
}

interface WorkflowRun {
  id: string;
  workflow: string;
  status: 'pending' | 'running' | 'success' | 'failed';
  celery_task_id: string;
  trigger_event: Record<string, unknown>;
  started_at: string;
  completed_at: string | null;
  result: { actions?: ActionResult[] } | null;
  error_message: string;
  duration_seconds: number | null;
}

const STATUS_STYLES: Record<string, string> = {
  success:              'bg-green-500/20 text-green-400 border border-green-500/30',
  failed:               'bg-red-500/20 text-red-400 border border-red-500/30',
  error:                'bg-red-500/20 text-red-400 border border-red-500/30',
  running:              'bg-blue-500/20 text-blue-400 border border-blue-500/30 animate-pulse',
  pending:              'bg-slate-500/20 text-slate-400 border border-slate-500/30',
  queued:               'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30',
  skipped:              'bg-slate-500/20 text-slate-400 border border-slate-500/30',
  completed:            'bg-green-500/20 text-green-400 border border-green-500/30',
  notification_created: 'bg-green-500/20 text-green-400 border border-green-500/30',
};

const ACTION_ICONS: Record<string, string> = {
  collect_news:      '📰',
  summarize_content: '🤖',
  generate_pdf:      '📄',
  send_email:        '📧',
  upload_to_drive:   '☁️',
  ai_digest:         '🧠',
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${STATUS_STYLES[status] ?? 'bg-slate-200 dark:bg-slate-600 text-slate-700 dark:text-slate-300'}`}>
      {status === 'running' ? '⟳ Running'
        : status.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
    </span>
  );
}

function ActionCard({ action, index }: { action: ActionResult; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const icon = ACTION_ICONS[action.action] ?? '⚙️';

  const summary = (() => {
    if (action.status === 'queued' && action.task_ids)
      return `${Object.keys(action.task_ids).length} task(s) queued`;
    if (action.file_path) return `File: ${action.file_path}`;
    if (action.web_view_link) return `Drive: ${action.file_id}`;
    if (action.notification_id) return `Notification ID: ${action.notification_id}`;
    if (action.answer) return action.answer.slice(0, 120) + (action.answer.length > 120 ? '…' : '');
    if (action.error) return action.error;
    return null;
  })();

  const isError = action.status === 'error' || action.status === 'failed';

  return (
    <div className={`border rounded-xl overflow-hidden transition-all ${isError ? 'border-red-500/30 bg-red-50 dark:bg-red-500/5' : 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/60'}`}>
      <button
        className="w-full flex items-center gap-3 p-4 text-left hover:bg-slate-50 dark:hover:bg-slate-700/20 transition-colors"
        onClick={() => setExpanded(e => !e)}
      >
        <div className="w-7 h-7 rounded-full bg-slate-200 dark:bg-slate-700 flex items-center justify-center text-xs font-bold text-slate-600 dark:text-slate-400 flex-shrink-0">
          {index + 1}
        </div>
        <span className="text-xl">{icon}</span>
        <div className="flex-1 min-w-0">
          <p className="text-slate-800 dark:text-white font-medium text-sm leading-tight">
            {action.action.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
          </p>
          {summary && <p className="text-xs text-slate-400 mt-0.5 truncate">{summary}</p>}
        </div>
        <StatusBadge status={action.status} />
        <span className="text-slate-500 text-xs ml-1">{expanded ? '▲' : '▼'}</span>
      </button>

      {expanded && (
        <div className="border-t border-slate-200 dark:border-slate-700 p-4 space-y-3">
          {action.error && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3">
              <p className="text-xs text-red-400 font-medium mb-1">Error</p>
              <p className="text-xs text-red-300">{action.error}</p>
            </div>
          )}
          {action.answer && (
            <div className="bg-white dark:bg-slate-900 rounded-lg p-3">
              <p className="text-xs text-slate-400 font-medium mb-1">AI Answer</p>
              <p className="text-xs text-slate-600 dark:text-slate-300 whitespace-pre-wrap leading-relaxed">{action.answer}</p>
            </div>
          )}
          {action.web_view_link && (
            <a href={action.web_view_link} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-2 text-xs text-indigo-600 dark:text-indigo-400 hover:text-indigo-500 dark:hover:text-indigo-300 transition-colors underline">
              ☁️ View in Google Drive →
            </a>
          )}
          {action.file_path && (
            <div>
              <p className="text-xs text-slate-400 font-medium mb-1">Generated File</p>
              <p className="text-xs font-mono text-slate-600 dark:text-slate-300 bg-white dark:bg-slate-900 rounded p-2 break-all">{action.file_path}</p>
            </div>
          )}
          {action.task_ids && Object.keys(action.task_ids).length > 0 && (
            <div>
              <p className="text-xs text-slate-400 font-medium mb-1">Queued Celery Task IDs</p>
              <div className="space-y-1">
                {Object.entries(action.task_ids).map(([src, tid]) => (
                  <p key={src} className="text-xs font-mono text-slate-400">
                    <span className="text-slate-500 mr-1">{src}:</span>{String(tid)}
                  </p>
                ))}
              </div>
            </div>
          )}
          <details>
            <summary className="text-xs text-slate-500 cursor-pointer hover:text-slate-400">Raw JSON</summary>
            <pre className="text-xs text-slate-600 dark:text-slate-500 bg-slate-100 dark:bg-slate-950 rounded p-2 mt-1 overflow-x-auto max-h-48">
              {JSON.stringify(action, null, 2)}
            </pre>
          </details>
        </div>
      )}
    </div>
  );
}

export default function RunDetailPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [liveRun, setLiveRun] = useState<WorkflowRun | null>(null);

  const { data: run, isLoading } = useQuery<WorkflowRun>({
    queryKey: ['run-detail', id],
    queryFn: async () => {
      const { data } = await api.get(`/automation/runs/${id}/`);
      return data;
    },
  });

  // Live-poll while run is active
  useEffect(() => {
    const current = liveRun ?? run;
    if (!current) return;
    const terminal = current.status === 'success' || current.status === 'failed';
    if (terminal) { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; } return; }

    if (!pollRef.current) {
      pollRef.current = setInterval(async () => {
        try {
          const { data } = await api.get(`/automation/runs/${id}/status/`);
          setLiveRun(data);
          if (data.status === 'success' || data.status === 'failed') {
            clearInterval(pollRef.current!); pollRef.current = null;
          }
        } catch { /* ignore */ }
      }, 2500);
    }
    return () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; } };
  }, [run?.status, id, liveRun]);

  const displayRun = liveRun ?? run;

  if (isLoading) {
    return (
      <div className="flex-1 p-8 flex items-center justify-center">
        <div className="text-slate-400 animate-pulse text-sm">Loading run details…</div>
      </div>
    );
  }

  if (!displayRun) {
    return (
      <div className="flex-1 p-8">
        <p className="text-red-400 mb-2">Run not found.</p>
        <Link href="/automation" className="text-indigo-600 dark:text-indigo-400 text-sm hover:text-indigo-500 dark:hover:text-indigo-300">← Back to Automation</Link>
      </div>
    );
  }

  const actions: ActionResult[] = displayRun.result?.actions ?? [];
  const successCount = actions.filter(a => ['success', 'queued', 'completed', 'notification_created'].includes(a.status)).length;
  const failCount = actions.filter(a => ['failed', 'error'].includes(a.status)).length;

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="p-6 max-w-3xl mx-auto pb-12">
        {/* Back */}
        <Link href="/automation" className="text-indigo-600 dark:text-indigo-400 text-sm hover:text-indigo-500 dark:hover:text-indigo-300 transition-colors inline-flex items-center gap-1">
          ← Back to Automation
        </Link>

        {/* Header */}
        <div className="mt-4 mb-6 flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h1 className="text-xl font-bold text-slate-900 dark:text-white">Workflow Run</h1>
              <StatusBadge status={displayRun.status} />
            </div>
            <p className="text-xs font-mono text-slate-500 mt-1">{displayRun.id}</p>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          {[
            { label: 'Started', value: new Date(displayRun.started_at).toLocaleString() },
            { label: 'Completed', value: displayRun.completed_at ? new Date(displayRun.completed_at).toLocaleString() : '—' },
            { label: 'Duration', value: displayRun.duration_seconds != null ? `${displayRun.duration_seconds.toFixed(1)}s` : '—' },
            { label: 'Actions', value: `${successCount}✅ ${failCount > 0 ? failCount + '❌' : ''}`.trim() || String(actions.length) },
          ].map(m => (
            <div key={m.label} className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-3">
              <p className="text-xs text-slate-400 mb-1">{m.label}</p>
              <p className="text-sm text-slate-800 dark:text-white font-medium truncate">{m.value}</p>
            </div>
          ))}
        </div>

        {/* Event trigger */}
        {displayRun.trigger_event && Object.keys(displayRun.trigger_event).length > 0 && (
          <div className="mb-5 bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-200 dark:border-indigo-500/20 rounded-xl p-4">
            <p className="text-xs font-medium text-indigo-600 dark:text-indigo-400 mb-2">⚡ Triggered by Event</p>
            <pre className="text-xs text-indigo-700 dark:text-indigo-300 overflow-x-auto">
              {JSON.stringify(displayRun.trigger_event, null, 2)}
            </pre>
          </div>
        )}

        {/* Error banner */}
        {displayRun.error_message && (
          <div className="mb-5 bg-red-500/10 border border-red-500/20 rounded-xl p-4">
            <p className="text-xs font-medium text-red-400 mb-1">❌ Run Error</p>
            <p className="text-sm text-red-300">{displayRun.error_message}</p>
          </div>
        )}

        {/* Live progress */}
        {(displayRun.status === 'running' || displayRun.status === 'pending') && (
          <div className="mb-5">
            <div className="flex justify-between mb-1">
              <p className="text-xs text-blue-400 animate-pulse">⟳ Workflow is running…</p>
              <p className="text-xs text-slate-500">refreshing every 2.5s</p>
            </div>
            <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-1.5 overflow-hidden">
              <div className="h-full bg-blue-500 rounded-full animate-pulse" style={{ width: '100%' }} />
            </div>
          </div>
        )}

        {/* Action results */}
        <div>
          <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-3">
            Action Results {actions.length > 0 && <span className="text-slate-500 font-normal">({actions.length})</span>}
          </h2>
          {actions.length === 0 ? (
            <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-8 text-center text-slate-400 text-sm">
              {displayRun.status === 'running' ? '⟳ Actions are executing…' : 'No action results recorded.'}
            </div>
          ) : (
            <div className="space-y-3">
              {actions.map((action, i) => (
                <ActionCard key={i} action={action} index={i} />
              ))}
            </div>
          )}
        </div>

        {/* Footer: celery task id */}
        {displayRun.celery_task_id && (
          <div className="mt-6 bg-slate-100 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700/60 rounded-xl p-4">
            <p className="text-xs text-slate-500 mb-1">Celery Task ID</p>
            <p className="text-xs font-mono text-slate-600 dark:text-slate-400 break-all">{displayRun.celery_task_id}</p>
          </div>
        )}
      </div>
    </div>
  );
}
