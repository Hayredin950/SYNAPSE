"""
Celery tasks for NLP processing of articles.

Phase 2.1 — NLP Processing Pipeline
Phase 2.2 — Article Summarization (Gemini / BART auto-run after scraping)

Tasks:
  process_article_nlp           — Full pipeline: clean → lang → keywords →
                                   topic → sentiment → NER → summary (Gemini/BART)
  process_pending_articles_nlp  — Batch-queue unprocessed articles
  summarize_article             — Standalone summarization task (Gemini → BART)
  summarize_pending_articles    — Queue summarization for articles without summary

Summary failure sentinel:
  Articles that fail summarization are marked with summary="__failed__" so they
  are excluded from future batch runs and never enter an infinite retry loop.
  Force-resetting: set summary="" and call summarize_article.delay(id, force=True).
"""

import logging
import os
import sys
import time
from typing import Dict, Optional

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)

# Sentinel value written to Article.summary when all summarization attempts fail.
# Prevents the article from being re-queued on every beat-schedule run.
SUMMARY_FAILED_SENTINEL = "__failed__"


# ── Multi-provider LLM helper (Groq → Vercel AI Gateway → OpenRouter) ─────────
# Summarization is latency-sensitive (we run it for every newly scraped article
# and the user sees an "AI summarizing…" badge until it completes). We therefore
# prefer providers in SPEED order, not capability order:
#
#   1. Groq                — ~500 t/s, ideal for short summaries
#   2. Vercel AI Gateway   — capable, single key for many models
#   3. OpenRouter / direct — legacy fallback, kept for backward compat
#
# Each provider is enabled by setting the matching env var. Set whichever you
# have a key for; the resolver picks the first available.


