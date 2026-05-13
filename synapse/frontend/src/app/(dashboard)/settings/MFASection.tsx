'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';
import Image from 'next/image';
import { api } from '@/utils/api';

// ── Types ─────────────────────────────────────────────────────────────────────

interface MFAStatus {
  is_enabled: boolean;
  device_name: string | null;
  confirmed_at: string | null;
}

interface MFASetupData {
  secret: string;
  qr_code: string;       // base64 data-url PNG
  backup_codes: string[];
  otpauth_url: string;
}

type Step = 'idle' | 'setup' | 'confirm' | 'backup_codes' | 'disable';

// ── Helpers ───────────────────────────────────────────────────────────────────

function OTPInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <input
      type="text"
      inputMode="numeric"
      pattern="[0-9]*"
      maxLength={6}
      value={value}
      onChange={e => onChange(e.target.value.replace(/\D/g, '').slice(0, 6))}
      placeholder="000000"
      className="w-full text-center text-3xl font-mono tracking-[0.5em] bg-white dark:bg-slate-900 border-2 border-slate-600 focus:border-indigo-500 rounded-xl px-4 py-4 text-white placeholder-slate-700 focus:outline-none transition-colors"
    />
  );
}

function BackupCodeGrid({ codes }: { codes: string[] }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(codes.join('\n'));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl p-4">
      <div className="grid grid-cols-2 gap-2 mb-3">
        {codes.map((code, i) => (
          <code key={i} className="text-xs font-mono bg-slate-100 dark:bg-slate-800 text-green-400 rounded px-2 py-1.5 text-center tracking-widest">
            {code}
          </code>
        ))}
      </div>
      <button onClick={handleCopy}
        className="w-full py-2 bg-slate-200 hover:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-300 text-xs font-medium rounded-lg transition-colors">
        {copied ? '✅ Copied!' : '📋 Copy All Codes'}
      </button>
    </div>
  );
}

// ── MFASection ────────────────────────────────────────────────────────────────

