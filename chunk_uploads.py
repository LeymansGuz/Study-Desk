"""Authenticated, bounded resumable transport; original upload validation remains authoritative."""
from __future__ import annotations
import asyncio, hashlib, json, logging, os, re, shutil, time, uuid
from pathlib import Path
from fastapi import Depends, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
import db
from upload_limits import WORKSPACE_FILES, IMAGE_BYTES, IMAGE_EXTENSIONS
from security import sanitize_filename, ALLOWED_CORPUS_EXTENSIONS
CHUNK_BYTES = 5 * 1024 * 1024
TTL = 3600
ACTIVE = {'receiving', 'processing'}
log = logging.getLogger(__name__)
_tasks = {}
_gate = None
_worker_gate = None
_chunk_slots = None
_maintenance = None
_services = None

class FileSpec(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    size: int = Field(gt=0)

class BatchSpec(BaseModel):
    course_id: str = Field(min_length=1, max_length=100)
    doc_type: str = 'notes'
    request_key: str = Field(default_factory=lambda: uuid.uuid4().hex, pattern='^[0-9a-f]{32}$')
    files: list[FileSpec] = Field(min_length=1, max_length=WORKSPACE_FILES)

def root():
    return db.DB_PATH.parent / 'upload-staging'

def folder(identifier):
    if not re.fullmatch('[0-9a-f]{32}', identifier):
        raise HTTPException(404, 'Upload not found.')
    return root() / identifier

def remove_files(identifier):
    directory = folder(identifier).resolve()
    if not directory.is_relative_to(root().resolve()):
        raise ValueError('Invalid staging directory')
    if directory.exists():
        shutil.rmtree(directory)

def read(identifier, user_id):
    folder(identifier)
    with db.connect() as c:
        row = c.execute('SELECT * FROM upload_batches WHERE id=? AND user_id=?', (identifier, user_id)).fetchone()
    if not row:
        raise HTTPException(404, 'Upload not found or expired. Select your files to restart.')
    return dict(row)

def public(row):
    return {'id': row['id'], 'status': row['status'], 'files': json.loads(row['manifest']), 'offsets': json.loads(row['offsets']), 'chunk_bytes': CHUNK_BYTES, 'expires_in_seconds': TTL, 'result': json.loads(row['result']) if row['result'] else None, 'error': row['error'], 'error_status': row['error_status']}

def cleanup():
    now = time.time()
    with db.connect() as c:
        expired = [r['id'] for r in c.execute("SELECT id FROM upload_batches WHERE status!='processing' AND updated<?", (now - TTL,))]
        for identifier in expired:
            c.execute('DELETE FROM upload_batches WHERE id=?', (identifier,))
        live = {r['id'] for r in c.execute('SELECT id FROM upload_batches')}
    if root().exists():
        for directory in root().iterdir():
            if directory.is_dir() and re.fullmatch('[0-9a-f]{32}', directory.name) and (directory.name not in live) and (directory.name not in _tasks):
                try:
                    remove_files(directory.name)
                except OSError:
                    log.warning('Could not remove an expired upload directory; cleanup will retry.')

async def start():
    global _gate, _worker_gate, _maintenance, _chunk_slots
    _gate = asyncio.Lock()
    _worker_gate = asyncio.Semaphore(1)
    _chunk_slots = asyncio.Semaphore(4)
    with db.connect() as c:
        c.execute("CREATE TABLE IF NOT EXISTS upload_batches(\n            id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,\n            course_id TEXT NOT NULL,doc_type TEXT NOT NULL,manifest TEXT NOT NULL,offsets TEXT NOT NULL,\n            total INTEGER NOT NULL,status TEXT NOT NULL,result TEXT,error TEXT NOT NULL DEFAULT '',\n            error_status INTEGER NOT NULL DEFAULT 0,updated REAL NOT NULL,request_key TEXT)")
        if 'request_key' not in {r['name'] for r in c.execute('PRAGMA table_info(upload_batches)')}:
            c.execute('ALTER TABLE upload_batches ADD COLUMN request_key TEXT')
        c.execute('CREATE UNIQUE INDEX IF NOT EXISTS upload_request_key ON upload_batches(user_id,request_key)')
        c.execute('CREATE INDEX IF NOT EXISTS upload_batches_owner ON upload_batches(user_id,status)')
        c.execute("UPDATE upload_batches SET status='receiving' WHERE status='processing'")
    await asyncio.to_thread(cleanup)

    async def sweep():
        while True:
            await asyncio.sleep(60)
            async with _gate:
                await asyncio.to_thread(cleanup)
    _maintenance = asyncio.create_task(sweep())

async def close():
    if _maintenance:
        _maintenance.cancel()
    tasks = list(_tasks.values())
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, *([_maintenance] if _maintenance else []), return_exceptions=True)
    _tasks.clear()

