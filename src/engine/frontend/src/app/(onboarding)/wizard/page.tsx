/**
 * SYNAPSE Onboarding Wizard — 5-step setup flow for new users.
 *
 * Step 1: Welcome + overview
 * Step 2: Interest selection (chips)
 * Step 3: Use-case selection (radio)
 * Step 4: First search demo
 * Step 5: Completion + confetti
 */
'use client';

import { useState, useEffect, useCallback, memo } from 'react';
import { useRouter } from 'next/navigation';
import ProgressBar from '@/components/onboarding/ProgressBar';
import { useOnboarding } from '@/hooks/useOnboarding';
import { useAuthStore } from '@/store/authStore';

// Types for step components
interface StepTryItProps {
  searchQuery: string;
  onSearchChange: (value: string) => void;
  onQueryButtonClick: (q: string) => void;
}

// StepTryIt component defined OUTSIDE main component to prevent re-render focus issues
const StepTryIt = memo(function StepTryIt({ searchQuery, onSearchChange, onQueryButtonClick }: StepTryItProps) {
  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-2xl font-bold text-white">Take it for a spin 🚀</h2>
        <p className="text-slate-400 mt-2">Type anything you want to research — papers, repos, articles, trends.</p>
      </div>
      <div className="relative">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="e.g. 'latest transformer architectures 2026' or 'best TypeScript frameworks'"
          className="w-full bg-slate-800 border border-slate-600 rounded-xl px-4 py-3.5 pr-12 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition-all"
        />
        <span className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-500">🔍</span>
      </div>
      <div className="bg-slate-800/60 rounded-xl p-4 border border-slate-700/50">
        <p className="text-slate-400 text-sm">
          💡 <strong className="text-slate-300">Tip:</strong> SYNAPSE uses semantic search — it understands meaning,
          not just keywords. Ask natural questions like &quot;what are the best tools for MLOps in 2026?&quot;
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        {['LLM fine-tuning 2026', 'Rust async patterns', 'vector database comparison', 'startup fundraising tips'].map(q => (
          <button
            key={q}
            onClick={() => onQueryButtonClick(q)}
            className="text-xs px-3 py-1.5 bg-slate-700 rounded-lg text-slate-300 hover:bg-slate-600 transition-colors"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
});

// ── Interests ─────────────────────────────────────────────────────────────────
const INTERESTS = [
  { slug: 'ai_ml',        label: '🤖 AI & Machine Learning' },
  { slug: 'web_dev',      label: '🌐 Web Development' },
  { slug: 'security',     label: '🔐 Security & Privacy' },
  { slug: 'cloud_devops', label: '☁️ Cloud & DevOps' },
  { slug: 'research',     label: '📚 Academic Research' },
  { slug: 'data_science', label: '📊 Data Science' },
  { slug: 'open_source',  label: '🐙 Open Source' },
  { slug: 'startup',      label: '🚀 Startups & Business' },
  { slug: 'finance',      label: '💰 Finance & Crypto' },
  { slug: 'health_bio',   label: '🧬 Health & Biotech' },
];

// ── Use Cases ─────────────────────────────────────────────────────────────────
const USE_CASES = [
  { slug: 'research',   label: '📰 Daily Research Digest',   desc: 'Get a personalised morning briefing of what matters in your field.' },
  { slug: 'automation', label: '⚙️ Workflow Automation',      desc: 'Auto-schedule scrapers, alerts, and reports — no code required.' },
  { slug: 'learning',   label: '🎓 Continuous Learning',      desc: 'Build a living knowledge base that grows with you.' },
  { slug: 'archiving',  label: '🗄️ Knowledge Archiving',      desc: 'Save articles, papers, and repos for future reference and search.' },
  { slug: 'team',       label: '👥 Team Collaboration',       desc: 'Share research context and insights across your team.' },
];

const TOTAL_STEPS = 5;

export default function OnboardingWizardPage() {
  const router                = useRouter();
  const { completeStep, finishOnboarding, startOnboarding, loading } = useOnboarding();
  const { user, refreshUser } = useAuthStore();

  const [currentStep,     setCurrentStep]     = useState(1);
  const [selectedInterests, setInterests]     = useState<string[]>([]);
  const [selectedUseCase,   setUseCase]       = useState('');
  const [searchQuery,       setSearchQuery]   = useState('');
  const [finished,          setFinished]      = useState(false);
  const [interestError,     setInterestError] = useState('');
  const [setupStatus,       setSetupStatus]   = useState<string>('');

  // Redirect if already onboarded
  useEffect(() => {
    if (user?.is_onboarded) {
      router.replace('/home');
      return;
    }
    startOnboarding();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleInterest = useCallback((slug: string) => {
    setInterests(prev =>
      prev.includes(slug) ? prev.filter(i => i !== slug) : [...prev, slug]
    );
    setInterestError('');
  }, []);

  const handleNext = useCallback(async () => {
    if (currentStep === 2 && selectedInterests.length === 0) {
      setInterestError('Please select at least one interest to personalise your feed.');
      return;
    }

    let payload: Record<string, unknown> = {};
    if (currentStep === 2) payload = { interests: selectedInterests };
    if (currentStep === 3) payload = { use_case: selectedUseCase };

    await completeStep(currentStep, payload);

    if (currentStep === TOTAL_STEPS) {
      setSetupStatus('Creating your automation workflows...');
      const ok = await finishOnboarding();
      // Always mark as finished and refresh, even if API had issues
      // The backend now processes everything async, so we can redirect quickly
      setFinished(true);
      setSetupStatus('Your personalised SYNAPSE feed is being prepared...');
      await refreshUser?.();
      if (ok) {
        // Short delay to show success message, then redirect
        setTimeout(() => router.replace('/home'), 3000);
      }
      // If not ok, the "Go to Dashboard" button will be shown
      return;
    }
    setCurrentStep(s => s + 1);
  }, [currentStep, selectedInterests, selectedUseCase, completeStep, finishOnboarding, refreshUser, router]);

  const handleBack = () => setCurrentStep(s => Math.max(1, s - 1));
  const handleSkip = useCallback(async () => {
    if (currentStep < TOTAL_STEPS) {
      setCurrentStep(s => s + 1);
    }
    // If skipping the final step, still trigger onboarding workflows
    if (currentStep === TOTAL_STEPS - 1) {
      setSetupStatus('Setting up your default feed...');
      const ok = await finishOnboarding();
      setFinished(true);
      setSetupStatus('Your SYNAPSE feed is being prepared...');
      await refreshUser?.();
      if (ok) {
        setTimeout(() => router.replace('/home'), 3000);
      }
    }
  }, [currentStep, finishOnboarding, refreshUser, router]);

  // ── Step renderers ─────────────────────────────────────────────────────────

  const StepWelcome = () => (
    <div className="text-center space-y-6">
      <div className="text-7xl">🧠</div>
      <div>
        <h1 className="text-3xl font-bold text-white">Welcome to SYNAPSE</h1>
        <p className="text-slate-400 mt-3 text-lg leading-relaxed">
          Your personal AI research intelligence platform. In the next few steps, 
          we&apos;ll personalise your feed so you see exactly what matters to you.
        </p>
      </div>
      <div className="grid grid-cols-2 gap-3 text-left mt-6">
        {[
          { icon: '🔍', title: 'Smart Search',   desc: 'Semantic search across 10M+ technical documents' },
          { icon: '🤖', title: 'AI Agents',       desc: 'Autonomous research agents that think and act' },
          { icon: '⚙️', title: 'Automation',      desc: 'Schedule workflows — no code required' },
          { icon: '📄', title: 'Documents',       desc: 'AI-generated reports from your research' },
        ].map(({ icon, title, desc }) => (
          <div key={title} className="bg-slate-800/60 rounded-xl p-4 border border-slate-700/50">
            <div className="text-2xl mb-2">{icon}</div>
            <div className="font-semibold text-white text-sm">{title}</div>
            <div className="text-slate-400 text-xs mt-1 leading-relaxed">{desc}</div>
          </div>
        ))}
      </div>
    </div>
  );

  const StepInterests = () => (
    <div className="space-y-5">
      <div>
        <h2 className="text-2xl font-bold text-white">What are you interested in?</h2>
        <p className="text-slate-400 mt-2">Select all that apply — we&apos;ll personalise your feed accordingly.</p>
      </div>
      <div className="flex flex-wrap gap-3">
        {INTERESTS.map(({ slug, label }) => {
          const active = selectedInterests.includes(slug);
          return (
            <button
              key={slug}
              onClick={() => toggleInterest(slug)}
              className={`px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 border ${
                active
                  ? 'bg-indigo-600 border-indigo-500 text-white shadow-lg shadow-indigo-500/20'
                  : 'bg-slate-800/60 border-slate-700 text-slate-300 hover:border-indigo-500/50 hover:text-white'
              }`}
            >
              {label}
            </button>
          );
        })}
      </div>
      {interestError && (
        <p className="text-red-400 text-sm">{interestError}</p>
      )}
      {selectedInterests.length > 0 && (
        <p className="text-indigo-400 text-sm">✓ {selectedInterests.length} selected</p>
      )}
    </div>
  );

  const StepUseCase = () => (
    <div className="space-y-5">
      <div>
        <h2 className="text-2xl font-bold text-white">What&apos;s your primary goal?</h2>
        <p className="text-slate-400 mt-2">This helps us surface the right features first.</p>
      </div>
      <div className="space-y-3">
        {USE_CASES.map(({ slug, label, desc }) => {
          const active = selectedUseCase === slug;
          return (
            <button
              key={slug}
              onClick={() => setUseCase(slug)}
              className={`w-full text-left p-4 rounded-xl border transition-all duration-200 ${
                active
                  ? 'bg-indigo-600/20 border-indigo-500 text-white'
                  : 'bg-slate-800/60 border-slate-700 text-slate-300 hover:border-indigo-500/40'
              }`}
            >
              <div className="font-semibold text-sm">{label}</div>
              <div className="text-xs text-slate-400 mt-1">{desc}</div>
            </button>
          );
        })}
      </div>
    </div>
  );

  // Handlers for StepTryIt (memoized to prevent unnecessary re-renders)
  const handleQueryButtonClick = useCallback((q: string) => {
    setSearchQuery(q);
  }, []);

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value);
  }, []);

  const StepDone = () => (
    <div className="text-center space-y-6">
      <div className="text-7xl animate-bounce">🎉</div>
      <div>
        <h2 className="text-3xl font-bold text-white">You&apos;re all set!</h2>
        <p className="text-slate-400 mt-3 text-lg">
          {setupStatus || "Your personalised SYNAPSE feed is being prepared..."}
        </p>
        {setupStatus && (
          <p className="text-slate-500 text-sm mt-2">
            Scraping 5 articles, repos, papers, videos, and tweets just for you.
          </p>
        )}
      </div>
      {selectedInterests.length > 0 && (
        <div className="bg-indigo-600/10 border border-indigo-500/30 rounded-xl p-4">
          <p className="text-indigo-300 text-sm font-medium">Your personalised topics:</p>
          <div className="flex flex-wrap gap-2 mt-2 justify-center">
            {selectedInterests.map(slug => {
              const interest = INTERESTS.find(i => i.slug === slug);
              return interest ? (
                <span key={slug} className="text-xs bg-indigo-600/30 text-indigo-200 px-3 py-1 rounded-full">
                  {interest.label}
                </span>
              ) : null;
            })}
          </div>
        </div>
      )}
      {finished ? (
        <button
          onClick={() => router.replace('/home')}
          className="mt-4 px-8 py-3 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-semibold rounded-xl transition-all duration-200 shadow-lg shadow-indigo-500/20"
        >
          Go to Dashboard
        </button>
      ) : (
        <>
          <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
            <div className="h-full bg-gradient-to-r from-indigo-500 to-violet-500 animate-pulse rounded-full w-full" />
          </div>
          <div className="text-slate-500 text-xs">
            <p>This may take 30-60 seconds while we fetch your personalized content...</p>
          </div>
        </>
      )}
    </div>
  );

  const STEPS = [StepWelcome, StepInterests, StepUseCase, StepTryIt, StepDone];

  return (
    <div className="bg-slate-900/80 backdrop-blur-xl rounded-2xl border border-slate-700/50 shadow-2xl p-8">
      <ProgressBar currentStep={currentStep} totalSteps={TOTAL_STEPS} />

      {/* Step content */}
      <div className="min-h-[300px]">
        {(() => {
          const CurrentStepComponent = STEPS[currentStep - 1];
          if (!CurrentStepComponent) return null;
          // StepTryIt (step 4) needs props; others don't
          if (currentStep === 4) {
            return <StepTryIt
              searchQuery={searchQuery}
              onSearchChange={(val) => handleInputChange({ target: { value: val } } as React.ChangeEvent<HTMLInputElement>)}
              onQueryButtonClick={handleQueryButtonClick}
            />;
          }
          const SafeComponent = CurrentStepComponent as React.FC;
          return <SafeComponent />;
        })()}
      </div>

      {/* Navigation buttons */}
      {!finished && (
        <div className="flex items-center justify-between mt-8 pt-6 border-t border-slate-700/50">
          <button
            onClick={handleBack}
            disabled={currentStep === 1 || loading}
            className="px-5 py-2.5 text-sm text-slate-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            ← Back
          </button>

          <div className="flex gap-3">
            {currentStep < TOTAL_STEPS && currentStep !== 2 && (
              <button
                onClick={handleSkip}
                disabled={loading}
                className="px-5 py-2.5 text-sm text-slate-400 hover:text-white disabled:opacity-30 transition-colors"
              >
                Skip
              </button>
            )}
            <button
              onClick={handleNext}
              disabled={loading}
              className="px-8 py-2.5 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-semibold rounded-xl transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-indigo-500/20"
            >
              {loading
                ? 'Please wait…'
                : currentStep === TOTAL_STEPS
                ? '🚀 Go to Dashboard'
                : 'Next →'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
