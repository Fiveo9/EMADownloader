"""Local web UI for EMA Downloader.

Flask application bound to the loopback interface only. Long-running work is
executed by ema_downloader.webapp.tasks.TaskManager; this module exposes the
JSON API the single-page frontend polls.
"""

from __future__ import annotations

import argparse
import logging
import os
import socket
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

try:
    from flask import Flask, jsonify, render_template, request
except ImportError as exc:  # pragma: no cover - friendly guidance instead of a traceback
    raise ImportError(
        "Web UI 需要 Flask。请安装 UI 扩展依赖: pip install -e \".[ui]\" (或 pip install flask)"
    ) from exc

from ema_downloader import __version__
from ema_downloader.config import load_config
from ema_downloader.database import Database
from ema_downloader.webapp.settings import (
    SettingsValidationError,
    read_settings,
    write_settings,
)
from ema_downloader.webapp.tasks import TaskConflictError, TaskManager

logger = logging.getLogger("ema_downloader.webapp")


def _resource_dir() -> Path:
    """Package directory, or the PyInstaller bundle dir in frozen builds."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).parent


def _freeze_bootstrap() -> None:
    """Anchor relative paths (library, config, rules CSV) to the exe folder."""
    if getattr(sys, "frozen", False):
        os.chdir(Path(sys.executable).parent)


def _find_free_port(host: str, start: int, attempts: int = 20) -> int:
    """First bindable port at or after `start`; returns `start` if none found."""
    for port in range(start, start + attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind((host, port))
                return port
        except OSError:
            continue
    return start


def _mask_proxy(proxy: str) -> str:
    """Hide credentials in a proxy URL before sending it to the browser."""
    if not proxy:
        return ""
    parsed = urlparse(proxy)
    if parsed.username or parsed.password:
        netloc = parsed.hostname or ""
        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"
        return f"{parsed.scheme}://{netloc}"
    return proxy


def _open_path(path: Path) -> None:
    """Open a file or folder with the OS default handler."""
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # noqa: S606 - intentional local shell dispatch
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def create_app(config_path: Optional[Path | str] = None) -> Flask:
    """Build the Flask application. config_path is forwarded to load_config."""
    resources = _resource_dir()
    app = Flask(
        __name__,
        template_folder=str(resources / "templates"),
        static_folder=str(resources / "static"),
    )
    app.json.ensure_ascii = False  # render Chinese text unescaped in JSON responses
    manager = TaskManager(config_path=str(config_path) if config_path else None)
    app.extensions["task_manager"] = manager

    def load_db() -> Database:
        config = load_config(config_path=config_path)
        return Database(config.storage.database_path)

    @app.get("/")
    def index() -> str:
        return render_template("index.html", version=__version__)

    @app.get("/api/summary")
    def api_summary() -> Any:
        config = load_config(config_path=config_path)
        db = load_db()
        counts = db.get_summary_counts()
        options = db.get_filter_options()
        last_sync = db.get_last_sync()
        if last_sync:
            last_sync = {k: v for k, v in last_sync.items() if k != "summary"}
        return jsonify(
            {
                "version": __version__,
                "library_dir": str(config.storage.library_dir.resolve()),
                "counts": counts,
                "filter_options": options,
                "last_sync": last_sync,
                "config": {
                    "default_types": config.filters.default_types,
                    "default_status": config.filters.default_status,
                    "workers": config.network.workers,
                    "proxy": _mask_proxy(config.network.get_effective_proxy() or ""),
                },
            }
        )

    @app.get("/api/documents")
    def api_documents() -> Any:
        args = request.args
        page = max(1, int(args.get("page", 1)))
        page_size = min(200, max(1, int(args.get("page_size", 50))))

        types = [t for t in args.get("types", "").split(",") if t]
        statuses = [s for s in args.get("statuses", "").split(",") if s]
        download_statuses = [s for s in args.get("download_statuses", "").split(",") if s]
        keyword = args.get("keyword", "").strip() or None

        db = load_db()
        total = db.count_documents(
            types=types or None,
            statuses=statuses or None,
            download_statuses=download_statuses or None,
            keyword=keyword,
        )
        docs = db.get_documents(
            types=types or None,
            statuses=statuses or None,
            download_statuses=download_statuses or None,
            keyword=keyword,
            limit=page_size,
            offset=(page - 1) * page_size,
        )
        return jsonify(
            {
                "total": total,
                "page": page,
                "page_size": page_size,
                "documents": [doc.to_dict() for doc in docs],
            }
        )

    @app.get("/api/config")
    def api_config() -> Any:
        config = load_config(config_path=config_path)
        return jsonify(
            {
                "version": __version__,
                "library_dir": str(config.storage.library_dir.resolve()),
                "database_path": str(config.storage.database_path),
                "rules_file": str(config.classification.rules_file),
                "network": {
                    "workers": config.network.workers,
                    "timeout": config.network.timeout,
                    "max_retries": config.network.max_retries,
                    "request_delay": config.network.request_delay,
                    "proxy": _mask_proxy(config.network.get_effective_proxy() or ""),
                },
                "filters": {
                    "default_types": config.filters.default_types,
                    "default_status": config.filters.default_status,
                    "default_languages": config.filters.default_languages,
                },
            }
        )

    @app.get("/api/settings")
    def api_get_settings() -> Any:
        return jsonify(read_settings(config_path))

    @app.put("/api/settings")
    def api_update_settings() -> Any:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "请求体必须是对象"}), 400
        try:
            applied = write_settings(config_path, data)
        except SettingsValidationError as exc:
            return jsonify({"error": str(exc), "details": exc.errors}), 400
        except OSError as exc:
            return jsonify({"error": f"写入配置文件失败: {exc}"}), 500
        return jsonify({"applied": applied, "settings": read_settings(config_path)})

    @app.post("/api/tasks")
    def api_create_task() -> Any:
        data = request.get_json(silent=True) or {}
        task_type = str(data.get("type", ""))
        params = data.get("params") or {}
        if not isinstance(params, dict):
            return jsonify({"error": "params 必须是对象"}), 400
        try:
            task = manager.submit(task_type, params)
        except TaskConflictError as exc:
            return jsonify({"error": str(exc)}), 409
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(task.to_dict()), 201

    @app.get("/api/tasks")
    def api_tasks() -> Any:
        return jsonify({"tasks": [task.to_dict() for task in manager.list_tasks()]})

    @app.get("/api/tasks/<task_id>")
    def api_task_detail(task_id: str) -> Any:
        task = manager.get(task_id)
        if not task:
            return jsonify({"error": "任务不存在"}), 404
        return jsonify(task.to_dict(include_logs=True))

    @app.post("/api/tasks/<task_id>/cancel")
    def api_cancel_task(task_id: str) -> Any:
        if not manager.get(task_id):
            return jsonify({"error": "任务不存在"}), 404
        cancelled = manager.cancel(task_id)
        return jsonify({"cancelled": cancelled})

    @app.get("/api/open")
    def api_open() -> Any:
        """Open a library file/folder with the OS handler (loopback server only)."""
        raw = (request.args.get("path") or "").strip()
        config = load_config(config_path=config_path)
        library_root = config.storage.library_dir.resolve()

        target = Path(raw) if raw else library_root
        if not target.is_absolute():
            target = library_root / target
        try:
            target = target.resolve()
        except OSError:
            return jsonify({"error": "无效路径"}), 400

        if target != library_root and library_root not in target.parents:
            return jsonify({"error": "路径超出资料库范围"}), 400
        if not target.exists():
            return jsonify({"error": "文件或目录不存在"}), 404

        _open_path(target)
        return jsonify({"opened": str(target)})

    @app.errorhandler(404)
    def not_found(_error: Any) -> Any:
        return jsonify({"error": "not found"}), 404

    return app


def run(
    host: str = "127.0.0.1",
    port: int = 5000,
    open_browser: bool = True,
    config_path: Optional[Path | str] = None,
) -> None:
    """Start the local web UI server (blocking)."""
    _freeze_bootstrap()
    port = _find_free_port(host, port)
    app = create_app(config_path=config_path)
    url = f"http://{host}:{port}"
    print(f"\n  EMA 监管文件库 Web UI 已启动: {url}")
    print("  使用时请不要关闭本窗口（关闭即退出程序）。\n")
    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host=host, port=port, debug=False)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="ema-downloader-ui",
        description="EMA 监管文件库本地 Web 界面",
    )
    parser.add_argument("--host", default="127.0.0.1", help="监听地址 (默认仅本机 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="监听端口 (默认 5000)")
    parser.add_argument("--config", default=None, help="自定义 settings.toml 路径")
    parser.add_argument("--no-browser", action="store_true", help="启动后不自动打开浏览器")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    try:
        run(
            host=args.host,
            port=args.port,
            open_browser=not args.no_browser,
            config_path=args.config,
        )
    except OSError as exc:
        print(f"启动失败: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
