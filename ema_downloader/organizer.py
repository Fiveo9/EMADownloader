"""Document classification and local directory organizer."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urlparse

from ema_downloader.models import ClassificationRule, EMADocument

logger = logging.getLogger(__name__)

# Level 1 mapping from document type to top-level folder.
# medicine-qa is the current EMA slug for Q&A documents (the old "q-and-a"
# identifier no longer exists in the feed); reflection/position/concept papers
# are published as scientific-guideline, so they share 01's level-2 rules.
DOCUMENT_TYPE_FOLDERS = {
    "scientific-guideline": "01_Scientific_Guidelines",
    "regulatory-procedural-guideline": "02_Regulatory_Procedural_Guidelines",
    "medicine-qa": "03_QA_Public_Statements",
    "public-statement": "03_QA_Public_Statements",
}

DEFAULT_TOP_FOLDER = "04_Other_Documents"
UNCATEGORIZED_FOLDER = "99_Uncategorized"


def load_classification_rules(rules_path: Optional[Path | str] = None) -> List[ClassificationRule]:
    """Load classification rules from a CSV file."""
    if not rules_path:
        return []

    p = Path(rules_path)
    if not p.exists():
        logger.warning("Classification rules file not found: %s", p)
        return []

    rules: List[ClassificationRule] = []
    with open(p, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                priority = int(row.get("Priority", 999))
                field_name = str(row.get("Field", "")).strip()
                raw_keywords = str(row.get("Keywords", "")).strip()
                folder = str(row.get("Folder", "")).strip()
                keywords = [k.strip().lower() for k in raw_keywords.split(";") if k.strip()]

                rules.append(
                    ClassificationRule(
                        priority=priority,
                        field=field_name,
                        keywords=keywords,
                        folder=folder,
                    )
                )
            except Exception as e:
                logger.warning("Error parsing classification rule row %s: %s", row, e)

    # Sort by priority ascending (10 before 20, etc.)
    rules.sort(key=lambda r: r.priority)
    return rules


def match_field_or_url(text: str, rule: ClassificationRule) -> bool:
    """Check whether any rule keyword matches text."""
    return rule.matches(text)


def classify_document(
    doc: EMADocument,
    rules: Optional[List[ClassificationRule]] = None,
) -> Tuple[str, str, str]:
    """Determine top-level folder, sub-folder, and category name for a document.

    Returns:
        (top_folder, sub_folder, category_name)
    """
    doc_type = (doc.document_type or "").lower().strip()
    top_folder = DOCUMENT_TYPE_FOLDERS.get(doc_type, DEFAULT_TOP_FOLDER)

    # Only apply level-2 subject domain rules to scientific guidelines (or uncategorized)
    if doc_type == "scientific-guideline" and rules:
        url_path = urlparse(doc.official_url).path.lower()
        ref_num = (doc.reference_number or "").lower()
        title = (doc.name or "").lower()

        # Step 1: Check reference number and URL path (higher specificity)
        for rule in rules:
            if match_field_or_url(ref_num, rule) or match_field_or_url(url_path, rule):
                return top_folder, rule.folder, rule.field

        # Step 2: Check title keywords (fallback)
        for rule in rules:
            if match_field_or_url(title, rule):
                return top_folder, rule.folder, rule.field

        # Unmatched scientific guideline
        return top_folder, UNCATEGORIZED_FOLDER, "Uncategorized"

    # For other document types, return empty subfolder
    clean_type_label = doc_type.replace("-", " ").title()
    return top_folder, "", clean_type_label


def compute_relative_path(
    doc: EMADocument,
    rules: Optional[List[ClassificationRule]] = None,
) -> str:
    """Compute relative file path from library root.

    Example:
    01_Scientific_Guidelines/01_Quality/20260902__EMA-CHMP-123456__Title__a1b2c3.pdf
    """
    top_folder, sub_folder, category = classify_document(doc, rules)
    doc.category = category
    doc.sub_category = sub_folder

    if sub_folder:
        rel_path = f"{top_folder}/{sub_folder}/{doc.local_filename}"
    else:
        rel_path = f"{top_folder}/{doc.local_filename}"

    doc.local_path = rel_path
    return rel_path
