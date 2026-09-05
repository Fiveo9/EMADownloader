"""Tests for the local web UI: task manager, runners, and Flask API."""

import hashlib
import json
import threading
import time
from pathlib import Path
from urllib.parse import quote

import pytest

# webapp 包在缺少 Flask 时会在导入期抛出带提示的 ImportError,
# 这里先跳过,避免环境未装 flask 时整个测试收集直接报错。
pytest.importorskip("flask")

from ema_downloader.config import load_config
from ema_downloader.database import Database
from ema_downloader.downloader import DownloadResult, Downloader
from ema_downloader.models import DownloadStatus, EMADocument, EMARawRecord
from ema_downloader.webapp import create_app
from ema_downloader.webapp.tasks import TaskConflictError, TaskManager, _check_cancel


def make_doc(ema_id: str, name: str = "Doc", **kwargs) -> EMADocument:
    defaults = dict(
        ema_id=str(ema_id),
        name=name,
        document_type="scientific-guideline",
        status="Adopted",
        last_updated_at="2026-01-01",
    )
    defaults.update(kwargs)
    return EMADocument(**defaults)


@pytest.fixture
def web_config_path(tmp_path: Path) -> Path:
    cfg = tmp_path / "settings.toml"
    cfg.write_text(f"[storage]\nlibrary_dir = '{(tmp_path / 'lib').as_posix()}'\n", encoding="utf-8")
    return cfg


@pytest.fixture
def web_app(web_config_path: Path):
    app = create_app(config_path=web_config_path)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def web_client(web_app):
    return web_app.test_client()


@pytest.fixture
def web_db(web_config_path: Path) -> Database:
    config = load_config(config_path=web_config_path)
    config.ensure_directories()
    return Database(config.storage.database_path)


# ---------------------------------------------------------------------------
# download_batch cancellation
# ---------------------------------------------------------------------------


def test_download_batch_cancel_check(sample_config, sample_db, monkeypatch):
    calls = {"n": 0}

    def fake_single(self, doc, client=None, is_update=False):
        time.sleep(0.2)
        return DownloadResult(doc=doc, success=True, status=DownloadStatus.DOWNLOADED, file_size=1)

    monkeypatch.setattr(Downloader, "download_single_document", fake_single)

    downloader = Downloader(sample_config, sample_db)
    items = [
        (
            EMADocument(
                ema_id=str(i),
                name=f"doc {i}",
                document_type="scientific-guideline",
                official_url=f"https://example.com/{i}.pdf",
            ),
            "new",
        )
        for i in range(10)
    ]

    def on_progress(_res):
        calls["n"] += 1

    results = downloader.download_batch(
        items, progress_callback=on_progress, cancel_check=lambda: calls["n"] >= 1
    )

    assert 1 <= len(results) < 10
    assert calls["n"] == len(results)


def test_download_batch_without_cancel_check_unchanged(sample_config, sample_db, monkeypatch):
    """Without cancel_check the batch completes all items (CLI behaviour)."""

    def fake_single(self, doc, client=None, is_update=False):
        return DownloadResult(doc=doc, success=True, status=DownloadStatus.DOWNLOADED, file_size=1)

    monkeypatch.setattr(Downloader, "download_single_document", fake_single)

    downloader = Downloader(sample_config, sample_db)
    items = [
        (EMADocument(ema_id=str(i), name=f"d{i}", document_type="t", official_url="https://x/{i}"), "new")
        for i in range(5)
    ]
    results = downloader.download_batch(items)
    assert len(results) == 5


# ---------------------------------------------------------------------------
# TaskManager
# ---------------------------------------------------------------------------


def test_task_manager_rejects_concurrent_tasks():
    started = threading.Event()
    release = threading.Event()

    def runner(config_path, task, params):
        started.set()
        release.wait(timeout=5)
        return {}

    mgr = TaskManager(runners={"slow": runner})
    task = mgr.submit("slow", {})
    assert started.wait(timeout=5)

    with pytest.raises(TaskConflictError):
        mgr.submit("slow", {})

    release.set()
    deadline = time.time() + 5
    while mgr.get(task.id).state != "success" and time.time() < deadline:
        time.sleep(0.05)
    assert mgr.get(task.id).state == "success"

    # Slot is free again: a new submission is accepted and finishes immediately.
    second = mgr.submit("slow", {})
    deadline = time.time() + 5
    while mgr.get(second.id).state != "success" and time.time() < deadline:
        time.sleep(0.05)
    assert mgr.get(second.id).state == "success"


