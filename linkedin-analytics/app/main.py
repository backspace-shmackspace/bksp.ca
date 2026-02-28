"""FastAPI application factory.

Creates and configures the FastAPI app:
  - Mounts static files
  - Includes route routers (dashboard, API, upload)
  - Initializes the database on startup via lifespan context manager
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.routes.api import router as api_router
from app.routes.dashboard import router as dashboard_router
from app.routes.upload import router as upload_router

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: initialize database on startup."""
    logger.info("Starting LinkedIn Analytics Dashboard on port %s", settings.app_port)
    import app.database as db_module
    init_db(db_module.engine)
    logger.info("Database ready at %s", settings.db_path)
    yield
    logger.info("Shutting down LinkedIn Analytics Dashboard.")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title="LinkedIn Analytics Dashboard",
        description="Self-hosted LinkedIn content performance dashboard.",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Mount static files
    application.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Include routers
    application.include_router(dashboard_router)
    application.include_router(api_router)
    application.include_router(upload_router)

    return application


app = create_app()
