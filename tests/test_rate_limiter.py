import pytest
from telegram_v1.guard.rate_limiter import AntiSpamRateLimiter


@pytest.mark.asyncio
async def test_in_memory_rate_limiter_allow_and_block():
    limiter = AntiSpamRateLimiter(default_limit=3, window_seconds=10)

    # 3 allowed requests
    for i in range(3):
        allowed, remaining = await limiter.check("test_user")
        assert allowed is True
        assert remaining == (2 - i)

    # 4th request must be blocked
    allowed, remaining = await limiter.check("test_user")
    assert allowed is False
    assert remaining == 0


@pytest.mark.asyncio
async def test_rate_limiter_manual_ban():
    limiter = AntiSpamRateLimiter(default_limit=10, window_seconds=10)
    limiter.ban("spammer", duration_seconds=60)

    allowed, remaining = await limiter.check("spammer")
    assert allowed is False
    assert remaining == 0
