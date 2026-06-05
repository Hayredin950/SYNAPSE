
---

## 🟢 Phase 4 — Tier 3: UX & Design Overhaul

---

### TASK-401 — Design System Upgrade

**Priority:** 🟢 Medium | **Effort:** Large | **Impact:** Brand consistency + dev speed

- [ ] **TASK-401-1:** Add custom design tokens to Tailwind config
  - File: `frontend/tailwind.config.ts`
  - Define: `colors.brand.*`, `colors.surface.*`, `spacing.*`, `borderRadius.*`, `fontSize.*`
  - Replace all ad-hoc `indigo-*`/`violet-*` classes with brand tokens

- [ ] **TASK-401-2:** Implement dark/light mode toggle
  - File: `frontend/tailwind.config.ts` — add `darkMode: 'class'`
  - File: `frontend/src/app/layout.tsx` — wrap with theme provider
  - File: `frontend/src/components/layout/Navbar.tsx` — add sun/moon toggle button
  - Store preference in `localStorage` + respect `prefers-color-scheme`

- [ ] **TASK-401-3:** Standardize spacing scale (4px base grid)
  - Audit all pages for inconsistent padding/margin
  - Replace arbitrary values with Tailwind spacing tokens

- [ ] **TASK-401-4:** Add Storybook for component documentation
  - Run: `npx storybook init` in `frontend/`
  - Write stories for: `Button`, `Card`, `Badge`, `Input`, `Modal`, `SkeletonLoader`
  - File: `frontend/.storybook/` *(new directory)*

---

### TASK-402 — Command Palette (⌘K Global Search)

**Priority:** 🟢 High | **Effort:** Medium | **Impact:** Instant UX quality signal

- [ ] **TASK-402-1:** Install `cmdk` library
  - File: `frontend/package.json`
  - Add: `cmdk` package

- [ ] **TASK-402-2:** Create CommandPalette component
  - File: `frontend/src/components/ui/CommandPalette.tsx` *(new)*
  - Triggered by `⌘K` / `Ctrl+K` keyboard shortcut
  - Search across: articles, papers, repos, agents, settings, pages
  - Sections: Recent / Content / Actions / Settings

- [ ] **TASK-402-3:** Connect to backend search API
  - File: `frontend/src/components/ui/CommandPalette.tsx`
  - Debounced `GET /api/search/?q=` call as user types
  - Show results grouped by type with icons

- [ ] **TASK-402-4:** Add CommandPalette to root layout
  - File: `frontend/src/app/layout.tsx`
  - Mount `<CommandPalette />` globally so it works on every page

---

### TASK-403 — Dashboard Redesign — Command Center Layout

**Priority:** 🟢 Medium | **Effort:** X-Large | **Impact:** UX differentiation

- [ ] **TASK-403-1:** Implement split-panel layout
  - File: `frontend/src/app/(dashboard)/layout.tsx`
  - Left panel: Sidebar navigation (existing, refine)
  - Center: Main content area with infinite scroll
  - Right panel: Persistent AI assistant drawer (collapsible)

- [ ] **TASK-403-2:** Build persistent AI assistant right panel
  - File: `frontend/src/components/layout/AIAssistantPanel.tsx` *(new)*
  - Mini chat interface always visible on right side (like Cursor)
  - Collapses to icon strip on mobile
  - Context-aware: knows which page user is on

- [ ] **TASK-403-3:** Add infinite scroll to feed/content pages
  - Files: `frontend/src/app/(dashboard)/feed/page.tsx`, `frontend/src/app/(dashboard)/research/page.tsx`
  - Replace pagination with React Query's `useInfiniteQuery`

---

### TASK-404 — Mobile-First Redesign + PWA Activation

**Priority:** 🟢 Medium | **Effort:** Large | **Impact:** Mobile users + PWA installs

- [ ] **TASK-404-1:** Add bottom navigation for mobile
  - File: `frontend/src/components/layout/Sidebar.tsx`
  - On screens `< md`: hide sidebar, show bottom tab bar
  - Tabs: Home / Feed / Search / Chat / Profile

