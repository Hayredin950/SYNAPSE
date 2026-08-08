"""
SYNAPSE AI Feature Endpoints — 40-Feature Implementation

Endpoints:
  POST /api/v1/ai/debate/          — Debate mode (pro/con analysis)
  POST /api/v1/ai/translate/       — One-click article translation
  POST /api/v1/ai/paper-to-blog/   — arXiv paper → readable blog post
  GET  /api/v1/ai/catch-up/        — "What you missed" brief
  POST /api/v1/ai/research/        — Autonomous research brief
  POST /api/v1/ai/tts/             — Text-to-speech (stream)
  POST /api/v1/ai/podcast/         — Weekly digest podcast script
  GET  /api/v1/ai/related/         — Related articles by content
  POST /api/v1/ai/code-extract/    — Extract & explain code snippets
"""

import json
import logging
import os

from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

logger = logging.getLogger(__name__)


def _get_ai_client():
    """Return an OpenAI-compatible client pointed at the Replit AI proxy."""
    try:
        import openai as _openai
        base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL", "").strip()
        api_key  = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY", "").strip() or "sk-replit"
        if not base_url:
            return None
        # Replit proxy: base_url = http://localhost:1106/modelfarm/openai
        # SDK appends /chat/completions  →  correct full path
        return _openai.OpenAI(base_url=base_url, api_key=api_key)
    except Exception as exc:
        logger.warning("Could not create AI client: %s", exc)
        return None


def _chat(system: str, user: str, max_tokens: int = 1200) -> str:
    """Single-turn AI chat helper. Returns the assistant text."""
    client = _get_ai_client()
    if not client:
        raise RuntimeError("AI service unavailable — no API key configured.")
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content.strip()


# ── Feature 12: Debate Mode ───────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def debate_mode(request):
    """
    Generate balanced pro/con arguments + alternative perspectives for an article.
    Body: { title, content/summary, url? }
    """
    title   = request.data.get("title", "").strip()
    content = (request.data.get("content") or request.data.get("summary") or "").strip()
    if not title and not content:
        return Response({"success": False, "error": "title or content required"},
                        status=status.HTTP_400_BAD_REQUEST)

    system = (
        "You are an expert debate analyst and critical thinker. "
        "Present balanced, well-reasoned arguments. Use markdown."
    )
    prompt = (
        f"Article: **{title}**\n\n{content[:2500]}\n\n"
        "Provide a structured debate analysis:\n\n"
        "## 👍 Arguments For / In Support\n(3 strong supporting points)\n\n"
        "## 👎 Arguments Against / Criticisms\n(3 substantive criticisms)\n\n"
        "## 🔀 Alternative Perspectives\n(2 different viewpoints)\n\n"
        "## ⚖️ Balanced Verdict\n(one paragraph synthesis)\n\n"
        "Be insightful, specific, and avoid generic statements."
    )
    try:
        result = _chat(system, prompt, max_tokens=1500)
        return Response({"success": True, "debate": result})
    except Exception as exc:
        logger.error("debate_mode error: %s", exc)
        return Response({"success": False, "error": str(exc)},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)


# ── Feature 14: Translation ───────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def translate_article(request):
    """
    Translate article text to the requested language.
    Body: { text, title?, target_language }
    """
    text     = (request.data.get("text") or request.data.get("content") or "").strip()
    title    = request.data.get("title", "").strip()
    lang     = request.data.get("target_language", "Spanish").strip()
    if not text:
        return Response({"success": False, "error": "text is required"},
                        status=status.HTTP_400_BAD_REQUEST)

    system = (
        f"You are a professional technical translator specializing in technology content. "
        f"Translate to {lang} preserving all technical terms accurately. "
        f"Output ONLY the translated text in markdown, no explanation."
    )
    combined = f"# {title}\n\n{text[:3000]}" if title else text[:3000]
    try:
        result = _chat(system, combined, max_tokens=2000)
        return Response({"success": True, "translated": result, "language": lang})
    except Exception as exc:
        logger.error("translate_article error: %s", exc)
        return Response({"success": False, "error": str(exc)},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)


