"""SQLite persistence for accounts, sessions, courses, and documents."""
from __future__ import annotations
import json
import os
import re
import sqlite3
import secrets
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator
PROJECT_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv('APP_DB_PATH', 'data/app.db'))
if not DB_PATH.is_absolute():
    DB_PATH = PROJECT_DIR / DB_PATH
SQLITE_TIMEOUT_SECONDS = float(os.getenv('SQLITE_TIMEOUT_SECONDS', '30'))
COMMIT_CONNECTION = ContextVar('generation_commit_connection', default=None)

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    existing = COMMIT_CONNECTION.get()
    if existing is not None:
        yield existing
        return
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=SQLITE_TIMEOUT_SECONDS)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys = ON')
    connection.execute(f'PRAGMA busy_timeout = {int(SQLITE_TIMEOUT_SECONDS * 1000)}')
    connection.execute('PRAGMA journal_mode = WAL')
    try:
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()

def init_db() -> None:
    with connect() as db:
        db.executescript("\n            CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT NOT NULL UNIQUE,name TEXT NOT NULL,username TEXT NOT NULL UNIQUE,created_at TEXT NOT NULL,is_active INTEGER NOT NULL DEFAULT 1,is_admin INTEGER NOT NULL DEFAULT 1,is_verified INTEGER NOT NULL DEFAULT 1,deleting INTEGER NOT NULL DEFAULT 0);\n\n            CREATE TABLE IF NOT EXISTS courses(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,name TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(user_id,name));\n            CREATE INDEX IF NOT EXISTS idx_courses_user ON courses(user_id);\n\n            CREATE TABLE IF NOT EXISTS documents (\n                id TEXT PRIMARY KEY,\n                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,\n                course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,\n                filename TEXT NOT NULL,\n                sha256 TEXT NOT NULL,\n                size INTEGER NOT NULL,\n                page_count INTEGER NOT NULL DEFAULT 0,\n                doc_type TEXT NOT NULL DEFAULT 'notes',syllabus_enabled INTEGER NOT NULL DEFAULT 1,\n                created_at TEXT NOT NULL,\n                UNIQUE(course_id, filename)\n            );\n            CREATE INDEX IF NOT EXISTS idx_documents_user ON documents(user_id);\n            CREATE INDEX IF NOT EXISTS idx_documents_course ON documents(course_id);\n\n            CREATE TABLE IF NOT EXISTS usage_events (\n                id INTEGER PRIMARY KEY AUTOINCREMENT,\n                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,\n                kind TEXT NOT NULL,\n                created_at TEXT NOT NULL\n            );\n            CREATE INDEX IF NOT EXISTS idx_usage_user ON usage_events(user_id);\n            CREATE INDEX IF NOT EXISTS idx_usage_created ON usage_events(created_at);\n\n            CREATE TABLE IF NOT EXISTS token_usage (\n                id INTEGER PRIMARY KEY AUTOINCREMENT,\n                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,\n                input_tokens INTEGER NOT NULL DEFAULT 0,\n                output_tokens INTEGER NOT NULL DEFAULT 0,\n                created_at TEXT NOT NULL\n            );\n            CREATE INDEX IF NOT EXISTS idx_token_usage_user ON token_usage(user_id);\n            CREATE INDEX IF NOT EXISTS idx_token_usage_created ON token_usage(created_at);\n\n            CREATE TABLE IF NOT EXISTS study_records (\n                id TEXT PRIMARY KEY,\n                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,\n                kind TEXT NOT NULL,\n                ref_id TEXT NOT NULL,\n                question TEXT NOT NULL,\n                question_type TEXT NOT NULL DEFAULT 'short_answer',\n                difficulty TEXT NOT NULL DEFAULT 'medium',\n                options TEXT NOT NULL DEFAULT '[]',\n                answer_key TEXT NOT NULL DEFAULT '',\n                solution TEXT NOT NULL DEFAULT '',\n                marking_guide TEXT NOT NULL DEFAULT '',\n                source_refs TEXT NOT NULL DEFAULT '[]',\n                source_summary TEXT NOT NULL DEFAULT '[]',\n                attempts INTEGER NOT NULL DEFAULT 0,\n                first_marks INTEGER NOT NULL DEFAULT 0,\n                latest_marks INTEGER NOT NULL DEFAULT 0,\n                max_marks INTEGER NOT NULL DEFAULT 0,\n                is_correct INTEGER NOT NULL DEFAULT 0,\n                status TEXT NOT NULL DEFAULT 'open',\n                fingerprint TEXT NOT NULL DEFAULT '',figure_json TEXT NOT NULL DEFAULT 'null',\n                created_at TEXT NOT NULL,\n                updated_at TEXT NOT NULL\n            );\n            CREATE INDEX IF NOT EXISTS idx_study_records_user\n                ON study_records(user_id, updated_at);\n\n            CREATE TABLE IF NOT EXISTS flashcards (\n                id TEXT PRIMARY KEY,\n                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,\n                record_id TEXT NOT NULL,\n                front TEXT NOT NULL,\n                back TEXT NOT NULL,\n                source_summary TEXT NOT NULL DEFAULT '[]',\n                interval_days INTEGER NOT NULL DEFAULT 0,\n                next_review_at TEXT NOT NULL,\n                review_count INTEGER NOT NULL DEFAULT 0,\n                last_reviewed_at TEXT,\n                status TEXT NOT NULL DEFAULT 'active',\n                created_at TEXT NOT NULL,\n                UNIQUE(user_id, record_id)\n            );\n            CREATE INDEX IF NOT EXISTS idx_flashcards_user_due\n                ON flashcards(user_id, status, next_review_at);\n\n            CREATE TABLE IF NOT EXISTS app_settings (\n                key TEXT PRIMARY KEY,\n                value TEXT NOT NULL,\n                updated_at TEXT NOT NULL\n            );\n\n            CREATE TABLE IF NOT EXISTS index_jobs (\n                id TEXT PRIMARY KEY,\n                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,\n                course_id TEXT NOT NULL,\n                filenames TEXT NOT NULL,\n                doc_type TEXT NOT NULL DEFAULT 'notes',\n                status TEXT NOT NULL DEFAULT 'queued',\n                message TEXT NOT NULL DEFAULT '',\n                chunks INTEGER NOT NULL DEFAULT 0,\n                progress INTEGER NOT NULL DEFAULT 0,\n                created_at TEXT NOT NULL,\n                updated_at TEXT NOT NULL\n            );\n            CREATE INDEX IF NOT EXISTS idx_index_jobs_user\n                ON index_jobs(user_id, created_at);\n            \n\n            CREATE TABLE IF NOT EXISTS user_settings(user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,theme TEXT NOT NULL DEFAULT 'light',attempts_before_reveal INTEGER NOT NULL DEFAULT 3,updated_at TEXT NOT NULL);\n            ;")
        db.executescript('\n            CREATE TABLE IF NOT EXISTS pipeline_exposures (\n                id TEXT PRIMARY KEY,\n                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,\n                scope_key TEXT NOT NULL,\n                skill_id TEXT NOT NULL,\n                question TEXT NOT NULL,\n                chunk_ids_json TEXT NOT NULL,\n                created_at TEXT NOT NULL\n            );\n            CREATE INDEX IF NOT EXISTS idx_pipeline_exposures_scope\n                ON pipeline_exposures(user_id, scope_key, created_at DESC);\n            CREATE TABLE IF NOT EXISTS extraction_manifests (\n                user_id TEXT NOT NULL,\n                course_id TEXT NOT NULL,\n                filename TEXT NOT NULL,\n                manifest_json TEXT NOT NULL,\n                PRIMARY KEY(user_id, course_id, filename)\n            );\n            CREATE TABLE IF NOT EXISTS curriculum_maps (\n                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,\n                scope_json TEXT NOT NULL,\n                version TEXT NOT NULL,\n                map_json TEXT NOT NULL,\n                created_at TEXT NOT NULL,\n                PRIMARY KEY(user_id, scope_json, version)\n            );\n        ;')
    import spaced_review
    with connect() as connection:
        spaced_review.initialize(connection)
    import learning_store
    learning_store.init_schema()
    import observability
    observability.initialize()
    import token_budget
    token_budget.initialize()
    import monitoring
    monitoring.initialize()
    import study_persistence
    study_persistence.initialize()
    import retention
    retention.initialize()

