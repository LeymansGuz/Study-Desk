"""Private, bounded page checkpoints. Cache misses never remove source coverage."""
import hashlib, json, time, zlib
from contextvars import ContextVar
import db
VERSION = 'pages-v2-layout-ocr'
PROGRESS = ContextVar('index_progress', default=None)
MAX_DOCUMENT = 4 * 1024 * 1024
MAX_USER = 128 * 1024 * 1024
MAX_GLOBAL = 1024 * 1024 * 1024

def initialize():
    with db.connect() as c:
        c.execute('CREATE TABLE IF NOT EXISTS index_page_cache(document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,user_id TEXT NOT NULL,stage TEXT NOT NULL,page INTEGER NOT NULL,signature TEXT NOT NULL,payload BLOB NOT NULL,updated REAL NOT NULL,PRIMARY KEY(document_id,stage,page))')
        c.execute('CREATE INDEX IF NOT EXISTS index_cache_owner ON index_page_cache(user_id,updated)')
        c.execute('CREATE TABLE IF NOT EXISTS index_job_details(job_id TEXT PRIMARY KEY REFERENCES index_jobs(id) ON DELETE CASCADE,payload TEXT NOT NULL)')

def signature(digest):
    import document_ocr
    return hashlib.sha256(f'{VERSION}:{digest}:{document_ocr.OCR_TEXT_THRESHOLD}:{document_ocr.MAX_OCR_PAGES}:1.4'.encode()).hexdigest()

def identity(user, course, filename):
    row = db.get_document_by_name(user, course, filename)
    return row['id'] if row else None

def load(document, stage, signature):
    if not document:
        return {}
    initialize()
    with db.connect() as c:
        rows = c.execute('SELECT page,payload FROM index_page_cache WHERE document_id=? AND stage=? AND signature=?', (document, stage, signature)).fetchall()
    result = {}
    for row in rows:
        try:
            result[row['page']] = json.loads(zlib.decompress(row['payload']))
        except (ValueError, zlib.error):
            pass
    return result

def save(document, user, stage, page, signature, payload):
    save_many(document, user, stage, signature, [(page, payload)])

def save_many(document, user, stage, signature, pages):
    if not document:
        return
    rows = []
    for page, payload in pages:
        blob = zlib.compress(json.dumps(payload, ensure_ascii=False).encode(), 3)
        if len(blob) <= MAX_DOCUMENT:
            rows.append((document, user, stage, page, signature, blob, time.time()))
    with db.connect() as c:
        c.execute('DELETE FROM index_page_cache WHERE document_id=? AND signature!=?', (document, signature))
        c.executemany('INSERT INTO index_page_cache VALUES(?,?,?,?,?,?,?) ON CONFLICT(document_id,stage,page) DO UPDATE SET signature=excluded.signature,payload=excluded.payload,updated=excluded.updated', rows)
        for clause, args, limit in [('document_id=?', (document,), MAX_DOCUMENT), ('user_id=?', (user,), MAX_USER), ('1=1', (), MAX_GLOBAL)]:
            total = c.execute('SELECT COALESCE(SUM(length(payload)),0) FROM index_page_cache WHERE ' + clause, args).fetchone()[0]
            if total <= limit:
                continue
            for row in c.execute('SELECT rowid,length(payload) size FROM index_page_cache WHERE ' + clause + ' ORDER BY updated,rowid', args).fetchall():
                c.execute('DELETE FROM index_page_cache WHERE rowid=?', (row['rowid'],))
                total -= row['size']
                if total <= limit:
                    break

def notify(**values):
    callback = PROGRESS.get()
    if callback:
        callback(**values)

def detail(job_id, **values):
    with db.connect() as c:
        row = c.execute('SELECT payload FROM index_job_details WHERE job_id=?', (job_id,)).fetchone()
        payload = json.loads(row[0]) if row else {'timings': {}, 'completed_files': 0}
        now = time.time()
        if values.get('stage') == 'starting':
            payload['phase_started'] = now
        elif values.get('stage') and values['stage'] != payload.get('stage'):
            previous = payload.get('stage')
            if previous and payload.get('phase_started'):
                timings = payload.setdefault('timings', {})
                timings[previous] = round(timings.get(previous, 0) + now - payload['phase_started'], 3)
            payload['phase_started'] = now
        payload.update(values)
        c.execute('INSERT INTO index_job_details VALUES(?,?) ON CONFLICT(job_id) DO UPDATE SET payload=excluded.payload', (job_id, json.dumps(payload)))

def details(job_id):
    with db.connect() as c:
        row = c.execute('SELECT payload FROM index_job_details WHERE job_id=?', (job_id,)).fetchone()
    return json.loads(row[0]) if row else {}
