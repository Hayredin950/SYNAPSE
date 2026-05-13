'use client'

import React, { useState, useEffect, useRef, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  X, ExternalLink, MessageSquare, Loader2, Clock, Share2, BookOpen,
  Swords, Languages, Code2, Volume2, Play, Pause,
  ChevronDown, Check, Copy, Tag,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api } from '@/utils/api'
import { BookmarkButton } from '@/components/BookmarkButton'
import { useRouter } from 'next/navigation'
import toast from 'react-hot-toast'
import { cn } from '@/utils/helpers'
import { RelatedArticles } from '@/components/ui/RelatedArticles'
import { CommentsSection } from '@/components/ui/CommentsSection'
import { UpvoteButton } from '@/components/ui/UpvoteButton'
import { ContentHighlighter } from '@/components/ui/ContentHighlighter'
import { FocusModeButton } from '@/components/ui/FocusMode'
import { SourceQualityBadge } from '@/components/ui/SourceQuality'
import { ReadingTimer } from '@/components/ui/ReadingTimer'

export interface ReaderArticle {
  id:           string
  title:        string
  summary?:     string
  url:          string
  scraped_at:   string
  tags?:        string[]
  topic?:       string
  source_type?: string
  content_type?: string
}

interface Props {
  article: ReaderArticle | null
  onClose: () => void
}

type Tab = 'summary' | 'ai' | 'debate' | 'translate' | 'code' | 'tts'

const TABS: { id: Tab; label: string; title: string }[] = [
  { id: 'summary',   label: '📝', title: 'Summary'   },
  { id: 'ai',        label: '🤖', title: 'Deep-Dive'  },
  { id: 'debate',    label: '⚔️', title: 'Debate'     },
  { id: 'translate', label: '🌍', title: 'Translate'  },
  { id: 'code',      label: '💻', title: 'Code'       },
  { id: 'tts',       label: '🔊', title: 'Listen'     },
]

const LANGUAGES = ['Spanish','French','German','Chinese','Japanese','Portuguese','Arabic','Hindi','Korean','Russian']

const SOURCE_COLOURS: Record<string, string> = {
  hackernews: 'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300',
  reddit:     'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300',
  arxiv:      'bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300',
  github:     'bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300',
  youtube:    'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300',
  default:    'bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300',
}

function ReadingTime({ text, wpm = 250 }: { text: string; wpm?: number }) {
  const mins = Math.max(1, Math.ceil(text.trim().split(/\s+/).length / wpm))
  return (
    <span className="flex items-center gap-1 text-xs text-slate-400 dark:text-slate-500">
      <Clock size={11} /> {mins} min read
    </span>
  )
}

