"""Normalizer for EMA raw records into clean, validated EMADocument instances."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from ema_downloader.models import EMADocument, EMARawRecord

# Characters not allowed in Windows / POSIX file names
INVALID_FILENAME_CHARS = re.compile(r'[\\/*?:"<>|]')
# Reserved names on Windows
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


def parse_date_to_yyyymmdd(date_str: Optional[str]) -> str:
    """Parse ISO or other date string to YYYYMMDD format.

    Falls back to 'unknown_date' if empty or unparseable.
    """
    if not date_str:
        return "unknown_date"
    date_str = date_str.strip()
    if not date_str:
        return "unknown_date"

    # Match YYYY-MM-DD prefix directly
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", date_str)
    if m:
        return f"{m.group(1)}{m.group(2)}{m.group(3)}"

    # Try common formats
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y%m%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt = datetime.strptime(date_str[:19], fmt[:19] if "%T" not in fmt else fmt)
            return dt.strftime("%Y%m%d")
        except (ValueError, TypeError):
            continue

    return "unknown_date"


def sanitize_filename_part(text: str, max_len: int = 60) -> str:
    """Sanitize a string for safe inclusion in filenames."""
    if not text:
        return ""

    # Replace ampersands with 'and'
    text = text.replace("&", " and ")

    # Replace invalid chars with hyphen
    cleaned = INVALID_FILENAME_CHARS.sub("-", text)
    # Clean dots next to hyphens (e.g. Rev.-3 -> Rev-3)
    cleaned = re.sub(r"\.-|-\.", "-", cleaned)
    # Replace whitespace and underscores with hyphens
    cleaned = re.sub(r"[\s_]+", "-", cleaned)
    # Remove consecutive hyphens
    cleaned = re.sub(r"-+", "-", cleaned)
    # Strip leading and trailing hyphens, dots, and spaces
    cleaned = cleaned.strip("- .")

    # Check Windows reserved base names
    base_upper = cleaned.upper()
    if base_upper in WINDOWS_RESERVED_NAMES:
        cleaned = f"_{cleaned}"

    # Truncate safely at word/hyphen boundary if possible
    if len(cleaned) > max_len:
        truncated = cleaned[:max_len]
        last_sep = truncated.rfind("-")
        if last_sep > max_len // 2:
            cleaned = truncated[:last_sep]
        else:
            cleaned = truncated.rstrip("- .")

    return cleaned


def extract_extension_from_url(url: str, default: str = ".pdf") -> str:
    """Extract file extension from URL, defaulting to .pdf."""
    if not url:
        return default
    parsed = urlparse(url)
    path = parsed.path.lower()
    for ext in (".pdf", ".xlsx", ".xls", ".doc", ".docx", ".zip", ".csv"):
        if path.endswith(ext):
            return ext
    return default


def generate_safe_filename(
    last_updated_date: Optional[str],
    reference_number: Optional[str],
    document_type: str,
    title: str,
    ema_id: str,
    extension: str = ".pdf"
) -> str:
    """Build a deterministic, filesystem-safe filename.

    Format:
    {last_updated_yyyymmdd}__{reference_number}__{safe_title}.pdf
    Or if no reference number:
    {last_updated_yyyymmdd}__{document_type}__{safe_title}.pdf

    Appends a short hash if title had to be heavily truncated or to ensure uniqueness.
    """
    date_part = parse_date_to_yyyymmdd(last_updated_date)
    ref_part = sanitize_filename_part(reference_number or "", max_len=30)
    type_part = sanitize_filename_part(document_type or "document", max_len=25)
    title_part = sanitize_filename_part(title or "untitled", max_len=60)

    middle_part = ref_part if ref_part else type_part
    if not middle_part:
        middle_part = "document"

    # Compute a short deterministic hash based on ema_id and title
    unique_seed = f"{ema_id}:{title}"
    short_hash = hashlib.md5(unique_seed.encode("utf-8", errors="ignore")).hexdigest()[:6]

    filename = f"{date_part}__{middle_part}__{title_part}__{short_hash}{extension}"
    return filename


def normalize_record(raw: EMARawRecord, source_dataset: str = "documents-output-json-report_en") -> EMADocument:
    """Convert an EMARawRecord to a normalized EMADocument."""
    ext = extract_extension_from_url(raw.document_url, default=".pdf")
    filename = generate_safe_filename(
        last_updated_date=raw.last_updated_date or raw.first_published_date,
        reference_number=raw.reference_number,
        document_type=raw.type,
        title=raw.name,
        ema_id=raw.id,
        extension=ext,
    )

    return EMADocument(
        ema_id=raw.id,
        name=raw.name,
        document_type=raw.type,
        status=raw.status,
        reference_number=raw.reference_number,
        medicine_name=raw.medicine_name,
        first_published_at=raw.first_published_date or None,
        last_updated_at=raw.last_updated_date or None,
        official_url=raw.document_url,
        source_dataset=source_dataset,
        local_filename=filename,
        file_extension=ext,
    )
