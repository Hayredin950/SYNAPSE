# SYNAPSE — Deployment

Everything below has been run and verified, except where explicitly marked
**untested**.

---

## 1. Local development

### Start the data layer

```bash
docker compose -f docker-compose.local.yml up -d
docker compose -f docker-compose.local.yml ps    # both must say (healthy)
```

Postgres binds host port **5433** and Redis **6380** — not the defaults — so the
stack does not collide with a Postgres or Redis you already run locally.
Postgres reports healthy only once the `vector` extension exists, so migrations
can never start against a database that lacks pgvector.

### Configure the backend

Create `backend/.env` (never commit it):

```bash
SECRET_KEY=<generate below>
DJANGO_SETTINGS_MODULE=config.settings.development
DATABASE_URL=postgresql://synapse_user:synapse_dev_password@127.0.0.1:5433/synapse_db
REDIS_URL=redis://127.0.0.1:6380/0
CELERY_BROKER_URL=redis://127.0.0.1:6380/0
```

Generate a key:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

> `config/settings/development.py` defaults `DB_PORT` to 5432. Always set
> `DATABASE_URL` (or `DB_PORT=5433`) or you will hit the local Postgres instead
> of the container.

### Migrate and run

```bash
cd backend
python manage.py migrate          # verified: full schema builds on pgvector 0.8.2
python manage.py createsuperuser
python manage.py runserver
```

Frontend, in a second terminal:

```bash
cd frontend
npm install
npm run dev                       # http://localhost:3000
```

Celery, in a third (only needed for scraping, agents, scheduled work):

```bash
cd backend
celery -A config worker -l info
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

Run exactly **one** beat process. Two will fire every scheduled task twice.

---

## 2. What the app needs to be useful

| Variable | Required? | Notes |
|---|---|---|
| `SECRET_KEY` | **yes** | Boot fails without it, by design |
| `DATABASE_URL` | **yes** | Postgres with pgvector |
| `REDIS_URL` | **yes** | Cache, Celery broker, WebSockets |
| `GROQ_API_KEY` | for AI | Primary provider — 14,400 req/day free |
| `NVIDIA_API_KEY` | optional | First fallback; tool-calling models |
| `GEMINI_API_KEY` | optional | Second fallback; 1M context |
| `EMAIL_HOST_PASSWORD` | for signup | Without it, verification email silently no-ops |
| `ALLOWED_HOSTS` | production | Backend hostnames only, never the frontend |
| `CORS_ALLOWED_ORIGINS` | production | Frontend origins |
| `NEXT_PUBLIC_API_URL` | production | **Baked in at build time** — rebuild to change |

Configure at least one AI provider. With several, requests fail over
automatically (see §4).

---

## 3. Production

The app is a long-running ASGI service (Django Channels), needs Postgres with
pgvector, and its ML dependencies (`torch`, `transformers`,
`sentence-transformers`) want ~2GB RAM. Serverless platforms and 512MB free
tiers will not run it.

Workable hosts: any VPS with 4GB+ RAM, or Oracle Cloud's Always Free ARM
instance (4 vCPU / 24GB). On ARM, `backend/requirements.txt:1` points at x86
PyTorch wheels and needs adjusting.

Production checklist:

1. `DJANGO_SETTINGS_MODULE=config.settings.production`
2. Real `SECRET_KEY`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`
3. `DISABLE_RATE_LIMITS` unset or `false` — **this now defaults to `false`;
   it previously defaulted to `true`, which silently disabled all throttling**
4. TLS terminated at a reverse proxy; `SECURE_SSL_REDIRECT` is already on
5. Run web, worker, and beat as separate processes
6. `python manage.py collectstatic` (WhiteNoise serves them)

**Untested:** `docker-compose.yml` and `docker-compose.prod.yml` build the
application images. Those builds have not been run to completion here — the ML
layer takes a long time to compile. Verify locally before relying on them.

---

## 3a. CI/CD

