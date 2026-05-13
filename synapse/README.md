# SYNAPSE

> **AI-Powered Technology Intelligence & Automation Platform**

A FAANG-style production system that continuously collects, analyzes, and surfaces technology intelligence from across the internet — powered by LLMs, semantic search, autonomous AI agents, and a beautiful real-time dashboard.

## What is SYNAPSE?

SYNAPSE is a combination of:
- 🔍 **Perplexity AI** — semantic search over curated tech knowledge
- 📚 **Notion** — personal knowledge management + document generation
- ⚡ **Zapier** — no-code automation workflows
- 🐙 **GitHub** — repository intelligence and trend monitoring

Specialized exclusively for **technology, AI, software engineering, and research**.

## Architecture

```
Internet Sources (HN, arXiv, GitHub, YouTube)
        ↓
Data Collection Layer (Scrapy, Playwright, APIs)
        ↓
Message Queue (Celery + Redis)
        ↓
Processing Pipeline (NLP, embeddings, classification)
        ↓
Knowledge Storage (PostgreSQL + pgvector + Redis + S3)
        ↓
AI Layer (LangChain, OpenAI, spaCy, HuggingFace)
        ↓
Agentic AI (Autonomous agents, document generation)
        ↓
API Layer (Django REST + FastAPI + GraphQL)
        ↓
Frontend (Next.js + React + TailwindCSS)
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django 4.2, FastAPI 0.104, Python 3.11 |
| Frontend | Next.js 14, React 18, TypeScript, TailwindCSS |
| Databases | PostgreSQL 15, Redis 7, pgvector |
| AI/ML | LangChain, OpenAI API, spaCy, HuggingFace |
| Scraping | Scrapy, BeautifulSoup4, Playwright |
| Queue | Celery 5.3 + Redis |
| DevOps | Docker, GitHub Actions, AWS |
| Monitoring | Prometheus, Grafana, Sentry |

## Key Features

### 🧠 AI & Research
- 🤖 **AI Chat Assistant** — RAG-powered Q&A grounded in your knowledge base with voice input (Whisper) and text-to-speech playback
- 🔬 **Deep Research Mode** — Plan-and-Execute agent decomposes queries into sub-questions, searches ArXiv + GitHub + knowledge base, synthesizes into cited reports with PDF export
- 🕸️ **Knowledge Graph** — NER-extracted entity graph with interactive force-directed visualization (concepts, papers, authors, tools)
- 🤖 **AI Agents** — Web search, Python execution, chart generation, document reading tools with rich trace UI
- 📚 **Prompt Library** — Community-curated prompts with upvoting, categories, search, and one-click use in chat/agents
- ☀️ **Daily AI Briefing** — Personalized morning brief generated at 06:30 UTC, delivered to home dashboard

### 📊 Intelligence & Analytics
- 📰 **Tech Intelligence Feed** — AI-summarized articles with interest-based personalization
- 🔬 **Research Explorer** — arXiv papers with AI summaries, difficulty ratings, semantic search
- ⭐ **GitHub Intelligence Dashboard** — Star velocity analytics, rising star detection, ecosystem health by language, Tech Radar
- 📈 **Technology Trend Radar** — Track rising/falling technologies with visual radar

### ⚙️ Automation & Workflows
- ⚡ **Automation Center** — Schedule workflows with Celery beat, event triggers, cron expressions
- 🛒 **Automation Marketplace** — Community workflow templates, one-click install, publish your own
- 📄 **Document Studio** — AI generates research reports, PDFs (reportlab), Word docs on demand

### 🔌 Integrations & APIs
- 📝 **Notion** — Import pages to knowledge base, export reports as Notion pages
- 💬 **Slack** — /synapse slash command, weekly digest delivery to channels
- 🔮 **Obsidian** — Vault upload, wikilink graph import, AI note export
- 📚 **Zotero** — Full library sync, paper/author knowledge graph nodes
- 🔑 **Public REST API** — API key auth (sk-syn-*), rate-limited endpoints for content, AI queries, trends
- 🌐 **Browser Extension** — Chrome/Firefox: floating Save button, right-click AI explain, popup dashboard
- 🛠️ **Developer Portal** — Interactive API docs, code snippets (Python/TS/cURL), rate limit table

### 👥 Teams & Organizations
- 🏢 **Team Workspaces** — Organizations, role-based access (owner/admin/editor/viewer), invites
- 💳 **Billing & Plans** — Stripe integration, Free/Pro/Enterprise tiers, usage tracking, upgrade modals

### 🔒 Security & Compliance
- 🔐 **MFA** — TOTP + recovery codes (8 single-use backup codes)
- 🔑 **API Keys** — SHA-256 hashed, scoped (read/write), 10-key limit per user, revocable
- 📋 **Audit Log** — 20 action types: login, API keys, billing, org membership, AI queries
- 🛡️ **Rate Limiting** — Plan-aware (Free: 5 chat/day, Pro: 200/day), X-RateLimit-* headers, 429 with upgrade CTA
- 🔏 **PII Redaction** — Logging filter redacts emails, credit cards, API keys, JWT tokens
- 🔒 **Content Moderation** — Input/output safety filtering via AI guardrails middleware

### 🎨 UX & Design
- 🌙 **Dark Mode** — System-aware dark/light toggle (next-themes), brand/surface/text design tokens
- ⌨️ **Command Palette** — ⌘K global search with debounced backend search, grouped results, keyboard navigation
- 📱 **Mobile Bottom Nav** — Fixed 5-tab nav for mobile, `md:hidden`, iOS safe-area
- ♿ **Accessibility** — ARIA roles/labels, skip-to-content link, focus trap in modals

### 📚 Knowledge Library
- 📚 **Personal Library** — Bookmarks, collections, reading lists
- 🔍 **Hybrid Search** — BM25 + vector (pgvector) semantic search across all content types

## New API Endpoints (Latest)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/v1/briefing/today/` | Today's AI briefing |
| `GET`  | `/api/v1/briefing/history/` | Last 7 days of briefings |
| `GET`  | `/api/v1/knowledge-graph/` | Entity graph (BFS subgraph) |
| `GET`  | `/api/v1/knowledge-graph/search/` | Search nodes by name |
| `GET`  | `/api/v1/knowledge-graph/nodes/{id}/` | Node detail + edges |
| `GET`  | `/api/v1/audit-log/` | Audit log (paginated) |
| `GET`  | `/api/v1/agents/prompts/` | Prompt library |
| `POST` | `/api/v1/agents/prompts/` | Create prompt |
| `POST` | `/api/v1/agents/prompts/{id}/use/` | Use prompt |
| `POST` | `/api/v1/agents/prompts/{id}/upvote/` | Toggle upvote |
| `GET`  | `/api/v1/agents/research/` | List research sessions |
| `POST` | `/api/v1/agents/research/` | Start deep research |
| `GET`  | `/api/v1/agents/research/{id}/` | Get research report |
| `GET`  | `/api/v1/research/{id}/export-pdf/` | Export report as PDF |
| `GET`  | `/api/v1/repos/trending-velocity/` | GitHub star velocity |
| `GET`  | `/api/v1/repos/ecosystem/{lang}/` | Language ecosystem health |
| `GET`  | `/api/v1/content/articles/` | Search articles (API key) |
| `GET`  | `/api/v1/content/papers/` | Search papers (API key) |
| `GET`  | `/api/v1/content/repos/` | Search repos (API key) |
| `POST` | `/api/v1/ai/query/` | Ask AI (API key) |
| `GET`  | `/api/v1/trends/` | Trending content (API key) |
| `GET`  | `/api/v1/users/keys/` | List API keys |
| `POST` | `/api/v1/users/keys/` | Create API key |
| `DELETE` | `/api/v1/users/keys/{id}/` | Revoke API key |
| `POST` | `/api/v1/ai/chat/transcribe/` | Voice → text (Whisper) |
| `GET`  | `/api/v1/automation/marketplace/` | Workflow marketplace |
| `POST` | `/api/v1/automation/marketplace/{id}/install/` | Install template |

