/**
 * useVoiceInput — Microphone recording + Whisper transcription hook
 *
 * TASK-304-F1: Captures audio via the browser MediaRecorder API and
 * POSTs the blob to POST /api/v1/ai/chat/transcribe/ for Whisper transcription.
 *
 * Usage:
 *   const { isRecording, isTranscribing, startRecording, stopRecording, error } = useVoiceInput({
 *     onTranscript: (text) => setInput(text),
 *   })
 */

'use client'

import { useState, useRef, useCallback } from 'react'
import { api } from '@/utils/api'

interface UseVoiceInputOptions {
  /** Called with the transcribed text when transcription completes */
  onTranscript: (text: string) => void
  /** Optional ISO-639-1 language hint, e.g. "en" */
  language?: string
  /** Max recording duration in ms — stops automatically (default 60s) */
  maxDurationMs?: number
}

interface UseVoiceInputReturn {
  isRecording:    boolean
  isTranscribing: boolean
  startRecording: () => Promise<void>
  stopRecording:  () => void
  error:          string | null
  clearError:     () => void
}

export function useVoiceInput({
  onTranscript,
  language,
  maxDurationMs = 60_000,
}: UseVoiceInputOptions): UseVoiceInputReturn {
  const [isRecording,    setIsRecording]    = useState(false)
  const [isTranscribing, setIsTranscribing] = useState(false)
  const [error,          setError]          = useState<string | null>(null)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef        = useRef<Blob[]>([])
  const autoStopRef      = useRef<ReturnType<typeof setTimeout> | null>(null)

  const stopRecording = useCallback(() => {
    if (autoStopRef.current) {
      clearTimeout(autoStopRef.current)
      autoStopRef.current = null
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop()
    }
  }, [])

  const startRecording = useCallback(async () => {
    setError(null)

    if (!navigator.mediaDevices?.getUserMedia) {
      setError('Microphone access is not supported in this browser.')
      return
    }

    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false })
    } catch (err: unknown) {
      const e = err as DOMException
      // Handle each DOMException type specifically (ERR-03)
      if (e.name === 'NotAllowedError' || e.name === 'PermissionDeniedError') {
        setError('Microphone permission denied. Please allow microphone access in your browser settings.')
      } else if (e.name === 'NotFoundError' || e.name === 'DevicesNotFoundError') {
        setError('No microphone found. Please connect a microphone and try again.')
      } else if (e.name === 'SecurityError') {
        setError('Microphone access blocked by browser security policy. Please use HTTPS or check site permissions.')
      } else if (e.name === 'AbortError') {
        setError('Microphone access was interrupted. Please try again.')
      } else if (e.name === 'NotReadableError' || e.name === 'TrackStartError') {
        setError('Microphone is already in use by another application. Please close other apps and try again.')
      } else {
        setError(`Could not access microphone: ${e.message ?? e.name}`)
      }
      return
    }

    chunksRef.current = []

    // Prefer webm/opus (best browser support), fall back to whatever is available
    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : MediaRecorder.isTypeSupported('audio/webm')
        ? 'audio/webm'
        : ''

    const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
    mediaRecorderRef.current = recorder

    recorder.ondataavailable = (e: BlobEvent) => {
      if (e.data.size > 0) chunksRef.current.push(e.data)
    }

    recorder.onstop = async () => {
      // Stop all mic tracks to release the microphone indicator
      stream.getTracks().forEach(t => t.stop())
      setIsRecording(false)

      if (chunksRef.current.length === 0) return

      const audioBlob = new Blob(chunksRef.current, {
        type: mimeType || 'audio/webm',
      })

      // Don't bother transcribing clips shorter than 0.5 s (likely accidental tap)
      if (audioBlob.size < 1024) return

      setIsTranscribing(true)
      try {
        const formData = new FormData()
        formData.append('audio', audioBlob, 'recording.webm')
        if (language) formData.append('language', language)

        const response = await api.post<{ text: string; language: string }>(
          '/ai/chat/transcribe/',
          formData,
          { headers: { 'Content-Type': 'multipart/form-data' } },
        )

        const text = response.data.text?.trim()
        if (text) {
          onTranscript(text)
        } else {
          setError('No speech detected. Please try again.')
        }
      } catch (err: unknown) {
        const axiosErr = err as { response?: { data?: { error?: string }; status?: number } }
        const msg = axiosErr?.response?.data?.error
        if (axiosErr?.response?.status === 503) {
          setError('Voice transcription is not configured on this server.')
        } else {
          setError(msg ?? 'Transcription failed. Please try again.')
        }
      } finally {
        setIsTranscribing(false)
      }
    }

    recorder.start(250)  // collect data every 250ms
    setIsRecording(true)

    // Auto-stop after maxDurationMs
    autoStopRef.current = setTimeout(stopRecording, maxDurationMs)
  }, [language, maxDurationMs, onTranscript, stopRecording])

  return {
    isRecording,
    isTranscribing,
    startRecording,
    stopRecording,
    error,
    clearError: () => setError(null),
  }
}
