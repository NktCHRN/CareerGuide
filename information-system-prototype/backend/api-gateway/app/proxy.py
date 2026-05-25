"""Transparent async reverse-proxy built on httpx.

Streams the request body upstream and the response body back to the client,
forwards the method / path / query / headers (minus hop-by-hop ones), injects the
validated `X-User-Id` / `X-User-Role`, and maps transport failures to 502/504.
"""
from __future__ import annotations

import logging

import httpx
from fastapi import Request
from starlette.background import BackgroundTask
from starlette.responses import JSONResponse, Response, StreamingResponse

from app.auth import Principal
from app.config import settings

logger = logging.getLogger("api-gateway.proxy")

# Connection-level headers must not be forwarded (RFC 7230 §6.1).
_HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}

# Dropped from the OUTGOING request:
#  • hop-by-hop;
#  • host / content-length — httpx recomputes them for the streamed request;
#  • x-user-* — never trust client-supplied identity; the gateway sets these itself.
_DROP_REQUEST_HEADERS = _HOP_BY_HOP | {"host", "content-length", "x-user-id", "x-user-role"}

# Dropped from the upstream response:
#  • hop-by-hop;
#  • CORS headers — the gateway's own CORSMiddleware is the single CORS authority,
#    forwarding the downstream ones too would duplicate them and break the browser.
_DROP_RESPONSE_HEADERS = _HOP_BY_HOP | {
    "access-control-allow-origin",
    "access-control-allow-credentials",
    "access-control-allow-methods",
    "access-control-allow-headers",
    "access-control-expose-headers",
    "access-control-max-age",
}

_IDEMPOTENT_METHODS = {"GET", "HEAD"}


def _error(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail})


class Proxy:
    """Holds a shared `httpx.AsyncClient` for the app's lifetime."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def start(self) -> None:
        timeout = httpx.Timeout(
            settings.PROXY_TIMEOUT_SECONDS,
            connect=settings.PROXY_CONNECT_TIMEOUT_SECONDS,
        )
        limits = httpx.Limits(max_connections=100, max_keepalive_connections=20)
        # Redirects are forwarded to the client verbatim, not followed by the gateway.
        self._client = httpx.AsyncClient(timeout=timeout, limits=limits, follow_redirects=False)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:  # pragma: no cover - guarded by the lifespan
            raise RuntimeError("Proxy client is not started")
        return self._client

    def _build_request_headers(self, request: Request, principal: Principal | None) -> dict[str, str]:
        headers = {k: v for k, v in request.headers.items() if k.lower() not in _DROP_REQUEST_HEADERS}
        if principal is not None:
            headers["X-User-Id"] = str(principal.user_id)
            headers["X-User-Role"] = principal.role
        client_host = request.client.host if request.client else None
        if client_host:
            prior = request.headers.get("x-forwarded-for")
            headers["X-Forwarded-For"] = f"{prior}, {client_host}" if prior else client_host
        headers.setdefault("X-Forwarded-Proto", request.url.scheme)
        return headers

    async def forward(
        self,
        request: Request,
        base_url: str,
        downstream_path: str,
        principal: Principal | None,
    ) -> Response:
        url = base_url + downstream_path
        if request.url.query:
            url = f"{url}?{request.url.query}"

        method = request.method.upper()
        headers = self._build_request_headers(request, principal)
        idempotent = method in _IDEMPOTENT_METHODS
        attempts = 1 + (settings.PROXY_RETRIES if idempotent else 0)

        for attempt in range(attempts):
            # Idempotent requests carry no body, so retrying is safe; for the rest
            # we stream the body and never retry (it can only be consumed once).
            content = None if idempotent else request.stream()
            upstream_request = self.client.build_request(method, url, headers=headers, content=content)
            try:
                upstream = await self.client.send(upstream_request, stream=True)
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                logger.warning("upstream connect failed [%s %s] attempt %d/%d: %s",
                               method, url, attempt + 1, attempts, exc)
                continue  # retry (idempotent) or fall through to 502
            except httpx.TimeoutException as exc:
                logger.warning("upstream timeout [%s %s]: %s", method, url, exc)
                return _error(504, "Upstream service timed out")
            except httpx.RequestError as exc:
                logger.warning("upstream request error [%s %s]: %s", method, url, exc)
                return _error(502, "Upstream service error")

            response_headers = {
                k: v for k, v in upstream.headers.items() if k.lower() not in _DROP_RESPONSE_HEADERS
            }
            return StreamingResponse(
                upstream.aiter_raw(),
                status_code=upstream.status_code,
                headers=response_headers,
                background=BackgroundTask(upstream.aclose),
            )

        return _error(502, "Upstream service unavailable")


proxy = Proxy()
