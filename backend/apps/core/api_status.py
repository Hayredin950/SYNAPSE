"""API configuration status checker for user-facing warnings."""

import os
from typing import Dict, List, Optional

from django.conf import settings


class APIStatus:
    """Check which APIs are configured and which are missing."""

    API_CONFIGS = {
        "github": {
            "key": "GITHUB_TOKEN",
            "env": "GITHUB_TOKEN",
            "label": "GitHub",
            "description": "GitHub API access for repository scraping",
            "required_for": ["GitHub Radar"],
        },
        "twitter": {
            "key": "X_API_KEY",
            "env": "X_API_KEY",
            "fallback_env": "TWITTER_BEARER_TOKEN",
            "label": "X/Twitter",
            "description": "X API access for tweet scraping",
            "required_for": ["X Feed", "Tweet scraping"],
        },
        "gemini": {
            "key": "GEMINI_API_KEY",
            "env": "GEMINI_API_KEY",
            "label": "Gemini AI",
            "description": "Google Gemini for AI summarization",
            "required_for": ["AI Chat", "Article summaries", "Briefings"],
        },
        "openrouter": {
            "key": "OPENROUTER_API_KEY",
            "env": "OPENROUTER_API_KEY",
            "label": "OpenRouter",
            "description": "OpenRouter API for AI features (Gemini fallback)",
            "required_for": ["AI Chat", "Article summaries", "Briefings"],
            "is_fallback": True,
        },
        "youtube": {
            "key": "YOUTUBE_API_KEY",
            "env": "YOUTUBE_API_KEY",
            "label": "YouTube",
            "description": "YouTube API for video scraping",
            "required_for": ["Video feed"],
        },
    }

    @classmethod
    def get_missing_apis(cls) -> List[Dict]:
        """Return list of APIs that are not configured."""
        missing = []

        for api_id, config in cls.API_CONFIGS.items():
            # Check if API key is set
            key_value = getattr(settings, config["key"], None)
            if not key_value:
                key_value = os.environ.get(config["env"])

            # Check fallback env var if defined
            if not key_value and "fallback_env" in config:
                key_value = os.environ.get(config["fallback_env"])

            if not key_value:
                missing.append(
                    {
                        "id": api_id,
                        "label": config["label"],
                        "description": config["description"],
                        "required_for": config.get("required_for", []),
                        "is_fallback": config.get("is_fallback", False),
                    }
                )

        return missing

    @classmethod
    def get_api_status(cls) -> Dict:
        """Get full API configuration status."""
        all_apis = []
        missing = []

        for api_id, config in cls.API_CONFIGS.items():
            key_value = getattr(settings, config["key"], None)
            if not key_value:
                key_value = os.environ.get(config["env"])
            if not key_value and "fallback_env" in config:
                key_value = os.environ.get(config["fallback_env"])

            is_configured = bool(key_value)
            api_info = {
                "id": api_id,
                "label": config["label"],
                "description": config["description"],
                "configured": is_configured,
                "required_for": config.get("required_for", []),
                "is_fallback": config.get("is_fallback", False),
            }
            all_apis.append(api_info)

            if not is_configured and not config.get("is_fallback", False):
                missing.append(api_info)

        return {
            "apis": all_apis,
            "missing": missing,
            "has_missing": len(missing) > 0,
            "critical_missing": [m for m in missing if not m.get("is_fallback")],
        }

    @classmethod
    def check_api(cls, api_id: str) -> bool:
        """Check if a specific API is configured."""
        if api_id not in cls.API_CONFIGS:
            return False

        config = cls.API_CONFIGS[api_id]
        key_value = getattr(settings, config["key"], None)
        if not key_value:
            key_value = os.environ.get(config["env"])
        if not key_value and "fallback_env" in config:
            key_value = os.environ.get(config["fallback_env"])

        return bool(key_value)


# Convenience functions
def get_missing_apis() -> List[Dict]:
    """Get list of missing API configurations."""
    return APIStatus.get_missing_apis()


def get_api_status() -> Dict:
    """Get full API configuration status."""
    return APIStatus.get_api_status()


def is_api_configured(api_id: str) -> bool:
    """Check if a specific API is configured."""
    return APIStatus.check_api(api_id)
