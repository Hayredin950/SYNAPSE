
---

## 🟢 Phase 2 — Tier 1: Revenue & Retention

> **Note:** TASK-001 (Onboarding), TASK-003 (Billing), TASK-006 (Teams) are already defined in Phase 0. This phase covers the remaining Tier 1 items.

---

### TASK-201 — Weekly AI Digest Email

**Priority:** 🟢 High | **Effort:** Medium | **Impact:** +25–35% re-engagement

#### Backend Tasks
- [ ] **TASK-201-B1:** Create weekly digest Celery task
  - File: `backend/apps/core/tasks.py`
  - Task: `send_weekly_digest()` — runs every Monday at 8am via Celery beat
  - For each active user: fetch top 5 articles, top 3 papers, top trending repo from their interest topics
- [ ] **TASK-201-B2:** Create digest email template
  - File: `backend/apps/notifications/email_service.py`
  - HTML email template with sections: Top Articles / Trending Papers / Rising Repos / AI Summary blurb
  - Plain-text fallback
- [ ] **TASK-201-B3:** Add digest preference to user model
  - File: `backend/apps/users/models.py`
  - Add field: `digest_enabled = BooleanField(default=True)`, `digest_day = CharField(default='monday')`
- [ ] **TASK-201-B4:** Schedule Celery beat entry
  - File: `backend/config/settings/base.py`
  - Add `send-weekly-digest` to `CELERY_BEAT_SCHEDULE` with cron `0 8 * * 1`

#### Frontend Tasks
- [ ] **TASK-201-F1:** Add digest toggle in settings
  - File: `frontend/src/app/(dashboard)/settings/page.tsx`
  - Toggle: "Weekly AI Digest Email" on/off
  - Dropdown: preferred day (Mon–Sun)

---

## 🟢 Phase 3 — Tier 2: AI Differentiation

---

### TASK-301 — Hybrid Search (BM25 + Semantic + Reranking)

**Priority:** 🟢 High | **Effort:** Large | **Impact:** 40–60% better retrieval accuracy

#### Backend Tasks
- [ ] **TASK-301-B1:** Install and configure BM25 search
  - File: `backend/requirements.txt`
  - Add: `rank-bm25`, `django-pg-fts` or use PostgreSQL full-text search (`SearchVector`, `SearchQuery`)
- [ ] **TASK-301-B2:** Add full-text search indexes to content models
  - Files: `backend/apps/articles/models.py`, `backend/apps/papers/models.py`, `backend/apps/repositories/models.py`
  - Add `GinIndex` on `title + summary` using `SearchVectorField`
  - New migrations for each app
- [ ] **TASK-301-B3:** Implement hybrid retriever
  - File: `ai_engine/rag/retriever.py`
  - New method `hybrid_search(query, k=10)`:
    1. Run semantic search → top-20 results with scores
    2. Run BM25/full-text search → top-20 results with scores
    3. Merge using Reciprocal Rank Fusion (RRF)
    4. Return top-k merged results
- [ ] **TASK-301-B4:** Add reranking step
  - File: `ai_engine/rag/retriever.py`
  - Integrate Cohere Rerank API (`cohere.rerank()`) or use `BAAI/bge-reranker-base` locally
  - Rerank merged top-20 → return top-5 for LLM context
- [ ] **TASK-301-B5:** Update RAG chain to use hybrid retriever
  - File: `ai_engine/rag/chain.py`
  - Replace `retriever.search()` calls with `retriever.hybrid_search()`
- [ ] **TASK-301-B6:** Update semantic search views
  - File: `backend/apps/core/views_nlp.py`
  - Update `/api/search/semantic/` to use hybrid approach
- [ ] **TASK-301-B7:** Add reranker to AI engine requirements
  - File: `ai_engine/requirements.txt`
  - Add: `cohere` (or `FlagEmbedding` for local reranker)

---

### TASK-302 — Add Claude + Ollama LLM Support

**Priority:** 🟢 High | **Effort:** Medium | **Impact:** Enterprise readiness + model flexibility

#### Backend Tasks
- [ ] **TASK-302-B1:** Add Anthropic Claude integration
  - File: `ai_engine/agents/base.py`
  - Add Claude model support via `langchain-anthropic`
  - Supported models: `claude-3-5-sonnet-20241022`, `claude-3-haiku-20240307`
  - Read `ANTHROPIC_API_KEY` from env
- [ ] **TASK-302-B2:** Add Ollama integration for local LLMs
  - File: `ai_engine/agents/base.py`
  - Add Ollama support via `langchain-ollama`
  - Supported models: `llama3.2`, `mistral`, `codellama`
  - Read `OLLAMA_BASE_URL` from env (default: `http://localhost:11434`)
- [ ] **TASK-302-B3:** Build model router
  - File: `ai_engine/agents/` — new file `router.py`
  - Logic: route by task type:
    - Simple Q&A → cheapest model (Haiku / Ollama)
    - Complex reasoning → Claude Sonnet / GPT-4o
    - Code tasks → CodeLlama / GPT-4o
  - Read user's model preference from request
- [ ] **TASK-302-B4:** Update AI engine requirements
  - File: `ai_engine/requirements.txt`
  - Add: `langchain-anthropic`, `langchain-ollama`
- [ ] **TASK-302-B5:** Add model selection to env config
  - File: `.env.example`
  - Add: `ANTHROPIC_API_KEY=`, `OLLAMA_BASE_URL=`, `DEFAULT_LLM_MODEL=gpt-4o`

#### Frontend Tasks
- [ ] **TASK-302-F1:** Add model selector in chat UI
  - File: `frontend/src/app/(dashboard)/chat/page.tsx`
  - Dropdown to select: GPT-4o / Claude 3.5 / Gemini / Ollama (local)
  - Show cost indicator per model (Free / $ / $$)
