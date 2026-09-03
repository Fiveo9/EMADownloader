"""Tests for CLI subcommands execution."""

import json
from pathlib import Path
from unittest.mock import patch
import pytest

from ema_downloader.cli import build_parser, main


def test_cli_parser_help():
    parser = build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--help"])
    assert exc.value.code == 0


def test_cli_sync_dry_run(temp_library_dir: Path, sample_documents_json_path: Path):
    # Set up raw snapshot
    raw_dir = temp_library_dir / "90_Raw_JSON"
    raw_dir.mkdir(parents=True, exist_ok=True)
    today_str = "20260903"
    snapshot = raw_dir / f"documents-output-json-report_en_{today_str}.json"

    with open(sample_documents_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    with open(snapshot, "w", encoding="utf-8") as f:
        json.dump(data, f)

    test_args = [
        "ema-downloader",
        "sync",
        "--library-dir", str(temp_library_dir),
        "--dry-run",
        "--cached",
        "--limit", "3",
    ]

    with patch("sys.argv", test_args):
        code = main()
        assert code == 0

    # Verify that index files were generated
    assert (temp_library_dir / "00_Index" / "ema_documents.sqlite3").exists()
    assert (temp_library_dir / "00_Index" / "EMA_Document_Index.xlsx").exists()
    assert (temp_library_dir / "00_Index" / "EMA_Document_Index.csv").exists()


def test_cli_export_command(temp_library_dir: Path, sample_db):
    test_args = [
        "ema-downloader",
        "export",
        "--library-dir", str(temp_library_dir),
        "--format", "csv",
    ]

    with patch("sys.argv", test_args):
        code = main()
        assert code == 0

    assert (temp_library_dir / "00_Index" / "EMA_Document_Index.csv").exists()


def test_cli_verify_command(temp_library_dir: Path, sample_db):
    test_args = [
        "ema-downloader",
        "verify",
        "--library-dir", str(temp_library_dir),
    ]

    with patch("sys.argv", test_args):
        code = main()
        assert code == 0
