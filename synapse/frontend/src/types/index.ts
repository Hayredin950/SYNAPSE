// Auth
export interface User {
  id: string
  username: string
  email: string
  first_name: string
  last_name: string
  role: 'user' | 'admin' | 'moderator'
  bio?: string
  avatar_url?: string
  preferences: Record<string, unknown>
  created_at: string       // from UserProfileSerializer
  last_login?: string | null
  // legacy aliases kept for backward compat
  date_joined?: string
  // Onboarding — TASK-001
  is_onboarded: boolean
  onboarded_at?: string | null
  // GitHub OAuth — TASK-002
  github_id?: string | null
  github_username?: string | null
  // Billing plan — TASK-003
  plan?: 'free' | 'pro' | 'enterprise'
}

export interface AuthTokens {
  access: string
  refresh: string
}

export interface LoginCredentials {
  email: string
  password: string
}

export interface RegisterData {
  username: string
  email: string
  password: string
  password2: string
  first_name?: string
  last_name?: string
}

// Article / Source
export interface Source {
  id: string
  name: string
  url: string
  source_type: 'news' | 'github' | 'arxiv' | 'youtube' | 'blog'
}

export interface Article {
  id: string
  title: string
  content?: string
  /** BART-generated abstractive summary (Phase 2.2). Empty string when not yet summarized. */
  summary: string
  url: string
  source: Source | null
  /** Direct source_type string (e.g. 'hackernews', 'blog') — convenience field from API. */
  source_type: string
  author: string
  published_at: string | null
  scraped_at: string
  topic: string
  tags: string[]
  keywords: string[]
  sentiment_score: number | null
  trending_score: number
  view_count: number
  /** True once the full NLP pipeline (keywords + topic + sentiment + summary) has run. */
  nlp_processed: boolean
  metadata?: Record<string, unknown>
  /** Short excerpt fetched from the article URL (populated before AI summary is ready). */
  excerpt?: string
}

// Repository
export interface Repository {
  id: string
  github_id: number
  name: string
  full_name: string
  description: string
  url: string
  clone_url?: string
  stars: number
  forks: number
  watchers: number
  open_issues: number
  language: string
  topics: string[]
  owner: string
  owner_name?: string
  is_trending: boolean
  stars_today: number
  stars_7d_delta: number
  velocity_7d: number
  trend_class: 'rising_star' | 'stable' | 'declining'
  is_rising_star: boolean
  readme_summary?: string
  scraped_at?: string
  repo_created_at: string | null
  metadata: Record<string, unknown>
}

// Research Paper
export interface ResearchPaper {
  id: string
  arxiv_id: string
  title: string
  abstract: string
  summary: string
  authors: string[]
  categories: string[]
  arxiv_categories?: string[]
  published_date: string | null
  url: string
  pdf_url: string
  citation_count: number
  difficulty_level: 'beginner' | 'intermediate' | 'advanced'
  key_contributions: string
  applications: string
  fetched_at: string
}

// Video
export interface Video {
  id: string
  youtube_id: string
  title: string
  description: string
  summary: string
  channel_name: string
  channel_id: string
  url: string
  thumbnail_url: string
  duration_seconds: number
  view_count: number
  like_count: number
  published_at: string | null
  topics: string[]
  fetched_at: string
}

// Tweet (X/Twitter)
export interface Tweet {
  id: string
  tweet_id: string
  text: string
  author_username: string
  author_display_name: string
  author_profile_image: string
  author_verified: boolean
  author_followers: number
  retweet_count: number
  like_count: number
  reply_count: number
  quote_count: number
  view_count: number
  bookmark_count: number
  posted_at: string | null
  scraped_at: string
  hashtags: string[]
  mentions: string[]
  media_urls: string[]
  urls: string[]
  is_retweet: boolean
  is_reply: boolean
  is_quote: boolean
  conversation_id: string
  in_reply_to_user: string
  lang: string
  url: string
  source_label: string
  topic: string
  trending_score: number
  sentiment_score: number | null
  metadata: Record<string, unknown>
}

// Pagination
export interface PaginatedResponse<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

// API Error
export interface ApiError {
  message: string
  errors?: Record<string, string[]>
  status?: number
}

// ─── AI Chat (Phase 3.2) ─────────────────────────────────────────────────────

export interface ChatSource {
  title: string
  url: string
  content_type: 'article' | 'paper' | 'repository' | 'video' | 'tweet' | string
  snippet: string
}

export interface ChatMessageAttachment {
  name: string
  type: string      // MIME type e.g. "image/jpeg"
  preview?: string  // data URL for images
}

export interface ChatMessage {
  id: string
  role: 'human' | 'ai'
  content: string
  ts: number
  sources?: ChatSource[]
  isStreaming?: boolean
  attachments?: ChatMessageAttachment[]
}

export interface Conversation {
  conversation_id: string
  title: string
  message_count: number
  created_at: string
  updated_at: string
}

export interface ChatResponse {
  answer: string
  sources: ChatSource[]
  conversation_id: string
}

export interface ConversationHistory {
  conversation_id: string
  title: string
  messages: Array<{ role: 'human' | 'ai'; content: string; ts: number }>
  created_at: string
  updated_at: string
}

// ─── Agentic AI (Phase 5.1–5.4) ─────────────────────────────────────────────

export type AgentTaskType =
  | 'research'
  | 'trends'
  | 'github'
  | 'arxiv'
  | 'tweets'
  | 'general'
  | 'document'
  | 'project'

export type AgentTaskStatus = 'pending' | 'processing' | 'completed' | 'failed'

export interface AgentIntermediateStep {
  tool: string
  input: string | Record<string, unknown>
  output: string
}

export interface AgentTaskResult {
  answer?: string
  intermediate_steps?: AgentIntermediateStep[]
  tokens_used?: number
  cost_usd?: number
  execution_time_s?: number
  file_path?: string
  file_name?: string
  file_size_bytes?: number
  download_url?: string
  [key: string]: unknown
}

export interface AgentTask {
  id: string
  task_type: AgentTaskType
  prompt: string
  status: AgentTaskStatus
  result: AgentTaskResult
  answer?: string
  intermediate_steps?: AgentIntermediateStep[]
  error_message: string
  tokens_used: number
  cost_usd: string
  execution_time_s?: number
  created_at: string
  completed_at: string | null
}

export interface AgentTool {
  name: string
  description: string
}

export interface AgentTaskCreate {
  task_type: AgentTaskType
  prompt: string
}

// ─── Notifications (Phase 4.2) ───────────────────────────────────────────────

export type NotifType =
  | 'info'
  | 'warning'
  | 'error'
  | 'success'
  | 'workflow_complete'

export interface Notification {
  id: string
  title: string
  message: string
  notif_type: NotifType
  is_read: boolean
  created_at: string
  metadata: Record<string, unknown>
}
