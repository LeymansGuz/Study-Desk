"""Additional byte/age ceilings for disposable runtime artifacts."""
import shutil, time, os
from pathlib import Path
import db
MAX_SOURCE_BYTES = 2 * 1024 ** 4
MAX_CHUNKS_DOCUMENT = 10000
MAX_CHUNKS_USER = 50000

def initialize():
    with db.connect() as c:
        c.executescript(f"CREATE TRIGGER IF NOT EXISTS capacity_source_bytes BEFORE INSERT ON documents WHEN (SELECT COALESCE(SUM(size),0) FROM documents)+NEW.size>{MAX_SOURCE_BYTES} BEGIN SELECT RAISE(ABORT,'capacity_limit: global source storage reached'); END;")

def disk(additional=0, path=None):
    from fastapi import HTTPException
    base = Path(path or db.DB_PATH.parent)
    base.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(base)
    reserve = max(int(os.getenv('APP_MIN_FREE_DISK_BYTES', str(1024 ** 3))), int(usage.total * float(os.getenv('APP_MIN_FREE_DISK_PERCENT', '20')) / 100))
    if usage.free - additional < reserve:
        raise HTTPException(507, 'Storage reserve reached. New uploads/exports are paused to protect existing documents; contact the owner.')

def chunks(user, course, filename, count):
    if count > MAX_CHUNKS_DOCUMENT:
        raise ValueError('This document exceeds the 10,000-chunk indexing capacity. Split the source document; its original file is preserved.')
    disk(count * 4096)
    with db.connect() as c:
        existing = c.execute("SELECT COALESCE(SUM(COALESCE(json_extract(manifest_json,'$.chunk_count'),0)),0) FROM extraction_manifests WHERE user_id=? AND NOT(course_id=? AND filename=?)", (user, course, filename)).fetchone()[0]
        legacy = c.execute("SELECT COUNT(*) FROM extraction_manifests WHERE user_id=? AND json_extract(manifest_json,'$.chunk_count') IS NULL", (user,)).fetchone()[0]
    if legacy:
        import retrieval
        collection = retrieval._get_collection(user)
        old = collection.get(where={'$and': [{'course_id': course}, {'source_file': filename}]}, include=['metadatas'])
        existing = collection.count() - len(old.get('ids') or [])
    if existing + count > MAX_CHUNKS_USER:
        raise ValueError('This account exceeds the 50,000-chunk indexing capacity. Remove unused indexed documents before adding more; originals are preserved.')

def sweep_files():
    root = db.DB_PATH.parent.resolve()
    directory = root / 'export-temp'
    if directory.exists():
        for file in directory.glob('study-export-*.zip'):
            if file.is_file() and (not file.is_symlink()) and (file.resolve().parent == directory.resolve()) and (file.stat().st_mtime < time.time() - 3600):
                file.unlink(missing_ok=True)
    previous = sorted((p for p in root.glob('pre_restore_*') if p.is_dir() and (not p.is_symlink())), key=lambda p: p.stat().st_mtime, reverse=True)
    for index, path in enumerate(previous):
        if (index >= 2 or path.stat().st_mtime < time.time() - 30 * 86400) and path.resolve().parent == root:
            shutil.rmtree(path)
