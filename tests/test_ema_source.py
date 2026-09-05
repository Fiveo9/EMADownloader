"""Tests for EMA data source and snapshot caching."""

import json
import time
from pathlib import Path

import httpx
import pytest

from ema_downloader.config import AppConfig
from ema_downloader.ema_source import EMASource, FetchCancelled, create_httpx_client


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


@pytest.fixture
def feed_payload(sample_documents_json_path: Path) -> bytes:
    return sample_documents_json_path.read_bytes()


def test_fetch_feed_falls_back_to_direct_on_403(
    sample_config: AppConfig, feed_payload: bytes, monkeypatch: pytest.MonkeyPatch
):
    """A 403 from EMA (anti-bot) should retry over a direct connection."""
    sample_config.network.proxy = "http://fake-proxy:8080"
    sample_config.network.max_retries = 3
    sample_config.network.retry_delay = 0.0

    state = {"blocked": True}
    proxy_args = []

    def handler(request: httpx.Request) -> httpx.Response:
        if state["blocked"]:
            state["blocked"] = False
            return httpx.Response(403)
        return httpx.Response(200, content=iter([feed_payload]))

    def fake_create_client(config: AppConfig, proxy=None) -> httpx.Client:
        proxy_args.append(proxy)
        return httpx.Client(transport=httpx.MockTransport(handler))

    monkeypatch.setattr("ema_downloader.ema_source.create_httpx_client", fake_create_client)

    source = EMASource(sample_config)
    meta, records, path = source.fetch_documents_report()

    assert len(records) == 5
    # Attempt 1 resolved the configured proxy; attempt 2 connected directly.
    assert proxy_args == [None, ""]
    assert path.exists()


def test_fetch_feed_aborts_stalled_attempt_and_retries(
    sample_config: AppConfig, feed_payload: bytes, monkeypatch: pytest.MonkeyPatch
):
    """A trickle-stalled connection must hit the attempt time budget, not hang."""
    sample_config.network.max_retries = 2
    sample_config.network.retry_delay = 0.0

    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] == 1:

            def trickle():
                yield b"{"
                time.sleep(2.0)
                yield feed_payload[1:]

            return httpx.Response(200, content=trickle())
        return httpx.Response(200, content=iter([feed_payload]))

    monkeypatch.setattr(
        "ema_downloader.ema_source.create_httpx_client",
        lambda config, proxy=None: httpx.Client(transport=httpx.MockTransport(handler)),
    )

    source = EMASource(sample_config)
    meta, records, path = source.fetch_documents_report(attempt_budget=0.5)

    assert attempts["n"] == 2
    assert len(records) == 5
    assert path.exists()


def test_fetch_feed_cancelled_before_request(sample_config: AppConfig, monkeypatch: pytest.MonkeyPatch):
    """cancel_check should abort the fetch before any request is made."""

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("request must not be sent when cancelled")

    monkeypatch.setattr(
        "ema_downloader.ema_source.create_httpx_client",
        lambda config, proxy=None: httpx.Client(transport=httpx.MockTransport(handler)),
    )

    source = EMASource(sample_config)
    with pytest.raises(FetchCancelled):
        source.fetch_documents_report(cancel_check=lambda: True)


def test_user_agent_is_plain_browser(sample_config: AppConfig):
    """The User-Agent must look like a plain browser, with no tool marker."""
    client = create_httpx_client(sample_config)
    try:
        ua = client.headers["User-Agent"]
    finally:
        client.close()

    assert "EMADownloader" not in ua
    assert ua.startswith("Mozilla/5.0")
