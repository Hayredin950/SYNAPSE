"""
SYNAPSE AI Rate Limiter + Budget Enforcer
-----------------------------------------
Tracks per-user AI request counts and token spend in Redis.

Plan limits (configurable via env):
  Free : AI_RATE_LIMIT_FREE  req/min  | AI_BUDGET_FREE_CENTS  USD-cents/day
  Pro  : AI_RATE_LIMIT_PRO   req/min  | AI_BUDGET_PRO_CENTS   USD-cents/day
  Team : AI_RATE_LIMIT_TEAM  req/min  | AI_BUDGET_TEAM_CENTS  USD-cents/day
"""

import logging
import os
import time
from datetime import date
from typing import Optional

import redis

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
RATE_LIMIT_FREE = int(os.environ.get("AI_RATE_LIMIT_FREE", "2"))  # req/min
RATE_LIMIT_PRO = int(os.environ.get("AI_RATE_LIMIT_PRO", "20"))
RATE_LIMIT_TEAM = int(os.environ.get("AI_RATE_LIMIT_TEAM", "60"))

BUDGET_FREE_CENTS = int(os.environ.get("AI_BUDGET_FREE_CENTS", "50"))  # $0.50
BUDGET_PRO_CENTS = int(os.environ.get("AI_BUDGET_PRO_CENTS", "1000"))  # $10.00
BUDGET_TEAM_CENTS = int(os.environ.get("AI_BUDGET_TEAM_CENTS", "5000"))  # $50.00

# Cost per 1000 tokens in USD-cents (approximate blended cost)
COST_PER_1K_TOKENS_CENTS = float(os.environ.get("COST_PER_1K_TOKENS_CENTS", "0.3"))

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_RL_DB = int(os.environ.get("REDIS_RL_DB", "4"))


class BudgetExceededError(Exception):
    """Raised when a user exceeds their daily AI spend budget."""

    def __init__(self, used_cents: int, limit_cents: int, reset_at: str):
        self.used_cents = used_cents
        self.limit_cents = limit_cents
        self.reset_at = reset_at
        super().__init__(
            f"Daily AI budget exceeded: {used_cents}/{limit_cents} cents used. Resets at {reset_at}."
        )


class RateLimitExceededError(Exception):
    """Raised when a user exceeds their per-minute request rate."""

    def __init__(self, limit: int, retry_after: int):
        self.limit = limit
        self.retry_after = retry_after
        super().__init__(
            f"Rate limit exceeded: {limit} req/min. Retry after {retry_after}s."
        )


def _get_redis() -> Optional[redis.Redis]:
    try:
        client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_RL_DB,
            decode_responses=True,
            socket_connect_timeout=1,
        )
        client.ping()
        return client
    except Exception as exc:
        logger.warning("Rate-limit Redis unavailable: %s — skipping limits", exc)
        return None


def _plan_rate_limit(role: str) -> int:
    """Return req/min limit for the given user role."""
    if role == "admin":
        return 999
    if role == "premium":
        return RATE_LIMIT_PRO
    return RATE_LIMIT_FREE


def _plan_budget_cents(role: str) -> int:
    """Return daily budget in USD-cents for the given user role."""
    if role == "admin":
        return 999_999
    if role == "premium":
        return BUDGET_PRO_CENTS
    return BUDGET_FREE_CENTS


def check_rate_limit(user_id: str, role: str = "user") -> None:
    """
    Enforce sliding-window rate limit (per minute).
    Raises RateLimitExceededError if exceeded.
    No-op if Redis is unavailable.
    """
    r = _get_redis()
    if r is None:
        return

    limit = _plan_rate_limit(role)
    now = int(time.time())
    window = 60  # seconds
    key = f"rl:ai:{user_id}:{now // window}"

    try:
        pipe = r.pipeline()
        pipe.incr(key)
        pipe.expire(key, window * 2)
        count, _ = pipe.execute()

        if count > limit:
            retry_after = window - (now % window)
            raise RateLimitExceededError(limit=limit, retry_after=retry_after)
    except (RateLimitExceededError, BudgetExceededError):
        raise
    except Exception as exc:
        logger.warning("Rate limit check failed (skipping): %s", exc)


def check_budget(user_id: str, role: str = "user") -> None:
    """
    Enforce daily token spend budget.
    Raises BudgetExceededError if exceeded.
    No-op if Redis is unavailable.
    """
    r = _get_redis()
    if r is None:
        return

    budget_cents = _plan_budget_cents(role)
    today = date.today().isoformat()
    key = f"budget:{user_id}:{today}"

    try:
        used_str = r.get(key)
        used = int(used_str) if used_str else 0

        if used >= budget_cents:
            reset_at = f"{today}T23:59:59Z"
            raise BudgetExceededError(
                used_cents=used, limit_cents=budget_cents, reset_at=reset_at
            )
    except (BudgetExceededError,):
        raise
    except Exception as exc:
        logger.warning("Budget check failed (skipping): %s", exc)


def record_token_usage(user_id: str, tokens_used: int) -> None:
    """
    Record token usage for a user (updates daily budget counter).
    cost_cents = tokens_used / 1000 * COST_PER_1K_TOKENS_CENTS
    """
    r = _get_redis()
    if r is None:
        return

    cost_cents = int((tokens_used / 1000) * COST_PER_1K_TOKENS_CENTS)
    if cost_cents <= 0:
        return

    today = date.today().isoformat()
    key = f"budget:{user_id}:{today}"

    try:
        pipe = r.pipeline()
        pipe.incrby(key, cost_cents)
        pipe.expire(key, 86400 + 3600)  # 25 hours TTL
        pipe.execute()
        logger.debug(
            "Recorded %d cents for user %s (today total: +%d)",
            cost_cents,
            user_id,
            cost_cents,
        )
    except Exception as exc:
        logger.warning("Failed to record token usage: %s", exc)


def get_budget_status(user_id: str, role: str = "user") -> dict:
    """Return current budget usage for a user (for API responses)."""
    r = _get_redis()
    budget_cents = _plan_budget_cents(role)

    if r is None:
        return {
            "used_cents": 0,
            "limit_cents": budget_cents,
            "remaining_cents": budget_cents,
        }

    today = date.today().isoformat()
    key = f"budget:{user_id}:{today}"
    used_str = r.get(key)
    used = int(used_str) if used_str else 0

    return {
        "used_cents": used,
        "limit_cents": budget_cents,
        "remaining_cents": max(0, budget_cents - used),
        "reset_at": f"{today}T23:59:59Z",
    }
