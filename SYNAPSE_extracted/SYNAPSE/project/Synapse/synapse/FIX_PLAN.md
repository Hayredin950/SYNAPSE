# SYNAPSE — Fix Plan

**Reviewer:** v0 (April 2026)
**Live deployments:**
- Frontend (Vercel): `https://synapse-app-six.vercel.app`
- Backend (Render): `https://synapse-api-oyld.onrender.com`
- Repo: `github.com/HayreKhan750/SYNAPSE`

This document is the prioritized action plan to make the deployed app actually
work end-to-end. Items are tagged **P0** (blocks all usage), **P1** (blocks a
major feature), **P2** (polish / quality).

---

## 0. What was fixed in this commit

The following code-side fixes are in this PR (everything else still requires
the dashboard / env-var work described below):

- **Removed root `package.json` stub** that contained only `rehype-raw` and
  conflicted with the real Next.js app under `/frontend`.
- **Login + Register pages**: OAuth buttons now detect missing
  `NEXT_PUBLIC_GOOGLE_CLIENT_ID` / `NEXT_PUBLIC_API_URL` and render in a
  clear **disabled** state with a tooltip explaining the deployment isn't
  configured for SSO — instead of opening a popup that fails silently.
- **Login page**: error codes returned by the GitHub OAuth callback
  (`?error=github_denied`, `github_no_email`, `github_token_failed`,
  `github_profile_failed`, `github_no_token`) are now read from the URL
  query string and surfaced as readable error messages.
- **Auth layout footer**: the corrupted `��` glyph at the copyright line
  was replaced with a proper `©`.
- **Sidebar**: removed the dead `BOTTOM_NAV` constant and the duplicated
  `tabs` array; mobile bottom nav now uses a single `MOBILE_BOTTOM_TABS`
  source of truth, and the `Profile` tab uses the `User` icon instead of
  `LayoutDashboard`.
- **Navbar (mobile)**: tightened spacing on phones, added a search icon
  trigger that's only visible under `md`, hid the org switcher under `sm`
  to stop the right cluster overflowing, and made the page title truncate
  cleanly instead of wrapping.
- **Production email backend**: `config/settings/production.py` now
  auto-switches to the real Django SMTP backend whenever
  `EMAIL_HOST_PASSWORD` (or `SENDGRID_API_KEY`) is set, and falls back to
  `dummy.EmailBackend` with a `RuntimeWarning` when no SMTP credentials
  exist — instead of silently inheriting the console backend from `base.py`
  and dropping every verification / password-reset email on the floor.
- **Automation `▶ Run` endpoint** (`apps/automation/views.py`): now pings
  Celery workers via `app.control.inspect().ping()` before enqueueing. If
  no worker responds within 1 s, the workflow runs **synchronously** in the
  request and the run record is updated with the result (or error). This
  is the single most common reason workflows appear stuck in PENDING when
  Render Redis is up but the worker service isn't deployed.
- **`.env.example`**: documented `NEXT_PUBLIC_GOOGLE_CLIENT_ID` (it was
  missing), and added clearer instructions for `GITHUB_CLIENT_ID` /
  `GITHUB_REDIRECT_URI` for production deployments.

---

## 1. Why things are broken (root causes)

The code itself is largely correct and well-architected. The reasons features
don't work in production are, in order of impact:

1. **Render web service alone is not enough.** Automation, scraping, agent
   runs, AI chat warmups, daily briefings, and email sending all rely on
   **Celery workers + Celery Beat** which must run as **separate Render
   Background Worker services**. Without them, every `task.delay()` call is
   queued into Redis but **never executed**.
2. **AI features have no key.** AI chat, agents, summarization, and the
   "warnings" panel all check for `GEMINI_API_KEY` / `OPENROUTER_API_KEY` /
   `SCITELY_API_KEY` and gracefully degrade when none are present. Currently
   they're degrading because nothing is configured.
3. **OAuth client IDs are not set.** Google login uses placeholder
   `'not-configured'`; GitHub login redirects to `${API_URL}/api/v1/auth/github/`
   which itself returns 503 when `GITHUB_CLIENT_ID` is missing.
4. **Email verification is required to log in after registration**, but no
   SMTP credentials are set on Render — so the verification email is never
   delivered (the backend silently swallows the exception).
5. A **stub `package.json` and `app/` directory at the repo root** (created by
   v0 scaffolding) conflict with the real Next.js app under `/frontend`. They
   don't break Vercel today (because the Vercel root is set to `/frontend`)
   but they will confuse contributors and break local `npm install`.

