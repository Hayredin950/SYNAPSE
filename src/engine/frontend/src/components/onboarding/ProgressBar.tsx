/**
 * Onboarding ProgressBar — shows step progress with labels.
 */
'use client';

interface ProgressBarProps {
  currentStep: number;
  totalSteps: number;
  stepLabels?: string[];
}

const DEFAULT_LABELS = ['Welcome', 'Interests', 'Goal', 'Try It', 'Done'];

export default function ProgressBar({ currentStep, totalSteps, stepLabels = DEFAULT_LABELS }: ProgressBarProps) {
  const progress = Math.round(((currentStep - 1) / (totalSteps - 1)) * 100);

  return (
    <div className="w-full mb-8">
      {/* Step counter */}
      <div className="flex justify-between items-center mb-2">
        <span className="text-xs font-medium text-slate-400">
          Step {currentStep} of {totalSteps}
        </span>
        <span className="text-xs font-medium text-indigo-400">{progress}% complete</span>
      </div>

      {/* Progress bar */}
      <div className="w-full bg-slate-800 rounded-full h-2 mb-4 overflow-hidden">
        <div
          className="h-2 rounded-full bg-gradient-to-r from-indigo-500 to-violet-500 transition-all duration-500 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Step dots */}
      <div className="flex justify-between">
        {stepLabels.slice(0, totalSteps).map((label, idx) => {
          const stepNum  = idx + 1;
          const isDone   = stepNum < currentStep;
          const isCurrent = stepNum === currentStep;
          return (
            <div key={stepNum} className="flex flex-col items-center gap-1">
              <div
                className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-300 ${
                  isDone
                    ? 'bg-indigo-500 text-white'
                    : isCurrent
                    ? 'bg-violet-500 text-white ring-2 ring-violet-300/30'
                    : 'bg-slate-700 text-slate-400'
                }`}
              >
                {isDone ? '✓' : stepNum}
              </div>
              <span className={`text-xs hidden sm:block ${isCurrent ? 'text-violet-300' : 'text-slate-500'}`}>
                {label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
