"""Command-line interface (CLI) for EMA Downloader."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from tqdm import tqdm

from ema_downloader import __version__
from ema_downloader.config import AppConfig, load_config
from ema_downloader.database import Database
from ema_downloader.downloader import Downloader
from ema_downloader.ema_source import EMASource
from ema_downloader.exporter import Exporter
from ema_downloader.models import (
    ClassificationRule,
    DownloadStatus,
    EMADocument,
    SyncSummary,
)
from ema_downloader.normalizer import normalize_record
from ema_downloader.organizer import (
    compute_relative_path,
    load_classification_rules,
)
from ema_downloader.reporting import print_terminal_summary, save_sync_report

logger = logging.getLogger("ema_downloader")


def setup_logging(verbose: bool = False) -> None:
    """Configure log level and console formatting."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def filter_raw_records(
    records: list,
    types: Optional[List[str]] = None,
    statuses: Optional[List[str]] = None,
    keyword: Optional[str] = None,
    updated_since: Optional[str] = None,
    limit: Optional[int] = None,
) -> list:
    """Filter raw records based on CLI arguments."""
    filtered = []
    types_set = {t.lower() for t in types} if types else None
    statuses_set = {s.lower() for s in statuses} if statuses else None
    kw_lower = keyword.lower() if keyword else None

    for r in records:
        if types_set and r.type.lower() not in types_set:
            continue
        if statuses_set and r.status.lower() not in statuses_set:
            continue
        if kw_lower:
            text = f"{r.name} {r.reference_number} {r.medicine_name}".lower()
            if kw_lower not in text:
                continue
        if updated_since:
            doc_date = r.last_updated_date or r.first_published_date or ""
            if doc_date < updated_since:
                continue

        filtered.append(r)
        if limit and len(filtered) >= limit:
            break

    return filtered


def prepare_documents(
    raw_records: list,
    rules: List[ClassificationRule],
    source_dataset: str = "documents-output-json-report_en",
) -> List[EMADocument]:
    """Normalize raw records and compute their classified relative paths."""
    docs = []
    for raw in raw_records:
        doc = normalize_record(raw, source_dataset=source_dataset)
        compute_relative_path(doc, rules)
        docs.append(doc)
    return docs