def test_task_manager_cancel_marks_task_cancelled():
    started = threading.Event()
    release = threading.Event()

    def runner(config_path, task, params):
        started.set()
        release.wait(timeout=5)
        _check_cancel(task)
        return {}

    mgr = TaskManager(runners={"slow": runner})
    task = mgr.submit("slow", {})
    assert started.wait(timeout=5)
    assert mgr.cancel(task.id) is True
    release.set()

    deadline = time.time() + 5
    while mgr.get(task.id).state != "cancelled" and time.time() < deadline:
        time.sleep(0.05)
    assert mgr.get(task.id).state == "cancelled"
    assert mgr.cancel(task.id) is False  # already finished


def test_task_manager_unknown_type_rejected():
    mgr = TaskManager()
    with pytest.raises(ValueError):
        mgr.submit("bogus", {})


# ---------------------------------------------------------------------------
# Flask API
# ---------------------------------------------------------------------------


def test_index_page(web_client):
    resp = web_client.get("/")
    assert resp.status_code == 200
    assert "EMA 监管文件库".encode("utf-8") in resp.data


def test_api_summary(web_client, web_db):
    web_db.batch_upsert_documents(
        [
            make_doc("1", "Alpha guideline"),
            make_doc("2", "Beta guideline", download_status="downloaded"),
            make_doc("3", "Gamma procedural", document_type="regulatory-procedural-guideline"),
        ]
    )
    data = web_client.get("/api/summary").get_json()
    assert data["counts"]["total"] == 3
    assert data["counts"]["status_downloaded"] == 1
    assert data["filter_options"]["types"] == [
        "regulatory-procedural-guideline",
        "scientific-guideline",
    ]
    assert data["last_sync"] is None
    assert data["config"]["default_types"]


def test_api_documents_pagination_and_filters(web_client, web_db):
    docs = []
    for i in range(5):
        docs.append(
            make_doc(
                str(i),
                f"Guideline number {i}",
                last_updated_at=f"2026-0{i + 1}-01",
                download_status="downloaded" if i % 2 else "new",
            )
        )
    docs[0].name = "Special chiral document"
    web_db.batch_upsert_documents(docs)

    # Pagination
    page1 = web_client.get("/api/documents?page=1&page_size=2").get_json()
    assert page1["total"] == 5
    assert len(page1["documents"]) == 2
    page3 = web_client.get("/api/documents?page=3&page_size=2").get_json()
    assert len(page3["documents"]) == 1

    # Keyword filter
    kw = web_client.get("/api/documents?keyword=chiral").get_json()
    assert kw["total"] == 1
    assert kw["documents"][0]["name"] == "Special chiral document"

    # Download-status filter
    dl = web_client.get("/api/documents?download_statuses=downloaded").get_json()
    assert dl["total"] == 2


def test_api_open_path_guard(web_client, web_config_path, monkeypatch):
    opened = []
    monkeypatch.setattr("ema_downloader.webapp._open_path", lambda p: opened.append(Path(p)))

    config = load_config(config_path=web_config_path)
    config.ensure_directories()
    root = config.storage.library_dir.resolve()

    # Absolute path outside the library -> rejected
    outside = web_config_path  # lives in tmp_path, outside the library dir
    resp = web_client.get(f"/api/open?path={quote(str(outside))}")
    assert resp.status_code == 400

    # Relative path resolving outside the library -> rejected
    resp = web_client.get("/api/open?path=../outside.pdf")
    assert resp.status_code == 400

    # Inside the library but missing -> 404
    resp = web_client.get("/api/open?path=missing/file.pdf")
    assert resp.status_code == 404

    # Inside the library and existing -> opened via OS handler
    target_dir = root / "01_Scientific_Guidelines"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "a.pdf"
    target.write_bytes(b"%PDF-1.4" + b"x" * 600)
    resp = web_client.get(f"/api/open?path={quote('01_Scientific_Guidelines/a.pdf')}")
    assert resp.status_code == 200
    assert len(opened) == 1


def test_api_task_unknown_type(web_client):
    resp = web_client.post("/api/tasks", json={"type": "bogus"})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Sync task end-to-end (dry-run, mocked EMA source)
# ---------------------------------------------------------------------------