# ── Feature 19: Paper-to-Blog ─────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def paper_to_blog(request):
    """
    Convert a dense academic/arXiv paper summary into a readable blog post.
    Body: { title, abstract/content, authors? }
    """
    title   = request.data.get("title", "").strip()
    content = (request.data.get("abstract") or request.data.get("content") or "").strip()
    authors = request.data.get("authors", "").strip()

    if not content:
        return Response({"success": False, "error": "abstract or content required"},
                        status=status.HTTP_400_BAD_REQUEST)

    system = (
        "You are a senior tech journalist who specializes in making complex research "
        "accessible to developers and engineers. Write engaging, clear blog posts."
    )
    prompt = (
        f"Convert this academic paper into an engaging blog post:\n\n"
        f"**Title:** {title}\n"
        f"{'**Authors:** ' + authors + chr(10) if authors else ''}"
        f"**Content:** {content[:2500]}\n\n"
        f"Write a blog post with:\n"
        f"1. A catchy opening hook\n"
        f"2. What problem this solves (for developers)\n"
        f"3. How it works (plain English, with an analogy)\n"
        f"4. Key results / benchmarks in simple terms\n"
        f"5. Why it matters for engineers\n"
        f"6. How to get started / where to learn more\n\n"
        f"Use markdown. Be engaging, concrete, and avoid jargon. "
        f"Target audience: senior software engineers."
    )
    try:
        result = _chat(system, prompt, max_tokens=1800)
        return Response({"success": True, "blog_post": result})
    except Exception as exc:
        logger.error("paper_to_blog error: %s", exc)
        return Response({"success": False, "error": str(exc)},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)


# ── Feature 23: Catch Me Up ───────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def catch_me_up(request):
    """
    AI-generated brief of what the user missed in the last N days.
    Query params: days (default 3)
    """
    try:
        days = int(request.query_params.get("days", 3))
        days = max(1, min(days, 14))
    except ValueError:
        days = 3

    # Gather recent high-signal content
    from django.utils import timezone
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(days=days)
    articles, papers, repos = [], [], []

    try:
        from apps.articles.models import Article
        qs = Article.objects.filter(scraped_at__gte=cutoff).order_by("-scraped_at")[:20]
        articles = [{"title": a.title, "summary": (a.summary or "")[:200], "source": a.source_type} for a in qs]
    except Exception:
        pass

    try:
        from apps.papers.models import ResearchPaper
        qs = ResearchPaper.objects.filter(fetched_at__gte=cutoff).order_by("-fetched_at")[:10]
        papers = [{"title": p.title, "abstract": (p.abstract or "")[:200]} for p in qs]
    except Exception:
        pass

    try:
        from apps.repositories.models import Repository
        qs = Repository.objects.filter(scraped_at__gte=cutoff).order_by("-stars")[:10]
        repos = [{"name": r.full_name, "description": (r.description or "")[:150], "stars": r.stars} for r in qs]
    except Exception:
        pass

    if not articles and not papers and not repos:
        return Response({"success": True, "brief": "No new content found in the last few days. Check back soon!"})

    content_summary = ""
    if articles:
        content_summary += f"## Recent Articles ({len(articles)} total)\n"
        for a in articles[:8]:
            content_summary += f"- **{a['title']}** ({a.get('source','')}) — {a.get('summary','')[:100]}\n"
        content_summary += "\n"
    if papers:
        content_summary += f"## Research Papers ({len(papers)} total)\n"
        for p in papers[:5]:
            content_summary += f"- **{p['title']}** — {p.get('abstract','')[:100]}\n"
        content_summary += "\n"
    if repos:
        content_summary += f"## Trending Repos ({len(repos)} total)\n"
        for r in repos[:5]:
            content_summary += f"- **{r['name']}** ⭐{r.get('stars','?')} — {r.get('description','')[:80]}\n"

    system = (
        "You are a sharp tech editor who writes crisp, insightful briefings. "
        "Be concise, pick the most important signals, and help the reader prioritize. "
        "Use markdown with emojis for section headers."
    )
    prompt = (
        f"The user has been away for {days} day(s). Here's what they missed:\n\n"
        f"{content_summary}\n\n"
        f"Write a 'Catch Me Up' brief that:\n"
        f"1. Highlights the 3-5 most important stories/papers/repos\n"
        f"2. Identifies any major themes or trends\n"
        f"3. Gives a 1-sentence verdict on each highlight\n"
        f"4. Ends with 'Your #1 priority read'\n\n"
        f"Keep it tight — this is a busy person who wants signal, not noise."
    )
    try:
        result = _chat(system, prompt, max_tokens=1200)
        return Response({
            "success": True,
            "brief": result,
            "stats": {"articles": len(articles), "papers": len(papers), "repos": len(repos), "days": days},
        })
    except Exception as exc:
        logger.error("catch_me_up error: %s", exc)
        return Response({"success": False, "error": str(exc)},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)


