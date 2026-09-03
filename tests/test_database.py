"""Tests for SQLite database index operations."""

from ema_downloader.database import Database
from ema_downloader.models import DownloadStatus, EMADocument, SyncSummary


def test_database_init(sample_db: Database):
    assert sample_db.db_path.exists()
    counts = sample_db.get_summary_counts()
    assert counts.get("total") == 0


def test_upsert_and_retrieve_document(sample_db: Database):
    doc = EMADocument(
        ema_id="101",
        name="Guideline on clinical trials",
        document_type="scientific-guideline",
        status="Adopted",
        reference_number="EMA/CHMP/101",
        first_published_at="2020-01-01",
        last_updated_at="2022-01-01",
        official_url="https://www.ema.europa.eu/test.pdf",
        local_path="01_Scientific_Guidelines/03_Clinical/test.pdf",
        local_filename="test.pdf",
    )
    sample_db.upsert_document(doc)

    retrieved = sample_db.get_document("101")
    assert retrieved is not None
    assert retrieved.ema_id == "101"
    assert retrieved.name == "Guideline on clinical trials"
    assert retrieved.status == "Adopted"


def test_batch_upsert_and_filters(sample_db: Database):
    docs = [
        EMADocument(
            ema_id=str(i),
            name=f"Document {i} safety",
            document_type="scientific-guideline" if i % 2 == 0 else "regulatory-procedural-guideline",
            status="Adopted" if i < 3 else "Draft",
            reference_number=f"REF/{i}",
            last_updated_at=f"202{i}-01-01",
            official_url=f"https://www.ema.europa.eu/{i}.pdf",
        )
        for i in range(1, 6)
    ]
    sample_db.batch_upsert_documents(docs)

    # Filter by type
    sci = sample_db.get_documents(types=["scientific-guideline"])
    assert len(sci) == 2

    # Filter by status
    adopted = sample_db.get_documents(statuses=["Adopted"])
    assert len(adopted) == 2

    # Filter by keyword
    safety_docs = sample_db.get_documents(keyword="safety")
    assert len(safety_docs) == 5

    # Filter by date
    recent = sample_db.get_documents(updated_since="2024-01-01")
    assert len(recent) == 2

    # Limit
    limited = sample_db.get_documents(limit=2)
    assert len(limited) == 2


def test_update_download_result(sample_db: Database):
    doc = EMADocument(
        ema_id="202",
        name="Test Update",
        document_type="scientific-guideline",
        official_url="https://www.ema.europa.eu/test.pdf",
    )
    sample_db.upsert_document(doc)

    sample_db.update_download_result(
        ema_id="202",
        download_status=DownloadStatus.DOWNLOADED.value,
        http_status=200,
        content_type="application/pdf",
        file_size=12345,
        sha256="abcdef1234567890",
        local_path="01_Scientific_Guidelines/test.pdf",
    )

    updated = sample_db.get_document("202")
    assert updated is not None
    assert updated.download_status == DownloadStatus.DOWNLOADED.value
    assert updated.file_size == 12345
    assert updated.sha256 == "abcdef1234567890"
    assert updated.downloaded_at is not None


def test_record_sync_history(sample_db: Database):
    summary = SyncSummary(
        timestamp="2026-09-03T12:00:00Z",
        total_records_in_feed=100,
        total_filtered=20,
        new_planned=5,
        updated_planned=2,
        downloaded_success=7,
        downloaded_failed=0,
        duration_seconds=3.14,
    )
    sample_db.record_sync_history(summary)

    counts = sample_db.get_summary_counts()
    assert "total" in counts
