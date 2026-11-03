"""Per-user, per-course ChromaDB ingestion and retrieval with page lineage.

Storage layout:
    data/users/<user_id>/courses/<course_id>/<files>

Each user gets an isolated Chroma collection. Course ids are stored in chunk
metadata so a full-course exam can select one or several courses.
"""
from __future__ import annotations
from pathlib import Path
from functools import lru_cache
import hashlib
import logging
import os
import re
import threading
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import chromadb
from dotenv import load_dotenv
from langsmith import traceable
from pypdf import PdfReader
from security import MAX_PDF_PAGES, MAX_UPLOAD_BYTES, extract_office_text, sanitize_text
import db
logger = logging.getLogger(__name__)
_PROJECT_DIR = Path(__file__).resolve().parent
for _env_path in (Path(__file__).resolve().parent / '.env',):
    if _env_path.is_file():
        load_dotenv(_env_path, override=False)
CHROMA_DIR = Path(os.getenv('CHROMA_DIR', 'data/chroma'))
if not CHROMA_DIR.is_absolute():
    CHROMA_DIR = _PROJECT_DIR / CHROMA_DIR
USERS_DIR = Path(os.getenv('USERS_DIR', 'data/users'))
if not USERS_DIR.is_absolute():
    USERS_DIR = _PROJECT_DIR / USERS_DIR
TOP_K = int(os.getenv('RETRIEVAL_TOP_K', '4'))
MIN_RELEVANCE_SCORE = float(os.getenv('MIN_RELEVANCE_SCORE', '0.32'))
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 80
PAGE_MARKER = re.compile('<!--\\s*(?:page|slide)\\s*:\\s*(\\d+)\\s*-->', re.IGNORECASE)
HEADING = re.compile('^#\\s+(.+)$', re.MULTILINE)
INGEST_LOCK = threading.Lock()
import weakref
_USER_INGEST_LOCKS = weakref.WeakValueDictionary()
_USER_LOCK_GUARD = threading.Lock()

def _user_ingest_lock(user):
    with _USER_LOCK_GUARD:
        value = _USER_INGEST_LOCKS.get(user)
        if value is None:
            value = threading.RLock()
            _USER_INGEST_LOCKS[user] = value
        return value
from contextvars import ContextVar
_EXTRACTION_CONTEXT = ContextVar('extraction_context', default=(None, None, None))

def user_workspace(user_id: str) -> Path:
    return USERS_DIR / user_id

def course_workspace(user_id: str, course_id: str) -> Path:
    user = db.get_user_by_id(user_id)
    if not user or user.get('deleting'):
        from fastapi import HTTPException
        raise HTTPException(403, 'This account is no longer available for study work.')
    return user_workspace(user_id) / 'courses' / course_id

def collection_name(user_id: str) -> str:
    safe = re.sub('[^A-Za-z0-9_-]', '_', user_id)
    return f'user_{safe}'

@lru_cache(maxsize=4)
def _client():
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_DIR))

def chroma_heartbeat() -> int:
    return int(_client().heartbeat())

def _get_collection(user_id: str):
    user = db.get_user_by_id(user_id)
    if not user or user.get('deleting'):
        from fastapi import HTTPException
        raise HTTPException(403, 'This account is not available for retrieval.')
    return _client().get_or_create_collection(name=db.get_app_setting(f'index_collection:{user_id}') or collection_name(user_id), metadata={'hnsw:space': 'cosine'})

def _course_scopes(user_id: str, course_ids: list[str] | None) -> list[tuple[str, list[str] | None]]:
    return [(user_id, course_ids or None)]

def _query_collection(owner_id: str, query: str, k: int, threshold: float, course_ids: list[str] | None, doc_types: list[str] | None) -> list[dict[str, Any]]:
    collection = _get_collection(owner_id)
    count = collection.count()
    if count == 0:
        return []
    filters = []
    if course_ids:
        filters.append({'course_id': {'$in': course_ids}})
    if doc_types:
        filters.append({'doc_type': {'$in': doc_types}})
    where = None
    if len(filters) == 1:
        where = filters[0]
    elif filters:
        where = {'$and': filters}
    result = collection.query(query_texts=[query], n_results=max(1, min(k, count)), where=where, include=['documents', 'metadatas', 'distances'])
    documents = (result.get('documents') or [[]])[0]
    metadatas = (result.get('metadatas') or [[]])[0]
    distances = (result.get('distances') or [[]])[0]
    rows = []
    visibility = {}
    for text, metadata, distance in zip(documents, metadatas, distances):
        if not _visible(metadata, visibility):
            continue
        score = max(0.0, min(1.0, 1.0 - float(distance)))
        if score < threshold:
            continue
        rows.append(_source_row(0, text, metadata, score))
    return rows

