"""Sync reporting and terminal summary presentation."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ema_downloader.config import AppConfig
from ema_downloader.models import SyncSummary

logger = logging.getLogger(__name__)


def save_sync_report(summary: SyncSummary, config: AppConfig) -> Path:
    """Save execution summary to JSON report in the index directory."""
    timestamp_safe = summary.timestamp.replace(":", "").replace("-", "")[:15]
    report_filename = f"sync_report_{timestamp_safe}.json"
    report_path = config.storage.full_index_dir / report_filename

    config.storage.full_index_dir.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary.to_dict(), f, indent=2, ensure_ascii=False)

    logger.info("Saved sync report to %s", report_path)
    return report_path


def format_bytes(size: int) -> str:
    """Format bytes into human-readable representation."""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.2f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.2f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.2f} GB"


def print_terminal_summary(summary: SyncSummary) -> None:
    """Print an attractive, clean ASCII summary table in the terminal."""
    border = "=" * 64
    sub_border = "-" * 64

    mode_label = "DRY-RUN PREVIEW (No files downloaded)" if summary.dry_run else "LIVE SYNC COMPLETED"

    lines = [
        border,
        f"  EMA Downloader - {mode_label}",
        border,
        f"  Timestamp:         {summary.timestamp}",
        f"  Execution Time:    {summary.duration_seconds:.2f} seconds",
        sub_border,
        f"  Feed Total:        {summary.total_records_in_feed:,} records found",
        f"  Matching Filter:   {summary.total_filtered:,} records selected",
        sub_border,
        f"  New Documents:     {summary.new_planned:,} planned",
        f"  Updated Documents: {summary.updated_planned:,} planned",
        f"  Skipped Documents: {summary.skipped_unchanged:,} unchanged",
        sub_border,
    ]

    if not summary.dry_run:
        lines.extend([
            f"  Downloaded:        {summary.downloaded_success:,} successful",
            f"  Failed:            {summary.downloaded_failed:,} errors",
            f"  Data Transferred:  {format_bytes(summary.total_bytes)}",
            sub_border,
        ])

    if summary.failures:
        lines.append(f"  Failures in this run ({len(summary.failures)}):")
        for fail in summary.failures[:5]:
            lines.append(f"    - [{fail.get('ema_id')}] {fail.get('name', '')[:40]}: {fail.get('error')}")
        if len(summary.failures) > 5:
            lines.append(f"    ... and {len(summary.failures) - 5} more (see download_failures.csv)")
        lines.append(sub_border)

    lines.append(border)
    print("\n" + "\n".join(lines) + "\n")
