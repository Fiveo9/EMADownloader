"""Tests for configuration loading and validation."""

from pathlib import Path
from ema_downloader.config import AppConfig, load_config


def test_default_config_properties(temp_library_dir: Path):
    cfg = load_config(library_dir=str(temp_library_dir))
    assert cfg.storage.library_dir == temp_library_dir
    assert cfg.storage.database_path == temp_library_dir / "00_Index" / "ema_documents.sqlite3"
    assert cfg.storage.excel_path == temp_library_dir / "00_Index" / "EMA_Document_Index.xlsx"
    assert cfg.storage.csv_path == temp_library_dir / "00_Index" / "EMA_Document_Index.csv"
    assert cfg.storage.failures_csv_path == temp_library_dir / "99_Failed_Downloads" / "download_failures.csv"


def test_config_overrides(temp_library_dir: Path):
    cfg = load_config(
        library_dir=str(temp_library_dir),
        workers=8,
        timeout=45.0,
        types=["scientific-guideline"],
        status=["Adopted"],
    )
    assert cfg.network.workers == 8
    assert cfg.network.timeout == 45.0
    assert cfg.filters.default_types == ["scientific-guideline"]
    assert cfg.filters.default_status == ["Adopted"]


def test_ensure_directories(sample_config: AppConfig):
    sample_config.ensure_directories()
    assert sample_config.storage.full_index_dir.exists()
    assert sample_config.storage.full_raw_json_dir.exists()
    assert sample_config.storage.full_failed_downloads_dir.exists()


def test_local_toml_overrides_base(tmp_path: Path):
    base = tmp_path / "settings.toml"
    base.write_text('[network]\nworkers = 2\nproxy = ""\n', encoding="utf-8")
    local = tmp_path / "settings.local.toml"
    local.write_text('[network]\nproxy = "http://127.0.0.1:7890"\n', encoding="utf-8")

    cfg = load_config(config_path=base)
    assert cfg.network.workers == 2
    assert cfg.network.proxy == "http://127.0.0.1:7890"
