"""FastAPI application factory with lifecycle management and graceful shutdown."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from crawler import __version__
from crawler.api.routes import router
from crawler.core.config import settings
from crawler.core.logging import logger
from crawler.pipeline.manager import job_manager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application startup and graceful shutdown."""
    logger.info(f"Starting {settings.app_name} v{__version__} API service...")
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    yield
    # Graceful shutdown handler
    logger.info("Graceful shutdown received. Cancelling running crawl jobs...")
    for job_id in list(job_manager._jobs.keys()):
        try:
            await job_manager.cancel_job(job_id)
        except Exception:
            pass
    logger.info("Shutdown tasks completed.")


def create_app() -> FastAPI:
    """Builds and configures the FastAPI application instance."""
    app = FastAPI(
        title="Sprawler: Business-Knowledge Web Crawler",
        description=(
            "Production-grade, asynchronous business knowledge extractor optimized for RAG systems. "
            "Discovers company domain activities, contact information, hours, addresses, FAQs, and policies "
            "while cleanly skipping product catalogs and pagination loops."
        ),
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Enable CORS for browser integration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    return app


# Default app instance for Uvicorn
app = create_app()
