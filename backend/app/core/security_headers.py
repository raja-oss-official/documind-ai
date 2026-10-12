# ============================================================
# IMPORTS
# ============================================================

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


# ============================================================
# SECURITY HEADERS MIDDLEWARE
# ============================================================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):

    async def dispatch(
        self,
        request: Request,
        call_next,
    ):
        response = await call_next(request)

        # -------------------------------------------------
        # Basic Security Headers
        # -------------------------------------------------

        # Prevent MIME-type sniffing.
        response.headers[
            "X-Content-Type-Options"
        ] = "nosniff"

        # Prevent the application from being
        # embedded inside an iframe.
        response.headers[
            "X-Frame-Options"
        ] = "DENY"

        # Control referrer information.
        response.headers[
            "Referrer-Policy"
        ] = "strict-origin-when-cross-origin"

        # Disable browser features that the API
        # does not need.
        response.headers[
            "Permissions-Policy"
        ] = (
            "camera=(), "
            "microphone=(), "
            "geolocation=(), "
            "payment=()"
        )

        # -------------------------------------------------
        # Content Security Policy
        # -------------------------------------------------
        #
        # Swagger UI (/docs) and ReDoc (/redoc) need
        # JavaScript and CSS to render their interface.
        #
        # Therefore, we don't apply the strict API CSP
        # to the documentation pages.
        #

        documentation_paths = (
            "/docs",
            "/redoc",
            "/openapi.json",
        )

        if request.url.path not in documentation_paths:

            response.headers[
                "Content-Security-Policy"
            ] = (
                "default-src 'none'; "
                "frame-ancestors 'none'; "
                "base-uri 'none'"
            )

        return response