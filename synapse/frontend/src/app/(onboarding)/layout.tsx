/**
 * Onboarding Layout — minimal, distraction-free shell.
 * No sidebar, no navbar, just centered content on a gradient background.
 */
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Welcome to SYNAPSE',
  description: 'Set up your personalized AI research hub',
};

export default function OnboardingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-indigo-950 to-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-2xl">
        {/* Logo */}
        <div className="text-center mb-8">
          <span className="text-3xl font-black tracking-tight bg-gradient-to-r from-indigo-400 to-violet-400 bg-clip-text text-transparent">
            SYNAPSE
          </span>
          <p className="text-slate-400 text-sm mt-1">AI Research Intelligence Platform</p>
        </div>
        {children}
      </div>
    </div>
  );
}
