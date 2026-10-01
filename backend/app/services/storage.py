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
        self.base_dir = settings.LOCAL_STORAGE_DIR
        os.makedirs(self.base_dir, exist_ok=True)
        logger.info(f"Initialized Local Storage Service at {self.base_dir}")

    def _get_absolute_path(self, key: str) -> str:
        # Sanitize path to prevent directory traversal
        sanitized_key = os.path.basename(key)
        return os.path.join(self.base_dir, sanitized_key)

    def upload_file(self, file_obj: BinaryIO, key: str, content_type: str) -> str:
        dest_path = self._get_absolute_path(key)
        file_obj.seek(0)
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(file_obj, f)
        logger.info(f"Saved local file to {dest_path}")
        return key

    def download_file(self, key: str, destination_path: str) -> None:
        source_path = self._get_absolute_path(key)
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Local file {source_path} does not exist.")
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        if source_path != destination_path:
            shutil.copyfile(source_path, destination_path)

    def generate_access_url(self, key: str, expires_in: int = 3600) -> str:
        # Returns API streaming endpoint for audio
        return f"{settings.API_V1_STR}/notes/{key}/audio"

    def delete_file(self, key: str) -> bool:
        path = self._get_absolute_path(key)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def file_exists(self, key: str) -> bool:
        return os.path.exists(self._get_absolute_path(key))


def get_storage_service() -> StorageService:
    """Factory to retrieve storage service based on configuration."""
    if settings.STORAGE_BACKEND.lower() == "s3":
        try:
            return S3StorageService()
        except Exception as e:
            logger.warning(f"Could not initialize S3 storage ({e}). Falling back to LocalStorageService.")
            return LocalStorageService()
    return LocalStorageService()
