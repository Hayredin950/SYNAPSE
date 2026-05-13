# 🧠 SYNAPSE — What's New & What to Check (Post-Implementation Guide)

> Based on all completed tasks from `SUGGESTION_TASKS.md`
> Last updated: 2026-04-04

---

## 🔴 Phase 0 — Critical Fixes (All Done)

### ✅ TASK-001 — Onboarding Wizard
**Where to check:** http://localhost:3000/wizard
- First-time users are guided through a multi-step wizard to set up interests, topics, and preferences
- ✔ Register a new account → should redirect to `/wizard` automatically

### ✅ TASK-002 — Authentication
**Where to check:** http://localhost:3000/login and http://localhost:3000/settings
- **MFA (2FA):** Settings → Security → enable TOTP (QR code scan)
- **MFA Recovery codes:** backup codes shown when enabling MFA
- **GitHub OAuth:** Login page → "Continue with GitHub" button

### ✅ TASK-003 — Billing / Stripe
**Where to check:** http://localhost:3000/billing and http://localhost:3000/pricing
- Full Stripe subscription flow (Free / Pro / Enterprise plans)
- Pricing page with plan comparison
- Upgrade modal appears when hitting plan limits

### ✅ TASK-004 — AI Guardrails & Cost Protection
- Per-user daily AI budget caps (Redis sliding window)
- Content moderation on all AI inputs/outputs
- Safety filters for toxic/harmful content
- ✔ Go to http://localhost:3000/chat → send many AI messages → should see a rate limit warning

### ✅ TASK-005 — Upgraded Embeddings (BGE-large 1024-dim)
- Semantic search is now 2–3× more accurate (was MiniLM-L6, now BAAI/bge-large-en-v1.5)
- ✔ Check: http://localhost:3000/search → try semantic search queries

### ✅ TASK-006 — Team Workspaces / Organizations
**Where to check:** http://localhost:3000/organizations
- Create/manage organizations
- Invite members, assign roles (Owner / Admin / Member)
- Org switcher in the top navbar
- Per-org audit logs
- ✔ Check: Navbar top-left → org switcher dropdown

---

## 🟡 Phase 1 — Cleanup (Done)

- Nitter spider removed (X/Twitter scraping was dead)
- Redis in-memory fallback removed (no more silent data loss)
- Automation templates moved to database (no more hardcoded frontend arrays)
- Modals extracted to `/components/modals/` system
- API versioned under `/api/v1/`

---

## 🟢 Phase 2 & 3 — AI Features (All Done)

### ✅ TASK-201 — Weekly AI Digest Email
**Where to check:** http://localhost:3000/settings (DigestSection)
- Toggle weekly digest on/off
- Personalized AI-generated email of your top content each week

### ✅ TASK-301 — Hybrid Search (BM25 + Semantic + Reranking)
**Where to check:** http://localhost:3000/search
- Search now combines full-text (BM25) + vector similarity + cross-encoder reranking
- Dramatically better results than before

### ✅ TASK-302 — Multi-LLM Support (Claude + Ollama + GPT-4o)
**Where to check:** http://localhost:3000/chat
- Model selector dropdown in chat → choose between Gemini / GPT-4o / Claude / Ollama
- ✔ Look for model picker near the chat input

### ✅ TASK-303 — Expanded AI Agent Tools
**Where to check:** http://localhost:3000/agents
- Agents can now: **web search** (Tavily), **read PDFs**, **generate charts**, **run Python code**
- ✔ Try: create an agent task like "search the web for latest AI news"

### ✅ TASK-304 — Voice Interface
**Where to check:** http://localhost:3000/chat
- 🎤 Microphone button in chat → speak your query (Whisper transcription)
- 🔊 Speaker button on AI responses → text-to-speech playback

### ✅ TASK-305 — Daily AI Briefing (In-App)
**Where to check:** http://localhost:3000/home
- Every morning: personalised AI briefing card with top stories, papers, repos
- ✔ Check home/dashboard page for a briefing card at the top

### ✅ TASK-306 — Prompt Library
**Where to check:** http://localhost:3000/prompts
- Browse, create, fork, and share reusable AI prompts
- Like/upvote community prompts

---

## 🟢 Phase 4, 5 & 6 — UX & New Features (Done)

