'use client'

/**
 * Feature #21: Interest Profile Builder
 * Onboarding quiz to auto-configure the user's feed.
 */

import React, { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Check, ChevronRight, Sparkles, X } from 'lucide-react'
import { cn } from '@/utils/helpers'

const TOPICS = [
  { id: 'ai',          label: 'AI & Machine Learning', emoji: '🤖' },
  { id: 'web',         label: 'Web Development',       emoji: '🌐' },
  { id: 'devops',      label: 'DevOps & Cloud',         emoji: '☁️' },
  { id: 'security',    label: 'Cybersecurity',          emoji: '🔒' },
  { id: 'rust',        label: 'Systems & Rust',         emoji: '⚙️' },
  { id: 'mobile',      label: 'Mobile Development',     emoji: '📱' },
  { id: 'data',        label: 'Data Engineering',       emoji: '📊' },
  { id: 'research',    label: 'Research Papers',        emoji: '📄' },
  { id: 'startup',     label: 'Startups & Business',    emoji: '🚀' },
  { id: 'open_source', label: 'Open Source',            emoji: '💻' },
  { id: 'blockchain',  label: 'Blockchain & Web3',      emoji: '⛓️' },
  { id: 'ux',          label: 'Design & UX',            emoji: '🎨' },
]

const EXPERIENCE = [
  { id: 'student',    label: 'Student',          desc: 'Learning to code' },
  { id: 'junior',     label: 'Junior',           desc: '1-3 years exp.' },
  { id: 'mid',        label: 'Mid-level',        desc: '3-7 years exp.' },
  { id: 'senior',     label: 'Senior',           desc: '7+ years exp.' },
  { id: 'principal',  label: 'Staff/Principal',  desc: 'Org-wide impact' },
]

const READING_GOALS_OPTS = [
  { id: 'stay_current', label: 'Stay current with tech trends' },
  { id: 'learn',        label: 'Learn new skills' },
  { id: 'research',     label: 'Conduct research' },
  { id: 'networking',   label: 'Find discussion topics' },
  { id: 'inspiration',  label: 'Get inspired & discover ideas' },
]

const STEP_COUNT = 3