def handle_sync(args: argparse.Namespace) -> int:
    """Execute full sync or dry-run."""
    start_time = time.time()
    config = load_config(
        config_path=args.config,
        library_dir=args.library_dir,
        workers=args.workers,
        proxy=args.proxy,
        types=args.types,
        status=args.status,
    )
    config.ensure_directories()
    setup_logging(args.verbose)

    db = Database(config.storage.database_path)
    rules = load_classification_rules(config.classification.rules_file)
    source = EMASource(config)
    downloader = Downloader(config, db)
    exporter = Exporter(config, db)

    logger.info("Starting sync (dry_run=%s) ...", args.dry_run)
    meta, raw_records, _ = source.fetch_documents_report(use_cached=args.cached)

    types = args.types or config.filters.default_types
    statuses = args.status or config.filters.default_status

    filtered_raw = filter_raw_records(
        raw_records,
        types=types,
        statuses=statuses,
        keyword=args.keyword,
        updated_since=args.updated_since,
        limit=args.limit,
    )

    logger.info("Selected %d documents matching filters", len(filtered_raw))
    docs = prepare_documents(filtered_raw, rules)

    # Batch upsert metadata into database
    db.batch_upsert_documents(docs)

    # Incremental planning
    planned_items: List[Tuple[EMADocument, str]] = []
    new_planned = 0
    updated_planned = 0
    skipped_unchanged = 0

    for doc in docs:
        action, reason = downloader.plan_document(doc)
        if action == "new":
            planned_items.append((doc, action))
            new_planned += 1
        elif action == "updated":
            planned_items.append((doc, action))
            updated_planned += 1
        elif action == "skip":
            skipped_unchanged += 1
            existing = db.get_document(doc.ema_id)
            if not existing or existing.download_status not in (DownloadStatus.DOWNLOADED.value, DownloadStatus.UPDATED.value):
                db.update_download_result(
                    ema_id=doc.ema_id,
                    download_status=DownloadStatus.SKIPPED_UNCHANGED.value,
                )

    logger.info(
        "Incremental check: %d new, %d updated, %d unchanged",
        new_planned,
        updated_planned,
        skipped_unchanged,
    )

    downloaded_success = 0
    downloaded_failed = 0
    total_bytes = 0
    failures = []

    if not args.dry_run and planned_items:
        logger.info("Downloading %d files with %d workers ...", len(planned_items), config.network.workers)
        with tqdm(total=len(planned_items), desc="Downloading", unit="file") as pbar:
            def on_progress(res):
                nonlocal downloaded_success, downloaded_failed, total_bytes
                pbar.update(1)
                if res.success:
                    downloaded_success += 1
                    total_bytes += res.file_size
                else:
                    downloaded_failed += 1
                    failures.append({
                        "ema_id": res.doc.ema_id,
                        "name": res.doc.name,
                        "error": res.error_message,
                    })

            downloader.download_batch(planned_items, progress_callback=on_progress)

    duration = time.time() - start_time
    summary = SyncSummary(
        timestamp=datetime.now(timezone.utc).isoformat(),
        total_records_in_feed=len(raw_records),
        total_filtered=len(filtered_raw),
        new_planned=new_planned,
        updated_planned=updated_planned,
        skipped_unchanged=skipped_unchanged,
        downloaded_success=downloaded_success,
        downloaded_failed=downloaded_failed,
        total_bytes=total_bytes,
        dry_run=args.dry_run,
        duration_seconds=duration,
        failures=failures,
    )

    db.record_sync_history(summary)
    save_sync_report(summary, config)

    # Export index files
    exporter.export_all(summary=summary)

    # Print terminal presentation
    print_terminal_summary(summary)
    return 0


def handle_metadata(args: argparse.Namespace) -> int:
    """Fetch official JSON and index documents into SQLite without downloading files."""
    config = load_config(
        config_path=args.config,
        library_dir=args.library_dir,
        types=args.types,
        status=args.status,
    )
    config.ensure_directories()
    setup_logging(args.verbose)

    db = Database(config.storage.database_path)
    rules = load_classification_rules(config.classification.rules_file)
    source = EMASource(config)
    exporter = Exporter(config, db)

    logger.info("Fetching documents metadata feed...")
    meta, raw_records, _ = source.fetch_documents_report(use_cached=args.cached)

    types = args.types or config.filters.default_types
    statuses = args.status or config.filters.default_status

    filtered_raw = filter_raw_records(
        raw_records,
        types=types,
        statuses=statuses,
        keyword=args.keyword,
        updated_since=args.updated_since,
        limit=args.limit,
    )

    logger.info("Processing metadata for %d documents...", len(filtered_raw))
    docs = prepare_documents(filtered_raw, rules)
    db.batch_upsert_documents(docs)

    # Optionally fetch general feed
    if args.include_general:
        logger.info("Fetching general guidance feed...")
        try:
            _, gen_records, _ = source.fetch_general_report(use_cached=args.cached)
            gen_docs = prepare_documents(gen_records, rules, source_dataset="general-json-report_en")
            db.batch_upsert_documents(gen_docs)
            logger.info("Indexed %d general guidance items", len(gen_docs))
        except Exception as e:
            logger.warning("Failed to index general guidance report: %s", e)

    exporter.export_all()
    logger.info("Metadata indexing complete! Total documents in database: %d", db.get_summary_counts().get("total", 0))
    return 0


