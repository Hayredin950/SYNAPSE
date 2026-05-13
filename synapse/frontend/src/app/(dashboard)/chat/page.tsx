'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Analytics } from '@/utils/analytics';
import { useSearchParams } from 'next/navigation';
import { useVoiceInput } from '@/hooks/useVoiceInput';
import { useTextToSpeech } from '@/hooks/useTextToSpeech';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Send,
  Plus,
  Trash2,
  MessageSquare,
  Loader2,
  Sparkles,
  ChevronRight,
  Bot,
  ChevronDown,
  Paperclip,
  X,
  Zap,
  AlertCircle,
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  BookOpen,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'react-hot-toast';
import { api } from '@/utils/api';
import { ChatMessage as ChatMessageType, Conversation, ChatSource } from '@/types';
import dynamic from 'next/dynamic';
// Lazy-load ChatMessage — it pulls in react-markdown, remark-gfm, remark-math,
// rehype-katex, and MermaidBlock (mermaid). This defers ~300KB of markdown/math
// libs until the chat page is actually opened, making every other page faster.
const ChatMessage = dynamic(
  () => import('@/components/chat/ChatMessage').then(m => ({ default: m.ChatMessage })),
  { ssr: false, loading: () => <div className="h-16 w-full animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" /> },
);
import { TypingIndicator } from '@/components/chat/TypingIndicator';
import { cn } from '@/utils/helpers';
import { useApiKeyStatus } from '@/hooks/useApiKeyStatus';
import Link from 'next/link';

// ─── Available models (powered by Replit AI — OpenAI-compatible) ─────────────
// All models route through Replit's built-in AI gateway (gpt-4o-mini default).
// User-supplied OpenRouter/Gemini keys unlock additional models in Settings.
const GEMINI_MODELS = [
  // ── Replit AI (built-in, no key needed) ──────────────────────────────────
  { id: 'gpt-4o-mini',   label: 'GPT-4o Mini',     badge: '⚡ Default' },
  { id: 'gpt-4o',        label: 'GPT-4o',           badge: '🧠 Smart' },
  { id: 'o1-mini',       label: 'o1 Mini',           badge: '🔬 Reasoning' },
  // ── Models available with your own OpenRouter key (add in Settings) ──────
  { id: 'google/gemini-2.0-flash-001',            label: 'Gemini 2.0 Flash',        badge: '🔑 Key needed' },
  { id: 'google/gemini-2.5-flash-preview',        label: 'Gemini 2.5 Flash Preview', badge: '🔑 Key needed' },
  { id: 'meta-llama/llama-3.3-70b-instruct',     label: 'Llama 3.3 70B',           badge: '🔑 Key needed' },
  { id: 'deepseek/deepseek-r1',                  label: 'DeepSeek R1 (Reasoning)',  badge: '🔑 Key needed' },
  { id: 'anthropic/claude-3.5-sonnet',           label: 'Claude 3.5 Sonnet',        badge: '🔑 Key needed' },
  { id: 'openai/gpt-4o',                         label: 'GPT-4o (OpenRouter)',       badge: '🔑 Key needed' },
];
const DEFAULT_MODEL = 'gpt-4o-mini';

// ─── Suggested prompts shown on empty chat ────────────────────────────────────
const SUGGESTED_PROMPTS = [
  'What are the latest AI research papers about large language models?',
  'Summarize the top trending GitHub repositories this week',
  'Explain the differences between RAG and fine-tuning',
  'What are the key trends in cloud computing right now?',
  'Find articles about TypeScript best practices',
  'What new papers have been published about diffusion models?',
];

// ─── Helpers ──────────────────────────────────────────────────────────────────
function nanoid() {
  return Math.random().toString(36).slice(2, 11);
}

