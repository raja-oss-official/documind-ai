import logging

from fastapi import Request
from fastapi.responses import JSONResponse


logger = logging.getLogger(
    "documind_ai"
)


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
):
    """
    Handle unexpected application errors safely.

    The actual exception is logged internally,
    but sensitive implementation details are
    never returned to the client.
    """

    logger.exception(
        "Unhandled exception while processing %s %s",
        request.method,
        request.url.path,
        exc_info=exc,
    )

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error"
        },
    )