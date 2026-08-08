'use client'

import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  BookMarked, FolderPlus, Trash2, FileText, GitBranch, BookOpen,
  Loader2, Plus, X, ChevronRight, ArrowLeft, FolderOpen, Globe, Lock,
  Check, FolderCheck, Pencil, Save, Twitter,
} from 'lucide-react'
import { api } from '@/utils/api'
import { cn } from '@/utils/helpers'
import { motion, AnimatePresence } from 'framer-motion'
import toast from 'react-hot-toast'
import { SmartCollections } from '@/components/ui/SmartCollections'
import { NotionExport } from '@/components/ui/NotionExport'
import { ShareDigest } from '@/components/ui/ShareDigest'

type ContentTab = 'all' | 'article' | 'repository' | 'researchpaper' | 'tweet'

const contentTabs = [
  { id: 'all' as ContentTab, label: 'All', icon: BookMarked },
  { id: 'article' as ContentTab, label: 'Articles', icon: FileText },
  { id: 'repository' as ContentTab, label: 'Repos', icon: GitBranch },
  { id: 'researchpaper' as ContentTab, label: 'Papers', icon: BookOpen },
  { id: 'tweet' as ContentTab, label: 'Tweets', icon: Twitter },
]

// ── InlineNoteEditor ──────────────────────────────────────────────────────────

