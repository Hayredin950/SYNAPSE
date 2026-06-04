
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
  - Files to refactor:
    - `frontend/src/app/(dashboard)/automation/EditWorkflowModal.tsx` → move to `frontend/src/components/modals/EditWorkflowModal.tsx`
    - `frontend/src/app/(dashboard)/automation/ScheduleModal.tsx` → `frontend/src/components/modals/ScheduleModal.tsx`
    - `frontend/src/app/(dashboard)/automation/AnalyticsModal.tsx` → `frontend/src/components/modals/AnalyticsModal.tsx`
- [ ] **TASK-104-3:** Extract document modals
  - File: `frontend/src/app/(dashboard)/documents/page.tsx`
  - Pull out any inline modal JSX into `frontend/src/components/modals/DocumentModal.tsx`
- [ ] **TASK-104-4:** Add modal portal via React `createPortal`
  - File: `frontend/src/app/layout.tsx`
  - Add `<div id="modal-root" />` at bottom of body for portal mounting

---

### TASK-105 — Add API Versioning

**Priority:** 🟡 Simplify | **Effort:** Small | **Impact:** Future-proof all API changes

- [ ] **TASK-105-1:** Prefix all routes with `/api/v1/`
  - File: `backend/config/urls.py`
  - Wrap all app URL includes under `api/v1/` prefix
- [ ] **TASK-105-2:** Update frontend API base URL
  - File: `frontend/src/utils/api.ts`
  - Change `baseURL` from `/api/` to `/api/v1/`
- [ ] **TASK-105-3:** Update Nginx proxy config
  - File: `infrastructure/nginx/conf.d/synapse.conf`
  - Ensure `/api/v1/` is correctly proxied to Django backend