def append_chunk(identifier, index, offset, payload, digest, row):
    manifest = json.loads(row['manifest'])
    offsets = json.loads(row['offsets'])
    if index < 0 or index >= len(manifest):
        raise HTTPException(404, 'Unknown upload file.')
    expected = min(CHUNK_BYTES, manifest[index]['size'] - offset)
    if offset < 0 or offset > manifest[index]['size'] or len(payload) != expected or (not payload):
        raise HTTPException(400, 'Chunk length does not match the declared file size.')
    if hashlib.sha256(payload).hexdigest() != digest:
        raise HTTPException(422, 'Chunk checksum mismatch. Retry this chunk.')
    path = folder(identifier) / f'{index}.part'
    current = offsets[index]
    if offset < current:
        if offset + len(payload) > current:
            raise HTTPException(409, 'Chunk overlaps uncommitted bytes.')
        with path.open('rb') as stream:
            stream.seek(offset)
            same = hashlib.sha256(stream.read(len(payload))).hexdigest() == digest
        if not same:
            raise HTTPException(409, 'Previously received chunk differs. Restart this upload.')
        return public(row)
    if offset != current:
        raise HTTPException(409, 'Chunk is out of order. Resume from the confirmed offset.')
    with path.open('r+b' if path.exists() else 'w+b') as stream:
        stream.truncate(current)
        stream.seek(current)
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    offsets[index] += len(payload)
    with db.connect() as c:
        c.execute('UPDATE upload_batches SET offsets=?,updated=? WHERE id=?', (json.dumps(offsets), time.time(), identifier))
    return public(read(identifier, row['user_id']))

async def commit(identifier, user, request):
    handles = []
    try:
        async with _worker_gate:
            row = read(identifier, user['id'])
            for index, item in enumerate(json.loads(row['manifest'])):
                path = folder(identifier) / f'{index}.part'
                if path.stat().st_size != item['size']:
                    raise HTTPException(422, 'A staged file is incomplete. Please upload it again.')
                handle = path.open('rb')
                handles.append(handle)
            files = [UploadFile(file=handle, filename=item['name']) for handle, item in zip(handles, json.loads(row['manifest']))]
            result = await _services['upload_workspace_files'](request, course_id=row['course_id'], doc_type=row['doc_type'], files=files, user=user)
            manifest = json.loads(row['manifest'])
            saved = {doc['filename']: doc for doc in db.list_documents(user['id'], [row['course_id']])}
            returned = {doc.filename: doc for doc in result.uploaded}
            for item in manifest:
                document = saved.get(item['name'])
                receipt = returned.get(item['name'])
                path = _services['course_workspace'](user['id'], row['course_id']) / item['name']
                if not document or not receipt or receipt.id != document['id'] or (document['size'] != item['size']) or (not path.is_file()) or (path.stat().st_size != item['size']):
                    raise HTTPException(500, 'The saved files could not be confirmed. Refresh Workspace and retry; existing files are preserved.')
            if result.job_id:
                job = db.get_index_job(result.job_id)
                if not job or job['user_id'] != user['id'] or job['course_id'] != row['course_id']:
                    raise HTTPException(500, 'The processing job could not be confirmed. Refresh Workspace and retry.')
            with db.connect() as c:
                c.execute("UPDATE upload_batches SET status='complete',result=?,updated=? WHERE id=?", (result.model_dump_json(), time.time(), identifier))
    except asyncio.CancelledError:
        with db.connect() as c:
            c.execute("UPDATE upload_batches SET status='receiving',updated=? WHERE id=?", (time.time(), identifier))
        raise
    except Exception as exc:
        code = exc.status_code if isinstance(exc, HTTPException) else 500
        detail = str(exc.detail) if isinstance(exc, HTTPException) else 'Could not finish saving these files. Retry the upload.'
        if code == 500:
            log.exception('Upload finalization failed')
        with db.connect() as c:
            c.execute("UPDATE upload_batches SET status='failed',error=?,error_status=?,updated=? WHERE id=?", (detail, code, time.time(), identifier))
    finally:
        for handle in handles:
            handle.close()
        try:
            if read(identifier, user['id'])['status'] in {'complete', 'failed'}:
                await asyncio.to_thread(remove_files, identifier)
        except HTTPException:
            await asyncio.to_thread(remove_files, identifier)
        _tasks.pop(identifier, None)