---

## 2. P0 — must fix before anything else works

### 2.1 Frontend (Vercel) env vars
Set in **Vercel project → Settings → Environment Variables**:

| Variable | Value |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | `https://synapse-api-oyld.onrender.com` |
| `NEXT_PUBLIC_WS_URL` | `wss://synapse-api-oyld.onrender.com/ws` |
| `NEXT_PUBLIC_APP_URL` | `https://synapse-app-six.vercel.app` |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | *(your Google OAuth Web Client ID)* |
| `NEXT_PUBLIC_SENTRY_DSN` | *(optional — Sentry frontend DSN)* |
| `NEXT_PUBLIC_POSTHOG_KEY` | *(optional — PostHog analytics)* |
| `NEXT_PUBLIC_POSTHOG_HOST` | `https://app.posthog.com` |

After saving, **redeploy** (Vercel does not pick up env changes until the next
build).

### 2.2 Backend (Render web service) env vars
Set in **Render → service → Environment**:

| Variable | Value | Notes |
| --- | --- | --- |
| `DJANGO_SETTINGS_MODULE` | `config.settings.production` | required |
| `SECRET_KEY` | *(50+ char random)* | required, see `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DEBUG` | `False` | required |
| `ALLOWED_HOSTS` | `synapse-api-oyld.onrender.com` | required |
| `DATABASE_URL` | *(from Render Postgres)* | required |
| `REDIS_URL` | *(from Render Redis or Upstash)* | required, must match Celery URL |
| `CELERY_BROKER_URL` | same as `REDIS_URL` | required |
| `CELERY_RESULT_BACKEND` | same as `REDIS_URL` | required |
| `FRONTEND_URL` | `https://synapse-app-six.vercel.app` | required |
| `CORS_ALLOWED_ORIGINS` | `https://synapse-app-six.vercel.app` | required |
| `CSRF_TRUSTED_ORIGINS` | `https://synapse-app-six.vercel.app` | required |
| `JWT_SIGNING_KEY` | *(random — different from SECRET_KEY)* | required |
| `GOOGLE_CLIENT_ID` | *(Google OAuth)* | optional but needed for Google login |
| `GITHUB_CLIENT_ID` | *(GitHub OAuth App)* | optional but needed for GitHub login |
| `GITHUB_CLIENT_SECRET` | *(GitHub OAuth App)* | optional but needed for GitHub login |
| `GITHUB_REDIRECT_URI` | `https://synapse-api-oyld.onrender.com/api/v1/auth/github/callback/` | must match what's configured in the GitHub OAuth App |
| `GEMINI_API_KEY` | *(from Google AI Studio — free)* | enables AI chat / agents |
| `EMAIL_HOST_USER` | `apikey` *(if SendGrid)* or your SMTP user | for verification emails |
| `EMAIL_HOST_PASSWORD` | *(SendGrid API key or SMTP password)* | for verification emails |
| `EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` | switch from console backend |
| `DEFAULT_FROM_EMAIL` | `noreply@yourdomain.com` | sender address |

### 2.3 Backend — Celery worker + beat on Render
This is the **single biggest reason** automation/scraping doesn't run in
production. The web service can only handle HTTP requests; long-running tasks
must execute somewhere.

Create **two new Render services**, both pointing at the same git repo and
using the existing `backend/Dockerfile` (override the start command):

1. **synapse-worker** (Background Worker)
   - Start command:
     `celery -A config worker -l INFO --concurrency=2 -Q default,scraping,nlp,embeddings,agents,slow_scraping`
   - Same env vars as web service.
2. **synapse-beat** (Background Worker)
   - Start command:
     `celery -A config beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler`
   - Same env vars as web service.

Once these are running, the `▶ Run` button on workflows, scraping schedules,
the daily briefing, and the weekly digest will all start firing.

### 2.4 OAuth provider setup
1. **Google** — in Google Cloud Console → APIs & Services → Credentials:
   - OAuth 2.0 Client ID type **Web application**
   - Authorized JavaScript origins: `https://synapse-app-six.vercel.app`
   - Authorized redirect URIs: *(Google access-token flow — none needed)*
   - Copy Client ID into both `NEXT_PUBLIC_GOOGLE_CLIENT_ID` (Vercel) and
     `GOOGLE_CLIENT_ID` (Render).