# ── Feature 11: AI Research Agent ────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def research_brief(request):
    """
    Generate an autonomous research brief on any topic.
    Body: { topic, depth? ('quick'|'deep'), focus? }
    """
    topic = request.data.get("topic", "").strip()
    depth = request.data.get("depth", "deep")
    focus = request.data.get("focus", "engineers")  # target audience

    if not topic:
        return Response({"success": False, "error": "topic is required"},
                        status=status.HTTP_400_BAD_REQUEST)

    # Try to find relevant content in the DB to ground the research
    context_items = []
    try:
        from apps.articles.models import Article
        from django.db.models import Q
        qs = Article.objects.filter(
            Q(title__icontains=topic) | Q(tags__icontains=topic) | Q(summary__icontains=topic[:20])
        ).order_by("-scraped_at")[:10]
        context_items = [f"- {a.title}: {(a.summary or '')[:150]}" for a in qs]
    except Exception:
        pass

    context_str = ""
    if context_items:
        context_str = "\n\nRelated content in SYNAPSE:\n" + "\n".join(context_items[:6])

    system = (
        "You are a world-class research analyst and senior engineer. "
        "Write comprehensive, accurate, and actionable research briefs."
    )
    tokens = 2500 if depth == "deep" else 1200
    prompt = (
        f"Write a comprehensive research brief on: **{topic}**\n"
        f"Target audience: {focus}\n"
        f"{context_str}\n\n"
        f"Structure your brief:\n\n"
        f"# 📋 Executive Summary\n(2-3 sentence TL;DR)\n\n"
        f"# 🔍 What Is It?\n(clear explanation, no jargon)\n\n"
        f"# 📈 Current State & Landscape\n(key players, tools, projects)\n\n"
        f"# 🔧 Technical Deep-Dive\n(how it works, key concepts)\n\n"
        f"# ⚡ Key Developments (2024-2025)\n(recent breakthroughs)\n\n"
        f"# 🚀 Practical Applications\n(real-world use cases)\n\n"
        f"# ⚠️ Challenges & Limitations\n\n"
        f"# 📚 Further Reading\n(key resources, papers, repos)\n\n"
        f"# 🎯 Action Items\n(what an engineer should do next)\n\n"
        f"Be specific, cite real projects/papers where possible, use markdown."
    )
    try:
        result = _chat(system, prompt, max_tokens=tokens)
        return Response({"success": True, "brief": result, "topic": topic})
    except Exception as exc:
        logger.error("research_brief error: %s", exc)
        return Response({"success": False, "error": str(exc)},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)


# ── Feature 13: Code Extractor ────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def code_extract(request):
    """
    Extract, identify, and explain code snippets from article content.
    Body: { content, title? }
    """
    content = (request.data.get("content") or request.data.get("text") or "").strip()
    title   = request.data.get("title", "").strip()

    if not content:
        return Response({"success": False, "error": "content required"},
                        status=status.HTTP_400_BAD_REQUEST)

    system = (
        "You are a senior software engineer. Extract and explain code from articles. "
        "Output valid JSON only."
    )
    prompt = (
        f"Article: {title}\n\nContent:\n{content[:3000]}\n\n"
        f"Extract ALL code snippets from this content. For each snippet:\n"
        f"Return a JSON array of objects with: language, code, explanation, runnable (bool)\n"
        f"Example: [{{'language':'python','code':'...','explanation':'...','runnable':true}}]\n\n"
        f"If no code found, return []\n"
        f"Return ONLY the JSON array, no other text."
    )
    try:
        raw = _chat(system, prompt, max_tokens=1500)
        # Parse JSON from response
        import re
        json_match = re.search(r'\[.*\]', raw, re.DOTALL)
        snippets = json.loads(json_match.group()) if json_match else []
        return Response({"success": True, "snippets": snippets})
    except Exception as exc:
        logger.error("code_extract error: %s", exc)
        return Response({"success": True, "snippets": [], "error": str(exc)})