- [ ] **TASK-404-2:** Activate Service Worker PWA
  - File: `frontend/public/sw.js` — implement proper caching strategy
  - Cache: static assets (network-first), API responses (stale-while-revalidate)
  - File: `frontend/src/components/ServiceWorkerRegistration.tsx` — verify it actually registers

- [ ] **TASK-404-3:** Add PWA install prompt
  - File: `frontend/src/components/ServiceWorkerRegistration.tsx`
  - Listen for `beforeinstallprompt` event
  - Show "Install App" banner at bottom of screen

- [ ] **TASK-404-4:** Add push notifications
  - File: `frontend/src/hooks/useNotificationSocket.ts`
  - Request push notification permission on login
  - Subscribe to: trending alerts, agent completions, digest ready

---

### TASK-405 — Accessibility (A11y) Audit

**Priority:** 🟢 Medium | **Effort:** Medium | **Impact:** WCAG compliance + screen readers

- [ ] **TASK-405-1:** Add ARIA labels to all modals
  - Files: All modal components in `frontend/src/components/ui/Modal.tsx` and page-level modals
  - Add: `role="dialog"`, `aria-modal="true"`, `aria-labelledby`, `aria-describedby`

- [ ] **TASK-405-2:** Implement focus trap in modals
  - File: `frontend/src/components/ui/Modal.tsx`
  - Use `focus-trap-react` library or implement custom focus trap
  - Ensure Tab/Shift+Tab cycles only within open modal

- [ ] **TASK-405-3:** Add keyboard navigation to automation builder
  - File: `frontend/src/app/(dashboard)/automation/page.tsx`
  - Arrow key navigation between workflow steps
  - Enter to edit, Delete to remove step, Escape to cancel

- [ ] **TASK-405-4:** Run color contrast audit
  - Check all text/background combinations against WCAG AA (4.5:1 ratio)
  - Fix low-contrast combinations in Tailwind design tokens

- [ ] **TASK-405-5:** Add skip-to-content link
  - File: `frontend/src/app/layout.tsx`
  - Add `<a href="#main-content" className="sr-only focus:not-sr-only">Skip to content</a>`

---

## 🏗️ Phase 5 — Technical Architecture Upgrades

---

### TASK-501 — Error Monitoring (Sentry)

**Priority:** 🏗️ High | **Effort:** Small | **Impact:** Know about bugs before users report them

- [ ] **TASK-501-B1:** Install Sentry in Django backend
  - File: `backend/requirements.txt` — add `sentry-sdk[django]`
  - File: `backend/config/settings/base.py` — add Sentry init with DSN from env
  - Capture: unhandled exceptions, slow transactions (>2s), Celery task errors

- [ ] **TASK-501-B2:** Install Sentry in FastAPI AI engine
  - File: `ai_engine/requirements.txt` — add `sentry-sdk[fastapi]`
  - File: `ai_engine/main.py` — add Sentry init

- [ ] **TASK-501-F1:** Install Sentry in Next.js frontend
  - Run: `npx @sentry/wizard@latest -i nextjs` in `frontend/`
  - File: `frontend/sentry.client.config.ts`, `frontend/sentry.server.config.ts` *(auto-generated)*
  - Add `NEXT_PUBLIC_SENTRY_DSN` to `.env.example`

---

### TASK-502 — Analytics (PostHog)

**Priority:** 🏗️ High | **Effort:** Small | **Impact:** Understand what users actually do

- [ ] **TASK-502-F1:** Install PostHog in Next.js frontend
  - File: `frontend/package.json` — add `posthog-js`
  - File: `frontend/src/components/AnalyticsProvider.tsx` — already exists, wire up PostHog
  - Add `NEXT_PUBLIC_POSTHOG_KEY` + `NEXT_PUBLIC_POSTHOG_HOST` to `.env.example`

- [ ] **TASK-502-F2:** Track key events
  - File: `frontend/src/utils/analytics.ts` — add PostHog event calls:
    - `user_signed_up`, `onboarding_completed`, `ai_query_sent`, `agent_run_started`
    - `document_generated`, `workflow_created`, `upgrade_prompt_shown`, `plan_upgraded`

