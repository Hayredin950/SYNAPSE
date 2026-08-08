import { formatDistanceToNow } from 'date-fns'
import clsx from 'clsx'
import { twMerge } from 'tailwind-merge'

export function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) {
    return 'Unknown'
  }

  try {
    const date = new Date(dateStr)
    const result = formatDistanceToNow(date, { addSuffix: true })
    // Shorten common time phrases to save space
    return result
      .replace(/less than a minute ago/, '<1 min ago')
      .replace(/(\d+) minutes? ago/, '$1 min ago')
      .replace(/(\d+) hours? ago/, '$1 hr ago')
      .replace(/(\d+) days? ago/, '$1 d ago')
      .replace(/(\d+) months? ago/, '$1 mo ago')
      .replace(/(\d+) years? ago/, '$1 yr ago')
      .replace(/about /, '')
      .replace(/almost /, '')
      .replace(/over /, '>')
  } catch {
    return 'Unknown'
  }
}

export function formatNumber(n: number | null | undefined): string {
  if (n == null || isNaN(n)) return '0'
  if (n >= 1_000_000) {
    return `${(n / 1_000_000).toFixed(1)}M`
  }
  if (n >= 1_000) {
    return `${(n / 1_000).toFixed(1)}k`
  }
  return n.toString()
}

export function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = seconds % 60

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`
}

export function getDifficultyColor(level: string): string {
  switch (level.toLowerCase()) {
    case 'beginner':
      return 'text-green-600 bg-green-50'
    case 'intermediate':
      return 'text-yellow-600 bg-yellow-50'
    case 'advanced':
      return 'text-red-600 bg-red-50'
    default:
      return 'text-gray-600 bg-gray-50'
  }
}

export function getLanguageColor(language: string): string {
  const colors: Record<string, string> = {
    Python: '#3776AB',
    JavaScript: '#F7DF1E',
    TypeScript: '#3178C6',
    Rust: '#CE422B',
    Go: '#00ADD8',
    Java: '#007396',
    'C++': '#00599C',
    C: '#A8B9CC',
    Ruby: '#CC342D',
    PHP: '#777BB4',
  }

  return colors[language] || '#6366F1'
}

export function cn(...classes: (string | undefined | null | false)[]): string {
  return twMerge(clsx(classes))
}

export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) {
    return text
  }
  return text.slice(0, maxLength) + '...'
}

export function getSourceIcon(sourceType: string): string {
  const icons: Record<string, string> = {
    news: '📰',
    github: '🐙',
    arxiv: '📄',
    youtube: '▶️',
    blog: '✍️',
  }

  return icons[sourceType.toLowerCase()] || '📌'
}
