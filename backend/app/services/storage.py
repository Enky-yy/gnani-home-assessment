import os
import shutil
import logging
from abc import ABC, abstractmethod
from typing import BinaryIO, Optional
import boto3
from botocore.exceptions import ClientError
from app.config import settings

logger = logging.getLogger(__name__)


class StorageService(ABC):
    """Abstract Base Class for Audio File Storage."""

    @abstractmethod
    def upload_file(self, file_obj: BinaryIO, key: str, content_type: str) -> str:
        """Upload a file stream to storage and return its identifier/path."""
        pass

    @abstractmethod
    def download_file(self, key: str, destination_path: str) -> None:
        """Download a file from storage to local disk."""
        pass

    @abstractmethod
    def generate_access_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a URL to stream or download the audio file."""
        pass

    @abstractmethod
    def delete_file(self, key: str) -> bool:
        """Delete a file from storage."""
        pass

    @abstractmethod
    def file_exists(self, key: str) -> bool:
        """Check if file exists in storage."""
        pass


class S3StorageService(StorageService):
    """Production AWS S3 Storage Service using boto3."""

    def __init__(self):
        self.bucket_name = settings.AWS_S3_BUCKET_NAME
        self.region = settings.AWS_REGION
        
        session_kwargs = {"region_name": self.region}
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            session_kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
            session_kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY

        self.s3_client = boto3.client(
            "s3",
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            **session_kwargs
        )
        logger.info(f"Initialized AWS S3 Storage Service for bucket: {self.bucket_name} in region: {self.region}")

    def upload_file(self, file_obj: BinaryIO, key: str, content_type: str) -> str:
        try:
            file_obj.seek(0)
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                key,
                ExtraArgs={"ContentType": content_type}
            )
            logger.info(f"Successfully uploaded {key} to S3 bucket {self.bucket_name}")
            return key
        except ClientError as e:
            logger.error(f"S3 upload error for key {key}: {e}")
            raise RuntimeError(f"Failed to upload audio to S3: {e}")

    def download_file(self, key: str, destination_path: str) -> None:
        try:
            os.makedirs(os.path.dirname(destination_path), exist_ok=True)
            self.s3_client.download_file(self.bucket_name, key, destination_path)
            logger.info(f"Downloaded S3 object {key} to {destination_path}")
        except ClientError as e:
            logger.error(f"S3 download error for key {key}: {e}")
            raise RuntimeError(f"Failed to download audio from S3: {e}")

    def generate_access_url(self, key: str, expires_in: int = 3600) -> str:
        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=expires_in,
            )
            return url
        except ClientError as e:
            logger.error(f"Error generating presigned S3 URL for {key}: {e}")
            return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{key}"

    def delete_file(self, key: str) -> bool:
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            logger.info(f"Deleted S3 object {key}")
            return True
        except ClientError as e:
            logger.error(f"S3 delete error for {key}: {e}")
            return False

    def file_exists(self, key: str) -> bool:
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError:
            return False


class LocalStorageService(StorageService):
    """Local filesystem storage service (for development and zero-cloud tests)."""

    def __init__(self):
        self.base_dir = os.path.abspath(settings.LOCAL_STORAGE_DIR)
        os.makedirs(self.base_dir, exist_ok=True)
        logger.info(f"Initialized Local Storage Service at {self.base_dir}")

    def _get_absolute_path(self, key: str) -> str:
        # Preserve partitioned hierarchy (e.g. audio/<note_id>/<file>)
        # while preventing directory traversal.
        raw = (key or "").replace("\\", "/")
        if ".." in raw.split("/"):
            raise ValueError(f"Storage key escapes base directory: {key!r}")
        normalized = os.path.normpath(raw)
        parts = [p for p in normalized.split("/") if p not in ("", ".", "..")]
        if not parts:
            raise ValueError(f"Invalid storage key: {key!r}")
        # Limit filename length to avoid OS errors
        parts[-1] = parts[-1][:200] or "file"
        abs_path = os.path.abspath(os.path.join(self.base_dir, *parts))
        if abs_path != self.base_dir and not abs_path.startswith(self.base_dir + os.sep):
            raise ValueError(f"Storage key escapes base directory: {key!r}")
        return abs_path

    def resolve_local_path(self, key: str) -> str:
        """Return the absolute filesystem path for a storage key."""
        return self._get_absolute_path(key)

    def upload_file(self, file_obj: BinaryIO, key: str, content_type: str) -> str:
        dest_path = self._get_absolute_path(key)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        file_obj.seek(0)
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(file_obj, f)
        logger.info(f"Saved local file to {dest_path}")
        return key

    def download_file(self, key: str, destination_path: str) -> None:
        source_path = self._get_absolute_path(key)
        if not os.path.exists(source_path):
            # Backward compat: files saved by the old basename-only layout.
            legacy = os.path.join(self.base_dir, os.path.basename(key))
            if os.path.exists(legacy):
                logger.warning(f"Resolving legacy flat-layout file for key {key!r}")
                source_path = legacy
            else:
                raise FileNotFoundError(f"Local file {source_path} does not exist.")
        os.makedirs(os.path.dirname(os.path.abspath(destination_path)), exist_ok=True)
        if os.path.abspath(source_path) != os.path.abspath(destination_path):
            shutil.copyfile(source_path, destination_path)

    def generate_access_url(self, key: str, expires_in: int = 3600) -> str:
        # Derive note_id from partitioned key layout audio/<note_id>/<filename>
        # so the URL matches GET /api/v1/notes/{note_id}/audio.
        parts = [p for p in key.replace("\\", "/").split("/") if p]
        note_id = parts[1] if len(parts) >= 3 and parts[0] == "audio" else None
        if note_id:
            return f"{settings.API_V1_STR}/notes/{note_id}/audio"
        # Fallback for legacy flat keys: stream via basename lookup is no
        # longer supported; return the generic audio route prefix.
        return f"{settings.API_V1_STR}/notes/audio"

    def delete_file(self, key: str) -> bool:
        path = self._get_absolute_path(key)
        # Also purge legacy flat-layout copy if present.
        legacy = os.path.join(self.base_dir, os.path.basename(key))
        deleted = False
        for candidate in {path, legacy}:
            if os.path.exists(candidate):
                os.remove(candidate)
                deleted = True
        if deleted:
            # Clean up now-empty parent dirs up to base_dir (e.g. audio/<note_id>/)
            try:
                parent = os.path.dirname(path)
                while parent.startswith(self.base_dir) and parent != self.base_dir:
                    if os.path.isdir(parent) and not os.listdir(parent):
                        os.rmdir(parent)
                        parent = os.path.dirname(parent)
                    else:
                        break
            except OSError:
                pass
            return True
        return False

    def file_exists(self, key: str) -> bool:
        try:
            if os.path.exists(self._get_absolute_path(key)):
                return True
            # Legacy flat-layout fallback
            return os.path.exists(os.path.join(self.base_dir, os.path.basename(key)))
        except ValueError:
            return False


def get_storage_service() -> StorageService:
    """Factory to retrieve storage service based on configuration."""
    if settings.STORAGE_BACKEND.lower() == "s3":
        try:
            return S3StorageService()
        except Exception as e:
            logger.warning(f"Could not initialize S3 storage ({e}). Falling back to LocalStorageService.")
            return LocalStorageService()
    return LocalStorageService()
