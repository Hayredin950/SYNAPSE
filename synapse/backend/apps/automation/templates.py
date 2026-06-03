"""
Pre-built workflow templates that users can clone.
"""

from typing import Any, Dict, List

WORKFLOW_TEMPLATES: List[Dict[str, Any]] = [
    {
        "id": "daily-digest",
        "name": "Daily Tech Digest",
        "description": "Every morning: collect news from all sources, summarize with AI, generate a PDF report, and email it to you.",
        "icon": "📰",
        "category": "digest",
        "trigger_type": "schedule",
        "cron_expression": "0 8 * * *",
        "event_config": {},
        "actions": [
            {
                "type": "collect_news",
                "params": {"sources": ["hackernews", "github", "arxiv"], "limit": 50},
            },
            {"type": "summarize_content", "params": {"batch_size": 30}},
            {
                "type": "generate_pdf",
                "params": {
                    "title": "Daily Tech Digest",
                    "subtitle": "Your morning briefing",
                    "article_limit": 10,
                },
            },
            {
                "type": "send_email",
                "params": {"subject": "Your Daily Tech Digest is ready"},
            },
        ],
    },
    {
        "id": "ai-research-brief",
        "name": "AI Research Brief",
        "description": "Every week: fetch the latest AI/ML papers from arXiv, run an AI digest on recent trends, and upload to Google Drive.",
        "icon": "🔬",
        "category": "research",
        "trigger_type": "schedule",
        "cron_expression": "0 9 * * 1",
        "event_config": {},
        "actions": [
            {
                "type": "collect_news",
                "params": {"sources": ["arxiv"], "days_back": 7, "max_papers": 50},
            },
            {
                "type": "ai_digest",
                "params": {"topic": "latest AI and machine learning research"},
            },
            {
                "type": "generate_pdf",
                "params": {
                    "title": "Weekly AI Research Brief",
                    "topic": "AI",
                    "article_limit": 8,
                },
            },
            {"type": "upload_to_drive", "params": {"folder_name": "SYNAPSE/Research"}},
        ],
    },
    {
        "id": "trending-alert",
        "name": "Trending Topic Alert",
        "description": "Fires automatically when a topic spikes in trending. Collects news and sends you an instant notification.",
        "icon": "📈",
        "category": "alerts",
        "trigger_type": "event",
        "cron_expression": "",
        "event_config": {
            "event_type": "trending_spike",
            "filter": {"topic": ""},
            "cooldown_minutes": 120,
        },
        "actions": [
            {
                "type": "collect_news",
                "params": {"sources": ["hackernews", "github"], "limit": 20},
            },
            {
                "type": "send_email",
                "params": {"subject": "🔥 Trending Topic Spike Detected"},
            },
        ],
    },
    {
        "id": "new-article-workflow",
        "name": "New Article Auto-Summarize",
        "description": "Fires every time a new article is published. Automatically summarizes it and creates a notification.",
        "icon": "⚡",
        "category": "alerts",
        "trigger_type": "event",
        "cron_expression": "",
        "event_config": {
            "event_type": "new_article",
            "filter": {"topic": ""},
            "cooldown_minutes": 30,
        },
        "actions": [
            {"type": "summarize_content", "params": {"batch_size": 5}},
            {
                "type": "send_email",
                "params": {"subject": "New article published and summarized"},
            },
        ],
    },
    {
        "id": "weekly-report",
        "name": "Weekly Intelligence Report",
        "description": "Every Friday: run a full collection, AI digest on all topics, generate a comprehensive PDF, and upload to Drive.",
        "icon": "📊",
        "category": "digest",
        "trigger_type": "schedule",
        "cron_expression": "0 17 * * 5",
        "event_config": {},
        "actions": [
            {
                "type": "collect_news",
                "params": {
                    "sources": ["hackernews", "github", "arxiv", "youtube"],
                    "limit": 100,
                },
            },
            {"type": "summarize_content", "params": {"batch_size": 50}},
            {
                "type": "ai_digest",
                "params": {"topic": "weekly technology trends and highlights"},
            },
            {
                "type": "generate_pdf",
                "params": {
                    "title": "Weekly Intelligence Report",
                    "subtitle": "Powered by SYNAPSE AI",
                    "article_limit": 15,
                },
            },
            {
                "type": "upload_to_drive",
                "params": {"folder_name": "SYNAPSE/Weekly Reports"},
            },
            {
                "type": "send_email",
                "params": {"subject": "📊 Your Weekly Intelligence Report is ready"},
            },
        ],
    },
    {
        "id": "github-radar",
        "name": "GitHub Trending Radar",
        "description": "Every 6 hours: scrape GitHub trending repos, run AI analysis, notify you of standout projects.",
        "icon": "💻",
        "category": "research",
        "trigger_type": "schedule",
        "cron_expression": "0 */6 * * *",
        "event_config": {},
        "actions": [
            {
                "type": "collect_news",
                "params": {"sources": ["github"], "days_back": 1, "limit": 30},
            },
            {
                "type": "ai_digest",
                "params": {
                    "topic": "trending GitHub repositories and open source projects"
                },
            },
            {
                "type": "send_email",
                "params": {"subject": "💻 GitHub Trending Radar Update"},
            },
        ],
    },
    {
        "id": "twitter-ai-pulse",
        "name": "X/Twitter AI Pulse",
        "description": "Every 2 hours: scrape the latest AI and tech tweets, run an AI digest on trends, and send you a curated summary.",
        "icon": "🐦",
        "category": "social",
        "trigger_type": "schedule",
        "cron_expression": "0 */2 * * *",
        "event_config": {},
        "actions": [
            {
                "type": "scrape_tweets",
                "params": {
                    "queries": "AI machine learning\nLLM GPT Claude\nPython programming\nWeb development",
                    "max_results": 100,
                },
            },
            {
                "type": "ai_digest",
                "params": {"topic": "AI and tech trends from X/Twitter"},
            },
            {
                "type": "send_email",
                "params": {"subject": "🐦 Your X/Twitter AI Pulse Report"},
            },
        ],
    },
    {
        "id": "twitter-trending-alert",
        "name": "X/Twitter Trending Alert",
        "description": "Fires when a trending spike is detected. Immediately scrapes relevant tweets and notifies you.",
        "icon": "📣",
        "category": "alerts",
        "trigger_type": "event",
        "cron_expression": "",
        "event_config": {
            "event_type": "trending_spike",
            "filter": {"topic": ""},
            "cooldown_minutes": 60,
        },
        "actions": [
            {
                "type": "scrape_tweets",
                "params": {"queries": "trending tech AI", "max_results": 50},
            },
            {
                "type": "send_email",
                "params": {"subject": "📣 Trending Spike — X/Twitter Alert"},
            },
        ],
    },
    {
        "id": "twitter-weekly-digest",
        "name": "X/Twitter Weekly Tech Digest",
        "description": "Every Sunday: scrape the week's best tech tweets, generate a PDF digest, and upload to Google Drive.",
        "icon": "📋",
        "category": "digest",
        "trigger_type": "schedule",
        "cron_expression": "0 10 * * 0",
        "event_config": {},
        "actions": [
            {
                "type": "scrape_tweets",
                "params": {
                    "queries": "AI machine learning\nPython Rust TypeScript\nopen source software\nCybersecurity DevOps",
                    "max_results": 200,
                },
            },
            {
                "type": "ai_digest",
                "params": {"topic": "weekly technology highlights from X/Twitter"},
            },
            {
                "type": "generate_pdf",
                "params": {
                    "title": "Weekly X/Twitter Tech Digest",
                    "subtitle": "Curated by SYNAPSE AI",
                    "article_limit": 15,
                },
            },
            {
                "type": "upload_to_drive",
                "params": {"folder_name": "SYNAPSE/Twitter Digests"},
            },
        ],
    },
    {
        "id": "full-social-intel",
        "name": "Full Social Intelligence",
        "description": "Daily: scrape tweets + GitHub + news, run AI analysis across all sources, generate a comprehensive PDF and email it.",
        "icon": "🌐",
        "category": "digest",
        "trigger_type": "schedule",
        "cron_expression": "0 7 * * *",
        "event_config": {},
        "actions": [
            {
                "type": "scrape_tweets",
                "params": {
                    "queries": "AI machine learning\ntechnology trends\nopen source",
                    "max_results": 150,
                },
            },
            {
                "type": "collect_news",
                "params": {"sources": ["hackernews", "github", "arxiv"], "limit": 50},
            },
            {"type": "summarize_content", "params": {"batch_size": 30}},
            {
                "type": "ai_digest",
                "params": {
                    "topic": "daily technology intelligence from social and technical sources"
                },
            },
            {
                "type": "generate_pdf",
                "params": {
                    "title": "Daily Social Intelligence Report",
                    "subtitle": "Powered by SYNAPSE AI",
                    "article_limit": 15,
                },
            },
            {
                "type": "send_email",
                "params": {"subject": "🌐 Your Daily Social Intelligence Report"},
            },
        ],
    },
]

TEMPLATE_MAP = {t["id"]: t for t in WORKFLOW_TEMPLATES}


def get_all_templates() -> List[Dict[str, Any]]:
    return WORKFLOW_TEMPLATES


def get_template(template_id: str) -> Dict[str, Any] | None:
    return TEMPLATE_MAP.get(template_id)
