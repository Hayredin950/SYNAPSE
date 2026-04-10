'use client'

/**
 * AIAssistantPanel — Persistent right-side AI assistant (TASK-403-2)
 * Features:
 * - Markdown rendering (GFM, code blocks, math)
 * - Message actions: copy, edit, delete, read aloud
 * - Drag-to-resize panel width
 * - Context-aware per page
 * - Collapses to icon strip; hidden on /chat page
 */

import React, { useState, useRef, useEffect, useCallback } from 'react'
import { usePathname } from 'next/navigation'
import {
  MessageSquare, Send, ChevronRight, Sparkles, Copy, RotateCcw,
  Loader2, User, Bot, Trash2, Pencil, Volume2, VolumeX, Check, X,
  GripVertical,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api } from '@/utils/api'

// ─── Types ────────────────────────────────────────────────────────────────────
interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}

interface AIAssistantPanelProps {
  isOpen: boolean
  onToggle: () => void
  className?: string
}

// ─── Page context helper ───────────────────────────────────────────────────────
function getPageContext(pathname: string): string {
  const page = pathname.split('/').filter(Boolean).pop() || 'dashboard'
  const map: Record<string, string> = {
    trends:       'Technology Trends — live radar with daily trend scores',
    feed:         'Personalised article feed',
    search:       'Search page',
    agents:       'AI Agents configuration',
    automation:   'Automation workflows',
    documents:    'Document generation',
    research:     'Research sessions',
    library:      'Saved content library',
    profile:      'Profile settings',
    billing:      'Billing & subscription',
    notifications:'Notifications',
    github:       'GitHub repositories',
    videos:       'Videos feed',
    tweets:       'Tweets feed',
    dashboard:    'Main dashboard overview',
  }
  return map[page] ?? `${page} page`
}

// ─── Mini markdown renderer ────────────────────────────────────────────────────
function MsgMarkdown({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        // inline code
        code({ children, className }) {
          const isBlock = className?.includes('language-')
          if (!isBlock) {
            return (
              <code className="bg-black/20 rounded px-1 py-0.5 text-[11px] font-mono">
                {children}
              </code>
            )
          }
          return (
            <pre className="bg-slate-900 rounded-lg p-2 my-1 overflow-x-auto">
              <code className="text-green-400 text-[11px] font-mono">{children}</code>
            </pre>
          )
        },
        p: ({ children }) => <p className="mb-1 last:mb-0">{children}</p>,
        ul: ({ children }) => <ul className="list-disc list-inside mb-1 space-y-0.5">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal list-inside mb-1 space-y-0.5">{children}</ol>,
        li: ({ children }) => <li className="text-xs">{children}</li>,
        strong: ({ children }) => <strong className="font-bold">{children}</strong>,
        em: ({ children }) => <em className="italic">{children}</em>,
        h1: ({ children }) => <h1 className="font-bold text-sm mb-1">{children}</h1>,
        h2: ({ children }) => <h2 className="font-semibold text-xs mb-1">{children}</h2>,
        h3: ({ children }) => <h3 className="font-semibold text-xs mb-0.5">{children}</h3>,
        blockquote: ({ children }) => (
          <blockquote className="border-l-2 border-indigo-400 pl-2 my-1 opacity-80">{children}</blockquote>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  )
}

// ─── Message bubble with actions ──────────────────────────────────────────────
function MessageBubble({
  message,
  onDelete,
  onEdit,
}: {
  message: Message
  onDelete: (id: string) => void
  onEdit: (id: string, newContent: string) => void
}) {
  const [copied, setCopied] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const [editing, setEditing] = useState(false)
  const [editValue, setEditValue] = useState(message.content)
  const [hover, setHover] = useState(false)
  const isUser = message.role === 'user'

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  const handleRead = () => {
    if (speaking) {
      window.speechSynthesis.cancel()
      setSpeaking(false)
      return
    }
    const utt = new SpeechSynthesisUtterance(message.content)
    utt.onend = () => setSpeaking(false)
    window.speechSynthesis.speak(utt)
    setSpeaking(true)
  }

  const handleSaveEdit = () => {
    if (editValue.trim()) {
      onEdit(message.id, editValue.trim())
    }
    setEditing(false)
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex gap-2 group ${isUser ? 'justify-end' : 'justify-start'}`}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      {/* Avatar */}
      {!isUser && (
        <div className="w-6 h-6 rounded-full bg-indigo-100 dark:bg-indigo-900 flex items-center justify-center shrink-0 mt-0.5">
          <Bot size={12} className="text-indigo-600 dark:text-indigo-400" />
        </div>
      )}

      <div className={`flex flex-col gap-1 max-w-[85%] ${isUser ? 'items-end' : 'items-start'}`}>
        {/* Bubble */}
        {editing ? (
          <div className="w-full">
            <textarea
              value={editValue}
              onChange={e => setEditValue(e.target.value)}
              className="w-full resize-none rounded-xl border border-indigo-400 bg-white dark:bg-slate-800 px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500"
              rows={3}
              autoFocus
            />
            <div className="flex gap-1 mt-1 justify-end">
              <button onClick={() => setEditing(false)} className="p-1 rounded text-slate-500 hover:text-slate-700 dark:hover:text-slate-300">
                <X size={12} />
              </button>
              <button onClick={handleSaveEdit} className="p-1 rounded bg-indigo-600 text-white hover:bg-indigo-500">
                <Check size={12} />
              </button>
            </div>
          </div>
        ) : (
          <div
            className={`rounded-2xl px-3 py-2 text-xs leading-relaxed ${
              isUser
                ? 'bg-indigo-600 text-white'
                : 'bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200'
            }`}
          >
            {isUser ? (
              <p className="whitespace-pre-wrap">{message.content}</p>
            ) : (
              <MsgMarkdown content={message.content} />
            )}
          </div>
        )}

        {/* Action bar — visible on hover */}
        <AnimatePresence>
          {hover && !editing && (
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              transition={{ duration: 0.1 }}
              className={`flex gap-0.5 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
            >
              {/* Copy */}
              <button
                onClick={handleCopy}
                title="Copy"
                className="p-1 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-500 hover:text-indigo-600 dark:hover:text-indigo-400 shadow-sm transition-colors"
              >
                {copied ? <Check size={11} className="text-green-500" /> : <Copy size={11} />}
              </button>
              {/* Read aloud */}
              <button
                onClick={handleRead}
                title={speaking ? 'Stop' : 'Read aloud'}
                className="p-1 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-500 hover:text-indigo-600 dark:hover:text-indigo-400 shadow-sm transition-colors"
              >
                {speaking ? <VolumeX size={11} /> : <Volume2 size={11} />}
              </button>
              {/* Edit (user messages only) */}
              {isUser && (
                <button
                  onClick={() => { setEditValue(message.content); setEditing(true) }}
                  title="Edit"
                  className="p-1 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-500 hover:text-indigo-600 dark:hover:text-indigo-400 shadow-sm transition-colors"
                >
                  <Pencil size={11} />
                </button>
              )}
              {/* Delete */}
              <button
                onClick={() => onDelete(message.id)}
                title="Delete"
                className="p-1 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-500 hover:text-red-500 shadow-sm transition-colors"
              >
                <Trash2 size={11} />
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* User avatar */}
      {isUser && (
        <div className="w-6 h-6 rounded-full bg-slate-200 dark:bg-slate-700 flex items-center justify-center shrink-0 mt-0.5">
          <User size={12} className="text-slate-600 dark:text-slate-400" />
        </div>
      )}
    </motion.div>
  )
}

