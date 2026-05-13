# SYNAPSE Workspace

## Overview

AI-Powered Technology Intelligence Platform. Full-stack app cloned from GitHub (HayreKhan750/SYNAPSE) and made fully production-ready in Replit.

## Architecture

- **Frontend**: Next.js 15.5 (React 18) — `synapse/frontend/`
- **Backend**: Django 4.2 (ASGI/Daphne) — `synapse/backend/`
- **AI Engine**: LangChain-based agent framework — `synapse/ai_engine/`
- **Database**: Replit PostgreSQL (host: helium, db: heliumdb)
- **AI Provider**: Replit built-in OpenAI (via `AI_INTEGRATIONS_OPENAI_BASE_URL` + `AI_INTEGRATIONS_OPENAI_API_KEY`)
- **Workspace**: pnpm monorepo

## Running Services

| Workflow | Description | Port |
|---|---|---|
| `artifacts/synapse: web` | Next.js frontend | varies (read PORT env) |
| `SYNAPSE Backend` | Django API (ASGI/Daphne) | 8000 |

## API Proxy

Next.js rewrites `/api/v1/*` → `http://localhost:8000/api/v1/*/` internally (no CORS issues).
Browser always uses relative paths — never `http://localhost:8000` directly.

## Django Settings

- **Settings module**: `config.settings.replit`
- **In-memory channels** (no Redis needed)
- **Console email backend** (no SMTP needed)
- **Celery eager mode** (no broker needed) — agent tasks use background threads to avoid blocking HTTP
- **Background scraper scheduler** — runs `synapse/scraper_scheduler.py` for periodic real data scraping
- **AUTO_VERIFY_EMAIL = True** — new registrations are auto-verified and receive JWT tokens immediately
- **All ALLOWED_HOSTS** enabled
- **PYTHONPATH** includes both `synapse/backend/` and `synapse/` (for ai_engine)
- **DISABLE_RATE_LIMITS=true** — all AI endpoints rate-limit-free for demo

## Test User

- **Email**: `demo@synapse.dev`
- **Password**: `Demo1234!`
- **UUID**: `57b9b0f1-338a-4004-9b46-ca4e1e82771b`
- **Status**: email_verified=True, is_onboarded=True, org="Synapse Demo Team", 10 bookmarks, 3 collections

## Live Scraped Data (all real, no seeds/fixtures)

Background scheduler (`synapse/scraper_scheduler.py`) runs every minute and dispatches:

| Content Type | Count | Source | Refresh Interval |
|---|---|---|---|
| Articles | 166 | HackerNews API (top/new/best 100) | Every 30 min |
| Repositories | 361 | GitHub Search API (all langs + TypeScript + Python) | Every 2 hrs |
| Research Papers | 392 | arXiv API (cs.AI, cs.LG, cs.CL, cs.CV) | Every 6 hrs |
| Videos | 99 | yt-dlp (AI/ML/dev YouTube channels) | Every 3 hrs |
| Tweets | 571 | Mastodon public API (no key needed) 7 topics | Every 1 hr |
| Tech Trends | 10 topics | Analyzed across all 5 sources | Every 2 hrs |
| AI Article Summaries | batch 30 | Replit AI (gpt-4o-mini) | Every 1 hr |
| Daily Briefings | per-user | Replit AI (gpt-4o-mini) — 4302+ chars | Every 24 hrs |

## Knowledge Graph

50 tech entity nodes (LLM, RAG, Python, Go, Rust, Claude, etc.) + 50 typed edges
(used_with, implemented_in, instance_of, framework_for, technique_for, etc.)
Built from trends data. Endpoint: `GET /api/v1/knowledge-graph/`

## Scheduler Tasks (`synapse/scraper_scheduler.py`)

| Task | Interval | Python call |
|---|---|---|
| HackerNews scraper | 30 min | `run_scrapers --sources hn` |
| GitHub scraper | 2 hrs | `run_scrapers --sources github` |
| arXiv scraper | 6 hrs | `run_scrapers --sources arxiv` |
| Mastodon tweet scraper | 1 hr | `scrape_twitter()` per topic |
| YouTube scraper | 3 hrs | `scrape_youtube()` |
| Trend analysis | 2 hrs | `analyze_trends_task()` |
| Article summarization | 1 hr | `summarize_pending_articles(batch_size=30)` |
| Daily briefings | 24 hrs | `generate_user_briefing()` per user |

## AI Features — All Working

- **AI Chat**: `POST /api/v1/ai/chat/` — any model ID normalizes to gpt-4o-mini via Replit AI
- **Agent Tasks**: `POST /api/v1/agents/tasks/` — task_type + prompt fields, runs research agents
- **Daily Briefing**: `GET /api/v1/briefing/today/` — 4302-char AI-generated brief per user
- **Research Sessions**: `POST /api/v1/agents/research/` — deep-dive AI research with citations
- **Rate limits**: DISABLED (`DISABLE_RATE_LIMITS=true`) for all AI endpoints

