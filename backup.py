"""Portable backups for the local Study Desk data directory.

A backup contains a consistent SQLite copy plus the user document and local
vector-index trees. Restores are staged and applied on the next process start, so the live
database is never overwritten underneath open connections.
"""
from __future__ import annotations
import logging
import os
import shutil
import sqlite3
import tempfile
import time
import uuid
import zipfile
from pathlib import Path
import db
from retrieval import CHROMA_DIR, USERS_DIR
logger = logging.getLogger(__name__)
DATA_DIR = db.DB_PATH.parent
PENDING_RESTORE = DATA_DIR / 'restore_pending.zip'
RESTORE_ROOT = DATA_DIR / 'restore_extracted'
DEFAULT_BACKUP_DIR = os.getenv('BACKUP_DIR',str(DATA_DIR / 'backups'))
BACKUP_RETENTION_DAYS = int(os.getenv('BACKUP_RETENTION_DAYS', '30'))

def backup_directory() -> Path:
    configured = db.get_app_setting('backup_dir', DEFAULT_BACKUP_DIR)
    return Path(configured).expanduser()

def set_backup_directory(value: str) -> Path:
    raw = (value or '').strip()
    if not raw:
        raise ValueError('Backup folder cannot be empty.')
    path = Path(raw).expanduser()
    if not path.is_absolute():
        raise ValueError('Backup folder must be an absolute path.')
    if path.exists() and (not path.is_dir()):
        raise ValueError('Backup folder is a file.')
    path.mkdir(parents=True, exist_ok=True)
    db.set_app_setting('backup_dir', str(path))
    return path

def create_backup(destination_dir: Path | None=None) -> Path:
    """Create a consistent zip backup in a folder, or in a temporary path."""
    if destination_dir is not None:
        destination_dir = Path(destination_dir).expanduser()
        destination_dir.mkdir(parents=True, exist_ok=True)
        archive = destination_dir / (time.strftime('study-desk-backup-%Y%m%d-%H%M%S-')+uuid.uuid4().hex[:8]+'.zip')
    else:
        descriptor, name = tempfile.mkstemp(prefix='study-desk-', suffix='.zip')
        os.close(descriptor)
        archive = Path(name)
    snapshot = Path(tempfile.mkdtemp(prefix='study-desk-backup-')) / 'app.db'
    source = sqlite3.connect(db.DB_PATH)
    target = sqlite3.connect(snapshot)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    try:
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(snapshot, 'app.db')
            for directory, arcroot in ((USERS_DIR, 'users'), (CHROMA_DIR, 'chroma')):
                if directory.exists():
                    for path in directory.rglob('*'):
                        if path.is_file():
                            zf.write(path, f'{arcroot}/{path.relative_to(directory)}')
    except Exception:
        archive.unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(snapshot.parent, ignore_errors=True)
    if destination_dir is not None:
        prune_backups(destination_dir)
    return archive

def prune_backups(directory: Path | None=None) -> int:
    directory = directory or backup_directory()
    if not directory.is_dir():
        return 0
    cutoff = time.time() - BACKUP_RETENTION_DAYS * 86400
    removed = 0
    archives = sorted(directory.glob('study-desk-backup-*.zip'), key=lambda p: p.stat().st_mtime, reverse=True)
    for index, archive in enumerate(archives):
        try:
            if (index >= 10 or archive.stat().st_mtime < cutoff) and (not archive.is_symlink()) and (archive.resolve().parent == directory.resolve()):
                archive.unlink()
                removed += 1
        except OSError:
            continue
    return removed

def latest_backup() -> Path | None:
    directory = backup_directory()
    if not directory.is_dir():
        return None
    archives = sorted(directory.glob('study-desk-backup-*.zip'), key=lambda item: item.stat().st_mtime, reverse=True)
    return archives[0] if archives else None