// ─── Main Panel ───────────────────────────────────────────────────────────────
const MIN_WIDTH = 280
const MAX_WIDTH = 600
const DEFAULT_WIDTH = 320

export function AIAssistantPanel({ isOpen, onToggle, className }: AIAssistantPanelProps) {
  const pathname = usePathname()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [panelWidth, setPanelWidth] = useState(DEFAULT_WIDTH)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const dragging = useRef(false)
  const dragStartX = useRef(0)
  const dragStartW = useRef(DEFAULT_WIDTH)

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // ── Drag-to-resize ────────────────────────────────────────────────────────
  const onDragStart = useCallback((e: React.MouseEvent) => {
    dragging.current = true
    dragStartX.current = e.clientX
    dragStartW.current = panelWidth
    e.preventDefault()
  }, [panelWidth])

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragging.current) return
      // Dragging left edge: moving mouse left → wider panel
      const delta = dragStartX.current - e.clientX
      const next = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, dragStartW.current + delta))
      setPanelWidth(next)
    }
    const onUp = () => { dragging.current = false }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
  }, [])

  // ── Send message ──────────────────────────────────────────────────────────
  const sendMessage = async (content = input) => {
    if (!content.trim() || isLoading) return
    const userMsg: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: content.trim(),
      timestamp: new Date(),
    }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setIsLoading(true)

    try {
      const res = await api.post('/ai/chat/', {
        question: content.trim(),
        conversation_id: 'assistant-panel',
        model: 'google/gemini-2.0-flash-001',
        context: getPageContext(pathname),
      })
      const assistantMsg: Message = {
        id: `ai-${Date.now()}`,
        role: 'assistant',
        content: res.data.answer || res.data.response || 'No response.',
        timestamp: new Date(),
      }
      setMessages(prev => [...prev, assistantMsg])
    } catch {
      setMessages(prev => [...prev, {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: 'Connection error — please try again.',
        timestamp: new Date(),
      }])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const deleteMessage = (id: string) => setMessages(prev => prev.filter(m => m.id !== id))

  const editMessage = (id: string, newContent: string) => {
    setMessages(prev => prev.map(m => m.id === id ? { ...m, content: newContent } : m))
  }

  // ── Collapsed (icon strip) ─────────────────────────────────────────────────
  if (!isOpen) {
    return (
      <div className="hidden xl:flex flex-col w-12 bg-white dark:bg-slate-900 border-l border-slate-200 dark:border-slate-700 shrink-0">
        <button
          onClick={onToggle}
          className="p-3 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors border-b border-slate-200 dark:border-slate-700 group"
          title="Open AI Assistant"
        >
          <MessageSquare size={18} className="text-slate-500 group-hover:text-indigo-600 dark:group-hover:text-indigo-400" />
        </button>
        <div className="flex-1 flex flex-col items-center py-4 gap-3">
          <div className="w-2 h-2 rounded-full bg-green-500" title="AI Online" />
          {messages.length > 0 && (
            <div className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse" />
          )}
        </div>
      </div>
    )
  }

  // ── Expanded panel ─────────────────────────────────────────────────────────
  return (
    <div
      className={`hidden xl:flex flex-col bg-white dark:bg-slate-900 border-l border-slate-200 dark:border-slate-700 shrink-0 relative ${className || ''}`}
      style={{ width: panelWidth }}
    >
      {/* Drag handle — left edge */}
      <div
        onMouseDown={onDragStart}
        className="absolute left-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-indigo-400 transition-colors z-10 group flex items-center justify-center"
        title="Drag to resize"
      >
        <GripVertical size={12} className="text-slate-300 opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>

      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-slate-200 dark:border-slate-700 shrink-0">
        <div className="flex items-center gap-2">
          <Sparkles size={14} className="text-indigo-600 dark:text-indigo-400" />
          <span className="text-sm font-semibold text-slate-800 dark:text-white">AI Assistant</span>
          <div className="w-1.5 h-1.5 rounded-full bg-green-500" />
        </div>
        <div className="flex items-center gap-1">
          {messages.length > 0 && (
            <button
              onClick={() => setMessages([])}
              title="Clear conversation"
              className="p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
            >
              <RotateCcw size={13} />
            </button>
          )}
          <button
            onClick={onToggle}
            title="Collapse panel"
            className="p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
          >
            <ChevronRight size={14} />
          </button>
        </div>
      </div>

      {/* Context badge */}
      <div className="px-3 py-1.5 bg-indigo-50 dark:bg-indigo-950/30 border-b border-indigo-100 dark:border-indigo-900 shrink-0">
        <p className="text-[10px] text-indigo-600 dark:text-indigo-400 truncate">
          📍 {getPageContext(pathname)}
        </p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3 min-h-0">
        {messages.length === 0 ? (
          <div className="text-center py-10 px-2">
            <Sparkles size={28} className="mx-auto mb-3 text-slate-300 dark:text-slate-600" />
            <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
              Ask me anything — I know you&apos;re on the <strong>{getPageContext(pathname).split(' ')[0]}</strong> page.
            </p>
          </div>
        ) : (
          <>
            {messages.map(msg => (
              <MessageBubble
                key={msg.id}
                message={msg}
                onDelete={deleteMessage}
                onEdit={editMessage}
              />
            ))}
            {isLoading && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex gap-2 justify-start"
              >
                <div className="w-6 h-6 rounded-full bg-indigo-100 dark:bg-indigo-900 flex items-center justify-center shrink-0">
                  <Loader2 size={12} className="text-indigo-600 animate-spin" />
                </div>
                <div className="bg-slate-100 dark:bg-slate-800 rounded-2xl px-3 py-2">
                  <div className="flex gap-1">
                    <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                </div>
              </motion.div>
            )}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-slate-200 dark:border-slate-700 shrink-0">
        <div className="flex gap-2 items-end">
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about this page… (Enter to send)"
            className="flex-1 resize-none rounded-xl border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-800 px-3 py-2 text-xs placeholder-slate-400 dark:placeholder-slate-500 focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400 dark:focus:border-indigo-500 outline-none transition-colors"
            rows={2}
            disabled={isLoading}
          />
          <button
            onClick={() => sendMessage()}
            disabled={!input.trim() || isLoading}
            className="shrink-0 w-8 h-8 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white flex items-center justify-center transition-colors"
          >
            {isLoading
              ? <Loader2 size={13} className="animate-spin" />
              : <Send size={13} />
            }
          </button>
        </div>
        <p className="text-[10px] text-slate-400 dark:text-slate-600 mt-1.5 text-center">
          Shift+Enter for new line • Drag left edge to resize
        </p>
      </div>
    </div>
  )
}