def _merge_sources(sources: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique = []
    for source in sorted(sources, key=lambda item: item.get('score', 0), reverse=True):
        key = source.get('chunk_id') or f"{source.get('course_id')}:{source.get('source_file')}:{source.get('page')}:{source.get('text', '')[:80]}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(source)
    unique = unique[:limit]
    for index, source in enumerate(unique, start=1):
        source['ref'] = f'S{index}'
    return unique

@traceable(run_type='retriever', name='chroma_search')
def search(query: str, user_id: str, k: int | None=None, min_score: float | None=None, course_ids: list[str] | None=None, doc_types: list[str] | None=None) -> list[dict[str, Any]]:
    """Retrieve relevant chunks from owned and currently shared courses."""
    threshold = MIN_RELEVANCE_SCORE if min_score is None else min_score
    limit = max(1, k or TOP_K)
    sources: list[dict[str, Any]] = []
    for owner_id, scope_ids in _course_scopes(user_id, course_ids):
        sources.extend(_query_collection(owner_id, query, limit, threshold, scope_ids, doc_types))
    merged = _merge_sources(sources, limit)
    logger.info('Retrieved %s chunks for user=%s across %s scope(s)', len(merged), user_id[:8], len(_course_scopes(user_id, course_ids)))
    return merged

def _tokens(text: str) -> set[str]:
    return set(re.findall('[^\\W_]+', (text or '').lower(), re.UNICODE))

def relabel_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**item, 'ref': f'S{index}'} for index, item in enumerate(sources, 1)]

def _all_records(collection, where=None, include=None, include_embeddings=False):
    """Read the complete filtered inventory instead of a silent first-page cap."""
    offset = 0
    visibility = {}
    while True:
        fields = list(include or ['documents', 'metadatas'])
        if include_embeddings:
            fields.append('embeddings')
        result = collection.get(where=where, include=fields, limit=256, offset=offset)
        ids = result.get('ids') or []
        if not ids:
            break
        documents = result.get('documents') or [''] * len(ids)
        metadata = result.get('metadatas') or [{}] * len(ids)
        if include_embeddings:
            embeddings = result.get('embeddings')
            for row in zip(ids, documents, metadata, embeddings if embeddings is not None else [None] * len(ids)):
                if _visible(row[2], visibility):
                    yield row
        else:
            for row in zip(ids, documents, metadata):
                if _visible(row[2], visibility):
                    yield row
        offset += len(ids)
        if len(ids) < 256:
            break

def inventory(user_id: str, course_ids=None, doc_types=None) -> list[dict[str, Any]]:
    rows = []
    for owner, courses in _course_scopes(user_id, course_ids):
        filters = []
        if courses:
            filters.append({'course_id': {'$in': courses}})
        if doc_types:
            filters.append({'doc_type': {'$in': doc_types}})
        where = filters[0] if len(filters) == 1 else {'$and': filters} if filters else None
        for chunk_id, text, metadata in _all_records(_get_collection(owner), where):
            rows.append(_source_row(0, text, {**(metadata or {}), 'chunk_id': chunk_id}, 0.5))
    return rows

def update_file_doc_type(user_id: str, course_id: str, filename: str, doc_type: str) -> int:
    """Update doc_type metadata on already-indexed chunks for one file."""
    with INGEST_LOCK:
        collection = _get_collection(user_id)
        result = collection.get(where={'$and': [{'course_id': course_id}, {'source_file': filename}]}, include=['metadatas'])
        ids = result.get('ids') or []
        metadatas = result.get('metadatas') or []
        if not ids:
            return 0
        updated = []
        for metadata in metadatas:
            item = dict(metadata or {})
            item['doc_type'] = doc_type
            updated.append(item)
        collection.update(ids=ids, metadatas=updated)
        db.bump_corpus_revision(user_id)
        logger.info('Updated doc_type for %s chunks of %s', len(ids), filename)
        return len(ids)

