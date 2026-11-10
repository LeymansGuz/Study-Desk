"""Bounded local study history and diagnostic retention."""
import asyncio
import logging
from logging.handlers import RotatingFileHandler
import db
LEARNING = {'tutor': 10, 'explain': 10, 'path': 10, 'exam': 10, 'bank': 500, 'quarantine': 100, 'benchmark_run': 8,'revision_sheet':20,'recall':10,'study_plan':1,'syllabus_plan':20,'annotation':200,'local_job':20,'course_guide':20,'card_proposal':10}

def initialize():
    with db.connect() as c:
        for kind in ('tutor','explain','path','exam'):
            c.execute(f'DROP TRIGGER IF EXISTS retain_learning_{kind}')
        for kind, limit in LEARNING.items():
            if kind in {'tutor','explain','path','exam'}:continue
            c.execute(f"CREATE TRIGGER IF NOT EXISTS retain_learning_{kind} AFTER INSERT ON learning_objects WHEN NEW.kind='{kind}' BEGIN DELETE FROM learning_objects WHERE kind='{kind}' AND user_id=NEW.user_id AND rowid NOT IN (SELECT rowid FROM learning_objects WHERE kind='{kind}' AND user_id=NEW.user_id ORDER BY updated DESC,rowid DESC LIMIT {limit}); END")
        for table, limit in [('courses', 100), ('documents', 500), ('study_records', 500), ('flashcards', 200)]:
            if table in {'courses', 'documents'}:
                c.execute(f"CREATE TRIGGER IF NOT EXISTS capacity_{table} BEFORE INSERT ON {table} WHEN (SELECT COUNT(*) FROM {table})>={limit} BEGIN SELECT RAISE(ABORT,'capacity_limit: local {table} storage reached'); END")
        c.execute('CREATE TRIGGER IF NOT EXISTS retain_records AFTER INSERT ON study_records BEGIN DELETE FROM study_records WHERE rowid NOT IN (SELECT rowid FROM study_records ORDER BY created_at DESC LIMIT 500); END')

def sweep():
    with db.connect() as c:
        for table, col, limit in [('operations', 'started_at', 50000), ('model_calls', 'created_at', 100000), ('generation_events', 'created_at', 20000), ('quality_events', 'created', 10000)]:
            c.execute(f'DELETE FROM {table} WHERE rowid NOT IN (SELECT rowid FROM {table} ORDER BY rowid DESC LIMIT ?)', (limit,))
        c.execute('DELETE FROM flashcards WHERE record_id NOT IN (SELECT id FROM study_records)')
        c.execute('DELETE FROM flashcards WHERE rowid NOT IN (SELECT rowid FROM flashcards ORDER BY rowid DESC LIMIT 200)')
        c.execute('DELETE FROM learning_receipts WHERE rowid NOT IN (SELECT rowid FROM learning_receipts ORDER BY updated DESC LIMIT 1000)')
        c.execute("DELETE FROM index_jobs WHERE status IN ('done','failed') AND rowid NOT IN (SELECT rowid FROM index_jobs ORDER BY rowid DESC LIMIT 100)")
    import learning_store
    learning_store.prune_sessions()
    import growth_limits
    growth_limits.sweep_files()

def ensure_disk_budget(*args, **kwargs):
    import growth_limits
    growth_limits.disk()

def check_documents(user_id, course_id, additional=1, **kwargs):
    from fastapi import HTTPException
    if len(db.list_documents(user_id)) + additional > 500:
        raise HTTPException(409, 'Local document limit reached (500).')

def configure_logs():
    handler = RotatingFileHandler(db.DB_PATH.parent / 'server-events.log', maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s'))
    logging.getLogger().addHandler(handler)

async def worker():
    while True:
        try:
            await asyncio.to_thread(sweep)
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.getLogger(__name__).exception('Local retention failed')
        await asyncio.sleep(300)

def limits_report():
    return [{'item': k, 'kept': v} for k, v in LEARNING.items()]
