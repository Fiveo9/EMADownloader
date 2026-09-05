"""Robust streaming document downloader with validation and incremental sync."""

from __future__ import annotations

import hashlib
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import httpx

from ema_downloader.config import AppConfig
from ema_downloader.database import Database
from ema_downloader.ema_source import create_httpx_client
from ema_downloader.models import DownloadStatus, EMADocument

logger = logging.getLogger(__name__)

# Minimum plausible size for a legitimate PDF document
MIN_VALID_FILE_SIZE = 512
PDF_MAGIC_BYTES = b"%PDF-"


class DownloadResult:
    """Result of a single file download attempt."""

    def __init__(
        self,
        doc: EMADocument,
        success: bool,
        status: DownloadStatus,
        http_status: Optional[int] = None,
        content_type: str = "",
        file_size: int = 0,
        sha256: str = "",
        error_message: str = "",
    ) -> None:
        self.doc = doc
        self.success = success
        self.status = status
        self.http_status = http_status
        self.content_type = content_type
        self.file_size = file_size
        self.sha256 = sha256
        self.error_message = error_message


def validate_downloaded_file(file_path: Path, expected_ext: str = ".pdf") -> Tuple[bool, str]:
    """Validate that downloaded file is not an HTML error page or corrupt empty file."""
    if not file_path.exists():
        return False, "File does not exist on disk"

    size = file_path.stat().st_size
    if size < MIN_VALID_FILE_SIZE:
        return False, f"File size too small ({size} bytes < {MIN_VALID_FILE_SIZE})"

    if expected_ext.lower() == ".pdf":
        try:
            with open(file_path, "rb") as f:
                header = f.read(1024)
                if PDF_MAGIC_BYTES not in header:
                    if b"<html" in header.lower() or b"<!doctype html" in header.lower():
                        return False, "Received HTML error/redirect page instead of valid PDF"
                    return False, "Missing %PDF- magic header in document file"
        except Exception as e:
            return False, f"Failed to read file header: {e}"

    return True, ""