2. **GitHub** — in GitHub → Settings → Developer settings → OAuth Apps:
   - Homepage URL: `https://synapse-app-six.vercel.app`
   - Authorization callback URL:
     `https://synapse-api-oyld.onrender.com/api/v1/auth/github/callback/`
   - Copy Client ID + Secret into Render (`GITHUB_CLIENT_ID`,
     `GITHUB_CLIENT_SECRET`, `GITHUB_REDIRECT_URI`).

### 2.5 Code fixes (this PR)
- **Delete** the placeholder root `/package.json` (only contained
  `rehype-raw`) and any stray root `/app/` directory. They are noise that
  confuses contributors and could break local installs.
- **Fix** the auth layout: replace the corrupted `��` glyph (line 145) with
  a proper `©` so the footer copyright renders correctly.
- **Disable** the Google sign-in button when `NEXT_PUBLIC_GOOGLE_CLIENT_ID`
  is not configured — currently it opens a popup that fails silently with no
  error message to the user.
- **Disable + label** the GitHub button when `NEXT_PUBLIC_API_URL` is not set.
- **Add error-query-param handling** to the login page — when GitHub OAuth
  fails, the backend redirects to `/login?error=<code>` and we should display
  the error rather than show a clean page.
- **Show a clearer message after registration** so the user knows to check
  their inbox (the toast disappears in 3.5s; the page itself should also state
  it).

### 2.6 Bigger UX fixes for auth (still P0)
- Auth pages currently render fine on mobile but the **dashboard layout
  forces a redirect to `/login` if not authenticated** *before* Zustand
  finishes rehydrating its persisted state — on slow devices this races and
  briefly flashes the dashboard. Already partially mitigated by `_appMounted`
  but should also gate on the persist hydration callback.

---

## 3. P1 — feature wiring fixes

### 3.1 Automation (Celery workflows)
After 2.3 (worker + beat on Render), the workflow `▶ Run` button will work.
Code-side issues to clean up:
- The existing `EditWorkflowModal`, `ScheduleModal`, `AnalyticsModal`, and
  `TemplatesModal` are **duplicated** under both
  `frontend/src/app/(dashboard)/automation/` and
  `frontend/src/components/modals/`. Pick one location (recommend
  `components/modals/`) and delete the duplicates to avoid drift.
- The Celery task router in `base.py` references `apps.organizations` but
  there is no `apps/organizations/tasks.py` matched by any wildcard — fine
  but worth a verification.

### 3.2 AI Chat / Agents / Personalization "warnings"
These all flow through the same code path:
- Frontend calls `GET /api/v1/users/ai-keys/` (`useApiKeyStatus.ts`)
- Backend reads keys from user preferences + env vars and returns a
  `warnings[]` array consumed by `ApiKeyWarningBanner.tsx`.

Fix path:
1. Set `GEMINI_API_KEY` in Render env (cheapest — Gemini has a generous free
   tier). The "warnings" banner will turn from `error` to `info` immediately.
2. Verify `apps.core.views_chat.py` falls back to env var when
   `user.preferences.gemini_api_key` is not set (it does today; just confirm).
3. The Settings → API Keys page lets users self-serve their own keys — make
   sure that page is accessible after the auth fixes from §2.

### 3.3 Scraping (HackerNews / arXiv / GitHub / YouTube / X)
Same root cause as 3.1 — without a Celery worker on the `scraping` queue,
nothing scrapes. After §2.3, scraping will run on the `scraping` and
`slow_scraping` queues automatically. The Beat schedule already triggers
`scrape_all` etc.

Optional improvement: **add an admin `▶ Run scrape now` button** to the home
page so the user can trigger a one-off scrape without waiting for cron. Not
critical.

### 3.4 AI Engine (FastAPI service)
The `/ai_engine` FastAPI service is referenced as `AI_SERVICE_URL` in env
but is **not deployed anywhere** in the current Render account. Two options:

- **Cheap option**: skip it. The Django backend already has a fallback path
  in `apps/core/views_chat.py` that calls Gemini directly. The FastAPI service
  is only required for advanced agent tooling (RAG, multi-step reasoning).
- **Full option**: deploy `ai_engine/Dockerfile` as a third Render service
  named `synapse-ai`, set `AI_SERVICE_URL=https://synapse-ai.onrender.com`
  on the backend.

Recommend deferring — get auth + automation working first.

---

## 4. P1 — Responsiveness sweep

