# SYNAPSE — Card-Free Cloud Stopgap: Click-by-Click Runbook

> Deploys SYNAPSE in **lite mode** on free tiers — **no credit card, no laptop
> serving, background jobs included** (via GitHub Actions cron).
>
> Stack: **Vercel** (frontend, already live) + **Render free** (Django web) +
> **Neon** (Postgres+pgvector) + **Upstash** (Redis) + **GH Actions cron**
> (Celery worker + scheduler). All free, all card-free.
>
> Estimated total time: **45–60 min** the first time. Most of it is waiting for
> the Render build.

---

## Before you start — copy these from your machine

You already have everything needed in `/home/hayredin/Music/synapse/.env.prod`
(AI keys, Brevo SMTP, secrets). Keep that file open; you'll paste values from
it into the dashboards below.

Quick reference (from `.env.cloud.example`):

| Value | Where it is |
|---|---|
| `GROQ_API_KEY` | `.env.prod` → `GROQ_API_KEY=` |
| `NVIDIA_API_KEY` | `.env.prod` → `NVIDIA_API_KEY=` |
| `GEMINI_API_KEY` | `.env.prod` → `GEMINI_API_KEY=` |
| `EMAIL_HOST_USER` | `.env.prod` → `EMAIL_HOST_USER=` (Brevo login, e.g. `xxxxx@smtp-brevo.com`) |
| `EMAIL_HOST_PASSWORD` | `.env.prod` → `EMAIL_HOST_PASSWORD=` (Brevo SMTP key `xsmtpsib-...`) |
| `SECRET_KEY` / `JWT_SIGNING_KEY` | `.env.prod` (already generated — reuse them) |
| Frontend URL | `https://synapse-one-blond.vercel.app` (already live) |

Generate a **new** DB password for Neon (Django/DB secrets should differ per
environment):

```bash
openssl rand -hex 24   # → paste into Neon below when it asks
```

---

## STEP 1 — Neon Postgres (free, ~8 min)

1. Open **https://console.neon.tech** in your browser.
2. **Sign in** — Google or GitHub account (no card, ever).
3. First time: accept the terms, then click **Create a project** (green button).
4. **Project settings:**
   - **Name:** `synapse`
   - **Database name:** `synapse_db`
   - **Region:** pick the closest to you, e.g. **EU Central (Frankfurt)** or
     **US East (Ohio)**. It doesn't matter much for a stopgap.
   - Leave **Compute size** at the default (free tier auto-scales).
5. Click **Create project**. Wait ~30 s for provisioning.
6. You land on the **Connection Details** screen.
7. **Copy the connection string** — use the **Pooled connection** tab:
   - Look for the section labeled *"Connection string"* / *"Pooled connection"*.
   - It looks like:
     `postgresql://synapse_owner:XXXX@ep-xxxx-xxxx-xxxx.region.aws.neon.tech/synapse_db?sslmode=require`
   - Click the **copy** icon. **Save this — it's your `DATABASE_URL`.**
8. (Optional) In Neon → **SQL editor** (left sidebar), run:
   ```sql
   SELECT default_version FROM pg_available_extensions WHERE name = 'vector';
   ```
   It should return a version (e.g. `0.8.0`). pgvector is built in — no install
   needed. ✅ Neon done.

---

## STEP 2 — Upstash Redis (free, ~5 min)

1. Open **https://console.upstash.com** → **Sign in** (GitHub or Google, no card).
2. Click **Create database** (top right).
3. Settings:
   - **Name:** `synapse`
   - **Region:** any (e.g. `eu-central-1`). Free tier = single region, fine.
   - Leave everything else default. Click **Create**.
4. You land on the database **Overview** page.
5. Find the **Redis** connection string — it starts with **`rediss://`**:
   - Format: `rediss://default:<password>@<something>.upstash.io:6379`
   - There is a **copy** button next to it. **Copy it — this is your `REDIS_URL`.**
   - ⚠️ Make sure it's the **`rediss://`** (TLS) URL, not the REST URL
     (`https://...`) — the app needs the Redis protocol one.
6. (Optional) confirm it works locally:
   ```bash
   # from your laptop — replace with YOUR url
   docker run --rm redis:7-alpine redis-cli -u "rediss://..." ping   # → PONG
   ```
   ✅ Upstash done.

---

## STEP 3 — Render web service (free, ~20 min incl. build)

You already have a Render account (your dashboard shows `forno-api`).