### ✅ TASK-401 — Design System
- Custom Tailwind tokens (brand colours, spacing, shadows)
- Consistent component library across the app

### ✅ TASK-402 — Command Palette
**Shortcut:** Press **`Ctrl+K`** (or `Cmd+K` on Mac) anywhere in the app
- Global search + keyboard navigation between all pages

### ✅ TASK-601 — Research Mode (Deep Dive Intelligence)
**Where to check:** http://localhost:3000/research
- Deep research workspace: search arXiv papers, AI synthesis, citation networks
- "Deep Research" panel → AI agent runs multi-step research session
- Progress tracker: searching → analysing → synthesising → done

### ✅ TASK-602 — GitHub Intelligence Dashboard
**Where to check:** http://localhost:3000/github
- Trending repos, star velocity sparklines, tech stack detection
- Rising stars, topic clustering

### ✅ TASK-603 — AI Knowledge Graph
**Where to check:** http://localhost:3000/knowledge-graph
- Visual graph of concepts auto-extracted from your saved content
- Nodes = concepts, edges = relationships between topics

### ✅ TASK-604 — Automation Marketplace
**Where to check:** http://localhost:3000/marketplace
- Browse and install community-published workflow templates

### ✅ TASK-605 — Public API + Developer Portal
**Where to check:** http://localhost:3000/developers
- Generate personal API keys
- API documentation for accessing Synapse programmatically

### ✅ TASK-606 — Browser Extension
- Files are in `browser-extension/` folder
- To install in Chrome: Extensions → Developer Mode → Load unpacked → select `browser-extension/`
- Adds a "Save to Synapse" button on any webpage

### ✅ TASK-607 — Integrations
**Where to check:** http://localhost:3000/settings
- Google Drive, Notion, Obsidian, Zotero, S3, Slack integrations

---

## 🗺️ Quick Navigation Checklist

| Page | URL | What to verify |
|------|-----|----------------|
| Home / Briefing | `/home` | Daily AI briefing card |
| Feed | `/feed` | For You + Trending tabs |
| Search | `/search` | Hybrid search results |
| Chat | `/chat` | Model selector + voice input |
| Agents | `/agents` | Web search, PDF, code tools |
| Research | `/research` | Deep research + paper synthesis |
| GitHub | `/github` | Intelligence dashboard |
| Knowledge Graph | `/knowledge-graph` | Visual concept graph |
| Automation | `/automation` | Workflow builder |
| Marketplace | `/marketplace` | Community templates |
| Prompts | `/prompts` | Prompt library |
| Developers | `/developers` | API keys |
| Billing | `/billing` | Subscription status |
| Pricing | `/pricing` | Public pricing page (no login needed) |
| Settings | `/settings` | MFA, digest, integrations |
| Organizations | `/organizations` | Team workspaces |
| Onboarding | `/wizard` | New user setup flow |

---

## 🐳 Running Services

| Service | URL | Notes |
|---------|-----|-------|
| Frontend | http://localhost:3000 | Next.js (dev mode) |
| Django Backend API | http://localhost:8000/api/v1/ | REST API |
| Django Admin | http://localhost:8000/admin/ | Superuser panel |
| FastAPI AI Engine | http://localhost:8001/docs | AI/LLM endpoints (start with `docker compose up -d fastapi_ai`) |
| Celery Flower | http://localhost:5555 | Task monitor (start with `docker compose up -d flower`) |

> **Note:** FastAPI AI and Flower are stopped by default to save RAM. Start them when needed with:
> ```bash
> docker compose up -d fastapi_ai flower
> ```

---

## 🐛 Bugs Fixed During Setup

| Bug | Fix Applied |
|-----|-------------|
| Login → instant logout | Rotated refresh token was not being saved after silent refresh (`api.ts`) |
| Redis crash on startup | Corrupted AOF file repaired with `redis-check-aof --fix` |
| Frontend crash loop | Missing `@sentry/nextjs` installed into container volume |
| Slow navigation (2+ min) | Google Fonts removed (was timing out); Celery concurrency 4→1 |
| PC freezing | Celery queue purged; beat stopped; Flower/FastAPI stopped to free RAM |
| `useEffect` not imported | Fixed in `UpgradeModal.tsx` |
| Duplicate `useQuery` import | Fixed in `research/page.tsx` |