Three workflows run on `main`:

| Workflow | Trigger | What it does |
|---|---|---|
| `ci.yml` | push, PR | lint, pytest against pgvector + Redis, Jest, build all 3 images |
| `security.yml` | PR, weekly | SAST, dependency scan, secret scan, Trivy, ZAP (scheduled) |
| `cd.yml` | push to `main` | build + push images to GHCR, then deploy **if enabled** |

### Deploys are off by default

`cd.yml`'s deploy job is skipped unless the repository variable
`DEPLOY_ENABLED` is `true`. Until you set it, every push still builds and
publishes images to GHCR — it just doesn't try to SSH anywhere. This is
deliberate: the job previously ran unconditionally and would fail on every push
without a host, and a permanently red pipeline is one nobody reads.

To turn deploys on — **Settings → Secrets and variables → Actions**:

*Variables*
| Name | Value |
|---|---|
| `DEPLOY_ENABLED` | `true` |
| `BUILD_PLATFORMS` | `linux/amd64,linux/arm64` — only for an ARM host |

*Secrets*
| Name | Notes |
|---|---|
| `SSH_HOST`, `SSH_USER`, `SSH_KEY` | target host; `SSH_PORT` optional (22) |
| `PRODUCTION_URL` | health check target, e.g. `https://your-domain.com` |
| `NEXT_PUBLIC_API_URL` | **baked into the frontend image at build time** |
| `SLACK_WEBHOOK_URL` | optional |

The job verifies these are set before doing anything, so a missing secret gives
a clear message rather than a failure deep inside the SSH step.

The host needs `/opt/synapse` containing `docker-compose.prod.yml`,
`infrastructure/`, and a populated `.env.prod`.

> Leave `BUILD_PLATFORMS` unset unless you need ARM. Building arm64 on an amd64
> runner goes through QEMU emulation, and for a torch image that can exceed the
> 6-hour job limit.

### Image naming

CD publishes to `ghcr.io/<owner-lowercase>/synapse-{backend,frontend,ai-engine}`
and `docker-compose.prod.yml` reads `IMAGE_OWNER` and `IMAGE_TAG` to construct
exactly those names. **The two must stay in sync** — they previously did not,
which would have failed every `docker compose pull` with "image not found".

To pull manually on the host:

```bash
export IMAGE_OWNER=hayredin950
export IMAGE_TAG=latest        # or a specific commit SHA
docker compose -f docker-compose.prod.yml pull
```

### Render (free-tier lite blueprint)

`render.yaml` is a Blueprint for the **card-free lite stopgap** (§3d): a single
Docker web service on the free plan with `SYNAPSE_LITE=1` baked in, connected
to external Neon (Postgres+pgvector) and Upstash (Redis) URLs. It deliberately
contains **no** `databases:`/`keyvalue:` blocks — Render's own free Postgres
expires after 30 days and free Key Value is in-memory (data lost on restart),
so Neon + Upstash (free forever, no card) are used instead.

---

## 3b. Oracle Cloud ARM + Vercel + Brevo (recommended free stack)

This is the zero-cost production path, matching the app's real needs:

| Layer | Service | Cost |
|---|---|---|
| Compute | Oracle Cloud ARM Ampere A1 (4 vCPU / 24 GB) | free, forever |
| Database | Postgres + pgvector in Docker on the box | uses free 200 GB disk |
| Redis | Redis in Docker on the box | same |
| Frontend | Vercel Hobby | free |
| Email | Brevo SMTP | free, 300/day |
| DNS/TLS | DuckDNS + Let's Encrypt | free |

**Why this works on ARM:** PyPI ships `aarch64` wheels for torch 2.13.0
(cp311), so the ML stack builds natively on the box — no QEMU emulation, no
6-hour CI job. The CD pipeline therefore builds images **on the host**, not by
pulling amd64 images from GHCR (which would not run on ARM).

