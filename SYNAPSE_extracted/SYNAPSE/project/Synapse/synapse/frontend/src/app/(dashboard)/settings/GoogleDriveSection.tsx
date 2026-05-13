'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';
import { api } from '@/utils/api';

interface DriveStatus {
  is_connected: boolean;
  google_email: string | null;
  connected_at: string | null;
}

export function GoogleDriveSection() {
  const queryClient = useQueryClient();
  const [disconnecting, setDisconnecting] = useState(false);

  const { data: status, isLoading } = useQuery<DriveStatus>({
    queryKey: ['drive-status'],
    queryFn: async () => {
      const { data } = await api.get('/integrations/drive/status/');
      return data;
    },
    retry: false,
  });

  const connectMutation = useMutation({
    mutationFn: async () => {
      const { data } = await api.get('/integrations/drive/connect/');
      return data as { auth_url: string };
    },
    onSuccess: (data) => {
      if (data.auth_url) {
        // Open Google OAuth in a popup window
        const width = 500, height = 650;
        const left = Math.round(window.screen.width / 2 - width / 2);
        const top = Math.round(window.screen.height / 2 - height / 2);
        const popup = window.open(
          data.auth_url,
          'google-drive-oauth',
          `width=${width},height=${height},top=${top},left=${left},scrollbars=yes`,
        );

        // Listen for postMessage from the OAuth callback page
        const handleMessage = (event: MessageEvent) => {
          if (event.data?.type === 'drive-oauth-complete') {
            window.removeEventListener('message', handleMessage);
            queryClient.invalidateQueries({ queryKey: ['drive-status'] });
          }
        };

        window.addEventListener('message', handleMessage);

        // Fallback: close listener after 5 minutes
        setTimeout(() => {
          window.removeEventListener('message', handleMessage);
        }, 5 * 60 * 1000);
      }
    },
    onError: () => toast.error('Could not start Google Drive OAuth. Check your GOOGLE_CLIENT_ID config.'),
  });

  const disconnectMutation = useMutation({
    mutationFn: async () => {
      await api.delete('/integrations/drive/disconnect/');
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['drive-status'] });
      toast.success('Google Drive disconnected.');
    },
    onError: () => toast.error('Failed to disconnect Google Drive.'),
  });

  if (isLoading) {
    return (
      <div className="animate-pulse h-24 bg-slate-700/30 rounded-xl" />
    );
  }

  const connected = status?.is_connected ?? false;

  return (
    <div className={`rounded-xl border p-5 transition-all ${connected ? 'border-green-500/30 bg-green-500/5' : 'border-slate-600/50 bg-slate-900/30'}`}>
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          {/* Google Drive icon */}
          <div className="w-10 h-10 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-700 flex items-center justify-center text-xl flex-shrink-0">
            ☁️
          </div>
          <div>
            <p className="text-slate-800 dark:text-white font-medium text-sm">Google Drive</p>
            {connected && status?.google_email ? (
              <p className="text-xs text-green-400 mt-0.5">✅ Connected as {status.google_email}</p>
            ) : (
              <p className="text-xs text-slate-400 mt-0.5">Not connected — connect to enable upload_to_drive workflows</p>
            )}
          </div>
        </div>

        {connected ? (
          <button
            onClick={() => disconnectMutation.mutate()}
            disabled={disconnectMutation.isPending}
            className="px-3 py-1.5 bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 text-red-400 text-xs font-medium rounded-lg transition-colors disabled:opacity-50 flex-shrink-0"
          >
            {disconnectMutation.isPending ? 'Disconnecting…' : 'Disconnect'}
          </button>
        ) : (
          <button
            onClick={() => connectMutation.mutate()}
            disabled={connectMutation.isPending}
            className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium rounded-lg transition-colors disabled:opacity-50 flex-shrink-0"
          >
            {connectMutation.isPending ? 'Redirecting…' : 'Connect Drive'}
          </button>
        )}
      </div>

      {connected && (
        <div className="mt-4 pt-4 border-t border-slate-700/50">
          <p className="text-xs text-slate-400 mb-3">Test your Drive connection:</p>
          <TestUploadButton />
        </div>
      )}

      {!connected && (
        <div className="mt-3 bg-slate-100 dark:bg-slate-800/60 rounded-lg p-3">
          <p className="text-xs text-slate-400 font-medium mb-1">Required environment variables:</p>
          <div className="space-y-0.5">
            {['GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 'GOOGLE_REDIRECT_URI'].map(v => (
              <p key={v} className="text-xs font-mono text-slate-500">{v}</p>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function TestUploadButton() {
  const [result, setResult] = useState<{ status: string; file_id?: string; web_view_link?: string; error?: string } | null>(null);
  const [testing, setTesting] = useState(false);

  const handleTest = async () => {
    setTesting(true);
    setResult(null);
    try {
      // Create a tiny test document in the DB first, then upload it
      const { data } = await api.post('/integrations/drive/upload/', {
        document_id: 'test',
        folder_name: 'SYNAPSE/Test',
      });
      setResult({ status: 'success', file_id: data.file_id, web_view_link: data.web_view_link });
      toast.success('Test upload succeeded!');
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Upload test failed.';
      setResult({ status: 'failed', error: msg });
      toast.error(msg);
    }
    setTesting(false);
  };

  return (
    <div>
      <button onClick={handleTest} disabled={testing}
        className="px-3 py-1.5 bg-slate-200 hover:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-300 text-xs rounded-lg transition-colors disabled:opacity-50">
        {testing ? '⟳ Testing…' : '🧪 Test Upload'}
      </button>
      {result && (
        <div className={`mt-2 p-2 rounded-lg text-xs ${result.status === 'success' ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
          {result.status === 'success' ? (
            <>
              ✅ Uploaded!{' '}
              {result.web_view_link && (
                <a href={result.web_view_link} target="_blank" rel="noopener noreferrer" className="underline ml-1">View in Drive →</a>
              )}
            </>
          ) : (
            <>❌ {result.error}</>
          )}
        </div>
      )}
    </div>
  );
}
