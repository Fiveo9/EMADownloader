"""Tests for streaming downloader, validation, and incremental sync."""

import hashlib
from pathlib import Path
import httpx
import pytest

from ema_downloader.config import AppConfig
from ema_downloader.database import Database
from ema_downloader.downloader import (
    Downloader,
    validate_downloaded_file,
    compute_file_sha256,
)
from ema_downloader.models import DownloadStatus, EMADocument


def test_validate_downloaded_file(tmp_path: Path):
    # Valid PDF file
    valid_pdf = tmp_path / "valid.pdf"
    valid_pdf.write_bytes(b"%PDF-1.4\n" + b"A" * 1000)
    ok, err = validate_downloaded_file(valid_pdf)
    assert ok is True
    assert err == ""

    # HTML error page
    html_page = tmp_path / "error.pdf"
    html_page.write_bytes(b"<!DOCTYPE html><html><body>Error 404</body></html>" + b" " * 600)
    ok, err = validate_downloaded_file(html_page)
    assert ok is False
    assert "HTML" in err

    # Too small
    small_file = tmp_path / "small.pdf"
    small_file.write_bytes(b"%PDF-1.4\n123")
    ok, err = validate_downloaded_file(small_file)
    assert ok is False
    assert "too small" in err


def test_incremental_plan_document(sample_config: AppConfig, sample_db: Database, tmp_path: Path):
    downloader = Downloader(sample_config, sample_db)

    doc = EMADocument(
        ema_id="301",
        name="Guideline on PK",
        document_type="scientific-guideline",
        official_url="https://www.ema.europa.eu/pk.pdf",
        local_path="01_Scientific_Guidelines/02_Nonclinical/pk.pdf",
        local_filename="pk.pdf",
        last_updated_at="2024-01-01",
    )

    # 1. Not in DB -> "new"
    action, reason = downloader.plan_document(doc)
    assert action == "new"

    # Insert into DB and create local file
    file_path = sample_config.storage.library_dir / doc.local_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_content = b"%PDF-1.4\n" + b"X" * 1000
    file_path.write_bytes(file_content)
    file_sha = hashlib.sha256(file_content).hexdigest()

    doc.download_status = DownloadStatus.DOWNLOADED.value
    doc.file_size = len(file_content)
    doc.sha256 = file_sha
    sample_db.upsert_document(doc)

    # 2. In DB, file exists, metadata unchanged -> "skip"
    action, reason = downloader.plan_document(doc)
    assert action == "skip"

    # 3. Metadata changed (last_updated_at) -> "updated"
    updated_doc = EMADocument(
        ema_id="301",
        name="Guideline on PK",
        document_type="scientific-guideline",
        official_url="https://www.ema.europa.eu/pk.pdf",
        local_path="01_Scientific_Guidelines/02_Nonclinical/pk.pdf",
        local_filename="pk.pdf",
        last_updated_at="2025-06-01",  # Changed!
    )
    action, reason = downloader.plan_document(updated_doc)
    assert action == "updated"

    # 4. File deleted from disk -> "new"
    file_path.unlink()
    action, reason = downloader.plan_document(doc)
    assert action == "new"


def test_download_single_document_mocked(sample_config: AppConfig, sample_db: Database):
    downloader = Downloader(sample_config, sample_db)

    doc = EMADocument(
        ema_id="501",
        name="Test Download Guideline",
        document_type="scientific-guideline",
        official_url="https://mock.ema.europa.eu/test.pdf",
        local_path="01_Scientific_Guidelines/test_doc.pdf",
        local_filename="test_doc.pdf",
    )

    # Mock transport
    content = b"%PDF-1.7\n" + b"Mock PDF stream data" * 50
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=content, headers={"Content-Type": "application/pdf"})
    )

    with httpx.Client(transport=transport) as client:
        res = downloader.download_single_document(doc, client=client)

    assert res.success is True
    assert res.status == DownloadStatus.DOWNLOADED
    assert res.file_size == len(content)

    saved_file = sample_config.storage.library_dir / doc.local_path
    assert saved_file.exists()
    assert saved_file.read_bytes() == content

    # Check database was updated
    db_doc = sample_db.get_document("501")
    assert db_doc is not None
    assert db_doc.download_status == DownloadStatus.DOWNLOADED.value
    assert db_doc.sha256 == hashlib.sha256(content).hexdigest()