**Why DuckDNS does not serve the frontend:** DuckDNS only supports A/AAAA
records (no CNAME), and Vercel needs a CNAME. So the frontend keeps Vercel's
own `*.vercel.app` URL, and the DuckDNS hostname (A record → box IP) serves the
API, admin, AI engine and WebSockets. Vercel auto-provisions its own
Let's Encrypt certificate.

### Provisioning steps (one-time)

1. **Oracle Cloud** — create an Always Free Ampere A1 instance
   (Ubuntu 22.04/24.04, 4 vCPU/24 GB, 200 GB boot volume). Open inbound rules
   for TCP 22, 80, 443. Save the SSH key.
2. **DuckDNS** — register a hostname, e.g. `synapse` → `synapseai.duckdns.org`,
   and copy the token. (DuckDNS updates are not needed for the A record once
   the cron below runs; the IP is pinned to the box.)
3. **Vercel** — create a project from the `frontend/` directory, or
   `cd frontend && npx vercel --prod`. Set env vars:
   `NEXT_PUBLIC_API_URL=https://synapseai.duckdns.org`,
   `NEXT_PUBLIC_WS_URL=wss://synapseai.duckdns.org/ws`,
   `NEXT_PUBLIC_APP_URL=https://<project>.vercel.app`.
   Vercel provisions TLS automatically.
4. **Brevo** — sign up, copy the SMTP relay login + master key
   (SMTP settings page). These go into `.env.prod`.
5. **AI keys** — Groq (primary), NVIDIA NIM, Gemini (fallbacks). Free tiers.
6. **Bootstrap the box** — SSH in and run:

   ```bash
   bash <(curl -sL https://raw.githubusercontent.com/Hayredin950/SYNAPSE/main/scripts/oracle_bootstrap.sh)
   ```

   The script installs Docker, generates `.env.prod` (random secrets for
   Django/DB/Redis/Flower), wires DuckDNS + certbot, builds all images
   natively and starts the stack. **After it finishes, edit
   `/opt/synapse/.env.prod`** and add Brevo SMTP + AI keys, then restart:

   ```bash
   cd /opt/synapse
   nano .env.prod          # EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, GROQ_API_KEY, ...
   docker compose -f docker-compose.prod.yml restart backend celery_worker celery_beat
   docker compose -f docker-compose.prod.yml exec backend python manage.py createsuperuser
   ```

7. **Enable automated deploys** — set these GitHub Actions **secrets/vars**
   (Settings → Secrets and variables → Actions):

   *Variables*
   | Name | Value |
   |---|---|
   | `DEPLOY_ENABLED` | `true` |
   | `PRODUCTION_URL` | `https://synapseai.duckdns.org` |

   *Secrets*
   | Name | Notes |
   |---|---|
   | `SSH_HOST` | Oracle box public IP |
   | `SSH_USER` | `ubuntu` (or `opc` on Oracle Linux) |
   | `SSH_KEY` | private key **whose public half is in the box's authorized_keys** |
   | `NEXT_PUBLIC_API_URL` | `https://synapseai.duckdns.org` (baked into Vercel/Docker build) |
   | `SLACK_WEBHOOK_URL` | optional |

   The deploy job then git-pulls on the host, rebuilds natively, migrates and
   restarts with zero downtime.

### What the box runs

`docker-compose.prod.yml` (production profile): nginx (TLS/API gateway),
postgres+pgvector, redis, Django backend on **Daphne** (ASGI — serves the
`/ws/notifications/` WebSockets that gunicorn cannot), FastAPI AI engine,
Celery worker, Celery beat, Flower. The frontend container is opt-in via
`--profile frontend` (default is Vercel).

Two fixes shipped alongside this setup:
- The Celery worker now listens on the queues the app actually routes to
  (`default,scraping,slow_scraping,agents,nlp,embeddings`) — the old hardcoded
  list matched none of them, so scraped/NLP/embedding tasks queued forever.
- The backend command is Daphne, not gunicorn, so Channels WebSockets work.

