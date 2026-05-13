'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';
import { api } from '@/utils/api';

interface ScheduleEntry {
  task_name: string;
  workflow_id: string;
  workflow_name: string;
  cron: string | null;
  cron_expression: string;
  enabled: boolean;
  last_run_at: string | null;
  total_run_count: number;
  next_run: string | null;
}

export function ScheduleModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();

  const { data: schedule = [], isLoading, error } = useQuery<ScheduleEntry[]>({
    queryKey: ['workflow-schedule'],
    queryFn: async () => { const { data } = await api.get('/automation/schedule/'); return data; },
    refetchInterval: 30000,
  });

  const toggleMutation = useMutation({
    mutationFn: async (workflowId: string) => {
      const { data } = await api.post(`/automation/schedule/${workflowId}/toggle/`);
      return data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['workflow-schedule'] });
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
      toast.success(`Schedule ${data.enabled ? 'enabled' : 'disabled'}.`);
    },
    onError: () => toast.error('Failed to toggle schedule.'),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl w-full max-w-2xl shadow-2xl flex flex-col max-h-[80vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-200 dark:border-slate-700">
          <div>
            <h2 className="text-lg font-semibold text-slate-800 dark:text-white">⏱ Scheduled Tasks</h2>
            <p className="text-xs text-slate-400 mt-0.5">Manage Celery Beat schedules for your workflows.</p>
          </div>
          <button onClick={onClose} className="text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-white text-xl transition-colors">✕</button>
        </div>

        <div className="overflow-y-auto flex-1 p-5 space-y-3">
          {isLoading && (
            <div className="space-y-2">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl p-4 animate-pulse h-20" />
              ))}
            </div>
          )}

          {!isLoading && error && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-red-400 text-sm">
              ⚠️ Could not load schedule. django-celery-beat may not be installed.
            </div>
          )}

          {!isLoading && !error && schedule.length === 0 && (
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl p-8 text-center">
              <p className="text-slate-400 text-sm">No scheduled workflows found.</p>
              <p className="text-slate-500 text-xs mt-1">Create a workflow with trigger type "Schedule" to see it here.</p>
            </div>
          )}

          {schedule.map(entry => (
            <div key={entry.task_name}
              className={`bg-white dark:bg-slate-900 border rounded-xl p-4 transition-all shadow-sm ${entry.enabled ? 'border-slate-200 dark:border-slate-700' : 'border-slate-200/60 dark:border-slate-700/40 opacity-60'}`}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <p className="text-slate-800 dark:text-white font-medium text-sm truncate">{entry.workflow_name}</p>
                    <span className={`text-xs px-2 py-0.5 rounded-full border ${entry.enabled
                      ? 'bg-green-500/20 text-green-400 border-green-500/30'
                      : 'bg-slate-600/20 text-slate-400 border-slate-600/30'}`}>
                      {entry.enabled ? 'Active' : 'Paused'}
                    </span>
                  </div>
                  <p className="text-xs font-mono text-indigo-600 dark:text-indigo-400 mb-2">⏱ {entry.cron_expression}</p>
                  <div className="flex flex-wrap gap-3 text-xs text-slate-500">
                    <span>🔄 {entry.total_run_count} total runs</span>
                    {entry.last_run_at && (
                      <span>Last: {new Date(entry.last_run_at).toLocaleDateString()}</span>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => toggleMutation.mutate(entry.workflow_id)}
                  disabled={toggleMutation.isPending}
                  className={`flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors disabled:opacity-50 ${
                    entry.enabled
                      ? 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400 hover:bg-yellow-500/20'
                      : 'bg-green-500/10 border-green-500/30 text-green-400 hover:bg-green-500/20'
                  }`}>
                  {entry.enabled ? '⏸ Pause' : '▶ Resume'}
                </button>
              </div>
            </div>
          ))}
        </div>

        <div className="p-4 border-t border-slate-200 dark:border-slate-700">
          <p className="text-xs text-slate-500 text-center">
            Schedules are powered by Celery Beat. Changes take effect on the next scheduler heartbeat.
          </p>
        </div>
      </div>
    </div>
  );
}
