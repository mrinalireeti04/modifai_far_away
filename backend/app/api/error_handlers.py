"""
Global exception handlers for the FastAPI application.
Catches all exceptions and returns user-friendly JSON error responses.
"""

import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from botocore.exceptions import ClientError
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI app."""

    @app.exception_handler(ClientError)
    async def boto3_error_handler(request: Request, exc: ClientError):
        """Handle AWS SDK (boto3) errors."""
        error_code = exc.response.get("Error", {}).get("Code", "Unknown")
        error_message = exc.response.get("Error", {}).get("Message", "An AWS service error occurred")
        logger.error(
            f"AWS ClientError [{error_code}]: {error_message}\n{traceback.format_exc()}"
        )
        return JSONResponse(
            status_code=502,
            content={
                "detail": f"AWS service error: {error_message}",
                "error_code": error_code,
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
        """Handle database errors."""
        logger.error(f"Database error: {exc}\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={"detail": "A database error occurred. Please try again later."},
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        """Handle validation errors that slip past Pydantic."""
        logger.warning(f"ValueError: {exc}")
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc)},
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        """Catch-all for any unhandled exceptions."""
        logger.error(f"Unhandled exception: {exc}\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={"detail": "An unexpected error occurred. Please try again later."},
        )