def _wait_for_task(web_client, task_id, timeout=20):
    deadline = time.time() + timeout
    payload = {}
    while time.time() < deadline:
        payload = web_client.get(f"/api/tasks/{task_id}").get_json()
        if payload["state"] in ("success", "failed", "cancelled"):
            return payload
        time.sleep(0.1)
    raise AssertionError(f"task did not finish in time: {payload}")


def test_sync_dry_run_task_flow(web_client, web_db, monkeypatch, fixtures_dir):
    raw_payload = json.loads(
        (fixtures_dir / "sample_documents_report.json").read_text(encoding="utf-8")
    )
    raw_records = [EMARawRecord.from_dict(item) for item in raw_payload["data"]]

    class FakeSource:
        def __init__(self, config):
            pass

        def fetch_documents_report(self, use_cached=False, cancel_check=None):
            return {"total_records": len(raw_records)}, raw_records, None

    monkeypatch.setattr("ema_downloader.webapp.tasks.EMASource", FakeSource)

    resp = web_client.post("/api/tasks", json={"type": "sync", "params": {"dry_run": True}})
    assert resp.status_code == 201
    task_id = resp.get_json()["id"]

    payload = _wait_for_task(web_client, task_id)
    assert payload["state"] == "success", payload.get("error")

    default_types = load_config(config_path=None).filters.default_types
    expected = sum(1 for r in raw_records if r.type.lower() in {t.lower() for t in default_types})
    summary = payload["result"]
    assert summary["total_filtered"] == expected
    assert summary["dry_run"] is True
    assert payload["stats"]["filtered"] == expected

    # Metadata was indexed, but dry-run downloaded nothing.
    docs = web_db.get_documents()
    assert len(docs) == expected
    assert all(doc.download_status != "downloaded" for doc in docs)

    # Task logs were captured for the UI.
    assert payload["logs"]

    # The sync run is now visible in /api/summary.
    summary_data = web_client.get("/api/summary").get_json()
    assert summary_data["last_sync"]["downloaded_success"] == 0

    # The feed's type distribution was persisted and is exposed for the dialog.
    dist = summary_data["feed_types"]
    assert dist.get("counts"), dist
    assert dist["counts"][raw_records[0].type] == sum(
        1 for r in raw_records if r.type == raw_records[0].type
    )
    assert dist.get("updated_at")


def test_verify_and_export_tasks(web_client, web_db, web_config_path):
    # One healthy file + one file missing from disk -> exactly one issue.
    config = load_config(config_path=web_config_path)
    config.ensure_directories()
    content = b"%PDF-1.4\n" + b"y" * 1000
    rel_path = "01_Scientific_Guidelines/ok.pdf"
    target = config.storage.library_dir / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)

    web_db.batch_upsert_documents(
        [
            make_doc(
                "1",
                "Healthy doc",
                local_path=rel_path,
                local_filename="ok.pdf",
                download_status="downloaded",
                file_size=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
            ),
            make_doc(
                "2",
                "Missing doc",
                local_path="01_Scientific_Guidelines/gone.pdf",
                local_filename="gone.pdf",
                download_status="downloaded",
            ),
        ]
    )

    resp = web_client.post("/api/tasks", json={"type": "verify", "params": {}})
    assert resp.status_code == 201
    payload = _wait_for_task(web_client, resp.get_json()["id"])
    assert payload["state"] == "success", payload.get("error")
    assert payload["result"]["issue_count"] == 1
    assert payload["result"]["issues"][0]["ema_id"] == "2"

    resp = web_client.post("/api/tasks", json={"type": "export", "params": {}})
    assert resp.status_code == 201
    payload = _wait_for_task(web_client, resp.get_json()["id"])
    assert payload["state"] == "success", payload.get("error")
    assert Path(payload["result"]["excel"]).exists()


# ---------------------------------------------------------------------------
# Settings management
# ---------------------------------------------------------------------------


