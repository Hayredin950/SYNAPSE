"""
TASK-607-2: Slack Integration

Slash command handler (/synapse {question}) and weekly digest delivery.

Required env vars:
    SLACK_CLIENT_ID          — from Slack App settings
    SLACK_CLIENT_SECRET      — from Slack App settings
    SLACK_SIGNING_SECRET     — for request verification
    SLACK_BOT_TOKEN          — Bot OAuth token (xoxb-...)
    SLACK_REDIRECT_URI       — OAuth redirect URI
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time

import requests

from django.conf import settings

logger = logging.getLogger(__name__)

SLACK_AUTH_URL = "https://slack.com/oauth/v2/authorize"
SLACK_TOKEN_URL = "https://slack.com/api/oauth.v2.access"
SLACK_API_BASE = "https://slack.com/api"


# ── OAuth ─────────────────────────────────────────────────────────────────────


def get_authorization_url(state: str = "") -> str:
    client_id = getattr(
        settings, "SLACK_CLIENT_ID", os.environ.get("SLACK_CLIENT_ID", "")
    )
    redirect_uri = getattr(
        settings, "SLACK_REDIRECT_URI", os.environ.get("SLACK_REDIRECT_URI", "")
    )
    scopes = "commands,chat:write,channels:read,users:read"
    return (
        f"{SLACK_AUTH_URL}?client_id={client_id}"
        f"&scope={scopes}"
        f"&redirect_uri={redirect_uri}" + (f"&state={state}" if state else "")
    )


def exchange_code_for_token(code: str) -> dict:
    client_id = getattr(
        settings, "SLACK_CLIENT_ID", os.environ.get("SLACK_CLIENT_ID", "")
    )
    client_secret = getattr(
        settings, "SLACK_CLIENT_SECRET", os.environ.get("SLACK_CLIENT_SECRET", "")
    )
    redirect_uri = getattr(
        settings, "SLACK_REDIRECT_URI", os.environ.get("SLACK_REDIRECT_URI", "")
    )

    resp = requests.post(
        SLACK_TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise ValueError(f"Slack token error: {data.get('error', 'unknown')}")
    return data


# ── Request verification ──────────────────────────────────────────────────────


def verify_slack_signature(request_body: bytes, timestamp: str, signature: str) -> bool:
    """Verify Slack webhook request signature (HMAC-SHA256)."""
    signing_secret = getattr(
        settings, "SLACK_SIGNING_SECRET", os.environ.get("SLACK_SIGNING_SECRET", "")
    )
    if not signing_secret:
        logger.warning("SLACK_SIGNING_SECRET not configured")
        return False

    # Reject requests older than 5 minutes
    if abs(time.time() - int(timestamp)) > 300:
        return False

    sig_base = f"v0:{timestamp}:{request_body.decode()}"
    expected = (
        "v0="
        + hmac.new(
            signing_secret.encode(), sig_base.encode(), hashlib.sha256
        ).hexdigest()
    )
    return hmac.compare_digest(expected, signature)


# ── Slash command handler ─────────────────────────────────────────────────────


def handle_slash_command(payload: dict) -> dict:
    """
    Handle /synapse {question} slash command.
    Returns Slack response payload (immediate acknowledgement).
    """
    text = payload.get("text", "").strip()
    channel_id = payload.get("channel_id", "")
    response_url = payload.get("response_url", "")

    if not text:
        return {
            "response_type": "ephemeral",
            "text": "❓ Usage: `/synapse <your question>` — Ask Synapse AI anything!",
        }

    # Acknowledge immediately (Slack requires < 3s response)
    # Fire background task to actually query AI and send delayed response
    try:
        from apps.core.tasks import slack_ai_query  # noqa: PLC0415

        slack_ai_query.delay(
            question=text, channel_id=channel_id, response_url=response_url
        )
    except Exception as exc:
        logger.warning("Could not enqueue Slack AI query: %s", exc)

    return {
        "response_type": "ephemeral",
        "text": f"🧠 *Synapse AI is thinking...* I'll reply in this channel shortly.\n> {text}",
    }


# ── Message sending ───────────────────────────────────────────────────────────


def send_message(
    bot_token: str, channel: str, text: str, blocks: list | None = None
) -> bool:
    """Send a message to a Slack channel."""
    payload: dict = {"channel": channel, "text": text}
    if blocks:
        payload["blocks"] = blocks
    try:
        resp = requests.post(
            f"{SLACK_API_BASE}/chat.postMessage",
            headers={
                "Authorization": f"Bearer {bot_token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )
        data = resp.json()
        if not data.get("ok"):
            logger.error("Slack message failed: %s", data.get("error"))
            return False
        return True
    except Exception as exc:
        logger.error("Slack send_message error: %s", exc)
        return False


def send_digest_to_channel(
    bot_token: str, channel: str, briefing_content: str, date: str
) -> bool:
    """
    Deliver weekly AI digest to a Slack channel.
    Formats briefing as rich Slack blocks.
    """
    paragraphs = [p.strip() for p in briefing_content.split("\n\n") if p.strip()]
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🧠 Synapse Weekly Digest — {date}",
            },
        },
        {"type": "divider"},
    ]
    for para in paragraphs[:3]:
        blocks.append(
            {"type": "section", "text": {"type": "mrkdwn", "text": para[:3000]}}
        )
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "🔗 <https://app.synapse.app|Open Synapse App> for full briefing & search",
                }
            ],
        }
    )
    return send_message(bot_token, channel, f"Synapse Weekly Digest — {date}", blocks)