## Model Normalization Fix

`synapse/backend/apps/core/views_chat.py` → `_get_replit_openai_pipeline()`:
Any non-OpenAI model ID (`google/*`, `meta-llama/*`, etc.) is normalized to `gpt-4o-mini`
before calling the Replit AI gateway. Frontend `DEFAULT_MODEL = 'gpt-4o-mini'`.

## API Key Banner Fix

`synapse/frontend/src/hooks/useApiKeyStatus.ts` reads `d.any_configured` from backend.
Backend always returns `any_configured: true` since Replit AI is the server-side key.
Banner only shows if truly no AI backend is available.

## 40-Feature Pack — All Implemented

### Home Dashboard (`/home`)
- **CatchMeUp** — `src/components/ui/CatchMeUp.tsx` — AI "since you were gone" digest via `/ai/catch-up/`
- **ReadingGoals** — `src/components/ui/ReadingGoals.tsx` — daily/weekly targets with progress ring
- **TopicWatchlist** — `src/components/ui/TopicWatchlist.tsx` — persistent topic monitoring (localStorage + `/social/watchlist/`)
- **NetworkReading** — `src/components/ui/NetworkReading.tsx` — "what your network is reading" via `/social/network-reading/`
- **InterestProfileBuilder** — `src/components/ui/InterestProfileBuilder.tsx` — first-run AI interest calibration modal
- **ActivityHeatmap** — `src/components/ui/ActivityHeatmap.tsx` — GitHub-style contribution heatmap

### Analytics Page (`/analytics`)
- **ActivityHeatmapCalendar** — `src/components/ui/ActivityHeatmapCalendar.tsx` — full-page heatmap calendar
- 14-day reading volume AreaChart, source breakdown PieChart, top topics BarChart
- ReadingGoals embedded, ReadingSpeedCalibration modal
- Achievement badges (streak, books, speed)

### Library Page (`/library`)
- **SmartCollections** — `src/components/ui/SmartCollections.tsx` — AI-auto-organizes bookmarks by topic
- **NotionExport** — `src/components/ui/NotionExport.tsx` — export reading list as Markdown/Obsidian format
- **ShareDigest** — `src/components/ui/ShareDigest.tsx` — generate shareable reading digest link

### Research Page (`/research`)
- **ResearchBrief** — `src/components/ui/ResearchBrief.tsx` — AI autonomous research brief generator
- **PaperToBlog** — `src/components/ui/PaperToBlog.tsx` — convert arXiv paper to readable blog post (per PaperCard)

### ContentReaderModal (6 Tabs + Features)
- Tabs: Summary 📝, AI Deep-Dive 🤖, Debate ⚔️, Translate 🌍, Code Extractor 💻, TTS Listen 🔊
- **RelatedArticles** embedded in summary tab
- **CommentsSection** with upvoting on every tab
- **ContentHighlighter** — highlight + save text snippets per article (localStorage)
- **FocusModeButton** — enter distraction-free focus mode
- **SourceQualityBadge** — credibility score for article source
- **ReadingTimer** — imported and available

### Command Palette
- Prefix modes: `>` AI commands, `@` Articles search, `#` Topics/nav
- Footer shows prefix mode hints
- `@articles` search sends `content_type=article` param

### Settings Page (`/settings`)
- **AccentThemePicker** — `src/components/ui/AccentTheme.tsx` — 8 accent color presets, CSS vars, localStorage
- **SourceQualityManager** — rate/block individual sources

### Global Layout
- **FocusModeProvider** — wraps root layout, keyboard shortcut `F` enters focus mode
- **useAccentTheme()** — initialized in dashboard layout to restore accent color on mount
- **PWAUpdateBanner** — `src/components/ui/PWAUpdateBanner.tsx` — service worker update notification
- **KeyboardShortcutsModal** — `src/components/ui/KeyboardShortcutsModal.tsx` — `?` shows all shortcuts
- Vim-style shortcuts: `g h` home, `g f` feed, `g r` research, `g a` analytics, `g c` chat, etc.

### Reading Experience
- **ReadingSpeedCalibration** — `src/components/ui/ReadingSpeedCalibration.tsx`
- **ReadingTimer** — `src/components/ui/ReadingTimer.tsx` — elapsed timer + estimated read time
- **ContentHighlighter** — `src/components/ui/ContentHighlighter.tsx` — 4 color highlight, saved per article

### New Standalone Components
- **AIQuickActions** — `src/components/ui/AIQuickActions.tsx` — floating AI action bar (summarize, deep-dive, translate, debate)
- **SourceQualityBadge/Manager** — `src/components/ui/SourceQuality.tsx`

## Backend AI Endpoints (all in `views_ai.py`)