export function MFASection() {
  const queryClient = useQueryClient();
  const [step, setStep] = useState<Step>('idle');
  const [setupData, setSetupData] = useState<MFASetupData | null>(null);
  const [token, setToken] = useState('');
  const [password, setPassword] = useState('');
  const [backupCodes, setBackupCodes] = useState<string[]>([]);
  const [error, setError] = useState('');

  const reset = () => { setStep('idle'); setToken(''); setPassword(''); setError(''); setSetupData(null); };

  // ── Status query ──────────────────────────────────────────────────────────
  const { data: status, isLoading } = useQuery<MFAStatus>({
    queryKey: ['mfa-status'],
    queryFn: async () => { const { data } = await api.get('/auth/mfa/status/'); return data; },
    retry: false,
  });

  // ── Setup mutation ────────────────────────────────────────────────────────
  const setupMutation = useMutation({
    mutationFn: async () => { const { data } = await api.get('/auth/mfa/setup/'); return data as MFASetupData; },
    onSuccess: (data) => { setSetupData(data); setStep('setup'); setError(''); },
    onError: () => { toast.error('Could not start MFA setup. Try again.'); },
  });

  // ── Confirm mutation ──────────────────────────────────────────────────────
  const confirmMutation = useMutation({
    mutationFn: async (otp: string) => {
      const { data } = await api.post('/auth/mfa/setup/confirm/', { token: otp });
      return data as { backup_codes: string[] };
    },
    onSuccess: (data) => {
      setBackupCodes(data.backup_codes ?? setupData?.backup_codes ?? []);
      setStep('backup_codes');
      setError('');
      queryClient.invalidateQueries({ queryKey: ['mfa-status'] });
      toast.success('MFA enabled successfully!');
    },
    onError: () => { setError('Invalid code. Please try again with a fresh 6-digit code from your authenticator app.'); },
  });

  // ── Disable mutation ──────────────────────────────────────────────────────
  const disableMutation = useMutation({
    mutationFn: async (pwd: string) => {
      await api.post('/auth/mfa/disable/', { password: pwd });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mfa-status'] });
      toast.success('MFA has been disabled.');
      reset();
    },
    onError: () => { setError('Incorrect password. Please try again.'); },
  });

  if (isLoading) {
    return <div className="animate-pulse h-24 bg-slate-700/30 rounded-xl" />;
  }

  const enabled = status?.is_enabled ?? false;

  // ── Backup codes display (after successful setup) ─────────────────────────
  if (step === 'backup_codes') {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3 p-4 bg-green-500/10 border border-green-500/30 rounded-xl">
          <span className="text-2xl">✅</span>
          <div>
            <p className="text-green-400 font-semibold text-sm">MFA Enabled Successfully!</p>
            <p className="text-green-300/70 text-xs mt-0.5">Save your backup codes in a safe place — you can only view them once.</p>
          </div>
        </div>
        <div>
          <p className="text-sm font-medium text-slate-600 dark:text-slate-300 mb-2">🔐 Backup Codes</p>
          <BackupCodeGrid codes={backupCodes} />
          <p className="text-xs text-slate-500 mt-2">Each code can only be used once. Store them somewhere secure (password manager, printed copy).</p>
        </div>
        <button onClick={reset} className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-xl transition-colors">
          Done — Close Setup
        </button>
      </div>
    );
  }

  // ── Confirm step ──────────────────────────────────────────────────────────
  if (step === 'confirm' && setupData) {
    return (
      <div className="space-y-4">
        <div>
          <p className="text-sm font-medium text-slate-600 dark:text-slate-300 mb-1">Step 2 — Enter the code from your app</p>
          <p className="text-xs text-slate-400">Open your authenticator app and enter the 6-digit code for SYNAPSE.</p>
        </div>
        <OTPInput value={token} onChange={v => { setToken(v); setError(''); }} />
        {error && <p className="text-xs text-red-400 bg-red-500/10 rounded-lg px-3 py-2">{error}</p>}
        <div className="flex gap-2">
          <button onClick={() => { setStep('setup'); setError(''); }}
            className="flex-1 py-2.5 bg-slate-200 hover:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-300 text-sm rounded-xl transition-colors">
            ← Back
          </button>
          <button
            onClick={() => confirmMutation.mutate(token)}
            disabled={token.length !== 6 || confirmMutation.isPending}
            className="flex-1 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium rounded-xl transition-colors">
            {confirmMutation.isPending ? 'Verifying…' : 'Verify & Enable MFA'}
          </button>
        </div>
        <button onClick={reset} className="w-full text-xs text-slate-500 hover:text-slate-400 transition-colors">Cancel setup</button>
      </div>
    );
  }

  // ── Setup step (QR code) ──────────────────────────────────────────────────
  if (step === 'setup' && setupData) {
    return (
      <div className="space-y-4">
        <div>
          <p className="text-sm font-medium text-slate-600 dark:text-slate-300 mb-1">Step 1 — Scan with your authenticator app</p>
          <p className="text-xs text-slate-400">Use Google Authenticator, Authy, or any TOTP-compatible app.</p>
        </div>

        {/* QR Code */}
        <div className="flex justify-center">
          <div className="bg-white p-3 rounded-xl inline-block">
            {setupData.qr_code ? (
              <img src={setupData.qr_code} alt="TOTP QR Code" width={180} height={180} className="block" />
            ) : (
              <div className="w-44 h-44 bg-slate-200 flex items-center justify-center rounded text-slate-400 text-xs">QR unavailable</div>
            )}
          </div>
        </div>

        {/* Manual entry */}
        <details className="group">
          <summary className="text-xs text-slate-500 cursor-pointer hover:text-slate-400 transition-colors">
            Can't scan? Enter the secret key manually ▼
          </summary>
          <div className="mt-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2">
            <p className="text-xs text-slate-400 mb-1">Secret key (Base32):</p>
            <code className="text-xs font-mono text-indigo-600 dark:text-indigo-300 break-all">{setupData.secret}</code>
          </div>
        </details>

        <button onClick={() => { setToken(''); setStep('confirm'); }}
          className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-xl transition-colors">
          I've scanned it → Enter Code
        </button>
        <button onClick={reset} className="w-full text-xs text-slate-500 hover:text-slate-400 transition-colors">Cancel</button>
      </div>
    );
  }

  // ── Disable step ──────────────────────────────────────────────────────────
  if (step === 'disable') {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/30 rounded-xl">
          <span className="text-2xl">⚠️</span>
          <div>
            <p className="text-red-400 font-semibold text-sm">Disable Two-Factor Authentication</p>
            <p className="text-red-300/70 text-xs mt-0.5">This will remove the extra layer of security from your account.</p>
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-600 dark:text-slate-300 mb-1">Confirm your password</label>
          <input type="password" value={password}
            onChange={e => { setPassword(e.target.value); setError(''); }}
            placeholder="Enter your current password"
            className="w-full bg-white dark:bg-slate-900 border border-slate-600 rounded-xl px-3 py-2.5 text-white text-sm placeholder-slate-500 focus:outline-none focus:border-red-500 transition-colors" />
        </div>
        {error && <p className="text-xs text-red-400 bg-red-500/10 rounded-lg px-3 py-2">{error}</p>}
        <div className="flex gap-2">
          <button onClick={reset} className="flex-1 py-2.5 bg-slate-200 hover:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-300 text-sm rounded-xl transition-colors">Cancel</button>
          <button onClick={() => disableMutation.mutate(password)}
            disabled={!password || disableMutation.isPending}
            className="flex-1 py-2.5 bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white text-sm font-medium rounded-xl transition-colors">
            {disableMutation.isPending ? 'Disabling…' : 'Disable MFA'}
          </button>
        </div>
      </div>
    );
  }

  // ── Idle: show current status ─────────────────────────────────────────────
  return (
    <div className={`rounded-xl border p-5 transition-all ${enabled ? 'border-green-500/30 bg-green-500/5' : 'border-slate-600/50 bg-slate-900/30'}`}>
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-xl flex-shrink-0 ${enabled ? 'bg-green-500/20' : 'bg-slate-100 dark:bg-slate-800'}`}>
            {enabled ? '🔐' : '🔓'}
          </div>
          <div>
            <p className="text-slate-800 dark:text-white font-medium text-sm">Two-Factor Authentication (TOTP)</p>
            {enabled ? (
              <p className="text-xs text-green-400 mt-0.5">✅ Enabled — your account is protected</p>
            ) : (
              <p className="text-xs text-slate-400 mt-0.5">Not enabled — add extra security to your account</p>
            )}
          </div>
        </div>
        {enabled ? (
          <button onClick={() => setStep('disable')}
            className="flex-shrink-0 px-3 py-1.5 bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 text-red-400 text-xs font-medium rounded-lg transition-colors">
            Disable
          </button>
        ) : (
          <button onClick={() => setupMutation.mutate()} disabled={setupMutation.isPending}
            className="flex-shrink-0 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium rounded-lg transition-colors disabled:opacity-50">
            {setupMutation.isPending ? 'Setting up…' : 'Enable MFA'}
          </button>
        )}
      </div>

      {enabled && status?.confirmed_at && (
        <div className="mt-3 pt-3 border-t border-slate-700/50">
          <p className="text-xs text-slate-500">
            Enabled on {new Date(status.confirmed_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}
          </p>
        </div>
      )}
    </div>
  );
}
