# Synapse Project — Complete Code Review Task List

> Generated: 2026-04-05 | Status: All issues pending resolution
> Sections: Security · Backend · Frontend · AI Engine · Infrastructure · Scraper

---

## Legend
- 🔴 **CRITICAL** — Security risk / breaks production
- 🟠 **HIGH** — Significant bug or bad practice
- 🟡 **MEDIUM** — Quality / maintainability issue
- 🟢 **LOW** — Polish / minor improvement

---

## 1. 🔴 CRITICAL — Security Issues

| # | Area | File | Issue | Action |
|---|------|------|-------|--------|
| SEC-01 | Backend | `config/settings/base.py` | `SECRET_KEY` falls back to `'django-insecure-change-in-production'` — silent default instead of raising `ImproperlyConfigured` | Raise exception if SECRET_KEY not set |
| SEC-02 | Backend | `config/settings/test.py` | Hardcoded DB credentials (`synapse_user`, `synapse_pass`) committed to version control | Move to env vars / CI secrets |
| SEC-03 | Backend | `conftest.py` | Unconditionally overrides `DB_HOST`/`DB_PORT` env vars — dangerous if run in production environment | Guard with env check |
| SEC-04 | Backend | `config/settings/test.py` | MD5 password hasher used in tests — MD5 is broken, test data could leak real password patterns | Use a dummy hasher that doesn't hash |
| SEC-05 | AI Engine | `agents/doc_tools.py` | `_doc_dir()` builds file paths using `user_id` with no sanitisation — path traversal risk | Sanitise / validate user_id, use `pathlib` safely |
| SEC-06 | AI Engine | `agents/project_tools.py` | `_create_project()` generates code from arbitrary `feature` list — no whitelist validation | Validate features against allowed enum |
| SEC-07 | AI Engine | `agents/tools.py` | `_read_document()` downloads from arbitrary user-supplied URLs with no size limit | Add max file size check before download |
| SEC-08 | AI Engine | `agents/tools.py` | `_run_python_code()` sandbox uses `_SAFE_BUILTINS_KEYS` / `_SAFE_MODULES` whitelist — insufficient for preventing escapes | Audit whitelist, consider Docker-based sandboxing |
| SEC-09 | Infra | `infrastructure/pgbouncer/pgbouncer.ini` | `auth_type = md5` — outdated; PostgreSQL 14+ prefers `scram-sha-256` | Update auth_type |
| SEC-10 | Infra | `.env.example` | `DEBUG=True` present — never safe to leave as default | Set `DEBUG=False` as default, add comment |
| SEC-11 | Infra | `infrastructure/nginx/conf.d/synapse.conf` | Admin IP CIDR blocks are placeholder — comment says "Replace with actual office/VPN CIDRs" | Document and enforce in deployment guide |
| SEC-12 | Infra | `infrastructure/nginx/conf.d/synapse.conf` | CSP header allows `unsafe-inline` for styles | Refactor to use nonces or hashes |

---

## 2. 🔴 CRITICAL — Bugs That Break Functionality

| # | Area | File | Issue | Action |
|---|------|------|-------|--------|
| BUG-01 | Frontend | Multiple hooks/components | `import api from '@/utils/api'` (default import) but `api` is a **named export** — will be `undefined` at runtime | Change to `import { api } from '@/utils/api'` in: `useApiKeyStatus.ts`, `useVoiceInput.ts`, `BookmarkButton.tsx` |
| BUG-02 | Frontend | `app/(dashboard)/layout.tsx` | `onMenuClick` prop passed to `<Navbar>` but component param is `onMobileMenuClick` — callback never fires | Align prop name |
| BUG-03 | Frontend | `components/cards/VideoCard.tsx` | `JSON.parse(topics.replace(/'/g, '"'))` — fragile and will throw on malformed data | Use safe parse with try/catch and validate |
| BUG-04 | AI Engine | `main.py` | `_stream()` generator inside `/agents/run` and `/chat` endpoints mixes sync generator with async function — incorrect async pattern | Rewrite as `async def` with `yield` |
| BUG-05 | AI Engine | `rag/memory.py` | `_load_history()` silently returns empty list on Redis error — chat history lost without any user notification | Log error prominently; surface failure state |
| BUG-06 | Backend | `config/settings/base.py` | `CONN_MAX_AGE = 0` — no DB connection pooling; each request opens a new connection, severe performance degradation under load | Set to `60` or use PgBouncer properly |
| BUG-07 | Infra | `scraper/settings.py` | Redis URL defaults to port `6380` but `.env.example` and all services use port `6379` — **port mismatch** | Fix default to `redis://localhost:6379/0` |

