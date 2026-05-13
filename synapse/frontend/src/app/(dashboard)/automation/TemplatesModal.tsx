'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';
import { api } from '@/utils/api';

interface Template {
  id: string;
  name: string;
  description: string;
  icon: string;
  category: string;
  trigger_type: string;
  cron_expression: string;
  event_config: Record<string, unknown>;
  actions: Array<{ type: string; params?: Record<string, unknown> }>;
}

const CATEGORY_LABELS: Record<string, string> = {
  digest: '📰 Digest',
  research: '🔬 Research',
  alerts: '⚡ Alerts',
};

const ACTION_LABELS: Record<string, string> = {
  collect_news: '📰 Collect News',
  scrape_hackernews: '🔶 HackerNews',
  scrape_github: '🐙 GitHub',
  scrape_arxiv: '📜 arXiv',
  scrape_videos: '🎬 Scrape Videos',
  scrape_tweets: '🐦 Scrape Tweets',
  summarize_content: '🤖 Summarize',
  generate_pdf: '📄 Generate PDF',
  send_email: '📧 Send Email',
  upload_to_drive: '☁️ Upload to Drive',
  ai_digest: '🧠 AI Digest',
};

export function TemplatesModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [cloningId, setCloningId] = useState<string | null>(null);
  const [customNames, setCustomNames] = useState<Record<string, string>>({});

  const { data: templates = [], isLoading } = useQuery<Template[]>({
    queryKey: ['workflow-templates'],
    queryFn: async () => { const { data } = await api.get('/automation/templates/'); return data; },
    staleTime: Infinity,
  });

  const cloneMutation = useMutation({
    mutationFn: async ({ templateId, name }: { templateId: string; name: string }) => {
      const { data } = await api.post(`/automation/templates/${templateId}/clone/`, { name });
      return data;
    },
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
      toast.success('Workflow created from template!');
      setCloningId(null);
    },
    onError: () => {
      toast.error('Failed to clone template.');
      setCloningId(null);
    },
  });

  const categories = ['all', ...Array.from(new Set(templates.map(t => t.category)))];
  const filtered = selectedCategory === 'all' ? templates : templates.filter(t => t.category === selectedCategory);

  const handleClone = (t: Template) => {
    setCloningId(t.id);
    cloneMutation.mutate({ templateId: t.id, name: customNames[t.id] || t.name });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl w-full max-w-3xl shadow-2xl flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-200 dark:border-slate-700">
          <div>
            <h2 className="text-lg font-semibold text-slate-800 dark:text-white">Workflow Templates</h2>
            <p className="text-xs text-slate-400 mt-0.5">Clone a pre-built workflow to get started instantly.</p>
          </div>
          <button onClick={onClose} className="text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-white text-xl transition-colors">✕</button>
        </div>

        {/* Category filter */}
        <div className="flex gap-2 px-5 py-3 border-b border-slate-200 dark:border-slate-700 overflow-x-auto">
          {categories.map(cat => (
            <button key={cat} onClick={() => setSelectedCategory(cat)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap border transition-colors ${
                selectedCategory === cat
                  ? 'bg-indigo-600 border-indigo-500 text-white'
                  : 'bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-400 hover:border-slate-400 dark:hover:border-slate-500'
              }`}>
              {cat === 'all' ? '🌐 All' : CATEGORY_LABELS[cat] ?? cat}
            </button>
          ))}
        </div>

        {/* Template grid */}
        <div className="overflow-y-auto flex-1 p-5">
          {isLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl p-4 animate-pulse h-40" />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {filtered.map(t => (
                <div key={t.id} className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl p-4 flex flex-col gap-3 hover:border-indigo-500/50 transition-all">
                  <div className="flex items-start gap-3">
                    <span className="text-3xl">{t.icon}</span>
                    <div className="flex-1 min-w-0">
                      <h3 className="text-slate-800 dark:text-white font-semibold text-sm leading-tight">{t.name}</h3>
                      <p className="text-xs text-slate-400 mt-1 line-clamp-2">{t.description}</p>
                    </div>
                  </div>

                  {/* Trigger info */}
                  <div className="flex flex-wrap gap-1.5">
                    <span className="text-xs bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 rounded px-2 py-0.5">
                      {t.trigger_type === 'schedule' ? `⏱ ${t.cron_expression}` : t.trigger_type === 'event' ? `⚡ ${(t.event_config as { event_type?: string })?.event_type}` : '🖐 Manual'}
                    </span>
                    {t.actions.map((a, i) => (
                      <span key={i} className="text-xs bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-500/20 rounded px-1.5 py-0.5">
                        {ACTION_LABELS[a.type] ?? a.type}
                      </span>
                    ))}
                  </div>

                  {/* Custom name */}
                  <input type="text" value={customNames[t.id] ?? t.name}
                    onChange={e => setCustomNames(prev => ({ ...prev, [t.id]: e.target.value }))}
                    className="w-full bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-600 rounded-lg px-2.5 py-1.5 text-slate-800 dark:text-white text-xs placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                    placeholder="Custom workflow name..." />

                  <button onClick={() => handleClone(t)} disabled={cloningId === t.id}
                    className="w-full py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-medium rounded-lg transition-colors">
                    {cloningId === t.id ? 'Creating…' : '+ Use This Template'}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
