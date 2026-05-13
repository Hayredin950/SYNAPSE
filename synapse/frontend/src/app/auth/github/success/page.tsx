/**
 * GitHub OAuth Success Page
 * Receives JWT tokens from the backend redirect, stores them, then routes user
 * to onboarding wizard (new users) or dashboard (returning users).
 */
'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuthStore } from '@/store/authStore';

function GitHubSuccessContent() {
  const router       = useRouter();
  const searchParams = useSearchParams();
  const { refreshUser, setTokens } = useAuthStore();
  const [error, setError] = useState('');

  useEffect(() => {
    const access      = searchParams.get('access');
    const refresh     = searchParams.get('refresh');
    const isOnboarded = searchParams.get('is_onboarded') === 'true';
    const errorParam  = searchParams.get('error');

    if (errorParam) {
      const messages: Record<string, string> = {
        github_denied:         'GitHub access was denied. Please try again.',
        github_no_email:       'Could not retrieve your GitHub email. Make sure your email is public or verified.',
        github_token_failed:   'GitHub authentication failed. Please try again.',
        github_profile_failed: 'Could not fetch your GitHub profile. Please try again.',
      };
      setError(messages[errorParam] ?? 'GitHub sign-in failed. Please try again.');
      return;
    }

    if (!access || !refresh) {
      setError('Authentication tokens missing. Please try signing in again.');
      return;
    }

    setTokens(access, refresh);
    refreshUser?.().then(() => {
      if (isOnboarded) {
        router.replace('/home');
      } else {
        router.replace('/wizard');
      }
    });
  }, [searchParams, router, refreshUser, setTokens]);

  if (error) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
        <div className="bg-slate-900 border border-red-500/30 rounded-2xl p-8 max-w-md w-full text-center">
          <div className="text-5xl mb-4">😕</div>
          <h2 className="text-xl font-bold text-white mb-2">Sign-in Failed</h2>
          <p className="text-slate-400 text-sm mb-6">{error}</p>
          <button
            onClick={() => router.replace('/login')}
            className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-medium transition-colors"
          >
            Back to Login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center">
      <div className="text-center space-y-4">
        <div className="w-12 h-12 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto" />
        <p className="text-slate-400">Signing you in with GitHub…</p>
      </div>
    </div>
  );
}

export default function GitHubSuccessPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-slate-950 flex items-center justify-center">
          <div className="w-12 h-12 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
        </div>
      }
    >
      <GitHubSuccessContent />
    </Suspense>
  );
}
