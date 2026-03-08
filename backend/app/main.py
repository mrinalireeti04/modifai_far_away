from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.v1.router import router as v1_router
from app.api.error_handlers import register_error_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    # e.g. connect to DB, load ML models, etc.
    yield
    # --- Shutdown ---
    # e.g. close DB connections, release resources


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global error handlers
    register_error_handlers(app)

    # Mount versioned API
    app.include_router(v1_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()
