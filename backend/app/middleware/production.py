from __future__ import annotations

import threading
import time
import uuid
from collections import defaultdict, deque
from typing import Deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RequestIdMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if not self.enabled:
            return response

        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "media-src 'self' blob:; "
            "connect-src 'self' ws: wss:; "
            "frame-ancestors 'none';",
        )
        return response


class FrontendNoCacheMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if not self.enabled:
            return response

        if request.method.upper() != "GET":
            return response

        path = request.url.path or "/"
        if path == "/" or path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        return response


class HttpsEnforcerMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, enforce_https: bool = False):
        super().__init__(app)
        self.enforce_https = enforce_https

    async def dispatch(self, request: Request, call_next):
        if not self.enforce_https:
            return await call_next(request)

        proto = request.headers.get("x-forwarded-proto", request.url.scheme).lower()
        if proto != "https":
            return JSONResponse(
                status_code=403,
                content={"detail": "HTTPS is required for this deployment."},
            )
        return await call_next(request)


class SlidingWindowRateLimiter:
    def __init__(self, window_seconds: int, max_requests: int):
        self.window_seconds = max(1, int(window_seconds))
        self.max_requests = max(1, int(max_requests))
        self._events: dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> tuple[bool, int]:
        now = time.time()
        threshold = now - self.window_seconds

        with self._lock:
            q = self._events[key]
            while q and q[0] < threshold:
                q.popleft()

            if len(q) >= self.max_requests:
                retry_after = max(1, int(q[0] + self.window_seconds - now))
                return False, retry_after

            q.append(now)
            return True, 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        enabled: bool,
        window_seconds: int,
        max_requests: int,
        auth_max_requests: int,
    ):
        super().__init__(app)
        self.enabled = enabled
        self.default_limiter = SlidingWindowRateLimiter(window_seconds, max_requests)
        self.auth_limiter = SlidingWindowRateLimiter(window_seconds, auth_max_requests)

    @staticmethod
    def _client_ip(request: Request) -> str:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",", 1)[0].strip() or "unknown"
        if request.client and request.client.host:
            return request.client.host
        return "unknown"

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self.enabled:
            return await call_next(request)

        path = request.url.path or "/"
        # Keep health/metrics unrestricted for observability tools.
        if path.startswith("/health") or path.startswith("/metrics") or path.startswith("/static"):
            return await call_next(request)

        ip = self._client_ip(request)
        is_auth = path.startswith("/auth/login")
        limiter = self.auth_limiter if is_auth else self.default_limiter
        key = f"{ip}:{'auth' if is_auth else 'default'}"

        allowed, retry_after = limiter.allow(key)
        if not allowed:
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(retry_after)},
                content={"detail": "Rate limit exceeded"},
            )

        return await call_next(request)
