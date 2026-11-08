"""Object storage + malware-scanning adapters (cloud specifics stay behind these interfaces)."""
from __future__ import annotations

import os
import socket
import struct
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import settings


class Storage(ABC):
    @abstractmethod
    def put(self, key: str, data: bytes) -> str: ...

    @abstractmethod
    def get(self, key: str) -> bytes: ...


class LocalStorage(Storage):
    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root not in p.parents:
            raise ValueError("invalid storage key")
        return p

    def put(self, key: str, data: bytes) -> str:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return key

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()


class S3Storage(Storage):
    """S3-compatible storage (AWS S3, MinIO, GCS interop, Azure via S3 gateways). Requires boto3."""

    def __init__(self, bucket: str):
        import boto3  # optional dependency

        self.bucket = bucket
        self.client = boto3.client("s3", endpoint_url=os.getenv("S3_ENDPOINT_URL") or None)

    def put(self, key: str, data: bytes) -> str:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ServerSideEncryption="AES256")
        return key

    def get(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()


def get_storage() -> Storage:
    if os.getenv("STORAGE_BACKEND", "local") == "s3":
        return S3Storage(os.environ["S3_BUCKET"])
    return LocalStorage(settings.storage_dir)


def new_key(org_id: uuid.UUID, kind: str, filename: str) -> str:
    ext = Path(filename).suffix.lower()[:6]
    return f"{org_id}/{kind}/{uuid.uuid4().hex}{ext}"


class ScanResult:
    def __init__(self, status: str, detail: str = ""):
        self.status = status  # CLEAN | INFECTED | NOT_SCANNED | ERROR
        self.detail = detail


def scan_bytes(data: bytes) -> ScanResult:
    """ClamAV INSTREAM scan when FILE_SCANNER=clamav; otherwise NOT_SCANNED (recorded honestly)."""
    if settings.file_scanner != "clamav":
        return ScanResult("NOT_SCANNED", "file scanning disabled (FILE_SCANNER=none)")
    try:
        with socket.create_connection((settings.clamav_host, settings.clamav_port), timeout=10) as s:
            s.sendall(b"zINSTREAM\0")
            for i in range(0, len(data), 8192):
                chunk = data[i:i + 8192]
                s.sendall(struct.pack("!L", len(chunk)) + chunk)
            s.sendall(struct.pack("!L", 0))
            reply = s.recv(4096).decode(errors="ignore").strip("\0").strip()
        if reply.endswith("OK"):
            return ScanResult("CLEAN", reply)
        if "FOUND" in reply:
            return ScanResult("INFECTED", reply)
        return ScanResult("ERROR", reply)
    except OSError as e:
        return ScanResult("ERROR", f"scanner unavailable: {e}")