---

## 3c. SYNAPSE Lite mode — run the whole app on a 2 GB box

The full stack loads five local ML models into RAM (~6–8 GB before Postgres,
Redis and Celery). If you can't get the 24 GB Oracle box, **Lite mode** runs the
same app on ~1.5–2 GB by moving those jobs to the free cloud APIs the app
already calls.

Set in `.env.prod` (or any env):

```bash
SYNAPSE_LITE=1
EMBEDDING_PROVIDER=api   # default when SYNAPSE_LITE=1
```

What changes:

| Local model (full mode) | Lite mode uses |
|---|---|
| `BAAI/bge-large-en-v1.5` embeddings (~1.3 GB) | **NVIDIA NIM API** — `nvidia/nv-embedqa-e5-v5`, 1024-dim (verified to match the vector columns) |
| `facebook/bart-large-cnn` summarizer (~1.6 GB) | Groq → NVIDIA → Gemini LLM |
| `facebook/bart-large-mnli` topic (~1.6 GB) | same LLM chain |
| `twitter-roberta-base` sentiment (~500 MB) | same LLM chain |
| KeyBERT keywords (loads sentence-transformers) | YAKE only (pure Python) |
| spaCy NER (~100 MB) | skipped (entities left empty) |

torch, transformers, sentence-transformers, spaCy and KeyBERT are **never
imported** in lite mode — verified by the `test_lite_mode.py` suite.

### Building the slim images

The Dockerfiles accept `SYNAPSE_LITE` as a build arg to omit the heavy wheels
(image shrinks ~2–3 GB, builds much faster):

```bash
export SYNAPSE_LITE=1
# CD does this automatically for the on-host build (reads it from .env.prod).
# For a manual build you must export it — compose reads build args from the
# shell env / `.env`, NOT from `env_file`, so `docker compose build` alone
# will not see SYNAPSE_LITE=1 from .env.prod.
docker compose -f docker-compose.prod.yml build backend fastapi_ai
```

On a small box, lower the compose memory limits too (the defaults assume the
full ML stack):

```bash
BACKEND_MEM_LIMIT=768M
AI_MEM_LIMIT=1G
```

### Trade-offs (honest)

- **Quota ceiling** — every summarize/topic/sentiment call spends the free
  tiers (Groq 14,400 req/day, NVIDIA ~40 rpm, Gemini 1,000/day). The existing
  content-hash caches mean duplicate articles and repeated search queries are
  not re-billed.
- **Latency** — API calls add ~0.2–2 s per item vs ~0.1 s local inference.
- **Quality** — LLM summaries/topics are generally *better* than the local
  BART models; NER entities are dropped entirely.

Flip `SYNAPSE_LITE=0` (and rebuild) to restore the full local-model stack —
nothing is permanently lost; the toggle is fully reversible.

---

## 3d. Card-free cloud stopgap — Render + Neon + Upstash + GH Actions

> Use this **only until the Oracle box (§3b) is available** (or forever, if you
> never get a card). It needs **no credit card anywhere** and the laptop never
> serves traffic.
>
> It runs **Lite mode** (§3c): local ML models are replaced by free cloud APIs.

| Layer | Service | Cost | Card? |
|---|---|---|---|
| Frontend | Vercel Hobby (already live) | free | no |
| Backend | Render free web (Django/Daphne, 512 MB) | free | no |
| Database | Neon Postgres + pgvector (0.5 GB) | free | no |
| Redis | Upstash (256 MB) | free | no |
| Celery worker + beat | GitHub Actions cron (public repo = unlimited) | free | no |
| Email | Brevo SMTP | free | no |
| AI | Groq + NVIDIA NIM + Gemini | free | no |