All API key endpoints accept `Authorization: Bearer sk-syn-{key}`.

## Quick Start

```bash
# 1. Clone and setup
git clone https://github.com/HayreKhan750/SYNAPSE.git
cd SYNAPSE

# 2. Copy environment variables
cp .env.example .env
# Edit .env with your API keys (OpenAI, Stripe, GitHub, etc.)

# 3. Start all services
docker-compose up -d

# 4. Run migrations
docker-compose exec backend python manage.py migrate

# 5. Create superuser
docker-compose exec backend python manage.py createsuperuser

# 6. Access the app
# Frontend:  http://localhost:3000
# Backend:   http://localhost:8000
# Admin:     http://localhost:8000/admin/
# API Docs:  http://localhost:8000/api/schema/swagger-ui/
```

## Environment Variables

Key variables to configure in `.env`:

```bash
# Required
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgresql://user:pass@localhost:5432/synapse
REDIS_URL=redis://localhost:6379/0
OPENAI_API_KEY=sk-...

# Stripe (billing)
STRIPE_PUBLIC_KEY=pk_live_...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# GitHub OAuth
GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...

# Notion Integration
NOTION_CLIENT_ID=...
NOTION_CLIENT_SECRET=...
NOTION_REDIRECT_URI=https://yourapp.com/api/v1/integrations/notion/callback/

# Slack Integration
SLACK_CLIENT_ID=...
SLACK_CLIENT_SECRET=...
SLACK_SIGNING_SECRET=...

# DB Backups (optional)
BACKUP_S3_BUCKET=synapse-backups
BACKUP_ADMIN_EMAIL=admin@yourcompany.com

# pgBouncer (optional)
PGBOUNCER=false

# OpenTelemetry (optional)
OTEL_ENABLED=false
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317

# Production CORS
CORS_ALLOWED_ORIGINS=https://yourdomain.com
```

