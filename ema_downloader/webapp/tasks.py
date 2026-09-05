"""Background task management for the local web UI.

Long-running operations (sync / organize / export / verify) are executed in a
daemon thread, one at a time, by composing the same core components the CLI
uses. Progress is exposed through Task attributes that the Flask layer
serializes for the frontend to poll.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from ema_downloader.cli import filter_raw_records, prepare_documents
from ema_downloader.config import AppConfig, load_config
from ema_downloader.database import Database
from ema_downloader.downloader import Downloader
from ema_downloader.ema_source import EMASource
from ema_downloader.exporter import Exporter
from ema_downloader.models import DownloadStatus, SyncSummary
from ema_downloader.organizer import compute_relative_path, load_classification_rules
from ema_downloader.reporting import save_sync_report

logger = logging.getLogger("ema_downloader.webapp")

# Types accepted by POST /api/tasks (each key maps to a runner below).
TASK_TYPES = ("sync", "organize", "export", "verify")

RUNNING_STATES = ("pending", "running")


class TaskCancelledError(Exception):
    """Raised inside a runner when the user requested cancellation."""


class TaskConflictError(Exception):
    """Raised when a task is submitted while another one is still active."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_list(value: Any) -> Optional[List[str]]:
    """Accept a list or a comma-separated string, return a list or None."""
    if value is None or value == "":
        return None
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return [str(part).strip() for part in value if str(part).strip()]


@dataclass
class Task:
    """State of one background operation, polled by the frontend."""

    id: str
    type: str
    params: Dict[str, Any] = field(default_factory=dict)
    state: str = "pending"  # pending | running | success | failed | cancelled
    phase: str = "queued"  # queued | fetching | planning | downloading | organizing | exporting | verifying | done
    progress_done: int = 0
    progress_total: int = 0  # 0 means indeterminate
    current_item: str = ""
    stats: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error: str = ""
    log_lines: deque = field(default_factory=lambda: deque(maxlen=500))
    cancel_event: threading.Event = field(default_factory=threading.Event)
    created_at: str = field(default_factory=_now_iso)
    started_at: str = ""
    finished_at: str = ""

    def to_dict(self, include_logs: bool = False, log_limit: int = 200) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "params": self.params,
            "state": self.state,
            "phase": self.phase,
            "progress": {"done": self.progress_done, "total": self.progress_total},
            "current_item": self.current_item,
            "stats": self.stats,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }
        if include_logs:
            logs = list(self.log_lines)
            data["logs"] = logs[-log_limit:]
        return data


class TaskLogHandler(logging.Handler):
    """Captures ema_downloader log records into the running task's log buffer."""

    def __init__(self, task: Task) -> None:
        super().__init__(level=logging.INFO)
        self.task = task
        self.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S")
        )

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.task.log_lines.append(self.format(record))
        except Exception:  # pragma: no cover - never break logging
            pass


def _check_cancel(task: Task) -> None:
    if task.cancel_event.is_set():
        raise TaskCancelledError()


def _make_config(params: Dict[str, Any], config_path: Optional[str]) -> AppConfig:
    """Map UI task parameters onto load_config overrides."""
    overrides: Dict[str, Any] = {}
    if params.get("library_dir"):
        overrides["library_dir"] = str(params["library_dir"])
    if params.get("workers"):
        overrides["workers"] = max(1, min(int(params["workers"]), 16))
    if params.get("proxy"):
        overrides["proxy"] = str(params["proxy"])
    types = _as_list(params.get("types"))
    if types:
        overrides["types"] = types
    status = _as_list(params.get("status"))
    if status:
        overrides["status"] = status
    return load_config(config_path=config_path, **overrides)


