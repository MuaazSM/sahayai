import logging
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("sahayai.errors")


async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch-all for any unhandled exception. Returns a clean JSON error
    instead of a stack trace so the Flutter app can show something
    useful and the user isn't staring at a blank screen.
    """
    logger.error(f"Unhandled error on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Something went wrong on our end.",
            "detail": str(exc)[:200],  # truncate so we don't leak internals
            "path": str(request.url.path),
        },
    )