def test_settings_roundtrip_preserves_unknown_keys(web_config_path):
    from ema_downloader.webapp.settings import write_settings

    local = web_config_path.with_name("settings.local.toml")
    local.write_text(
        "# my header\n"
        "[network]\n"
        "proxy = 'http://user:secret@old:1'\n"
        "\n"
        "[network.extra]\n"
        "flag = true\n",
        encoding="utf-8",
    )
    base_before = web_config_path.read_text(encoding="utf-8")

    applied = write_settings(
        web_config_path,
        {
            "network": {"workers": 8, "proxy": "http://new:2"},
            "filters": {"default_types": ["scientific-guideline"]},
            "storage": {"library_dir": "C:/some lib"},
        },
    )

    assert applied["network"]["workers"] == 8
    text = local.read_text(encoding="utf-8")
    assert "# my header" in text  # leading comments preserved
    assert "http://new:2" in text  # proxy replaced
    assert "user:secret@old:1" not in text
    assert "[network.extra]" in text  # unknown sub-table preserved
    assert "flag = true" in text

    cfg = load_config(config_path=web_config_path)
    assert cfg.network.workers == 8
    assert cfg.network.proxy == "http://new:2"
    assert cfg.filters.default_types == ["scientific-guideline"]
    assert str(cfg.storage.library_dir) == str(Path("C:/some lib"))
    # The committed base template is never touched.
    assert web_config_path.read_text(encoding="utf-8") == base_before


def test_settings_validation_rejects_invalid(web_config_path):
    from ema_downloader.webapp.settings import SettingsValidationError, write_settings

    local = web_config_path.with_name("settings.local.toml")
    with pytest.raises(SettingsValidationError) as excinfo:
        write_settings(
            web_config_path,
            {
                "network": {"workers": 99, "timeout": "abc", "nope": 1},
                "bogus_section": {"x": 1},
            },
        )
    errors = excinfo.value.errors
    by_field = {(e["section"], e["field"]): e["message"] for e in errors}
    assert ("network", "workers") in by_field
    assert ("network", "timeout") in by_field
    assert ("network", "nope") in by_field
    assert ("bogus_section", "-") in by_field
    assert not local.exists()  # nothing written when validation fails


def test_settings_mask_placeholder_skips_proxy(web_config_path):
    from ema_downloader.webapp.settings import PROXY_MASK, write_settings

    local = web_config_path.with_name("settings.local.toml")
    applied = write_settings(web_config_path, {"network": {"proxy": PROXY_MASK, "workers": 4}})
    assert "proxy" not in applied.get("network", {})
    assert applied["network"]["workers"] == 4
    assert "proxy" not in local.read_text(encoding="utf-8")


def test_api_settings_get_masks_proxy(web_client, web_config_path):
    local = web_config_path.with_name("settings.local.toml")
    local.write_text("[network]\nproxy = 'http://user:secret@host:1'\n", encoding="utf-8")

    data = web_client.get("/api/settings").get_json()
    assert data["values"]["network"]["proxy"] == "********"
    assert "secret" not in json.dumps(data)
    assert "proxy" in data["overridden"]["network"]
    assert data["local_path"].endswith("settings.local.toml")


def test_api_settings_put_flow(web_client, web_config_path):
    local = web_config_path.with_name("settings.local.toml")

    # 1. Valid update takes effect immediately.
    resp = web_client.put(
        "/api/settings",
        json={
            "network": {"workers": 6, "proxy": "http://user:secret@host:9"},
            "filters": {"default_status": ["Adopted"]},
        },
    )
    assert resp.status_code == 200
    cfg = load_config(config_path=web_config_path)
    assert cfg.network.workers == 6
    assert cfg.filters.default_status == ["Adopted"]

    # 2. GET masks the stored credential.
    data = web_client.get("/api/settings").get_json()
    assert data["values"]["network"]["proxy"] == "********"
    assert "secret" not in json.dumps(data)

    # 3. Resubmitting the mask keeps the stored proxy untouched.
    resp = web_client.put(
        "/api/settings", json={"network": {"proxy": "********", "request_delay": 1.5}}
    )
    assert resp.status_code == 200
    text = local.read_text(encoding="utf-8")
    assert "user:secret@host:9" in text
    assert "request_delay = 1.5" in text

    # 4. Empty proxy clears it in the file.
    resp = web_client.put("/api/settings", json={"network": {"proxy": ""}})
    assert resp.status_code == 200
    assert "proxy = ''" in local.read_text(encoding="utf-8")

    # 5. Invalid values -> 400 with per-field details, file untouched.
    before = local.read_text(encoding="utf-8")
    resp = web_client.put("/api/settings", json={"network": {"workers": 0}})
    assert resp.status_code == 400
    assert any(d["field"] == "workers" for d in resp.get_json()["details"])
    assert local.read_text(encoding="utf-8") == before