---

## 3. 🟠 HIGH — Configuration Problems

| # | Area | File | Issue | Action |
|---|------|------|-------|--------|
| CFG-01 | Backend | `config/settings/development.py` | `CORS_ALLOW_ALL_ORIGINS = True` — allows any origin in dev, inconsistent with production model | Restrict to `localhost` origins explicitly |
| CFG-02 | Backend | `config/settings/base.py` | All third-party API keys (`GOOGLE_CLIENT_ID`, `AWS_ACCESS_KEY_ID`, `SENDGRID_API_KEY`) default to empty string `''` — silent failures | Add startup validation / warnings if keys missing |
| CFG-03 | Backend | `config/settings/base.py` | OpenTelemetry imports inside `if OTEL_ENABLED:` block at module level — if packages missing, settings import partially fails | Wrap in try/except ImportError |
| CFG-04 | Backend | `config/settings/production.py` | `ALLOWED_HOSTS` split on comma but doesn't strip whitespace — `'example.com, other.com'` will fail silently | Add `.strip()` to each element |
| CFG-05 | Backend | `config/settings/production.py` | Sentry only initialises `if SENTRY_DSN:` — production errors not tracked if DSN is missing | Make SENTRY_DSN required in production, warn loudly |
| CFG-06 | Backend | `config/settings/base.py` | `SESSION_ENGINE = cache` — if Redis crashes, all sessions are lost with no fallback | Switch to `cached_db` backend |
| CFG-07 | Backend | `config/settings/test.py` | `CELERY_TASK_ALWAYS_EAGER = True` — async behaviour not tested; race conditions hidden | Add separate async integration tests |
| CFG-08 | Infra | `docker-compose.yml` | No `healthcheck:` blocks on any service — Docker has no way to know if services are ready | Add healthchecks to all services |
| CFG-09 | Infra | `.env.example` | `EMBEDDING_PROVIDER=local` but Pinecone keys also provided — conflicting / confusing configuration | Add comments clarifying which vars belong to which provider |
| CFG-10 | Infra | `docker-compose.monitoring.yml` | Prometheus config references `postgres_exporter`, `redis_exporter`, `nginx_exporter` but none are defined as services | Add exporter services or remove from prometheus.yml |
| CFG-11 | Infra | Multiple | `DOMAIN`, `GRAFANA_URL`, `SLACK_WEBHOOK_URL` used in configs but **not defined** in `.env.example` | Add all missing vars to `.env.example` |
| CFG-12 | Infra | `infrastructure/docker/postgres/init.sql` | Does not create the `synapse` user or database — incomplete initialisation | Add `CREATE USER` / `CREATE DATABASE` statements |
| CFG-13 | Infra | `infrastructure/nginx/conf.d/synapse.conf` | `${DOMAIN}` variable used in nginx config but never documented or set | Document and add to `.env.example` |
| CFG-14 | Infra | `infrastructure/pgbouncer/pgbouncer.ini` | PgBouncer is fully configured but **not included as a service** in any docker-compose file | Add pgbouncer service to `docker-compose.prod.yml` |
| CFG-15 | Frontend | `next.config.mjs` | `ignoreBuildErrors: true` and `ignoreDuringBuilds: true` — masks real TypeScript/ESLint errors in CI | Remove both flags; fix underlying errors |

---

## 4. 🟠 HIGH — Missing Error Handling

