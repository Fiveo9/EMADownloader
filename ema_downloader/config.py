"""Configuration loader and schema for EMA Downloader."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

if sys.version_info >= (3, 11):
    import tomllib
else:  # Python 3.10: tomllib 是 tomli 的内置版，接口一致
    import tomli as tomllib


@dataclass
class SourceConfig:
    """EMA remote data sources."""
    documents_url: str = "https://www.ema.europa.eu/en/documents/report/documents-output-json-report_en.json"
    general_url: str = "https://www.ema.europa.eu/en/documents/report/general-json-report_en.json"


@dataclass
class StorageConfig:
    """Storage directories and filenames."""
    library_dir: Path = Path("EMA_Regulatory_Library")
    index_dir: str = "00_Index"
    raw_json_dir: str = "90_Raw_JSON"
    failed_downloads_dir: str = "99_Failed_Downloads"
    database_name: str = "ema_documents.sqlite3"
    excel_name: str = "EMA_Document_Index.xlsx"
    csv_name: str = "EMA_Document_Index.csv"

    @property
    def full_index_dir(self) -> Path:
        return self.library_dir / self.index_dir

    @property
    def full_raw_json_dir(self) -> Path:
        return self.library_dir / self.raw_json_dir

    @property
    def full_failed_downloads_dir(self) -> Path:
        return self.library_dir / self.failed_downloads_dir

    @property
    def database_path(self) -> Path:
        return self.full_index_dir / self.database_name

    @property
    def excel_path(self) -> Path:
        return self.full_index_dir / self.excel_name

    @property
    def csv_path(self) -> Path:
        return self.full_index_dir / self.csv_name

    @property
    def failures_csv_path(self) -> Path:
        return self.full_failed_downloads_dir / "download_failures.csv"

    @property
    def manifest_csv_path(self) -> Path:
        return self.full_failed_downloads_dir / "download_manifest.csv"


@dataclass
class NetworkConfig:
    """Network connection parameters."""
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 1.0
    workers: int = 3
    proxy: str = ""
    chunk_size: int = 1048576  # 1MB
    request_delay: float = 2.0  # Delay after successful download to avoid rate limiting

    def get_effective_proxy(self) -> Optional[str]:
        """Return proxy from config, environment variables, or auto-detect local proxy."""
        if self.proxy:
            return self.proxy
        # Check standard environment variables
        env_proxy = (
            os.environ.get("ALL_PROXY")
            or os.environ.get("HTTPS_PROXY")
            or os.environ.get("HTTP_PROXY")
            or os.environ.get("https_proxy")
            or os.environ.get("http_proxy")
        )
        if env_proxy:
            return env_proxy

        # Check if local Clash / V2Ray proxy (127.0.0.1:7890) is reachable
        try:
            import socket
            with socket.create_connection(("127.0.0.1", 7890), timeout=0.1):
                return "http://127.0.0.1:7890"
        except (OSError, TimeoutError):
            pass

        return None


@dataclass
class FilterConfig:
    """Default filtering options."""
    default_types: List[str] = field(
        default_factory=lambda: [
            "scientific-guideline",
            "regulatory-procedural-guideline",
        ]
    )
    default_status: List[str] = field(default_factory=list)
    default_languages: List[str] = field(default_factory=lambda: ["en"])


@dataclass
class ClassificationConfig:
    """Classification rules configuration."""
    rules_file: Path = Path("config/classification_rules.csv")


@dataclass
class AppConfig:
    """Root configuration object."""
    sources: SourceConfig = field(default_factory=SourceConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    filters: FilterConfig = field(default_factory=FilterConfig)
    classification: ClassificationConfig = field(default_factory=ClassificationConfig)

    def ensure_directories(self) -> None:
        """Create standard library directory structure."""
        self.storage.full_index_dir.mkdir(parents=True, exist_ok=True)
        self.storage.full_raw_json_dir.mkdir(parents=True, exist_ok=True)
        self.storage.full_failed_downloads_dir.mkdir(parents=True, exist_ok=True)


def find_default_config_path() -> Optional[Path]:
    """Search for settings.toml in standard locations."""
    env_cfg = os.environ.get("EMA_CONFIG")
    if env_cfg:
        p = Path(env_cfg)
        if p.exists():
            return p

    candidates = [
        Path.cwd() / "config" / "settings.toml",
        Path.cwd() / "settings.toml",
        Path(__file__).resolve().parent.parent / "config" / "settings.toml",
    ]
    if getattr(sys, "frozen", False):
        # Standalone exe build: prefer the config shipped next to the executable.
        candidates.insert(0, Path(sys.executable).parent / "config" / "settings.toml")
    for c in candidates:
        if c.exists():
            return c
    return None


def _load_toml(path: Path) -> dict[str, Any]:
    with open(path, "rb") as f:
        return tomllib.load(f)


def load_config(config_path: Optional[Path | str] = None, **overrides: Any) -> AppConfig:
    """Load configuration from file and merge with runtime overrides."""
    path = Path(config_path) if config_path else find_default_config_path()
    data: dict[str, Any] = {}

    if path and path.exists():
        data = _load_toml(path)
        # settings.local.toml holds private values (e.g. proxy credentials) and
        # is gitignored; merge it section by section on top of the base file.
        local_path = path.with_name("settings.local.toml")
        if local_path.exists():
            for section, values in _load_toml(local_path).items():
                if isinstance(values, dict) and isinstance(data.get(section), dict):
                    data[section] = {**data[section], **values}
                else:
                    data[section] = values

    # Parse sections
    sources_data = data.get("sources", {})
    sources = SourceConfig(
        documents_url=sources_data.get("documents_url", SourceConfig.documents_url),
        general_url=sources_data.get("general_url", SourceConfig.general_url),
    )

    storage_data = data.get("storage", {})
    lib_dir = overrides.get("library_dir") or storage_data.get("library_dir") or "EMA_Regulatory_Library"
    storage = StorageConfig(
        library_dir=Path(lib_dir),
        index_dir=storage_data.get("index_dir", StorageConfig.index_dir),
        raw_json_dir=storage_data.get("raw_json_dir", StorageConfig.raw_json_dir),
        failed_downloads_dir=storage_data.get("failed_downloads_dir", StorageConfig.failed_downloads_dir),
        database_name=storage_data.get("database_name", StorageConfig.database_name),
        excel_name=storage_data.get("excel_name", StorageConfig.excel_name),
        csv_name=storage_data.get("csv_name", StorageConfig.csv_name),
    )

    net_data = data.get("network", {})
    network = NetworkConfig(
        timeout=float(overrides.get("timeout") or net_data.get("timeout", NetworkConfig.timeout)),
        max_retries=int(overrides.get("max_retries") or net_data.get("max_retries", NetworkConfig.max_retries)),
        retry_delay=float(net_data.get("retry_delay", NetworkConfig.retry_delay)),
        workers=int(overrides.get("workers") or net_data.get("workers", NetworkConfig.workers)),
        proxy=str(overrides.get("proxy") or net_data.get("proxy", NetworkConfig.proxy)),
        chunk_size=int(net_data.get("chunk_size", NetworkConfig.chunk_size)),
        request_delay=float(net_data.get("request_delay", NetworkConfig.request_delay)),
    )

    default_filter = FilterConfig()
    filt_data = data.get("filters", {})
    default_types = overrides.get("types") or filt_data.get("default_types", default_filter.default_types)
    default_status = overrides.get("status") or filt_data.get("default_status", default_filter.default_status)
    if isinstance(default_types, str):
        default_types = [default_types]
    if isinstance(default_status, str):
        default_status = [default_status]

    default_languages = filt_data.get("default_languages", default_filter.default_languages)
    if isinstance(default_languages, str):
        default_languages = [default_languages]

    filters = FilterConfig(
        default_types=list(default_types),
        default_status=list(default_status),
        default_languages=list(default_languages),
    )

    class_data = data.get("classification", {})
    rules_file_path = overrides.get("rules_file") or class_data.get("rules_file") or "config/classification_rules.csv"
    # Resolve relative to config location or cwd
    rules_p = Path(rules_file_path)
    if not rules_p.is_absolute():
        if path and path.parent:
            candidate = path.parent.parent / rules_p
            if candidate.exists():
                rules_p = candidate
            elif (Path.cwd() / rules_p).exists():
                rules_p = Path.cwd() / rules_p
    classification = ClassificationConfig(rules_file=rules_p)

    return AppConfig(
        sources=sources,
        storage=storage,
        network=network,
        filters=filters,
        classification=classification,
    )
