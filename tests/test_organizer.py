"""Tests for document classification and folder hierarchy organization."""

from ema_downloader.models import EMADocument
from ema_downloader.organizer import classify_document, compute_relative_path


def test_classify_scientific_guidelines(sample_rules):
    # Quality guideline
    doc_qual = EMADocument(
        ema_id="1",
        name="Guideline on manufacture and stability testing of drug substances",
        document_type="scientific-guideline",
        reference_number="EMA/CHMP/QWP/123",
        official_url="https://www.ema.europa.eu/en/documents/scientific-guideline/stability_en.pdf",
        local_filename="20260101__test.pdf",
    )
    top, sub, cat = classify_document(doc_qual, sample_rules)
    assert top == "01_Scientific_Guidelines"
    assert sub == "01_Quality"
    assert cat == "Quality"

    # ICH guideline
    doc_ich = EMADocument(
        ema_id="2",
        name="ICH guideline Q3A(R2) Impurities in new drug substances",
        document_type="scientific-guideline",
        reference_number="EMA/CHMP/ICH/422/2002",
        official_url="https://www.ema.europa.eu/en/documents/scientific-guideline/ich-q3a_en.pdf",
        local_filename="20260101__ich.pdf",
    )
    top, sub, cat = classify_document(doc_ich, sample_rules)
    assert top == "01_Scientific_Guidelines"
    # Q3A should match ICH or Quality based on priority (Quality is 10, ICH is 60)
    assert top == "01_Scientific_Guidelines"
    assert sub in ("01_Quality", "06_ICH")

    # Nonclinical
    doc_nonclin = EMADocument(
        ema_id="3",
        name="Guideline on repeated dose toxicity",
        document_type="scientific-guideline",
        reference_number="EMA/CHMP/SWP/1042/1999",
        official_url="https://www.ema.europa.eu/en/documents/scientific-guideline/toxicology_en.pdf",
        local_filename="20260101__tox.pdf",
    )
    top, sub, cat = classify_document(doc_nonclin, sample_rules)
    assert top == "01_Scientific_Guidelines"
    assert sub == "02_Nonclinical"
    assert cat == "Nonclinical"


def test_classify_regulatory_procedural():
    doc_reg = EMADocument(
        ema_id="4",
        name="Procedural advice on post-authorisation measures",
        document_type="regulatory-procedural-guideline",
        reference_number="EMA/9876",
        official_url="https://www.ema.europa.eu/en/documents/regulatory-procedural-guideline/pam_en.pdf",
        local_filename="20260101__reg.pdf",
    )
    top, sub, cat = classify_document(doc_reg)
    assert top == "02_Regulatory_Procedural_Guidelines"
    assert sub == ""


def test_compute_relative_path(sample_rules):
    doc = EMADocument(
        ema_id="5",
        name="Guideline on clinical safety and efficacy of vaccines",
        document_type="scientific-guideline",
        reference_number="EMA/CHMP/VWP/123",
        official_url="https://www.ema.europa.eu/en/documents/scientific-guideline/vaccines_en.pdf",
        local_filename="20260101__EMA-CHMP-VWP-123__vaccines.pdf",
    )
    rel_path = compute_relative_path(doc, sample_rules)
    # Check that the path begins with 01_Scientific_Guidelines
    assert rel_path.startswith("01_Scientific_Guidelines/")
    assert rel_path.endswith("20260101__EMA-CHMP-VWP-123__vaccines.pdf")
    assert doc.local_path == rel_path
