/**
 * useTextToSpeech — Browser SpeechSynthesis API hook
 *
 * TASK-304-F2: Uses the Web Speech API (window.speechSynthesis) to read
 * AI responses aloud. No API key required — runs entirely in the browser.
 *
 * Usage:
 *   const { isSpeaking, speak, stop, isSupported } = useTextToSpeech()
 *   speak("Hello, world!")    // starts TTS
 *   stop()                    // stops immediately
 */

'use client'

import { useState, useRef, useCallback, useEffect } from 'react'

interface UseTextToSpeechReturn {
  isSpeaking:  boolean
  isSupported: boolean
  speak:       (text: string) => void
  stop:        () => void
}

export function useTextToSpeech(): UseTextToSpeechReturn {
  const [isSpeaking,  setIsSpeaking]  = useState(false)
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null)

  // Check browser support (only available in browser, not SSR)
  const isSupported =
    typeof window !== 'undefined' && 'speechSynthesis' in window

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (isSupported) window.speechSynthesis.cancel()
    }
  }, [isSupported])

  const stop = useCallback(() => {
    if (!isSupported) return
    window.speechSynthesis.cancel()
    setIsSpeaking(false)
  }, [isSupported])

  const speak = useCallback((text: string) => {
    if (!isSupported || !text.trim()) return

    // Cancel any current speech
    window.speechSynthesis.cancel()
    setIsSpeaking(false)

    // Strip markdown-style formatting for cleaner TTS
    const clean = text
      .replace(/```[\s\S]*?```/g, 'code block')   // code blocks → "code block"
      .replace(/`[^`]+`/g, '')                     // inline code → removed
      .replace(/\*\*([^*]+)\*\*/g, '$1')           // bold → plain
      .replace(/\*([^*]+)\*/g, '$1')               // italic → plain
      .replace(/#+\s/g, '')                         // headings → plain
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')    // links → link text only
      .replace(/\n{2,}/g, '. ')                    // paragraph breaks → pause
      .replace(/\n/g, ' ')
      .trim()

    if (!clean) return

    const utterance = new SpeechSynthesisUtterance(clean)
    utteranceRef.current = utterance

    // Select the best available English voice using a robust scoring strategy.
    // Avoid name.includes('Natural') — this string is browser/OS-specific and
    // unreliable across Chrome, Firefox, Safari, and mobile browsers.
    // Instead score by: local service (lower latency) + en-US preference + non-robot names.
    const voices = window.speechSynthesis.getVoices()
    const enVoices = voices.filter(v => v.lang.startsWith('en'))

    const scoreVoice = (v: SpeechSynthesisVoice): number => {
      let score = 0
      if (v.localService) score += 10          // local = lower latency, no network
      if (v.lang === 'en-US') score += 5       // prefer US English
      else if (v.lang === 'en-GB') score += 3  // British English as fallback
      // Prefer voices that are known to sound natural (cross-browser safe names)
      const lower = v.name.toLowerCase()
      if (lower.includes('samantha') || lower.includes('karen') ||
          lower.includes('daniel') || lower.includes('moira') ||
          lower.includes('fiona') || lower.includes('alex')) score += 4
      // Deprioritise obviously robotic/legacy voices
      if (lower.includes('espeak') || lower.includes('mbrola')) score -= 5
      return score
    }

    const preferredVoice = enVoices.length > 0
      ? enVoices.reduce((best, v) => scoreVoice(v) >= scoreVoice(best) ? v : best)
      : null

    if (preferredVoice) utterance.voice = preferredVoice
    utterance.rate   = 1.0
    utterance.pitch  = 1.0
    utterance.volume = 1.0

    utterance.onstart = () => setIsSpeaking(true)
    utterance.onend   = () => setIsSpeaking(false)
    utterance.onerror = () => setIsSpeaking(false)

    window.speechSynthesis.speak(utterance)
  }, [isSupported])

  return { isSpeaking, isSupported, speak, stop }
}