def update_file_identity(user_id: str, course_id: str, filename: str, *, new_course_id: str | None=None, new_course_name: str | None=None, new_filename: str | None=None) -> int:
    """Update course/file metadata after a file rename or move."""
    with INGEST_LOCK:
        collection = _get_collection(user_id)
        result = collection.get(where={'$and': [{'course_id': course_id}, {'source_file': filename}]}, include=['metadatas'])
        ids = result.get('ids') or []
        metadatas = result.get('metadatas') or []
        if not ids:
            return 0
        updated = []
        for metadata in metadatas:
            item = dict(metadata or {})
            if new_course_id:
                item['course_id'] = new_course_id
            if new_course_name:
                item['course_name'] = new_course_name
            if new_filename:
                item['source_file'] = new_filename
            updated.append(item)
        collection.update(ids=ids, metadatas=updated)
        db.bump_corpus_revision(user_id)
        return len(ids)

def update_course_name(user_id: str, course_id: str, course_name: str) -> int:
    """Keep Chroma course_name metadata in sync after an admin rename."""
    with INGEST_LOCK:
        collection = _get_collection(user_id)
        result = collection.get(where={'course_id': course_id}, include=['metadatas'])
        ids = result.get('ids') or []
        metadatas = result.get('metadatas') or []
        if not ids:
            return 0
        updated = []
        for metadata in metadatas:
            item = dict(metadata or {})
            item['course_name'] = course_name
            updated.append(item)
        collection.update(ids=ids, metadatas=updated)
        db.bump_corpus_revision(user_id)
        logger.info('Updated course_name for %s chunks of %s', len(ids), course_id)
        return len(ids)