**Why GitHub Actions runs the worker:** every card-free host (Render free,
Koyeb free) forbids background workers or sleeps after idle. But this repo is
**public**, and public repos get **unlimited** Actions minutes — so
`.github/workflows/celery-worker.yml` boots a throwaway worker every 10 minutes
that drains the Upstash queue and exits, and
`.github/workflows/celery-scheduler.yml` fires daily briefings, scrapers and
re-embedding on cron. Beat's `django_celery_beat` DB scheduler is not used in
this stopgap.

> 📖 **Full click-by-click guide:** see `docs/CLOUD_STOPGAP_RUNBOOK.md` —
> every button, every field, every secret name, plus troubleshooting.

### Setup — step by step

**1. Neon Postgres** (~5 min)
1. neon.tech → Sign in with Google/GitHub → **Create a project**.
2. Copy the **pooled** connection string (Settings → Connection Details →
   `postgresql://...?...sslmode=require`).
3. Neon supports pgvector natively — nothing to install.

**2. Upstash Redis** (~3 min)
1. upstash.com → Create a database (any region, free tier, 256 MB).
2. Copy the **TLS** URL: `rediss://default:<password>@<region>.upstash.io:6379`.
3. The app normalizes it to DB 0 automatically (Upstash free only allows DB 0).

**3. Render web service** (~15 min + build)
1. render.com → New → **Blueprint** → select the SYNAPSE repo. `render.yaml`
   creates `synapse-backend` on the **free** plan with `SYNAPSE_LITE=1`.
2. Open the service → **Environment** and set the `sync: false` values:
   `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `JWT_SIGNING_KEY`,
   `GROQ_API_KEY`, `NVIDIA_API_KEY`, `GEMINI_API_KEY`, `EMAIL_HOST_USER`,
   `EMAIL_HOST_PASSWORD` (all from your `.env.prod` / §2 table).
3. Deploy. When the build finishes, the service health-checks
   `/api/v1/health/` and stays live.
4. Note the service URL, e.g. `https://synapse-backend.onrender.com`.

**4. Point the frontend at it** (Vercel, ~5 min)
1. Vercel → SYNAPSE project → Settings → Environment Variables.
2. `NEXT_PUBLIC_API_URL=https://synapse-backend.onrender.com`
3. `NEXT_PUBLIC_WS_URL=wss://synapse-backend.onrender.com/ws`
4. Redeploy (`npx vercel --prod` or push to the connected branch).
   The old `synapseai.duckdns.org` values stay ready for the Oracle switch.

**5. GitHub Actions secrets** (~5 min)
Settings → Secrets and variables → Actions → New repository secret — exactly
the names the workflows read (see `.env.cloud.example`):

```
DATABASE_URL, REDIS_URL, SECRET_KEY, DB_PASSWORD, REDIS_PASSWORD,
JWT_SIGNING_KEY, GROQ_API_KEY, NVIDIA_API_KEY, GEMINI_API_KEY,
OPENROUTER_API_KEY, TAVILY_API_KEY,
EMAIL_HOST=smtp-relay.brevo.com, EMAIL_PORT=587, EMAIL_USE_TLS=True,
EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, DEFAULT_FROM_EMAIL="SYNAPSE <noreply@synapse.ai>",
FRONTEND_URL=https://synapse-one-blond.vercel.app,
RENDER_HEALTH_URL=https://synapse-backend.onrender.com/api/v1/health/
```

> The `EMAIL_*` secrets matter: without them the settings default to
> `smtp.sendgrid.net`, and notification/briefing emails from the cron worker
> silently fail instead of going through Brevo.

**6. Verify**
```bash
curl https://synapse-backend.onrender.com/api/v1/health/          # 200
# open the Vercel URL → register an account → check Brevo inbox
# Actions tab: celery-worker.yml runs every 10 min, scheduler daily
```

### Limitations (honest)

- Render free sleeps after 15 min idle → first hit after idle is a ~1 min cold
  start. The GH Actions keep-warm ping mitigates this.
- Scraping/embeddings/notifications run on the 10-minute cron, so fresh data
  appears with up to 10 min delay (fine for daily briefings).