| # | Area | File | Issue | Action |
|---|------|------|-------|--------|
| ERR-01 | Frontend | `utils/analytics.ts` | All catch blocks are empty `catch {}` — PostHog errors silently swallowed | Add at least `console.warn` or Sentry capture |
| ERR-02 | Frontend | `contexts/OrganizationContext.tsx` | `console.error()` called on API failure but component continues silently | Show user-facing error state |
| ERR-03 | Frontend | `hooks/useVoiceInput.ts` | `getUserMedia` error doesn't distinguish `AbortError`, `SecurityError`, `NotFoundError` | Handle each DOMException type specifically |
| ERR-04 | AI Engine | `agents/tools.py` | Tavily API key accessed with `os.environ.get()` but no validation at call time — fails with cryptic error | Validate key exists before making API call |
| ERR-05 | AI Engine | `agents/router.py` | `BudgetExceededError` imported inside functions to avoid circular import — fragile pattern | Restructure imports to eliminate circular dependency |
| ERR-06 | AI Engine | `rag/memory.py` | `_get_redis_client()` raises `RuntimeError` on failure — no graceful degradation for non-critical cache | Return `None` and handle absence gracefully |
| ERR-07 | AI Engine | `middleware/moderation.py` | API failure silently allows content through — moderation bypass on network error | Fail closed (block) or surface error clearly |
| ERR-08 | AI Engine | `agents/research_agent.py` | `plan_sub_questions()` return not checked — if it returns empty list, pipeline continues silently | Add guard: raise or return early if empty |
| ERR-09 | Backend | `config/settings/production.py` | `PiiRedactionFilter` class referenced in logging config — not verified to exist at import time | Add import check and test |

---

## 5. 🟡 MEDIUM — Code Quality & Bad Practices

| # | Area | File | Issue | Action |
|---|------|------|-------|--------|
| QA-01 | Frontend | `utils/helpers.ts` + `utils/cn.ts` | `cn()` function **duplicated** in both files | Delete one, keep `cn.ts`, update all imports |
| QA-02 | Frontend | `components/cards/ArticleCard.tsx` | `(article as any).excerpt` unsafe cast — `excerpt` not in Article type | Add `excerpt?: string` to Article interface |
| QA-03 | Frontend | `app/(dashboard)/page.tsx` | `StatCard` component uses `any` type for all props | Define proper `StatCardProps` interface |
| QA-04 | Frontend | `hooks/useTextToSpeech.ts` | Voice selection by checking `name.includes('Natural')` — fragile across browsers/OS | Use a more robust voice selection strategy |
| QA-05 | Frontend | `components/cards/RepositoryCard.tsx` | `contentType="repository"` passed to bookmark but API may expect `"github"` | Verify correct content type string with backend API |
| QA-06 | Frontend | `app/(dashboard)/feed/page.tsx` | Polling intervals (15s, 10s, 3min) as magic numbers inline | Extract to named constants |
| QA-07 | Frontend | `components/Providers.tsx` | `googleClientId` passed even if it is empty string `''` — should guard | Add `if (googleClientId)` guard |
| QA-08 | Frontend | `components/layout/OrgSwitcher.tsx` | Manual pluralization logic inline | Use `Intl.PluralRules` or a utility |
| QA-09 | Frontend | `hooks/useOnboarding.ts` | Manual error extraction instead of using existing `normaliseApiError()` | Refactor to use shared error utility |
| QA-10 | Frontend | `hooks/useNotificationSocket.ts` | `(ws as any)._ping` stores property on WebSocket using `any` cast | Use a wrapper class or `Map` to track ping state |
| QA-11 | AI Engine | `agents/base.py` | `_build_llm()` is 117 lines with nested try/except — too complex | Refactor into provider-specific factory methods |
| QA-12 | AI Engine | `agents/base.py` | `run()` and `stream()` share almost identical logic — DRY violation | Extract shared logic into `_execute()` helper |
| QA-13 | AI Engine | `agents/executor.py` | `_get_default_agent()` not cached — called repeatedly in loops | Cache result with `functools.lru_cache` or instance var |
| QA-14 | AI Engine | `agents/executor.py` | `tiktoken` imported inside `_estimate_tokens()` function body | Move import to module level |
| QA-15 | AI Engine | `agents/executor.py` | `max_workers=1` hardcoded in thread pool executor | Make configurable via env var |
| QA-16 | AI Engine | `agents/doc_tools.py` | `_generate_pdf()` is 163+ lines, `_generate_ppt()` is 290+ lines — unmaintainable | Extract into dedicated document builder classes |
| QA-17 | AI Engine | `agents/project_tools.py` | Template functions (`_django_template`, `_fastapi_template`, etc.) are heavily repetitive | Use base template system with substitution |
| QA-18 | AI Engine | `agents/tools.py` | HTTP client created inline per request instead of reusing session | Use `httpx.AsyncClient` as a shared session |
| QA-19 | AI Engine | `agents/tools.py` | `_fetch_articles()` Django ORM queries may cause N+1 | Add `select_related`/`prefetch_related` |
| QA-20 | AI Engine | `nlp/pipeline.py` | String slicing `[:2000]` hardcoded in multiple places | Define `MAX_TEXT_CHARS` constant and reuse |
| QA-21 | AI Engine | `nlp/ner.py` | spaCy model name `"en_core_web_sm"` hardcoded | Read from env var with fallback |
| QA-22 | AI Engine | `nlp/sentiment_analyzer.py` | `device=-1` (CPU only) hardcoded with no documentation | Add env var for device selection (`cpu`/`cuda`) |
| QA-23 | AI Engine | `nlp/summarizer.py` | `MAX_LENGTH=150`, `MIN_LENGTH=50` arbitrary fixed values | Make configurable per-request |
| QA-24 | AI Engine | `rag/chain.py` | `_build_llm()` duplicates provider logic already in `agents/base.py` | Consolidate into shared LLM factory |
| QA-25 | AI Engine | `rag/chain.py` | `SystemMessage`, `json` imported inside functions | Move to module level |
| QA-26 | AI Engine | `rag/pipeline.py` | `@lru_cache(maxsize=1)` on `get_rag_pipeline()` — config changes not reflected without restart | Document this limitation clearly or use factory pattern |
| QA-27 | Backend | `config/settings/production.py` | `# type: ignore` comments suppress list comprehension warnings — design smell | Refactor MIDDLEWARE/INSTALLED_APPS modification |
| QA-28 | Backend | `config/settings/base.py` | `CONN_MAX_AGE` comment references `# TASK-506-3` — stale task reference in code | Remove task reference, add proper comment |
| QA-29 | Backend | `config/settings/base.py` | `CELERY_BROKER_URL` defaults to `redis://localhost:6379/1` — assumes Redis available locally | Document requirement clearly |

