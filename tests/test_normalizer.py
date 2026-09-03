"""Tests for record normalizer and safe filename generation."""

from ema_downloader.models import EMARawRecord
from ema_downloader.normalizer import (
    generate_safe_filename,
    normalize_record,
    parse_date_to_yyyymmdd,
    sanitize_filename_part,
)


def test_parse_date_to_yyyymmdd():
    assert parse_date_to_yyyymmdd("1993-10-01T01:00:00Z") == "19931001"
    assert parse_date_to_yyyymmdd("2026-09-02") == "20260902"
    assert parse_date_to_yyyymmdd(None) == "unknown_date"
    assert parse_date_to_yyyymmdd("") == "unknown_date"
    assert parse_date_to_yyyymmdd("invalid-date-string") == "unknown_date"


def test_sanitize_filename_part():
    # Removal of invalid filesystem chars
    assert sanitize_filename_part('Guideline / on "Quality" & Safety?') == "Guideline-on-Quality-and-Safety"
    # Consecutive spaces and hyphens
    assert sanitize_filename_part("Hello    World---Test") == "Hello-World-Test"
    # Windows reserved names
    assert sanitize_filename_part("CON") == "_CON"
    assert sanitize_filename_part("nul") == "_nul"
    assert sanitize_filename_part("aux") == "_aux"


def test_generate_safe_filename():
    fn = generate_safe_filename(
        last_updated_date="2026-09-02T05:00:00Z",
        reference_number="EMA/CHMP/123/2026",
        document_type="scientific-guideline",
        title="Guideline on Quality of Medicinal Products",
        ema_id="12345",
        extension=".pdf",
    )
    assert fn.startswith("20260902__EMA-CHMP-123-2026__Guideline-on-Quality")
    assert fn.endswith(".pdf")
    assert "__" in fn


def test_generate_safe_filename_fallback_no_reference():
    fn = generate_safe_filename(
        last_updated_date="2026-09-02",
        reference_number="",
        document_type="scientific-guideline",
        title="Testing Without Reference",
        ema_id="999",
        extension=".pdf",
    )
    assert fn.startswith("20260902__scientific-guideline__")


def test_normalize_record():
    raw = EMARawRecord(
        id="42",
        name="Guideline on bioanalytical method validation",
        type="scientific-guideline",
        status="Adopted",
        reference_number="EMEA/CHMP/EWP/192272/2009",
        first_published_date="2011-07-21T00:00:00Z",
        last_updated_date="2012-02-01T00:00:00Z",
        document_url="https://www.ema.europa.eu/en/documents/scientific-guideline/bioanalytical_en.pdf",
    )
    doc = normalize_record(raw)
    assert doc.ema_id == "42"
    assert doc.name == "Guideline on bioanalytical method validation"
    assert doc.document_type == "scientific-guideline"
    assert doc.file_extension == ".pdf"
    assert "20120201__EMEA-CHMP-EWP-192272-2009__" in doc.local_filename
