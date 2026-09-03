"""Tests for EMA data source and snapshot caching."""

import json
from pathlib import Path
from ema_downloader.config import AppConfig
from ema_downloader.ema_source import EMASource


def test_fetch_feed_from_cached(sample_config: AppConfig, sample_documents_json_path: Path):
    source = EMASource(sample_config)
    snapshot_filename = source._get_snapshot_filename("documents-output-json-report_en")
    target_snapshot = sample_config.storage.full_raw_json_dir / snapshot_filename

    # Copy fixture to target snapshot path
    with open(sample_documents_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    with open(target_snapshot, "w", encoding="utf-8") as f:
        json.dump(data, f)

    meta, records, path = source.fetch_documents_report(use_cached=True)
    assert len(records) == 5
    assert records[0].id == "2406"
    assert records[0].type == "scientific-guideline"
    assert meta.get("total_records") == 5
    assert path == target_snapshot
