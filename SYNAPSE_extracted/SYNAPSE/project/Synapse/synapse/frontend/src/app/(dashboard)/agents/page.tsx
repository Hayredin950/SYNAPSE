'use client'

/**
 * Phase 5.4 — Agent UI (merged with Documents)
 * /agents page: command interface, active tasks, task history, SSE progress
 * + Files tab: document generation (PDF/PPT/Word/Markdown) & management
 */

import React, { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import { formatDistanceToNow } from 'date-fns'
import {
  Bot,
  Brain,
  Send,
  X,
  ChevronDown,
  ChevronUp,
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  Zap,
  DollarSign,
  Timer,
  FileText,
  Search,
  TrendingUp,
  GitBranch,
  BookOpen,
  Sparkles,
  AlertCircle,
  Download,
  RefreshCw,
  Terminal,
  Copy,
  Check,
  FileCode,
  FileJson,
  Archive,
  FolderOpen,
  Presentation,
  FileType,
  Cpu,
  Package,
  ExternalLink,
  Plus,
  Trash2,
  Eye,
  HardDrive,
  Cloud,
  Globe,
  File,
  FolderGit2,
  FileCode2,
  Link2,
  LayoutTemplate,
} from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '@/utils/api'
import { cn } from '@/utils/helpers'
import type { AgentTask, AgentTaskType, AgentTool, AgentIntermediateStep } from '@/types'
import { useApiKeyStatus } from '@/hooks/useApiKeyStatus'
import Link from 'next/link'

// ─── Document Types & Constants ───────────────────────────────────────────────
type DocType = 'pdf' | 'ppt' | 'word' | 'markdown'
type GenerateDocType = DocType

interface DocumentRecord {
  id: string
  title: string
  doc_type: DocType
  file_size_bytes: number
  file_path: string
  download_url: string
  agent_prompt: string
  metadata: Record<string, unknown>
  created_at: string
  version?: number
  parent?: string | null
}

interface GeneratePayload {
  doc_type: GenerateDocType
  title: string
  prompt: string
  subtitle?: string
  author?: string
}

const DOC_TYPE_CONFIG: Record<DocType, { label: string; icon: React.ElementType; colour: string; bg: string }> = {
  pdf:      { label: 'PDF Report',  icon: FileText,     colour: 'text-red-500',     bg: 'bg-red-50 dark:bg-red-900/20' },
  ppt:      { label: 'PowerPoint',  icon: Presentation, colour: 'text-amber-500',   bg: 'bg-amber-50 dark:bg-amber-900/20' },
  word:     { label: 'Word Doc',    icon: File,         colour: 'text-blue-500',    bg: 'bg-blue-50 dark:bg-blue-900/20' },
  markdown: { label: 'Markdown',    icon: FileCode2,    colour: 'text-emerald-500', bg: 'bg-emerald-50 dark:bg-emerald-900/20' },
}

const PROMPT_EXAMPLES: Record<GenerateDocType, string> = {
  pdf:      'Write a comprehensive report on the latest advancements in Large Language Models including key players, benchmark results, and future directions.',
  ppt:      'Create a 5-slide presentation on RAG (Retrieval-Augmented Generation) explaining what it is, how it works, use cases, limitations, and future outlook.',
  word:     'Generate a technical design document for a microservices architecture for an e-commerce platform with sections on services, data flow, API contracts, and deployment.',
  markdown: 'Write a developer README for a Python CLI tool that scrapes Hacker News and summarizes top stories using OpenAI.',
}

// ─── Document API helpers ─────────────────────────────────────────────────────
const fetchDocuments = async (): Promise<DocumentRecord[]> => {
  const { data } = await api.get('/documents/')
  if (Array.isArray(data?.data)) return data.data
  if (Array.isArray(data?.results)) return data.results
  if (Array.isArray(data)) return data
  return []
}

const deleteDocument = async (id: string) => api.delete(`/documents/${id}/`)

const fetchDriveStatus = async (): Promise<{ is_connected: boolean }> => {
  try { const { data } = await api.get('/integrations/drive/status/'); return data }
  catch { return { is_connected: false } }
}

const formatBytes = (bytes: number): string => {
  if (bytes === 0) return '0 B'
  const k = 1024; const sizes = ['B', 'KB', 'MB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
}


// ─── Section Editor Modal ─────────────────────────────────────────────────────
function SectionEditorModal({ doc, onClose, onSaved }: { doc: DocumentRecord; onClose: () => void; onSaved: (d: DocumentRecord) => void }) {
  const [sections, setSections] = React.useState<Array<{ heading: string; content: string }>>(
    (doc.metadata?.sections as Array<{ heading: string; content: string }>) || []
  )
  const [editingIdx, setEditingIdx] = React.useState<number | null>(null)
  const [editContent, setEditContent] = React.useState('')
  const [editHeading, setEditHeading] = React.useState('')
  const [regenInstruction, setRegenInstruction] = React.useState('')
  const [regenLoading, setRegenLoading] = React.useState(false)
  const [persistLoading, setPersistLoading] = React.useState(false)
  const [regenAllLoading, setRegenAllLoading] = React.useState(false)
  const [regenAllInstruction, setRegenAllInstruction] = React.useState('')

  const handleEdit = (idx: number) => { setEditingIdx(idx); setEditHeading(sections[idx].heading); setEditContent(sections[idx].content); setRegenInstruction('') }
  const handleSaveEdit = () => {
    if (editingIdx === null) return
    const updated = [...sections]; updated[editingIdx] = { heading: editHeading, content: editContent }
    setSections(updated); setEditingIdx(null)
  }
  const handleRegenSection = async () => {
    if (editingIdx === null) return; setRegenLoading(true)
    try {
      const { data } = await api.post(`/documents/${doc.id}/regenerate-section/`, { heading: editHeading, instruction: regenInstruction || `Write a comprehensive section about: ${editHeading}` })
      setEditContent(data.content); toast.success('Section regenerated!')
    } catch { toast.error('Regeneration failed.') } finally { setRegenLoading(false) }
  }
  const handlePersistSections = async () => {
    setPersistLoading(true)
    try { const { data } = await api.post(`/documents/${doc.id}/update-sections/`, { sections }); toast.success('Document rebuilt!'); onSaved(data); onClose() }
    catch { toast.error('Failed to save sections.') } finally { setPersistLoading(false) }
  }
  const handleRegenAll = async () => {
    setRegenAllLoading(true)
    try {
      const { data } = await api.post(`/documents/${doc.id}/regenerate-all/`, { instruction: regenAllInstruction })
      toast.success(`Regenerated! ${data.metadata?.section_count ?? 0} sections rebuilt.`)
      setSections(data.metadata?.sections ?? []); onSaved(data)
    } catch { toast.error('Regeneration failed.') } finally { setRegenAllLoading(false) }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <motion.div initial={{ opacity: 0, scale: 0.95, y: 20 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.95, y: 20 }}
        className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden">
        <div className="flex items-center justify-between p-5 border-b border-gray-200 dark:border-gray-700 bg-gradient-to-r from-indigo-600 to-violet-600">
          <div><h2 className="text-lg font-bold text-white">Section Editor</h2><p className="text-xs text-indigo-200">{doc.title} — {sections.length} sections</p></div>
          <button onClick={onClose} className="p-2 rounded-lg text-white/70 hover:text-white hover:bg-white/10 transition"><X className="w-5 h-5" /></button>
        </div>
        <div className="flex items-center gap-3 px-5 py-3 bg-gray-50 dark:bg-gray-800/50 border-b border-gray-200 dark:border-gray-700 flex-wrap">
          <input value={regenAllInstruction} onChange={e => setRegenAllInstruction(e.target.value)} placeholder="Optional instruction for full regeneration…"
            className="flex-1 px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-xs text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-violet-500 min-w-0" />
          <button onClick={handleRegenAll} disabled={regenAllLoading} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-700 text-white text-xs font-semibold transition disabled:opacity-60 whitespace-nowrap">
            {regenAllLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />} Regenerate All
          </button>
          <button onClick={handlePersistSections} disabled={persistLoading || sections.length === 0} className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold transition disabled:opacity-60 whitespace-nowrap">
            {persistLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null} Save & Rebuild
          </button>
        </div>
        <div className="flex flex-1 overflow-hidden">
          <div className="w-56 border-r border-gray-200 dark:border-gray-700 overflow-y-auto bg-gray-50 dark:bg-gray-800/50 flex-shrink-0">
            {sections.length === 0 ? <div className="p-4 text-xs text-gray-400 text-center mt-4">No sections found.</div>
              : sections.map((sec, idx) => (
                <button key={idx} onClick={() => handleEdit(idx)} className={cn("w-full text-left px-4 py-3 text-xs border-b border-gray-200 dark:border-gray-700 transition", editingIdx === idx ? "bg-indigo-50 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 font-semibold" : "text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700")}>
                  <span className="block font-bold text-indigo-600 dark:text-indigo-400 mb-0.5">{String(idx + 1).padStart(2, "0")}</span>
                  <span className="line-clamp-2">{sec.heading}</span>
                </button>
              ))}
          </div>
          <div className="flex-1 overflow-y-auto p-5 flex flex-col gap-4">
            {editingIdx === null ? (
              <div className="flex flex-col items-center justify-center h-full text-gray-400"><FileText className="w-12 h-12 mb-3 opacity-30" /><p className="text-sm">Select a section to edit</p></div>
            ) : (
              <>
                <div><label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">Section Heading</label>
                  <input value={editHeading} onChange={e => setEditHeading(e.target.value)} className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm font-semibold text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500" /></div>
                <div className="flex-1"><label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">Content</label>
                  <textarea value={editContent} onChange={e => setEditContent(e.target.value)} rows={12} className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-xs text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none font-mono leading-relaxed" /></div>
                <div className="bg-indigo-50 dark:bg-indigo-900/20 rounded-xl p-4 border border-indigo-100 dark:border-indigo-800">
                  <p className="text-xs font-semibold text-indigo-700 dark:text-indigo-300 mb-2 flex items-center gap-1.5"><Sparkles className="w-3.5 h-3.5" /> AI Regenerate</p>
                  <div className="flex gap-2">
                    <input value={regenInstruction} onChange={e => setRegenInstruction(e.target.value)} placeholder="Optional instruction…" className="flex-1 px-3 py-2 rounded-lg border border-indigo-200 dark:border-indigo-700 bg-white dark:bg-gray-800 text-xs text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                    <button onClick={handleRegenSection} disabled={regenLoading} className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold transition disabled:opacity-60">
                      {regenLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />} Regenerate
                    </button>
                  </div>
                </div>
                <button onClick={handleSaveEdit} className="w-full py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-semibold transition">Save Changes</button>
              </>
            )}
          </div>
        </div>
      </motion.div>
    </div>
  )
}

// ─── Document Card ────────────────────────────────────────────────────────────
function DocCard({ doc, onDelete, driveConnected, onEdited }: { doc: DocumentRecord; onDelete: (id: string) => void; driveConnected: boolean; onEdited: (d: DocumentRecord) => void }) {
  const cfg = DOC_TYPE_CONFIG[doc.doc_type] ?? DOC_TYPE_CONFIG.pdf
  const Icon = cfg.icon
  const [showPreview, setShowPreview] = React.useState(false)
  const [previewLoading, setPreviewLoading] = React.useState(false)
  const [renderUrl, setRenderUrl] = React.useState<string | null>(null)
  const [showSectionEditor, setShowSectionEditor] = React.useState(false)
  const [driveUploading, setDriveUploading] = React.useState(false)
  const [s3Uploading, setS3Uploading] = React.useState(false)
  const [showVersions, setShowVersions] = React.useState(false)
  const [versions, setVersions] = React.useState<DocumentRecord[]>([])
  const [driveUrl, setDriveUrl] = React.useState<string | null>(doc.metadata?.drive_url as string ?? null)

  const handleDownload = async () => {
    try {
      // Use api utility which has proper baseURL and auth headers
      const res = await api.get(`/documents/${doc.id}/download/`, { responseType: 'blob' })
      const blob = res.data
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a'); a.href = url
      const cd = res.headers['content-disposition'] || ''
      const match = cd.match(/filename="?([^"]+)"?/)
      a.download = match ? match[1] : `document.${doc.doc_type}`
      a.click(); URL.revokeObjectURL(url)
    } catch { toast.error('Download failed.') }
  }

  const handlePreview = async () => {
    if (showPreview) { setShowPreview(false); return }
    setPreviewLoading(true)
    try {
      // Use a relative URL so it goes through the proxy correctly.
      // The render endpoint accepts a ?token= param for iframe-friendly auth.
      const token = typeof window !== 'undefined'
        ? (localStorage.getItem('synapse_access_token') || localStorage.getItem('access_token') || '')
        : ''
      setRenderUrl(`/api/v1/documents/${doc.id}/render/${token ? `?token=${encodeURIComponent(token)}` : ''}`)
      setShowPreview(true)
    } catch { toast.error('Preview failed.') } finally { setPreviewLoading(false) }
  }

  const handleDriveUpload = async () => {
    setDriveUploading(true)
    try {
      const { data } = await api.post('/integrations/drive/upload/', { document_id: doc.id, folder_name: 'Synapse' })
      setDriveUrl(data.drive_url); toast.success('Uploaded to Drive!')
    } catch { toast.error('Drive upload failed.') } finally { setDriveUploading(false) }
  }

  const handleS3Upload = async () => {
    setS3Uploading(true)
    try {
      await api.post('/integrations/s3/upload/', { document_id: doc.id })
      toast.success('Uploaded to S3!')
    } catch { toast.error('S3 upload failed.') } finally { setS3Uploading(false) }
  }

  const handleShowVersions = async () => {
    if (showVersions) { setShowVersions(false); return }
    try {
      const { data } = await api.get(`/documents/${doc.id}/versions/`)
      setVersions(Array.isArray(data) ? data : data?.results ?? [])
      setShowVersions(true)
    } catch { setShowVersions(true) }
  }

  return (
    <motion.div layout initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, scale: 0.95 }}
      className="group relative bg-white dark:bg-slate-800/80 rounded-2xl border border-slate-200 dark:border-slate-700/60 p-4 flex flex-col gap-3 shadow-sm hover:shadow-lg transition-all">
      <div className="flex items-start justify-between gap-2">
        <div className={`p-2.5 rounded-xl ${cfg.bg} shrink-0`}><Icon className={`w-5 h-5 ${cfg.colour}`} /></div>
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full whitespace-nowrap ${cfg.bg} ${cfg.colour}`}>{cfg.label}</span>
      </div>
      <div>
        <h3 className="font-semibold text-slate-900 dark:text-white text-sm leading-tight line-clamp-2">{doc.title}</h3>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 line-clamp-2">{doc.agent_prompt}</p>
      </div>
      <div className="flex items-center justify-between text-xs text-slate-400 dark:text-slate-500 mt-auto">
        <span>{formatBytes(doc.file_size_bytes)}</span>
        <span>{formatDistanceToNow(new Date(doc.created_at), { addSuffix: true })}</span>
      </div>
      <div className="flex gap-2">
        <button onClick={handleDownload} className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 text-xs font-medium hover:bg-indigo-100 dark:hover:bg-indigo-900/50 transition">
          <Download className="w-3.5 h-3.5" /> Download
        </button>
        <button onClick={handlePreview} disabled={previewLoading} title="Preview" className={cn("p-1.5 rounded-lg transition", showPreview ? "text-indigo-600 bg-indigo-50 dark:bg-indigo-900/30" : "text-slate-400 hover:text-indigo-500 hover:bg-indigo-50 dark:hover:bg-indigo-900/20")}>
          {previewLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Eye className="w-4 h-4" />}
        </button>
      </div>
      <div className="flex items-center gap-1 justify-between">
        <button onClick={() => setShowSectionEditor(true)} className="flex-1 flex items-center justify-center gap-1 py-1 rounded-lg text-xs text-slate-500 hover:text-violet-600 hover:bg-violet-50 dark:hover:bg-violet-900/20 transition" title="Edit sections">
          <Archive className="w-3.5 h-3.5" /><span className="hidden sm:inline">Edit</span>
        </button>
        <button onClick={handleShowVersions} className={cn("flex-1 flex items-center justify-center gap-1 py-1 rounded-lg text-xs font-bold transition", showVersions ? "bg-violet-100 dark:bg-violet-900/30 text-violet-700" : "text-slate-500 hover:bg-violet-50 hover:text-violet-600")} title="Version history">
          <span>v{doc.version ?? 1}</span>
        </button>
        <button onClick={() => onDelete(doc.id)} className="flex-1 flex items-center justify-center gap-1 py-1 rounded-lg text-xs text-slate-500 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition" title="Delete">
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
      <div className="flex gap-2 pt-0.5 border-t border-slate-100 dark:border-slate-700/50">
        <button onClick={handleDriveUpload} disabled={!driveConnected || driveUploading} title={driveConnected ? "Upload to Google Drive" : "Connect Drive first"}
          className={cn("flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-lg text-xs font-medium transition", driveConnected ? "bg-blue-50 dark:bg-blue-900/20 text-blue-600 hover:bg-blue-100" : "bg-slate-50 dark:bg-slate-700/50 text-slate-400 cursor-not-allowed")}>
          {driveUploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <HardDrive className="w-3.5 h-3.5" />} Drive
        </button>
        <button onClick={handleS3Upload} disabled={s3Uploading} className="flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-lg bg-orange-50 dark:bg-orange-900/20 text-orange-600 text-xs font-medium hover:bg-orange-100 transition disabled:opacity-60">
          {s3Uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Cloud className="w-3.5 h-3.5" />} S3
        </button>
      </div>
      {showVersions && versions.length > 0 && (
        <div className="mt-1 pt-2 border-t border-slate-100 dark:border-slate-700 space-y-1.5">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Version History</p>
          {versions.map(v => (
            <div key={v.id} className={cn("flex items-center gap-2 p-2 rounded-lg text-xs", v.id === doc.id ? "bg-indigo-50 dark:bg-indigo-900/20 border border-indigo-200 dark:border-indigo-700" : "bg-slate-50 dark:bg-slate-800")}>
              <span className={cn("font-bold px-1.5 py-0.5 rounded text-xs", v.id === doc.id ? "bg-indigo-600 text-white" : "bg-slate-200 dark:bg-slate-600 text-slate-700 dark:text-slate-300")}>v{v.version ?? 1}</span>
              <span className="flex-1 text-slate-500 truncate">{String(v.metadata?.section_count ?? '?')} sections{v.id === doc.id && <span className="text-indigo-500 ml-1">(current)</span>}</span>
              <span className="text-slate-400">{new Date(v.created_at).toLocaleDateString()}</span>
            </div>
          ))}
        </div>
      )}
      {showPreview && renderUrl && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md" onClick={() => setShowPreview(false)}>
          <motion.div initial={{ opacity: 0, scale: 0.85 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.85 }}
            className="relative w-full max-w-5xl rounded-2xl overflow-hidden shadow-2xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-3 bg-gray-900/95 border-b border-white/10">
              <div className="flex items-center gap-3"><div className={cn("w-7 h-7 rounded-lg flex items-center justify-center", cfg.bg)}><Icon className={cn("w-3.5 h-3.5", cfg.colour)} /></div>
                <div><p className="text-sm font-semibold text-white line-clamp-1">{doc.title}</p><p className="text-xs text-gray-400">{cfg.label} Preview</p></div></div>
              <button onClick={() => setShowPreview(false)} className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition"><X className="w-4 h-4" /></button>
            </div>
            <div className="bg-gray-950" style={{ height: '75vh' }}>
              <iframe src={renderUrl} className="w-full h-full border-none" title={`Preview of ${doc.title}`} sandbox="allow-scripts allow-same-origin allow-popups allow-forms" />
            </div>
            <div className="flex items-center justify-between px-5 py-3 bg-gray-900/95 border-t border-white/10">
              <p className="text-xs text-gray-500">🖱 Scroll to read</p>
              <div className="flex gap-2">
                <button onClick={() => window.open(renderUrl, '_blank', 'noopener')} className="px-3 py-1.5 rounded-lg text-xs bg-white/10 hover:bg-white/20 text-white transition">Open Full ↗</button>
                <button onClick={handleDownload} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 text-white transition"><Download className="w-3.5 h-3.5" /> Download</button>
              </div>
            </div>
          </motion.div>
        </div>
      )}
      <AnimatePresence>
        {showSectionEditor && <SectionEditorModal doc={doc} onClose={() => setShowSectionEditor(false)} onSaved={onEdited} />}
      </AnimatePresence>
    </motion.div>
  )
}

// ─── Document Generate Panel ──────────────────────────────────────────────────
function DocGeneratePanel({ onGenerated }: { onGenerated: () => void }) {
  const [docType, setDocType] = React.useState<GenerateDocType>('pdf')
  const [title, setTitle] = React.useState('')
  const [prompt, setPrompt] = React.useState('')
  const [generating, setGenerating] = React.useState(false)

  const handleGenerate = async () => {
    if (!title.trim() || !prompt.trim()) { toast.error('Please fill in title and prompt.'); return }
    setGenerating(true)
    try {
      await api.post('/documents/generate/', { doc_type: docType, title: title.trim(), prompt: prompt.trim() })
      toast.success('Document queued! It will appear in Files when ready.')
      setTitle(''); setPrompt('')
      setTimeout(onGenerated, 2000)
    } catch (err: unknown) {
      const errData = (err as { response?: { data?: { error?: string | { message?: string } } } })?.response?.data?.error
      const msg = typeof errData === 'string' 
        ? errData 
        : (errData as { message?: string })?.message ?? 'Generation failed.'
      toast.error(msg)
    } finally { setGenerating(false) }
  }

  return (
    <div className="rounded-2xl bg-white dark:bg-[#0c0e17] border border-orange-200 dark:border-orange-500/20 shadow-lg mb-6 overflow-hidden">
      <div className="absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r from-orange-500 via-amber-500 to-yellow-500" style={{ position: 'relative' }} />
      <div className="p-5">
        <div className="flex items-center gap-2.5 mb-5">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-orange-500 to-amber-600 flex items-center justify-center shadow-lg shrink-0">
            <FileText size={14} className="text-white" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-800 dark:text-white">Generate Document</h2>
            <p className="text-[10px] text-slate-500 dark:text-slate-400">AI-powered PDF, PPT, Word & Markdown generation</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5 mb-4">
          {(Object.keys(DOC_TYPE_CONFIG) as DocType[]).map(dt => {
            const cfg = DOC_TYPE_CONFIG[dt]
            const Icon = cfg.icon
            const active = docType === dt
            return (
              <button key={dt} onClick={() => { setDocType(dt); setPrompt(PROMPT_EXAMPLES[dt]) }}
                className={cn('flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all border',
                  active ? 'bg-orange-50 dark:bg-orange-500/20 border-orange-300 dark:border-orange-400/60 text-orange-700 dark:text-orange-200 shadow-sm'
                    : 'bg-slate-50 dark:bg-white/5 border-slate-200 dark:border-white/10 text-slate-600 dark:text-slate-400 hover:border-orange-300 hover:text-orange-600')}>
                <Icon size={12} />{cfg.label}
              </button>
            )
          })}
        </div>
        <input value={title} onChange={e => setTitle(e.target.value)} placeholder="Document title…"
          className="w-full mb-3 px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/50 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-orange-400" />
        <textarea value={prompt} onChange={e => setPrompt(e.target.value)} placeholder="Describe what you want to generate…" rows={4}
          className="w-full mb-3 px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/50 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-orange-400 resize-none" />
        <button onClick={handleGenerate} disabled={generating || !title.trim() || !prompt.trim()}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-600 hover:to-amber-600 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-bold transition-all shadow-md">
          {generating ? <><Loader2 size={15} className="animate-spin" /> Generating…</> : <><Sparkles size={15} /> Generate {DOC_TYPE_CONFIG[docType].label}</>}
        </button>
      </div>
    </div>
  )
}

// ─── constants ───────────────────────────────────────────────────────────────

const TASK_TYPES: { value: AgentTaskType; label: string; icon: React.ElementType; description: string; locked?: boolean; lockReason?: string }[] = [
  { value: 'general',  label: 'General',  icon: Sparkles,   description: 'Open-ended reasoning and Q&A' },
  { value: 'research', label: 'Research', icon: Search,     description: 'Deep research using knowledge base' },
  { value: 'trends',   label: 'Trends',   icon: TrendingUp, description: 'Analyze technology trends' },
  { value: 'github',   label: 'GitHub',   icon: GitBranch,  description: 'Search GitHub repositories' },
  { value: 'arxiv',    label: 'arXiv',    icon: BookOpen,   description: 'Fetch and analyze research papers' },
  { value: 'tweets',   label: 'X/Twitter', icon: ExternalLink, description: 'Analyze tweets & X/Twitter trends' },
  { value: 'document', label: 'Document', icon: FileText,   description: 'Generate PDF / PPT / Word docs' },
]

const COMMAND_TEMPLATES = [
  { label: 'Research AI trends',       prompt: 'Research the latest trends in large language models and summarize key findings.', type: 'research' as AgentTaskType },
  { label: 'Analyze React repos',      prompt: 'Search GitHub for trending React repositories and provide an analysis.', type: 'github' as AgentTaskType },
  { label: 'Fetch ML papers',          prompt: 'Fetch the latest machine learning papers from arXiv and summarize them.', type: 'arxiv' as AgentTaskType },
  { label: 'Summarise paper findings', prompt: 'Fetch recent cs.AI papers from arXiv and summarise the key findings and implications of each paper.', type: 'arxiv' as AgentTaskType },
  { label: 'Compare paper methods',    prompt: 'Fetch recent cs.LG papers from arXiv and compare and contrast the methodologies used across the papers.', type: 'arxiv' as AgentTaskType },
  { label: 'Open research problems',   prompt: 'Fetch recent cs.CL papers from arXiv and identify the open problems and future research directions mentioned.', type: 'arxiv' as AgentTaskType },
  { label: 'Datasets & benchmarks',    prompt: 'Fetch recent cs.AI papers from arXiv and list the datasets and benchmarks commonly used in this research area.', type: 'arxiv' as AgentTaskType },
  { label: 'Tech trend report',        prompt: 'Analyze current technology trends in AI and cloud computing.', type: 'trends' as AgentTaskType },
  { label: 'X/Twitter AI buzz',        prompt: 'Analyze the latest tweets and discussions about AI, LLMs and machine learning. Identify key themes, top voices, and emerging trends from X/Twitter.', type: 'tweets' as AgentTaskType },
  { label: 'Top tech tweets today',    prompt: 'Find and summarize the most impactful tech tweets from today. Focus on AI, programming, and open source topics.', type: 'tweets' as AgentTaskType },
  { label: 'PDF: AI State of the Art',  prompt: 'Generate a comprehensive PDF report on the current state of generative AI with key trends, breakthroughs, and future outlook.', type: 'document' as AgentTaskType },
  { label: 'PPT: RAG Explainer',        prompt: 'Create a 6-slide PowerPoint presentation explaining Retrieval-Augmented Generation (RAG): what it is, how it works, use cases, limitations, and future directions.', type: 'document' as AgentTaskType },
  { label: 'Markdown: API README',      prompt: 'Write a developer README in Markdown for a REST API service, including setup instructions, authentication, endpoints, and examples.', type: 'document' as AgentTaskType },
]

// Research synthesis quick-prompts (shown when arxiv task type is selected)
const RESEARCH_SYNTHESIS_PROMPTS = [
  { label: '📋 Key findings',     prompt: 'Fetch the latest cs.AI papers from arXiv and summarise the key findings and implications of each paper.' },
  { label: '🔬 Methodologies',    prompt: 'Fetch recent cs.LG papers from arXiv and analyse what are the main methodologies used across these papers.' },
  { label: '🔮 Open problems',    prompt: 'Fetch recent cs.CL papers from arXiv and identify what open problems or future research directions are identified.' },
  { label: '⚖️ Compare methods',  prompt: 'Fetch recent cs.AI papers from arXiv and compare and contrast the approaches taken by the papers.' },
  { label: '📊 Datasets used',    prompt: 'Fetch recent cs.AI papers from arXiv and list what datasets and benchmarks are commonly used in this area.' },
]

const STATUS_CONFIG = {
  pending:    { color: 'text-amber-700 dark:text-amber-400',  bg: 'bg-amber-100 dark:bg-amber-400/10',  border: 'border-amber-300 dark:border-amber-400/30',  icon: Clock,     label: 'Pending' },
  processing: { color: 'text-blue-700 dark:text-blue-400',   bg: 'bg-blue-100 dark:bg-blue-400/10',   border: 'border-blue-300 dark:border-blue-400/30',   icon: Loader2,   label: 'Running' },
  completed:  { color: 'text-emerald-700 dark:text-emerald-400',bg: 'bg-emerald-100 dark:bg-emerald-400/10',border: 'border-emerald-300 dark:border-emerald-400/30',icon: CheckCircle,label: 'Completed' },
  failed:     { color: 'text-red-700 dark:text-red-400',    bg: 'bg-red-100 dark:bg-red-400/10',    border: 'border-red-300 dark:border-red-400/30',    icon: XCircle,   label: 'Failed' },
}

// ─── helpers ─────────────────────────────────────────────────────────────────

function formatCost(cost: string | number): string {
  const n = typeof cost === 'string' ? parseFloat(cost) : cost
  if (isNaN(n) || n === 0) return '$0.00'
  if (n < 0.001) return `$${n.toFixed(6)}`
  return `$${n.toFixed(4)}`
}

function formatDuration(seconds: number | null | undefined): string {
  if (!seconds) return '—'
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  return `${Math.floor(seconds / 60)}m ${(seconds % 60).toFixed(0)}s`
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

function fileExtIcon(name: string): React.ElementType {
  const ext = name.split('.').pop()?.toLowerCase() ?? ''
  if (['pdf'].includes(ext)) return FileType
  if (['pptx', 'ppt'].includes(ext)) return Presentation
  if (['docx', 'doc'].includes(ext)) return FileText
  if (['zip', 'tar', 'gz'].includes(ext)) return Archive
  if (['json', 'yaml', 'yml', 'toml'].includes(ext)) return FileJson
  if (['ts', 'tsx', 'js', 'jsx', 'py', 'go', 'rs', 'java', 'cs', 'cpp', 'c', 'rb', 'sh'].includes(ext)) return FileCode
  return FileText
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const handle = async () => {
    try { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1800) } catch {}
  }
  return (
    <button onClick={handle} title="Copy" className="p-1.5 rounded text-slate-500 hover:text-slate-700 dark:hover:text-slate-200 transition-colors">
      {copied ? <Check size={13} className="text-emerald-600 dark:text-emerald-400" /> : <Copy size={13} />}
    </button>
  )
}

// ─── sub-components ──────────────────────────────────────────────────────────

/** Full-featured markdown renderer — same pipeline as ChatMessage */
function AgentMarkdown({ content }: { content: string }) {
  const [copiedBlock, setCopiedBlock] = useState<number | null>(null)
  return (
    <div className="prose prose-sm prose-slate dark:prose-invert max-w-none">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          code({ className, children, ...props }: any) {
            const language = (className ?? '').replace('language-', '').trim()
            const raw = String(children).replace(/\n$/, '')
            const isBlock = Boolean(className?.startsWith('language-'))
            if (!isBlock) {
              return (
                <code className="bg-slate-100 dark:bg-slate-900 text-indigo-700 dark:text-indigo-300 rounded px-1.5 py-0.5 text-xs font-mono" {...props}>
                  {children}
                </code>
              )
            }
            return (
              <div className="my-3 rounded-xl overflow-hidden border border-slate-200 dark:border-slate-700 bg-slate-100 dark:bg-slate-900">
                <div className="flex items-center justify-between px-4 py-2 bg-slate-200 dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700">
                  <span className="text-xs font-mono text-slate-400">{language || 'code'}</span>
                  <button
                    onClick={async () => {
                      await navigator.clipboard.writeText(raw)
                      setCopiedBlock(Date.now())
                      setTimeout(() => setCopiedBlock(null), 1800)
                    }}
                    className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
                  >
                    {copiedBlock ? <Check size={12} className="text-emerald-600 dark:text-emerald-400" /> : <Copy size={12} />}
                    {copiedBlock ? 'Copied!' : 'Copy'}
                  </button>
                </div>
                <pre className="overflow-x-auto p-4 text-sm text-slate-700 dark:text-slate-200 font-mono leading-relaxed m-0">
                  <code>{raw}</code>
                </pre>
              </div>
            )
          },
          pre({ children }: any) { return <>{children}</> },
          h1: ({ children }: any) => <h1 className="text-xl font-bold text-slate-800 dark:text-white mt-5 mb-2 pb-1 border-b border-slate-200 dark:border-slate-700">{children}</h1>,
          h2: ({ children }: any) => <h2 className="text-lg font-semibold text-slate-800 dark:text-white mt-4 mb-2 flex items-center gap-2">{children}</h2>,
          h3: ({ children }: any) => <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100 mt-3 mb-1">{children}</h3>,
          h4: ({ children }: any) => <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mt-2 mb-1">{children}</h4>,
          p: ({ children }: any) => <p className="mb-3 last:mb-0 leading-relaxed text-slate-700 dark:text-slate-200">{children}</p>,
          ul: ({ children }: any) => <ul className="list-disc pl-5 mb-3 space-y-1 text-slate-700 dark:text-slate-200">{children}</ul>,
          ol: ({ children }: any) => <ol className="list-decimal pl-5 mb-3 space-y-1 text-slate-700 dark:text-slate-200">{children}</ol>,
          li: ({ children }: any) => <li className="leading-relaxed">{children}</li>,
          strong: ({ children }: any) => <strong className="font-semibold text-slate-800 dark:text-white">{children}</strong>,
          em: ({ children }: any) => <em className="italic text-slate-600 dark:text-slate-300">{children}</em>,
          blockquote: ({ children }: any) => (
            <blockquote className="border-l-4 border-indigo-500 bg-slate-100 dark:bg-slate-900/50 pl-4 pr-2 py-2 my-3 rounded-r-lg text-slate-600 dark:text-slate-400 italic">
              {children}
            </blockquote>
          ),
          a: ({ href, children }: any) => (
            <a href={href} target="_blank" rel="noopener noreferrer"
              className="text-indigo-600 dark:text-indigo-400 hover:text-indigo-500 dark:hover:text-indigo-300 underline underline-offset-2 transition-colors inline-flex items-center gap-1">
              {children}<ExternalLink size={11} className="opacity-60" />
            </a>
          ),
          hr: () => <hr className="border-slate-300 dark:border-slate-700 my-4" />,
          table: ({ children }: any) => (
            <div className="my-4 rounded-lg border border-slate-300 dark:border-slate-700 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm border-collapse">{children}</table>
              </div>
            </div>
          ),
          thead: ({ children }: any) => <thead className="bg-slate-200 dark:bg-slate-800">{children}</thead>,
          tbody: ({ children }: any) => <tbody className="divide-y divide-slate-200 dark:divide-slate-700">{children}</tbody>,
          tr: ({ children }: any) => <tr className="even:bg-slate-100 dark:even:bg-slate-800/40 hover:bg-slate-200 dark:hover:bg-slate-700/40 transition-colors">{children}</tr>,
          th: ({ children }: any) => <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-600 dark:text-slate-300 uppercase tracking-wider">{children}</th>,
          td: ({ children }: any) => <td className="px-4 py-2.5 text-slate-700 dark:text-slate-300">{children}</td>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}

// ── Tool-specific output renderers (TASK-303-F1) ─────────────────────────────

/** Render web_search results as a list of links with snippets */
function WebSearchOutput({ output }: { output: unknown }) {
  let results: Array<{ title?: string; url?: string; snippet?: string; score?: number }> = []
  try {
    results = typeof output === 'string' ? JSON.parse(output) : (output as typeof results)
  } catch { return <RawOutput output={output} /> }
  if (!Array.isArray(results) || results[0]?.hasOwnProperty('error')) return <RawOutput output={output} />
  return (
    <div className="space-y-2">
      {results.map((r, i) => (
        <div key={i} className="rounded-lg bg-slate-100 dark:bg-slate-800 p-2 border border-slate-200 dark:border-slate-700">
          <a href={r.url} target="_blank" rel="noopener noreferrer"
             className="text-indigo-600 dark:text-indigo-400 font-medium text-xs hover:underline truncate block">
            {r.title || r.url}
          </a>
          {r.url && <p className="text-[10px] text-slate-400 truncate">{r.url}</p>}
          {r.snippet && <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 line-clamp-2">{r.snippet}</p>}
        </div>
      ))}
    </div>
  )
}

/** Render run_python_code with stdout + error */
function PythonOutput({ output }: { output: unknown }) {
  let result: { success?: boolean; stdout?: string; stderr?: string } = {}
  try {
    result = typeof output === 'string' ? JSON.parse(output) : (output as typeof result)
  } catch { return <RawOutput output={output} /> }
  return (
    <div className="space-y-2">
      {result.stdout && (
        <div>
          <span className="text-[10px] text-green-500 font-semibold uppercase tracking-wider">stdout</span>
          <pre className="mt-1 text-xs font-mono text-green-400 bg-slate-950 rounded-lg p-2 border border-slate-700 max-h-36 overflow-y-auto whitespace-pre-wrap">
            {result.stdout}
          </pre>
        </div>
      )}
      {result.stderr && (
        <div>
          <span className="text-[10px] text-red-400 font-semibold uppercase tracking-wider">stderr</span>
          <pre className="mt-1 text-xs font-mono text-red-400 bg-slate-950 rounded-lg p-2 border border-red-900/30 max-h-24 overflow-y-auto whitespace-pre-wrap">
            {result.stderr}
          </pre>
        </div>
      )}
    </div>
  )
}

/** Render generate_chart as an inline image */
function ChartOutput({ output }: { output: unknown }) {
  let result: { data_uri?: string; title?: string; chart_type?: string; error?: string } = {}
  try {
    result = typeof output === 'string' ? JSON.parse(output) : (output as typeof result)
  } catch { return <RawOutput output={output} /> }
  if (result.error) return <RawOutput output={output} />
  if (!result.data_uri) return <RawOutput output={output} />
  return (
    <div className="space-y-2">
      {result.title && (
        <p className="text-xs text-slate-500 dark:text-slate-400">
          {result.chart_type} chart: <span className="font-medium text-slate-700 dark:text-slate-300">{result.title}</span>
        </p>
      )}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={result.data_uri} alt={result.title || 'chart'} className="rounded-lg w-full border border-slate-700 max-h-64 object-contain" />
    </div>
  )
}

/** Render read_document output with metadata */
function DocumentOutput({ output }: { output: unknown }) {
  let result: { url?: string; doc_type?: string; page_count?: number; char_count?: number; truncated?: boolean; text?: string; error?: string } = {}
  try {
    result = typeof output === 'string' ? JSON.parse(output) : (output as typeof result)
  } catch { return <RawOutput output={output} /> }
  if (result.error) return <RawOutput output={output} />
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 flex-wrap text-[10px] text-slate-400">
        {result.doc_type && <span className="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 uppercase font-mono">{result.doc_type}</span>}
        {result.page_count && <span>{result.page_count} pages</span>}
        {result.char_count && <span>{result.char_count.toLocaleString()} chars</span>}
        {result.truncated && <span className="text-amber-400">⚠ truncated</span>}
      </div>
      {result.text && (
        <pre className="text-xs text-slate-400 dark:text-slate-500 bg-slate-100 dark:bg-slate-900/70 rounded-lg p-2 border border-slate-200 dark:border-slate-700 max-h-36 overflow-y-auto whitespace-pre-wrap">
          {result.text.slice(0, 800)}{(result.text.length ?? 0) > 800 ? '\n…' : ''}
        </pre>
      )}
    </div>
  )
}

/** Fallback: raw pre output */
function RawOutput({ output }: { output: unknown }) {
  return (
    <pre className="text-slate-600 dark:text-slate-300 font-mono whitespace-pre-wrap break-words bg-slate-100 dark:bg-slate-800 rounded-lg p-2 border border-slate-200 dark:border-slate-700 max-h-40 overflow-y-auto text-xs">
      {String(output).slice(0, 600)}{String(output).length > 600 ? '\n…(truncated)' : ''}
    </pre>
  )
}

/** Route tool output to the correct rich renderer */
function ToolOutput({ toolName, output }: { toolName: string; output: unknown }) {
  if (toolName === 'web_search')      return <WebSearchOutput output={output} />
  if (toolName === 'run_python_code') return <PythonOutput output={output} />
  if (toolName === 'generate_chart')  return <ChartOutput output={output} />
  if (toolName === 'read_document')   return <DocumentOutput output={output} />
  return <RawOutput output={output} />
}

const TOOL_ICONS: Record<string, string> = {
  web_search:            '🌐',
  run_python_code:       '🐍',
  generate_chart:        '📊',
  read_document:         '📄',
  search_knowledge_base: '🔍',
  fetch_articles:        '📰',
  analyze_trends:        '📈',
  search_github:         '💻',
  fetch_arxiv_papers:    '🔬',
  generate_pdf:          '📋',
  generate_ppt:          '🖥️',
  create_project:        '🏗️',
}

/** Tool-call trace accordion — TASK-303-F1 enhanced */
function StepTrace({ steps }: { steps: AgentIntermediateStep[] }) {
  const [open, setOpen] = useState(false)
  if (!steps?.length) return null
  return (
    <div className="mt-4">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-colors group"
      >
        <div className="p-0.5 rounded bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 group-hover:border-indigo-500/50 transition-colors">
          {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </div>
        <Cpu size={11} className="text-indigo-600 dark:text-indigo-400" />
        <span>Reasoning trace · {steps.length} tool call{steps.length !== 1 ? 's' : ''}</span>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="mt-3 space-y-2">
              {steps.map((step, i) => {
                const emoji = TOOL_ICONS[step.tool] ?? '🔧'
                return (
                  <div key={i} className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden">
                    {/* Header */}
                    <div className="flex items-center gap-2 px-3 py-2 bg-slate-100 dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700">
                      <div className="w-5 h-5 rounded-full bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center flex-shrink-0">
                        <span className="text-[9px] font-bold text-indigo-600 dark:text-indigo-400">{i + 1}</span>
                      </div>
                      <span className="text-sm">{emoji}</span>
                      <span className="font-mono text-xs text-indigo-600 dark:text-indigo-300 font-semibold">{step.tool}</span>
                    </div>
                    {/* Body */}
                    <div className="p-3 space-y-2 text-xs">
                      {/* Input */}
                      <div>
                        <span className="text-slate-500 uppercase tracking-wider text-[10px] font-semibold">Input</span>
                        {/* Render code input with syntax hint for Python tool */}
                        {step.tool === 'run_python_code' ? (
                          <pre className="mt-1 text-xs font-mono text-emerald-400 bg-slate-950 rounded-lg p-2 border border-slate-700 max-h-36 overflow-y-auto whitespace-pre-wrap">
                            {typeof step.input === 'string' ? step.input : (step.input as { code?: string })?.code ?? JSON.stringify(step.input, null, 2)}
                          </pre>
                        ) : (
                          <pre className="mt-1 text-slate-600 dark:text-slate-300 font-mono whitespace-pre-wrap break-words bg-slate-100 dark:bg-slate-800 rounded-lg p-2 border border-slate-200 dark:border-slate-700 text-xs">
                            {typeof step.input === 'string' ? step.input : JSON.stringify(step.input, null, 2)}
                          </pre>
                        )}
                      </div>
                      {/* Output — routed to rich renderer */}
                      <div>
                        <span className="text-slate-500 uppercase tracking-wider text-[10px] font-semibold">Output</span>
                        <div className="mt-1">
                          <ToolOutput toolName={step.tool} output={step.output} />
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

/** Collapsible file list for project scaffolds */
function FileListAccordion({ files }: { files: string[] }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen(o => !o)}
        className="text-xs text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 flex items-center gap-1 transition-colors"
      >
        <FolderOpen size={11} />
        {open ? 'Hide' : 'View'} {files.length} included files
      </button>
      {open && (
        <div className="mt-2 bg-slate-50 dark:bg-slate-900/70 rounded-lg p-2 border border-slate-200 dark:border-slate-700 max-h-36 overflow-y-auto">
          {files.map((f, i) => {
            const FI = fileExtIcon(f) as React.ComponentType<{ size?: number; className?: string }>
            return (
              <div key={i} className="flex items-center gap-1.5 py-0.5 text-xs text-slate-400 font-mono">
                <FI size={11} className="text-slate-500 flex-shrink-0" />
                {f}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

/** Rich download card for Document & Project results */
function DownloadResultCard({ task }: { task: AgentTask }) {
  const result = task.result ?? {}
  const downloadUrl = result.download_url as string | undefined
  const fileName = result.file_name as string | undefined
  const filePath = result.file_path as string | undefined
  const fileSize = result.file_size_bytes as number | undefined
  const isProject = task.task_type === 'project'
  const isDoc = task.task_type === 'document'
  if (!downloadUrl && !filePath) return null

  const displayName = fileName ?? (filePath ? filePath.split('/').pop() : 'Generated file') ?? 'file'
  const FileIcon = fileExtIcon(displayName) as React.ComponentType<{ size?: number }>
  const ext = displayName.split('.').pop()?.toUpperCase() ?? 'FILE'
  const sizeStr = fileSize
    ? fileSize > 1024 * 1024 ? `${(fileSize / (1024 * 1024)).toFixed(1)} MB`
    : fileSize > 1024 ? `${(fileSize / 1024).toFixed(1)} KB`
    : `${fileSize} B`
    : null

  const accentClass = isProject
    ? 'from-emerald-600/20 to-cyan-600/10 border-emerald-500/30'
    : 'from-indigo-600/20 to-violet-600/10 border-indigo-500/30'
  const iconClass = isProject ? 'text-emerald-600 dark:text-emerald-400 bg-emerald-500/10' : 'text-indigo-600 dark:text-indigo-400 bg-indigo-500/10'
  const btnClass = isProject
    ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
    : 'bg-indigo-600 hover:bg-indigo-500 text-white'

  return (
    <div className={`mt-4 rounded-xl border bg-gradient-to-br ${accentClass} p-4`}>
      <div className="flex items-start gap-4">
        <div className={`p-3 rounded-xl ${iconClass} flex-shrink-0`}>
          {isProject ? <Package size={22} /> : <FileIcon size={22} />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <span className="text-xs font-bold uppercase tracking-widest text-slate-400">
              {isProject ? 'Project Scaffold' : 'Generated Document'}
            </span>
            <span className="text-xs px-1.5 py-0.5 rounded bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300 font-mono font-bold">{ext}</span>
          </div>
          <p className="text-sm font-semibold text-slate-800 dark:text-white truncate">{displayName}</p>
          {sizeStr && (
            <p className="text-xs text-slate-400 mt-0.5 flex items-center gap-1">
              <Archive size={11} />
              {sizeStr}
            </p>
          )}
          {isProject && Array.isArray(result.file_list) && (result.file_list as string[]).length > 0 && (
            <FileListAccordion files={result.file_list as string[]} />
          )}
        </div>
        {downloadUrl && (
          <a
            href={downloadUrl}
            target="_blank"
            rel="noreferrer"
            className={`flex-shrink-0 flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all shadow-lg ${btnClass}`}
          >
            <Download size={15} />
            Download
          </a>
        )}
      </div>
    </div>
  )
}

function TaskCard({
  task,
  onCancel,
  onRefresh,
}: {
  task: AgentTask
  onCancel: (id: string) => void
  onRefresh: (id: string) => void
}) {
  const [expanded, setExpanded] = useState(task.status === 'processing' || task.status === 'pending')
  const cfg = STATUS_CONFIG[task.status]
  const StatusIcon = cfg.icon
  const TypeInfo = TASK_TYPES.find(t => t.value === task.task_type)
  const TypeIcon = TypeInfo?.icon ?? Bot
  const isActive = task.status === 'pending' || task.status === 'processing'
  const answer = task.answer ?? (task.result?.answer as string | undefined)
  const steps = task.intermediate_steps ?? (task.result?.intermediate_steps as AgentIntermediateStep[] | undefined) ?? []
  const hasDownload = !!(task.result?.download_url || task.result?.file_path)

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8, scale: 0.98 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
      className={`rounded-2xl border bg-white dark:bg-slate-900/80 backdrop-blur-sm overflow-hidden shadow-card dark:shadow-lg border-slate-200 dark:${cfg.border}`}
    >
      {/* Status accent bar */}
      <div className={`h-0.5 w-full ${
        task.status === 'processing' ? 'bg-gradient-to-r from-blue-500 via-indigo-500 to-blue-500 animate-pulse' :
        task.status === 'completed'  ? 'bg-gradient-to-r from-emerald-500 to-cyan-500' :
        task.status === 'failed'     ? 'bg-gradient-to-r from-red-500 to-rose-500' :
        'bg-gradient-to-r from-amber-500 to-orange-500'
      }`} />

      {/* Header */}
      <div
        className="flex items-start gap-3 p-4 cursor-pointer select-none"
        onClick={() => setExpanded(e => !e)}
      >
        <div className={`mt-0.5 p-2 rounded-xl ${cfg.bg} ${cfg.color} border ${cfg.border} flex-shrink-0`}>
          <TypeIcon size={15} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className={`inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-0.5 rounded-full ${cfg.bg} ${cfg.color} border ${cfg.border}`}>
              <StatusIcon size={10} className={task.status === 'processing' ? 'animate-spin' : ''} />
              {cfg.label}
            </span>
            <span className="text-xs font-medium text-slate-500 dark:text-slate-500 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded-full border border-slate-200 dark:border-slate-700">
              {TypeInfo?.label ?? task.task_type}
            </span>
            <span className="text-xs text-slate-500 dark:text-slate-600">{timeAgo(task.created_at)}</span>
            {hasDownload && task.status === 'completed' && (
              <span className="inline-flex items-center gap-1 text-xs text-emerald-400 bg-emerald-400/10 border border-emerald-400/20 px-2 py-0.5 rounded-full">
                <Download size={9} />
                Ready
              </span>
            )}
          </div>
          <p className="text-sm text-slate-700 dark:text-slate-200 font-medium leading-snug line-clamp-2">{task.prompt}</p>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0 mt-0.5">
          {isActive && (
            <button
              onClick={e => { e.stopPropagation(); onCancel(task.id) }}
              className="p-1.5 rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-400/10 transition-colors"
              title="Cancel task"
            >
              <X size={14} />
            </button>
          )}
          {!isActive && (
            <button
              onClick={e => { e.stopPropagation(); onRefresh(task.id) }}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
              title="Refresh"
            >
              <RefreshCw size={13} />
            </button>
          )}
          {answer && <CopyButton text={answer} />}
          <div className={`p-1 rounded transition-colors ${expanded ? 'text-slate-600 dark:text-slate-300' : 'text-slate-600'}`}>
            {expanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
          </div>
        </div>
      </div>

      {/* Metrics strip */}
      <div className="flex items-center gap-4 px-4 pb-3 text-xs border-b border-slate-200 dark:border-slate-800">
        <span className="flex items-center gap-1 text-slate-500 dark:text-slate-500">
          <Zap size={10} className="text-amber-500" />
          {(task.tokens_used || 0).toLocaleString()} tokens
        </span>
        <span className="flex items-center gap-1 text-slate-500 dark:text-slate-500">
          <DollarSign size={10} className="text-emerald-500" />
          {formatCost(task.cost_usd)}
        </span>
        {task.execution_time_s != null && (
          <span className="flex items-center gap-1 text-slate-500 dark:text-slate-500">
            <Timer size={10} className="text-blue-500 dark:text-blue-400" />
            {formatDuration(task.execution_time_s)}
          </span>
        )}
        {steps.length > 0 && (
          <span className="flex items-center gap-1 text-slate-500 dark:text-slate-500">
            <Cpu size={10} className="text-indigo-500 dark:text-indigo-400" />
            {steps.length} tool{steps.length !== 1 ? 's' : ''} used
          </span>
        )}
      </div>

      {/* Expanded body */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-5 pt-4 space-y-4">

              {/* Processing state */}
              {task.status === 'processing' && (
                <div className="flex items-center gap-3 text-blue-400 text-sm bg-blue-400/5 border border-blue-400/20 rounded-xl px-4 py-3">
                  <Loader2 size={15} className="animate-spin flex-shrink-0" />
                  <div>
                    <p className="font-medium">Agent is working…</p>
                    <p className="text-xs text-blue-400/70 mt-0.5">Streaming results in real-time via SSE</p>
                  </div>
                </div>
              )}

              {/* Pending state */}
              {task.status === 'pending' && (
                <div className="flex items-center gap-3 text-amber-400 text-sm bg-amber-400/5 border border-amber-400/20 rounded-xl px-4 py-3">
                  <Clock size={15} className="flex-shrink-0 animate-pulse" />
                  <p className="font-medium">Queued — waiting for agent worker</p>
                </div>
              )}

              {/* Error state */}
              {task.status === 'failed' && task.error_message && (
                <div className="flex items-start gap-3 text-red-400 text-sm bg-red-400/5 border border-red-400/20 rounded-xl px-4 py-3">
                  <AlertCircle size={15} className="flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-medium mb-0.5">Task failed</p>
                    <p className="text-xs text-red-400/80">
                      {typeof task.error_message === 'string' 
                        ? task.error_message 
                        : (task.error_message as { message?: string })?.message ?? 'Unknown error'}
                    </p>
                  </div>
                </div>
              )}

              {/* Answer — rendered as beautiful markdown */}
              {answer && (
                <div className="bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-200 dark:border-slate-700/60 px-5 py-4 prose-headings:text-slate-800 dark:prose-headings:text-white prose-p:text-slate-700 dark:prose-p:text-slate-300">
                  <AgentMarkdown content={answer} />
                </div>
              )}

              {/* Premium download card for document/project tasks */}
              {hasDownload && <DownloadResultCard task={task} />}

              {/* Tool trace accordion */}
              {steps.length > 0 && <StepTrace steps={steps} />}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

// ─── main page ───────────────────────────────────────────────────────────────

export default function AgentsPage() {
  const { status: apiKeyStatus } = useApiKeyStatus()
  const [prompt, setPrompt]           = useState('')
  const [taskType, setTaskType]       = useState<AgentTaskType>('general')
  const [submitting, setSubmitting]   = useState(false)
  const [tasks, setTasks]             = useState<AgentTask[]>([])
  const [tools, setTools]             = useState<AgentTool[]>([])
  const [loadingTasks, setLoadingTasks] = useState(true)
  const [activeTab, setActiveTab]     = useState<'active' | 'history' | 'files'>('active')
  const [documents, setDocuments]     = useState<DocumentRecord[]>([])
  const [driveConnected, setDriveConnected] = useState(false)
  const [loadingDocs, setLoadingDocs] = useState(false)
  const [docSubType, setDocSubType]   = useState<DocType>('pdf')
  const [docTitle, setDocTitle]       = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const sseRefs = useRef<Map<string, EventSource>>(new Map())

  // ── fetch task list ────────────────────────────────────────────────────────
  const fetchTasks = useCallback(async () => {
    try {
      const res = await api.get('/agents/tasks/?ordering=-created_at')
      // StandardPagination returns {success, data, meta}
      // Fall back through common shapes to always get an array
      const payload = res.data
      const items: AgentTask[] =
        Array.isArray(payload)            ? payload            :
        Array.isArray(payload?.data)      ? payload.data       :
        Array.isArray(payload?.results)   ? payload.results    :
        []
      setTasks(items)
    } catch {
      // silently fail on background refreshes
    } finally {
      setLoadingTasks(false)
    }
  }, [])

  // ── fetch tool list ────────────────────────────────────────────────────────
  const fetchTools = useCallback(async () => {
    try {
      const res = await api.get('/agents/tools/')
      setTools(res.data.tools ?? [])
    } catch {
      // tools are non-critical
    }
  }, [])

  const loadDocuments = useCallback(async () => {
    setLoadingDocs(true)
    try {
      const docs = await fetchDocuments()
      setDocuments(docs)
      const ds = await fetchDriveStatus()
      setDriveConnected(ds.is_connected)
    } catch { /* silent */ } finally { setLoadingDocs(false) }
  }, [])

  useEffect(() => {
    fetchTasks()
    fetchTools()
    loadDocuments()
  }, [fetchTasks, fetchTools, loadDocuments])

  // ── SSE subscription for a single task ────────────────────────────────────
  const subscribeSSE = useCallback((taskId: string) => {
    if (sseRefs.current.has(taskId)) return   // already subscribed
    const token =
      localStorage.getItem('synapse_access_token') ||
      localStorage.getItem('access_token') ||
      (() => {
        try {
          const s = JSON.parse(localStorage.getItem('synapse-auth') || '{}')
          return s?.state?.accessToken ?? s?.state?.access ?? ''
        } catch { return '' }
      })()

    const baseUrl = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1').replace(/\/+$/, '')
    // Always ensure the base URL ends with /api/v1 (not just the origin)
    const apiBase = baseUrl.endsWith('/api/v1') ? baseUrl : `${baseUrl}/api/v1`
    const url = `${apiBase}/agents/tasks/${taskId}/stream/?token=${encodeURIComponent(token)}`
    const es = new EventSource(url)

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        setTasks(prev => prev.map(t =>
          t.id === taskId
            ? {
                ...t,
                status:           data.status,
                answer:           data.answer,
                tokens_used:      data.tokens_used,
                cost_usd:         data.cost_usd,
                execution_time_s: data.execution_time_s,
                intermediate_steps: data.intermediate_steps,
                error_message:    data.error_message,
                completed_at:     data.completed_at,
              }
            : t
        ))
        if (data.status === 'completed' || data.status === 'failed') {
          es.close()
          sseRefs.current.delete(taskId)
          if (data.status === 'completed') toast.success('Agent task completed!')
          else toast.error('Agent task failed.')
        }
      } catch { /* ignore parse errors */ }
    }

    es.addEventListener('done', () => {
      es.close()
      sseRefs.current.delete(taskId)
    })

    es.addEventListener('error', () => {
      es.close()
      sseRefs.current.delete(taskId)
    })

    sseRefs.current.set(taskId, es)
  }, [])

  // ── subscribe SSE for any active tasks on load ─────────────────────────────
  useEffect(() => {
    tasks
      .filter(t => t.status === 'pending' || t.status === 'processing')
      .forEach(t => subscribeSSE(t.id))
  }, [tasks, subscribeSSE])

  // cleanup SSE on unmount
  useEffect(() => {
    return () => {
      sseRefs.current.forEach(es => es.close())
      sseRefs.current.clear()
    }
  }, [])

  // ── auto-resize textarea ───────────────────────────────────────────────────
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`
    }
  }, [prompt])

  // ── submit new task ────────────────────────────────────────────────────────
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const p = prompt.trim()
    if (!p || submitting) return
    if (p.length < 10) { toast.error('Prompt must be at least 10 characters.'); return }

    setSubmitting(true)
    try {
      if (taskType === 'document') {
        // Route document generation through the documents API
        const title = docTitle.trim() || p.slice(0, 80)
        await api.post('/documents/generate/', { doc_type: docSubType, title, prompt: p })
        setPrompt('')
        setDocTitle('')
        setActiveTab('files')
        toast.success('Document queued! Check the Files tab when ready.')
        setTimeout(loadDocuments, 3000)
      } else {
        const res = await api.post('/agents/tasks/', { task_type: taskType, prompt: p })
        const newTask: AgentTask = res.data
        setTasks(prev => [newTask, ...prev])
        setPrompt('')
        setActiveTab('active')
        toast.success('Task queued!')
        subscribeSSE(newTask.id)
      }
    } catch (err: unknown) {
      // Backend wraps errors in {success, error: {code, message, details}}
      // Extract the message string safely to avoid rendering an object
      const errData = (err as { response?: { data?: { error?: string | { message?: string } } } })?.response?.data?.error
      const msg = typeof errData === 'string' 
        ? errData 
        : (errData as { message?: string })?.message ?? 'Failed to queue task.'
      toast.error(msg)
    } finally {
      setSubmitting(false)
    }
  }

  // ── cancel task ────────────────────────────────────────────────────────────
  const handleCancel = async (taskId: string) => {
    try {
      await api.post(`/agents/tasks/${taskId}/cancel/`)
      setTasks(prev => prev.map(t => t.id === taskId ? { ...t, status: 'failed' as const, error_message: 'Cancelled by user.' } : t))
      toast.success('Task cancelled.')
      sseRefs.current.get(taskId)?.close()
      sseRefs.current.delete(taskId)
    } catch {
      toast.error('Failed to cancel task.')
    }
  }

  // ── refresh single task ────────────────────────────────────────────────────
  const handleRefresh = async (taskId: string) => {
    try {
      const res = await api.get(`/agents/tasks/${taskId}/`)
      setTasks(prev => prev.map(t => t.id === taskId ? res.data : t))
    } catch {
      toast.error('Failed to refresh task.')
    }
  }

  // ── derived lists ──────────────────────────────────────────────────────────
  const activeTasks  = tasks.filter(t => t.status === 'pending' || t.status === 'processing')
  const historyTasks = tasks.filter(t => t.status === 'completed' || t.status === 'failed')

  return (
    <div className="flex-1 overflow-y-auto bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white">
      <div className="max-w-5xl mx-auto px-4 py-8 pb-24 lg:pb-8">

        {/* ── Page Header ── */}
        <div className="flex items-center gap-4 mb-8 flex-wrap">
          <div className="p-3 rounded-2xl bg-indigo-600/20 border border-indigo-500/30">
            <Bot size={28} className="text-indigo-600 dark:text-indigo-400" />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white">AI Agents</h1>
            <p className="text-slate-400 text-sm">Command autonomous agents to research, analyse, generate documents &amp; scaffold projects</p>
          </div>
          {/* TASK-306-F2: Browse Prompts link */}
          <Link
            href="/prompts"
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-indigo-50 dark:hover:bg-indigo-900/30 text-slate-600 dark:text-slate-300 hover:text-indigo-600 dark:hover:text-indigo-400 text-sm font-medium transition-colors border border-slate-200 dark:border-slate-700"
          >
            <BookOpen size={15} />
            📚 Browse Prompts
          </Link>
        </div>

        {/* ── No API key warning banner ── */}
        {apiKeyStatus && !apiKeyStatus.any_configured && (
          <div className="flex items-center gap-3 px-4 py-3 mb-6 bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/20 rounded-xl text-amber-700 dark:text-amber-300 text-sm">
            <AlertCircle size={16} className="flex-shrink-0 text-amber-500 dark:text-amber-400" />
            <span>
              No AI API key configured — agents are using the shared server key.{' '}
              <Link href="/settings" className="underline hover:text-amber-600 dark:hover:text-amber-200 font-medium">
                Add your own key in Settings → AI Engine
              </Link>{' '}
              to use your own quota.
            </span>
          </div>
        )}

        {/* ── Command Interface ── */}
        {/* Light mode: clean card with indigo accent. Dark mode: premium dark terminal. */}
        <div className="relative rounded-2xl mb-6 overflow-hidden bg-white dark:bg-[#0c0e17] border border-indigo-200 dark:border-indigo-500/20 shadow-lg shadow-indigo-500/5 dark:shadow-[0_0_0_1px_rgba(99,102,241,0.06),0_8px_40px_rgba(0,0,0,0.5)]">
          {/* Top accent line */}
          <div className="absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r from-indigo-500 via-violet-500 to-cyan-500" />

          <div className="p-4 sm:p-6">
            {/* Header */}
            <div className="flex items-center justify-between mb-5 flex-wrap gap-2">
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/30 shrink-0">
                  <Terminal size={12} className="text-white sm:w-[14px] sm:h-[14px]" />
                </div>
                <div>
                  <h2 className="text-xs sm:text-sm font-bold text-slate-800 dark:text-white tracking-tight">Command Interface</h2>
                  <p className="text-[9px] sm:text-[10px] text-slate-500 dark:text-slate-400">Autonomous AI agent execution</p>
                </div>
              </div>
              {/* Tools count chip */}
              {tools.length > 0 && (
                <div className="flex items-center gap-1.5 px-2 py-0.5 sm:px-2.5 sm:py-1 rounded-full bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-200 dark:border-indigo-500/20 text-indigo-600 dark:text-indigo-300 text-[9px] sm:text-[10px] font-bold">
                  <Zap size={9} className="sm:w-[10px] sm:h-[10px]" />
                  {tools.length} tools ready
                </div>
              )}
            </div>

            {/* Task type picker */}
            <div className="mb-4">
              <p className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-widest mb-2">Agent Mode</p>
              <div className="flex flex-wrap gap-1.5">
                {TASK_TYPES.map(tt => {
                  if (tt.locked) return (
                    <div
                      key={tt.value}
                      title={tt.lockReason}
                      className="relative group/lock flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-700/30 bg-slate-100 dark:bg-slate-800/20 opacity-40 cursor-not-allowed select-none"
                    >
                      <tt.icon size={12} className="text-slate-500 shrink-0" />
                      <span className="text-xs font-semibold text-slate-500">{tt.label}</span>
                      <svg xmlns="http://www.w3.org/2000/svg" width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-slate-500 shrink-0"><rect width="18" height="11" x="3" y="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                    </div>
                  )
                  const Icon = tt.icon
                  const active = taskType === tt.value
                  return (
                    <button
                      key={tt.value}
                      onClick={() => setTaskType(tt.value)}
                      className={cn(
                        'flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all border',
                        active
                          ? 'bg-indigo-50 dark:bg-indigo-500/20 border-indigo-300 dark:border-indigo-400/60 text-indigo-700 dark:text-indigo-200 shadow-sm'
                          : 'bg-slate-50 dark:bg-white/5 border-slate-200 dark:border-white/10 text-slate-600 dark:text-slate-400 hover:border-indigo-300 dark:hover:border-indigo-400/40 hover:text-indigo-600 dark:hover:text-slate-200 hover:bg-indigo-50/50 dark:hover:bg-white/8'
                      )}
                    >
                      <Icon size={12} className={active ? 'text-indigo-600 dark:text-indigo-300' : 'text-slate-400 dark:text-slate-500'} />
                      {tt.label}
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Document sub-options — only shown when document mode is selected */}
            {taskType === 'document' && (
              <div className="mb-4 p-3 rounded-xl bg-orange-50 dark:bg-orange-500/10 border border-orange-200 dark:border-orange-500/20">
                <p className="text-[10px] font-bold text-orange-600 dark:text-orange-400 uppercase tracking-widest mb-2">Output Format</p>
                <div className="flex flex-wrap gap-1.5 mb-3">
                  {(Object.keys(DOC_TYPE_CONFIG) as DocType[]).map(dt => {
                    const cfg = DOC_TYPE_CONFIG[dt]
                    const Icon = cfg.icon
                    const active = docSubType === dt
                    return (
                      <button key={dt} type="button" onClick={() => setDocSubType(dt)}
                        className={cn('flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all border',
                          active
                            ? 'bg-orange-100 dark:bg-orange-500/20 border-orange-400 dark:border-orange-400/60 text-orange-700 dark:text-orange-200 shadow-sm'
                            : 'bg-white dark:bg-white/5 border-slate-200 dark:border-white/10 text-slate-600 dark:text-slate-400 hover:border-orange-300 hover:text-orange-600')}>
                        <Icon size={12} />{cfg.label}
                      </button>
                    )
                  })}
                </div>
                <input
                  value={docTitle}
                  onChange={e => setDocTitle(e.target.value)}
                  placeholder="Document title (optional — will use prompt if empty)"
                  className="w-full px-3 py-2 rounded-lg border border-orange-200 dark:border-orange-500/30 bg-white dark:bg-slate-900/50 text-xs text-slate-800 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-orange-400"
                />
              </div>
            )}

            {/* Prompt input */}
            <form onSubmit={handleSubmit}>
              <div className="relative rounded-xl overflow-hidden bg-slate-50 dark:bg-[rgba(4,5,10,0.9)] border border-slate-200 dark:border-indigo-500/20">
                {/* Terminal bar */}
                <div className="flex items-center gap-1.5 px-3 py-2 border-b border-slate-200 dark:border-white/5 bg-slate-100 dark:bg-transparent">
                  <div className="w-2 h-2 rounded-full bg-red-400/70" />
                  <div className="w-2 h-2 rounded-full bg-amber-400/70" />
                  <div className="w-2 h-2 rounded-full bg-emerald-400/70" />
                  <span className="ml-2 text-[10px] text-slate-400 dark:text-slate-600 font-mono">
                    synapse-agent ~ {taskType === 'document' ? `document · ${DOC_TYPE_CONFIG[docSubType]?.label}` : TASK_TYPES.find(t => t.value === taskType)?.label?.toLowerCase() ?? 'general'}
                  </span>
                </div>
                <div className="flex items-start px-3 py-3">
                  <span className="text-indigo-500 font-mono text-sm mr-2 mt-[2px] shrink-0">▶</span>
                  <textarea
                    ref={textareaRef}
                    value={prompt}
                    onChange={e => setPrompt(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(e as unknown as React.FormEvent) } }}
                    placeholder={taskType === 'document' ? `Describe the ${DOC_TYPE_CONFIG[docSubType]?.label} you want to generate…` : `${TASK_TYPES.find(t => t.value === taskType)?.description ?? 'Describe your task'}…`}
                    rows={3}
                    className="flex-1 bg-transparent text-sm text-slate-800 dark:text-slate-200 placeholder-slate-400 dark:placeholder-slate-600 resize-none focus:outline-none font-mono leading-relaxed min-h-[72px]"
                  />
                </div>
                {/* Bottom toolbar */}
                <div className="flex items-center justify-between px-3 py-2 border-t border-slate-200 dark:border-white/5 bg-slate-50 dark:bg-transparent">
                  <p className="text-[10px] text-slate-400 dark:text-slate-600 font-mono">Enter ↵ to run · Shift+Enter for newline</p>
                  <button
                    type="submit"
                    disabled={submitting || !prompt.trim()}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed transition-all text-white text-xs font-semibold shadow-md shadow-indigo-500/20"
                  >
                    {submitting
                      ? <><Loader2 size={12} className="animate-spin" /> Running…</>
                      : <><Send size={12} /> Execute</>
                    }
                  </button>
                </div>
              </div>
            </form>

            {/* ── Research Synthesis quick-prompts (arxiv task type only) ── */}
            {taskType === 'arxiv' && (
              <div className="mt-4 rounded-xl border border-indigo-100 dark:border-indigo-800/60 bg-gradient-to-br from-indigo-50 to-violet-50 dark:from-indigo-950/30 dark:to-violet-950/20 overflow-hidden">
                <div className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-indigo-600 to-violet-600">
                  <Brain size={14} className="text-white shrink-0" />
                  <span className="text-xs font-bold text-white">AI Research Synthesis</span>
                  <span className="ml-auto text-[10px] text-indigo-200">Click to analyse papers from arXiv</span>
                </div>
                <div className="p-3 flex flex-wrap gap-1.5">
                  {RESEARCH_SYNTHESIS_PROMPTS.map(s => (
                    <button
                      key={s.label}
                      onClick={() => setPrompt(s.prompt)}
                      className="text-xs px-2.5 py-1.5 rounded-lg bg-white dark:bg-indigo-900/40 border border-indigo-200 dark:border-indigo-700 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-50 dark:hover:bg-indigo-900/60 transition font-medium"
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Quick commands */}
            <div className="mt-4">
              <p className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-widest mb-2">Quick Commands</p>
              <div className="flex flex-wrap gap-1.5">
                {COMMAND_TEMPLATES.map(tpl => (
                  <button
                    key={tpl.label}
                    onClick={() => { setPrompt(tpl.prompt); setTaskType(tpl.type) }}
                    className="text-xs px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 text-slate-600 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-300 hover:border-indigo-300 dark:hover:border-indigo-400/40 hover:bg-indigo-50 dark:hover:bg-indigo-500/5 transition-all font-medium"
                  >
                    {tpl.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Available tools strip */}
            {tools.length > 0 && (
              <div className="mt-4 pt-4 border-t border-slate-200 dark:border-white/5">
                <div className="flex flex-wrap gap-1">
                  {tools.map(tool => (
                    <span
                      key={tool.name}
                      title={tool.description}
                      className="text-[10px] px-2 py-0.5 rounded-md bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 text-slate-500 dark:text-slate-500 font-mono cursor-default hover:text-slate-700 dark:hover:text-slate-300 transition-colors"
                    >
                      {tool.name}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ── Tab bar ── */}
        <div className="flex items-center gap-1 mb-5 bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-700/60 rounded-xl p-1 w-full sm:w-fit shadow-sm overflow-x-auto scrollbar-hide">
          {([
            { id: 'active',  label: 'Active',  count: activeTasks.length },
            { id: 'history', label: 'History', count: historyTasks.length },
            { id: 'files',   label: '📄 Files',  count: documents.length },
          ] as const).map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'flex-1 sm:flex-none flex items-center justify-center gap-2 px-3 sm:px-4 py-2 rounded-lg text-xs sm:text-sm font-semibold transition-all whitespace-nowrap',
                activeTab === tab.id
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
              )}
            >
              {tab.label}
              {tab.count > 0 && (
                <span className={cn(
                  'text-[10px] sm:text-xs px-1.5 py-0.5 rounded-full font-bold',
                  activeTab === tab.id ? 'bg-white/20 text-white' : 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-400'
                )}>
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* ── Task Lists ── */}
        {loadingTasks ? (
          <div className="flex items-center justify-center py-20 text-slate-500">
            <Loader2 size={24} className="animate-spin mr-3" />
            Loading tasks…
          </div>
        ) : (
          <AnimatePresence mode="wait">
            {activeTab === 'active' ? (
              <motion.div key="active" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                {activeTasks.length === 0 ? (
                  <div className="text-center py-16 text-slate-500">
                    <Bot size={40} className="mx-auto mb-3 opacity-30" />
                    <p className="text-sm">No active tasks · run a command above</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <AnimatePresence>
                      {activeTasks.map(task => (
                        <TaskCard key={task.id} task={task} onCancel={handleCancel} onRefresh={handleRefresh} />
                      ))}
                    </AnimatePresence>
                  </div>
                )}
              </motion.div>
            ) : activeTab === 'history' ? (
              <motion.div key="history" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                {historyTasks.length === 0 ? (
                  <div className="text-center py-16 text-slate-500">
                    <Clock size={40} className="mx-auto mb-3 opacity-30" />
                    <p className="text-sm">No completed tasks yet</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <AnimatePresence>
                      {historyTasks.map(task => (
                        <TaskCard key={task.id} task={task} onCancel={handleCancel} onRefresh={handleRefresh} />
                      ))}
                    </AnimatePresence>
                  </div>
                )}
              </motion.div>
            ) : (
              <motion.div key="files" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                {loadingDocs ? (
                  <div className="flex items-center justify-center py-16 text-slate-500">
                    <Loader2 size={22} className="animate-spin mr-3" /> Loading files…
                  </div>
                ) : documents.length === 0 ? (
                  <div className="text-center py-16 text-slate-500">
                    <FileText size={40} className="mx-auto mb-3 opacity-30" />
                    <p className="text-sm">No documents yet</p><p className="text-xs text-slate-400 mt-1">Select <span className="font-semibold text-orange-500">Document</span> mode in the command interface and run a prompt</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    <AnimatePresence>
                      {documents.map(doc => (
                        <DocCard
                          key={doc.id}
                          doc={doc}
                          driveConnected={driveConnected}
                          onDelete={async (id) => {
                            await deleteDocument(id)
                            setDocuments(prev => prev.filter(d => d.id !== id))
                            toast.success('Document deleted.')
                          }}
                          onEdited={(updated) => setDocuments(prev => prev.map(d => d.id === updated.id ? updated : d))}
                        />
                      ))}
                    </AnimatePresence>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        )}
      </div>
    </div>
  )
}