1. Go to **https://dashboard.render.com** → **New** (top-right) → **Blueprint**.
   - Blueprint = reads `render.yaml` from the repo → creates the service for you.
2. **Connect repository** → select **Hayredin950/SYNAPSE** (authorize GitHub if
   asked).
3. Render scans the repo and finds `render.yaml`. It shows a plan:
   - **synapse-backend** — Web Service, free plan.
   - Accept the defaults → click **Apply**.
4. Render starts building the Docker image (this takes a while — the lite
   image is small, but the first build downloads base images + Python deps:
   expect **5–15 min**). The service will appear with status *"Building"*.
5. **While it builds**, open the service → **Environment** tab → **Add
   Environment Variable** for each of these (click **Add**, paste, save):

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | the **Neon pooled** URL from Step 1 |
   | `REDIS_URL` | the **Upstash rediss://** URL from Step 2 |
   | `SECRET_KEY` | from `.env.prod` (or `openssl rand -hex 32`) |
   | `JWT_SIGNING_KEY` | from `.env.prod` (or `openssl rand -hex 32`) |
   | `GROQ_API_KEY` | `gsk_...` from `.env.prod` |
   | `NVIDIA_API_KEY` | `nvapi-...` from `.env.prod` |
   | `GEMINI_API_KEY` | `AIza...` from `.env.prod` |
   | `EMAIL_HOST_USER` | Brevo login from `.env.prod` |
   | `EMAIL_HOST_PASSWORD` | Brevo SMTP key from `.env.prod` |
   | `DB_PASSWORD` | `openssl rand -hex 24` (legacy key, keep non-empty) |
   | `REDIS_PASSWORD` | `openssl rand -hex 24` (legacy key, keep non-empty) |

   > The blueprint already pre-fills everything else: `SYNAPSE_LITE=1`,
   > `EMBEDDING_PROVIDER=api`, `EMBEDDING_DIM=1024`, SMTP host/port,
   > `ALLOWED_HOSTS`, CORS, queues, etc. You only add the 11 secrets above.

6. **Wait for the build to finish** → status becomes *"Deployed"* (or
   *"Live"*). If it fails, click the build → the **Logs** tab shows why; the
   most common causes are a typo in `DATABASE_URL` or a missing `SECRET_KEY`.
7. **Get your service URL**: the service page shows `https://synapse-backend.onrender.com`
   (Render appends a random suffix if the name is taken, e.g.
   `synapse-backend-abc123.onrender.com` — use whatever it shows).
8. **Verify the API is live** (from your laptop):
   ```bash
   curl https://synapse-backend.onrender.com/api/v1/health/
   ```
   You want JSON with `"status": "ok"` (or similar). If it times out, the
   service is still cold-starting — wait 1 min and retry.
   ✅ Render done.

---

## STEP 4 — Point the Vercel frontend at Render (~5 min)

The frontend source reads `NEXT_PUBLIC_API_URL` from env — no code change
needed, just flip the env vars.

1. Open **https://vercel.com/dashboard** → your **synapse** project
   (`synapse-one-blond`).
2. Left menu → **Settings** → **Environment Variables**.
3. You'll see existing entries (currently the DuckDNS/Oracle values). **Change
   them** (Edit):
   | Name | New value |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | `https://synapse-backend.onrender.com` (your Render URL) |
   | `NEXT_PUBLIC_WS_URL` | `wss://synapse-backend.onrender.com/ws` |
   | `NEXT_PUBLIC_APP_URL` | `https://synapse-one-blond.vercel.app` (unchanged) |
   | `NEXT_PUBLIC_APP_NAME` | `SYNAPSE` (unchanged) |
4. Apply to **Production** environment (and Preview if you want).
5. **Redeploy**: open the **Deployments** tab → on the latest deployment click
   the **⋮** menu → **Redeploy** → **Redeploy**.
6. Wait ~2 min for the build. Then open your site:
   ```bash
   curl -s https://synapse-one-blond.vercel.app | head -5   # returns HTML
   ```
   ✅ Vercel done.

---

## STEP 5 — GitHub Actions secrets (free, ~10 min)

This powers the **Celery worker + scheduler** (background jobs) — the part
every free host forbids. Your repo is **public**, so Actions minutes are
**unlimited**.

1. Open **https://github.com/Hayredin950/SYNAPSE** →
   **Settings** → **Secrets and variables** → **Actions**.