def _resolve_summarizer_provider(
    override_key: Optional[str] = None,
) -> Optional[tuple]:
    """
    Resolve (api_key, base_url, model) for an OpenAI-compatible summarization call.
    Returns None if no provider is configured.

    Priority:
      override_key → Groq → Vercel AI Gateway → OpenRouter / Gemini (legacy).
    """
    # Per-call override — keep using the legacy OpenRouter base by default
    if override_key:
        return (
            override_key,
            os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            os.environ.get("OPENROUTER_MODEL", "google/gemini-2.0-flash-001"),
        )

    # 1. Groq — fastest, OpenAI-compatible at /openai/v1
    groq_key = (os.environ.get("GROQ_API_KEY") or "").strip()
    if groq_key:
        return (
            groq_key,
            "https://api.groq.com/openai/v1",
            os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
        )

    # 2. Vercel AI Gateway — OpenAI-compatible at /v1
    gateway_key = (os.environ.get("AI_GATEWAY_API_KEY") or "").strip()
    if gateway_key:
        return (
            gateway_key,
            "https://ai-gateway.vercel.sh/v1",
            os.environ.get("AI_GATEWAY_MODEL", "openai/gpt-4o-mini"),
        )

    # 3. OpenRouter / Gemini — legacy
    legacy_key = (
        os.environ.get("OPENROUTER_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or getattr(settings, "OPENROUTER_API_KEY", None)
        or getattr(settings, "GEMINI_API_KEY", None)
        or ""
    )
    legacy_key = legacy_key.strip() if isinstance(legacy_key, str) else ""
    if legacy_key:
        return (
            legacy_key,
            os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            os.environ.get("OPENROUTER_MODEL", "google/gemini-2.0-flash-001"),
        )

    return None


def _summarize_with_gemini(
    text: str, max_chars: int = 8000, api_key: Optional[str] = None
) -> Optional[str]:
    """
    Summarize text via the first available OpenAI-compatible provider.
    Function name kept for backward compatibility with existing callers.
    Returns None on failure so callers fall back to local BART/extractive.
    """
    provider = _resolve_summarizer_provider(override_key=api_key)
    if provider is None:
        logger.info(
            "No summarizer API key configured (set GROQ_API_KEY, "
            "AI_GATEWAY_API_KEY, or OPENROUTER_API_KEY) - skipping LLM summary."
        )
        return None  # Caller falls back to BART

    api_key, base_url, model_name = provider

    logger.info(
        "_summarize_with_gemini: START base_url=%s model=%s text_length=%d",
        base_url,
        model_name,
        len(text),
    )

    has_full_content = len(text) > 300 and "Article Content:" in text
    if has_full_content:
        prompt = (
            "You are a technical summarizer for a tech news feed. Write a clear 3-4 sentence "
            "summary of the following article. Focus on: what the project/finding is, "
            "why it matters, and key technical details. Be specific and informative — "
            "avoid vague filler.\n\n"
            f"Article:\n{text[:max_chars]}\n\nSummary:"
        )
    else:
        prompt = (
            "You are a tech news summarizer for a developer news feed. Based on the title "
            "and metadata below, write a 3-4 sentence explanation of what this is about, "
            "why it's relevant to developers, and what makes it interesting. "
            "Be specific — infer context from the title, URL, and tags. "
            "Do NOT just repeat the title.\n\n"
            f"{text[:max_chars]}\n\nSummary:"
        )

    # Try langchain_openai first; fall back to direct httpx call if not installed
    _use_httpx = False
    try:
        from langchain_core.messages import HumanMessage  # noqa: PLC0415
        from langchain_openai import ChatOpenAI  # noqa: PLC0415

        try:
            llm = ChatOpenAI(
                model=model_name,
                temperature=0.3,
                max_tokens=500,
                openai_api_key=api_key,
                openai_api_base=base_url,
            )
        except Exception as exc:
            logger.error("Failed to build ChatOpenAI (model=%s): %s", model_name, exc)
            _use_httpx = True
    except ImportError:
        logger.warning(
            "langchain_openai not installed — using httpx fallback for summarization"
        )
        _use_httpx = True

    for attempt in range(2):
        try:
            if _use_httpx:
                import httpx  # noqa: PLC0415

                resp = httpx.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://synapse.ai",
                        "X-Title": "SYNAPSE Summarizer",
                    },
                    json={
                        "model": model_name,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 500,
                        "temperature": 0.3,
                    },
                    timeout=45,
                )
                resp.raise_for_status()
                data = resp.json()
                summary = data["choices"][0]["message"]["content"].strip()
            else:
                result = llm.invoke([HumanMessage(content=prompt)])
                summary = result.content.strip() if hasattr(result, "content") else ""

            if summary:
                logger.info(
                    "_summarize_with_gemini: SUCCESS provider=%s attempt=%d len=%d",
                    base_url,
                    attempt + 1,
                    len(summary),
                )
                return summary
            logger.error(
                "LLM summarizer: empty response provider=%s attempt=%d model=%s",
                base_url,
                attempt + 1,
                model_name,
            )
            return None
        except Exception as exc:
            exc_str = str(exc).lower()
            is_rate_limit = any(
                k in exc_str for k in ("429", "rate limit", "quota", "too many")
            )
            logger.error(
                "LLM summarizer: API error provider=%s attempt=%d model=%s rate_limit=%s: %s",
                base_url,
                attempt + 1,
                model_name,
                is_rate_limit,
                exc,
            )
            if is_rate_limit and attempt == 0:
                import time  # noqa: PLC0415

                time.sleep(5)
                continue
            return None
    return None


def _run_nlp(text: str, title: str = "") -> Optional[object]:
    """
    Import and run the NLP pipeline.  Handles import errors gracefully so
    that the Django/Celery process does not crash when heavy ML dependencies
    are absent from the backend virtualenv.
    """
    try:
        # Add the project root to sys.path so ai_engine is importable from
        # within the backend Celery worker.
        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        )
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        from ai_engine.nlp.pipeline import run_pipeline  # noqa: PLC0415

        return run_pipeline(text=text, title=title)
    except ImportError as exc:
        logger.error(
            "NLP pipeline import failed (is ai_engine on PYTHONPATH?): %s", exc
        )
        return None
    except Exception as exc:
        logger.error("NLP pipeline execution error: %s", exc)
        return None