def handle_download(args: argparse.Namespace) -> int:
    """Download documents that are planned, new, or previously failed."""
    config = load_config(
        config_path=args.config,
        library_dir=args.library_dir,
        workers=args.workers,
        proxy=args.proxy,
    )
    config.ensure_directories()
    setup_logging(args.verbose)

    db = Database(config.storage.database_path)
    downloader = Downloader(config, db)
    exporter = Exporter(config, db)

    # Query candidate documents
    statuses = [
        DownloadStatus.NEW.value,
        DownloadStatus.PLANNED.value,
        DownloadStatus.HTTP_ERROR.value,
        DownloadStatus.WRITE_ERROR.value,
    ]
    docs = db.get_documents(
        types=args.types,
        download_statuses=statuses,
        limit=args.limit,
    )

    if not docs:
        logger.info("No pending documents to download.")
        return 0

    planned_items: List[Tuple[EMADocument, str]] = []
    for doc in docs:
        action, reason = downloader.plan_document(doc)
        if action in ("new", "updated"):
            planned_items.append((doc, action))

    if not planned_items:
        logger.info("All selected documents are already up to date on disk.")
        return 0

    logger.info("Downloading %d pending documents ...", len(planned_items))
    with tqdm(total=len(planned_items), desc="Downloading", unit="file") as pbar:
        downloader.download_batch(planned_items, progress_callback=lambda _: pbar.update(1))

    exporter.export_all()
    logger.info("Download run finished.")
    return 0


def handle_organize(args: argparse.Namespace) -> int:
    """Reorganize existing files based on updated classification rules."""
    config = load_config(config_path=args.config, library_dir=args.library_dir)
    setup_logging(args.verbose)

    db = Database(config.storage.database_path)
    rules = load_classification_rules(config.classification.rules_file)
    exporter = Exporter(config, db)

    docs = db.get_documents()
    moved_count = 0

    for doc in docs:
        old_path = doc.local_path
        compute_relative_path(doc, rules)
        new_path = doc.local_path

        if old_path and new_path and old_path != new_path:
            old_file = config.storage.library_dir / old_path
            new_file = config.storage.library_dir / new_path

            if old_file.exists():
                new_file.parent.mkdir(parents=True, exist_ok=True)
                os.replace(old_file, new_file)
                moved_count += 1
                logger.debug("Moved: %s -> %s", old_path, new_path)

        # Update category and path in database
        db.upsert_document(doc)

    exporter.export_all()
    logger.info("Reorganization finished! Moved %d files, updated %d index records.", moved_count, len(docs))
    return 0


def handle_export(args: argparse.Namespace) -> int:
    """Export database index to Excel and/or CSV."""
    config = load_config(config_path=args.config, library_dir=args.library_dir)
    setup_logging(args.verbose)

    db = Database(config.storage.database_path)
    exporter = Exporter(config, db)

    fmt = (args.format or "all").lower()
    if fmt == "xlsx":
        out = exporter.export_excel(output_path=Path(args.output) if args.output else None)
        print(f"Excel exported to: {out}")
    elif fmt == "csv":
        out = exporter.export_csv(output_path=Path(args.output) if args.output else None)
        print(f"CSV exported to: {out}")
    else:
        results = exporter.export_all()
        for k, v in results.items():
            print(f"Exported {k}: {v}")
    return 0


def handle_verify(args: argparse.Namespace) -> int:
    """Verify local file integrity against database records."""
    config = load_config(config_path=args.config, library_dir=args.library_dir)
    setup_logging(args.verbose)

    db = Database(config.storage.database_path)
    downloader = Downloader(config, db)

    logger.info("Verifying library integrity at %s ...", config.storage.library_dir)
    issues = downloader.verify_library()

    if not issues:
        print("\nAll downloaded files passed integrity checks (Existence, Size, %PDF- Header, SHA-256)!\n")
        return 0

    print(f"\nFound {len(issues)} integrity issue(s):")
    for iss in issues:
        print(f"  - [{iss['ema_id']}] {iss['name'][:40]}: {iss['issue']} ({iss['local_path']})")
    print()
    return 1