- [ ] **TASK-502-B1:** Add PostHog server-side tracking for backend events
  - File: `backend/requirements.txt` — add `posthog`
  - Track: subscription changes, billing events, API usage

---

### TASK-503 — Form Validation (React Hook Form + Zod)

**Priority:** 🏗️ Medium | **Effort:** Medium | **Impact:** Type-safe, validated forms everywhere

- [ ] **TASK-503-1:** Install dependencies
  - File: `frontend/package.json` — add `react-hook-form`, `zod`, `@hookform/resolvers`

- [ ] **TASK-503-2:** Add Zod schemas for all auth forms
  - File: `frontend/src/app/(auth)/login/page.tsx` — add email + password schema
  - File: `frontend/src/app/(auth)/register/page.tsx` — add full registration schema
  - File: `frontend/src/app/(auth)/forgot-password/page.tsx` — email schema

- [ ] **TASK-503-3:** Add validation to settings forms
  - File: `frontend/src/app/(dashboard)/settings/page.tsx`
  - Profile update form, password change form, notification preferences

- [ ] **TASK-503-4:** Add validation to automation workflow builder
  - File: `frontend/src/app/(dashboard)/automation/page.tsx`
  - Validate: workflow name, trigger config, action config before save

---

### TASK-504 — Per-User Rate Limiting

**Priority:** 🏗️ High | **Effort:** Medium | **Impact:** Prevent abuse, enforce plan tiers

- [ ] **TASK-504-B1:** Install django-ratelimit
  - File: `backend/requirements.txt` — add `django-ratelimit`

- [ ] **TASK-504-B2:** Add rate limits to AI endpoints
  - File: `backend/apps/core/views_chat.py`
  - Free: 5 AI queries/day, Pro: 200/day, Team: pooled 1000/day
  - Use Redis-backed rate limit keys: `rl:user:{user_id}:ai_query:{date}`

- [ ] **TASK-504-B3:** Add rate limits to agent endpoints
  - File: `backend/apps/agents/views.py`
  - Free: 1 run/day, Pro: 50/day

- [ ] **TASK-504-B4:** Return clear 429 responses with retry info
  - Include headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
  - Return JSON: `{"error": "rate_limit_exceeded", "reset_at": "2026-04-02T00:00:00Z", "upgrade_url": "/pricing"}`

- [ ] **TASK-504-F1:** Handle 429 errors gracefully in frontend
  - File: `frontend/src/utils/api.ts`
  - Intercept 429 responses, show upgrade prompt modal or countdown timer

---

### TASK-505 — Database Backups

**Priority:** 🏗️ High | **Effort:** Small-Medium | **Impact:** Data loss prevention

- [ ] **TASK-505-B1:** Create automated pg_dump Celery task
  - File: `backend/apps/core/tasks.py`
  - Task: `backup_database()` — runs daily at 2am via Celery beat
  - Dump to S3: `s3://synapse-backups/postgres/{date}.sql.gz`
  - Keep last 30 days of backups

- [ ] **TASK-505-B2:** Add backup monitoring
  - Send alert if backup fails (email + Slack webhook)
  - Add backup status to admin dashboard

- [ ] **TASK-505-3:** Add backup restore documentation
  - File: `DEPLOYMENT.md` — add "Restoring from backup" section

---

### TASK-506 — OpenTelemetry Distributed Tracing

**Priority:** 🏗️ Medium | **Effort:** Medium | **Impact:** Debug cross-service latency

- [ ] **TASK-506-B1:** Add OpenTelemetry to Django backend
  - File: `backend/requirements.txt` — add `opentelemetry-sdk`, `opentelemetry-instrumentation-django`
  - File: `backend/config/settings/base.py` — configure OTLP exporter to Tempo/Jaeger

- [ ] **TASK-506-B2:** Add OpenTelemetry to FastAPI AI engine
  - File: `ai_engine/requirements.txt` — add `opentelemetry-instrumentation-fastapi`
  - File: `ai_engine/main.py` — add tracer setup