def publish_index(user_id: str, collection: str, manifests: list[dict[str, Any]], *, full: bool) -> None:
    """Commit an index pointer and its extraction manifest together."""
    with connect() as connection:
        if full:
            connection.execute('DELETE FROM extraction_manifests WHERE user_id = ?', (user_id,))
        for manifest in manifests:
            connection.execute('INSERT OR REPLACE INTO extraction_manifests VALUES (?, ?, ?, ?)', (user_id, manifest['course_id'], manifest['filename'], json.dumps(manifest)))
        for key, value in ((f'index_collection:{user_id}', collection), (f'corpus_revision:{user_id}', uuid.uuid4().hex)):
            connection.execute('INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at', (key, value, utc_now()))

def bump_corpus_revision(user_id: str) -> None:
    set_app_setting(f'corpus_revision:{user_id}', uuid.uuid4().hex)

def save_curriculum_map(user_id: str, course_ids: list[str], version: str, sections: list[dict[str, Any]]) -> None:
    scope = json.dumps(sorted(course_ids))
    with connect() as connection:
        connection.execute('INSERT OR REPLACE INTO curriculum_maps VALUES (?, ?, ?, ?, ?)', (user_id, scope, version, json.dumps(sections), utc_now()))
        connection.execute('DELETE FROM curriculum_maps WHERE user_id=? AND scope_json=? AND version NOT IN (SELECT version FROM curriculum_maps WHERE user_id=? AND scope_json=? ORDER BY created_at DESC LIMIT 3)', (user_id, scope, user_id, scope))