def install(app, services):
    global _services
    _services = services
    require_user = services['require_user']

    @app.post('/workspace/uploads', status_code=201, tags=['workspace'])
    async def create(spec: BatchSpec, request: Request, user=Depends(require_user)):
        services['enforce_rate_limit'](request, services['UPLOAD_LIMIT'], 'upload', user_id=user['id'])
        course = db.get_course(user['id'], spec.course_id)
        if not course:
            raise HTTPException(404, 'Unknown course.')
        services['_assert_course_editable'](user, course)
        if spec.doc_type not in services['DOC_TYPES']:
            raise HTTPException(400, 'Unknown document type.')
        if len(spec.files) > services['MAX_BATCH_FILES']:
            raise HTTPException(400, 'Too many files.')
        names = [sanitize_filename(item.name, ALLOWED_CORPUS_EXTENSIONS) for item in spec.files]
        if len(set(names)) != len(names):
            raise HTTPException(400, 'The batch contains the same filename twice.')
        total = sum((item.size for item in spec.files))
        if total > services['MAX_BATCH_BYTES'] or any((item.size > services['MAX_UPLOAD_BYTES'] for item in spec.files)):
            raise HTTPException(413, 'Keep uploads within 50 files and 500 MB total, with at most 200 MB per document.')
        if any(Path(item.name).suffix.lower() in IMAGE_EXTENSIONS and item.size>IMAGE_BYTES for item in spec.files):
            raise HTTPException(413,'Keep each screenshot within 20 MB.')
        __import__('growth_limits').disk(total)
        async with _gate:
            await asyncio.to_thread(cleanup)
            with db.connect() as c:
                c.execute('BEGIN IMMEDIATE')
                prior = c.execute('SELECT * FROM upload_batches WHERE user_id=? AND request_key=?', (user['id'], spec.request_key)).fetchone()
                if prior:
                    expected = [{'name': name, 'size': item.size} for name, item in zip(names, spec.files)]
                    if prior['course_id'] != spec.course_id or prior['doc_type'] != spec.doc_type or json.loads(prior['manifest']) != expected:
                        raise HTTPException(409, 'Upload request identifier was reused for different files.')
                    return public(dict(prior))
                active = c.execute("SELECT COUNT(*),COALESCE(SUM(total),0) FROM upload_batches WHERE user_id=? AND status IN ('receiving','processing')", (user['id'],)).fetchone()
                global_active = c.execute("SELECT COUNT(*) FROM upload_batches WHERE status IN ('receiving','processing')").fetchone()[0]
                if active[0] >= 2 or global_active >= 16:
                    raise HTTPException(429, 'Uploads are busy. Finish an existing batch and retry.')
                if db.user_storage_bytes(user['id']) + active[1] + total > services['_storage_limit'](user):
                    raise HTTPException(413, 'This batch would exceed your storage allowance.')
                stale = c.execute("SELECT id FROM upload_batches WHERE status IN ('complete','failed') AND (user_id=? OR (SELECT COUNT(*) FROM upload_batches)>=128) ORDER BY updated DESC LIMIT -1 OFFSET 8", (user['id'],)).fetchall()
                for old in stale:
                    c.execute('DELETE FROM upload_batches WHERE id=?', (old['id'],))
                identifier = uuid.uuid4().hex
                manifest = [{'name': name, 'size': item.size} for name, item in zip(names, spec.files)]
                c.execute('INSERT INTO upload_batches(id,user_id,course_id,doc_type,manifest,offsets,total,status,updated,request_key) VALUES(?,?,?,?,?,?,?,?,?,?)', (identifier, user['id'], spec.course_id, spec.doc_type, json.dumps(manifest), json.dumps([0] * len(manifest)), total, 'receiving', time.time(), spec.request_key))
            folder(identifier).mkdir(parents=True, exist_ok=False)
        return public(read(identifier, user['id']))

    @app.get('/workspace/uploads/{identifier}', tags=['workspace'])
    async def status(identifier: str, user=Depends(require_user)):
        return public(read(identifier, user['id']))

    @app.put('/workspace/uploads/{identifier}/files/{index}', tags=['workspace'])
    async def chunk(identifier: str, index: int, offset: int, request: Request, user=Depends(require_user)):
        read(identifier, user['id'])
        async with _chunk_slots:
            payload = bytearray()
            async for block in request.stream():
                if len(payload) + len(block) > CHUNK_BYTES:
                    raise HTTPException(413, 'Chunk exceeds 5 MB.')
                payload.extend(block)
            digest = request.headers.get('x-chunk-sha256', '')
            async with _gate:
                row = read(identifier, user['id'])
                if row['status'] != 'receiving':
                    raise HTTPException(409, 'This batch is already being finalized.')
                return await asyncio.to_thread(append_chunk, identifier, index, offset, bytes(payload), digest, row)

    @app.post('/workspace/uploads/{identifier}/complete', status_code=202, tags=['workspace'])
    async def complete(identifier: str, request: Request, user=Depends(require_user)):
        async with _gate:
            row = read(identifier, user['id'])
            if row['status'] != 'receiving':
                return public(row)
            if json.loads(row['offsets']) != [item['size'] for item in json.loads(row['manifest'])]:
                raise HTTPException(409, 'Some chunks are missing. Resume the upload first.')
            with db.connect() as c:
                c.execute("UPDATE upload_batches SET status='processing',updated=? WHERE id=?", (time.time(), identifier))
            _tasks[identifier] = asyncio.create_task(commit(identifier, user, request))
        return public(read(identifier, user['id']))

    @app.delete('/workspace/uploads/{identifier}', status_code=204, tags=['workspace'])
    async def cancel(identifier: str, user=Depends(require_user)):
        async with _gate:
            row = read(identifier, user['id'])
            if row['status'] == 'processing':
                raise HTTPException(409, 'Files are being verified. Wait for completion before cancelling.')
            with db.connect() as c:
                c.execute('DELETE FROM upload_batches WHERE id=?', (identifier,))
            await asyncio.to_thread(remove_files, identifier)
