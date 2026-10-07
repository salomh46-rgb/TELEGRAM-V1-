"""
Upstash Redis-backed Rate Limiter & Anti-Spam Guard for Telegram v1/v2.
Provides sliding-window rate limiting to defend against brute-force attacks,
message flooding, and DDoS. Gracefully falls back to in-memory tracking if Redis is unreachable.
"""

import os
import time
import logging
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
import httpx

logger = logging.getLogger("telegram_v1.guard")


class AntiSpamRateLimiter:
    """
    Hybrid Rate Limiter: Upstash Serverless Redis REST API with In-Memory Fallback.
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        redis_token: Optional[str] = None,
        default_limit: int = 60,
        window_seconds: int = 60,
    ):
        self.redis_url = (redis_url or os.getenv("UPSTASH_REDIS_REST_URL", "")).rstrip("/")
        self.redis_token = redis_token or os.getenv("UPSTASH_REDIS_REST_TOKEN", "")
        self.default_limit = default_limit
        self.window_seconds = window_seconds

        # In-memory fallback: key -> list of timestamps
        self._memory_windows: Dict[str, List[float]] = defaultdict(list)
        # Banned keys: key -> ban_expiry_timestamp
        self._banned_keys: Dict[str, float] = {}

    @property
    def is_redis_configured(self) -> bool:
        return bool(self.redis_url and self.redis_token)

    async def check(
        self,
        identifier: str,
        limit: Optional[int] = None,
        window_seconds: Optional[int] = None,
    ) -> Tuple[bool, int]:
        """
        Checks if an identifier (IP address or @username) is permitted to perform an action.
        Returns:
            Tuple[bool, int]: (is_allowed, remaining_quota)
        """
        limit = limit or self.default_limit
        window = window_seconds or self.window_seconds
        now = time.time()

        # Check temporary ban
        if identifier in self._banned_keys:
            if now < self._banned_keys[identifier]:
                return False, 0
            del self._banned_keys[identifier]

        # 1. Try Upstash Redis if configured
        if self.is_redis_configured:
            try:
                allowed, remaining = await self._check_upstash(identifier, limit, window)
                return allowed, remaining
            except Exception as e:
                logger.warning(f"[RateLimiter] Upstash error, falling back to in-memory: {e}")

        # 2. In-memory sliding window fallback
        return self._check_memory(identifier, limit, window, now)

    async def _check_upstash(self, identifier: str, limit: int, window: int) -> Tuple[bool, int]:
        """
        Executes atomic sliding-window counter in Upstash Redis via REST API.
        """
        bucket_key = f"tg_rate:{identifier}:{int(time.time() // window)}"
        url = f"{self.redis_url}/pipeline"
        headers = {"Authorization": f"Bearer {self.redis_token}"}
        
        # Pipeline: INCR + EXPIRE
        commands = [
            ["INCR", bucket_key],
            ["EXPIRE", bucket_key, window * 2],
        ]

        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.post(url, headers=headers, json=commands)
            if resp.status_code == 200:
                results = resp.json()
                count = int(results[0].get("result", 1))
                remaining = max(0, limit - count)
                is_allowed = count <= limit
                if not is_allowed:
                    self._banned_keys[identifier] = time.time() + 30  # 30-sec cooldown
                return is_allowed, remaining
            raise RuntimeError(f"Upstash returned status {resp.status_code}")

    def _check_memory(self, identifier: str, limit: int, window: int, now: float) -> Tuple[bool, int]:
        """
        Local sliding window implementation in memory.
        """
        timestamps = self._memory_windows[identifier]
        threshold = now - window

        # Prune expired timestamps
        valid_ts = [t for t in timestamps if t > threshold]
        self._memory_windows[identifier] = valid_ts

        if len(valid_ts) >= limit:
            self._banned_keys[identifier] = now + 30
            return False, 0

        valid_ts.append(now)
        remaining = max(0, limit - len(valid_ts))
        return True, remaining

    def ban(self, identifier: str, duration_seconds: int = 300) -> None:
        """Manually ban an identifier (IP or username)."""
        self._banned_keys[identifier] = time.time() + duration_seconds
        logger.warning(f"🚫 [BAN] Identifier {identifier} temporarily banned for {duration_seconds}s.")
