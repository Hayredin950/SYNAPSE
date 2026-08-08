'use client'

/**
 * Feature #26: Notion/Obsidian Export
 * Export reading list / highlights as markdown files.
 */

import React, { useState } from 'react'
import { FileText, Download, Check, Loader2 } from 'lucide-react'
import { api } from '@/utils/api'
import toast from 'react-hot-toast'

interface Article {
  id:      string
  title:   string
  url:     string
  summary?: string
  tags?:   string[]
  scraped_at?: string
}

interface Props {
  articles: Article[]
  label?:  string
  variant?: 'notion' | 'obsidian' | 'markdown'
}

function toMarkdown(articles: Article[], variant: 'notion' | 'obsidian' | 'markdown'): string {
  const date = new Date().toLocaleDateString('en', { year: 'numeric', month: 'long', day: 'numeric' })

  if (variant === 'obsidian') {
    return [
      `---`,
      `tags: [synapse, reading-list]`,
      `created: ${new Date().toISOString().slice(0, 10)}`,
      `---`,
      ``,
      `# SYNAPSE Reading List — ${date}`,
      ``,
      ...articles.map(a => [
        `## ${a.title}`,
        ``,
        `- **URL:** ${a.url}`,
        a.scraped_at ? `- **Saved:** ${new Date(a.scraped_at).toLocaleDateString()}` : '',
        a.tags?.length ? `- **Tags:** ${a.tags.map(t => `#${t}`).join(' ')}` : '',
        ``,
        a.summary || '_No summary available_',
        ``,
        `---`,
        ``,
      ].filter(Boolean).join('\n')),
    ].join('\n')
  }

  if (variant === 'notion') {
    return [
      `# SYNAPSE Reading List — ${date}`,
      ``,
      `> Exported from SYNAPSE · ${articles.length} articles`,
      ``,
      ...articles.map((a, i) => [
        `${i + 1}. **[${a.title}](${a.url})**`,
        a.tags?.length ? `   Tags: ${a.tags.join(', ')}` : '',
        a.summary ? `   > ${a.summary.slice(0, 200)}…` : '',
        ``,
      ].filter(Boolean).join('\n')),
    ].join('\n')
  }

  // plain markdown
  return [
    `# Reading List — ${date}`,
    ``,
    ...articles.map(a => `- [${a.title}](${a.url})${a.summary ? ' — ' + a.summary.slice(0, 100) + '…' : ''}`),
  ].join('\n')
}

export function NotionExport({ articles, label, variant = 'markdown' }: Props) {
  const [loading, setLoading] = useState(false)
  const [done,    setDone]    = useState(false)

  const handleExport = async () => {
    if (!articles.length) { toast.error('No articles to export'); return }
    setLoading(true)
    try {
      const content = toMarkdown(articles, variant)
      const blob = new Blob([content], { type: 'text/markdown' })
      const url  = URL.createObjectURL(blob)
      const a    = document.createElement('a')
      a.href     = url
      a.download = `synapse-${variant}-${new Date().toISOString().slice(0, 10)}.md`
      a.click()
      URL.revokeObjectURL(url)
      setDone(true)
      setTimeout(() => setDone(false), 2500)
      toast.success(`Exported as ${variant === 'notion' ? 'Notion' : variant === 'obsidian' ? 'Obsidian' : 'Markdown'}!`)
    } finally {
      setLoading(false)
    }
  }

  const icons = { notion: '📝', obsidian: '🔮', markdown: '📄' }

  return (
    <button
      onClick={handleExport}
      disabled={loading || !articles.length}
      className="flex items-center gap-2 px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm text-slate-600 dark:text-slate-300 hover:border-indigo-400 disabled:opacity-50 transition-colors"
      title={`Export as ${variant}`}
    >
      {loading ? <Loader2 size={14} className="animate-spin" />
       : done    ? <Check size={14} className="text-emerald-500" />
                : <Download size={14} />}
      <span>{label || `${icons[variant]} Export ${variant === 'notion' ? 'to Notion' : variant === 'obsidian' ? 'to Obsidian' : 'Markdown'}`}</span>
    </button>
  )
}
