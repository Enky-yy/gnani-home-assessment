from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.storage import StorageService, get_storage_service
from app.services.gnani_stt import GnaniSTTClient
from app.services.auth import get_current_user
from app.models.user import User

__all__ = ["get_db", "get_storage", "get_gnani_client", "get_current_user", "User"]


def get_storage() -> StorageService:
    return get_storage_service()


def get_gnani_client() -> GnaniSTTClient:
    return GnaniSTTClient()