- [ ] **TASK-506-B3:** Add Jaeger/Tempo to docker-compose
  - File: `docker-compose.monitoring.yml`
  - Add `tempo` service (Grafana Tempo for trace storage)
  - Add Tempo datasource to Grafana provisioning

---

### TASK-507 — Audit Log

**Priority:** 🏗️ Medium | **Effort:** Medium | **Impact:** Enterprise compliance (SOC2)

- [ ] **TASK-507-B1:** Create AuditLog model
  - File: `backend/apps/core/models.py`
  - Fields: `user`, `action`, `resource_type`, `resource_id`, `metadata` (JSON), `ip_address`, `created_at`
  - Indexed on: `user`, `created_at`, `action`

- [ ] **TASK-507-B2:** Create audit log signal/middleware
  - File: `backend/apps/core/` — new `audit.py`
  - Decorator `@audit_log(action='agent.run')` for key views
  - Log: login, logout, plan changes, agent runs, document generations, API key creation

- [ ] **TASK-507-B3:** Add audit log API for admins/org owners
  - `GET /api/admin/audit-logs/` — filterable by user, date range, action type

---

## 🚀 Phase 6 — New Market Differentiation Features

---

### TASK-601 — Research Mode (Deep Dive Intelligence)

**Priority:** 🚀 High | **Effort:** X-Large | **Impact:** Core product differentiator

#### Backend Tasks
- [ ] **TASK-601-B1:** Create ResearchSession model
  - File: `backend/apps/agents/models.py`
  - Fields: `user`, `query`, `status`, `report` (text), `sources` (JSON), `created_at`

- [ ] **TASK-601-B2:** Create research agent workflow
  - File: `ai_engine/agents/` — new `research_agent.py`
  - Multi-step plan:
    1. Decompose query into sub-questions
    2. Search ArXiv, GitHub, knowledge base in parallel
    3. Synthesize results per sub-question
    4. Generate final structured report with citations
  - Uses LangGraph with Plan-and-Execute pattern

- [ ] **TASK-601-B3:** Add research mode API endpoint
  - `POST /api/research/` — start research session (returns session_id)
  - `GET /api/research/{id}/` — get session status + report
  - `GET /api/research/{id}/export/` — download as PDF

- [ ] **TASK-601-B4:** Add PDF export for research reports
  - File: `backend/apps/documents/views.py`
  - Use existing document generation infrastructure
  - Template: literature review format with citations

#### Frontend Tasks
- [ ] **TASK-601-F1:** Create Research Mode page
  - File: `frontend/src/app/(dashboard)/research/page.tsx` — overhaul existing page
  - Large search bar center-screen (like Perplexity)
  - "Research Mode" toggle vs "Quick Search"
  - Show multi-step progress: Searching → Analyzing → Writing Report

- [ ] **TASK-601-F2:** Research report viewer
  - Render structured report with section headers + inline citations
  - Clickable citations → open source in side panel
  - Export buttons: PDF / Notion / Google Docs

---

### TASK-602 — GitHub Intelligence Dashboard

**Priority:** 🚀 Medium | **Effort:** Large | **Impact:** Developer/CTO audience

- [ ] **TASK-602-B1:** Enhance GitHub spider with trend analytics
  - File: `scraper/spiders/github_spider.py`
  - Capture: star count history, fork count, language, topics, contributor count, last commit date

- [ ] **TASK-602-B2:** Create GitHub trend analysis task
  - File: `backend/apps/repositories/` — new `analytics.py`
  - Daily Celery task: compute 7d/30d star velocity, classify repos as rising/stable/declining

- [ ] **TASK-602-B3:** Add GitHub intelligence API endpoints
  - `GET /api/github/trending/` — rising stars by topic/language
  - `GET /api/github/ecosystem/{language}/` — health score for a language ecosystem
  - `GET /api/github/repo/{id}/analysis/` — full repo analysis

- [ ] **TASK-602-F1:** Create GitHub Intelligence page
  - File: `frontend/src/app/(dashboard)/github/page.tsx` — overhaul existing page
  - Trending repos chart (star velocity over time using Recharts)
  - Language ecosystem health cards
  - "Rising Stars" section with momentum indicators