def run_sync(config_path: Optional[str], task: Task, params: Dict[str, Any]) -> Dict[str, Any]:
    """Full pipeline: fetch feed -> filter -> index -> plan -> download -> report -> export."""
    start_time = time.time()
    config = _make_config(params, config_path)
    config.ensure_directories()

    db = Database(config.storage.database_path)
    rules = load_classification_rules(config.classification.rules_file)
    source = EMASource(config)
    downloader = Downloader(config, db)
    exporter = Exporter(config, db)
    dry_run = bool(params.get("dry_run"))

    task.phase = "fetching"
    _check_cancel(task)
    meta, raw_records, _ = source.fetch_documents_report()
    task.stats["feed_total"] = len(raw_records)

    types = _as_list(params.get("types")) or config.filters.default_types
    statuses = _as_list(params.get("status")) or config.filters.default_status
    filtered_raw = filter_raw_records(
        raw_records,
        types=types,
        statuses=statuses,
        keyword=params.get("keyword") or None,
        updated_since=params.get("updated_since") or None,
        limit=int(params["limit"]) if params.get("limit") else None,
    )
    task.stats["filtered"] = len(filtered_raw)

    task.phase = "planning"
    docs = prepare_documents(filtered_raw, rules)
    db.batch_upsert_documents(docs)

    planned_items: List[Any] = []
    new_planned = 0
    updated_planned = 0
    skipped_unchanged = 0
    task.progress_total = len(docs)
    for index, doc in enumerate(docs, start=1):
        _check_cancel(task)
        action, _reason = downloader.plan_document(doc)
        if action == "new":
            planned_items.append((doc, action))
            new_planned += 1
        elif action == "updated":
            planned_items.append((doc, action))
            updated_planned += 1
        elif action == "skip":
            skipped_unchanged += 1
            existing = db.get_document(doc.ema_id)
            if not existing or existing.download_status not in (
                DownloadStatus.DOWNLOADED.value,
                DownloadStatus.UPDATED.value,
            ):
                db.update_download_result(
                    ema_id=doc.ema_id,
                    download_status=DownloadStatus.SKIPPED_UNCHANGED.value,
                )
        task.progress_done = index
        task.current_item = doc.name[:120]

    task.stats.update(
        {
            "new_planned": new_planned,
            "updated_planned": updated_planned,
            "skipped_unchanged": skipped_unchanged,
        }
    )

    downloaded_success = 0
    downloaded_failed = 0
    total_bytes = 0
    failures: List[Dict[str, Any]] = []

    if not dry_run and planned_items:
        task.phase = "downloading"
        task.progress_done = 0
        task.progress_total = len(planned_items)
        logger.info("Downloading %d files with %d workers ...", len(planned_items), config.network.workers)

        def on_progress(res: Any) -> None:
            nonlocal downloaded_success, downloaded_failed, total_bytes
            task.progress_done += 1
            task.current_item = res.doc.name[:120]
            if res.success:
                downloaded_success += 1
                total_bytes += res.file_size
            else:
                downloaded_failed += 1
                failures.append(
                    {
                        "ema_id": res.doc.ema_id,
                        "name": res.doc.name,
                        "error": res.error_message,
                    }
                )

        downloader.download_batch(
            planned_items,
            progress_callback=on_progress,
            cancel_check=task.cancel_event.is_set,
        )

    duration = time.time() - start_time
    summary = SyncSummary(
        timestamp=_now_iso(),
        total_records_in_feed=len(raw_records),
        total_filtered=len(filtered_raw),
        new_planned=new_planned,
        updated_planned=updated_planned,
        skipped_unchanged=skipped_unchanged,
        downloaded_success=downloaded_success,
        downloaded_failed=downloaded_failed,
        total_bytes=total_bytes,
        dry_run=dry_run,
        duration_seconds=duration,
        failures=failures,
    )

    # Record partial results even when cancelled, so the audit trail stays consistent.
    db.record_sync_history(summary)
    save_sync_report(summary, config)

    _check_cancel(task)
    task.phase = "exporting"
    exporter.export_all(summary=summary)

    task.stats.update(
        {
            "downloaded_success": downloaded_success,
            "downloaded_failed": downloaded_failed,
            "total_bytes": total_bytes,
            "duration_seconds": round(duration, 2),
            "dry_run": dry_run,
        }
    )
    task.progress_done = task.progress_total
    return summary.to_dict()


def run_organize(config_path: Optional[str], task: Task, params: Dict[str, Any]) -> Dict[str, Any]:
    """Re-classify and move existing files according to the current rules."""
    import os

    config = _make_config(params, config_path)
    config.ensure_directories()
    db = Database(config.storage.database_path)
    rules = load_classification_rules(config.classification.rules_file)
    exporter = Exporter(config, db)

    docs = db.get_documents()
    task.phase = "organizing"
    task.progress_total = len(docs)
    moved_count = 0

    for index, doc in enumerate(docs, start=1):
        _check_cancel(task)
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

        db.upsert_document(doc)
        task.progress_done = index
        task.current_item = doc.name[:120]

    _check_cancel(task)
    task.phase = "exporting"
    exporter.export_all()

    task.stats["moved"] = moved_count
    return {"moved": moved_count, "total": len(docs)}