- [ ] **TASK-302-F2:** Add model selector in agent UI
  - File: `frontend/src/app/(dashboard)/agents/page.tsx`
  - Same model picker, persisted to user preferences

---

### TASK-303 — AI Agent Tool Expansion

**Priority:** 🟢 High | **Effort:** Large | **Impact:** Agent power + differentiation

- [ ] **TASK-303-B1:** Add web search tool (Tavily API)
  - File: `ai_engine/agents/tools.py`
  - New tool: `web_search(query)` using Tavily API
  - Read `TAVILY_API_KEY` from env
  - Add to `.env.example`
- [ ] **TASK-303-B2:** Add code execution sandbox (E2B)
  - File: `ai_engine/agents/tools.py`
  - New tool: `run_python_code(code)` using E2B API
  - Returns: stdout, stderr, any generated files
  - Read `E2B_API_KEY` from env
- [ ] **TASK-303-B3:** Add PDF/document reader tool
  - File: `ai_engine/agents/tools.py`
  - New tool: `read_document(file_url)` — fetch PDF, extract text via `pymupdf`
  - Chunk and embed on-the-fly for single-doc Q&A
- [ ] **TASK-303-B4:** Add chart generator tool
  - File: `ai_engine/agents/tools.py`
  - New tool: `generate_chart(data, chart_type)` — produce matplotlib chart as base64 PNG
  - Return image URL for frontend rendering
- [ ] **TASK-303-B5:** Add Notion reader tool
  - File: `ai_engine/agents/tools.py`
  - New tool: `read_notion_page(page_id)` — fetch Notion page content via Notion API
  - Read `NOTION_API_KEY` from env
- [ ] **TASK-303-B6:** Register all new tools in agent registry
  - File: `ai_engine/agents/registry.py`
  - Add all new tools to the tool registry with descriptions for LLM tool selection
- [ ] **TASK-303-F1:** Show tool call traces in agent UI
  - File: `frontend/src/app/(dashboard)/agents/page.tsx`
  - Render tool call steps: tool name, input, output in collapsible trace view
  - Show code execution output in syntax-highlighted block
  - Render generated charts inline

---

### TASK-304 — Voice Interface

**Priority:** 🟢 Medium | **Effort:** Medium | **Impact:** Differentiation

- [ ] **TASK-304-B1:** Add Whisper transcription endpoint
  - File: `backend/apps/core/views_chat.py` or `ai_engine/main.py`
  - `POST /api/chat/transcribe/` — accept audio file, return transcribed text via OpenAI Whisper API
- [ ] **TASK-304-F1:** Add voice input button to chat
  - File: `frontend/src/app/(dashboard)/chat/page.tsx`
  - Microphone button: record → send to transcribe endpoint → populate input field
  - Use browser `MediaRecorder` API
- [ ] **TASK-304-F2:** Add TTS response playback
  - File: `frontend/src/app/(dashboard)/chat/page.tsx`
  - "Read aloud" button on AI responses
  - Use browser `SpeechSynthesis` API (free) or ElevenLabs API for quality

---

### TASK-305 — AI Daily Briefing (In-App)

**Priority:** 🟢 Medium | **Effort:** Medium | **Impact:** Daily engagement loop

- [ ] **TASK-305-B1:** Create daily briefing Celery task
  - File: `backend/apps/core/tasks.py`
  - Task: `generate_daily_briefing(user_id)` — runs at 7am per user timezone
  - Query top trending content from last 24h matching user topics
  - Call AI engine to generate a 3-paragraph briefing
  - Store in new `DailyBriefing` model
- [ ] **TASK-305-B2:** Create DailyBriefing model
  - File: `backend/apps/core/models.py`
  - Fields: `user`, `content` (text), `generated_at`, `sources` (JSON array of content IDs)
- [ ] **TASK-305-B3:** Add briefing API endpoint
  - File: `backend/apps/core/views.py`
  - `GET /api/briefing/today/` — return today's briefing for the user
- [ ] **TASK-305-F1:** Show briefing on home dashboard
  - File: `frontend/src/app/(dashboard)/home/page.tsx`
  - "Today's Brief" card at top of home page
  - Expandable, with source links and "Ask follow-up" button that opens chat

---

### TASK-306 — Prompt Library

**Priority:** 🟢 Medium | **Effort:** Medium | **Impact:** User stickiness + community

#### Backend Tasks
- [ ] **TASK-306-B1:** Create PromptTemplate model
  - File: `backend/apps/agents/models.py`
  - Fields: `title`, `description`, `content`, `category`, `author`, `is_public`, `use_count`, `upvotes`
- [ ] **TASK-306-B2:** Add prompt library API endpoints
  - File: `backend/apps/agents/views.py`
  - `GET /api/prompts/` — list public prompts (filterable by category)
  - `POST /api/prompts/` — create new prompt
  - `POST /api/prompts/{id}/use/` — increment use_count, return prompt content
  - `POST /api/prompts/{id}/upvote/`

#### Frontend Tasks
- [ ] **TASK-306-F1:** Create Prompt Library page
  - File: `frontend/src/app/(dashboard)/prompts/page.tsx` *(new)*
  - Grid of prompt cards with category filter tabs
  - "Use Prompt" → opens agent runner with prompt pre-filled
  - "Save Prompt" → save to personal library
- [ ] **TASK-306-F2:** Add prompt picker to agent/chat UI
  - File: `frontend/src/app/(dashboard)/agents/page.tsx`
  - "Browse Prompts" button → open prompt picker modal