def build_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="ema-downloader",
        description="EMA Regulatory Document Downloader & Organizer - Tool for downloading and maintaining EMA scientific guidelines and regulatory documents.",
    )
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Common options helper
    def add_common_options(p):
        p.add_argument("--config", type=str, help="Path to custom settings.toml")
        p.add_argument("--library-dir", type=str, help="Root directory for downloaded library")
        p.add_argument("--verbose", action="store_true", help="Enable verbose debug logging")

    # Command: sync
    sync_p = subparsers.add_parser("sync", help="Synchronize EMA documents (fetch, index, download, organize, export)")
    add_common_options(sync_p)
    sync_p.add_argument("--types", nargs="+", help="Filter by document type (e.g. scientific-guideline)")
    sync_p.add_argument("--status", nargs="+", help="Filter by document status (e.g. Adopted, Draft)")
    sync_p.add_argument("--updated-since", type=str, help="Filter documents updated on or after YYYY-MM-DD")
    sync_p.add_argument("--keyword", type=str, help="Search term in title or reference number")
    sync_p.add_argument("--limit", type=int, help="Maximum number of documents to process")
    sync_p.add_argument("--workers", type=int, help="Number of concurrent download workers")
    sync_p.add_argument("--proxy", type=str, help="HTTP/SOCKS proxy URL")
    sync_p.add_argument("--dry-run", action="store_true", help="Preview planned downloads without saving files")
    sync_p.add_argument("--cached", action="store_true", help="Use locally cached raw JSON snapshot if available")
    sync_p.set_defaults(func=handle_sync)

    # Command: metadata
    meta_p = subparsers.add_parser("metadata", help="Fetch and index EMA JSON metadata without downloading files")
    add_common_options(meta_p)
    meta_p.add_argument("--types", nargs="+", help="Filter document types to index")
    meta_p.add_argument("--status", nargs="+", help="Filter by document status")
    meta_p.add_argument("--updated-since", type=str, help="Filter documents updated on or after YYYY-MM-DD")
    meta_p.add_argument("--keyword", type=str, help="Search term in title or reference number")
    meta_p.add_argument("--limit", type=int, help="Maximum records to index")
    meta_p.add_argument("--cached", action="store_true", help="Use locally cached raw JSON snapshot")
    meta_p.add_argument("--include-general", action="store_true", help="Also fetch and index general-json-report_en")
    meta_p.set_defaults(func=handle_metadata)

    # Command: download
    dl_p = subparsers.add_parser("download", help="Download pending or failed documents from local index")
    add_common_options(dl_p)
    dl_p.add_argument("--types", nargs="+", help="Filter document types")
    dl_p.add_argument("--limit", type=int, help="Maximum files to download")
    dl_p.add_argument("--workers", type=int, help="Number of concurrent download workers")
    dl_p.add_argument("--proxy", type=str, help="Proxy URL")
    dl_p.set_defaults(func=handle_download)

    # Command: organize
    org_p = subparsers.add_parser("organize", help="Reorganize downloaded files according to classification rules")
    add_common_options(org_p)
    org_p.set_defaults(func=handle_organize)

    # Command: export
    exp_p = subparsers.add_parser("export", help="Export index to Excel or CSV")
    add_common_options(exp_p)
    exp_p.add_argument("--format", choices=["xlsx", "csv", "all"], default="all", help="Export format")
    exp_p.add_argument("--output", type=str, help="Custom output file path")
    exp_p.set_defaults(func=handle_export)

    # Command: verify
    ver_p = subparsers.add_parser("verify", help="Verify integrity of local downloaded files")
    add_common_options(ver_p)
    ver_p.set_defaults(func=handle_verify)

    return parser


def main() -> int:
    """CLI application entrypoint."""
    parser = build_parser()
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        return 1

    args = parser.parse_args()
    if hasattr(args, "func"):
        return args.func(args)
    parser.print_help(sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