def _sample_collection(owner_id: str, course_ids: list[str] | None, doc_types: list[str] | None) -> list[tuple[str, dict[str, Any]]]:
    collection = _get_collection(owner_id)
    if collection.count() == 0:
        return []
    filters = []
    if course_ids:
        filters.append({'course_id': {'$in': course_ids}})
    if doc_types:
        filters.append({'doc_type': {'$in': doc_types}})
    where = None
    if len(filters) == 1:
        where = filters[0]
    elif filters:
        where = {'$and': filters}
    grouped: dict[tuple[str, str], list[tuple[str, dict[str, Any]]]] = {}
    for _, text, metadata in _all_records(collection, where):
        metadata = metadata or {}
        key = (str(metadata.get('course_id', '')), str(metadata.get('source_file', 'unknown')))
        grouped.setdefault(key, []).append((text or '', metadata))
    selected: list[tuple[str, dict[str, Any]]] = []
    for key in sorted(grouped):
        chunks = sorted(grouped[key], key=lambda item: (item[1].get('page', 1), item[1].get('chunk_index', 0)))
        indices = sorted({0, len(chunks) // 2, len(chunks) - 1})
        selected.extend((chunks[index] for index in indices if chunks[index][0].strip()))
    return selected

def course_sources(user_id: str, course_ids: list[str] | None=None, limit: int=24, doc_types: list[str] | None=None) -> list[dict[str, Any]]:
    """Sample across owned and currently shared course documents."""
    selected: list[tuple[str, dict[str, Any]]] = []
    for owner_id, scope_ids in _course_scopes(user_id, course_ids):
        selected.extend(_sample_collection(owner_id, scope_ids, doc_types))
    if len(selected) > limit:
        step = len(selected) / limit
        selected = [selected[int(index * step)] for index in range(limit)]
    sources = [_source_row(index + 1, text, metadata, 0.5) for index, (text, metadata) in enumerate(selected)]
    logger.info('Selected %s chunks across %s course documents for user=%s', len(sources), len({(item[1].get('course_id'), item[1].get('source_file')) for item in selected}), user_id[:8])
    return sources

def _source_row(index: int, text: str, metadata: dict[str, Any] | None, score: float) -> dict[str, Any]:
    metadata = metadata or {}
    clean_text = sanitize_text(text or '', max_chars=4000)
    return {'ref': f'S{index}', 'text': clean_text, 'excerpt': clean_text if len(clean_text) <= 650 else clean_text[:647].rstrip() + '...', 'source_file': metadata.get('source_file', 'unknown'), 'source_title': metadata.get('source_title', metadata.get('source_file', 'Course material')), 'page': metadata.get('page', 1), 'chunk_index': int(metadata.get('chunk_index', 0)), 'kind': metadata.get('kind', 'note'), 'doc_type': metadata.get('doc_type', 'notes'), 'chunk_id': metadata.get('chunk_id', ''), 'course_id': metadata.get('course_id', ''), 'course_name': metadata.get('course_name', ''), 'score': round(score, 4), 'quality_review_required': bool(metadata.get('quality_review_required', False))}

def format_context(sources: list[dict[str, Any]], max_chars: int=11000) -> str:
    if not sources:
        return 'No supporting course evidence is available. Do not invent course coverage.'
    blocks = []
    for source in sources:
        text = sanitize_text(source['text'], max_chars=4000)
        course = f"{source.get('course_name')} — " if source.get('course_name') else ''
        block = f"[{source['ref']}] {course}{source['source_title']} (page {source['page']}, {source['kind']}):\n{text}"
        if sum((len(value) + 2 for value in blocks)) + len(block) > max_chars:
            continue
        blocks.append(block)
    return '\n\n'.join(blocks)

def pack_sources(sources: list[dict[str, Any]], max_chars: int=10000) -> list[dict[str, Any]]:
    """The returned manifest contains only complete blocks that will be shown."""
    packed, used = ([], 0)
    seen = set()
    for source in sources:
        if source['chunk_id'] in seen:
            continue
        size = len(format_context([source], max_chars=100000)) + 2
        if used + size > max_chars:
            continue
        packed.append(source)
        seen.add(source['chunk_id'])
        used += size
    return relabel_sources(packed)

def format_lineage(sources: list[dict[str, Any]], used_refs: list[str] | None=None) -> str:
    if not sources:
        return ''
    wanted = set(used_refs or [])
    selected = [source for source in sources if not wanted or source['ref'] in wanted]
    if not selected:
        selected = sources
    lines = []
    for source in selected:
        course = f"{source.get('course_name')} · " if source.get('course_name') else ''
        lines.append(f"- **[{source['ref']}]** {course}{source['source_title']} — page {source['page']} (`{source['source_file']}`)")
    return '\n\n**Source lineage**\n' + '\n'.join(lines)

def ingest_user(user_id: str, courses: list[dict[str, Any]], doc_types: dict[tuple[str, str], str] | None=None) -> dict[str, Any]:
    """Rebuild one user's collection from their per-course folders."""
    with _user_ingest_lock(user_id):
        return _ingest_user_locked(user_id, courses, doc_types or {})

def _extract_index_file(path, user_id, course_id, course_name, doc_type):
    manifest = {'course_id': course_id, 'filename': path.name}
    import index_cache
    with path.open('rb') as handle:
        digest = hashlib.file_digest(handle, 'sha256').hexdigest()
    document = index_cache.identity(user_id, course_id, path.name)
    token = _EXTRACTION_CONTEXT.set((document, user_id, index_cache.signature(digest)))
    try:
        chunks = _chunks_for_file(path, user_id, course_id, course_name, doc_type, manifest)
    finally:
        _EXTRACTION_CONTEXT.reset(token)
    if not chunks:
        raise ValueError(f'No usable text extracted from {path.name}; previous index retained.')
    import growth_limits
    growth_limits.chunks(user_id, course_id, path.name, len(chunks))
    page_numbers = sorted({chunk['metadata']['page'] for chunk in chunks})
    manifest.setdefault('page_count', max(page_numbers, default=0))
    manifest.setdefault('pages', [{'page': number, 'status': 'text'} for number in page_numbers])
    manifest['indexed_pages'] = page_numbers
    manifest['chunk_count'] = len(chunks)
    manifest['extraction_signature'] = index_cache.signature(digest)
    manifest['status'] = 'partial' if any((row['status'] not in {'text', 'ocr'} for row in manifest['pages'])) or len(page_numbers) < manifest['page_count'] else 'text_indexed'
    record = {'course_id': course_id, 'course_name': course_name, 'filename': path.name, 'sha256': digest, 'size': path.stat().st_size, 'page_count': manifest['page_count'], 'chunks': len(chunks), 'pages': page_numbers, 'doc_type': doc_type}
    return (chunks, record, manifest)

def prune_index_versions(user_id):
    client = _client()
    base = collection_name(user_id)
    active = db.get_app_setting(f'index_collection:{user_id}') or base
    candidates = [c for c in client.list_collections() if c.name == base or c.name.startswith(base + '_v_')]
    inactive = sorted((c for c in candidates if c.name != active), key=lambda c: ((c.metadata or {}).get('created_at', 0), c.name), reverse=True)
    for collection in inactive[2:]:
        if collection.name != active:
            client.delete_collection(collection.name)

@lru_cache(maxsize=16)
def _published_tokens(user, revision):
    import json
    with db.connect() as c:
        rows = c.execute('SELECT manifest_json FROM extraction_manifests WHERE user_id=?', (user,)).fetchall()
    return frozenset((json.loads(row[0]).get('publication_id') for row in rows))

def _visible(metadata, visibility):
    token = (metadata or {}).get('publication_id')
    if not token:
        return True
    user = metadata.get('user_id', '')
    if user not in visibility:
        visibility[user] = _published_tokens(user, db.get_app_setting(f'corpus_revision:{user}'))
    return token in visibility[user]

def _append_document(user, chunks, manifest):
    """New documents become visible only after all chunks pass the count check."""
    collection = _get_collection(user)
    token = uuid.uuid4().hex
    previous = collection.get(where={'$and': [{'course_id': manifest['course_id']}, {'source_file': manifest['filename']}]}, include=['metadatas'])
    visibility = {}
    stale = [identifier for identifier, metadata in zip(previous.get('ids') or [], previous.get('metadatas') or []) if not _visible(metadata, visibility)]
    if stale:
        collection.delete(ids=stale)
    rows = [{**row, 'id': row['id'] + '_' + token[:10], 'metadata': {**row['metadata'], 'chunk_id': row['id'] + '_' + token[:10], 'publication_id': token}} for row in chunks]
    ids = [row['id'] for row in rows]
    try:
        for start in range(0, len(rows), 256):
            batch = rows[start:start + 256]
            collection.add(ids=[r['id'] for r in batch], documents=[r['text'] for r in batch], metadatas=[r['metadata'] for r in batch])
        import index_cache
        index_cache.notify(stage='publication', pages_done=0, pages_total=0)
        found = collection.get(ids=ids, include=['metadatas'])['ids']
        if set(found) != set(ids):
            raise ValueError('Document index count check failed.')
        manifest['publication_id'] = token
        db.publish_index(user, collection.name, [manifest], full=False)
    except Exception:
        collection.delete(ids=ids)
        raise
    return len(rows)

def _publish_chunks(user_id, chunks, manifests, *, full=False, replacements=None):
    """Stage a complete snapshot; readers retain the prior version on failure.

    Old snapshots remain available to in-flight readers and for recovery. Never
    delete the serving collection before its replacement has been validated.
    """
    client = _client()
    name = f'{collection_name(user_id)}_v_{uuid.uuid4().hex}'
    staged = client.create_collection(name=name, metadata={'hnsw:space': 'cosine', 'created_at': time.time()})
    try:
        import index_cache
        index_cache.notify(stage='index_copy', pages_done=0, pages_total=0)
        pending = list(chunks)
        if not full:
            for chunk_id, text, metadata, embedding in _all_records(_get_collection(user_id), include_embeddings=True):
                identity = ((metadata or {}).get('course_id'), (metadata or {}).get('source_file'))
                if identity not in (replacements or set()):
                    pending.append({'id': chunk_id, 'text': text, 'metadata': metadata, 'embedding': embedding})
        __import__('growth_limits').disk(len(pending) * 4096)
        for start in range(0, len(pending), 256):
            batch = pending[start:start + 256]
            for reuse in (False, True):
                subset = [row for row in batch if (row.get('embedding') is not None) == reuse]
                if not subset:
                    continue
                index_cache.notify(stage='index_copy' if reuse else 'embedding', pages_done=0, pages_total=0)
                kwargs = {'embeddings': [row['embedding'] for row in subset]} if reuse else {}
                staged.add(ids=[row['id'] for row in subset], documents=[row['text'] for row in subset], metadatas=[row['metadata'] for row in subset], **kwargs)
        if staged.count() != len(pending):
            raise ValueError('Replacement index failed its record-count check')
        index_cache.notify(stage='publication', pages_done=0, pages_total=0)
        db.publish_index(user_id, name, manifests, full=full)
    except Exception:
        client.delete_collection(name)
        raise
    try:
        prune_index_versions(user_id)
    except Exception:
        logger.warning('Inactive index cleanup deferred to maintenance')
    return (name, len(pending))

def _ingest_user_locked(user_id, courses, doc_types):
    chunks, records, manifests = ([], [], [])
    for course in courses:
        directory = course_workspace(user_id, str(course['id']))
        if not directory.is_dir():
            continue
        for path in _files_in_course(directory):
            batch, record, manifest = _extract_index_file(path, user_id, str(course['id']), str(course.get('name', 'Course')), doc_types.get((str(course['id']), path.name), 'notes'))
            chunks.extend(batch)
            records.append(record)
            manifests.append(manifest)
    with INGEST_LOCK:
        name, count = _publish_chunks(user_id, chunks, manifests, full=True)
    return {'chunks': count, 'files': records, 'collection': name, 'coverage': manifests, 'indexed_at': datetime.now(timezone.utc).isoformat(timespec='seconds')}

def ingest_files(user_id, course, filenames, doc_type='notes', progress=None, *, force=False):
    with _user_ingest_lock(user_id):
        return _ingest_file_set(user_id, course, filenames, doc_type, progress, force=force)

def _ingest_file_set(user_id, course, filenames, doc_type='notes', progress=None, *, force=False):
    """Checkpoint extraction outside the publication lock; expose complete new files early."""
    import index_cache, json
    chunks, records, manifests = ([], [], [])
    course_id = str(course['id'])
    directory = course_workspace(user_id, course_id)
    known = {(row['course_id'], row['source_file']) for row in corpus_documents(user_id, [course_id])}
    with db.connect() as c:
        published = {row['filename']: json.loads(row['manifest_json']) for row in c.execute('SELECT filename,manifest_json FROM extraction_manifests WHERE user_id=? AND course_id=?', (user_id, course_id))}
    for index, filename in enumerate(dict.fromkeys(filenames), 1):
        path = directory / filename
        if not path.is_file() or path.is_symlink():
            raise ValueError(f'File unavailable for indexing: {filename}')
        started = time.perf_counter()
        index_cache.notify(filename=filename, file_number=index, files_total=len(filenames), stage='text_extraction', pages_done=0, pages_total=0)
        existing = db.get_document_by_name(user_id, course_id, filename)
        with path.open('rb') as handle:
            digest = hashlib.file_digest(handle, 'sha256').hexdigest()
        if not force and existing and published.get(filename, {}).get('extraction_signature') == index_cache.signature(digest) and (existing['doc_type'] == doc_type):
            record = {**existing, 'course_name': course.get('name', 'Course'), 'pages': published[filename].get('indexed_pages', [])}
            records.append(record)
            index_cache.notify(stage='cached', completed_files=index, cache_hits=existing.get('page_count', 0))
            if progress:
                progress(index, len(filenames))
            continue
        batch, record, manifest = _extract_index_file(path, user_id, course_id, str(course.get('name', 'Course')), doc_type)
        index_cache.notify(stage='embedding', pages_done=0, pages_total=0, extraction_seconds=round(time.perf_counter() - started, 3))
        publish_started = time.perf_counter()
        if (course_id, filename) not in known:
            with INGEST_LOCK:
                _append_document(user_id, batch, manifest)
            db.sync_documents(user_id, [record], prune=False, update_doc_type=False)
            known.add((course_id, filename))
            index_cache.notify(stage='published', completed_files=index, publish_seconds=round(time.perf_counter() - publish_started, 3))
        else:
            chunks.extend(batch)
            manifests.append(manifest)
        records.append(record)
        if progress:
            progress(index, len(filenames))
    if manifests:
        index_cache.notify(stage='publication', pages_done=0, pages_total=0)
        with INGEST_LOCK:
            _publish_chunks(user_id, chunks, manifests, replacements={(course_id, m['filename']) for m in manifests})
    return {'chunks': sum((int(r.get('chunks', 0)) for r in records)), 'files': records, 'coverage': manifests, 'indexed_at': datetime.now(timezone.utc).isoformat(timespec='seconds')}

def delete_file(user_id: str, course_id: str, filename: str) -> None:
    """Remove one file's chunks without rebuilding the whole collection."""
    with INGEST_LOCK:
        collection = _get_collection(user_id)
        try:
            collection.delete(where={'$and': [{'course_id': course_id}, {'source_file': filename}]})
            with db.connect() as connection:
                connection.execute('DELETE FROM extraction_manifests WHERE user_id=? AND course_id=? AND filename=?', (user_id, course_id, filename))
            db.bump_corpus_revision(user_id)
        except Exception as exc:
            logger.warning('Could not remove chunks for %s: %s', filename, exc)

def delete_user_collection(user_id: str) -> None:
    try:
        prefix = collection_name(user_id)
        for collection in _client().list_collections():
            name = collection if isinstance(collection, str) else collection.name
            if name == prefix or name.startswith(prefix + '_v_'):
                _client().delete_collection(name)
        with db.connect() as connection:
            connection.execute('DELETE FROM extraction_manifests WHERE user_id=?', (user_id,))
            connection.execute('DELETE FROM app_settings WHERE key IN (?, ?)', (f'index_collection:{user_id}', f'corpus_revision:{user_id}'))
    except Exception as exc:
        logger.info('No collection to remove for user=%s: %s', user_id[:8], exc)

def collection_count(user_id: str) -> int:
    try:
        return _get_collection(user_id).count()
    except Exception as exc:
        logger.warning('Could not count collection for user=%s: %s', user_id[:8], exc)
        return 0

def corpus_documents(user_id: str, course_ids: list[str] | None=None) -> list[dict[str, Any]]:
    collection = _get_collection(user_id)
    where = {'course_id': {'$in': course_ids}} if course_ids else None
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for _, _, metadata in _all_records(collection, where, include=['metadatas']):
        metadata = metadata or {}
        key = (str(metadata.get('course_id', '')), str(metadata.get('source_file', 'unknown')))
        entry = grouped.setdefault(key, {'course_id': metadata.get('course_id', ''), 'course_name': metadata.get('course_name', ''), 'source_file': metadata.get('source_file', 'unknown'), 'source_title': metadata.get('source_title', metadata.get('source_file', 'Course material')), 'kind': metadata.get('kind', 'note'), 'doc_type': metadata.get('doc_type', 'notes'), 'pages': set(), 'chunks': 0})
        entry['pages'].add(metadata.get('page', 1))
        entry['chunks'] += 1
    documents = []
    for entry in grouped.values():
        entry['pages'] = sorted(entry['pages'])
        documents.append(entry)
    return sorted(documents, key=lambda item: (item['course_name'], item['source_file']))

def _files_in_course(directory: Path) -> list[Path]:
    root = directory.resolve()
    suffixes = {'.pdf', '.md', '.txt', '.markdown', '.doc', '.docx'}
    files = []
    for path in directory.rglob('*'):
        try:
            if path.is_symlink() or not path.is_file():
                continue
            resolved = path.resolve()
            if not resolved.is_relative_to(root):
                logger.warning('Skipping path outside course root: %s', path)
                continue
            if path.name.startswith('.') or path.suffix.lower() not in suffixes:
                continue
            files.append(path)
        except OSError:
            logger.warning('Skipping unreadable path: %s', path)
    return sorted(files)

def _chunks_for_file(path: Path, user_id: str, course_id: str, course_name: str, doc_type: str='notes', manifest: dict[str, Any] | None=None) -> list[dict[str, Any]]:
    try:
        if path.stat().st_size > MAX_UPLOAD_BYTES:
            logger.warning('Skipping oversized file: %s', path.name)
            return []
        pages = _read_pages(path, manifest=manifest)
    except Exception as exc:
        logger.warning('Skipping %s: %s', path, exc)
        return []
    title = _title_for(path, pages)
    kind = _kind_for(path)
    statuses = {item['page']: item for item in (manifest or {}).get('pages', [])}
    chunks: list[dict[str, Any]] = []
    for page_number, page_text in pages:
        for index, raw_text in enumerate(_split_text(page_text)):
            text = sanitize_text(raw_text, max_chars=4000)
            if len(text) < 40:
                continue
            chunk_id = hashlib.sha1(f'{user_id}|{course_id}|{path.name}|{page_number}|{index}|{text}'.encode('utf-8')).hexdigest()[:20]
            chunks.append({'id': chunk_id, 'text': text, 'metadata': {'user_id': user_id, 'course_id': course_id, 'course_name': course_name, 'source_file': path.name, 'source_title': title, 'page': page_number, 'kind': kind, 'doc_type': doc_type, 'chunk_index': index, 'chunk_id': chunk_id, 'document_page_count': max((number for number, _ in pages), default=0), 'quality_review_required': statuses.get(page_number, {}).get('status', 'text') in {'needs_review', 'ocr_pending', 'render_failed'}}})
    return chunks

def _read_pages(path: Path, manifest: dict[str, Any] | None=None) -> list[tuple[int, str]]:
    if path.suffix.lower() == '.pdf':
        reader = PdfReader(str(path))
        if len(reader.pages) > MAX_PDF_PAGES:
            raise ValueError(f'PDF exceeds the {MAX_PDF_PAGES}-page limit')
        import index_cache
        from pdf_text import extract_page
        from document_ocr import enrich_pdf_pages, enrich_checkpointed
        document, user, signature = _EXTRACTION_CONTEXT.get()
        cached = index_cache.load(document, 'text', signature)
        pages = []
        new = []
        started = time.perf_counter()
        for index, page in enumerate(reader.pages, 1):
            text = cached[index]['text'] if index in cached else extract_page(page)
            pages.append((index, text))
            if index not in cached:
                new.append((index, {'text': text}))
            index_cache.notify(stage='text_extraction', pages_done=index, pages_total=len(reader.pages), cache_hits=len(cached), extraction_seconds=round(time.perf_counter() - started, 3))
        if new:
            index_cache.save_many(document, user, 'text', signature, new)
        statuses = []
        pages = enrich_checkpointed(path, pages, document, user, signature, statuses) if document else enrich_pdf_pages(path, pages, statuses=statuses)
        for status, (_, text) in zip(statuses, pages):
            damaged = text.count('�') + len(re.findall('\\(cid:\\d+\\)', text))
            status['damaged_glyphs'] = damaged
            if damaged >= 3:
                status['status'] = 'needs_review'
            status['equation_or_table_review'] = bool(re.search('[∫∑√∂≈≤≥]|\\s\\|\\s', text))
        if manifest is not None:
            manifest.update(page_count=len(reader.pages), pages=statuses, visual_coverage='text_and_ocr_only')
        return pages
    if path.suffix.lower() in {'.doc', '.docx'}:
        text = extract_office_text(path.read_bytes())
        return [(1, text)] if text.strip() else []
    text = path.read_text(encoding='utf-8', errors='replace')
    if PAGE_MARKER.search(text):
        return _split_marked_pages(text)
    return [(index, page) for index, page in enumerate(text.split('\x0c'), start=1) if page.strip()]

def _split_marked_pages(text: str) -> list[tuple[int, str]]:
    parts = PAGE_MARKER.split(text)
    pages: list[tuple[int, str]] = []
    if parts and parts[0].strip():
        pages.append((1, parts[0]))
    for index in range(1, len(parts), 2):
        page_number = int(parts[index])
        content = parts[index + 1] if index + 1 < len(parts) else ''
        if content.strip():
            pages.append((page_number, content))
    return pages

def _split_text(text: str) -> list[str]:
    normalized = re.sub('[ \\t]+', ' ', text)
    normalized = re.sub('\\n{3,}', '\n\n', normalized).strip()
    if not normalized:
        return []
    paragraphs = [part.strip() for part in re.split('\\n\\s*\\n', normalized) if part.strip()]
    chunks: list[str] = []
    current = ''
    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 2 <= CHUNK_SIZE:
            current = f'{current}\n\n{paragraph}'.strip()
            continue
        if current:
            chunks.append(current)
        if len(paragraph) <= CHUNK_SIZE:
            current = paragraph
        else:
            start = 0
            while start < len(paragraph):
                chunk = paragraph[start:start + CHUNK_SIZE]
                chunks.append(chunk.strip())
                start += CHUNK_SIZE - CHUNK_OVERLAP
            current = ''
    if current:
        chunks.append(current)
    if len(chunks) > 1 and CHUNK_OVERLAP:
        with_overlap = []
        for index, chunk in enumerate(chunks):
            prefix = chunks[index - 1][-CHUNK_OVERLAP:] if index else ''
            with_overlap.append(f'{prefix}\n{chunk}'.strip())
        chunks = with_overlap
    return [window for chunk in chunks for window in _token_windows(chunk)]

@lru_cache(maxsize=1)
def _embedding_tokenizer():
    path = Path.home() / '.cache/chroma/onnx_models/all-MiniLM-L6-v2/onnx/tokenizer.json'
    if not path.is_file():
        return None
    from tokenizers import Tokenizer
    tokenizer = Tokenizer.from_file(str(path))
    tokenizer.no_truncation()
    return tokenizer

def _token_windows(text: str) -> list[str]:
    tokenizer = _embedding_tokenizer()
    if tokenizer is None:
        return [text[start:start + 220] for start in range(0, len(text), 200)]
    encoded = tokenizer.encode(text, add_special_tokens=False)
    if len(encoded.ids) <= 224:
        return [text]
    windows = []
    for start in range(0, len(encoded.ids), 208):
        offsets = encoded.offsets[start:start + 224]
        if offsets:
            windows.append(text[offsets[0][0]:offsets[-1][1]])
    return windows

def _title_for(path: Path, pages: list[tuple[int, str]]) -> str:
    for _, text in pages:
        match = HEADING.search(text)
        if match:
            return match.group(1).strip()
    return path.stem.replace('_', ' ').replace('-', ' ').title()

def _kind_for(path: Path) -> str:
    name = path.stem.lower()
    if 'past' in name or 'paper' in name or 'exam' in name:
        return 'past_paper'
    if 'lecture' in name or 'slide' in name or 'lesson' in name:
        return 'lecture'
    return 'note'