def compute_file_sha256(file_path: Path) -> str:
    """Compute SHA-256 hash of a file on disk."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(1048576):
            hasher.update(chunk)
    return hasher.hexdigest()


class Downloader:
    """Coordinates incremental downloads with retry, rate-limiting, and validation."""

    def __init__(self, config: AppConfig, database: Database) -> None:
        self.config = config
        self.db = database
        self.library_dir = config.storage.library_dir

    def plan_document(self, doc: EMADocument) -> Tuple[str, str]:
        """Determine incremental sync action for a document.

        Returns:
            (action, reason) where action is 'new', 'updated', 'skip', or 'no_url'
        """
        if not doc.official_url:
            return "no_url", "Missing official download URL"

        existing = self.db.get_document(doc.ema_id)
        if not existing:
            return "new", "New document not present in local index"

        # Check metadata changes
        if doc.last_updated_at and existing.last_updated_at and doc.last_updated_at != existing.last_updated_at:
            return "updated", f"Last updated date changed ({existing.last_updated_at} -> {doc.last_updated_at})"

        if doc.official_url != existing.official_url:
            return "updated", "Official URL changed"

        # Verify local file presence
        local_file_path = self.library_dir / (existing.local_path or doc.local_path)
        if not local_file_path.exists():
            return "new", "Local file missing from disk, re-download needed"

        # Verify file size and checksum if already downloaded
        if existing.download_status in (DownloadStatus.DOWNLOADED.value, DownloadStatus.UPDATED.value):
            if local_file_path.stat().st_size == 0:
                return "updated", "Local file exists but is empty (0 bytes)"
            if existing.sha256:
                # Fast check or verify
                return "skip", "Document and local file unchanged"

        return "skip", "Document unchanged in index"

    def download_single_document(
        self,
        doc: EMADocument,
        client: Optional[httpx.Client] = None,
        is_update: bool = False,
    ) -> DownloadResult:
        """Stream download a single document, validate it, and atomically save it."""
        if not doc.official_url:
            return DownloadResult(
                doc=doc,
                success=False,
                status=DownloadStatus.NO_DOWNLOAD_URL,
                error_message="No official download URL provided",
            )

        target_file = self.library_dir / doc.local_path
        target_file.parent.mkdir(parents=True, exist_ok=True)
        temp_file = target_file.with_name(f"{target_file.name}.tmp")

        close_client = False
        if client is None:
            client = create_httpx_client(self.config)
            close_client = True

        retries = self.config.network.max_retries
        delay = self.config.network.retry_delay
        hasher = hashlib.sha256()
        total_bytes = 0
        content_type = ""
        http_status = None
        last_error = ""

        try:
            for attempt in range(1, retries + 1):
                try:
                    hasher = hashlib.sha256()
                    total_bytes = 0

                    with client.stream("GET", doc.official_url) as resp:
                        http_status = resp.status_code
                        content_type = resp.headers.get("content-type", "")

                        if resp.status_code in (429, 503):
                            raise httpx.HTTPStatusError(
                                f"Rate limited / Service unavailable: {resp.status_code}",
                                request=resp.request,
                                response=resp,
                            )

                        if resp.status_code != 200:
                            return DownloadResult(
                                doc=doc,
                                success=False,
                                status=DownloadStatus.HTTP_ERROR,
                                http_status=http_status,
                                content_type=content_type,
                                error_message=f"HTTP {http_status}",
                            )

                        with open(temp_file, "wb") as f:
                            for chunk in resp.iter_bytes(chunk_size=self.config.network.chunk_size):
                                f.write(chunk)
                                hasher.update(chunk)
                                total_bytes += len(chunk)

                    # Validate downloaded content
                    valid, reason = validate_downloaded_file(temp_file, expected_ext=doc.file_extension)
                    if not valid:
                        temp_file.unlink(missing_ok=True)
                        return DownloadResult(
                            doc=doc,
                            success=False,
                            status=DownloadStatus.INVALID_CONTENT,
                            http_status=http_status,
                            content_type=content_type,
                            file_size=total_bytes,
                            error_message=reason,
                        )

                    # Atomic move into final position
                    os.replace(temp_file, target_file)

                    digest = hasher.hexdigest()
                    final_status = DownloadStatus.UPDATED if is_update else DownloadStatus.DOWNLOADED

                    # Ensure document is indexed in database
                    if not self.db.get_document(doc.ema_id):
                        self.db.upsert_document(doc)

                    # Update database
                    self.db.update_download_result(
                        ema_id=doc.ema_id,
                        download_status=final_status.value,
                        http_status=http_status,
                        content_type=content_type,
                        file_size=total_bytes,
                        sha256=digest,
                        local_path=doc.local_path,
                        downloaded_at=datetime.now(timezone.utc).isoformat(),
                    )

                    # Add configurable delay to avoid rate limiting
                    time.sleep(self.config.network.request_delay)

                    return DownloadResult(
                        doc=doc,
                        success=True,
                        status=final_status,
                        http_status=http_status,
                        content_type=content_type,
                        file_size=total_bytes,
                        sha256=digest,
                    )

                except (httpx.RequestError, httpx.HTTPStatusError) as e:
                    temp_file.unlink(missing_ok=True)
                    last_error = str(e)
                    if attempt < retries:
                        # For rate limiting (429), use longer exponential backoff
                        if "429" in str(e) or "Rate limited" in str(e):
                            sleep_time = delay * (3 ** attempt)  # 3, 9, 27 seconds
                            logger.warning(f"Rate limited, waiting {sleep_time:.1f}s before retry {attempt + 1}/{retries}")
                        else:
                            sleep_time = delay * (2 ** (attempt - 1))
                        time.sleep(sleep_time)
                except Exception as e:
                    temp_file.unlink(missing_ok=True)
                    return DownloadResult(
                        doc=doc,
                        success=False,
                        status=DownloadStatus.WRITE_ERROR,
                        http_status=http_status,
                        error_message=f"Write error: {e}",
                    )

            # All retries failed
            return DownloadResult(
                doc=doc,
                success=False,
                status=DownloadStatus.HTTP_ERROR,
                http_status=http_status,
                error_message=f"Failed after {retries} retries: {last_error}",
            )

        finally:
            if temp_file.exists():
                temp_file.unlink(missing_ok=True)
            if close_client:
                client.close()

    def download_batch(
        self,
        planned_items: List[Tuple[EMADocument, str]],
        progress_callback: Optional[Callable[[DownloadResult], None]] = None,
    ) -> List[DownloadResult]:
        """Download multiple documents concurrently using thread pool."""
        results: List[DownloadResult] = []
        if not planned_items:
            return results

        workers = max(1, min(self.config.network.workers, 16))

        with create_httpx_client(self.config) as shared_client:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(
                        self.download_single_document,
                        doc,
                        shared_client,
                        action == "updated",
                    ): doc
                    for doc, action in planned_items
                }

                for future in as_completed(futures):
                    try:
                        res = future.result()
                        results.append(res)
                        if progress_callback:
                            progress_callback(res)
                    except Exception as e:
                        doc = futures[future]
                        res = DownloadResult(
                            doc=doc,
                            success=False,
                            status=DownloadStatus.WRITE_ERROR,
                            error_message=f"Unexpected thread exception: {e}",
                        )
                        results.append(res)
                        if progress_callback:
                            progress_callback(res)

        return results

    def verify_library(self) -> List[dict]:
        """Verify integrity of all documents recorded in the database."""
        docs = self.db.get_documents()
        issues = []

        for doc in docs:
            # Check docs marked as downloaded or having a local file specified
            if doc.local_path:
                local_file = self.library_dir / doc.local_path
                if not local_file.exists():
                    if doc.download_status in (DownloadStatus.DOWNLOADED.value, DownloadStatus.UPDATED.value):
                        issues.append({
                            "ema_id": doc.ema_id,
                            "name": doc.name,
                            "local_path": doc.local_path,
                            "issue": "File missing from disk",
                        })
                    continue

                size = local_file.stat().st_size
                if size == 0 or size < MIN_VALID_FILE_SIZE:
                    issues.append({
                        "ema_id": doc.ema_id,
                        "name": doc.name,
                        "local_path": doc.local_path,
                        "issue": f"File too small ({size} bytes)",
                    })
                    continue

                valid, reason = validate_downloaded_file(local_file, doc.file_extension)
                if not valid:
                    issues.append({
                        "ema_id": doc.ema_id,
                        "name": doc.name,
                        "local_path": doc.local_path,
                        "issue": reason,
                    })
                    continue

                actual_sha = compute_file_sha256(local_file)
                if doc.sha256:
                    if actual_sha != doc.sha256:
                        issues.append({
                            "ema_id": doc.ema_id,
                            "name": doc.name,
                            "local_path": doc.local_path,
                            "issue": f"SHA-256 mismatch (db: {doc.sha256[:8]}..., disk: {actual_sha[:8]}...)",
                        })
                else:
                    # Backfill missing sha256 and file_size in database
                    self.db.update_download_result(
                        ema_id=doc.ema_id,
                        download_status=DownloadStatus.DOWNLOADED.value,
                        file_size=size,
                        sha256=actual_sha,
                    )

        return issues
