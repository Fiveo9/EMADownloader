"""EMA data source fetcher and raw snapshot manager."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

from ema_downloader.config import AppConfig
from ema_downloader.models import EMARawRecord

logger = logging.getLogger(__name__)

# A stalled proxy connection can trickle bytes just fast enough to never trip
# the per-read timeout, so each attempt also gets a hard wall-clock budget.
ATTEMPT_BUDGET_FACTOR = 3.0
MIN_ATTEMPT_BUDGET = 90.0

# EMA's anti-bot intermittently blocks proxy exit IPs with 403 (429 when
# throttled); these statuses trigger a direct-connection fallback attempt.
BLOCKED_STATUSES = (403, 429)


class FetchCancelled(RuntimeError):
    """Raised when a cancel callback aborts an in-progress feed fetch."""


def create_httpx_client(config: AppConfig, proxy: Optional[str] = None) -> httpx.Client:
    """Create an httpx.Client configured with timeouts, headers, and proxy.

    `proxy` overrides `config.network` resolution; an empty string forces a
    direct connection (used to bypass blocked proxy exit IPs).
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        # Identity keeps iter_raw() bytes identical to the file bytes, so the
        # streaming loops can react to every network read (cancel / stall).
        "Accept-Encoding": "identity",
    }
    proxy = config.network.get_effective_proxy() if proxy is None else (proxy or None)
    timeout = httpx.Timeout(config.network.timeout, connect=15.0)

    # Note: If socks5 is configured but socksio is missing, handle fallback
    if proxy and proxy.startswith("socks"):
        try:
            import socksio  # noqa: F401
            return httpx.Client(proxy=proxy, timeout=timeout, headers=headers, follow_redirects=True)
        except ImportError:
            logger.warning("SOCKS proxy '%s' detected but socksio is not installed. Trying direct connection.", proxy)
            return httpx.Client(timeout=timeout, headers=headers, follow_redirects=True)

    if proxy:
        try:
            return httpx.Client(proxy=proxy, timeout=timeout, headers=headers, follow_redirects=True)
        except Exception as e:
            logger.warning("Failed to initialize client with proxy %s: %s. Falling back to direct.", proxy, e)

    return httpx.Client(timeout=timeout, headers=headers, follow_redirects=True)