---

## 6. 🟡 MEDIUM — Missing Features / Incomplete Implementations

| # | Area | File | Issue | Action |
|---|------|------|-------|--------|
| INC-01 | AI Engine | `agents/research_agent.py` | `search_github()` makes raw HTTP without rate-limit handling | Add retry + backoff for GitHub API |
| INC-02 | AI Engine | `agents/research_agent.py` | `research_sub_question()` doesn't verify or deduplicate results from multiple sources | Add deduplication and source ranking |
| INC-03 | AI Engine | `agents/research_agent.py` | `run_research_pipeline()` tightly coupled to Django ORM — not reusable in standalone mode | Decouple via repository/adapter pattern |
| INC-04 | AI Engine | `agents/tools.py` | ArXiv XML parsing has no namespace handling — fragile to API changes | Use proper XML namespace parsing |
| INC-05 | AI Engine | `agents/tools.py` | `_generate_chart()` uses matplotlib without memory cleanup — leak risk under load | Call `plt.close()` after rendering |
| INC-06 | AI Engine | `middleware/rate_limit.py` | Redis-unavailable scenario not consistently handled by callers | Add circuit breaker pattern |
| INC-07 | AI Engine | `nlp/language_detector.py` | Short text (< 5 words) auto-assumed to be English with no confidence score | Return low-confidence result, don't assume |
| INC-08 | AI Engine | `nlp/keyword_extractor.py` | Both KeyBERT and YAKE use hardcoded parameters — no request-level configuration | Add parameter overrides |
| INC-09 | AI Engine | `embeddings/embedder.py` | Empty strings in `embed_batch()` return zero vectors — misleading in retrieval | Filter out empty strings before embedding |
| INC-10 | AI Engine | `embeddings/embedder.py` | Truncation hardcoded at 8192 chars — may not match actual model max tokens | Map truncation to model-specific token limits |
| INC-11 | Backend | `config/settings/base.py` | AWS S3 silently falls back to local storage if `USE_S3` not set | Log warning when falling back |
| INC-12 | Backend | `config/settings/base.py` | Email backend not validated — SendGrid not tested during startup | Add startup check for email configuration |
| INC-13 | Infra | `infrastructure/nginx/conf.d/synapse.conf` | Rate limiting zones hardcoded (`30r/m`, `10r/m`, `60r/m`) | Make configurable or at least documented |
| INC-14 | Infra | All docker-compose files | No liveness/readiness probes for Celery workers or FastAPI service | Add health endpoint to AI engine; document probe config |
| INC-15 | Scraper | `scraper/settings.py` | `HTTPCACHE_ENABLED = False` with dev comment — dev setting committed to production config | Move cache enable to env var |

---

## 7. 🟡 MEDIUM — Dead Code / Unused Code / Junk

