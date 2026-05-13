# 🧠 SYNAPSE — Detailed Implementation Task List

> **How to use this file:**
> - Check off `- [x]` when a task is complete
> - Each task includes: what to do, which files to touch, and implementation notes
> - Tasks are ordered by priority — work top to bottom
> - Status legend: 🔴 Critical | 🟡 Simplify/Remove | 🟢 Add | 🏗️ Architecture | 🚀 New Feature

---

## 📋 TABLE OF CONTENTS

1. [🔴 Phase 0 — Critical Fixes (Do First)](#phase-0--critical-fixes)
2. [🟡 Phase 1 — Remove & Simplify](#phase-1--remove--simplify)
3. [🟢 Phase 2 — Tier 1: Revenue & Retention](#phase-2--tier-1-revenue--retention)
4. [🟢 Phase 3 — Tier 2: AI Differentiation](#phase-3--tier-2-ai-differentiation)
5. [🟢 Phase 4 — Tier 3: UX & Design Overhaul](#phase-4--tier-3-ux--design-overhaul)
6. [🏗️ Phase 5 — Technical Architecture Upgrades](#phase-5--technical-architecture-upgrades)
7. [🚀 Phase 6 — New Market Differentiation Features](#phase-6--new-market-differentiation-features)

---

## 🔴 Phase 0 — Critical Fixes

> These are blocking issues. Nothing else matters until these are done.

---

### 🚪 TASK-001 — Onboarding Wizard

**Priority:** 🔴 Critical | **Effort:** Large | **Impact:** +40–60% Day-1 retention

#### Backend Tasks
- [ ] **TASK-001-B1:** Create `onboarding` app or add onboarding models to `users` app
  - File: `backend/apps/users/models.py`
  - Add `OnboardingProfile` model with fields: `topics[]`, `tech_stack[]`, `sources[]`, `completed_at`, `step`
  - Migration: `backend/apps/users/migrations/`

- [ ] **TASK-001-B2:** Create onboarding API endpoints
  - File: `backend/apps/users/views.py`
  - `POST /api/users/onboarding/step/` — save each step's data
  - `GET /api/users/onboarding/status/` — return current step + completion state
  - `POST /api/users/onboarding/complete/` — mark onboarding done, trigger first brief generation

- [ ] **TASK-001-B3:** Create onboarding serializers
  - File: `backend/apps/users/serializers.py`
  - Add `OnboardingSerializer` with topic/source/stack validation

- [ ] **TASK-001-B4:** Trigger first personalized brief on onboarding completion
  - File: `backend/apps/core/tasks.py`
  - Create Celery task `generate_first_brief(user_id)` that seeds the feed with relevant content

- [ ] **TASK-001-B5:** Add onboarding URL routes
  - File: `backend/apps/users/urls.py`
  - Register all onboarding endpoints

#### Frontend Tasks
- [ ] **TASK-001-F1:** Create onboarding wizard route
  - File: `frontend/src/app/(auth)/onboarding/page.tsx` *(new file)*
  - Multi-step wizard with progress bar (Steps 1–4)

- [ ] **TASK-001-F2:** Step 1 — Interest selector UI
  - File: `frontend/src/app/(auth)/onboarding/page.tsx`
  - Tag-style multi-select for topics: AI, Web Dev, DevOps, Research, Security, etc.
  - Tech stack selector: Python, TypeScript, Rust, Go, etc.

- [ ] **TASK-001-F3:** Step 2 — Integration connectors UI
  - Connect GitHub, Google Drive, Notion buttons (OAuth redirects)
  - Show connected/skip state for each

- [ ] **TASK-001-F4:** Step 3 — "Generating your brief" loading screen
  - Animated loading state while `generate_first_brief` Celery task runs
  - Poll `GET /api/users/onboarding/status/` every 2s

- [ ] **TASK-001-F5:** Step 4 — "Your feed is ready" success screen
  - Celebration animation (Framer Motion)
  - CTA button → redirect to `/home`

- [ ] **TASK-001-F6:** Add empty state components across all pages
  - Files to update:
    - `frontend/src/app/(dashboard)/feed/page.tsx`
    - `frontend/src/app/(dashboard)/research/page.tsx`
    - `frontend/src/app/(dashboard)/library/page.tsx`
  - Show friendly empty state with "Set up your feed →" CTA for new users

- [ ] **TASK-001-F7:** Redirect new users to onboarding after registration
  - File: `frontend/src/app/(auth)/register/page.tsx`
  - After successful register, check `onboarding.completed` → redirect to `/onboarding`

---

### 🔐 TASK-002 — Authentication Completion

**Priority:** 🔴 Critical | **Effort:** Medium | **Impact:** Developer trust + security

#### MFA Recovery Codes
- [ ] **TASK-002-B1:** Add recovery codes model
  - File: `backend/apps/users/mfa.py`
  - Generate 10 single-use recovery codes on MFA enable
  - Store as hashed values in DB

- [ ] **TASK-002-B2:** Add recovery code API endpoints
  - File: `backend/apps/users/mfa_views.py`
  - `POST /api/users/mfa/recovery-codes/regenerate/`
  - `POST /api/users/mfa/verify-recovery/` — use a code to bypass TOTP

- [ ] **TASK-002-F1:** Show recovery codes UI after MFA setup
  - File: `frontend/src/app/(dashboard)/settings/MFASection.tsx`
  - Display codes in a copyable grid
  - "Download codes" button (saves as `.txt`)
  - "Regenerate codes" with confirmation modal

#### GitHub OAuth
- [ ] **TASK-002-B3:** Add GitHub OAuth backend
  - File: `backend/apps/users/views.py`
  - Add `GitHubOAuthView` — exchange code for token, fetch user profile
  - Map GitHub email → existing account or create new

- [ ] **TASK-002-B4:** Add GitHub OAuth URL
  - File: `backend/apps/users/urls.py`
  - `GET /api/users/auth/github/`
  - `GET /api/users/auth/github/callback/`

- [ ] **TASK-002-F2:** Add "Continue with GitHub" button on login/register
  - Files: `frontend/src/app/(auth)/login/page.tsx`, `frontend/src/app/(auth)/register/page.tsx`
  - Add GitHub button alongside Google OAuth button
  - Use GitHub SVG icon

#### Email Verification Flow
- [ ] **TASK-002-B5:** Improve email verification UX
  - File: `backend/apps/users/views.py`
  - Add resend verification email endpoint: `POST /api/users/resend-verification/`
  - Add expiry check with clear error messages

- [ ] **TASK-002-F3:** Improve verify-email page
  - File: `frontend/src/app/(auth)/verify-email/page.tsx`
  - Show clear success/error states
  - Add "Resend email" button with cooldown timer

---

### 💳 TASK-003 — Billing Activation

**Priority:** 🔴 Critical | **Effort:** Large | **Impact:** Revenue generation

#### Backend Tasks
- [ ] **TASK-003-B1:** Complete Stripe subscription plans setup
  - File: `backend/apps/billing/stripe_service.py`
  - Create Stripe Products + Prices for Free, Pro ($19/mo), Team ($49/seat/mo)
  - Add annual pricing variants (20% discount)

- [ ] **TASK-003-B2:** Add subscription management endpoints
  - File: `backend/apps/billing/views.py`
  - `POST /api/billing/subscribe/` — create Stripe checkout session
  - `POST /api/billing/cancel/` — cancel subscription
  - `POST /api/billing/upgrade/` — change plan
  - `GET /api/billing/portal/` — Stripe customer portal redirect
  - `POST /api/billing/webhook/` — handle Stripe webhooks (already partial?)

- [ ] **TASK-003-B3:** Add usage metering models
  - File: `backend/apps/billing/models.py`
  - Add `UsageRecord` model: `user`, `resource_type` (ai_query/agent_run/storage), `count`, `period`
  - Add `PlanLimit` model: defines limits per plan tier

- [ ] **TASK-003-B4:** Add usage tracking middleware/decorator
  - File: `backend/apps/billing/tasks.py` or new `backend/apps/billing/metering.py`
  - Decorator `@check_usage_limit('ai_query')` for AI views
  - Celery task to reset daily counters at midnight

- [ ] **TASK-003-B5:** Add plan-based feature gates
  - File: `backend/apps/billing/` — new `permissions.py`
  - DRF permission class `HasActivePlan(plan='pro')` 
  - Apply to: agent views, advanced search, automation views

- [ ] **TASK-003-B6:** Trial logic
  - File: `backend/apps/billing/models.py`
  - Add `trial_ends_at` field to user/subscription
  - Celery beat task: send trial expiry warning at 3 days + 1 day before expiry

#### Frontend Tasks
- [ ] **TASK-003-F1:** Create pricing page
  - File: `frontend/src/app/(dashboard)/pricing/page.tsx` *(new file)*
  - 3-column pricing cards: Free / Pro / Team
  - Annual/monthly toggle with savings badge
  - Feature comparison table below cards
  - CTA: "Start Free", "Upgrade to Pro", "Contact Sales"

- [ ] **TASK-003-F2:** Add upgrade prompts at feature gates
  - Files to update:
    - `frontend/src/app/(dashboard)/agents/page.tsx` — gate after 1 run/day
    - `frontend/src/app/(dashboard)/chat/page.tsx` — gate after 5 queries/day
    - `frontend/src/app/(dashboard)/automation/page.tsx` — gate after 3 workflows
  - Show upgrade modal with plan comparison when limit hit

- [ ] **TASK-003-F3:** Create billing settings section
  - File: `frontend/src/app/(dashboard)/settings/page.tsx`
  - Show current plan, usage meters (queries used, storage)
  - "Manage Subscription" → Stripe portal link
  - "Upgrade Plan" CTA

- [ ] **TASK-003-F4:** Create usage meter components
  - File: `frontend/src/components/ui/UsageMeter.tsx` *(new file)*
  - Progress bar showing X/Y usage
  - Color: green → yellow → red as limit approaches

---

### 🛡️ TASK-004 — AI Guardrails

**Priority:** 🔴 Critical | **Effort:** Medium | **Impact:** Cost protection + safety

- [ ] **TASK-004-B1:** Add per-user AI rate limiting
  - File: `backend/apps/core/views_chat.py` and `backend/apps/agents/views.py`
  - Use `django-ratelimit` or Redis counters
  - Limits: Free=5/day, Pro=unlimited with soft cap, Team=pooled

- [ ] **TASK-004-B2:** Add cost budget caps per user tier
  - File: `ai_engine/agents/base.py`
  - Track token usage per request
  - Reject requests if user's monthly budget exceeded
  - Store usage in Redis with TTL=end of month

- [ ] **TASK-004-B3:** Add content filtering / jailbreak detection
  - File: `ai_engine/agents/base.py` or new `ai_engine/guardrails.py`
  - Add input validation: block prompt injection patterns
  - Use simple keyword blocklist + regex for obvious attacks
  - Optionally integrate `guardrails-ai` library

- [ ] **TASK-004-B4:** Add output validation
  - File: `ai_engine/rag/chain.py`
  - Validate LLM responses don't contain PII patterns (emails, phone numbers, SSNs)
  - Add response length limits

- [ ] **TASK-004-B5:** Remove dangerous in-memory Redis fallback
  - File: `ai_engine/rag/memory.py`
  - Remove silent fallback to in-memory dict
  - Raise proper `ServiceUnavailableError` if Redis is down
  - Add health check endpoint for Redis connectivity

- [ ] **TASK-004-B6:** Add AI usage dashboard for admins
  - File: `backend/apps/billing/views.py`
  - Admin endpoint: `GET /api/admin/ai-usage/` — cost per user, per model, per day

---

### 📉 TASK-005 — Upgrade Embeddings Model

**Priority:** 🔴 Critical | **Effort:** Medium | **Impact:** 40–60% better search quality

- [ ] **TASK-005-B1:** Replace `all-MiniLM-L6-v2` with `BAAI/bge-large-en-v1.5`
  - File: `ai_engine/embeddings/embedder.py`
  - Change model name, update dimension from 384 → 1024
  - Update batch size (larger model = smaller batches, try 16)

- [ ] **TASK-005-B2:** Update pgvector column dimensions
  - Files: All `embedding_tasks.py` and migrations in:
    - `backend/apps/articles/migrations/`
    - `backend/apps/papers/migrations/`
    - `backend/apps/repositories/migrations/`
    - `backend/apps/videos/migrations/`
    - `backend/apps/tweets/migrations/`
  - Create new migration to alter vector(384) → vector(1024)

- [ ] **TASK-005-B3:** Re-embed all existing content
  - File: `backend/apps/articles/embedding_tasks.py` (and all similar files)
  - Create one-time management command: `python manage.py reembed_all`
  - Run in batches of 100 with progress logging

- [ ] **TASK-005-B4:** Update IVFFlat index parameters
  - Files: All `0004_*_ivfflat_index.py` migrations
  - New migration to rebuild index with `lists=100` for 1024d vectors

- [ ] **TASK-005-B5:** Update AI engine requirements
  - File: `ai_engine/requirements.txt`
  - Ensure `sentence-transformers>=2.7.0` is present
  - Add `torch` CPU-only version if not already there

---

### 👥 TASK-006 — Team Workspaces / Organizations

**Priority:** 🔴 Critical | **Effort:** X-Large | **Impact:** B2B revenue ceiling

#### Backend Tasks
- [ ] **TASK-006-B1:** Create `organizations` app
  - New app: `backend/apps/organizations/`
  - Models: `Organization`, `OrganizationMember` (with role: owner/admin/member/viewer)
  - Migrations, admin, serializers, views, urls

- [ ] **TASK-006-B2:** Add org-scoped content models
  - `SharedFeed` — org-level feed preferences
  - `SharedKnowledgeBase` — org-level RAG document collection
  - `OrgAgentRun` — agent runs visible to all org members

- [ ] **TASK-006-B3:** Add org management API
  - `POST /api/orgs/` — create org
  - `POST /api/orgs/{id}/invite/` — invite member by email
  - `PATCH /api/orgs/{id}/members/{user_id}/` — change role
  - `DELETE /api/orgs/{id}/members/{user_id}/` — remove member
  - `GET /api/orgs/{id}/usage/` — org-level usage stats

- [ ] **TASK-006-B4:** Scope all queries to org context
  - Add `org` FK to relevant models (feeds, agent runs, documents)
  - Add `OrgPermission` DRF class that checks membership + role

- [ ] **TASK-006-B5:** Update billing for seat-based pricing
  - File: `backend/apps/billing/stripe_service.py`
  - Add seat quantity to Stripe subscription
  - Prorate on member add/remove

#### Frontend Tasks
- [ ] **TASK-006-F1:** Create org settings page
  - File: `frontend/src/app/(dashboard)/settings/organization/page.tsx` *(new)*
  - Member list with roles, invite by email, remove member

- [ ] **TASK-006-F2:** Add org switcher to navbar
  - File: `frontend/src/components/layout/Navbar.tsx`
  - Dropdown to switch between personal and org workspaces

- [ ] **TASK-006-F3:** Show presence indicators
  - File: `frontend/src/app/(dashboard)/feed/page.tsx`
  - WebSocket-based "N teammates viewing this" indicator
  - Use existing `notifications/consumers.py` WebSocket infrastructure

---

## 🟡 Phase 1 — Remove & Simplify

---

### TASK-101 — Kill the Nitter Spider

**Priority:** 🟡 Remove | **Effort:** Small | **Impact:** Reduce dead code + maintenance burden

- [ ] **TASK-101-1:** Delete Nitter spider file
  - File: `scraper/spiders/nitter_spider.py` → delete
- [ ] **TASK-101-2:** Remove Nitter from Celery beat schedule
  - File: `backend/config/settings/base.py` — remove any `nitter` beat task entries
- [ ] **TASK-101-3:** Remove Nitter pipeline references
  - File: `scraper/pipelines/database.py` — remove Nitter-specific logic
- [ ] **TASK-101-4:** *(Optional)* Replace with X/Twitter API v2
  - File: `scraper/spiders/twitter_spider.py` — update to use official Twitter API v2 Bearer Token
  - Requires: `TWITTER_BEARER_TOKEN` env var in `.env.example`

---

### TASK-102 — Remove In-Memory Redis Fallback

**Priority:** 🟡 Remove | **Effort:** Small | **Impact:** Prevent silent data loss in production

- [ ] **TASK-102-1:** Remove in-memory fallback from memory manager
  - File: `ai_engine/rag/memory.py`
  - Delete the `except` block that falls back to a plain dict
  - Replace with: raise `RuntimeError("Redis unavailable — conversation history disabled")`
- [ ] **TASK-102-2:** Add Redis health check to AI engine startup
  - File: `ai_engine/main.py`
  - On startup, ping Redis; if down, log critical error and refuse to start
- [ ] **TASK-102-3:** Add Redis health to `/health` endpoint
  - File: `ai_engine/main.py`
  - Include `redis: ok/fail` in health check response JSON

---

### TASK-103 — Fix Static Automation Templates

**Priority:** 🟡 Simplify | **Effort:** Small-Medium | **Impact:** API-driven templates, no more frontend hardcoding

- [ ] **TASK-103-1:** Create templates API endpoint
  - File: `backend/apps/automation/views.py`
  - `GET /api/automation/templates/` — return all available templates from DB
- [ ] **TASK-103-2:** Seed templates into DB via fixture
  - File: `backend/apps/automation/fixtures/templates.json` *(new)*
  - Move all hardcoded frontend templates into this fixture
  - Run: `python manage.py loaddata templates`
- [ ] **TASK-103-3:** Remove hardcoded fallback from frontend
  - File: `frontend/src/app/(dashboard)/automation/TemplatesModal.tsx`
  - Remove static fallback schema arrays
  - Fetch from `GET /api/automation/templates/` via React Query

---

### TASK-104 — Extract Inline Modals to Proper Modal System

**Priority:** 🟡 Simplify | **Effort:** Medium | **Impact:** Cleaner code, reusable modal system

- [ ] **TASK-104-1:** Create global Modal component
  - File: `frontend/src/components/ui/Modal.tsx` — already exists, extend it
  - Ensure it supports: size variants (sm/md/lg/xl/fullscreen), close on ESC, focus trap, backdrop click dismiss
- [ ] **TASK-104-2:** Extract automation modals
  - `frontend/src/app/(dashboard)/automation/EditWorkflowModal.tsx` → `frontend/src/components/modals/EditWorkflowModal.tsx`
  - `frontend/src/app/(dashboard)/automation/ScheduleModal.tsx` → `frontend/src/components/modals/ScheduleModal.tsx`
  - `frontend/src/app/(dashboard)/automation/AnalyticsModal.tsx` → `frontend/src/components/modals/AnalyticsModal.tsx`
- [ ] **TASK-104-3:** Extract document modals
  - File: `frontend/src/app/(dashboard)/documents/page.tsx`
  - Pull out inline modal JSX into `frontend/src/components/modals/DocumentModal.tsx`
- [ ] **TASK-104-4:** Add modal portal via React `createPortal`
  - File: `frontend/src/app/layout.tsx`
  - Add `<div id="modal-root" />` at bottom of body for portal mounting

---

### TASK-105 — Add API Versioning

**Priority:** 🟡 Simplify | **Effort:** Small | **Impact:** Future-proof all API changes

- [ ] **TASK-105-1:** Prefix all routes with `/api/v1/`
  - File: `backend/config/urls.py` — wrap all app URL includes under `api/v1/` prefix
- [ ] **TASK-105-2:** Update frontend API base URL
  - File: `frontend/src/utils/api.ts` — change `baseURL` from `/api/` to `/api/v1/`
- [ ] **TASK-105-3:** Update Nginx proxy config
  - File: `infrastructure/nginx/conf.d/synapse.conf` — ensure `/api/v1/` is proxied to Django

---
