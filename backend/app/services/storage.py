"""Storage abstraction for MinIO/local fallback."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Optional

from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)


@dataclass
class StorageConfig:
    endpoint: str
    access_key: str
    secret_key: str
    bucket: str
    secure: bool = False
    base_dir: Optional[Path] = None  # local fallback


class StorageClient:
    """Lightweight wrapper to read/write objects to MinIO with local fallback."""

    def __init__(self, cfg: StorageConfig) -> None:
        self.cfg = cfg
        # 默认落地路径调整到 rag/data 下，避免 backend/backend 重复
        self._local = cfg.base_dir or Path("rag/data/uploads")
        self._local.mkdir(parents=True, exist_ok=True)

        self._client: Optional[Minio] = None
        if cfg.endpoint and cfg.access_key and cfg.secret_key:
            try:
                self._client = Minio(
                    cfg.endpoint,
                    access_key=cfg.access_key,
                    secret_key=cfg.secret_key,
                    secure=cfg.secure,
                )
                self._ensure_bucket()
                logger.info("MinIO storage initialized: %s/%s", cfg.endpoint, cfg.bucket)
            except Exception as exc:  # pragma: no cover
                logger.warning("MinIO init failed, fallback to local: %s", exc)
                self._client = None

    def _ensure_bucket(self) -> None:
        assert self._client
        if not self._client.bucket_exists(self.cfg.bucket):
            self._client.make_bucket(self.cfg.bucket)

    def put(self, object_name: str, data: BinaryIO, length: int, content_type: str | None = None) -> str:
        """Upload object, return storage URI."""
        if self._client:
            try:
                self._client.put_object(
                    self.cfg.bucket,
                    object_name,
                    data,
                    length=length,
                    content_type=content_type,
                )
                return f"minio://{self.cfg.bucket}/{object_name}"
            except S3Error as exc:  # pragma: no cover
                logger.warning("MinIO put_object failed, fallback to local: %s", exc)

        # fallback: save to local disk
        target = self._local / object_name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as fp:
            fp.write(data.read())
        return str(target)

    def get(self, object_name: str, target_path: Path) -> Path:
        """Download object to target_path, return local path."""
        if self._client:
            try:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                self._client.fget_object(self.cfg.bucket, object_name, str(target_path))
                return target_path
            except S3Error as exc:  # pragma: no cover
                logger.warning("MinIO fget_object failed, fallback to local: %s", exc)

        # fallback to local storage path
        local_obj = self._local / object_name
        if not local_obj.exists():
            raise FileNotFoundError(f"object not found: {object_name}")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(local_obj.read_bytes())
        return target_path

    def delete(self, object_name: str) -> None:
        """Delete object from MinIO/local; ignore errors."""
        if self._client:
            try:
                self._client.remove_object(self.cfg.bucket, object_name)
            except Exception as exc:  # pragma: no cover
                logger.warning("MinIO remove_object failed: %s", exc)
        local_obj = self._local / object_name
        try:
            if local_obj.exists():
                local_obj.unlink()
        except Exception as exc:  # pragma: no cover
            logger.warning("Delete local object failed: %s", exc)
