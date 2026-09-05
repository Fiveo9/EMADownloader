"""Pytest fixtures for EMA Downloader test suite."""

from pathlib import Path
import pytest

from ema_downloader.config import AppConfig, ClassificationConfig, FilterConfig, NetworkConfig, SourceConfig, StorageConfig
from ema_downloader.database import Database
from ema_downloader.models import ClassificationRule
from ema_downloader.organizer import load_classification_rules


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_documents_json_path(fixtures_dir: Path) -> Path:
    return fixtures_dir / "sample_documents_report.json"


@pytest.fixture
def sample_general_json_path(fixtures_dir: Path) -> Path:
    return fixtures_dir / "sample_general_report.json"


@pytest.fixture
def temp_library_dir(tmp_path: Path) -> Path:
    lib_dir = tmp_path / "EMA_Regulatory_Library"
    lib_dir.mkdir(parents=True, exist_ok=True)
    return lib_dir


@pytest.fixture
def sample_config(temp_library_dir: Path) -> AppConfig:
    storage = StorageConfig(library_dir=temp_library_dir)
    cfg = AppConfig(
        sources=SourceConfig(),
        storage=storage,
        network=NetworkConfig(timeout=5.0, max_retries=1, workers=2),
        filters=FilterConfig(),
        classification=ClassificationConfig(
            rules_file=Path(__file__).resolve().parent.parent / "config" / "classification_rules.csv"
        ),
    )
    cfg.ensure_directories()
    return cfg


@pytest.fixture
def sample_db(sample_config: AppConfig) -> Database:
    return Database(sample_config.storage.database_path)


@pytest.fixture
def sample_rules(sample_config: AppConfig) -> list[ClassificationRule]:
    return load_classification_rules(sample_config.classification.rules_file)