---

### TASK-603 — AI Knowledge Graph

**Priority:** 🚀 Medium | **Effort:** X-Large | **Impact:** Unique visual differentiator

- [ ] **TASK-603-B1:** Design knowledge graph data model
  - New model: `KnowledgeNode` (entity: paper/repo/concept/author)
  - New model: `KnowledgeEdge` (relationship: cites/uses/related_to/authored_by)

- [ ] **TASK-603-B2:** Build graph construction pipeline
  - Celery task: extract entities from NLP pipeline, create nodes + edges
  - Use NER results from `ai_engine/nlp/ner.py` to identify entities
  - Link papers citing same concepts, repos using same libraries

- [ ] **TASK-603-B3:** Add graph API endpoint
  - `GET /api/knowledge-graph/?center={entity_id}&depth=2` — return nodes + edges JSON

- [ ] **TASK-603-F1:** Build interactive knowledge graph UI
  - File: `frontend/src/app/(dashboard)/` — new `knowledge-graph/page.tsx`
  - Use `cytoscape.js` or `react-force-graph` for visualization
  - Click node → show details panel
  - Filter by: content type, topic, date range

---

### TASK-604 — Automation Marketplace

**Priority:** 🚀 Medium | **Effort:** Large | **Impact:** Community + monetization

- [ ] **TASK-604-B1:** Add marketplace fields to workflow model
  - File: `backend/apps/automation/models.py`
  - Add: `is_published`, `download_count`, `upvotes`, `price` (0 = free), `author_revenue_share`

- [ ] **TASK-604-B2:** Add marketplace API endpoints
  - `GET /api/marketplace/workflows/` — list public templates
  - `POST /api/marketplace/workflows/{id}/install/` — copy template to user's workspace
  - `POST /api/marketplace/workflows/{id}/publish/` — publish user's workflow

- [ ] **TASK-604-F1:** Create Marketplace page
  - File: `frontend/src/app/(dashboard)/` — new `marketplace/page.tsx`
  - Grid of workflow cards with: name, description, author, downloads, rating
  - Filter by: category, free/paid, popularity

---

### TASK-605 — Public API + Developer Portal

**Priority:** 🚀 Medium | **Effort:** Large | **Impact:** PLG motion + developer ecosystem

- [ ] **TASK-605-B1:** Create API key model + management
  - File: `backend/apps/users/models.py` — add `APIKey` model
  - Fields: `user`, `key_hash`, `name`, `scopes[]`, `last_used`, `created_at`, `is_active`
  - Endpoint: `POST /api/keys/` — generate key, `DELETE /api/keys/{id}/` — revoke

- [ ] **TASK-605-B2:** Add API key authentication
  - File: `backend/apps/core/` — new `auth.py`
  - DRF authentication class: `APIKeyAuthentication` — reads `Authorization: Bearer sk-...` header
  - Apply to all public API endpoints

- [ ] **TASK-605-B3:** Create public API endpoints (rate-limited by plan)
  - `GET /api/v1/content/articles/` — search articles
  - `GET /api/v1/content/papers/` — search papers
  - `POST /api/v1/ai/query/` — ask AI a question
  - `GET /api/v1/trends/` — get current trends

- [ ] **TASK-605-F1:** Create API Keys settings section
  - File: `frontend/src/app/(dashboard)/settings/page.tsx`
  - List user's API keys with last-used timestamp
  - "Create Key" button + name input + scope selector
  - One-time key display with copy button

- [ ] **TASK-605-F2:** Create Developer Portal page
  - File: `frontend/src/app/(dashboard)/` — new `developers/page.tsx`
  - Interactive API docs (link to auto-generated Swagger/ReDoc)
  - Quick start code snippets: Python / TypeScript / cURL
  - SDK download links

---

### TASK-606 — Browser Extension

**Priority:** 🚀 Low | **Effort:** Large | **Impact:** Acquisition channel

- [ ] **TASK-606-1:** Create Chrome extension project
  - New directory: `browser-extension/`
  - Manifest V3 setup: `manifest.json`, `background.js`, `content.js`, `popup.html`