def verify_latest() -> dict[str, object]:
    archive = latest_backup()
    if not archive:
        raise ValueError('No backup exists yet.')
    with zipfile.ZipFile(archive) as zf:
        bad = zf.testzip()
        if bad:
            raise ValueError(f'Backup archive is corrupt at {bad}.')
        with tempfile.TemporaryDirectory(prefix='study-desk-verify-') as temp:
            extracted = Path(temp) / 'app.db'
            with zf.open('app.db') as source, open(extracted, 'wb') as target:
                shutil.copyfileobj(source, target)
            connection = sqlite3.connect(extracted)
            try:
                integrity = connection.execute('PRAGMA integrity_check').fetchone()[0]
                if integrity != 'ok':
                    raise ValueError(f'SQLite integrity check failed: {integrity}')
                tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
                required = {'users', 'courses', 'documents', 'learning_objects'}
                missing = required - tables
                if missing:
                    raise ValueError('Backup is missing tables: ' + ', '.join(sorted(missing)))
                user_count = connection.execute('SELECT COUNT(*) FROM users').fetchone()[0]
            finally:
                connection.close()
    return {'filename': archive.name, 'size': archive.stat().st_size, 'users': int(user_count), 'verified_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}

def _safe_extract(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(archive) as zf:
        import deletion_journal, growth_limits
        if 'app.db' not in zf.namelist():
            raise ValueError('Backup does not contain app.db.')
        deletion_journal.validate_archive(zf)
        members = zf.infolist()
        if len(members) > 200000:
            raise ValueError('Backup contains too many files.')
        growth_limits.disk(sum((member.file_size for member in members)), destination)
        for member in members:
            if member.filename.split('/')[0] not in {'app.db', 'users', 'chroma'}:
                raise ValueError('Unknown backup content.')
            target = (destination / member.filename).resolve()
            if not target.is_relative_to(root):
                raise ValueError('Unsafe path in backup.')
            zf.extract(member, destination)
    if not (destination / 'app.db').is_file():
        raise ValueError('Backup does not contain app.db.')

def stage_restore(data: bytes) -> None:
    """Validate an uploaded zip and stage it for the next restart."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(delete=False, suffix='.zip', dir=DATA_DIR) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    try:
        extracted = Path(tempfile.mkdtemp(prefix='study-desk-check-', dir=DATA_DIR))
        try:
            _safe_extract(temporary, extracted)
            connection = sqlite3.connect(extracted / 'app.db')
            try:
                connection.execute('SELECT 1 FROM users LIMIT 1').fetchone()
            finally:
                connection.close()
        finally:
            shutil.rmtree(extracted, ignore_errors=True)
        temporary.replace(PENDING_RESTORE)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

def apply_pending_restore() -> bool:
    """Apply a staged restore. Must run before the database is opened."""
    if not PENDING_RESTORE.exists():
        return False
    stamp = time.strftime('%Y%m%d-%H%M%S')
    previous = DATA_DIR / f'pre_restore_{stamp}'
    extracted = Path(tempfile.mkdtemp(prefix='study-desk-restore-', dir=DATA_DIR))
    try:
        _safe_extract(PENDING_RESTORE, extracted)
        previous.mkdir(parents=True, exist_ok=True)
        for current, name in ((db.DB_PATH, 'app.db'), (Path(str(db.DB_PATH) + '-wal'), 'app.db-wal'), (Path(str(db.DB_PATH) + '-shm'), 'app.db-shm'), (USERS_DIR, 'users'), (CHROMA_DIR, 'chroma')):
            if current.exists():
                shutil.move(str(current), str(previous / name))
        shutil.copy2(extracted / 'app.db', db.DB_PATH)
        for name, destination in (('users', USERS_DIR), ('chroma', CHROMA_DIR)):
            source = extracted / name
            if source.exists():
                shutil.copytree(source, destination)
        PENDING_RESTORE.unlink(missing_ok=True)
        logger.info('Applied backup restore; previous data kept at %s', previous)
        return True
    finally:
        shutil.rmtree(extracted, ignore_errors=True)
