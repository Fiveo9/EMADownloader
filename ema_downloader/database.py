"""SQLite storage and index management for EMA Downloader."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ema_downloader.models import DownloadStatus, EMADocument, SyncSummary


class Database:
    """Manages the local SQLite metadata index."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def _get_connection(self) -> sqlite3.Connection:
        # Generous busy timeout: the web UI reads while background tasks write.
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        """Create necessary tables and indexes if they do not exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ema_documents (
                    ema_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    document_type TEXT,
                    status TEXT,
                    reference_number TEXT,
                    medicine_name TEXT,
                    first_published_at TEXT,
                    last_updated_at TEXT,
                    official_url TEXT,
                    source_dataset TEXT,
                    local_path TEXT,
                    local_filename TEXT,
                    file_extension TEXT,
                    http_status INTEGER,
                    content_type TEXT,
                    file_size INTEGER DEFAULT 0,
                    sha256 TEXT,
                    download_status TEXT,
                    downloaded_at TEXT,
                    last_seen_at TEXT,
                    is_archived INTEGER DEFAULT 0,
                    category TEXT,
                    sub_category TEXT,
                    error_message TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    total_records INTEGER DEFAULT 0,
                    new_planned INTEGER DEFAULT 0,
                    updated_planned INTEGER DEFAULT 0,
                    downloaded_success INTEGER DEFAULT 0,
                    downloaded_failed INTEGER DEFAULT 0,
                    skipped_unchanged INTEGER DEFAULT 0,
                    duration_seconds REAL DEFAULT 0.0,
                    summary_json TEXT
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_type ON ema_documents(document_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_download_status ON ema_documents(download_status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_last_updated ON ema_documents(last_updated_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_ref ON ema_documents(reference_number)")
            conn.commit()

    def get_document(self, ema_id: str) -> Optional[EMADocument]:
        """Fetch a single document by its EMA ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ema_documents WHERE ema_id = ?", (ema_id,))
            row = cursor.fetchone()
            if row:
                return EMADocument.from_row(dict(row))
        return None

    def upsert_document(self, doc: EMADocument) -> None:
        """Insert or update a single document."""
        self.batch_upsert_documents([doc])

    def batch_upsert_documents(self, docs: List[EMADocument]) -> None:
        """Batch insert or update documents."""
        if not docs:
            return

        sql = """
            INSERT INTO ema_documents (
                ema_id, name, document_type, status, reference_number, medicine_name,
                first_published_at, last_updated_at, official_url, source_dataset,
                local_path, local_filename, file_extension, http_status, content_type,
                file_size, sha256, download_status, downloaded_at, last_seen_at,
                is_archived, category, sub_category, error_message
            ) VALUES (
                :ema_id, :name, :document_type, :status, :reference_number, :medicine_name,
                :first_published_at, :last_updated_at, :official_url, :source_dataset,
                :local_path, :local_filename, :file_extension, :http_status, :content_type,
                :file_size, :sha256, :download_status, :downloaded_at, :last_seen_at,
                :is_archived, :category, :sub_category, :error_message
            )
            ON CONFLICT(ema_id) DO UPDATE SET
                name = excluded.name,
                document_type = excluded.document_type,
                status = excluded.status,
                reference_number = excluded.reference_number,
                medicine_name = excluded.medicine_name,
                first_published_at = excluded.first_published_at,
                last_updated_at = excluded.last_updated_at,
                official_url = excluded.official_url,
                source_dataset = excluded.source_dataset,
                local_path = CASE WHEN excluded.local_path != '' THEN excluded.local_path ELSE ema_documents.local_path END,
                local_filename = CASE WHEN excluded.local_filename != '' THEN excluded.local_filename ELSE ema_documents.local_filename END,
                file_extension = excluded.file_extension,
                http_status = COALESCE(excluded.http_status, ema_documents.http_status),
                content_type = CASE WHEN excluded.content_type != '' THEN excluded.content_type ELSE ema_documents.content_type END,
                file_size = CASE WHEN excluded.file_size > 0 THEN excluded.file_size ELSE ema_documents.file_size END,
                sha256 = CASE WHEN excluded.sha256 != '' THEN excluded.sha256 ELSE ema_documents.sha256 END,
                download_status = CASE
                    WHEN ema_documents.download_status IN ('downloaded', 'updated') THEN ema_documents.download_status
                    ELSE excluded.download_status
                END,
                downloaded_at = COALESCE(excluded.downloaded_at, ema_documents.downloaded_at),
                last_seen_at = excluded.last_seen_at,
                is_archived = excluded.is_archived,
                category = CASE WHEN excluded.category != '' THEN excluded.category ELSE ema_documents.category END,
                sub_category = CASE WHEN excluded.sub_category != '' THEN excluded.sub_category ELSE ema_documents.sub_category END,
                error_message = excluded.error_message
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(sql, [d.to_dict() for d in docs])
            conn.commit()

    def update_download_result(
        self,
        ema_id: str,
        download_status: str,
        http_status: Optional[int] = None,
        content_type: str = "",
        file_size: int = 0,
        sha256: str = "",
        local_path: str = "",
        error_message: str = "",
        downloaded_at: Optional[str] = None,
    ) -> None:
        """Update download status and checksum for a completed or failed download."""
        if not downloaded_at and download_status in (DownloadStatus.DOWNLOADED.value, DownloadStatus.UPDATED.value):
            downloaded_at = datetime.now(timezone.utc).isoformat()

        sql = """
            UPDATE ema_documents SET
                download_status = ?,
                http_status = COALESCE(?, http_status),
                content_type = CASE WHEN ? != '' THEN ? ELSE content_type END,
                file_size = CASE WHEN ? > 0 THEN ? ELSE file_size END,
                sha256 = CASE WHEN ? != '' THEN ? ELSE sha256 END,
                local_path = CASE WHEN ? != '' THEN ? ELSE local_path END,
                error_message = ?,
                downloaded_at = COALESCE(?, downloaded_at)
            WHERE ema_id = ?
        """
        with self._get_connection() as conn:
            conn.execute(
                sql,
                (
                    download_status,
                    http_status,
                    content_type,
                    content_type,
                    file_size,
                    file_size,
                    sha256,
                    sha256,
                    local_path,
                    local_path,
                    error_message,
                    downloaded_at,
                    ema_id,
                ),
            )
            conn.commit()

    def _build_filter_conditions(
        self,
        types: Optional[List[str]] = None,
        statuses: Optional[List[str]] = None,
        download_statuses: Optional[List[str]] = None,
        keyword: Optional[str] = None,
        updated_since: Optional[str] = None,
    ) -> Tuple[List[str], List[Any]]:
        """Build shared WHERE fragments for document queries."""
        conditions = []
        params: List[Any] = []

        if types:
            placeholders = ",".join("?" for _ in types)
            conditions.append(f"document_type IN ({placeholders})")
            params.extend(types)

        if statuses:
            placeholders = ",".join("?" for _ in statuses)
            conditions.append(f"LOWER(status) IN ({placeholders})")
            params.extend([s.lower() for s in statuses])

        if download_statuses:
            placeholders = ",".join("?" for _ in download_statuses)
            conditions.append(f"download_status IN ({placeholders})")
            params.extend(download_statuses)

        if keyword:
            kw = f"%{keyword.lower()}%"
            conditions.append(
                "(LOWER(name) LIKE ? OR LOWER(reference_number) LIKE ? OR LOWER(medicine_name) LIKE ?)"
            )
            params.extend([kw, kw, kw])

        if updated_since:
            conditions.append("last_updated_at >= ?")
            params.append(updated_since)

        return conditions, params

    def get_documents(
        self,
        types: Optional[List[str]] = None,
        statuses: Optional[List[str]] = None,
        download_statuses: Optional[List[str]] = None,
        keyword: Optional[str] = None,
        updated_since: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[EMADocument]:
        """Query documents with filtering and pagination options."""
        conditions, params = self._build_filter_conditions(
            types, statuses, download_statuses, keyword, updated_since
        )

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        if limit:
            limit_clause = f"LIMIT {int(limit)} OFFSET {int(offset)}"
        elif offset:
            # SQLite requires a LIMIT clause when OFFSET is used; -1 means unlimited.
            limit_clause = f"LIMIT -1 OFFSET {int(offset)}"
        else:
            limit_clause = ""

        query = f"SELECT * FROM ema_documents {where_clause} ORDER BY last_updated_at DESC {limit_clause}"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [EMADocument.from_row(dict(r)) for r in rows]

    def count_documents(
        self,
        types: Optional[List[str]] = None,
        statuses: Optional[List[str]] = None,
        download_statuses: Optional[List[str]] = None,
        keyword: Optional[str] = None,
        updated_since: Optional[str] = None,
    ) -> int:
        """Count documents matching the same filters as get_documents."""
        conditions, params = self._build_filter_conditions(
            types, statuses, download_statuses, keyword, updated_since
        )
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM ema_documents {where_clause}", params)
            return cursor.fetchone()[0]

    def get_filter_options(self) -> Dict[str, List[str]]:
        """Return distinct document types and official statuses for UI dropdowns."""
        options: Dict[str, List[str]] = {"types": [], "statuses": []}
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT DISTINCT document_type FROM ema_documents WHERE document_type != '' ORDER BY document_type"
            )
            options["types"] = [row[0] for row in cursor.fetchall()]
            cursor.execute(
                "SELECT DISTINCT status FROM ema_documents WHERE status != '' ORDER BY status"
            )
            options["statuses"] = [row[0] for row in cursor.fetchall()]
        return options

    def get_last_sync(self) -> Optional[Dict[str, Any]]:
        """Return the most recent sync_history row as a dict, or None."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sync_history ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            try:
                data["summary"] = json.loads(data.get("summary_json") or "{}")
            except json.JSONDecodeError:
                data["summary"] = {}
            data.pop("summary_json", None)
            return data

    def get_summary_counts(self) -> Dict[str, int]:
        """Return counts by document type and download status."""
        counts: Dict[str, int] = {}
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM ema_documents")
            counts["total"] = cursor.fetchone()[0]

            cursor.execute("SELECT download_status, COUNT(*) FROM ema_documents GROUP BY download_status")
            for status, count in cursor.fetchall():
                counts[f"status_{status}"] = count

            cursor.execute("SELECT document_type, COUNT(*) FROM ema_documents GROUP BY document_type")
            for doc_type, count in cursor.fetchall():
                counts[f"type_{doc_type}"] = count
        return counts

    def record_sync_history(self, summary: SyncSummary) -> None:
        """Record sync run into history table."""
        sql = """
            INSERT INTO sync_history (
                timestamp, total_records, new_planned, updated_planned,
                downloaded_success, downloaded_failed, skipped_unchanged,
                duration_seconds, summary_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._get_connection() as conn:
            conn.execute(
                sql,
                (
                    summary.timestamp,
                    summary.total_records_in_feed,
                    summary.new_planned,
                    summary.updated_planned,
                    summary.downloaded_success,
                    summary.downloaded_failed,
                    summary.skipped_unchanged,
                    summary.duration_seconds,
                    json.dumps(summary.to_dict()),
                ),
            )
            conn.commit()