- [ ] **TASK-606-2:** "Save to Synapse" button
  - Inject button on web pages + GitHub repos + ArXiv papers
  - On click: send page URL + title + selected text to `POST /api/v1/content/save/`

- [ ] **TASK-606-3:** "Explain with Synapse AI" context menu
  - Right-click any selected text → "Explain with Synapse AI"
  - Opens popup with AI explanation using RAG chain

- [ ] **TASK-606-4:** Add save endpoint to backend
  - File: `backend/apps/articles/views.py`
  - `POST /api/v1/content/save/` — accept URL, scrape metadata, add to user's library

---

### TASK-607 — Integrations Marketplace

**Priority:** 🚀 Low | **Effort:** Large | **Impact:** Enterprise stickiness

- [ ] **TASK-607-1:** Notion integration
  - File: `backend/apps/integrations/` — new `notion.py`
  - OAuth flow to connect Notion workspace
  - Read pages into RAG knowledge base
  - Write research reports back to Notion

- [ ] **TASK-607-2:** Slack integration
  - File: `backend/apps/integrations/` — new `slack.py`
  - Slack app: `/synapse` slash command → ask AI question in Slack
  - Daily digest delivered to Slack channel

- [ ] **TASK-607-3:** Obsidian integration
  - File: `backend/apps/integrations/` — new `obsidian.py`
  - Sync Obsidian vault notes into Synapse knowledge base via webhook or file upload

- [ ] **TASK-607-4:** Zotero integration
  - File: `backend/apps/integrations/` — new `zotero.py`
  - Import Zotero library via API — auto-embed papers into RAG

- [ ] **TASK-607-5:** Update integrations settings UI
  - File: `frontend/src/app/(dashboard)/settings/page.tsx`
  - Add integration cards for each service with connect/disconnect buttons

---

## 📊 Task Summary

| Phase | Tasks | Effort | Priority |
|---|---|---|---|
| Phase 0 — Critical Fixes | TASK-001 to TASK-006 | 6–8 weeks | 🔴 Do First |
| Phase 1 — Remove & Simplify | TASK-101 to TASK-105 | 1–2 weeks | 🟡 Quick Wins |
| Phase 2 — Revenue & Retention | TASK-201 | 1 week | 🟢 High |
| Phase 3 — AI Differentiation | TASK-301 to TASK-306 | 4–6 weeks | 🟢 High |
| Phase 4 — UX & Design | TASK-401 to TASK-405 | 4–5 weeks | 🟢 Medium |
| Phase 5 — Architecture | TASK-501 to TASK-507 | 3–4 weeks | 🏗️ Ongoing |
| Phase 6 — New Features | TASK-601 to TASK-607 | 8–12 weeks | 🚀 After PMF |

---

## ✅ Quick Reference — Top 10 Start-Now Tasks

| # | Task ID | Action | File(s) |
|---|---|---|---|
| 1 | TASK-101 | Kill the Nitter spider | `scraper/spiders/nitter_spider.py` |
| 2 | TASK-001 | Build onboarding wizard | `backend/apps/users/`, `frontend/src/app/(auth)/onboarding/` |
| 3 | TASK-003 | Activate Stripe billing | `backend/apps/billing/`, `frontend/src/app/(dashboard)/pricing/` |
| 4 | TASK-004 | Add AI guardrails + rate limits | `ai_engine/guardrails.py`, `ai_engine/rag/memory.py` |
| 5 | TASK-005 | Upgrade embeddings to BGE-large | `ai_engine/embeddings/embedder.py` |
| 6 | TASK-402 | Add ⌘K command palette | `frontend/src/components/ui/CommandPalette.tsx` |
| 7 | TASK-501 | Add Sentry error monitoring | `backend/config/settings/base.py`, `frontend/sentry.client.config.ts` |
| 8 | TASK-502 | Add PostHog analytics | `frontend/src/components/AnalyticsProvider.tsx` |
| 9 | TASK-006 | Build team workspaces | `backend/apps/organizations/` |
| 10 | TASK-301 | Add hybrid search (BM25 + vector) | `ai_engine/rag/retriever.py` |