function formatChatDate(isoString: string) {
  const date = new Date(isoString);
  const now = new Date();
  const diffDays = Math.floor((now.getTime() - date.getTime()) / 86_400_000);
  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays} days ago`;
  return date.toLocaleDateString();
}

// ─── API functions ────────────────────────────────────────────────────────────
async function fetchConversations(): Promise<Conversation[]> {
  const res = await api.get('/ai/chat/conversations/');
  return res.data.conversations || [];
}

async function fetchHistory(conversationId: string) {
  const res = await api.get(`/ai/chat/${conversationId}/history/`);
  return res.data;
}

async function deleteConversation(conversationId: string) {
  await api.delete(`/ai/chat/${conversationId}/`);
}

// ─── Client-side image compression (before upload) ───────────────────────────
async function compressImage(file: File, maxDim = 1024, quality = 0.82): Promise<File> {
  return new Promise((resolve) => {
    if (!file.type.startsWith('image/')) { resolve(file); return; }
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(url);
      const scale = Math.min(1, maxDim / Math.max(img.width, img.height));
      const w = Math.round(img.width * scale);
      const h = Math.round(img.height * scale);
      const canvas = document.createElement('canvas');
      canvas.width = w; canvas.height = h;
      canvas.getContext('2d')!.drawImage(img, 0, 0, w, h);
      canvas.toBlob(
        (blob) => resolve(blob ? new File([blob], file.name, { type: 'image/jpeg' }) : file),
        'image/jpeg', quality,
      );
    };
    img.onerror = () => { URL.revokeObjectURL(url); resolve(file); };
    img.src = url;
  });
}

// ─── Streaming chat via SSE ───────────────────────────────────────────────────
async function streamChat(
  question: string,
  conversationId: string,
  onToken: (token: string) => void,
  onSources: (sources: ChatSource[]) => void,
  onDone: () => void,
  onError: (err: string) => void,
  model?: string,
  attachments?: AttachedFile[],
) {
  const accessToken =
    typeof window !== 'undefined'
      ? localStorage.getItem('synapse_access_token') || ''
      : '';

  // Use the backend URL directly for SSE streaming to avoid the Next.js proxy
  // doubling the trailing slash (/api/v1/ai/chat/stream// → 404).
  // Build the stream URL. In the browser, NEXT_PUBLIC_API_URL is embedded at
  // build time. Fall back to same-host port 8000 when running locally so the
  // request bypasses the Next.js proxy (which mangles trailing slashes → 404).
  const _apiBase = process.env.NEXT_PUBLIC_API_URL || '';
  const backendBase = _apiBase
    ? _apiBase.replace(/\/$/, '').replace(/\/api\/v1$/, '')
    : (typeof window !== 'undefined'
        ? `${window.location.protocol}//${window.location.hostname}:8000`
        : 'http://localhost:8000');
  const STREAM_URL = `${backendBase}/api/v1/ai/chat/stream/`;

  let body: BodyInit;
  let headers: Record<string, string> = {};
  if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`;

  if (attachments && attachments.length > 0) {
    const form = new FormData();
    form.append('question', question);
    form.append('conversation_id', conversationId);
    if (model) form.append('model', model);
    // Compress images before upload to speed up Gemini processing
    for (const a of attachments) {
      const compressed = await compressImage(a.file);
      form.append('files', compressed, a.file.name);
    }
    body = form;
  } else {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify({ question, conversation_id: conversationId, model });
  }

  let response: Response;
  try {
    response = await fetch(STREAM_URL, {
      method: 'POST',
      headers,
      body,
    });
  } catch (e) {
    onError('Network error — please check your connection.');
    return;
  }

  if (!response.ok || !response.body) {
    onError('Server error — could not stream response.');
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';

    for (const line of lines) {
      if (line.startsWith('event: sources')) {
        // next data line has sources JSON
        continue;
      }
      if (line.startsWith('event: done')) {
        onDone();
        return;
      }
      if (line.startsWith('data: ')) {
        const raw = line.slice(6).trim();
        if (!raw) continue;
        try {
          const parsed = JSON.parse(raw);
          if (parsed.error) {
            onError(parsed.error);
            return;
          }
          // Sources are delivered as a JSON array string
          if (Array.isArray(parsed)) {
            onSources(parsed as ChatSource[]);
            continue;
          }
          // Otherwise it's a token (string)
          if (typeof parsed === 'string') {
            onToken(parsed);
          }
        } catch {
          // raw SSE data line wasn't JSON — treat as plain text token
          onToken(raw);
        }
      }
    }
  }
  onDone();
}

// ─── Fallback non-streaming chat ──────────────────────────────────────────────
async function regularChat(question: string, conversationId: string, model?: string) {
  const res = await api.post('/ai/chat/', { question, conversation_id: conversationId, model });
  return res.data;
}

// ─── Attached file type ───────────────────────────────────────────────────────
interface AttachedFile {
  id: string;
  file: File;
  preview?: string; // data URL for images
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function ChatPage() {
  const queryClient = useQueryClient();
  const { status: apiKeyStatus } = useApiKeyStatus();

  // Conversation state
  const [activeConversationId, setActiveConversationId] = useState<string>('');
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [selectedModel, setSelectedModel] = useState(DEFAULT_MODEL);
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false);
  const [attachedFiles, setAttachedFiles] = useState<AttachedFile[]>([]);

  // TASK-304-F1: Microphone / voice input
  const { isRecording, isTranscribing, startRecording, stopRecording, error: voiceError } = useVoiceInput({
    onTranscript: (text) => setInputValue((prev) => prev ? `${prev} ${text}` : text),
  })

  // TASK-304-F2: Text-to-speech
  const { isSpeaking, isSupported: ttsSupported, speak: speakText, stop: stopSpeech } = useTextToSpeech()

  // Show voice errors as toasts
  useEffect(() => {
    if (voiceError) toast.error(voiceError, { duration: 4000 })
  }, [voiceError])

  const searchParams = useSearchParams();
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const modelDropdownRef = useRef<HTMLDivElement>(null);
  const didAutoSend = useRef(false);

  // Fetch conversation list
  const { data: conversations = [], isLoading: convsLoading } = useQuery({
    queryKey: ['conversations'],
    queryFn: fetchConversations,
    staleTime: 30_000,
  });

  // Auto-scroll to bottom — scroll within the messages container only,
  // never the document body.
  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;
    container.scrollTop = container.scrollHeight;
  }, [messages]);

  // Close model dropdown when clicking outside
  useEffect(() => {
    if (!modelDropdownOpen) return;
    const handler = (e: MouseEvent) => {
      if (modelDropdownRef.current && !modelDropdownRef.current.contains(e.target as Node)) {
        setModelDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [modelDropdownOpen]);

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`;
  }, [inputValue]);

  // Load history when switching conversations
  const loadConversation = useCallback(
    async (conversationId: string) => {
      if (!conversationId) return;
      try {
        const data = await fetchHistory(conversationId);
        const loaded: ChatMessageType[] = (data.messages || []).map(
          (m: { role: 'human' | 'ai'; content: unknown; ts: number }) => ({
            id: nanoid(),
            role: m.role,
            // Backend may return content as a nested object; always extract a plain string
            content: typeof m.content === 'string'
              ? m.content
              : typeof (m.content as any)?.answer === 'string'
                ? (m.content as any).answer
                : typeof (m.content as any)?.text === 'string'
                  ? (m.content as any).text
                  : String(m.content ?? ''),
            ts: m.ts,
          })
        );
        setMessages(loaded);
        setActiveConversationId(conversationId);
      } catch {
        toast.error('Could not load conversation history.');
      }
    },
    []
  );

  // Delete conversation mutation
  const deleteMutation = useMutation({
    mutationFn: deleteConversation,
    onSuccess: (_, deletedId) => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] });
      if (deletedId === activeConversationId) {
        setActiveConversationId('');
        setMessages([]);
      }
    },
    onError: () => toast.error('Failed to delete conversation.'),
  });

  // Start a new chat — reset ALL conversation state completely
  const startNewChat = useCallback(() => {
    setActiveConversationId('');
    setMessages([]);
    setInputValue('');
    setIsGenerating(false);
    didAutoSend.current = false;
    textareaRef.current?.focus();
  }, []);

  // Delete a message pair from UI and backend
  const deleteMessagePair = useCallback(
    async (msgIndex: number) => {
      if (!activeConversationId) {
        // No backend record yet — just remove from local state
        setMessages((prev) => {
          const next = [...prev];
          // remove AI reply if present
          if (next[msgIndex + 1]?.role === 'ai') next.splice(msgIndex + 1, 1);
          next.splice(msgIndex, 1);
          return next;
        });
        return;
      }
      // Find the DB index (count only persisted messages up to this point)
      const dbIndex = msgIndex; // 1:1 with messages array since we persist in order
      try {
        await api.delete(`/ai/chat/${activeConversationId}/messages/${dbIndex}/`);
      } catch {
        // best-effort
      }
      setMessages((prev) => {
        const next = [...prev];
        if (next[msgIndex + 1]?.role === 'ai') next.splice(msgIndex + 1, 1);
        next.splice(msgIndex, 1);
        return next;
      });
    },
    [activeConversationId]
  );

  // Edit a message — repopulate input and strip messages from that point
  const editMessage = useCallback(
    (msgIndex: number, content: string) => {
      setInputValue(content);
      setMessages((prev) => prev.slice(0, msgIndex));
      textareaRef.current?.focus();
    },
    []
  );

  // File attachment helpers
  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    const newAttachments: AttachedFile[] = files.map((file) => {
      const id = nanoid();
      const af: AttachedFile = { id, file };
      if (file.type.startsWith('image/')) {
        const reader = new FileReader();
        reader.onload = (ev) => {
          setAttachedFiles((prev) =>
            prev.map((a) => a.id === id ? { ...a, preview: ev.target?.result as string } : a)
          );
        };
        reader.readAsDataURL(file);
      }
      return af;
    });
    setAttachedFiles((prev) => [...prev, ...newAttachments]);
    // Reset input so same file can be re-selected
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, []);

  const removeAttachment = useCallback((id: string) => {
    setAttachedFiles((prev) => prev.filter((a) => a.id !== id));
  }, []);

  // Send message — always creates a fresh conversation_id when activeConversationId is empty
  const sendMessage = useCallback(
    async (question: string) => {
      // Allow sending with files even if there's no text
      if ((!question.trim() && attachedFiles.length === 0) || isGenerating) return;

      // IMPORTANT: generate a brand-new ID when starting fresh so backend
      // creates a new Conversation record, not appending to an old one.
      const conversationId = activeConversationId || nanoid();
      if (!activeConversationId) setActiveConversationId(conversationId);

      // TASK-203: PostHog — track AI chat message sent
      Analytics.aiChat(question.trim().length);

      // Snapshot attachments and clear them immediately
      const currentAttachments = [...attachedFiles];
      setAttachedFiles([]);

      // Append user message immediately with attachment metadata for rendering
      const userMsg: ChatMessageType = {
        id: nanoid(),
        role: 'human',
        content: question.trim(),
        ts: Date.now() / 1000,
        attachments: currentAttachments.map((a) => ({
          name: a.file.name,
          type: a.file.type,
          preview: a.preview,
        })),
      };
      setMessages((prev) => [...prev, userMsg]);
      setInputValue('');
      setIsGenerating(true);

      // Placeholder AI message for streaming
      const aiMsgId = nanoid();
      const aiPlaceholder: ChatMessageType = {
        id: aiMsgId,
        role: 'ai',
        content: '',
        ts: Date.now() / 1000,
        isStreaming: true,
      };
      setMessages((prev) => [...prev, aiPlaceholder]);

      let streamedContent = '';
      let streamedSources: ChatSource[] = [];
      let streamingWorked = false;

      try {
        await streamChat(
          question.trim(),
          conversationId,
          (token) => {
            streamingWorked = true;
            streamedContent += token;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === aiMsgId
                  ? { ...m, content: streamedContent, isStreaming: true }
                  : m
              )
            );
          },
          (sources) => {
            streamedSources = sources;
          },
          () => {
            // done
            setMessages((prev) =>
              prev.map((m) =>
                m.id === aiMsgId
                  ? {
                      ...m,
                      content: streamedContent,
                      sources: streamedSources,
                      isStreaming: false,
                    }
                  : m
              )
            );
            setIsGenerating(false);
            queryClient.invalidateQueries({ queryKey: ['conversations'] });
          },
          (err) => {
            if (!streamingWorked) {
              // Fall back to regular (non-streaming) endpoint
              regularChat(question.trim(), conversationId, selectedModel)
                .then((data) => {
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === aiMsgId
                        ? {
                            ...m,
                            content: data.answer || 'No response received.',
                            sources: data.sources || [],
                            isStreaming: false,
                          }
                        : m
                    )
                  );
                  queryClient.invalidateQueries({ queryKey: ['conversations'] });
                })
                .catch(() => {
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === aiMsgId
                        ? {
                            ...m,
                            content: `Error: ${err}`,
                            isStreaming: false,
                          }
                        : m
                    )
                  );
                })
                .finally(() => setIsGenerating(false));
            } else {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === aiMsgId ? { ...m, isStreaming: false } : m
                )
              );
              setIsGenerating(false);
            }
          },
          selectedModel,
          currentAttachments,
        );
      } catch {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === aiMsgId
              ? { ...m, content: 'Unexpected error. Please try again.', isStreaming: false }
              : m
          )
        );
        setIsGenerating(false);
      }
    },
    [activeConversationId, isGenerating, queryClient, selectedModel, attachedFiles]
  );

  // Auto-send ?q= prompt from "Ask AI" card buttons (runs once after sendMessage is stable)
  useEffect(() => {
    const q = searchParams?.get('q');
    if (q && !didAutoSend.current) {
      didAutoSend.current = true;
      sendMessage(decodeURIComponent(q));
    }
  }, [sendMessage, searchParams]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (inputValue.trim() || attachedFiles.length > 0) {
        sendMessage(inputValue);
      }
    }
  };

  // ─── Render ────────────────────────────────────────────────────────────────
  return (
    // Absolutely fill the parent <main> element which is flex-1.
    // Using absolute inset-0 makes this 100% immune to any ancestor flex chain.
    <div className="absolute inset-0 flex overflow-hidden bg-slate-50 dark:bg-slate-950">

      {/* ── Conversation Sidebar — premium overlay ── */}
      <AnimatePresence initial={false}>
        {sidebarOpen && (
          <>
            {/* Mobile backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 z-20 bg-black/50 backdrop-blur-[2px] lg:hidden"
              onClick={() => setSidebarOpen(false)}
            />
            <motion.aside
              key="chat-sidebar"
              initial={{ x: -260, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: -260, opacity: 0 }}
              transition={{ duration: 0.22, ease: [0.32, 0.72, 0, 1] }}
              className="absolute left-0 top-0 bottom-0 z-30 w-[260px] flex flex-col overflow-hidden bg-white dark:bg-[#0f1117]"
              style={{
                borderRight: '1px solid rgba(99,102,241,0.15)',
                boxShadow: '4px 0 32px rgba(0,0,0,0.3), 1px 0 0 rgba(99,102,241,0.08)',
              }}
            >
              {/* ── Sidebar Header ── */}
              <div className="flex items-center justify-between px-3 py-3 border-b border-slate-200 dark:border-white/5">
                <div className="flex items-center gap-2.5">
                  {/* Gradient logo mark */}
                  <div className="w-7 h-7 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/30 shrink-0">
                    <MessageSquare size={13} className="text-slate-900 dark:text-white" />
                  </div>
                  <div>
                    <p className="text-xs font-bold text-slate-800 dark:text-white tracking-tight">Chat History</p>
                    <p className="text-[10px] text-slate-500 dark:text-slate-500">{conversations.length} conversation{conversations.length !== 1 ? 's' : ''}</p>
                  </div>
                </div>
                {/* Close button */}
                <button
                  onClick={() => setSidebarOpen(false)}
                  className="p-1.5 rounded-lg text-slate-500 hover:text-slate-800 dark:hover:text-white hover:bg-slate-200/80 dark:hover:bg-white/8 transition-all"
                >
                  <ChevronRight size={15} className="rotate-180" />
                </button>
              </div>

              {/* ── New Chat Button ── */}
              <div className="px-3 py-2.5 border-b border-slate-200 dark:border-white/5">
                <button
                  onClick={startNewChat}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-xl bg-indigo-50 dark:bg-indigo-600/15 hover:bg-indigo-100 dark:hover:bg-indigo-600/25 border border-indigo-200 dark:border-indigo-500/20 hover:border-indigo-300 dark:hover:border-indigo-500/40 text-indigo-600 dark:text-indigo-300 hover:text-indigo-700 dark:hover:text-white text-xs font-semibold transition-all group/new"
                >
                  <div className="w-5 h-5 rounded-lg bg-indigo-600 flex items-center justify-center shrink-0 group-hover/new:bg-indigo-500 transition-colors">
                    <Plus size={11} className="text-slate-900 dark:text-white" />
                  </div>
                  New Conversation
                </button>
              </div>

              {/* ── Conversation list ── */}
              <div className="flex-1 overflow-y-auto py-2 px-2 space-y-0.5 scrollbar-hide">
                {convsLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 size={18} className="animate-spin text-slate-600" />
                  </div>
                ) : conversations.length === 0 ? (
                  <div className="text-center py-12 px-4">
                    <div className="w-10 h-10 rounded-2xl bg-slate-100 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 flex items-center justify-center mx-auto mb-3">
                      <MessageSquare size={18} className="text-slate-500 dark:text-slate-600" />
                    </div>
                    <p className="text-xs font-semibold text-slate-400">No conversations yet</p>
                    <p className="text-[10px] text-slate-600 mt-1">Start chatting to see history here</p>
                  </div>
                ) : (
                  conversations.map((conv) => {
                    const isActive = activeConversationId === conv.conversation_id
                    return (
                      <div
                        key={conv.conversation_id}
                        className={cn(
                          'group relative flex items-start gap-2.5 px-2.5 py-2 rounded-xl cursor-pointer transition-all duration-150',
                          isActive
                            ? 'bg-indigo-50 dark:bg-indigo-600/18 border border-indigo-200 dark:border-indigo-500/25'
                            : 'hover:bg-slate-100 dark:hover:bg-white/5 border border-transparent'
                        )}
                        onClick={() => loadConversation(conv.conversation_id)}
                      >
                        {/* Active indicator */}
                        {isActive && (
                          <div className="absolute left-0 top-3 bottom-3 w-0.5 rounded-r-full bg-indigo-500" />
                        )}
                        <div className={cn(
                          'w-6 h-6 rounded-lg flex items-center justify-center shrink-0 mt-0.5 transition-colors',
                          isActive ? 'bg-indigo-100 dark:bg-indigo-600/30' : 'bg-slate-100 dark:bg-slate-800 group-hover:bg-slate-200 dark:group-hover:bg-slate-700'
                        )}>
                          <MessageSquare size={11} className={isActive ? 'text-indigo-600 dark:text-indigo-400' : 'text-slate-500'} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className={cn('text-xs font-semibold truncate leading-snug', isActive ? 'text-slate-900 dark:text-white' : 'text-slate-700 dark:text-slate-300')}>
                            {conv.title || 'Untitled'}
                          </p>
                          <p className="text-[10px] text-slate-500 dark:text-slate-600 mt-0.5 flex items-center gap-1">
                            <span>{formatChatDate(conv.updated_at)}</span>
                            <span>·</span>
                            <span>{conv.message_count} msg{conv.message_count !== 1 ? 's' : ''}</span>
                          </p>
                        </div>
                        {/* Delete button */}
                        <button
                          onClick={(e) => { e.stopPropagation(); deleteMutation.mutate(conv.conversation_id); }}
                          className="opacity-0 group-hover:opacity-100 p-1 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/40 text-slate-500 dark:text-slate-600 hover:text-red-500 dark:hover:text-red-400 transition-all shrink-0"
                          title="Delete"
                        >
                          <Trash2 size={11} />
                        </button>
                      </div>
                    )
                  })
                )}
              </div>

              {/* ── Sidebar Footer ── */}
              <div className="px-3 py-2.5 border-t border-slate-200 dark:border-white/5">
                <p className="text-[10px] text-slate-500 dark:text-slate-600 text-center">Powered by SYNAPSE RAG</p>
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      {/* ── Main Chat Area — sidebar overlays, always full width ── */}
      <div className="flex flex-col w-full min-h-0 overflow-hidden bg-slate-50 dark:bg-slate-950">

        {/* ── No API key warning banner ── */}
        {apiKeyStatus && !apiKeyStatus.any_configured && (
          <div className="flex-shrink-0 flex items-center gap-3 px-4 py-2.5 bg-amber-50 dark:bg-amber-500/10 border-b border-amber-200 dark:border-amber-500/20 text-amber-700 dark:text-amber-300 text-xs">
            <AlertCircle size={14} className="flex-shrink-0 text-amber-500 dark:text-amber-400" />
            <span>
              No AI API key configured — chat is using the shared server key.{' '}
              <Link href="/settings" className="underline hover:text-amber-600 dark:hover:text-amber-200 font-medium">
                Add your own key in Settings → AI Engine
              </Link>{' '}
              for dedicated access.
            </span>
          </div>
        )}

        {/* Chat header */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/50 flex-shrink-0">
          {/* Sidebar toggle */}
          <button
            onClick={() => setSidebarOpen((v) => !v)}
            className={cn(
              'relative p-2 rounded-xl transition-all duration-200',
              sidebarOpen
                ? 'text-indigo-600 dark:text-indigo-400 bg-indigo-600/15 border border-indigo-500/25'
                : 'text-slate-500 hover:text-slate-800 dark:hover:text-white hover:bg-slate-200 dark:hover:bg-slate-800/80 border border-transparent hover:border-slate-300 dark:hover:border-slate-700'
            )}
          >
            <ChevronRight
              size={16}
              className={cn('transition-transform duration-200', sidebarOpen && 'rotate-180')}
            />
          </button>
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center">
              <Bot size={14} className="text-slate-900 dark:text-white" />
            </div>
            <div>
              <h1 className="text-sm font-semibold text-slate-800 dark:text-white">SYNAPSE AI</h1>
              <p className="text-[10px] text-slate-400">RAG-powered · grounded in your knowledge base</p>
            </div>
          </div>

          {/* ── Model selector — premium grouped dropdown ── */}
          <div ref={modelDropdownRef} className="relative ml-3">
            <button
              onClick={() => setModelDropdownOpen((v) => !v)}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-800/80 hover:bg-slate-200 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700/80 hover:border-indigo-300 dark:hover:border-indigo-500/50 text-xs text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white transition-all group"
            >
              <Zap size={11} className="text-indigo-600 dark:text-indigo-400 shrink-0" />
              <span className="max-w-[110px] sm:max-w-[140px] truncate font-medium">
                {GEMINI_MODELS.find((m) => m.id === selectedModel)?.label ?? 'Select model'}
              </span>
              <ChevronDown size={11} className={cn('transition-transform shrink-0 text-slate-500 dark:group-hover:text-slate-300', modelDropdownOpen && 'rotate-180')} />
            </button>

            <AnimatePresence>
              {modelDropdownOpen && (
                <motion.div
                  initial={{ opacity: 0, y: -4, scale: 0.97 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -4, scale: 0.97 }}
                  transition={{ duration: 0.12 }}
                  className="absolute left-0 top-full mt-2 z-50 w-72 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700/80 rounded-2xl shadow-2xl shadow-black/20 dark:shadow-black/40 overflow-hidden backdrop-blur-sm"
                >
                  {/* Header */}
                  <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700/60 bg-slate-50 dark:bg-slate-800/60">
                    <p className="text-[10px] font-bold text-slate-600 dark:text-slate-300 uppercase tracking-widest flex items-center gap-1.5">
                      <Zap size={10} className="text-indigo-600 dark:text-indigo-400" /> AI Model
                    </p>
                    <p className="text-[10px] text-slate-500 mt-0.5">Choose the model for this conversation</p>
                  </div>
                  <div className="max-h-80 overflow-y-auto py-1.5">
                    {/* Group: Built-in (no key needed) */}
                    <p className="px-3 py-1.5 text-[9px] font-black uppercase tracking-widest text-indigo-500/70">⚡ Built-in</p>
                    {GEMINI_MODELS.filter(m => !m.badge?.includes('Key needed')).map(m => (
                      <button
                        key={m.id}
                        onClick={() => { setSelectedModel(m.id); setModelDropdownOpen(false); }}
                        className={cn(
                          'w-full flex items-center justify-between px-3 py-2 text-xs transition-all text-left group/item rounded-lg mx-1.5 mb-0.5 w-[calc(100%-12px)]',
                          selectedModel === m.id
                            ? 'bg-indigo-600/15 dark:bg-indigo-600/25 border border-indigo-300 dark:border-indigo-500/30 text-indigo-700 dark:text-white'
                            : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-white border border-transparent'
                        )}
                      >
                        <span className="flex items-center gap-2 min-w-0">
                          {selectedModel === m.id
                            ? <div className="w-1.5 h-1.5 rounded-full bg-indigo-500 dark:bg-indigo-400 shrink-0" />
                            : <div className="w-1.5 h-1.5 rounded-full bg-transparent shrink-0" />
                          }
                          <span className="truncate font-medium">{m.label}</span>
                        </span>
                        {m.badge && (
                          <span className={cn(
                            'text-[9px] px-1.5 py-0.5 rounded-full font-bold shrink-0 ml-2 border',
                            m.badge.includes('Default') ? 'bg-indigo-100 dark:bg-indigo-500/20 text-indigo-700 dark:text-indigo-300 border-indigo-500/30' :
                            m.badge.includes('Smart')   ? 'bg-violet-100 dark:bg-violet-500/20 text-violet-700 dark:text-violet-300 border-violet-500/30' :
                            m.badge.includes('Reason')  ? 'bg-cyan-100 dark:bg-cyan-500/20 text-cyan-700 dark:text-cyan-300 border-cyan-500/30' :
                            'bg-slate-100 dark:bg-slate-700/80 text-slate-500 dark:text-slate-400 border-slate-200 dark:border-slate-600/50'
                          )}>
                            {m.badge}
                          </span>
                        )}
                      </button>
                    ))}
                    {/* Group: Bring your own key */}
                    <p className="px-3 pt-2 pb-1.5 text-[9px] font-black uppercase tracking-widest text-amber-500/70">🔑 Your key (Settings → AI Engine)</p>
                    {GEMINI_MODELS.filter(m => m.badge?.includes('Key needed')).map(m => (
                      <button
                        key={m.id}
                        onClick={() => { setSelectedModel(m.id); setModelDropdownOpen(false); }}
                        className={cn(
                          'w-full flex items-center justify-between px-3 py-2 text-xs transition-all text-left rounded-lg mx-1.5 mb-0.5 w-[calc(100%-12px)]',
                          selectedModel === m.id
                            ? 'bg-indigo-600/15 dark:bg-indigo-600/25 border border-indigo-300 dark:border-indigo-500/30 text-indigo-700 dark:text-white'
                            : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-white border border-transparent'
                        )}
                      >
                        <span className="flex items-center gap-2 min-w-0">
                          {selectedModel === m.id
                            ? <div className="w-1.5 h-1.5 rounded-full bg-indigo-500 dark:bg-indigo-400 shrink-0" />
                            : <div className="w-1.5 h-1.5 rounded-full bg-transparent shrink-0" />
                          }
                          <span className="truncate font-medium">{m.label}</span>
                        </span>
                        <span className="text-[9px] px-1.5 py-0.5 rounded-full font-bold shrink-0 ml-2 border bg-amber-50 dark:bg-amber-500/15 text-amber-600 dark:text-amber-300 border-amber-200 dark:border-amber-500/25">
                          {m.badge}
                        </span>
                      </button>
                    ))}
                  </div>
                  {/* Footer */}
                  <div className="px-4 py-2.5 border-t border-slate-200 dark:border-slate-700/60 bg-slate-50 dark:bg-slate-800/40">
                    <p className="text-[9px] text-slate-500 dark:text-slate-600">Powered by OpenRouter · Requires your API key in Settings</p>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {activeConversationId && (
            <button
              onClick={startNewChat}
              className="ml-auto flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 rounded-lg transition-colors border border-slate-700"
            >
              <Plus size={12} />
              New Chat
            </button>
          )}
        </div>

        {/* Messages area */}
        <div ref={messagesContainerRef} className="flex-1 overflow-y-auto px-4 py-6 space-y-6">
          {messages.length === 0 ? (
            /* ── Empty state ── */
            <div className="flex flex-col items-center justify-center h-full gap-8 text-center px-4">
              <div>
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center mx-auto mb-4 shadow-lg shadow-indigo-900/40">
                  <Sparkles size={28} className="text-slate-900 dark:text-white" />
                </div>
                <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-2">Ask SYNAPSE AI</h2>
                <p className="text-sm text-slate-400 max-w-md">
                  Get answers grounded in your knowledge base — articles, papers, repositories, and more.
                </p>
              </div>

              {/* Suggested prompts */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-2xl">
                {SUGGESTED_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => sendMessage(prompt)}
                    className={cn(
                      'text-left px-4 py-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/60',
                      'text-sm text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:border-indigo-500/60 hover:bg-slate-100 dark:hover:bg-slate-800',
                      'transition-all duration-150'
                    )}
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            /* ── Messages ── */
            <>
              <AnimatePresence initial={false}>
                {messages.map((msg, idx) => (
                  <motion.div
                    key={msg.id}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    <ChatMessage
                      message={msg}
                      messageIndex={idx}
                      onEdit={msg.role === 'human' ? editMessage : undefined}
                      onDelete={msg.role === 'human' ? deleteMessagePair : undefined}
                    />
                    {/* TASK-304-F2: TTS "Read Aloud" button for AI messages */}
                    {msg.role === 'ai' && !msg.isStreaming && msg.content && ttsSupported && (
                      <div className="flex justify-start pl-11 -mt-4 mb-1">
                        <button
                          onClick={() => isSpeaking ? stopSpeech() : speakText(msg.content)}
                          title={isSpeaking ? 'Stop reading' : 'Read aloud'}
                          className={cn(
                            'flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-medium transition-all',
                            isSpeaking
                              ? 'text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-200 dark:border-indigo-500/30'
                              : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 border border-transparent hover:border-slate-200 dark:hover:border-slate-700'
                          )}
                        >
                          {isSpeaking ? <VolumeX size={11} /> : <Volume2 size={11} />}
                          {isSpeaking ? 'Stop' : 'Read aloud'}
                        </button>
                      </div>
                    )}
                  </motion.div>
                ))}
              </AnimatePresence>

              {/* Typing indicator — shown ONLY while waiting for the very first
                  token (content is still empty string).
                  Once ANY content arrives, ChatMessage takes over and renders
                  a streaming cursor instead — TypingIndicator must be gone.
                  Condition: generating + last msg is AI + streaming + NO content yet.
                  ChatMessage returns null for this same state, so exactly ONE
                  bot avatar is ever visible at a time. */}
              {(() => {
                const last = messages[messages.length - 1];
                const showTyping =
                  isGenerating &&
                  last?.role === 'ai' &&
                  last?.isStreaming === true &&
                  (last?.content ?? '') === '';
                return showTyping ? <TypingIndicator /> : null;
              })()}
            </>
          )}
          <div />
        </div>

        {/* ── Input Area ── */}
        <div className="flex-shrink-0 border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 px-4 py-3">
          <div className="max-w-4xl mx-auto">

            {/* ── Gemini-style input card ── */}
            <div className={cn(
              'bg-slate-100 dark:bg-slate-800 border rounded-3xl transition-colors overflow-hidden',
              isGenerating ? 'border-slate-200 dark:border-slate-700' : 'border-slate-300 dark:border-slate-600 focus-within:border-indigo-400 dark:focus-within:border-indigo-500/70'
            )}>

              {/* Image grid staging area — shown above textarea when files are attached */}
              {attachedFiles.length > 0 && (
                <div className="px-4 pt-3 pb-1">
                  <div className={cn(
                    'grid gap-2',
                    attachedFiles.length === 1 ? 'grid-cols-1' :
                    attachedFiles.length === 2 ? 'grid-cols-2' :
                    'grid-cols-3'
                  )}>
                    {attachedFiles.map((af) => (
                      <div key={af.id} className="relative group rounded-xl overflow-hidden">
                        {af.preview ? (
                          <>
                            <img
                              src={af.preview}
                              alt={af.file.name}
                              className="w-full object-cover rounded-xl"
                              style={{ maxHeight: attachedFiles.length === 1 ? 240 : 140 }}
                            />
                            {/* Dark overlay on hover */}
                            <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-colors rounded-xl" />
                          </>
                        ) : (
                          <div className="flex items-center gap-2 bg-slate-100 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-xl px-3 py-3 text-xs text-slate-600 dark:text-slate-300">
                            <Paperclip size={13} className="text-indigo-600 dark:text-indigo-400 flex-shrink-0" />
                            <span className="truncate">{af.file.name}</span>
                          </div>
                        )}
                        {/* Remove button */}
                        <button
                          onClick={() => removeAttachment(af.id)}
                          className="absolute top-1.5 right-1.5 w-6 h-6 rounded-full bg-black/70 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-600"
                        >
                          <X size={12} />
                        </button>
                        {/* Filename badge for images */}
                        {af.preview && (
                          <div className="absolute bottom-1.5 left-1.5 bg-black/60 text-white text-[9px] px-1.5 py-0.5 rounded-md truncate max-w-[80%] opacity-0 group-hover:opacity-100 transition-opacity">
                            {af.file.name}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Text input row */}
              <div className="flex items-end gap-2 px-3 py-3">
                {/* Hidden file input */}
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept="image/*,.pdf,.txt,.md,.csv,.json,.py,.js,.ts,.jsx,.tsx"
                  className="hidden"
                  onChange={handleFileSelect}
                />

                {/* Attach button */}
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isGenerating}
                  title="Attach files"
                  className="flex-shrink-0 p-2 rounded-full text-slate-400 hover:text-slate-200 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors disabled:opacity-40"
                >
                  <Paperclip size={18} />
                </button>

                {/* TASK-306-F2: Browse Prompts button */}
                <Link
                  href="/prompts"
                  title="Browse Prompt Library"
                  className="flex-shrink-0 p-2 rounded-full text-slate-400 hover:text-indigo-400 hover:bg-indigo-500/10 dark:hover:bg-slate-700 transition-colors"
                >
                  <BookOpen size={18} />
                </Link>

                {/* TASK-304-F1: Mic button — click to start/stop recording */}
                <button
                  onClick={isRecording ? stopRecording : startRecording}
                  disabled={isGenerating || isTranscribing}
                  title={isRecording ? 'Stop recording' : isTranscribing ? 'Transcribing…' : 'Voice input'}
                  className={cn(
                    'flex-shrink-0 p-2 rounded-full transition-all',
                    isRecording
                      ? 'text-red-500 bg-red-500/15 border border-red-500/40 animate-pulse'
                      : isTranscribing
                        ? 'text-indigo-400 bg-indigo-500/10 cursor-wait'
                        : 'text-slate-400 hover:text-indigo-400 hover:bg-indigo-500/10 dark:hover:bg-slate-700 disabled:opacity-40'
                  )}
                >
                  {isTranscribing
                    ? <Loader2 size={18} className="animate-spin" />
                    : isRecording
                      ? <MicOff size={18} />
                      : <Mic size={18} />
                  }
                </button>

                <textarea
                  ref={textareaRef}
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={attachedFiles.length > 0
                    ? 'Add a message or just press Send…'
                    : 'Ask about articles, papers, repos… (Enter to send)'}
                  disabled={isGenerating}
                  rows={1}
                  className="flex-1 bg-transparent text-slate-800 dark:text-slate-100 placeholder-slate-500 text-sm resize-none focus:outline-none min-h-[24px] max-h-[160px] py-1.5 disabled:opacity-50"
                />

                <button
                  onClick={() => sendMessage(inputValue)}
                  disabled={(!inputValue.trim() && attachedFiles.length === 0) || isGenerating}
                  className={cn(
                    'flex-shrink-0 p-2.5 rounded-full transition-all',
                    (inputValue.trim() || attachedFiles.length > 0) && !isGenerating
                      ? 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-900/40'
                      : 'bg-slate-200 dark:bg-slate-700 text-slate-400 dark:text-slate-500 cursor-not-allowed'
                  )}
                  title="Send message"
                >
                  {isGenerating ? (
                    <Loader2 size={17} className="animate-spin" />
                  ) : (
                    <Send size={17} />
                  )}
                </button>
              </div>
            </div>

            <p className="text-center text-[10px] text-slate-600 mt-2">
              Responses are grounded in the SYNAPSE knowledge base. Always verify important information.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