# ── Feature 8: Text-to-Speech ─────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def text_to_speech(request):
    """
    Convert article text to speech via OpenAI TTS.
    Body: { text, voice? ('alloy'|'echo'|'fable'|'onyx'|'nova'|'shimmer') }
    Returns binary MP3 audio stream.
    """
    text  = (request.data.get("text") or "").strip()[:4096]
    voice = request.data.get("voice", "alloy")

    VALID_VOICES = {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}
    if voice not in VALID_VOICES:
        voice = "alloy"

    if not text:
        return Response({"success": False, "error": "text is required"},
                        status=status.HTTP_400_BAD_REQUEST)

    try:
        import openai as _openai
        base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL", "").strip()
        api_key  = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY", "").strip() or "sk-replit"

        if not base_url:
            return Response({"success": False, "error": "TTS not configured"},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)

        client = _openai.OpenAI(base_url=base_url, api_key=api_key)
        audio_response = client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text,
            response_format="mp3",
        )
        audio_data = audio_response.read()

        from django.http import HttpResponse
        resp = HttpResponse(audio_data, content_type="audio/mpeg")
        resp["Content-Disposition"] = 'attachment; filename="synapse-tts.mp3"'
        resp["Cache-Control"] = "no-cache"
        return resp

    except Exception as exc:
        logger.error("text_to_speech error: %s", exc)
        return Response(
            {"success": False, "error": f"TTS failed: {exc}"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


# ── Feature 15: AI Podcast Script ─────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def generate_podcast(request):
    """
    Generate a podcast script from top articles (two-host format).
    Body: { articles: [{title, summary}], duration_minutes? }
    """
    articles = request.data.get("articles", [])
    duration = int(request.data.get("duration_minutes", 5))
    duration = max(3, min(duration, 10))

    if not articles:
        # Fall back to recent articles
        try:
            from apps.articles.models import Article
            qs = Article.objects.order_by("-scraped_at")[:8]
            articles = [{"title": a.title, "summary": (a.summary or "")[:200]} for a in qs]
        except Exception:
            pass

    articles_str = "\n".join([f"- **{a.get('title','')}**: {a.get('summary','')[:150]}" for a in articles[:8]])

    system = (
        "You are a podcast script writer for a tech show. "
        "Write natural, engaging dialogue. Hosts: Alex (analytical) and Sam (enthusiastic)."
    )
    prompt = (
        f"Write a {duration}-minute tech podcast script covering these stories:\n\n"
        f"{articles_str}\n\n"
        f"Format:\n"
        f"[INTRO]\nALEX: ...\nSAM: ...\n\n"
        f"[STORY 1: Title]\nALEX: ...\nSAM: ...\n\n"
        f"...continue for all stories...\n\n"
        f"[OUTRO]\nALEX: ...\nSAM: ...\n\n"
        f"Make it conversational, include listener takeaways, running ~{duration*150} words."
    )
    try:
        result = _chat(system, prompt, max_tokens=2500)
        return Response({"success": True, "script": result, "duration_minutes": duration})
    except Exception as exc:
        logger.error("generate_podcast error: %s", exc)
        return Response({"success": False, "error": str(exc)},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)


# ── Feature 5: Related Articles ───────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([AllowAny])
def related_articles(request):
    """
    Return related articles based on tags/topic similarity.
    Query params: article_id (required), limit (default 5)
    """
    article_id = request.query_params.get("article_id", "")
    limit      = min(int(request.query_params.get("limit", 5)), 10)

    if not article_id:
        return Response({"success": False, "error": "article_id required"},
                        status=status.HTTP_400_BAD_REQUEST)

    try:
        from apps.articles.models import Article
        from django.db.models import Q

        try:
            source = Article.objects.get(pk=article_id)
        except (Article.DoesNotExist, Exception):
            return Response({"success": True, "articles": []})

        # Build similarity query: same topic OR overlapping tags
        tags = getattr(source, "tags", []) or []
        qs = Article.objects.exclude(pk=article_id)

        if source.topic:
            qs = qs.filter(topic=source.topic)
        elif tags:
            tag_q = Q()
            for tag in tags[:3]:
                tag_q |= Q(tags__icontains=tag)
            qs = qs.filter(tag_q)
        else:
            qs = qs.filter(source_type=source.source_type)

        qs = qs.order_by("-scraped_at")[:limit]

        from apps.articles.serializers import ArticleSerializer
        serializer = ArticleSerializer(qs, many=True, context={"request": request})
        return Response({"success": True, "articles": serializer.data})

    except Exception as exc:
        logger.error("related_articles error: %s", exc)
        return Response({"success": True, "articles": []})


# ── Feature: AI Deep-Dive Analysis ────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def deep_dive(request):
    """
    Generate a thorough, multi-angle deep-dive analysis of an article.
    Body: { title, content, article_id? }
    """
    title   = request.data.get("title", "Untitled")
    content = request.data.get("content", "")

    system = (
        "You are a senior technology analyst and researcher. "
        "Provide thorough, multi-angle analysis of content with concrete insights."
    )
    prompt = (
        f"Perform a comprehensive deep-dive analysis of this article:\n\n"
        f"**{title}**\n\n{content[:4000]}\n\n"
        f"Structure your analysis:\n\n"
        f"## 🔍 Core Thesis\n(What is the main argument/finding?)\n\n"
        f"## 📊 Evidence & Support\n(Key data points, proof, examples)\n\n"
        f"## ⚡ Implications\n(What does this mean for the field?)\n\n"
        f"## 🔗 Connections\n(How does this relate to other trends/topics?)\n\n"
        f"## 🤔 Critical Assessment\n(Strengths, weaknesses, gaps)\n\n"
        f"## 🎯 Actionable Takeaways\n(What should you do with this information?)\n\n"
        f"Be specific, analytical, and insightful."
    )
    try:
        result = _chat(system, prompt, max_tokens=2000)
        return Response({"success": True, "analysis": result, "title": title})
    except Exception as exc:
        logger.error("deep_dive error: %s", exc)
        return Response({"success": False, "error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