// ── TTS Player ────────────────────────────────────────────────────────────────
function TTSPlayer({ text }: { text: string }) {
  const [loading,  setLoading]  = useState(false)
  const [playing,  setPlaying]  = useState(false)
  const [error,    setError]    = useState('')
  const [voice,    setVoice]    = useState('alloy')
  const [progress, setProgress] = useState(0)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const urlRef   = useRef<string>('')
  const VOICES   = ['alloy','echo','fable','onyx','nova','shimmer']

  const generate = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const resp = await api.post('/ai/tts/', { text: text.slice(0, 3000), voice }, { responseType: 'blob' })
      const url  = URL.createObjectURL(resp.data)
      if (urlRef.current) URL.revokeObjectURL(urlRef.current)
      urlRef.current = url
      const audio = new Audio(url)
      audioRef.current = audio
      audio.ontimeupdate = () => setProgress(audio.duration ? (audio.currentTime / audio.duration) * 100 : 0)
      audio.onended = () => { setPlaying(false); setProgress(0) }
      audio.play(); setPlaying(true)
    } catch { setError('TTS unavailable — audio generation not supported by this proxy.') }
    finally { setLoading(false) }
  }, [text, voice])

  const togglePlay = () => {
    if (!audioRef.current) { generate(); return }
    if (playing) { audioRef.current.pause(); setPlaying(false) }
    else { audioRef.current.play(); setPlaying(true) }
  }

  useEffect(() => () => { audioRef.current?.pause(); if (urlRef.current) URL.revokeObjectURL(urlRef.current) }, [])

  return (
    <div className="space-y-4">
      <div className="bg-gradient-to-br from-indigo-50 to-violet-50 dark:from-indigo-900/20 dark:to-violet-900/20 rounded-2xl p-5 border border-indigo-100 dark:border-indigo-800">
        <div className="flex items-center gap-2 mb-4">
          <Volume2 size={18} className="text-indigo-500" />
          <div>
            <h3 className="font-semibold text-sm text-slate-800 dark:text-slate-100">AI Text-to-Speech</h3>
            <p className="text-xs text-slate-400">Listen to this article read aloud</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5 mb-4">
          {VOICES.map(v => (
            <button key={v} onClick={() => { setVoice(v); audioRef.current?.pause(); audioRef.current = null; setPlaying(false); setProgress(0) }}
              className={cn('px-2.5 py-1 rounded-lg text-xs font-medium capitalize transition-all border',
                voice === v ? 'bg-indigo-600 text-white border-indigo-600' : 'border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300 hover:border-indigo-400')}>
              {v}
            </button>
          ))}
        </div>
        {progress > 0 && <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-1.5 mb-4"><div className="h-1.5 bg-indigo-500 rounded-full transition-all" style={{ width: `${progress}%` }} /></div>}
        {error
          ? <div className="text-xs text-red-500 bg-red-50 dark:bg-red-900/20 rounded-xl p-3">{error}</div>
          : <button onClick={togglePlay} disabled={loading} className="w-full flex items-center justify-center gap-2 py-3 bg-indigo-600 text-white rounded-xl font-medium hover:bg-indigo-700 disabled:opacity-60 transition-colors">
              {loading ? <><Loader2 size={18} className="animate-spin" /> Generating audio…</>
               : playing ? <><Pause size={18} /> Pause</> : <><Play size={18} /> {audioRef.current ? 'Resume' : 'Listen'}</>}
            </button>
        }
      </div>
    </div>
  )
}

