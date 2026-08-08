"""
TASK-601-B2: Plan-and-Execute Research Agent

Multi-step LangGraph-style research workflow:
  1. PLAN    — LLM decomposes query into 3-5 sub-questions
  2. RESEARCH — For each sub-question: search ArXiv + GitHub + knowledge base
  3. SYNTHESIZE — LLM synthesizes findings per sub-question with citations
  4. REPORT  — LLM generates final structured markdown report
  5. FORMAT  — Inline citations [1][2]... linked to sources

Callable as a Celery task via run_research_session(session_id).
Streams progress by updating ResearchSession.status + sub_questions.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from typing import Generator

import requests

logger = logging.getLogger(__name__)

# ── Step 1: Plan ──────────────────────────────────────────────────────────────


def plan_sub_questions(query: str, llm_client=None) -> list[str]:
    """
    Decompose a research query into 3-5 focused sub-questions.
    Falls back to rule-based decomposition if LLM unavailable.
    """
    if llm_client:
        try:
            prompt = (
                f"You are a research assistant. Break down the following research question "
                f"into 3-5 specific, focused sub-questions that will help answer it comprehensively.\n\n"
                f"Research question: {query}\n\n"
                f"Return ONLY a JSON array of sub-questions, e.g.: "
                f'["sub-q 1", "sub-q 2", "sub-q 3"]'
            )
            resp = llm_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.3,
            )
            raw = resp.choices[0].message.content.strip()
            # Extract JSON array
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if match:
                return json.loads(match.group())[:5]
        except Exception as exc:
            logger.warning("LLM plan failed, using rule-based: %s", exc)

    # Rule-based fallback: generate sub-questions from query tokens
    words = query.split()
    return [
        f"What is the current state of research on {query}?",
        f"What are the main methodologies used for {' '.join(words[:5])}?",
        f"What are the open challenges and limitations in {' '.join(words[:4])}?",
        f"What are the most cited papers on {query}?",
        f"What are practical applications of {' '.join(words[:3])}?",
    ][:5]


# ── Step 2: Research ──────────────────────────────────────────────────────────


def search_arxiv(query: str, max_results: int = 5) -> list[dict]:
    """Search ArXiv API for papers matching the query."""
    try:
        import urllib.parse

        q = urllib.parse.quote(query)
        url = f"http://export.arxiv.org/api/query?search_query=all:{q}&max_results={max_results}&sortBy=relevance"
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()

        # Parse Atom feed
        results = []
        entries = re.findall(r"<entry>(.*?)</entry>", resp.text, re.DOTALL)
        for entry in entries:
            title = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
            summary = re.search(r"<summary>(.*?)</summary>", entry, re.DOTALL)
            link = re.search(r"<id>(.*?)</id>", entry)
            authors = re.findall(r"<name>(.*?)</name>", entry)

            if title and link:
                results.append(
                    {
                        "title": title.group(1).strip().replace("\n", " "),
                        "url": link.group(1).strip(),
                        "abstract": (
                            summary.group(1).strip().replace("\n", " ")[:500]
                            if summary
                            else ""
                        ),
                        "authors": authors[:3],
                        "type": "paper",
                        "source": "arxiv",
                    }
                )
        return results
    except Exception as exc:
        logger.warning("ArXiv search failed for '%s': %s", query, exc)
        return []


def search_github(query: str, max_results: int = 3) -> list[dict]:
    """Search GitHub repos related to the query."""
    try:
        token = os.environ.get("GITHUB_TOKEN", "")
        headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            headers["Authorization"] = f"token {token}"
        url = f"https://api.github.com/search/repositories?q={requests.utils.quote(query)}&sort=stars&per_page={max_results}"
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        repos = resp.json().get("items", [])
        return [
            {
                "title": r["full_name"],
                "url": r["html_url"],
                "abstract": r.get("description", "")[:300],
                "stars": r.get("stargazers_count", 0),
                "type": "repository",
                "source": "github",
            }
            for r in repos
        ]
    except Exception as exc:
        logger.warning("GitHub search failed for '%s': %s", query, exc)
        return []


def search_knowledge_base(query: str, max_results: int = 5) -> list[dict]:
    """Search Synapse knowledge base via internal API."""
    try:
        from apps.core.models import KnowledgeNode  # noqa: PLC0415

        nodes = KnowledgeNode.objects.filter(name__icontains=query.split()[0]).order_by(
            "-mention_count"
        )[:max_results]
        return [
            {
                "title": node.name,
                "url": node.metadata.get("url", ""),
                "abstract": node.description[:300],
                "type": node.entity_type,
                "source": "knowledge_base",
            }
            for node in nodes
        ]
    except Exception as exc:
        logger.warning("KB search failed: %s", exc)
        return []


def research_sub_question(sub_question: str) -> dict:
    """Research a single sub-question. Returns {sub_question, sources}."""
    sources = []
    # Parallel search (simplified — run sequentially)
    sources.extend(search_arxiv(sub_question, max_results=3))
    sources.extend(search_github(sub_question, max_results=2))
    sources.extend(search_knowledge_base(sub_question, max_results=2))
    return {
        "sub_question": sub_question,
        "sources": sources,
    }


# ── Step 3: Synthesize ────────────────────────────────────────────────────────


def synthesize_findings(research_results: list[dict], llm_client=None) -> list[dict]:
    """
    For each sub-question + its sources, write a synthesis paragraph.
    Returns list of {sub_question, synthesis, sources} dicts.
    """
    synthesized = []
    for result in research_results:
        sub_q = result["sub_question"]
        sources = result["sources"]

        source_text = "\n".join(
            f"[{i+1}] {s['title']}: {s.get('abstract', '')[:200]}"
            for i, s in enumerate(sources[:5])
        )

        if llm_client and source_text:
            try:
                prompt = (
                    f"You are a research assistant writing a synthesis paragraph.\n\n"
                    f"Sub-question: {sub_q}\n\n"
                    f"Sources:\n{source_text}\n\n"
                    f"Write a concise 2-3 sentence synthesis paragraph that answers the sub-question "
                    f"using these sources. Use inline citations like [1], [2]."
                )
                resp = llm_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=300,
                    temperature=0.5,
                )
                synthesis = resp.choices[0].message.content.strip()
            except Exception as exc:
                logger.warning("Synthesis LLM call failed: %s", exc)
                synthesis = (
                    f"Research on '{sub_q}' identified {len(sources)} relevant sources."
                )
        else:
            synthesis = (
                f"Research on '{sub_q}' identified {len(sources)} relevant sources: "
                + ", ".join(s["title"][:60] for s in sources[:3])
            )

        synthesized.append(
            {
                "sub_question": sub_q,
                "synthesis": synthesis,
                "sources": sources,
            }
        )
    return synthesized


# ── Step 4: Report ────────────────────────────────────────────────────────────


def generate_report(
    query: str,
    synthesized_results: list[dict],
    all_sources: list[dict],
    llm_client=None,
) -> str:
    """
    Generate the final structured markdown research report.
    """
    sections_text = "\n\n".join(
        f"### {r['sub_question']}\n\n{r['synthesis']}" for r in synthesized_results
    )

    if llm_client and synthesized_results:
        try:
            prompt = (
                f"You are a research report writer. Write a polished academic-style research report "
                f"for the following query.\n\n"
                f"Query: {query}\n\n"
                f"Research sections:\n{sections_text}\n\n"
                f"Write a complete research report with:\n"
                f"1. Executive Summary (2-3 sentences)\n"
                f"2. One section per sub-question (use the provided synthesis)\n"
                f"3. Conclusion with key takeaways and open questions\n\n"
                f"Use markdown formatting. Keep citations like [1], [2]."
            )
            resp = llm_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
                temperature=0.6,
            )
            report = resp.choices[0].message.content.strip()
        except Exception as exc:
            logger.warning("Report generation LLM failed: %s", exc)
            report = _fallback_report(query, synthesized_results, all_sources)
    else:
        report = _fallback_report(query, synthesized_results, all_sources)

    # Append numbered references
    report += "\n\n---\n\n## References\n\n"
    seen = set()
    idx = 1
    for src in all_sources:
        url = src.get("url", "")
        if url and url not in seen:
            seen.add(url)
            report += f"[{idx}] [{src['title']}]({url})\n"
            idx += 1

    return report


def _fallback_report(query: str, synthesized: list[dict], sources: list[dict]) -> str:
    date_str = datetime.now().strftime("%B %d, %Y")
    report = f"# Research Report: {query}\n\n*Generated by Synapse AI · {date_str}*\n\n"
    report += "## Executive Summary\n\n"
    report += f"This report synthesises research on *{query}* across {len(sources)} sources.\n\n"
    for r in synthesized:
        report += f"## {r['sub_question']}\n\n{r['synthesis']}\n\n"
    report += "## Conclusion\n\n"
    report += (
        f"The research on *{query}* reveals multiple dimensions worth further exploration. "
        f"Key sources include {', '.join(s['title'][:50] for s in sources[:3])}."
    )
    return report


# ── Main orchestrator ─────────────────────────────────────────────────────────


def run_research_pipeline(session_id: str) -> None:
    """
    Full Plan-and-Execute research pipeline.
    Updates ResearchSession status at each step.
    Called by the Celery task apps.core.tasks.run_research_session.
    """
    import django  # noqa
    from django.utils import timezone as dj_tz  # noqa

    # Lazy import to avoid circular imports when used as Celery task
    try:
        from apps.agents.models import ResearchSession  # noqa
    except ImportError:
        logger.error("Cannot import ResearchSession — are Django settings configured?")
        return

    try:
        session = ResearchSession.objects.get(pk=session_id)
    except ResearchSession.DoesNotExist:
        logger.error("ResearchSession %s not found", session_id)
        return

    # Initialize LLM client
    llm_client = None
    try:
        import openai  # noqa

        from django.conf import settings as dj_settings  # noqa

        api_key = getattr(
            dj_settings, "OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", "")
        )
        if api_key:
            llm_client = openai.OpenAI(api_key=api_key)
    except Exception:
        pass

    try:
        # ── Step 1: Plan ─────────────────────────────────────────────────────
        session.status = ResearchSession.Status.RUNNING
        session.save(update_fields=["status"])

        sub_questions = plan_sub_questions(session.query, llm_client)
        session.sub_questions = sub_questions
        session.save(update_fields=["sub_questions"])
        logger.info(
            "Research plan: %d sub-questions for session %s",
            len(sub_questions),
            session_id,
        )

        # ── Step 2: Research ──────────────────────────────────────────────────
        research_results = []
        for sub_q in sub_questions:
            result = research_sub_question(sub_q)
            research_results.append(result)
            logger.debug("Researched: '%s' → %d sources", sub_q, len(result["sources"]))

        # ── Step 3: Synthesize ────────────────────────────────────────────────
        synthesized = synthesize_findings(research_results, llm_client)

        # ── Step 4: Report ────────────────────────────────────────────────────
        all_sources = []
        seen_urls = set()
        for r in research_results:
            for src in r["sources"]:
                url = src.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_sources.append(src)
                elif not url:
                    all_sources.append(src)

        report = generate_report(session.query, synthesized, all_sources, llm_client)

        # ── Save results ──────────────────────────────────────────────────────
        session.report = report
        session.sources = all_sources[:30]
        session.status = ResearchSession.Status.COMPLETE
        session.completed_at = dj_tz.now()
        session.save(update_fields=["report", "sources", "status", "completed_at"])
        logger.info(
            "Research session %s completed: %d chars, %d sources",
            session_id,
            len(report),
            len(all_sources),
        )

    except Exception as exc:
        logger.error(
            "Research pipeline failed for session %s: %s",
            session_id,
            exc,
            exc_info=True,
        )
        session.status = ResearchSession.Status.FAILED
        session.save(update_fields=["status"])