| # | Area | File | Issue | Action |
|---|------|------|-------|--------|
| DEAD-01 | Frontend | `utils/cn.ts` | Entire file is duplicate of `cn()` in `helpers.ts` | Delete file or remove from `helpers.ts` |
| DEAD-02 | Backend | `config/settings/production.py` | `if DEBUG:` check in logging formatter — DEBUG is always `False` in production; dead branch | Remove dead branch |
| DEAD-03 | AI Engine | `agents/executor.py` | `_model_router` initialised in `__init__` but never used in class | Remove unused attribute |
| DEAD-04 | AI Engine | `main.py` | `_uuid` alias imported but usage unclear — may be unused | Audit and remove if unused |
| DEAD-05 | AI Engine | `agents/registry.py` | Tool registration silently swallows exceptions — errors lost | Collect and surface registration errors |
| DEAD-06 | Backend | `config/settings/base.py` | Both `DATABASE_URL` and individual `DB_*` vars present — redundant; only one likely used | Remove unused pattern, document which is used |
| DEAD-07 | Scraper | `scraper/spiders/twitter_spider.py` | Likely references deprecated Nitter — verify and remove dead scraping logic | Audit and rewrite or remove spider |

---

## 8. 🟢 LOW — Polish & Minor Improvements

| # | Area | File | Issue | Action |
|---|------|------|-------|--------|
| POL-01 | Frontend | `components/ErrorBoundary.tsx` | `console.error()` in `componentDidCatch` — should report to Sentry | Integrate Sentry `captureException` |
| POL-02 | Frontend | Multiple | `console.error()` / `console.log()` left in production components | Replace with Sentry or remove |
| POL-03 | AI Engine | `middleware/safety.py` | Jailbreak regex patterns hardcoded inline — hard to maintain | Move to config file or database |
| POL-04 | AI Engine | `nlp/cleaner.py` | Whitespace normalisation regex doesn't handle all Unicode whitespace characters | Use `\s` with `re.UNICODE` flag |
| POL-05 | AI Engine | `nlp/topic_classifier.py` | `MIN_CONFIDENCE = 0.20` is very low — many false positives likely | Tune or make configurable |
| POL-06 | AI Engine | `agents/tools.py` | `_HTTP_TIMEOUT = 30` hardcoded | Move to env var `HTTP_TIMEOUT` |
| POL-07 | Backend | `.pre-commit-config.yaml` | Bandit checks scraper/ but flake8 may not exclude it consistently | Align both tool configs |
| POL-08 | Infra | `infrastructure/pgbouncer/pgbouncer.ini` | `server_reset_query = DISCARD ALL` needs validation with Django's transaction handling | Document and verify compatibility |
| POL-09 | Infra | `infrastructure/nginx/conf.d/synapse.conf` | Flower `.htpasswd` file required but not documented how to generate | Add generation command to DEPLOYMENT.md |
| POL-10 | AI Engine | `requirements.txt` | `pymupdf` and `matplotlib` included unconditionally — heavy dependencies for optional features | Make optional/extras |

---

## Summary Dashboard

| Category | Critical 🔴 | High 🟠 | Medium 🟡 | Low 🟢 | Total |
|----------|------------|---------|-----------|--------|-------|
| Security (SEC) | 12 | — | — | — | **12** |
| Bugs (BUG) | 7 | — | — | — | **7** |
| Configuration (CFG) | — | 15 | — | — | **15** |
| Error Handling (ERR) | — | 9 | — | — | **9** |
| Code Quality (QA) | — | — | 29 | — | **29** |
| Incomplete (INC) | — | — | 15 | — | **15** |
| Dead Code (DEAD) | — | — | 7 | — | **7** |
| Polish (POL) | — | — | — | 10 | **10** |
| **TOTAL** | **19** | **24** | **51** | **10** | **104** |

---

## Suggested Fix Order (Sprints)

### Sprint 1 — Security & Critical Bugs (SEC + BUG)
Fix all SEC-* and BUG-* items. These are production risks.

### Sprint 2 — Configuration & Error Handling (CFG + ERR)
Fix all CFG-* and ERR-* items. These prevent proper deployment and silent failures.

### Sprint 3 — Code Quality & Incomplete Features (QA + INC)
Tackle QA-* and INC-* items. These improve maintainability and correctness.

### Sprint 4 — Cleanup (DEAD + POL)
Remove dead code and apply polish items.