def extraction_coverage(user_id: str, course_ids: list[str] | None=None) -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute('SELECT course_id, manifest_json FROM extraction_manifests WHERE user_id = ?', (user_id,)).fetchall()
    return [json.loads(row['manifest_json']) for row in rows if not course_ids or row['course_id'] in course_ids]

def recent_exposures(user_id: str, scope_key: str, limit: int=80) -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute('SELECT * FROM pipeline_exposures WHERE user_id = ? AND scope_key = ? ORDER BY created_at DESC LIMIT ?', (user_id, scope_key, min(500, limit))).fetchall()
    return [{**dict(row), 'chunk_ids': json.loads(row['chunk_ids_json'])} for row in rows]

def record_exposure(user_id: str, scope_key: str, skill_id: str, question: str, chunk_ids: list[str]) -> None:
    from generation_control import defer
    if defer(lambda: record_exposure(user_id, scope_key, skill_id, question, chunk_ids)):
        return
    'Reserve generated items too, so skips and restarts do not repeat them.'
    with connect() as connection:
        connection.execute('INSERT INTO pipeline_exposures VALUES (?, ?, ?, ?, ?, ?, ?)', (uuid.uuid4().hex, user_id, scope_key, skill_id, question, json.dumps(chunk_ids), utc_now()))
        connection.execute('DELETE FROM pipeline_exposures WHERE user_id = ? AND id NOT IN (SELECT id FROM pipeline_exposures WHERE user_id = ? ORDER BY created_at DESC LIMIT 2000)', (user_id, user_id))

def skill_exposure_counts(user_id: str, scope_key: str) -> dict[str, int]:
    with connect() as connection:
        rows = connection.execute('SELECT skill_id, COUNT(*) AS n FROM pipeline_exposures WHERE user_id = ? AND scope_key = ? GROUP BY skill_id', (user_id, scope_key)).fetchall()
    return {row['skill_id']: row['n'] for row in rows}

def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None

def healthcheck() -> bool:
    with connect() as db:
        return db.execute('SELECT 1').fetchone()[0] == 1

def get_app_setting(key: str, default: str='') -> str:
    with connect() as db:
        row = db.execute('SELECT value FROM app_settings WHERE key = ?', (key,)).fetchone()
    return str(row['value']) if row else default

def set_app_setting(key: str, value: str) -> None:
    with connect() as db:
        db.execute('\n            INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)\n            ON CONFLICT(key) DO UPDATE SET value = excluded.value,\n                updated_at = excluded.updated_at\n            ', (key, value, utc_now()))

def get_settings(user_id):
    with connect() as c:
        row = c.execute('SELECT theme,attempts_before_reveal FROM user_settings WHERE user_id=?', (user_id,)).fetchone()
    return dict(row) if row else {'theme': 'light', 'attempts_before_reveal': 3}

def update_settings(user_id, theme, attempts_before_reveal=3):
    with connect() as c:
        c.execute('INSERT INTO user_settings VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET theme=excluded.theme,attempts_before_reveal=excluded.attempts_before_reveal,updated_at=excluded.updated_at', (user_id, theme, attempts_before_reveal, utc_now()))
    return get_settings(user_id)

def user_storage_bytes(user_id: str) -> int:
    with connect() as db:
        row = db.execute('SELECT COALESCE(SUM(size), 0) AS total FROM documents WHERE user_id = ?', (user_id,)).fetchone()
    return int(row['total']) if row else 0

def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    return _row(row)

def create_course(user_id: str, name: str) -> dict[str, Any]:
    course_id = uuid.uuid4().hex
    now = utc_now()
    with connect() as db:
        db.execute('INSERT INTO courses (id, user_id, name, created_at) VALUES (?, ?, ?, ?)', (course_id, user_id, name.strip(), now))
    return {'id': course_id, 'user_id': user_id, 'name': name.strip(), 'created_at': now}

def list_courses(user_id: str) -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute('SELECT * FROM courses WHERE user_id = ? ORDER BY name COLLATE NOCASE', (user_id,)).fetchall()
    return [dict(row) for row in rows]

def get_course(user_id: str, course_id: str) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute('SELECT * FROM courses WHERE id = ? AND user_id = ?', (course_id, user_id)).fetchone()
    return _row(row)

def get_document_any(document_id: str) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute('SELECT * FROM documents WHERE id = ?', (document_id,)).fetchone()
    return dict(row) if row else None

def list_course_documents(course_id: str) -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute('SELECT * FROM documents WHERE course_id = ? ORDER BY filename COLLATE NOCASE', (course_id,)).fetchall()
    return [dict(row) for row in rows]

def get_course_any(course_id: str) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute('SELECT * FROM courses WHERE id = ?', (course_id,)).fetchone()
    return dict(row) if row else None

def delete_course(user_id: str, course_id: str) -> bool:
    with connect() as db:
        cursor = db.execute('DELETE FROM courses WHERE id = ? AND user_id = ?', (course_id, user_id))
    return cursor.rowcount > 0

