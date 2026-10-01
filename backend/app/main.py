import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import init_db
from app.api.v1.api import api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    logger.info("Initializing Audio Notes Platform API...")
    # Initialize database tables
    await init_db()
    logger.info("Database tables initialized successfully.")
    yield
    logger.info("Shutting down Audio Notes Platform API...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "Backend API for Audio Notes Platform. Integrates Gnani Voice AI STT, "
        "AWS S3 Object Storage, PostgreSQL, and LLM Summarization."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add X-Process-Time-Ms diagnostic header to all responses."""
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = (time.perf_counter() - start_time) * 1000
    response.headers["X-Process-Time-Ms"] = f"{process_time:.2f}"
    return response


# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": str(exc) if settings.DEBUG else "An unexpected server error occurred.",
            "path": request.url.path,
        },
    )


# Mount API V1
app.include_router(api_router, prefix=settings.API_V1_STR)

# Top-level /health alias for load balancers and quick checks
from app.api.v1.endpoints.health import health_check
app.add_api_route("/health", health_check, methods=["GET"], tags=["Health"], include_in_schema=False)

# OpenAI-compatible /v1/models alias
from app.api.v1.endpoints.models import list_models
app.add_api_route("/v1/models", list_models, methods=["GET"], tags=["Models"], include_in_schema=False)


@app.get("/", tags=["Root"])
async def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "online",
        "docs": "/docs",
        "health": "/health",
        "models": "/v1/models",
        "api_v1": settings.API_V1_STR,
    }
