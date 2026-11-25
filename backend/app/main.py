"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.api.profiles import router as profiles_router
from app.config import get_settings
from app.db import get_engine, init_db


@asynccontextmanager
async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
    """Ensure database tables exist on startup."""
    init_db(get_engine())
    yield


def create_app(initialize_db: bool = True) -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        version="0.1.0",
        lifespan=lifespan if initialize_db else None,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(health_router)
    application.include_router(profiles_router)
    application.include_router(chat_router)
    return application


app = create_app()
