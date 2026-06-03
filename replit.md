# SYNAPSE — AI-Powered Technology Intelligence Platform

SYNAPSE aggregates articles, research papers, GitHub repos, X/Twitter posts and videos, then lets AI agents research, summarize, and automate so engineers never miss a breakthrough.

## Run & Operate

| Service | Command | Port |
|---------|---------|------|
| Django Backend | `bash synapse/start-backend-replit.sh` | 8000 |
| Next.js Frontend | `bash synapse/start-frontend-replit.sh` | 3000 |
| Node API Proxy | (auto via workflow) | 8080 |

- `SYNAPSE Backend` workflow — Django/Daphne ASGI server
- `artifacts/synapse: web` workflow — Next.js dev server
- `artifacts/api-server: API Server` — Node.js proxy that forwards `/api/*` to Django

## Demo Login

- **Email:** `demo@synapse.dev`
- **Password:** `Demo1234!`

## Stack

- **Backend:** Django 4.2 + DRF + Daphne (ASGI/WebSockets) + Channels
- **Frontend:** Next.js 15 + React 19 + TailwindCSS + shadcn/ui + Framer Motion
- **Database:** PostgreSQL (Replit managed) + pgvector extension
- **AI Engine:** LangChain + OpenAI (via Replit AI integration proxy)
- **Task Queue:** Celery (in-memory broker in dev; Redis optional)
- **Auth:** JWT (djangorestframework-simplejwt)

## Where Things Live

| Path | Purpose |
|------|---------|
| `synapse/backend/` | Django project root |
| `synapse/backend/config/settings/replit.py` | Replit-specific Django settings |
| `synapse/backend/apps/` | Django apps (articles, users, agents, billing, …) |
| `synapse/frontend/` | Next.js app |
| `synapse/frontend/next.config.mjs` | Next.js config (proxy rewrites, allowed origins) |
| `synapse/start-backend-replit.sh` | Backend startup script (sets Replit DB env vars) |
| `synapse/start-frontend-replit.sh` | Frontend startup script |
| `artifacts/api-server/src/app.ts` | Node proxy: forwards `/api/*` → Django port 8000 |

## Architecture Decisions

- **Dual proxy pattern:** Replit routes `/api` → Node.js API server; that server proxies everything to Django at port 8000 (with `pathRewrite` to restore the `/api` prefix that Express strips).
- **In-memory Channels:** WebSocket layer uses in-memory channel layer in dev (no Redis required).
- **Replit AI integration:** Django reads `AI_INTEGRATIONS_OPENAI_API_KEY` and `AI_INTEGRATIONS_OPENAI_BASE_URL` from env for all LLM calls — no external key needed.
- **Auto email verify:** `replit.py` settings auto-verify email and disable rate limits for easy dev testing.
- **pgvector:** Installed and enabled in the Replit PG database for semantic search on articles, papers, and videos.

## User Preferences

- Keep Django settings module at `config.settings.replit` for Replit environment.
- Always use `--break-system-packages` when pip-installing in this Nix environment.
- PYTHONPATH must include both `synapse/backend` and `synapse` for imports to resolve.

## Gotchas

- The Replit proxy routes `/api` to the Node API server (port 8080), NOT directly to Django (port 8000). The Node server must be running and proxying to Django.
- `pnpm run dev` at workspace root is blocked by design — use `restart_workflow` to start services.
- Django `manage.py` commands need env vars: `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `SECRET_KEY`, `DJANGO_SETTINGS_MODULE`, `PYTHONPATH`, `OPENAI_API_KEY` (dummy value is fine).
- `pgvector` Python package required at startup (`pip install pgvector --break-system-packages`).