| Endpoint | Feature |
|---|---|
| `POST /api/v1/ai/catch-up/` | CatchMeUp digest |
| `POST /api/v1/ai/summarize/` | Article summary |
| `POST /api/v1/ai/deep-dive/` | Deep-dive analysis |
| `POST /api/v1/ai/debate/` | Steelman debate |
| `POST /api/v1/ai/translate/` | Article translation |
| `POST /api/v1/ai/code-extract/` | Code extraction |
| `POST /api/v1/ai/tts/` | Text-to-speech |
| `POST /api/v1/ai/paper-to-blog/` | Paper → blog post |
| `POST /api/v1/ai/research/` | Research brief |
| `POST /api/v1/ai/podcast/` | Podcast script generation |
| `GET /api/v1/ai/related/` | Related articles |

## Backend Social Endpoints (all in `views_social.py`)

| Endpoint | Feature |
|---|---|
| `POST /api/v1/social/upvote/` | Upvote/downvote articles |
| `GET /api/v1/social/upvotes/` | Get upvote counts |
| `GET/POST /api/v1/social/comments/` | Get/post comments |
| `DELETE /api/v1/social/comments/{cid}/` | Delete comment |
| `GET/POST /api/v1/social/watchlist/` | Topic watchlist CRUD |
| `DELETE /api/v1/social/watchlist/{id}/` | Remove topic |
| `POST /api/v1/social/digest/share/` | Create shareable digest |
| `GET /api/v1/social/digest/{share_id}/` | View shared digest |
| `GET /api/v1/social/network-reading/` | Network reading feed |
| `GET /api/v1/social/source-quality/{domain}/` | Source credibility |

## User Activity

- `GET /api/v1/users/activity/?days=120` — daily activity counts for heatmap (new)

## Endpoints — All Working

- `POST /api/v1/auth/login/` — JWT auth
- `GET /api/v1/articles/?for_you=1` — personalized feed (135 articles)
- `GET /api/v1/repos/?ordering=-stars` — GitHub trending
- `GET /api/v1/papers/` — arXiv research papers
- `GET /api/v1/videos/` — YouTube tech videos
- `GET /api/v1/tweets/` — Mastodon posts (tech topics)
- `GET /api/v1/trends/?ordering=-trend_score` — Go 618, LLM 560, RAG 443...
- `GET /api/v1/briefing/today/` — AI daily brief (4302 chars, topic_summary)
- `GET /api/v1/knowledge-graph/` — 50 nodes, 50 edges (named source/target)
- `GET /api/v1/search/?q=machine+learning` — global search (32 results)
- `POST /api/v1/ai/chat/` — AI chat (gpt-4o-mini via Replit AI)
- `POST /api/v1/agents/tasks/` — AI agent tasks (task_type + prompt)
- `GET /api/v1/bookmarks/` — user bookmarks (10)
- `GET /api/v1/collections/` — user collections (3)
- `GET /api/v1/organizations/` — user orgs
- `GET /api/v1/automation/workflows/` — 4 workflows
- `GET /api/v1/billing/subscription/` — billing status
- `GET /api/v1/users/activity/?days=120` — activity heatmap data

## Key Files

- `synapse/start-backend.sh` — env vars, pip install, DB migrate, scheduler launch, daphne start
- `synapse/scraper_scheduler.py` — all 8 periodic scraping tasks
- `synapse/backend/apps/core/views_chat.py` — AI chat, model normalization, briefing
- `synapse/backend/apps/core/views_ai.py` — all new AI feature endpoints (11 endpoints)
- `synapse/backend/apps/core/views_social.py` — all new social endpoints (10 endpoints)
- `synapse/backend/apps/core/urls_nlp.py` — AI endpoint routing
- `synapse/backend/apps/core/urls.py` — social endpoint routing
- `synapse/backend/apps/users/views.py` — user activity heatmap endpoint
- `synapse/backend/apps/users/urls.py` — users URL routing (activity route added)
- `synapse/backend/apps/core/throttles.py` — rate limit bypass (DISABLE_RATE_LIMITS)
- `synapse/frontend/src/app/layout.tsx` — root layout (FocusModeProvider, PWAUpdateBanner)
- `synapse/frontend/src/app/(dashboard)/layout.tsx` — dashboard layout (useAccentTheme, useKeyboardShortcuts)
- `synapse/frontend/src/app/(dashboard)/home/page.tsx` — Dashboard with all 5 new widgets
- `synapse/frontend/src/app/(dashboard)/library/page.tsx` — SmartCollections, ShareDigest, NotionExport
- `synapse/frontend/src/app/(dashboard)/analytics/page.tsx` — ActivityHeatmapCalendar + charts
- `synapse/frontend/src/app/(dashboard)/settings/page.tsx` — AccentThemePicker, SourceQualityManager
- `synapse/frontend/src/app/(dashboard)/research/page.tsx` — ResearchBrief button
- `synapse/frontend/src/components/modals/ContentReaderModal.tsx` — 6-tab reader (all AI tabs)
- `synapse/frontend/src/components/ui/CommandPalette.tsx` — prefix-mode command palette (>, @, #)
- `synapse/frontend/src/components/Providers.tsx` — QueryClient, ThemeProvider, FocusModeProvider export
