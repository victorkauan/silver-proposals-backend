import uuid
from collections.abc import Callable

from fastapi import Request, status
from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

from app.shared.errors import AppError, ErrorCode

# In-memory counters are per process: with several API tasks each one limits on its own.
storage = MemoryStorage()
limiter = MovingWindowRateLimiter(storage)


def rate_limit(limit: str, *, scope: str | None = None) -> Callable[[Request], None]:
    item = parse(limit)

    def dependency(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        if not limiter.hit(item, scope or request.url.path, client):
            raise AppError(ErrorCode.RATE_LIMITED, status.HTTP_429_TOO_MANY_REQUESTS)

    return dependency


USER_LIMIT = parse("10/15 minutes")


def hit_user_limit(scope: str, user_id: uuid.UUID) -> bool:
    return limiter.hit(USER_LIMIT, scope, str(user_id))