The codebase already has reasonable mobile considerations (`MobileBottomNav`,
`md:hidden` patterns, fluid auth panel) but several pages need attention.

| Page / component | Issue | Fix |
| --- | --- | --- |
| `Navbar.tsx` | Right-side cluster (org switcher, AI toggle, theme, bell, plan badge, avatar) overflows below 360 px | Hide non-essential icons under `sm:`, collapse plan badge under `md:` |
| `Sidebar.tsx` mobile drawer | OK, but bottom-nav `tabs` array reuses `MessageSquare` for "Search" — looks like a bug | Replace with `Search` icon |
| `(dashboard)/automation/page.tsx` | Workflow cards use `grid-cols-3` with no breakpoint | Change to `grid-cols-1 md:grid-cols-2 xl:grid-cols-3` |
| `(dashboard)/agents/page.tsx` | Two-column split crashes on mobile | Stack to single column with tabs under `lg:` |
| `(dashboard)/chat/page.tsx` | Sidebar of conversations is always visible, eating screen real estate on mobile | Slide-out drawer with toggle button on mobile |
| `(dashboard)/billing/page.tsx` | Pricing grid 3-up doesn't reflow | `grid-cols-1 md:grid-cols-3` |
| `(dashboard)/feed/page.tsx` filters bar | Wraps awkwardly | Horizontal scroll on `<md` |
| Modals (`EditWorkflowModal`, `ScheduleModal`, `TemplatesModal`) | Fixed widths on mobile | `max-w-[calc(100vw-2rem)]` and `max-h-[90vh] overflow-y-auto` |

I'll work through these in a single responsive sweep PR after auth is fixed.

---

## 5. P2 — Code quality / housekeeping

These don't block any feature but should be cleaned up:

- Delete the duplicate `automation/AnalyticsModal.tsx` /
  `automation/EditWorkflowModal.tsx` etc. (kept once in `components/modals/`).
- `frontend/src/components/layout/Sidebar.tsx` declares an unused `BOTTOM_NAV`
  constant — dead code.
- `frontend/src/components/Providers.tsx` falls back to
  `'not-configured'` for the Google client ID — replace with `null` and
  conditionally render `GoogleOAuthProvider` so the Google button can be
  disabled rather than fail silently.
- `next.config.mjs` tries to upload Sentry source maps even when no DSN is
  set; the current guards work but emit a warning during `next build`. Wrap
  the entire `withSentryConfig` call in `process.env.NEXT_PUBLIC_SENTRY_DSN
  ? withSentryConfig(...) : nextConfig`.
- The `_workflows_temp/` folder contains GitHub Actions workflows that
  weren't committed because the v0 GitHub token lacked the `workflow` scope.
  The user's already-committed `.github/workflows/{ci,cd,security}.yml` may
  duplicate them — diff and pick one set.
- `.env.example` lists 10 `GEMINI_API_KEY_N` variables — overkill. Trim to 3.
- `package.json` at repo root only contains `{"dependencies": {"rehype-raw":
  "^7.0.0"}}` — dead, delete.

---

## 6. Suggested execution order

1. **Set Vercel env vars** (§2.1) → redeploy → verify the login page no
   longer crashes when you click Google.
2. **Set Render env vars** (§2.2) → redeploy backend → test
   `POST /api/v1/auth/login/` with curl.
3. **Land code fixes** (§2.5, §2.6) — small PR, this is what I'll start
   with now.
4. **Configure GitHub & Google OAuth apps** (§2.4).
5. **Add Celery worker + beat services on Render** (§2.3).
6. **Get an `GEMINI_API_KEY`** (§3.2) and add it to Render.
7. **Responsive sweep** (§4) — one PR over the top 8 pages.
8. **Optional**: deploy AI engine (§3.4).
9. **Cleanup PR** (§5).

---

## 7. Things v0 cannot do for you

Be aware these require **you** to take action — I cannot do them from inside
the v0 sandbox:

- Set Vercel/Render env vars (must be done in their dashboards).
- Create the Render Celery worker/beat services.
- Create OAuth apps in Google Cloud Console / GitHub.
- Buy / generate API keys (Gemini, SendGrid, Stripe, etc.).
- Run the actual deploy (Vercel will auto-deploy on push; Render needs you to
  click Deploy or trigger via webhook).

I will fix all of the **code-side** issues (§2.5, §2.6, §3.1 dedup, §4
responsive, §5 cleanup) in subsequent PRs.
