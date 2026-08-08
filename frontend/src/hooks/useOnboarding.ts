/**
 * useOnboarding — hooks for the 5-step onboarding wizard.
 * Talks to /api/v1/auth/onboarding/* endpoints.
 */
'use client';

import { useState, useCallback } from 'react';
import { api } from '@/utils/api';

export interface OnboardingState {
  is_onboarded: boolean;
  current_step: number;
  total_steps: number;
  completed: boolean;
  interests: string[];
  use_case: string;
  step_config: { title: string; description: string };
}

export function useOnboarding() {
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  const getStatus = useCallback(async (): Promise<OnboardingState | null> => {
    try {
      setLoading(true);
      const res = await api.get('/auth/onboarding/status/');
      return res.data as OnboardingState;
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { error?: string } } })?.response?.data?.error ?? 'Failed to fetch onboarding status';
      setError(msg);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const startOnboarding = useCallback(async (): Promise<OnboardingState | null> => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.post('/auth/onboarding/start/');
      return res.data as OnboardingState;
    } catch {
      setError('Failed to start onboarding');
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const completeStep = useCallback(async (
    step: number,
    payload?: Record<string, unknown>
  ): Promise<OnboardingState | null> => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.post(`/auth/onboarding/steps/${step}/complete/`, payload ?? {});
      return res.data as OnboardingState;
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { error?: string } } })?.response?.data?.error ?? 'Failed to complete step';
      setError(msg);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const finishOnboarding = useCallback(async (): Promise<boolean> => {
    try {
      setLoading(true);
      setError(null);
      await api.post('/auth/onboarding/finish/');
      return true;
    } catch {
      setError('Failed to finish onboarding');
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  return { getStatus, startOnboarding, completeStep, finishOnboarding, loading, error };
}