- 512 MB is enough for Django + Daphne in lite mode, but not for huge
  concurrent exports; the worker and web share the free 750 instance-hours.
- Re-embedding now calls `ai_engine.embeddings.embed_batch` **directly** — the
  separate FastAPI service is not deployed in this stopgap.

When the Oracle box is ready: set `SYNAPSE_LITE=0`, flip the Vercel env vars
back to `synapseai.duckdns.org`, run §3b, and these workflows become inert.

---

## 4. Cost and quota behaviour

AI providers are tried in order, failing over on error or rate limit:

```
Groq → NVIDIA NIM → Gemini → OpenRouter → Scitely
```

Each has an independent quota, so a 429 on one is survivable. An explicitly
requested provider is never silently swapped.

Consumption is held down by four mechanisms:

- **Per-user quotas** (`apps/core/quotas.py`) — daily *and* monthly ceilings.
  Daily is what stops one user draining a day's capacity.
- **Rate limits** (`apps/core/throttles.py`) — short-window burst protection.
- **Semantic cache** (`apps/core/semantic_cache.py`) — a near-duplicate
  question reuses a prior answer instead of spending a call. Only applies to
  the first turn of a conversation, since follow-ups depend on history.
- **Agent iteration cap** — `MAX_ITERATIONS` is 5, not 10. Each iteration is a
  separate LLM call.

Referrals raise a user's **monthly** ceiling (not daily), up to 5 referrals.

Embeddings run locally via `sentence-transformers` — free and unmetered — and
are cached by content hash, so re-scraped or duplicate articles are not
re-embedded.

---

## 5. Things worth knowing

**Embedding dimensions are 1024** across every vector column, matching
`BAAI/bge-large-en-v1.5`. The embedder refuses to start if `EMBEDDING_MODEL`
produces a different width, rather than failing later inside Postgres.

The older `*_embedding_1024` migrations are **silent no-ops** — their
`IF EXISTS` guards test Django's default table names while the models define
custom `db_table` values. The `*_alter_*_embedding` migrations do the real work.
Leave both in place; the no-ops are harmless and removing them would break
applied migration history.

**There is no billing.** The app is free. `apps/growth` holds referrals and
feedback; quotas live in `apps/core/quotas.py`.

### The archived second branch — do not merge or restore

`main` is the only branch, and it is the healthy one.

A second branch once existed alongside it, holding the same application nested
under `src/engine/`. **It has been deleted**, and is preserved as the tag
`archive/truncated-branch` (133 commits, 861 files).

> Naming note: that deleted branch was itself once called `main`. The name now
> belongs to the working branch. The archive tag was deliberately renamed so the
> word `main` refers to exactly one thing.

It was deleted rather than kept because it looked like the newer, tidier branch
while being quietly damaged. It was produced by stripping the **last line of
every file** in a corrupted snapshot of the working branch. Where the corruption
was a duplicated closing delimiter, that accidentally fixed the file. Everywhere
else it **deleted a real line of code** — `connect_signals()`, `ph.flush()`, a
`fields = [...]` declaration, and so on across roughly 51 files.

The dangerous part is that those files still parse. No syntax check, linter, or
type checker flags them; the behaviour just silently goes missing at runtime.

Everything worth keeping was merged in first: `infrastructure/` (nginx,
Prometheus/Grafana/Loki, pgbouncer, OpenTelemetry), personalized briefings in
`views_ai.py`, the background-thread workflow fallback, real analytics data (the
working branch had `Math.random()` placeholders), and two UI components. The
audit is recorded in commits `009999e` and `186a6aa`.

To inspect the archive:

```bash
git show archive/truncated-branch:src/engine/<path>
git ls-tree -r archive/truncated-branch --name-only
```

Take individual hunks only. Never restore the branch or merge the tag.

> CI, CD, the security scan, and `render.yaml` all once targeted the *other*
> branch, so the pipeline built and deployed the damaged code while the working
> branch was never built at all. All five references now target `main`.