// ── Code Card ─────────────────────────────────────────────────────────────────
function CodeCard({ snippet }: { snippet: any }) {
  const [copied, setCopied] = useState(false)
  const copy = () => { navigator.clipboard.writeText(snippet.code); setCopied(true); setTimeout(() => setCopied(false), 2000) }
  return (
    <div className="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 bg-slate-800 dark:bg-slate-900">
        <span className="text-xs font-mono text-slate-400 capitalize">{snippet.language}</span>
        <button onClick={copy} className="text-slate-400 hover:text-white transition-colors">
          {copied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
        </button>
      </div>
      <pre className="text-xs font-mono text-slate-200 bg-slate-900 p-3 overflow-x-auto whitespace-pre-wrap">{snippet.code}</pre>
      {snippet.explanation && <div className="px-3 py-2 bg-slate-50 dark:bg-slate-800 text-xs text-slate-500 dark:text-slate-400 border-t border-slate-200 dark:border-slate-700">{snippet.explanation}</div>}
    </div>
  )
}

// ── Main Modal ────────────────────────────────────────────────────────────────
export function ContentReaderModal({ article, onClose }: Props) {
  const router = useRouter()
  const [tab,           setTab]           = useState<Tab>('summary')
  const [aiAnalysis,    setAiAnalysis]    = useState('')
  const [debate,        setDebate]        = useState('')
  const [translation,   setTranslation]   = useState('')
  const [codeSnippets,  setCodeSnippets]  = useState<any[]>([])
  const [loadingMap,    setLoadingMap]    = useState<Record<Tab, boolean>>({ summary:false, ai:false, debate:false, translate:false, code:false, tts:false })
  const [targetLang,    setTargetLang]    = useState('Spanish')
  const [showLangMenu,  setShowLangMenu]  = useState(false)
  const [wpm,           setWpm]           = useState(250)

  const content = article?.summary || ''

  useEffect(() => {
    if (typeof window !== 'undefined') {
      try { const s = JSON.parse(localStorage.getItem('synapse_reading_stats') || '{}'); setWpm(s.wpm || 250) } catch {}
    }
  }, [])

  useEffect(() => {
    if (!article) { setAiAnalysis(''); setDebate(''); setTranslation(''); setCodeSnippets([]); return }
    setAiAnalysis(''); setTab('summary')
    setLoadingMap(m => ({ ...m, ai: true }))
    api.post('/ai/deep-dive/', { title: article.title, content: article.summary || '' })
      .then(r => setAiAnalysis(r.data?.analysis || r.data?.summary || r.data?.content || ''))
      .catch(() => api.post('/ai/summarize/', { title: article.title, content: article.summary || '', url: article.url, mode: 'extended' })
        .then(r2 => setAiAnalysis(r2.data?.summary || article.summary || ''))
        .catch(() => setAiAnalysis(article.summary || '')))
      .finally(() => setLoadingMap(m => ({ ...m, ai: false })))
  }, [article?.id])

  const fetchTab = async (t: Tab) => {
    setTab(t)
    if (!article) return

    if (t === 'debate' && !debate) {
      setLoadingMap(m => ({ ...m, debate: true }))
      try {
        const { data } = await api.post('/ai/debate/', { title: article.title, content: article.summary || '' })
        setDebate(data.debate || '')
      } catch { setDebate('⚠️ Debate analysis unavailable.') }
      finally { setLoadingMap(m => ({ ...m, debate: false })) }
    }

    if (t === 'code' && codeSnippets.length === 0) {
      setLoadingMap(m => ({ ...m, code: true }))
      try {
        const { data } = await api.post('/ai/code-extract/', { title: article.title, content: article.summary || '' })
        setCodeSnippets(data.snippets || [])
      } catch { setCodeSnippets([]) }
      finally { setLoadingMap(m => ({ ...m, code: false })) }
    }
  }

  const fetchTranslation = async () => {
    if (!article) return
    setLoadingMap(m => ({ ...m, translate: true }))
    setTranslation('')
    try {
      const { data } = await api.post('/ai/translate/', { title: article.title, text: article.summary || '', target_language: targetLang })
      setTranslation(data.translated || '')
    } catch { setTranslation('⚠️ Translation unavailable.') }
    finally { setLoadingMap(m => ({ ...m, translate: false })) }
  }

  const srcColour = SOURCE_COLOURS[article?.source_type?.toLowerCase() ?? ''] ?? SOURCE_COLOURS.default

  if (typeof window === 'undefined') return null

  return createPortal(
    <AnimatePresence>
      {article && (
        <motion.div
          key="reader-backdrop"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          className="fixed inset-0 z-[150] flex items-end sm:items-center justify-center sm:p-6 bg-black/60 backdrop-blur-sm"
          onClick={onClose}
        >
          <motion.div
            key="reader-panel"
            initial={{ y: 60, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 60, opacity: 0 }}
            transition={{ type: 'spring', damping: 30, stiffness: 320 }}
            className="bg-white dark:bg-slate-900 rounded-t-3xl sm:rounded-2xl border border-slate-200 dark:border-slate-700 shadow-2xl w-full max-w-3xl max-h-[92vh] flex flex-col overflow-hidden"
            onClick={e => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-start justify-between gap-4 px-5 sm:px-6 pt-5 pb-3 border-b border-slate-100 dark:border-slate-800 flex-shrink-0">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap mb-1.5">
                  {article.source_type && (
                    <span className={cn('inline-block text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded-full', srcColour)}>
                      {article.source_type}
                    </span>
                  )}
                  {content && <ReadingTime text={content} wpm={wpm} />}
                  {article.source_type && <SourceQualityBadge source={article.source_type} size="sm" />}
                  <UpvoteButton articleId={article.id} contentType={article.content_type || 'article'} />
                </div>
                <h2 className="text-base sm:text-xl font-bold text-slate-900 dark:text-white leading-snug">{article.title}</h2>
                {article.tags && article.tags.length > 0 && (
                  <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
                    {article.tags.slice(0, 4).map(tag => (
                      <span key={tag} className="flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400">
                        <Tag size={9} /> {tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <button onClick={onClose} className="w-8 h-8 flex items-center justify-center rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 flex-shrink-0 transition-colors">
                <X size={16} />
              </button>
            </div>

            {/* Tab bar */}
            <div className="flex items-center gap-0.5 px-3 py-2 border-b border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50 flex-shrink-0 overflow-x-auto scrollbar-hide">
              {TABS.map(t => (
                <button
                  key={t.id}
                  onClick={() => fetchTab(t.id)}
                  className={cn(
                    'flex items-center gap-1 px-3 py-1.5 rounded-xl text-xs font-medium transition-all whitespace-nowrap',
                    tab === t.id
                      ? 'bg-white dark:bg-slate-700 text-indigo-600 dark:text-indigo-400 shadow-sm'
                      : 'text-slate-500 dark:text-slate-400 hover:bg-white/60 dark:hover:bg-slate-700/60',
                  )}
                >
                  <span>{t.label}</span> <span>{t.title}</span>
                  {loadingMap[t.id] && <Loader2 size={10} className="animate-spin ml-0.5" />}
                </button>
              ))}
            </div>

            {/* Tab body */}
            <div className="flex-1 overflow-y-auto px-5 sm:px-6 py-4 space-y-4">
              {tab === 'summary' && (
                article.summary
                  ? <div className="prose prose-sm prose-slate dark:prose-invert max-w-none"><ReactMarkdown remarkPlugins={[remarkGfm]}>{article.summary}</ReactMarkdown></div>
                  : <div className="text-center py-10 text-slate-400"><BookOpen size={32} className="mx-auto mb-3 opacity-40" /><p className="text-sm">No summary available yet.</p></div>
              )}

              {tab === 'ai' && (
                loadingMap.ai
                  ? <div className="flex flex-col items-center gap-3 py-12"><Loader2 size={28} className="animate-spin text-indigo-500" /><p className="text-sm text-slate-400">Generating AI analysis…</p></div>
                  : aiAnalysis
                    ? <div className="prose prose-sm prose-slate dark:prose-invert max-w-none"><ReactMarkdown remarkPlugins={[remarkGfm]}>{aiAnalysis}</ReactMarkdown></div>
                    : <p className="text-sm text-slate-400 text-center py-10">AI analysis unavailable.</p>
              )}

              {tab === 'debate' && (
                loadingMap.debate
                  ? <div className="flex flex-col items-center gap-3 py-12"><Loader2 size={28} className="animate-spin text-indigo-500" /><p className="text-sm text-slate-400">Generating debate analysis…</p></div>
                  : debate
                    ? <div className="prose prose-sm prose-slate dark:prose-invert max-w-none"><ReactMarkdown remarkPlugins={[remarkGfm]}>{debate}</ReactMarkdown></div>
                    : <div className="text-center py-10"><p className="text-sm text-slate-400 mb-3">Get balanced pro/con arguments on this article.</p><button onClick={() => fetchTab('debate')} className="px-4 py-2 bg-indigo-600 text-white rounded-xl text-sm hover:bg-indigo-700 transition-colors">Start Debate Analysis</button></div>
              )}

              {tab === 'translate' && (
                <div className="space-y-4">
                  <div className="flex items-center gap-3 flex-wrap">
                    <span className="text-sm text-slate-600 dark:text-slate-400">Translate to:</span>
                    <div className="relative">
                      <button onClick={() => setShowLangMenu(!showLangMenu)} className="flex items-center gap-2 px-3 py-1.5 border border-slate-200 dark:border-slate-600 rounded-xl text-sm bg-white dark:bg-slate-800 hover:border-indigo-400">
                        {targetLang} <ChevronDown size={14} />
                      </button>
                      {showLangMenu && (
                        <div className="absolute top-full left-0 mt-1 bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 shadow-xl z-10 py-1 w-40">
                          {LANGUAGES.map(lang => (
                            <button key={lang} onClick={() => { setTargetLang(lang); setShowLangMenu(false); setTranslation('') }} className={cn('w-full text-left px-4 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-700', targetLang === lang ? 'text-indigo-600 dark:text-indigo-400 font-medium' : 'text-slate-700 dark:text-slate-300')}>
                              {lang}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                    <button onClick={fetchTranslation} disabled={loadingMap.translate} className="flex items-center gap-2 px-4 py-1.5 bg-indigo-600 text-white rounded-xl text-sm hover:bg-indigo-700 disabled:opacity-60">
                      {loadingMap.translate ? <Loader2 size={14} className="animate-spin" /> : '🌍'} Translate
                    </button>
                  </div>
                  {loadingMap.translate
                    ? <div className="flex flex-col items-center gap-3 py-10"><Loader2 size={28} className="animate-spin text-indigo-500" /><p className="text-sm text-slate-400">Translating to {targetLang}…</p></div>
                    : translation
                      ? <div className="prose prose-sm prose-slate dark:prose-invert max-w-none"><ReactMarkdown remarkPlugins={[remarkGfm]}>{translation}</ReactMarkdown></div>
                      : <p className="text-sm text-slate-400 py-4">Select a language and click Translate.</p>
                  }
                </div>
              )}

              {tab === 'code' && (
                loadingMap.code
                  ? <div className="flex flex-col items-center gap-3 py-12"><Loader2 size={28} className="animate-spin text-indigo-500" /><p className="text-sm text-slate-400">Extracting code snippets…</p></div>
                  : codeSnippets.length > 0
                    ? <div className="space-y-4"><p className="text-xs text-slate-400">{codeSnippets.length} snippet{codeSnippets.length !== 1 ? 's' : ''} found</p>{codeSnippets.map((s, i) => <CodeCard key={i} snippet={s} />)}</div>
                    : <div className="text-center py-10"><Code2 size={32} className="mx-auto mb-3 text-slate-300 dark:text-slate-600" /><p className="text-sm text-slate-400">No code snippets detected in this article.</p></div>
              )}

              {tab === 'tts' && <TTSPlayer text={content || article?.title || ''} />}

              {/* Related Articles — shown in summary tab */}
              {tab === 'summary' && article && <RelatedArticles articleId={article.id} />}

              {/* Comments — shown in all tabs */}
              {article && <CommentsSection articleId={article.id} />}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between gap-3 px-5 sm:px-6 py-3 border-t border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50 flex-shrink-0">
              <div className="flex items-center gap-1 flex-wrap">
                <BookmarkButton contentType={(article.content_type as any) || 'article'} objectId={article.id} size={15} />
                <button onClick={() => { navigator.clipboard.writeText(article.url); toast.success('Link copied!') }} className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-800">
                  <Share2 size={12} /> Share
                </button>
                <button onClick={() => { onClose(); router.push(`/chat?q=${encodeURIComponent('Discuss: ' + article.title)}`) }} className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-900/30">
                  <MessageSquare size={12} /> Ask AI
                </button>
                <ContentHighlighter articleId={article.id} />
                <FocusModeButton />
              </div>
              <a href={article.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm">
                Read Original <ExternalLink size={12} />
              </a>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  )
}