## Documentation

All project documentation is in the `docs/` directory:

| Document | Description |
|----------|-------------|
| `01_SRS.pdf` | Software Requirements Specification |
| `02_Architecture_Design.pdf` | System Architecture & Design |
| `03_Database_Schema.pdf` | Complete Database Schema |
| `04_API_Specification.pdf` | REST API Specification |
| `05_Roadmap.pdf` | 22-Week Development Roadmap |
| `06_Implementation_Guide.pdf` | Step-by-step Implementation Guide |
| `07_UI_UX_Design.pdf` | UI/UX Design System |
| `08_DevOps_Deployment.pdf` | DevOps & Deployment Guide |
| `09_Security_Compliance.pdf` | Security & Compliance |
| `10_Testing_Strategy.pdf` | Testing Strategy |
| `11_Business_Plan.pdf` | Business Plan & Monetization |
| `12_Data_Pipeline.pdf` | Data Pipeline Design |
| `13_AI_Agent_Spec.pdf` | AI Agent Specification |
| `14_API_SDK_Guide.pdf` | API SDK Guide |
| `15_OSS_Stack.pdf` | Open Source Libraries & Stack |

## Development Setup

```bash
# Clone repository
git clone https://github.com/HayreKhan750/SYNAPSE.git
cd SYNAPSE

# Start all services with Docker
docker-compose up -d

# Backend setup
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

# Frontend setup
cd frontend
npm install
npm run dev
```

## Project Status

🚧 **In Development** — See [TASKS.md](TASKS.md) for the full task list and progress tracking.

## License

MIT License — see [LICENSE](LICENSE) for details.

## GitHub Actions Workflows

The CI/CD workflow files are in `_workflows_temp/`. To enable them:
1. Go to your GitHub token settings and add the `workflow` scope
2. Move files: `cp _workflows_temp/*.yml .github/workflows/`
3. Push: `git add -A && git push origin main`

Alternatively, create the workflow files directly in GitHub UI under **Actions → New workflow**.