2. Click **New repository secret** for each of these (Name = key, Value from
   your `.env.prod` / the steps above). The workflows already exist in the repo
   (`.github/workflows/celery-worker.yml`, `celery-scheduler.yml`) and read
   exactly these names:

   | Secret name | Value |
   |---|---|
   | `DATABASE_URL` | Neon pooled URL (same as Step 3) |
   | `REDIS_URL` | Upstash rediss:// URL |
   | `SECRET_KEY` | same as Render |
   | `DB_PASSWORD` | same as Render |
   | `REDIS_PASSWORD` | same as Render |
   | `JWT_SIGNING_KEY` | same as Render |
   | `GROQ_API_KEY` | from `.env.prod` |
   | `NVIDIA_API_KEY` | from `.env.prod` |
   | `GEMINI_API_KEY` | from `.env.prod` |
   | `OPENROUTER_API_KEY` | leave empty or from `.env.prod` if set |
   | `TAVILY_API_KEY` | leave empty or from `.env.prod` if set |
   | `EMAIL_HOST` | `smtp-relay.brevo.com` |
   | `EMAIL_PORT` | `587` |
   | `EMAIL_USE_TLS` | `True` |
   | `EMAIL_HOST_USER` | Brevo login |
   | `EMAIL_HOST_PASSWORD` | Brevo SMTP key |
   | `DEFAULT_FROM_EMAIL` | `SYNAPSE <noreply@synapse.ai>` |
   | `FRONTEND_URL` | `https://synapse-one-blond.vercel.app` |
   | `RENDER_HEALTH_URL` | `https://synapse-backend.onrender.com/api/v1/health/` |

3. **Trigger the worker once manually** to prove it works:
   - Open **https://github.com/Hayredin950/SYNAPSE/actions** →
     **Celery Worker (cron)** → **Run workflow** → **Run workflow** (green).
   - The job installs lite deps (~2–4 min on first run, cached after) then runs
     the worker for up to 9 min. It should end **green**.
4. The **scheduler** workflow fires daily briefings at 06:30 UTC, scrapers at
   02:00 UTC, re-embedding at 03:00 UTC.
   ✅ GitHub done.

---

## STEP 6 — Create your admin + final verification

1. **Create a superuser** on Render:
   - Render → **synapse-backend** service → **Shell** tab →
     (a terminal opens in the container):
     ```bash
     python manage.py createsuperuser
     ```
     (Fill username/email/password.)
2. **Open the admin**: `https://synapse-backend.onrender.com/admin` → log in.
3. **Register a real user** on the frontend:
   `https://synapse-one-blond.vercel.app` → Sign up → check
   `sadim9812@gmail.com` inbox for the Brevo verification email.
4. **Watch the pipeline end-to-end**:
   - GitHub Actions → **Celery Scheduler** → **Run workflow** manually once.
   - After it finishes, log into the frontend → check that scraped articles,
     briefings, or search results appear (first scrape can take a few minutes).
5. **Health check from anywhere**:
   ```bash
   curl https://synapse-backend.onrender.com/api/v1/health/
   ```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Render deploy fails at build | Logs tab → usually a bad `DATABASE_URL` or missing `SECRET_KEY`. Fix env, then **Redeploy**. |
| `curl` health times out | Free tier cold-start (~1 min). Wait, retry. If persistent, check Render → Logs for startup errors (migration failure, wrong REDIS URL). |
| Worker job fails in Actions | Open the failed run → the step with the error. Most common: a missing/typo'd secret name. |
| Frontend shows API errors | Check Vercel env vars are applied to **Production** and you **Redeployed** after changing them. |
| Emails not arriving | Verify `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` (Brevo), and that the 5 `EMAIL_*` secrets exist in GitHub (worker sends them). |
| Search returns nothing | First scrape hasn't run yet → Actions → Celery Scheduler → Run workflow; then re-embed (03:00 UTC job or manual run). |

---

## Switching back to Oracle (when the box is ready)

1. Deploy per DEPLOYMENT.md §3b (Oracle bootstrap).
2. Vercel env vars → flip `NEXT_PUBLIC_API_URL`/`NEXT_PUBLIC_WS_URL` back to
   `https://synapseai.duckdns.org` → **Redeploy**.
3. The `celery-worker.yml` / `celery-scheduler.yml` workflows become inert
   (Oracle runs its own Celery). No code changes needed.