@shared_task(
    bind=True,
    max_retries=1,
    default_retry_delay=60,
    queue="nlp",
    name="apps.articles.tasks.process_article_nlp",
    soft_time_limit=120,  # 2 minutes soft limit
    time_limit=180,  # 3 minutes hard limit
)
def process_article_nlp(self, article_id: str) -> Dict:
    """
    Run the full NLP pipeline on a single article and persist results.

    Steps:
      1. Fetch Article from DB
      2. Run ai_engine NLP pipeline (clean → lang → keywords → topic → sentiment → NER)
      3. Persist keywords, topic, sentiment_score and nlp_processed flag

    Args:
        article_id: UUID string of the Article to process.

    Returns:
        Dict with processing status and extracted fields.
    """
    task_id = self.request.id
    logger.info("[%s] Starting NLP for article: %s", task_id, article_id)
    start_time = time.time()

    try:
        from apps.articles.models import Article  # noqa: PLC0415

        try:
            article = Article.objects.get(pk=article_id)
        except Article.DoesNotExist:
            logger.error("[%s] Article %s not found.", task_id, article_id)
            return {
                "status": "error",
                "reason": "article_not_found",
                "article_id": article_id,
            }

        # Build the text to analyse
        text = article.content or ""
        title = article.title or ""

        if not text and not title:
            logger.warning("[%s] Article %s has no text content.", task_id, article_id)
            return {
                "status": "skipped",
                "reason": "no_content",
                "article_id": article_id,
            }

        # Run the NLP pipeline
        result = _run_nlp(text=text, title=title)

        if result is None:
            logger.error(
                "[%s] NLP pipeline returned None for article %s.", task_id, article_id
            )
            return {
                "status": "error",
                "reason": "pipeline_failed",
                "article_id": article_id,
            }

        if result.skipped:
            logger.info(
                "[%s] Article %s skipped: %s", task_id, article_id, result.skip_reason
            )
            return {
                "status": "skipped",
                "reason": result.skip_reason,
                "article_id": article_id,
            }

        # Persist extracted fields
        update_fields = ["updated_at"]

        if result.keywords:
            article.keywords = result.keywords
            update_fields.append("keywords")

        if result.topic:
            article.topic = result.topic
            update_fields.append("topic")

        if result.sentiment_score is not None:
            article.sentiment_score = result.sentiment_score
            update_fields.append("sentiment_score")

        # Phase 2.2 — Persist summary.
        # Prefer a Gemini-generated summary; fall back to whatever the NLP
        # pipeline produced (BART / extractive).  Only write if the article
        # does not already have a human-supplied summary so we don't destroy
        # richer scraped content.
        if not article.summary:
            # Build rich context for summarization (title + excerpt + content)
            summary_parts = []
            if title:
                summary_parts.append(f"Title: {title}")
            if article.url:
                summary_parts.append(f"URL: {article.url}")
            if article.topic:
                summary_parts.append(f"Topic: {article.topic}")
            tags_str = ", ".join(article.tags) if article.tags else ""
            if tags_str:
                summary_parts.append(f"Tags: {tags_str}")
            metadata = article.metadata or {}
            if metadata.get("excerpt"):
                summary_parts.append(f"Excerpt: {metadata['excerpt']}")
            if text:
                summary_parts.append(f"\nArticle Content:\n{text}")
            summary_text = "\n".join(summary_parts) if summary_parts else text

            # Try to use the article owner's API key if available (future: link articles to users)
            # For now falls back to env var key inside _summarize_with_gemini
            gemini_summary = _summarize_with_gemini(summary_text)
            chosen_summary = gemini_summary or result.summary
            # Final fallback: use first 200 chars of cleaned text if no AI summary
            if not chosen_summary and len(text) > 50:
                chosen_summary = text[:200] + "..." if len(text) > 200 else text
            if chosen_summary:
                article.summary = chosen_summary
                update_fields.append("summary")

        # Store NER entities in metadata JSON field
        if result.entities:
            if not isinstance(article.metadata, dict):
                article.metadata = {}
            article.metadata["entities"] = result.entities
            article.metadata["language"] = result.language
            article.metadata["topic_confidence"] = result.topic_confidence
            update_fields.append("metadata")

        # Mark NLP as processed
        article.nlp_processed = True
        update_fields.append("nlp_processed")

        article.save(update_fields=update_fields)

        elapsed = round(time.time() - start_time, 2)
        logger.info(
            "[%s] NLP complete for article %s in %.2fs — "
            "topic=%s, sentiment=%.4f, keywords=%d, summary=%s",
            task_id,
            article_id,
            elapsed,
            result.topic,
            result.sentiment_score or 0.0,
            len(result.keywords),
            "yes" if result.summary else "no",
        )

        return {
            "status": "success",
            "article_id": article_id,
            "topic": result.topic,
            "sentiment_score": result.sentiment_score,
            "keywords": result.keywords,
            "entities_count": len(result.entities),
            "summary_generated": bool(result.summary),
            "elapsed_seconds": elapsed,
        }

    except Exception as exc:
        logger.error(
            "[%s] Unexpected error processing article %s: %s", task_id, article_id, exc
        )
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@shared_task(
    bind=True,
    max_retries=1,
    queue="nlp",
    name="apps.articles.tasks.process_pending_articles_nlp",
    soft_time_limit=60,
    time_limit=90,
)
def process_pending_articles_nlp(self, batch_size: int = 10) -> Dict:
    """
    Queue NLP processing for articles that have not been processed yet.

    Fetches up to *batch_size* articles where ``nlp_processed=False`` and
    dispatches individual :func:`process_article_nlp` tasks for each.

    Args:
        batch_size: Maximum number of articles to enqueue (default 50).

    Returns:
        Dict summarising how many tasks were queued.
    """
    task_id = self.request.id
    logger.info(
        "[%s] Queuing NLP for pending articles (batch_size=%d)", task_id, batch_size
    )

    try:
        from apps.articles.models import Article  # noqa: PLC0415

        pending = Article.objects.filter(nlp_processed=False).values_list(
            "id", flat=True
        )[:batch_size]

        queued = 0
        for article_id in pending:
            # Stagger dispatch using countdown (non-blocking) instead of sleep.
            # 12 s apart keeps us under 5 RPM to avoid overwhelming the worker
            process_article_nlp.apply_async(
                args=[str(article_id)],
                countdown=queued * 12,
                queue="nlp",
            )
            queued += 1

        logger.info("[%s] Queued %d NLP tasks.", task_id, queued)
        return {"status": "success", "queued": queued}

    except Exception as exc:
        logger.error("[%s] process_pending_articles_nlp failed: %s", task_id, exc)
        raise self.retry(exc=exc, countdown=120)


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    queue="default",
    name="apps.articles.tasks.fetch_article_excerpt",
)
def fetch_article_excerpt(self, article_id: str) -> dict:
    """
    Fetch a real human-readable excerpt from the article's URL.

    Strategy (fastest → richest):
      1. og:description  — Open Graph description tag (best for news sites)
      2. meta description — standard HTML meta description
      3. twitter:description — Twitter card description
      4. First meaningful <p> tag from the article body
      5. trafilatura full-text extraction fallback

    Result stored in article.metadata['excerpt'] — no DB migration needed.
    """
    task_id = self.request.id or "no-task-id"
    try:
        from apps.articles.models import Article  # noqa: PLC0415

        try:
            article = Article.objects.get(pk=article_id)
        except Article.DoesNotExist:
            return {"status": "not_found", "article_id": article_id}

        # Skip if already fetched a real excerpt
        existing = (article.metadata or {}).get("excerpt", "")
        if existing and len(existing) > 30:
            return {"status": "skipped", "reason": "already_has_excerpt"}

        url = article.url or ""
        if not url.startswith("http"):
            return {"status": "skipped", "reason": "no_http_url"}

        logger.info("[%s] fetch_article_excerpt: fetching %s", task_id, url[:80])

        excerpt = ""
        try:
            import requests as req  # noqa: PLC0415
            from bs4 import BeautifulSoup  # noqa: PLC0415

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml",
            }
            resp = req.get(url, headers=headers, timeout=8, allow_redirects=True)
            resp.raise_for_status()
            html = resp.text
            soup = BeautifulSoup(html, "html.parser")

            # 1. og:description (best quality — written by publishers)
            og = soup.find("meta", property="og:description")
            if og and og.get("content", "").strip():
                excerpt = og["content"].strip()

            # 2. meta description
            if not excerpt:
                meta = soup.find("meta", attrs={"name": "description"})
                if meta and meta.get("content", "").strip():
                    excerpt = meta["content"].strip()

            # 3. twitter:description
            if not excerpt:
                tw = soup.find("meta", attrs={"name": "twitter:description"})
                if tw and tw.get("content", "").strip():
                    excerpt = tw["content"].strip()

            # 4. First meaningful <p> tag (skip nav/header boilerplate)
            if not excerpt:
                for p in soup.find_all("p"):
                    text = p.get_text(strip=True)
                    if len(text) > 80:
                        excerpt = text
                        break

            # 5. trafilatura full-text fallback
            if not excerpt:
                try:
                    import trafilatura  # noqa: PLC0415

                    extracted = trafilatura.extract(
                        html,
                        include_comments=False,
                        include_tables=False,
                        no_fallback=False,
                    )
                    if extracted:
                        sentences = [
                            s.strip()
                            for s in extracted.replace("\n", " ").split(".")
                            if len(s.strip()) > 40
                        ]
                        excerpt = ". ".join(sentences[:2]) + "." if sentences else ""
                except Exception:
                    pass

        except Exception as exc:
            logger.warning(
                "[%s] fetch_article_excerpt: HTTP fetch failed for %s: %s",
                task_id,
                url[:60],
                exc,
            )

        # Truncate to 220 chars at word boundary
        if len(excerpt) > 220:
            excerpt = excerpt[:220].rsplit(" ", 1)[0] + "…"

        if excerpt:
            meta = article.metadata or {}
            meta["excerpt"] = excerpt
            article.metadata = meta
            # Sanitise metadata — remove null bytes and invalid Unicode
            # that PostgreSQL JSON rejects.
            try:
                import json as _json
                import re as _re

                raw = _json.dumps(article.metadata, ensure_ascii=True)
                # Strip null bytes \u0000 which PG cannot store in JSON
                raw = raw.replace("\\u0000", "").replace("\x00", "")
                raw = _re.sub(r"\\u0000", "", raw)
                article.metadata = _json.loads(raw)
            except Exception:
                article.metadata = {}
            article.save(update_fields=["metadata", "updated_at"])
            logger.info(
                "[%s] fetch_article_excerpt: saved %d chars for article %s",
                task_id,
                len(excerpt),
                article_id,
            )
            return {"status": "success", "excerpt_length": len(excerpt)}
        else:
            logger.warning(
                "[%s] fetch_article_excerpt: no excerpt found for %s", task_id, url[:60]
            )
            return {"status": "no_excerpt", "article_id": article_id}

    except Exception as exc:
        logger.error(
            "[%s] fetch_article_excerpt FAILED: %s", task_id, exc, exc_info=True
        )
        raise self.retry(exc=exc, countdown=30)


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    queue="default",
    name="apps.articles.tasks.fetch_pending_excerpts",
)
def fetch_pending_excerpts(self, batch_size: int = 30) -> dict:
    """Queue excerpt-fetching for all articles missing a metadata excerpt."""
    task_id = self.request.id or "no-task-id"
    try:
        from apps.articles.models import Article  # noqa: PLC0415

        all_articles = list(
            Article.objects.filter(url__startswith="http").values("id", "metadata")
        )
        to_fetch = [
            str(a["id"])
            for a in all_articles
            if not (a.get("metadata") or {}).get("excerpt")
        ][:batch_size]

        for i, article_id in enumerate(to_fetch):
            fetch_article_excerpt.apply_async(
                args=[article_id], countdown=i * 2, queue="default"
            )

        logger.info(
            "[%s] fetch_pending_excerpts: queued %d tasks", task_id, len(to_fetch)
        )
        return {"status": "success", "queued": len(to_fetch)}
    except Exception as exc:
        logger.error(
            "[%s] fetch_pending_excerpts FAILED: %s", task_id, exc, exc_info=True
        )
        raise self.retry(exc=exc, countdown=60)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="apps.articles.tasks.summarize_article",
)
def summarize_article(self, article_id: str, force: bool = False) -> Dict:
    """
    Phase 2.2 — Standalone BART summarization task.

    Generates an abstractive summary for a single article using
    ``facebook/bart-large-cnn`` and persists it to ``Article.summary``.

    This task can be called independently (e.g. for re-summarization or
    when only summarization is needed without the full NLP pipeline).

    Args:
        article_id: UUID string of the Article to summarize.
        force:      If True, overwrite an existing summary. Default False.

    Returns:
        Dict with status and summary metadata.
    """
    task_id = self.request.id
    logger.info("[%s] Starting BART summarization for article: %s", task_id, article_id)
    start_time = time.time()

    try:
        from apps.articles.models import Article  # noqa: PLC0415

        try:
            article = Article.objects.get(pk=article_id)
        except Article.DoesNotExist:
            logger.error("[%s] Article %s not found.", task_id, article_id)
            return {
                "status": "error",
                "reason": "article_not_found",
                "article_id": article_id,
            }

        # Skip if already has a real summary (or sentinel) and force is not set
        if article.summary and not force:
            logger.info(
                "[%s] Article %s already has summary (or sentinel); skipping "
                "(use force=True to overwrite). summary_prefix=%r",
                task_id,
                article_id,
                article.summary[:40],
            )
            return {
                "status": "skipped",
                "reason": "already_summarized",
                "article_id": article_id,
            }

        # Build the best possible text to summarize.
        # Many HackerNews articles only have a title + URL — no full content.
        # We construct a rich prompt from all available fields so Gemini can
        # still produce a useful summary.
        content = article.content or ""
        title = article.title or ""
        url = article.url or ""
        topic = article.topic or ""
        tags = ", ".join(article.tags) if article.tags else ""
        keywords = ", ".join(article.keywords) if article.keywords else ""
        metadata = article.metadata or {}

        # Build text from whatever is available
        text_parts = []
        if title:
            text_parts.append(f"Title: {title}")
        if url:
            text_parts.append(f"URL: {url}")
        if topic:
            text_parts.append(f"Topic: {topic}")
        if tags:
            text_parts.append(f"Tags: {tags}")
        if keywords:
            text_parts.append(f"Keywords: {keywords}")
        # Include HN metadata if present
        if metadata:
            if metadata.get("score"):
                text_parts.append(f"HackerNews Score: {metadata['score']}")
            if metadata.get("comments"):
                text_parts.append(f"Comments: {metadata['comments']}")
            # Include excerpt (fetched by fetch_article_excerpt task) — this
            # gives the AI real article description even when full content is missing
            if metadata.get("excerpt"):
                text_parts.append(f"Excerpt: {metadata['excerpt']}")
        if content:
            text_parts.append(f"\nArticle Content:\n{content}")

        text = "\n".join(text_parts)

        if not text.strip() or (not content and not title):
            logger.warning(
                "[%s] Article %s has no usable text at all.", task_id, article_id
            )
            article.summary = SUMMARY_FAILED_SENTINEL
            article.save(update_fields=["summary", "updated_at"])
            return {"status": "skipped", "reason": "no_text", "article_id": article_id}

        logger.info(
            "[%s] Article %s: content_len=%d, title=%r — building summary from available fields.",
            task_id,
            article_id,
            len(content),
            title[:60],
        )

        # Try Gemini first, then fall back to BART/extractive summarizer
        logger.info(
            "[%s] Attempting Gemini summarization for article %s", task_id, article_id
        )
        summary = _summarize_with_gemini(text)

        if not summary:
            logger.error(
                "[%s] Gemini summarization failed for article %s (title=%r). "
                "Writing failure sentinel to prevent infinite re-queuing.",
                task_id,
                article_id,
                title[:60],
            )
            article.summary = SUMMARY_FAILED_SENTINEL
            article.save(update_fields=["summary", "updated_at"])
            return {
                "status": "error",
                "reason": "gemini_failed",
                "article_id": article_id,
            }

        article.summary = summary
        article.save(update_fields=["summary", "updated_at"])

        elapsed = round(time.time() - start_time, 2)
        logger.info(
            "[%s] Summary generated for article %s in %.2fs (%d chars).",
            task_id,
            article_id,
            elapsed,
            len(summary),
        )

        return {
            "status": "success",
            "article_id": article_id,
            "summary_length": len(summary),
            "elapsed_seconds": elapsed,
        }

    except Exception as exc:
        logger.error(
            "[%s] Unexpected error summarizing article %s: %s", task_id, article_id, exc
        )
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@shared_task(
    bind=True,
    max_retries=1,
    queue="nlp",
    name="apps.articles.tasks.summarize_pending_articles",
)
def summarize_pending_articles(self, batch_size: int = 500) -> Dict:
    """
    Phase 2.2 — Queue BART summarization for articles without a summary.

    Fetches up to *batch_size* articles that have been NLP-processed but
    still lack a summary, and dispatches :func:`summarize_article` tasks.

    Articles that were already processed by the full NLP pipeline (which
    includes summarization) will typically already have a summary.  This
    task handles edge cases: very old articles imported before Phase 2.2,
    or articles whose summarization failed transiently.

    Args:
        batch_size: Maximum number of articles to enqueue (default 500).

    Returns:
        Dict summarising how many tasks were queued.
    """
    task_id = self.request.id
    logger.info(
        "[%s] Queuing summarization for articles without summary (batch_size=%d)",
        task_id,
        batch_size,
    )

    try:
        from apps.articles.models import Article  # noqa: PLC0415

        # Target articles that have no summary AND are not marked with the
        # failure sentinel.  This prevents infinite re-queuing of articles
        # that have already exhausted all summarization attempts.
        pending = list(
            Article.objects.filter(summary="")
            .exclude(summary=SUMMARY_FAILED_SENTINEL)
            .values_list("id", flat=True)[:batch_size]
        )
        # Also pick up NULL summaries (legacy rows)
        pending_null = list(
            Article.objects.filter(summary__isnull=True).values_list("id", flat=True)[
                : batch_size - len(pending)
            ]
        )
        all_pending = pending + pending_null

        logger.info(
            "[%s] summarize_pending_articles: found %d articles needing summaries.",
            task_id,
            len(all_pending),
        )

        queued = 0
        for article_id in all_pending:
            summarize_article.apply_async(args=[str(article_id)])
            queued += 1

        logger.info("[%s] Queued %d summarization tasks.", task_id, queued)
        return {"status": "success", "queued": queued}

    except Exception as exc:
        logger.error(
            "[%s] summarize_pending_articles FAILED: %s", task_id, exc, exc_info=True
        )
        raise self.retry(exc=exc, countdown=120)