class EMASource:
    """Fetcher for official EMA JSON feeds."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def _get_snapshot_filename(self, base_name: str) -> str:
        """Format snapshot filename with current date: e.g. base_20260903.json."""
        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        return f"{base_name}_{today_str}.json"

    def fetch_feed(
        self,
        url: str,
        feed_name: str,
        use_cached: bool = False,
        cancel_check: Optional[Callable[[], bool]] = None,
        attempt_budget: Optional[float] = None,
    ) -> Tuple[Dict[str, Any], List[EMARawRecord], Path]:
        """Fetch an EMA JSON feed, save raw snapshot, and return parsed records.

        `cancel_check` is polled between and during attempts; when it returns
        True, FetchCancelled is raised so callers can abort a stalled fetch.

        Returns:
            (meta_dict, list_of_raw_records, snapshot_path)
        """
        snapshot_filename = self._get_snapshot_filename(feed_name)
        snapshot_path = self.config.storage.full_raw_json_dir / snapshot_filename

        # If cache requested and file exists, load directly
        if use_cached and snapshot_path.exists():
            logger.info("Loading cached snapshot from %s", snapshot_path)
            with open(snapshot_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            meta = payload.get("meta", {})
            data_items = payload.get("data", [])
            records = [EMARawRecord.from_dict(item) for item in data_items]
            return meta, records, snapshot_path

        # Otherwise download with retry
        logger.info("Fetching EMA feed from %s ...", url)
        self.config.storage.full_raw_json_dir.mkdir(parents=True, exist_ok=True)
        temp_snapshot = snapshot_path.with_suffix(".json.tmp")

        if attempt_budget is None:
            attempt_budget = max(
                self.config.network.timeout * ATTEMPT_BUDGET_FACTOR, MIN_ATTEMPT_BUDGET
            )
        proxy = self.config.network.get_effective_proxy()
        primary_client = create_httpx_client(self.config)
        direct_client: Optional[httpx.Client] = None
        # Once EMA blocks the proxy exit IP (403/429), later attempts go direct.
        use_direct = False
        retries = self.config.network.max_retries
        delay = self.config.network.retry_delay

        try:
            for attempt in range(1, retries + 1):
                if cancel_check and cancel_check():
                    raise FetchCancelled(f"Fetch of {url} cancelled before attempt {attempt}")
                client = primary_client
                if use_direct and proxy:
                    if direct_client is None:
                        logger.info("Retrying via direct connection (proxy exit IP blocked).")
                        direct_client = create_httpx_client(self.config, proxy="")
                    client = direct_client
                attempt_started = time.monotonic()
                try:
                    with client.stream("GET", url) as response:
                        response.raise_for_status()
                        with open(temp_snapshot, "wb") as f:
                            for chunk in response.iter_raw():
                                f.write(chunk)
                                if time.monotonic() - attempt_started > attempt_budget:
                                    raise TimeoutError(
                                        f"Attempt exceeded its {attempt_budget:.0f}s time budget; "
                                        "connection is likely stalled."
                                    )
                    # Atomically replace snapshot
                    temp_snapshot.replace(snapshot_path)
                    break
                except (httpx.HTTPError, httpx.StreamError, TimeoutError) as exc:
                    if temp_snapshot.exists():
                        temp_snapshot.unlink(missing_ok=True)
                    logger.warning("Attempt %d/%d failed to fetch %s: %s", attempt, retries, url, exc)
                    if (
                        isinstance(exc, httpx.HTTPStatusError)
                        and exc.response.status_code in BLOCKED_STATUSES
                        and proxy
                        and not use_direct
                    ):
                        use_direct = True
                    if attempt == retries:
                        # Fallback to local snapshot if exists
                        if snapshot_path.exists():
                            logger.warning("Using existing local snapshot %s as fallback.", snapshot_path)
                            break
                        raise RuntimeError(f"Failed to fetch EMA feed from {url} after {retries} attempts: {exc}") from exc
                    if cancel_check and cancel_check():
                        raise FetchCancelled(f"Fetch of {url} cancelled while waiting for retry") from exc
                    time.sleep(delay * (2 ** (attempt - 1)))
        finally:
            primary_client.close()
            if direct_client is not None:
                direct_client.close()

        logger.info("Saved raw JSON snapshot to %s", snapshot_path)
        with open(snapshot_path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        meta = payload.get("meta", {})
        data_items = payload.get("data", [])
        records = [EMARawRecord.from_dict(item) for item in data_items]
        logger.info("Parsed %d records from feed %s (reported total: %s)", len(records), feed_name, meta.get("total_records"))
        return meta, records, snapshot_path

    def fetch_documents_report(
        self,
        use_cached: bool = False,
        cancel_check: Optional[Callable[[], bool]] = None,
        attempt_budget: Optional[float] = None,
    ) -> Tuple[Dict[str, Any], List[EMARawRecord], Path]:
        """Fetch all documents report."""
        return self.fetch_feed(
            url=self.config.sources.documents_url,
            feed_name="documents-output-json-report_en",
            use_cached=use_cached,
            cancel_check=cancel_check,
            attempt_budget=attempt_budget,
        )

    def fetch_general_report(
        self,
        use_cached: bool = False,
        cancel_check: Optional[Callable[[], bool]] = None,
        attempt_budget: Optional[float] = None,
    ) -> Tuple[Dict[str, Any], List[EMARawRecord], Path]:
        """Fetch guidance and general information report."""
        return self.fetch_feed(
            url=self.config.sources.general_url,
            feed_name="general-json-report_en",
            use_cached=use_cached,
            cancel_check=cancel_check,
            attempt_budget=attempt_budget,
        )
