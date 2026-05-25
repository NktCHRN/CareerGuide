"""ApiGateway FastAPI application — the single entry point (C4, table 4.2).

All client traffic enters here. The gateway validates the JWT (HS256, shared
`JWT_SECRET`), authorises the route (public allow-list + admin-only rules),
rewrites `/api/<service-key>/...` to the downstream service's own `/api/...`
path and reverse-proxies the request, forwarding the validated principal as
`X-User-Id` / `X-User-Role`. Downstream services therefore run in
`AUTH_MODE=gateway` and trust those headers.

Lifespan: open the shared httpx client; close it on shutdown.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response

from app.auth import parse_principal, verify_with_user_service
from app.config import settings
from app.proxy import proxy
from app.routers import health
from app.routing import is_public, requires_admin, resolve_target

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("api-gateway")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "ApiGateway starting (APP_ENV=%s, verify_via_user_service=%s)",
        settings.APP_ENV,
        settings.GATEWAY_VERIFY_VIA_USER_SERVICE,
    )
    proxy.start()
    try:
        yield
    finally:
        await proxy.close()
        logger.info("ApiGateway stopped")


app = FastAPI(
    title="CareerGuide — ApiGateway",
    description="Single entry point: JWT validation, authorisation and reverse-proxy routing.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# The gateway's own endpoints are registered FIRST, so `/api/health` and
# `/api/health/all` match before the catch-all proxy route below.
app.include_router(health.router)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)
_PROXY_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]


@app.api_route("/api/{full_path:path}", methods=_PROXY_METHODS)
async def gateway(
    full_path: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> Response:
    target = resolve_target(full_path)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    base_url, downstream_path = target

    method = request.method.upper()
    principal = parse_principal(authorization)

    if not is_public(method, full_path):
        if principal is None:
            raise _UNAUTHORIZED
        if requires_admin(method, full_path) and principal.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrator privileges required",
            )
        if settings.GATEWAY_VERIFY_VIA_USER_SERVICE:
            await verify_with_user_service(proxy.client, authorization, principal)

    return await proxy.forward(request, base_url, downstream_path, principal)