def add_index_job(user_id: str, course_id: str, filenames: list[str], doc_type: str) -> dict[str, Any]:
    job_id = uuid.uuid4().hex
    now = utc_now()
    with connect() as db:
        db.execute('INSERT INTO index_jobs (id, user_id, course_id, filenames, doc_type, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)', (job_id, user_id, course_id, json.dumps(filenames, separators=(',', ':')), doc_type, now, now))
    return {'id': job_id, 'user_id': user_id, 'course_id': course_id, 'filenames': filenames, 'doc_type': doc_type, 'status': 'queued'}

def update_index_job(job_id: str, status: str, message: str='', chunks: int=0, progress: int | None=None) -> None:
    with connect() as db:
        if progress is None:
            db.execute('UPDATE index_jobs SET status = ?, message = ?, chunks = ?, updated_at = ? WHERE id = ?', (status, message[:1000], chunks, utc_now(), job_id))
        else:
            db.execute('UPDATE index_jobs SET status = ?, message = ?, chunks = ?, progress = ?, updated_at = ? WHERE id = ?', (status, message[:1000], chunks, max(0, min(100, int(progress))), utc_now(), job_id))

def get_index_job(job_id: str) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute('SELECT * FROM index_jobs WHERE id = ?', (job_id,)).fetchone()
    if not row:
        return None
    item = dict(row)
    try:
        item['filenames'] = json.loads(item.get('filenames') or '[]')
    except (TypeError, ValueError):
        item['filenames'] = []
    return item

def active_index_job(user_id: str, course_id: str) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute("SELECT * FROM index_jobs WHERE user_id = ? AND course_id = ? AND status IN ('queued', 'running') ORDER BY created_at DESC LIMIT 1", (user_id, course_id)).fetchone()
    if not row:
        return None
    item = dict(row)
    try:
        item['filenames'] = json.loads(item.get('filenames') or '[]')
    except (TypeError, ValueError):
        item['filenames'] = []
    return item

def list_index_jobs(user_id: str, limit: int=20) -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute("SELECT * FROM index_jobs WHERE user_id = ? ORDER BY CASE status WHEN 'running' THEN 0 WHEN 'queued' THEN 1 ELSE 2 END, created_at DESC, rowid DESC LIMIT ?", (user_id, max(1, min(100, limit)))).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        try:
            item['filenames'] = json.loads(item.get('filenames') or '[]')
        except (TypeError, ValueError):
            item['filenames'] = []
        items.append(item)
    return items

def requeue_index_jobs() -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute("SELECT * FROM index_jobs WHERE status IN ('queued', 'running') ORDER BY created_at").fetchall()
        db.execute("UPDATE index_jobs SET status = 'queued', progress = 0, updated_at = ? WHERE status = 'running'", (utc_now(),))
    items = []
    for row in rows:
        item = dict(row)
        try:
            item['filenames'] = json.loads(item.get('filenames') or '[]')
        except (TypeError, ValueError):
            item['filenames'] = []
        items.append(item)
    return items

def get_document_by_name(user_id: str, course_id: str, filename: str) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute('SELECT * FROM documents WHERE user_id = ? AND course_id = ? AND filename = ?', (user_id, course_id, filename)).fetchone()
    return dict(row) if row else None

def update_document_location(user_id: str, document_id: str, *, filename: str, course_id: str) -> bool:
    with connect() as db:
        cursor = db.execute('UPDATE documents SET filename = ?, course_id = ? WHERE id = ? AND user_id = ?', (filename, course_id, document_id, user_id))
    return cursor.rowcount > 0