def run_export(config_path: Optional[str], task: Task, params: Dict[str, Any]) -> Dict[str, Any]:
    """Export the database index to Excel/CSV files."""
    config = _make_config(params, config_path)
    config.ensure_directories()
    db = Database(config.storage.database_path)
    exporter = Exporter(config, db)

    task.phase = "exporting"
    results = exporter.export_all()
    task.progress_done = task.progress_total = len(results)
    return {key: str(path) for key, path in results.items()}


def run_verify(config_path: Optional[str], task: Task, params: Dict[str, Any]) -> Dict[str, Any]:
    """Verify integrity (existence / size / header / SHA-256) of the library."""
    config = _make_config(params, config_path)
    config.ensure_directories()
    db = Database(config.storage.database_path)
    downloader = Downloader(config, db)

    task.phase = "verifying"

    def on_progress(doc: Any, index: int, total: int) -> None:
        task.progress_total = total
        task.progress_done = index - 1
        task.current_item = doc.name[:120]

    issues = downloader.verify_library(
        progress_callback=on_progress,
        cancel_check=task.cancel_event.is_set,
    )
    task.progress_done = task.progress_total
    task.stats["issues"] = len(issues)
    return {"issues": issues, "issue_count": len(issues)}


RUNNERS: Dict[str, Callable[[Optional[str], Task, Dict[str, Any]], Dict[str, Any]]] = {
    "sync": run_sync,
    "organize": run_organize,
    "export": run_export,
    "verify": run_verify,
}


class TaskManager:
    """Executes one background task at a time; extra submissions are rejected."""

    def __init__(
        self,
        config_path: Optional[str] = None,
        runners: Optional[Dict[str, Callable[[Optional[str], Task, Dict[str, Any]], Dict[str, Any]]]] = None,
    ) -> None:
        self._config_path = config_path
        self._runners = dict(runners) if runners is not None else dict(RUNNERS)
        self._lock = threading.Lock()
        self._tasks: "OrderedDict[str, Task]" = OrderedDict()

    def has_task_type(self, task_type: str) -> bool:
        return task_type in self._runners

    def submit(self, task_type: str, params: Optional[Dict[str, Any]] = None) -> Task:
        with self._lock:
            active = [t for t in self._tasks.values() if t.state in RUNNING_STATES]
            if active:
                active_task = active[0]
                raise TaskConflictError(
                    f"任务 {active_task.type} ({active_task.id}) 正在运行，请等待完成或先取消"
                )
            if task_type not in self._runners:
                raise ValueError(f"未知任务类型: {task_type}")
            task = Task(id=uuid.uuid4().hex[:12], type=task_type, params=dict(params or {}))
            self._tasks[task.id] = task

        thread = threading.Thread(
            target=self._run, args=(task,), name=f"webui-task-{task.type}", daemon=True
        )
        thread.start()
        return task

    def cancel(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task and task.state in RUNNING_STATES:
            task.cancel_event.set()
            return True
        return False

    def get(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def active_task(self) -> Optional[Task]:
        for task in reversed(self._tasks.values()):  # type: ignore[arg-type]
            if task.state in RUNNING_STATES:
                return task
        return None

    def list_tasks(self, limit: int = 50) -> List[Task]:
        tasks = list(self._tasks.values())
        tasks.reverse()  # newest first
        return tasks[:limit]

    def _run(self, task: Task) -> None:
        handler = TaskLogHandler(task)
        package_logger = logging.getLogger("ema_downloader")
        # Without basicConfig (e.g. under pytest) the package logger's effective
        # level falls back to root's WARNING and INFO records never reach the
        # handler; clamp it so the UI log feed is always populated.
        if package_logger.level == logging.NOTSET or package_logger.level > logging.INFO:
            package_logger.setLevel(logging.INFO)
        package_logger.addHandler(handler)
        task.state = "running"
        task.started_at = _now_iso()
        try:
            runner = self._runners[task.type]
            result = runner(self._config_path, task, task.params)
            task.result = result
            task.state = "cancelled" if task.cancel_event.is_set() else "success"
            logger.info("任务 %s (%s) 结束，状态: %s", task.id, task.type, task.state)
        except TaskCancelledError:
            task.state = "cancelled"
            logger.info("任务 %s (%s) 已被用户取消", task.id, task.type)
        except Exception as exc:  # noqa: BLE001 - surface any failure in the UI
            task.state = "failed"
            task.error = str(exc)
            logger.exception("任务 %s (%s) 失败: %s", task.id, task.type, exc)
        finally:
            package_logger.removeHandler(handler)
            task.phase = "done"
            task.finished_at = _now_iso()
