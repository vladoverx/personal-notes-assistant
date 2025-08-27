from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from .api.middleware.security import SecurityMiddleware
from .api.v1.router import api_router
from .config import settings
from .utils.logging import setup_logging


def create_app() -> FastAPI:
    setup_logging()

    app = FastAPI(
        title="Notes Assistant API",
        debug=settings.debug,
        version="0.1.0",
        root_path=settings.root_path or "",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=[
            "Accept",
            "Accept-Language",
            "Content-Language",
            "Content-Type",
            "Authorization",
            "X-Requested-With",
            "X-CSRF-Token"
        ],
        max_age=600,  # Cache preflight requests for 10 minutes
    )

    # Proxy headers (X-Forwarded-*) when behind ALB/ingress
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])

    # Trusted hosts (configure in env for production)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)

    # GZip compression
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    app.add_middleware(SecurityMiddleware)

    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()


