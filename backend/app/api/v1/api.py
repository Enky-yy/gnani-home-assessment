from fastapi import APIRouter
from app.api.v1.endpoints import notes, health, models

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(notes.router, prefix="/notes", tags=["Audio Notes"])
api_router.include_router(models.router, prefix="/models", tags=["Models"])
