"""Tests for streaming downloader, validation, and incremental sync."""

import hashlib
import time
from pathlib import Path

import httpx
import pytest

import ema_downloader.downloader as downloader_module
from ema_downloader.config import AppConfig
from ema_downloader.database import Database
from ema_downloader.downloader import (
    DownloadCancelled,
    Downloader,
    validate_downloaded_file,
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
        lambda request: httpx.Response(
            200, content=iter([content]), headers={"Content-Type": "application/pdf"}
        )
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


def _make_doc(ema_id: str, filename: str) -> EMADocument:
    return EMADocument(
        ema_id=ema_id,
        name=f"Test Document {ema_id}",
        document_type="scientific-guideline",
        official_url=f"https://mock.ema.europa.eu/{filename}",
        local_path=f"01_Scientific_Guidelines/{filename}",
        local_filename=filename,
    )


def test_download_cancelled_midstream(sample_config: AppConfig, sample_db: Database):
    """An in-flight download aborts at the next chunk boundary when cancelled."""
    downloader = Downloader(sample_config, sample_db)
    doc = _make_doc("502", "cancelled.pdf")

    def handler(request: httpx.Request) -> httpx.Response:
        def stream():
            yield b"%PDF-1.7\n"
            time.sleep(5)  # must never be reached: cancel fires first
            yield b"tail"

        return httpx.Response(200, content=stream())

    polls = {"n": 0}

    def cancel_check() -> bool:
        polls["n"] += 1
        return polls["n"] > 1  # first poll (attempt start) passes, chunk poll cancels

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        start = time.monotonic()
        with pytest.raises(DownloadCancelled):
            downloader.download_single_document(doc, client=client, cancel_check=cancel_check)
        assert time.monotonic() - start < 3

    target = sample_config.storage.library_dir / doc.local_path
    assert not target.exists()
    assert not target.with_name(target.name + ".tmp").exists()


def test_download_stalled_attempt_is_retried(
    sample_config: AppConfig, sample_db: Database, monkeypatch: pytest.MonkeyPatch
):
    """A trickle-stalled transfer is aborted by stall detection and retried."""
    sample_config.network.max_retries = 2
    sample_config.network.retry_delay = 0.0
    sample_config.network.request_delay = 0.0
    monkeypatch.setattr(downloader_module, "STALL_WINDOW_SECONDS", 0.3)
    monkeypatch.setattr(downloader_module, "STALL_MIN_BYTES", 64 * 1024)

    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] == 1:

            def trickle():
                yield b"%PDF-1.7\n"
                time.sleep(1.0)  # far beyond the stall window
                yield b"tail"

            return httpx.Response(200, content=trickle())
        return httpx.Response(200, content=iter([b"%PDF-1.7\n" + b"fast" * 300]))

    downloader = Downloader(sample_config, sample_db)
    doc = _make_doc("503", "stalled.pdf")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        res = downloader.download_single_document(doc, client=client)

    assert res.success is True
    assert attempts["n"] == 2
    assert (sample_config.storage.library_dir / doc.local_path).exists()


def test_download_batch_cancel_stops_promptly(
    sample_config: AppConfig, sample_db: Database, monkeypatch: pytest.MonkeyPatch
):
    """Cancelling drops queued files and aborts in-flight workers within seconds."""
    sample_config.network.workers = 1

    def handler(request: httpx.Request) -> httpx.Response:
        def stream():
            yield b"%PDF-1.7\n"
            time.sleep(8)  # in-flight file must not be waited for
            yield b"tail"

        return httpx.Response(200, content=stream())

    monkeypatch.setattr(
        "ema_downloader.downloader.create_httpx_client",
        lambda config: httpx.Client(transport=httpx.MockTransport(handler)),
    )

    docs = [_make_doc(str(600 + i), f"batch{i}.pdf") for i in range(3)]
    downloader = Downloader(sample_config, sample_db)

    start = time.monotonic()
    results = downloader.download_batch([(d, "new") for d in docs], cancel_check=lambda: True)
    elapsed = time.monotonic() - start

    assert elapsed < 4, f"batch took {elapsed:.1f}s to stop"
    assert results == []  # cancelled files are neither successes nor failures
