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

### Render

`render.yaml` is a valid Blueprint (top-level `services:` and `databases:`
lists — an earlier version used singular keys that Render silently would not
accept). It provisions Postgres, Redis, the Daphne web service, a Celery
worker, and a single beat scheduler.

The backend is on the `standard` plan, not `starter`: 512MB cannot load torch +
transformers + spaCy. Keep beat at exactly one instance or every periodic task
fires twice.

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