export function InterestProfileBuilder({ onClose }: { onClose?: () => void }) {
  const [step,     setStep]     = useState(0)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [expLevel, setExpLevel] = useState('')
  const [goals,    setGoals]    = useState<Set<string>>(new Set())
  const [done,     setDone]     = useState(false)
  const [mounted,  setMounted]  = useState(false)

  useEffect(() => { setMounted(true) }, [])

  const toggleTopic = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const toggleGoal = (id: string) => {
    setGoals(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const finish = () => {
    const profile = { topics: [...selected], experience: expLevel, goals: [...goals], version: 1 }
    localStorage.setItem('synapse_interest_profile', JSON.stringify(profile))
    localStorage.setItem('synapse_profile_built', '1')
    setDone(true)
    setTimeout(() => onClose?.(), 2000)
  }

  if (!mounted) return null

  const modal = (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      >
        <motion.div
          className="bg-white dark:bg-slate-800 rounded-3xl shadow-2xl w-full max-w-lg overflow-hidden"
          initial={{ scale: 0.9, y: 30 }} animate={{ scale: 1, y: 0 }}
        >
          {done ? (
            <div className="p-12 text-center space-y-4">
              <div className="text-5xl">✨</div>
              <h2 className="text-xl font-bold text-slate-800 dark:text-slate-100">Profile saved!</h2>
              <p className="text-sm text-slate-500">Your feed is now personalized to your interests.</p>
            </div>
          ) : (
            <>
              {/* Progress */}
              <div className="flex h-1.5 bg-slate-100 dark:bg-slate-700">
                {Array.from({ length: STEP_COUNT }, (_, i) => (
                  <div key={i} className={cn('flex-1 transition-all duration-500', i <= step ? 'bg-indigo-500' : '')} />
                ))}
              </div>

              <div className="p-6 space-y-5">
                {/* Step 0: Topics */}
                {step === 0 && (
                  <div className="space-y-4">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <Sparkles size={18} className="text-indigo-500" />
                        <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100">What interests you?</h2>
                      </div>
                      <p className="text-sm text-slate-500">Pick all that apply (min. 2)</p>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                      {TOPICS.map(t => (
                        <button
                          key={t.id}
                          onClick={() => toggleTopic(t.id)}
                          className={cn(
                            'flex items-center gap-2 px-3 py-2.5 rounded-xl border-2 text-left text-sm font-medium transition-all',
                            selected.has(t.id)
                              ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300'
                              : 'border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300 hover:border-indigo-300',
                          )}
                        >
                          <span>{t.emoji}</span>
                          <span className="text-xs">{t.label}</span>
                          {selected.has(t.id) && <Check size={12} className="ml-auto text-indigo-500" />}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Step 1: Experience */}
                {step === 1 && (
                  <div className="space-y-4">
                    <div>
                      <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100">Your experience level?</h2>
                      <p className="text-sm text-slate-500">We'll tune content depth accordingly</p>
                    </div>
                    <div className="space-y-2">
                      {EXPERIENCE.map(e => (
                        <button
                          key={e.id}
                          onClick={() => setExpLevel(e.id)}
                          className={cn(
                            'w-full flex items-center justify-between px-4 py-3 rounded-xl border-2 text-left transition-all',
                            expLevel === e.id
                              ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/30'
                              : 'border-slate-200 dark:border-slate-600 hover:border-indigo-300',
                          )}
                        >
                          <div>
                            <div className="text-sm font-semibold text-slate-700 dark:text-slate-200">{e.label}</div>
                            <div className="text-xs text-slate-400">{e.desc}</div>
                          </div>
                          {expLevel === e.id && <Check size={18} className="text-indigo-500" />}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Step 2: Goals */}
                {step === 2 && (
                  <div className="space-y-4">
                    <div>
                      <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100">Reading goals?</h2>
                      <p className="text-sm text-slate-500">Pick all that apply</p>
                    </div>
                    <div className="space-y-2">
                      {READING_GOALS_OPTS.map(g => (
                        <button
                          key={g.id}
                          onClick={() => toggleGoal(g.id)}
                          className={cn(
                            'w-full flex items-center gap-3 px-4 py-3 rounded-xl border-2 text-left transition-all',
                            goals.has(g.id)
                              ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/30'
                              : 'border-slate-200 dark:border-slate-600 hover:border-indigo-300',
                          )}
                        >
                          <span className="text-sm text-slate-700 dark:text-slate-200">{g.label}</span>
                          {goals.has(g.id) && <Check size={16} className="ml-auto text-indigo-500 flex-shrink-0" />}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Footer */}
                <div className="flex items-center justify-between pt-2">
                  {step > 0
                    ? <button onClick={() => setStep(s => s - 1)} className="text-sm text-slate-500 hover:text-slate-700 dark:hover:text-slate-300">← Back</button>
                    : <div />
                  }
                  {step < STEP_COUNT - 1 ? (
                    <button
                      onClick={() => setStep(s => s + 1)}
                      disabled={step === 0 && selected.size < 2}
                      className="flex items-center gap-2 px-5 py-2 bg-indigo-600 text-white rounded-xl text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
                    >
                      Next <ChevronRight size={16} />
                    </button>
                  ) : (
                    <button
                      onClick={finish}
                      disabled={goals.size === 0}
                      className="flex items-center gap-2 px-5 py-2 bg-emerald-600 text-white rounded-xl text-sm font-medium hover:bg-emerald-700 disabled:opacity-50 transition-colors"
                    >
                      <Sparkles size={16} /> Build My Feed
                    </button>
                  )}
                </div>
              </div>
            </>
          )}
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )

  return createPortal(modal, document.body)
}

// Hook to check if profile has been built
export function useInterestProfile() {
  const [profile,  setProfile]  = useState<any>(null)
  const [needsBuild, setNeedsBuild] = useState(false)
  useEffect(() => {
    const built = localStorage.getItem('synapse_profile_built') === '1'
    setNeedsBuild(!built)
    if (built) {
      try { setProfile(JSON.parse(localStorage.getItem('synapse_interest_profile') || 'null')) }
      catch {}
    }
  }, [])
  return { profile, needsBuild }
}