function InlineNoteEditor({ bookmark, onSaved }: { bookmark: any; onSaved: (notes: string) => void }) {
  const [editing, setEditing] = React.useState(false)
  const [value, setValue] = React.useState(bookmark.notes || '')
  const [saving, setSaving] = React.useState(false)
  const textareaRef = React.useRef<HTMLTextAreaElement>(null)

  const handleEdit = (e: React.MouseEvent) => {
    e.stopPropagation()
    setEditing(true)
    setTimeout(() => textareaRef.current?.focus(), 50)
  }

  const handleSave = async (e: React.MouseEvent) => {
    e.stopPropagation()
    setSaving(true)
    try {
      await api.patch(`/bookmarks/${bookmark.id}/notes/`, { notes: value })
      onSaved(value)
      setEditing(false)
      toast.success('Note saved', { style: { background: '#1e293b', color: '#f1f5f9' } })
    } catch {
      toast.error('Failed to save note', { style: { background: '#1e293b', color: '#f1f5f9' } })
    } finally {
      setSaving(false)
    }
  }

  const handleCancel = (e: React.MouseEvent) => {
    e.stopPropagation()
    setValue(bookmark.notes || '')
    setEditing(false)
  }

  if (editing) {
    return (
      <div className="mt-2" onClick={e => e.stopPropagation()}>
        <textarea
          ref={textareaRef}
          value={value}
          onChange={e => setValue(e.target.value)}
          placeholder="Add a note about this bookmark…"
          rows={2}
          className="w-full text-xs bg-slate-50 dark:bg-slate-700/80 border border-slate-300 dark:border-slate-600 rounded-lg px-2.5 py-2 text-slate-700 dark:text-slate-200 placeholder-slate-400 dark:placeholder-slate-500 resize-none focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500"
        />
        <div className="flex gap-1.5 mt-1.5">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-1 px-2.5 py-1 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-white text-xs font-semibold rounded-lg transition-colors"
          >
            {saving ? <Loader2 size={11} className="animate-spin" /> : <Save size={11} />}
            Save
          </button>
          <button
            onClick={handleCancel}
            className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-600 dark:text-slate-400 text-xs rounded-lg transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="mt-1 flex items-start gap-1 min-w-0">
      {value ? (
        <p className="text-xs text-slate-400 italic line-clamp-1 flex-1 min-w-0">"{value}"</p>
      ) : (
        <p className="text-xs text-slate-600 flex-1">No note yet</p>
      )}
      <button
        onClick={handleEdit}
        className="opacity-0 group-hover:opacity-100 shrink-0 p-0.5 text-slate-600 hover:text-indigo-600 dark:hover:text-indigo-400 transition-all rounded"
        title="Edit note"
      >
        <Pencil size={11} />
      </button>
    </div>
  )
}

// ── AddToCollectionModal ──────────────────────────────────────────────────────

function AddToCollectionModal({
  bookmark,
  onClose,
}: {
  bookmark: any
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const [adding, setAdding] = useState<string | null>(null)
  const [added, setAdded] = useState<Set<string>>(new Set())

  const { data: colData, isLoading } = useQuery({
    queryKey: ['collections'],
    queryFn: () => api.get('/collections/').then(r => r.data),
  })
  const collections: any[] = colData?.data ?? colData?.results ?? []

  const handleAdd = async (collectionId: string) => {
    setAdding(collectionId)
    try {
      await api.post(`/collections/${collectionId}/bookmarks/`, { bookmark_id: bookmark.id })
      setAdded(prev => new Set(prev).add(collectionId))
      queryClient.invalidateQueries({ queryKey: ['collections'] })
      toast.success('Added to collection!', { style: { background: '#1e293b', color: '#f1f5f9' } })
    } catch {
      toast.error('Failed to add to collection', { style: { background: '#1e293b', color: '#f1f5f9' } })
    } finally {
      setAdding(null)
    }
  }

  const handleRemove = async (collectionId: string) => {
    setAdding(collectionId)
    try {
      await api.delete(`/collections/${collectionId}/bookmarks/`, { data: { bookmark_id: bookmark.id } })
      setAdded(prev => { const s = new Set(prev); s.delete(collectionId); return s })
      queryClient.invalidateQueries({ queryKey: ['collections'] })
      toast.success('Removed from collection', { style: { background: '#1e293b', color: '#f1f5f9' } })
    } catch {
      toast.error('Failed to remove', { style: { background: '#1e293b', color: '#f1f5f9' } })
    } finally {
      setAdding(null)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl w-full max-w-sm shadow-2xl overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-700">
          <div className="flex items-center gap-2 min-w-0">
            <FolderCheck size={16} className="text-indigo-600 dark:text-indigo-400 shrink-0" />
            <div className="min-w-0">
              <p className="text-sm font-bold text-slate-800 dark:text-white">Add to Collection</p>
              <p className="text-xs text-slate-500 truncate">{bookmark.content_object_title || 'Untitled'}</p>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-white transition-colors shrink-0 ml-2">
            <X size={18} />
          </button>
        </div>

        {/* Collection list */}
        <div className="p-3 max-h-72 overflow-y-auto space-y-1.5">
          {isLoading ? (
            <div className="flex justify-center py-6"><Loader2 size={20} className="animate-spin text-indigo-600 dark:text-indigo-400" /></div>
          ) : collections.length === 0 ? (
            <div className="text-center py-8 text-slate-500 text-sm">
              <FolderOpen size={32} className="mx-auto mb-2 opacity-40" />
              No collections yet. Create one first.
            </div>
          ) : (
            collections.map((col: any) => {
              const isAdded = added.has(col.id)
              const isLoading = adding === col.id
              return (
                <button
                  key={col.id}
                  onClick={() => isAdded ? handleRemove(col.id) : handleAdd(col.id)}
                  disabled={isLoading}
                  className={cn(
                    'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition-all',
                    isAdded
                      ? 'bg-indigo-50 dark:bg-indigo-600/20 border border-indigo-300 dark:border-indigo-500/40 text-indigo-600 dark:text-indigo-300'
                      : 'bg-slate-50 dark:bg-slate-700/50 border border-slate-200 dark:border-transparent hover:border-slate-300 dark:hover:border-slate-600 text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white'
                  )}
                >
                  {isLoading
                    ? <Loader2 size={15} className="animate-spin shrink-0" />
                    : isAdded
                    ? <Check size={15} className="text-indigo-600 dark:text-indigo-400 shrink-0" />
                    : <FolderPlus size={15} className="text-slate-500 shrink-0" />
                  }
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold truncate">{col.name}</p>
                    <p className="text-xs text-slate-500">{col.bookmark_count} items</p>
                  </div>
                  {col.is_public
                    ? <Globe size={12} className="text-slate-600 shrink-0" />
                    : <Lock size={12} className="text-slate-600 shrink-0" />
                  }
                </button>
              )
            })
          )}
        </div>

        <div className="px-4 pb-4">
          <p className="text-xs text-slate-600 text-center">Click a collection to add or remove this bookmark</p>
        </div>
      </motion.div>
    </div>
  )
}

// ── CollectionDetailView ──────────────────────────────────────────────────────

function CollectionDetailView({ collection, onBack }: { collection: any; onBack: () => void }) {
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['collection-detail', collection.id],
    queryFn: () => api.get(`/collections/${collection.id}/`).then(r => r.data),
    staleTime: 30_000,
  })

  const detail = data?.data ?? data
  const bookmarks: any[] = detail?.bookmarks ?? []

  const { mutate: removeFromCollection } = useMutation({
    mutationFn: (bookmarkId: string) =>
      api.delete(`/collections/${collection.id}/bookmarks/`, { data: { bookmark_id: bookmarkId } }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['collection-detail', collection.id] })
      queryClient.invalidateQueries({ queryKey: ['collections'] })
      toast.success('Removed from collection', { style: { background: '#1e293b', color: '#f1f5f9' } })
    },
    onError: () => toast.error('Failed to remove'),
  })

  const getTypeIcon = (type: string) => {
    if (type === 'article') return '📰'
    if (type === 'repository') return '🐙'
    if (type === 'researchpaper') return '📄'
    if (type === 'tweet') return '🐦'
    return '📌'
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className="space-y-4 sm:space-y-5"
    >
      {/* Back + header */}
      <div className="flex items-center gap-3">
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-white transition-colors text-sm font-medium"
        >
          <ArrowLeft size={16} /> Back
        </button>
        <span className="text-slate-600">/</span>
        <div className="flex items-center gap-2 min-w-0">
          <FolderOpen size={18} className="text-indigo-600 dark:text-indigo-400 shrink-0" />
          <h2 className="text-base sm:text-lg font-bold text-slate-800 dark:text-white truncate">{collection.name}</h2>
          {collection.is_public
            ? <span className="flex items-center gap-1 text-xs text-cyan-400 bg-cyan-900/30 border border-cyan-700/30 px-2 py-0.5 rounded-full shrink-0"><Globe size={10} />Public</span>
            : <span className="flex items-center gap-1 text-xs text-slate-500 bg-slate-100 dark:bg-slate-800 border border-slate-700 px-2 py-0.5 rounded-full shrink-0"><Lock size={10} />Private</span>
          }
        </div>
      </div>

      {collection.description && (
        <p className="text-sm text-slate-400 leading-relaxed">{collection.description}</p>
      )}

      {/* Bookmark count */}
      <div className="flex items-center gap-2 text-xs text-slate-500">
        <BookMarked size={13} className="text-rose-600 dark:text-rose-400" />
        <span><strong className="text-slate-600 dark:text-slate-300">{bookmarks.length}</strong> bookmark{bookmarks.length !== 1 ? 's' : ''} in this collection</span>
      </div>

      {/* Bookmark list */}
      {isLoading ? (
        <div className="flex justify-center py-12"><Loader2 size={24} className="animate-spin text-indigo-600 dark:text-indigo-400" /></div>
      ) : bookmarks.length === 0 ? (
        <div className="text-center py-16 bg-slate-100 dark:bg-slate-800/50 rounded-2xl border border-slate-200 dark:border-slate-700/50">
          <FolderOpen size={36} className="mx-auto text-slate-600 mb-3" />
          <p className="text-slate-400 text-sm font-medium">This collection is empty</p>
          <p className="text-slate-600 text-xs mt-1">Go to a bookmark and click the folder icon to add it here</p>
        </div>
      ) : (
        <div className="space-y-2.5">
          <AnimatePresence>
            {bookmarks.map((bookmark: any) => (
              <motion.div
                key={bookmark.id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, x: 20 }}
                className="flex items-center gap-3 p-3 sm:p-4 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl hover:border-slate-600 transition-all group"
              >
                <div className="text-lg shrink-0">{getTypeIcon(bookmark.content_type_name)}</div>
                <div className="flex-1 min-w-0">
                  <a
                    href={bookmark.content_object_url || '#'}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-semibold text-sm text-slate-800 dark:text-white hover:text-indigo-300 transition-colors truncate block"
                  >
                    {bookmark.content_object_title || 'Untitled'}
                  </a>
                  <p className="text-xs text-slate-500 mt-0.5 capitalize">{bookmark.content_type_name}</p>
                </div>
                <button
                  onClick={() => removeFromCollection(bookmark.id)}
                  className="opacity-0 group-hover:opacity-100 p-1.5 text-slate-500 hover:text-red-400 transition-all rounded-lg hover:bg-red-500/10 shrink-0"
                  title="Remove from collection"
                >
                  <X size={14} />
                </button>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
    </motion.div>
  )
}

// ── NewCollectionModal ────────────────────────────────────────────────────────

function NewCollectionModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [isPublic, setIsPublic] = useState(false)

  const { mutate, isPending } = useMutation({
    mutationFn: () =>
      api.post('/collections/', { name, description, is_public: isPublic }).then(r => r.data),
    onSuccess: () => {
      toast.success('Collection created!', { style: { background: '#1e293b', color: '#f1f5f9' } })
      onCreated()
      onClose()
    },
    onError: () => {
      toast.error('Failed to create collection', { style: { background: '#1e293b', color: '#f1f5f9' } })
    },
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-6 w-full max-w-md mx-4"
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-slate-800 dark:text-white">New Collection</h2>
          <button onClick={onClose} className="text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-white"><X size={20} /></button>
        </div>
        <div className="space-y-4">
          <div>
            <label className="text-sm text-slate-400 mb-1 block">Name *</label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g. AI Papers, Rust Resources..."
              className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="text-sm text-slate-400 mb-1 block">Description</label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="What's this collection about?"
              rows={2}
              className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
            />
          </div>
          <label className="flex items-center gap-3 cursor-pointer">
            <div
              onClick={() => setIsPublic(!isPublic)}
              className={cn(
                'w-10 h-5 rounded-full transition-colors relative',
                isPublic ? 'bg-indigo-600' : 'bg-slate-300 dark:bg-slate-700'
              )}
            >
              <div className={cn(
                'absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform',
                isPublic ? 'translate-x-5' : 'translate-x-0.5'
              )} />
            </div>
            <span className="text-sm text-slate-600 dark:text-slate-300">Make public</span>
          </label>
        </div>
        <div className="flex gap-3 mt-6">
          <button onClick={onClose} className="flex-1 px-4 py-2 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-600 dark:text-slate-400 hover:text-slate-800 dark:hover:text-white transition-colors text-sm">
            Cancel
          </button>
          <button
            onClick={() => mutate()}
            disabled={!name.trim() || isPending}
            className="flex-1 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 rounded-lg text-white transition-colors text-sm font-medium"
          >
            {isPending ? 'Creating...' : 'Create'}
          </button>
        </div>
      </motion.div>
    </div>
  )
}

export default function LibraryPage() {
  const [activeTab, setActiveTab] = useState<ContentTab>('all')
  const [showNewCollection, setShowNewCollection] = useState(false)
  const [selectedCollection, setSelectedCollection] = useState<any | null>(null)
  const [addToCollectionBookmark, setAddToCollectionBookmark] = useState<any | null>(null)
  const queryClient = useQueryClient()

  const { data: bookmarksData, isLoading: bookmarksLoading } = useQuery({
    queryKey: ['bookmarks', activeTab],
    queryFn: () =>
      api.get('/bookmarks/', {
        params: activeTab !== 'all' ? { type: activeTab } : {},
      }).then(r => r.data),
  })

  const { data: collectionsData, isLoading: collectionsLoading } = useQuery({
    queryKey: ['collections'],
    queryFn: () => api.get('/collections/').then(r => r.data),
  })

  const { mutate: deleteBookmark } = useMutation({
    mutationFn: (bookmark: any) =>
      api.post(`/bookmarks/${bookmark.content_type_name}/${bookmark.object_id}/`).then(r => r.data),
    onSuccess: () => {
      toast.success('Bookmark removed', { style: { background: '#1e293b', color: '#f1f5f9' } })
      queryClient.invalidateQueries({ queryKey: ['bookmarks'] })
    },
  })

  const { mutate: deleteCollection } = useMutation({
    mutationFn: (id: string) => api.delete(`/collections/${id}/`).then(r => r.data),
    onSuccess: () => {
      toast.success('Collection deleted', { style: { background: '#1e293b', color: '#f1f5f9' } })
      queryClient.invalidateQueries({ queryKey: ['collections'] })
    },
  })

  const bookmarks = bookmarksData?.data || []
  const collections = collectionsData?.data || []

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'article': return <FileText size={14} className="text-indigo-600 dark:text-indigo-400" />
      case 'repository': return <GitBranch size={14} className="text-emerald-600 dark:text-emerald-400" />
      case 'researchpaper': return <BookOpen size={14} className="text-violet-600 dark:text-violet-400" />
      case 'tweet': return <Twitter size={14} className="text-sky-500 dark:text-sky-400" />
      default: return <BookMarked size={14} className="text-slate-500 dark:text-slate-400" />
    }
  }

  const getTypeBadge = (type: string) => {
    const styles: Record<string, string> = {
      article: 'bg-indigo-100 dark:bg-indigo-900/50 text-indigo-600 dark:text-indigo-300',
      repository: 'bg-emerald-100 dark:bg-emerald-900/50 text-emerald-600 dark:text-emerald-300',
      researchpaper: 'bg-violet-100 dark:bg-violet-900/50 text-violet-600 dark:text-violet-300',
      tweet: 'bg-sky-100 dark:bg-sky-900/50 text-sky-600 dark:text-sky-300',
    }
    const labels: Record<string, string> = {
      article: 'Article',
      repository: 'Repo',
      tweet: 'Tweet',
      researchpaper: 'Paper',
    }
    return (
      <span className={cn('text-xs px-2 py-0.5 rounded-full font-medium', styles[type] || 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300')}>
        {labels[type] || type}
      </span>
    )
  }

  // If a collection is selected, show its detail view
  if (selectedCollection) {
    return (
      <div className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="max-w-3xl mx-auto pb-8">
          <CollectionDetailView
            collection={selectedCollection}
            onBack={() => setSelectedCollection(null)}
          />
        </div>
        <AnimatePresence>
          {addToCollectionBookmark && (
            <AddToCollectionModal
              bookmark={addToCollectionBookmark}
              onClose={() => setAddToCollectionBookmark(null)}
            />
          )}
        </AnimatePresence>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 sm:p-6">
    <div className="space-y-6 sm:space-y-8 pb-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-white truncate">Knowledge Library</h1>
          <p className="text-slate-400 mt-1 text-xs sm:text-sm">Your saved articles, repos, and papers</p>
        </div>
        <div className="flex flex-wrap items-center gap-2 shrink-0">
          <ShareDigest articles={bookmarks.map((b: any) => ({ id: String(b.object_id || ''), title: b.content_title || b.title || 'Untitled', url: b.content_url || b.url || '#', summary: b.content_summary || b.summary || '' }))} label="Share" />
          <NotionExport articles={bookmarks.map((b: any) => ({ id: String(b.object_id || ''), title: b.content_title || b.title || 'Untitled', url: b.content_url || b.url || '#', summary: b.content_summary || b.summary || '', tags: b.tags || [] }))} label="Export" />
          <button
            onClick={() => setShowNewCollection(true)}
            className="flex items-center gap-2 px-3 sm:px-4 py-2 bg-indigo-600 hover:bg-indigo-700 rounded-xl text-white text-xs sm:text-sm font-semibold transition-colors"
          >
            <FolderPlus size={14} />
            <span>New Collection</span>
          </button>
        </div>
      </div>

      {/* Collections */}
      <section>
        <h2 className="text-lg font-semibold text-slate-800 dark:text-white mb-4 flex items-center gap-2">
          <FolderPlus size={18} className="text-cyan-600 dark:text-cyan-400" />
          Collections
          <span className="text-sm text-slate-500 font-normal">({collections.length})</span>
        </h2>
        {collectionsLoading ? (
          <div className="flex justify-center py-8"><Loader2 className="animate-spin text-indigo-600 dark:text-indigo-400" /></div>
        ) : collections.length === 0 ? (
          <div className="text-center py-10 bg-slate-100 dark:bg-slate-800/50 rounded-xl border border-slate-200 dark:border-slate-700/50">
            <FolderPlus size={32} className="mx-auto text-slate-600 mb-3" />
            <p className="text-slate-500 dark:text-slate-400">No collections yet</p>
            <button
              onClick={() => setShowNewCollection(true)}
              className="mt-3 text-sm text-indigo-600 dark:text-indigo-400 hover:text-indigo-600 dark:hover:text-indigo-300 flex items-center gap-1 mx-auto"
            >
              <Plus size={14} /> Create your first collection
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
            <AnimatePresence>
              {collections.map((col: any) => (
                <motion.div
                  key={col.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  className="group relative bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl p-4 hover:border-indigo-500/50 hover:shadow-lg hover:shadow-indigo-500/5 transition-all duration-200 overflow-hidden cursor-pointer"
                  onClick={() => setSelectedCollection(col)}
                >
                  <div className="absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r from-indigo-500 to-violet-500 opacity-0 group-hover:opacity-100 transition-opacity rounded-t-2xl" />
                  <div className="flex items-start justify-between mb-2 gap-2">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-slate-800 dark:text-white truncate text-sm sm:text-base">{col.name}</h3>
                      {col.description && (
                        <p className="text-xs text-slate-400 mt-0.5 line-clamp-2 leading-relaxed">{col.description}</p>
                      )}
                    </div>
                    <button
                      onClick={e => { e.stopPropagation(); deleteCollection(col.id) }}
                      className="opacity-0 group-hover:opacity-100 p-1 text-slate-500 hover:text-red-400 transition-all ml-1 shrink-0"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                  <div className="flex items-center justify-between mt-3 flex-wrap gap-1">
                    <span className="text-xs text-slate-500">{col.bookmark_count ?? 0} items</span>
                    <div className="flex items-center gap-2">
                      {col.is_public && (
                        <span className="flex items-center gap-1 text-xs bg-cyan-900/40 text-cyan-400 px-2 py-0.5 rounded-full border border-cyan-700/30 whitespace-nowrap">
                          <Globe size={9} /> Public
                        </span>
                      )}
                      <span className="flex items-center gap-1 text-xs text-slate-500 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors whitespace-nowrap">
                        Open <ChevronRight size={12} />
                      </span>
                    </div>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
            {/* Add new collection card */}
            <button
              onClick={() => setShowNewCollection(true)}
              className="border-2 border-dashed border-slate-300 dark:border-slate-700 hover:border-indigo-500 rounded-2xl p-4 flex flex-col items-center justify-center gap-2 text-slate-500 hover:text-indigo-500 dark:hover:text-indigo-400 transition-all min-h-[90px] sm:min-h-[100px]"
            >
              <Plus size={18} />
              <span className="text-xs sm:text-sm font-medium">New Collection</span>
            </button>
          </div>
        )}
      </section>

      {/* Smart Collections */}
      <section>
        <SmartCollections />
      </section>

      {/* Bookmarks */}
      <section>
        <div className="flex flex-col xs:flex-row xs:items-center justify-between mb-4 gap-3">
          <h2 className="text-base sm:text-lg font-semibold text-slate-800 dark:text-white flex items-center gap-2 shrink-0">
            <BookMarked size={17} className="text-rose-600 dark:text-rose-400" />
            Bookmarks
            <span className="text-xs sm:text-sm text-slate-500 font-normal">({bookmarks.length})</span>
          </h2>
          {/* Type filter tabs — scrollable on small screens */}
          <div className="flex gap-1 bg-slate-100 dark:bg-slate-800 rounded-xl p-1 overflow-x-auto scrollbar-hide">
            {contentTabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'flex items-center gap-1 sm:gap-1.5 px-2 sm:px-2.5 py-1 rounded-lg text-xs font-semibold transition-colors whitespace-nowrap shrink-0',
                  activeTab === tab.id ? 'bg-indigo-600 text-white' : 'text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-white'
                )}
              >
                <tab.icon size={11} />
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {bookmarksLoading ? (
          <div className="flex justify-center py-8"><Loader2 className="animate-spin text-indigo-600 dark:text-indigo-400" /></div>
        ) : bookmarks.length === 0 ? (
          <div className="text-center py-16 bg-slate-100 dark:bg-slate-800/50 rounded-xl border border-slate-200 dark:border-slate-700/50 flex flex-col items-center gap-3 px-6">
            <div className="w-16 h-16 rounded-2xl bg-rose-100 dark:bg-rose-900/30 flex items-center justify-center">
              <BookMarked size={28} className="text-rose-400" />
            </div>
            <div>
              <p className="text-slate-800 dark:text-slate-200 font-semibold text-lg">
                {activeTab === 'all' ? 'No bookmarks yet' : `No ${activeTab} bookmarks`}
              </p>
              <p className="text-slate-500 dark:text-slate-400 text-sm mt-1 max-w-xs mx-auto">
                {activeTab === 'all'
                  ? 'Click the bookmark icon ♡ on any article, paper, repo, or tweet to save it here.'
                  : `No ${activeTab}s saved yet. Browse and bookmark ${activeTab}s to see them here.`}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2 justify-center">
              <a
                href="/feed"
                className="px-4 py-2 rounded-xl text-sm font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition-colors"
              >
                Browse articles
              </a>
              <a
                href="/wizard"
                className="px-4 py-2 rounded-xl text-sm font-semibold border border-indigo-300 dark:border-indigo-700 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-900/20 transition-colors"
              >
                ✨ Personalise your feed
              </a>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <AnimatePresence>
              {bookmarks.map((bookmark: any) => (
                <motion.div
                  key={bookmark.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 10 }}
                  className="flex items-center gap-3 sm:gap-4 p-3 sm:p-4 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl hover:border-slate-600 hover:shadow-md transition-all duration-200 group overflow-hidden"
                >
                  <div className="flex-shrink-0 text-lg sm:text-xl">{getTypeIcon(bookmark.content_type_name)}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 sm:gap-2 mb-1 flex-wrap">
                      {getTypeBadge(bookmark.content_type_name)}
                      <span className="text-xs text-slate-500 whitespace-nowrap">
                        {new Date(bookmark.created_at).toLocaleDateString()}
                      </span>
                    </div>
                    <a
                      href={bookmark.content_object_url || '#'}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-semibold text-sm text-slate-800 dark:text-white hover:text-indigo-600 dark:hover:text-indigo-300 transition-colors truncate block"
                    >
                      {bookmark.content_object_title || 'Untitled'}
                    </a>
                    <InlineNoteEditor
                      bookmark={bookmark}
                      onSaved={(notes) => {
                        // Optimistically update bookmark in cache
                        queryClient.setQueryData(['bookmarks', activeTab], (old: any) => {
                          const list: any[] = old?.data ?? old?.results ?? []
                          const updated = list.map((b: any) => b.id === bookmark.id ? { ...b, notes } : b)
                          if (old?.data) return { ...old, data: updated }
                          if (old?.results) return { ...old, results: updated }
                          return updated
                        })
                      }}
                    />
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    {/* Add to collection button */}
                    <button
                      onClick={() => setAddToCollectionBookmark(bookmark)}
                      className="opacity-0 group-hover:opacity-100 p-1.5 text-slate-500 hover:text-indigo-400 transition-all rounded-lg hover:bg-indigo-500/10"
                      title="Add to collection"
                    >
                      <FolderPlus size={14} />
                    </button>
                    <button
                      onClick={() => deleteBookmark(bookmark)}
                      className="opacity-0 group-hover:opacity-100 p-1.5 sm:p-2 text-slate-500 hover:text-red-400 transition-all rounded-lg hover:bg-red-500/10"
                      title="Remove bookmark"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}
      </section>

      {/* New Collection Modal */}
      <AnimatePresence>
        {showNewCollection && (
          <NewCollectionModal
            onClose={() => setShowNewCollection(false)}
            onCreated={() => queryClient.invalidateQueries({ queryKey: ['collections'] })}
          />
        )}
      </AnimatePresence>

      {/* Add to Collection Modal */}
      <AnimatePresence>
        {addToCollectionBookmark && (
          <AddToCollectionModal
            bookmark={addToCollectionBookmark}
            onClose={() => setAddToCollectionBookmark(null)}
          />
        )}
      </AnimatePresence>
    </div>
    </div>
  )
}