def add_document(*, user_id: str, course_id: str, filename: str, sha256: str, size: int, page_count: int) -> dict[str, Any]:
    document_id = uuid.uuid4().hex
    now = utc_now()
    with connect() as db:
        db.execute('INSERT INTO documents (id, user_id, course_id, filename, sha256, size, page_count, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (document_id, user_id, course_id, filename, sha256, size, page_count, now))
    return {'id': document_id, 'user_id': user_id, 'course_id': course_id, 'filename': filename, 'sha256': sha256, 'size': size, 'page_count': page_count, 'created_at': now}

def list_documents(user_id: str, course_ids: list[str] | None=None) -> list[dict[str, Any]]:
    with connect() as db:
        if course_ids:
            placeholders = ','.join(('?' for _ in course_ids))
            rows = db.execute(f'\n                SELECT d.*, c.name AS course_name\n                FROM documents d JOIN courses c ON c.id = d.course_id\n                WHERE d.user_id = ? AND d.course_id IN ({placeholders})\n                ORDER BY c.name COLLATE NOCASE, d.filename COLLATE NOCASE\n                ', (user_id, *course_ids)).fetchall()
        else:
            rows = db.execute('\n                SELECT d.*, c.name AS course_name\n                FROM documents d JOIN courses c ON c.id = d.course_id\n                WHERE d.user_id = ?\n                ORDER BY c.name COLLATE NOCASE, d.filename COLLATE NOCASE\n                ', (user_id,)).fetchall()
    return [dict(row) for row in rows]

def sync_documents(user_id: str, records: list[dict[str, Any]], *, prune: bool=True, update_doc_type: bool=True) -> None:
    """Reconcile the document registry while preserving stable document ids."""
    now = utc_now()
    with connect() as db:
        existing_rows = db.execute('SELECT id, course_id, filename FROM documents WHERE user_id = ?', (user_id,)).fetchall()
        existing = {(row['course_id'], row['filename']): row['id'] for row in existing_rows}
        keep_ids: set[str] = set()
        for record in records:
            key = (record['course_id'], record['filename'])
            document_id = existing.get(key) or uuid.uuid4().hex
            keep_ids.add(document_id)
            if key in existing:
                if update_doc_type:
                    db.execute('\n                        UPDATE documents\n                        SET sha256 = ?, size = ?, page_count = ?, doc_type = ?\n                        WHERE id = ? AND user_id = ?\n                        ', (record['sha256'], record['size'], record.get('page_count', 0), record.get('doc_type', 'notes'), document_id, user_id))
                else:
                    db.execute('\n                        UPDATE documents\n                        SET sha256 = ?, size = ?, page_count = ?\n                        WHERE id = ? AND user_id = ?\n                        ', (record['sha256'], record['size'], record.get('page_count', 0), document_id, user_id))
            else:
                db.execute('\n                    INSERT INTO documents\n                    (id, user_id, course_id, filename, sha256, size, page_count, doc_type, created_at)\n                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)\n                    ', (document_id, user_id, record['course_id'], record['filename'], record['sha256'], record['size'], record.get('page_count', 0), record.get('doc_type', 'notes'), now))
        for document_id in existing.values():
            if prune and document_id not in keep_ids:
                db.execute('DELETE FROM documents WHERE id = ? AND user_id = ?', (document_id, user_id))

def get_document(user_id: str, document_id: str) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute('SELECT * FROM documents WHERE id = ? AND user_id = ?', (document_id, user_id)).fetchone()
    return _row(row)

def update_document_type(user_id: str, document_id: str, doc_type: str) -> bool:
    with connect() as db:
        cursor = db.execute('UPDATE documents SET doc_type = ? WHERE id = ? AND user_id = ?', (doc_type, document_id, user_id))
    return cursor.rowcount > 0

def delete_document(user_id: str, filename: str, course_id: str) -> bool:
    with connect() as db:
        cursor = db.execute('DELETE FROM documents WHERE user_id = ? AND course_id = ? AND filename = ?', (user_id, course_id, filename))
    return cursor.rowcount > 0

def log_usage(user_id: str, kind: str) -> None:
    with connect() as db:
        db.execute('INSERT INTO usage_events (user_id, kind, created_at) VALUES (?, ?, ?)', (user_id, kind, utc_now()))
        import observability
        observability.event(db, user_id, kind)

def record_token_usage(user_id: str, input_tokens: int, output_tokens: int, cost_usd: float | None=None) -> None:
    input_tokens = max(0, int(input_tokens or 0))
    output_tokens = max(0, int(output_tokens or 0))
    if not input_tokens and (not output_tokens):
        return
    import observability
    cost_usd = observability.charge(input_tokens, output_tokens) if cost_usd is None else cost_usd
    with connect() as db:
        db.execute('INSERT INTO token_usage (user_id, input_tokens, output_tokens, created_at) VALUES (?, ?, ?, ?)', (user_id, input_tokens, output_tokens, utc_now()))
        observability.accumulate(db, user_id, input_tokens, output_tokens, cost_usd)

def clear_token_usage(user_id: str | None=None) -> int:
    with connect() as db:
        if user_id:
            cursor = db.execute('DELETE FROM token_usage WHERE user_id = ?', (user_id,))
        else:
            cursor = db.execute('DELETE FROM token_usage')
        count = cursor.rowcount
        for table in ['billing_totals', 'billing_daily', 'model_daily', 'operations', 'model_calls']:
            db.execute(f'DELETE FROM {table}' + (' WHERE user_id=?' if user_id else ''), (user_id,) if user_id else ())
    return count

def save_study_record(user_id: str, record: dict[str, Any]) -> dict[str, Any]:
    """Create or update one practice/exam question result and its mistake card."""
    now = utc_now()
    record_id = str(record['id'])
    is_correct = bool(record.get('is_correct'))
    attempts = int(record.get('attempts', 0))
    needs_review = not is_correct or attempts > 1
    status = 'open' if needs_review else 'resolved'
    source_summary = record.get('source_summary') or []
    options = record.get('options') or []
    source_refs = record.get('source_refs') or []
    fingerprint = str(record.get('fingerprint') or '')
    with connect() as conn:
        previous = conn.execute("SELECT id FROM study_records WHERE user_id = ? AND status = 'open' AND fingerprint = ? AND fingerprint <> '' AND id <> ?", (user_id, fingerprint, record_id)).fetchall()
        conn.execute('\n            INSERT INTO study_records\n            (id, user_id, kind, ref_id, question, question_type, difficulty,\n             options, answer_key, solution, marking_guide, source_refs,\n             source_summary, attempts, first_marks, latest_marks, max_marks,\n             is_correct, status, fingerprint, created_at, updated_at)\n            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n            ON CONFLICT(id) DO UPDATE SET\n                attempts = excluded.attempts,\n                first_marks = excluded.first_marks,\n                latest_marks = excluded.latest_marks,\n                max_marks = excluded.max_marks,\n                is_correct = excluded.is_correct,\n                status = excluded.status,\n                answer_key = excluded.answer_key,\n                solution = excluded.solution,\n                marking_guide = excluded.marking_guide,\n                source_summary = excluded.source_summary,\n                updated_at = excluded.updated_at\n            ', (record_id, user_id, record.get('kind', 'practice'), record.get('ref_id', ''), record.get('question', ''), record.get('question_type', 'short_answer'), record.get('difficulty', 'medium'), json.dumps(options, separators=(',', ':')), record.get('answer_key', ''), record.get('solution', ''), record.get('marking_guide', ''), json.dumps(source_refs, separators=(',', ':')), json.dumps(source_summary, separators=(',', ':')), int(record.get('attempts', 0)), int(record.get('first_marks', 0)), int(record.get('latest_marks', 0)), int(record.get('max_marks', 0)), 1 if is_correct else 0, status, fingerprint, now, now))
        conn.execute('UPDATE study_records SET figure_json=? WHERE id=? AND user_id=?', (json.dumps(record.get('figure'), separators=(',', ':')), record_id, user_id))
        if is_correct and previous:
            previous_ids = [row['id'] for row in previous]
            placeholders = ','.join(('?' for _ in previous_ids))
            conn.execute(f"UPDATE study_records SET status = 'resolved', updated_at = ? WHERE user_id = ? AND id IN ({placeholders})", (now, user_id, *previous_ids))
            conn.execute(f"UPDATE flashcards SET status = 'resolved' WHERE user_id = ? AND record_id IN ({placeholders})", (user_id, *previous_ids))
        if not needs_review:
            conn.execute("UPDATE flashcards SET status = 'resolved' WHERE user_id = ? AND record_id = ?", (user_id, record_id))
        if needs_review:
            back = '\n\n'.join((part.strip() for part in (f"**Answer:** {record.get('answer_key', '')}", record.get('marking_guide', '') or record.get('solution', '')) if part.strip()))
            conn.execute("\n                INSERT INTO flashcards\n                (id, user_id, record_id, front, back, source_summary,\n                 interval_days, next_review_at, due_date, review_count, status, created_at)\n                VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, 0, 'active', ?)\n                ON CONFLICT(user_id, record_id) DO UPDATE SET\n                    front = excluded.front,\n                    back = excluded.back,\n                    source_summary = excluded.source_summary,\n                    interval_days = CASE WHEN flashcards.status='active' THEN flashcards.interval_days ELSE 0 END,\n                    next_review_at = CASE WHEN flashcards.status='active' THEN flashcards.next_review_at ELSE excluded.next_review_at END,\n                    due_date = CASE WHEN flashcards.status='active' THEN flashcards.next_review_at ELSE excluded.next_review_at END,\n                    fsrs_json = CASE WHEN flashcards.status='active' THEN flashcards.fsrs_json ELSE '' END,\n                    stability = CASE WHEN flashcards.status='active' THEN flashcards.stability ELSE NULL END,\n                    difficulty = CASE WHEN flashcards.status='active' THEN flashcards.difficulty ELSE NULL END,\n                    status = 'active'\n                ", (uuid.uuid4().hex, user_id, record_id, record.get('question', ''), back, json.dumps(source_summary, separators=(',', ':')), now, now, now))
    return get_study_record(user_id, record_id) or {}

def _record_row(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    try:
        item['figure'] = json.loads(item.pop('figure_json', 'null') or 'null')
    except (TypeError, ValueError):
        item['figure'] = None
    for key in ('options', 'source_refs', 'source_summary'):
        try:
            item[key] = json.loads(item.get(key) or '[]')
        except (TypeError, ValueError):
            item[key] = []
    return item

def get_study_record(user_id: str, record_id: str) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute('SELECT * FROM study_records WHERE id = ? AND user_id = ?', (record_id, user_id)).fetchone()
    return _record_row(row) if row else None

def progress_counts(user_id: str) -> dict[str, int]:
    with connect() as db:
        records = db.execute('SELECT COUNT(*) AS count FROM study_records WHERE user_id = ?', (user_id,)).fetchone()['count']
        cards = db.execute('SELECT COUNT(*) AS count FROM flashcards WHERE user_id = ?', (user_id,)).fetchone()['count']
    return {'records': int(records), 'flashcards': int(cards)}

def purge_exam_progress(user_id: str) -> dict[str, int]:
    """Delete legacy exam records, their cards, and exam usage events."""
    with connect() as db:
        record_ids = [row['id'] for row in db.execute("SELECT id FROM study_records WHERE user_id = ? AND kind = 'exam'", (user_id,)).fetchall()]
        if record_ids:
            placeholders = ','.join(('?' for _ in record_ids))
            cards = db.execute(f'DELETE FROM flashcards WHERE user_id = ? AND record_id IN ({placeholders})', (user_id, *record_ids)).rowcount
        else:
            cards = 0
        records = db.execute("DELETE FROM study_records WHERE user_id = ? AND kind = 'exam'", (user_id,)).rowcount
        usage = db.execute("DELETE FROM usage_events WHERE user_id = ? AND kind LIKE 'exam%'", (user_id,)).rowcount
    return {'records': int(records), 'flashcards': int(cards), 'usage': int(usage)}

def reset_progress(user_id: str) -> dict[str, int]:
    """Hard-delete one user's study history and flashcards; keep all other data."""
    with connect() as db:
        counts = {'records': int(db.execute('SELECT COUNT(*) AS count FROM study_records WHERE user_id = ?', (user_id,)).fetchone()['count']), 'flashcards': int(db.execute('SELECT COUNT(*) AS count FROM flashcards WHERE user_id = ?', (user_id,)).fetchone()['count'])}
        db.execute('DELETE FROM flashcards WHERE user_id = ?', (user_id,))
        db.execute('DELETE FROM study_records WHERE user_id = ?', (user_id,))
        db.execute('DELETE FROM learning_outcomes WHERE user_id=?', (user_id,))
    return counts

def list_study_records(user_id: str, limit: int=100, mistakes_only: bool=False) -> list[dict[str, Any]]:
    query = 'SELECT * FROM study_records WHERE user_id = ?'
    params: list[Any] = [user_id]
    if mistakes_only:
        query += " AND status = 'open'"
    query += ' ORDER BY updated_at DESC, rowid DESC LIMIT ?'
    params.append(max(1, min(500, limit)))
    with connect() as db:
        rows = db.execute(query, params).fetchall()
    return [_record_row(row) for row in rows]

def list_exam_records(user_id: str, exam_id: str) -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute("SELECT * FROM study_records WHERE user_id = ? AND kind = 'exam' AND ref_id = ? ORDER BY updated_at ASC", (user_id, exam_id)).fetchall()
    return [_record_row(row) for row in rows]

def resolve_all_mistakes(user_id: str) -> int:
    with connect() as db:
        cursor = db.execute("UPDATE study_records SET status = 'resolved', updated_at = ? WHERE user_id = ? AND status = 'open'", (utc_now(), user_id))
        db.execute("UPDATE flashcards SET status = 'resolved' WHERE user_id = ? AND record_id IN (SELECT id FROM study_records WHERE user_id = ? AND status = 'resolved')", (user_id, user_id))
    return cursor.rowcount

def resolve_study_record(user_id: str, record_id: str) -> bool:
    with connect() as db:
        cursor = db.execute("UPDATE study_records SET status = 'resolved', updated_at = ? WHERE id = ? AND user_id = ?", (utc_now(), record_id, user_id))
        db.execute("UPDATE flashcards SET status = 'resolved' WHERE record_id = ? AND user_id = ?", (record_id, user_id))
    return cursor.rowcount > 0

def list_due_flashcards(user_id: str, limit: int=50) -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute("\n            SELECT f.*,r.figure_json FROM flashcards f LEFT JOIN study_records r ON r.id=f.record_id AND r.user_id=f.user_id\n            WHERE f.user_id = ? AND f.status = 'active' AND f.next_review_at <= ?\n            ORDER BY f.next_review_at ASC LIMIT ?\n            ", (user_id, utc_now(), max(1, min(200, limit)))).fetchall()
    cards = []
    for row in rows:
        item = dict(row)
        try:
            item['figure'] = json.loads(item.pop('figure_json', 'null') or 'null')
        except (TypeError, ValueError):
            item['figure'] = None
        try:
            item['source_summary'] = json.loads(item.get('source_summary') or '[]')
        except (TypeError, ValueError):
            item['source_summary'] = []
        cards.append(item)
    return cards

def review_flashcard(user_id: str, card_id: str, rating: str) -> dict[str, Any] | None:
    now = datetime.now(timezone.utc)
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM flashcards WHERE id = ? AND user_id = ?', (card_id, user_id)).fetchone()
        if not row:
            return None
        if rating == 'mastered':
            db.execute("UPDATE flashcards SET status = 'resolved', review_count = review_count + 1, last_reviewed_at = ? WHERE id = ? AND user_id = ?", (utc_now(), card_id, user_id))
            db.execute("UPDATE study_records SET status = 'resolved', updated_at = ? WHERE id = ? AND user_id = ?", (utc_now(), row['record_id'], user_id))
            next_review = None
        else:
            from spaced_review import schedule
            scheduled, days = schedule(row, rating, now)
            next_review = scheduled.due.isoformat(timespec='seconds')
            db.execute('UPDATE flashcards SET interval_days = ?, next_review_at = ?, due_date=?,stability=?,difficulty=?,fsrs_json=?, review_count = review_count + 1, last_reviewed_at = ? WHERE id = ? AND user_id = ?', (days, next_review, next_review, scheduled.stability, scheduled.difficulty, json.dumps(scheduled.to_dict()), utc_now(), card_id, user_id))
    with connect() as db:
        updated = db.execute('SELECT * FROM flashcards WHERE id = ? AND user_id = ?', (card_id, user_id)).fetchone()
    item = dict(updated) if updated else None
    if item:
        try:
            item['source_summary'] = json.loads(item.get('source_summary') or '[]')
        except (TypeError, ValueError):
            item['source_summary'] = []
    return item

def study_dashboard(user_id: str) -> dict[str, Any]:
    with connect() as db:
        totals = db.execute("\n            SELECT COUNT(*) AS total,\n                   SUM(CASE WHEN kind = 'practice' THEN 1 ELSE 0 END) AS practice,\n                   SUM(CASE WHEN kind = 'exam' THEN 1 ELSE 0 END) AS exam,\n                   SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) AS correct,\n                   SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) AS mistakes,\n                   COALESCE(SUM(latest_marks), 0) AS latest_marks,\n                   COALESCE(SUM(first_marks), 0) AS first_marks,\n                   COALESCE(SUM(max_marks), 0) AS max_marks\n            FROM study_records WHERE user_id = ? AND kind = 'practice'\n            ", (user_id,)).fetchone()
        due = db.execute("SELECT COUNT(*) AS count FROM flashcards WHERE user_id = ? AND status = 'active' AND next_review_at <= ?", (user_id, utc_now())).fetchone()['count']
        reviewed_today = db.execute("SELECT COUNT(*) AS count FROM flashcards WHERE user_id = ? AND last_reviewed_at IS NOT NULL AND substr(last_reviewed_at, 1, 10) = date('now')", (user_id,)).fetchone()['count']
        activity = db.execute("\n            SELECT day FROM (\n                SELECT substr(last_reviewed_at, 1, 10) AS day FROM flashcards\n                WHERE user_id = ? AND last_reviewed_at IS NOT NULL\n                UNION\n                SELECT substr(updated_at, 1, 10) AS day FROM study_records\n                WHERE user_id = ? AND kind = 'practice' \n            ) WHERE day IS NOT NULL ORDER BY day DESC\n            ", (user_id, user_id)).fetchall()
        weak = db.execute("\n            SELECT question_type, COUNT(*) AS total,\n                   SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) AS correct,\n                   COALESCE(SUM(latest_marks), 0) AS marks,\n                   COALESCE(SUM(max_marks), 0) AS max_marks\n            FROM study_records WHERE user_id = ? AND kind = 'practice'\n            GROUP BY question_type ORDER BY total DESC\n            ", (user_id,)).fetchall()
    total = int(totals['total'] or 0)
    max_marks = int(totals['max_marks'] or 0)
    days = [row['day'] for row in activity]
    streak = 0
    cursor = datetime.now(timezone.utc).date()
    if days and days[0] != cursor.isoformat():
        cursor -= timedelta(days=1)
    day_set = set(days)
    while cursor.isoformat() in day_set:
        streak += 1
        cursor -= timedelta(days=1)
    return {'total': total, 'practice': int(totals['practice'] or 0), 'exam': int(totals['exam'] or 0), 'correct': int(totals['correct'] or 0), 'accuracy': round(int(totals['correct'] or 0) / total * 100, 1) if total else 0, 'mistakes': int(totals['mistakes'] or 0), 'flashcards_due': int(due or 0), 'reviewed_today': int(reviewed_today or 0), 'streak_days': int(streak), 'marks_earned': int(totals['latest_marks'] or 0), 'first_marks_earned': int(totals['first_marks'] or 0), 'max_marks': max_marks, 'mark_percent': round(int(totals['latest_marks'] or 0) / max_marks * 100, 1) if max_marks else None, 'weak_by_type': [{'question_type': row['question_type'], 'total': int(row['total']), 'correct': int(row['correct'] or 0), 'mark_percent': round(int(row['marks'] or 0) / int(row['max_marks']) * 100, 1) if int(row['max_marks'] or 0) else None} for row in weak]}

def usage_counts(user_id: str | None=None) -> dict[str, int]:
    with connect() as db:
        if user_id:
            rows = db.execute('SELECT kind, SUM(count) AS count FROM usage_totals WHERE user_id = ? GROUP BY kind', (user_id,)).fetchall()
        else:
            rows = db.execute('SELECT kind, SUM(count) AS count FROM usage_totals GROUP BY kind').fetchall()
    return {row['kind']: int(row['count']) for row in rows}
