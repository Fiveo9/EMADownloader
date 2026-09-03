"""Data models for EMA Downloader."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class DownloadStatus(str, Enum):
    """Lifecycle status of a document download."""
    NEW = "new"
    PLANNED = "planned"
    DOWNLOADED = "downloaded"
    UPDATED = "updated"
    SKIPPED_UNCHANGED = "skipped_unchanged"
    SKIPPED_EXISTING = "skipped_existing"
    NO_DOWNLOAD_URL = "no_download_url"
    HTTP_ERROR = "http_error"
    INVALID_CONTENT = "invalid_content"
    CHECKSUM_ERROR = "checksum_error"
    WRITE_ERROR = "write_error"


@dataclass
class EMARawRecord:
    """Raw record representation as returned by EMA JSON feeds."""
    id: str
    name: str
    type: str
    medicine_name: str = ""
    ema_product_number: str = ""
    status: str = ""
    consultation_date: str = ""
    first_published_date: str = ""
    last_updated_date: str = ""
    reference_number: str = ""
    document_url: str = ""
    translations: Dict[str, Any] = field(default_factory=dict)
    extra_fields: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EMARawRecord":
        known_keys = {
            "id", "name", "type", "medicine_name", "ema_product_number",
            "status", "consultation_date", "first_published_date",
            "last_updated_date", "reference_number", "document_url",
            "translations"
        }
        extra = {k: v for k, v in data.items() if k not in known_keys}
        return cls(
            id=str(data.get("id", "")).strip(),
            name=str(data.get("name", "")).strip(),
            type=str(data.get("type", "")).strip(),
            medicine_name=str(data.get("medicine_name", "") or "").strip(),
            ema_product_number=str(data.get("ema_product_number", "") or "").strip(),
            status=str(data.get("status", "") or "").strip(),
            consultation_date=str(data.get("consultation_date", "") or "").strip(),
            first_published_date=str(data.get("first_published_date", "") or "").strip(),
            last_updated_date=str(data.get("last_updated_date", "") or "").strip(),
            reference_number=str(data.get("reference_number", "") or "").strip(),
            document_url=str(data.get("document_url", "") or "").strip(),
            translations=data.get("translations", {}) if isinstance(data.get("translations"), dict) else {},
            extra_fields=extra,
        )


@dataclass
class EMADocument:
    """Normalized document representation stored in SQLite index and exported."""
    ema_id: str
    name: str
    document_type: str
    status: str = ""
    reference_number: str = ""
    medicine_name: str = ""
    first_published_at: Optional[str] = None
    last_updated_at: Optional[str] = None
    official_url: str = ""
    source_dataset: str = "documents-output-json-report_en"
    local_path: str = ""
    local_filename: str = ""
    file_extension: str = ".pdf"
    http_status: Optional[int] = None
    content_type: str = ""
    file_size: int = 0
    sha256: str = ""
    download_status: str = DownloadStatus.NEW.value
    downloaded_at: Optional[str] = None
    last_seen_at: Optional[str] = None
    is_archived: int = 0
    category: str = ""
    sub_category: str = ""
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "EMADocument":
        return cls(
            ema_id=str(row.get("ema_id", "")),
            name=str(row.get("name", "")),
            document_type=str(row.get("document_type", "")),
            status=str(row.get("status", "") or ""),
            reference_number=str(row.get("reference_number", "") or ""),
            medicine_name=str(row.get("medicine_name", "") or ""),
            first_published_at=row.get("first_published_at"),
            last_updated_at=row.get("last_updated_at"),
            official_url=str(row.get("official_url", "") or ""),
            source_dataset=str(row.get("source_dataset", "") or "documents-output-json-report_en"),
            local_path=str(row.get("local_path", "") or ""),
            local_filename=str(row.get("local_filename", "") or ""),
            file_extension=str(row.get("file_extension", "") or ".pdf"),
            http_status=int(row["http_status"]) if row.get("http_status") is not None else None,
            content_type=str(row.get("content_type", "") or ""),
            file_size=int(row.get("file_size") or 0),
            sha256=str(row.get("sha256", "") or ""),
            download_status=str(row.get("download_status", DownloadStatus.NEW.value)),
            downloaded_at=row.get("downloaded_at"),
            last_seen_at=row.get("last_seen_at"),
            is_archived=int(row.get("is_archived") or 0),
            category=str(row.get("category", "") or ""),
            sub_category=str(row.get("sub_category", "") or ""),
            error_message=str(row.get("error_message", "") or ""),
        )


@dataclass
class ClassificationRule:
    """Rule for mapping keywords to domain folder."""
    priority: int
    field: str
    keywords: List[str]
    folder: str

    def matches(self, text: str) -> bool:
        """Check if any keyword is present in text."""
        lowered = text.lower()
        for kw in self.keywords:
            if kw and kw in lowered:
                return True
        return False


@dataclass
class SyncSummary:
    """Execution summary statistics for a sync operation."""
    timestamp: str
    total_records_in_feed: int = 0
    total_filtered: int = 0
    new_planned: int = 0
    updated_planned: int = 0
    skipped_unchanged: int = 0
    downloaded_success: int = 0
    downloaded_failed: int = 0
    total_bytes: int = 0
    dry_run: bool = False
    duration_seconds: float = 0.0
    failures: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
