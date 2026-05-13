'use client';

/**
 * TASK-006-F5: Invite Acceptance Page
 * Route: /invite/[token]
 *
 * Shows org name, inviter, role. "Accept" calls POST /api/v1/organizations/invites/{token}/accept/
 * If not logged in → redirects to /login?next=/invite/[token]
 */

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { Building2, CheckCircle, XCircle, Loader2, LogIn } from 'lucide-react';
import { api } from '@/utils/api';
import { useAuthStore } from '@/store/authStore';

interface InviteInfo {
  org_name: string;
  invited_by_email: string;
  role: string;
  expires_at: string | null;
}

export default function InviteAcceptPage() {
  const params = useParams();
  const router = useRouter();
  const token = params?.token as string;
  const { isAuthenticated, user } = useAuthStore();

  const [info, setInfo] = useState<InviteInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [accepting, setAccepting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  // Fetch invite preview (org name / role)
  useEffect(() => {
    if (!token) return;
    // We try to fetch the info; if the user is not authenticated they'll see a login prompt
    api.get(`/organizations/invites/${token}/preview/`)
      .then(r => setInfo(r.data?.data))
      .catch(() => {
        // Fallback: show a generic message if preview endpoint not available
        setInfo({ org_name: 'an organization', invited_by_email: '', role: 'member', expires_at: null });
      })
      .finally(() => setLoading(false));
  }, [token]);

  const handleAccept = async () => {
    if (!isAuthenticated) {
      router.push(`/login?next=/invite/${token}`);
      return;
    }
    setAccepting(true);
    setError('');
    try {
      await api.post(`/organizations/invites/${token}/accept/`);
      setSuccess(true);
      setTimeout(() => router.push('/organizations'), 2000);
    } catch (e: any) {
      const msg = e?.response?.data?.error;
      setError(typeof msg === 'string' ? msg : 'Failed to accept invite. The link may have expired.');
    } finally {
      setAccepting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center">
        <Loader2 className="animate-spin text-indigo-500" size={32} />
      </div>
    );
  }

  if (success) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center p-4">
        <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl border border-slate-200 dark:border-slate-800 p-8 max-w-sm w-full text-center">
          <div className="w-14 h-14 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center mx-auto mb-4">
            <CheckCircle size={28} className="text-green-600 dark:text-green-400" />
          </div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-white mb-2">Welcome aboard!</h1>
          <p className="text-sm text-slate-600 dark:text-slate-400">
            You have joined <strong>{info?.org_name}</strong>. Redirecting…
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center p-4">
      <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl border border-slate-200 dark:border-slate-800 p-8 max-w-sm w-full">
        {/* Logo */}
        <div className="flex justify-center mb-6">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg">
            <span className="text-white font-black text-lg">S</span>
          </div>
        </div>

        {/* Content */}
        <div className="text-center mb-6">
          <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-violet-500 to-indigo-500 flex items-center justify-center mx-auto mb-4 shadow-md">
            <Building2 size={24} className="text-white" />
          </div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-white mb-2">
            You&apos;re invited!
          </h1>
          {info && (
            <p className="text-sm text-slate-600 dark:text-slate-400">
              {info.invited_by_email
                ? <><strong>{info.invited_by_email}</strong> has invited you</>
                : 'You have been invited'
              }{' '}
              to join <strong>{info.org_name}</strong> as{' '}
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300">
                {info.role}
              </span>.
            </p>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="flex items-start gap-2 text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded-xl p-3 mb-4">
            <XCircle size={16} className="flex-shrink-0 mt-0.5" />
            {error}
          </div>
        )}

        {/* Auth check */}
        {!isAuthenticated ? (
          <div className="space-y-3">
            <p className="text-sm text-slate-600 dark:text-slate-400 text-center">
              Please log in to accept this invitation.
            </p>
            <Link
              href={`/login?next=/invite/${token}`}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium transition-colors"
            >
              <LogIn size={16} />
              Log in to accept
            </Link>
            <Link
              href={`/register?next=/invite/${token}`}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 text-sm font-medium transition-colors"
            >
              Create account
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-xs text-center text-slate-500 dark:text-slate-400">
              Accepting as <strong>{user?.email}</strong>
            </p>
            <button
              onClick={handleAccept}
              disabled={accepting}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium transition-colors disabled:opacity-60"
            >
              {accepting
                ? <Loader2 size={16} className="animate-spin" />
                : <CheckCircle size={16} />
              }
              {accepting ? 'Accepting…' : 'Accept invitation'}
            </button>
            <Link
              href="/home"
              className="block text-center text-sm text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300 transition-colors"
            >
              Decline
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
