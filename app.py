"""Study Desk: document-grounded study tools for one local workspace."""
from __future__ import annotations
import asyncio
import hashlib
import io
import json
import logging
import time
import mimetypes
import os
import re
import shutil
import uuid
import zipfile
from contextlib import asynccontextmanager, nullcontext
from pipeline_runtime import BACKGROUND, generation_process
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Literal
from fastapi import Depends, FastAPI, File, Form, HTTPException, Path as PathParam, Request, Response, UploadFile
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from langgraph.types import Command
from markdown_it import MarkdownIt
from pydantic import BaseModel, Field, field_validator, model_validator
from starlette.exceptions import HTTPException as StarletteHTTPException
from rate_limits import limiter, generation_limit, grading_limit, index_limit
from generation_control import generation_endpoint
import backup
import db
import curriculum
import practice_queue
import generation_progress
import learning_store
import observability
import retention
from token_budget import BudgetExceeded
from public_rubric import rubric as public_rubric
from extended_assessment import criteria as extended_criteria
from durable_learning import StudyRequests
from answer_parts import PartAssessment, feedback_summary
from auth import current_user as require_user
from extraction import extract_assignment_file
from graph import graph, initial_state
from policy import decide, opa_ready, close_policy_client
from retrieval import TOP_K, collection_count, corpus_documents, course_workspace, delete_file, delete_user_collection, ingest_files, search, update_course_name, update_file_doc_type, update_file_identity, user_workspace, format_lineage
from security import ALLOWED_CORPUS_EXTENSIONS, MAX_ASSIGNMENT_CHARS, MAX_UPLOAD_BYTES, SlidingWindowLimiter, enforce_rate_limit, extract_office_text, sanitize_filename, sanitize_text, security_headers, validate_upload
from tools import Assessment, Difficulty, MAX_ATTEMPTS, QuestionType, TutorError, choice_answer_correct, generate_choice_hint, public_settings
from study_catalog import DOC_TYPES, DocumentType
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s | %(message)s')
logger = logging.getLogger('study.api')
PROJECT_DIR = Path(__file__).resolve().parent
STATIC_DIR = PROJECT_DIR / 'static'
MAX_CONCURRENT_LLM = int(os.getenv('MAX_CONCURRENT_LLM', '2'))
from upload_limits import WORKSPACE_FILES, WORKSPACE_BYTES
MAX_BATCH_FILES = int(os.getenv('MAX_BATCH_FILES', str(WORKSPACE_FILES)))
MAX_BATCH_BYTES = int(os.getenv('MAX_BATCH_BYTES', str(WORKSPACE_BYTES)))
MAX_USER_STORAGE_BYTES = int(os.getenv('MAX_USER_STORAGE_BYTES', str(5 * 1024 * 1024 * 1024)))
OWNER_STORAGE_LIMIT_BYTES = int(os.getenv('OWNER_STORAGE_LIMIT_BYTES', str(100 * 1024 * 1024 * 1024)))
ThreadId = Annotated[str, PathParam(min_length=8, max_length=64, pattern='^[A-Za-z0-9_-]+$')]
ASK_LIMIT = SlidingWindowLimiter(5, 60)
ANSWER_LIMIT = SlidingWindowLimiter(10, 60)
EXTRACT_LIMIT = SlidingWindowLimiter(8, 300)
UPLOAD_LIMIT = SlidingWindowLimiter(12, 300)
DOC_TYPE_LIMIT = SlidingWindowLimiter(120, 300)
DOWNLOAD_LIMIT = SlidingWindowLimiter(60, 300)
LLM_SEMAPHORE = asyncio.Semaphore(int(os.getenv('MAX_CONCURRENT_WORKFLOWS', '8')))
WORKSPACE_LOCK = asyncio.Lock()
LAST_INGEST: dict[str, str] = {}
MARKDOWN_PREVIEW = MarkdownIt('commonmark', {'html': False, 'linkify': False}).enable('table').enable('strikethrough')
INDEX_QUEUE: asyncio.Queue | None = None
INDEX_WORKER: asyncio.Task | None = None

@asynccontextmanager
async def lifespan(_: FastAPI):
    global INDEX_QUEUE, INDEX_WORKER, MONITOR_LOOP
    MONITOR_LOOP = asyncio.get_running_loop()
    if backup.apply_pending_restore():
        logger.info('A pending backup restore was applied before startup')
    db.init_db()
    import course_versions
    await asyncio.to_thread(course_versions.initialize)
    await asyncio.to_thread(course_versions.warm)
    pass
    index_cache.initialize()
    await asyncio.to_thread(local_jobs.initialize)
    library_worker = asyncio.create_task(local_jobs.worker(globals()))
    backup_scheduler = asyncio.create_task(backup_tools.scheduler())
    await chunk_uploads.start()
    learning_store.prune_sessions()
    production_default = 'true' if db.DB_PATH.resolve() == (PROJECT_DIR / 'data/app.db').resolve() else 'false'
    maintenance_task = asyncio.create_task(retention.worker()) if os.getenv('AUTO_MAINTENANCE', production_default).lower() == 'true' else None
    if os.getenv('MANAGED_LOGGING', production_default).lower() == 'true':
        retention.configure_logs()
    INDEX_QUEUE = asyncio.Queue()
    INDEX_WORKER = asyncio.create_task(_index_worker_loop())
    for job in db.requeue_index_jobs():
        await INDEX_QUEUE.put(job)
    if os.getenv('AUTO_UPGRADE_PIPELINE', 'true').lower() in {'1', 'true', 'yes'}:
        with db.connect() as connection:
            owners = [row['id'] for row in connection.execute('SELECT id FROM users WHERE is_active=1')]
        for owner in owners:
            known = {(row['course_id'], row['filename']) for row in db.extraction_coverage(owner)}
            for course in db.list_courses(owner):
                key = f"pipeline_upgrade_queued:{owner}:{course['id']}"
                missing = [document['filename'] for document in db.list_documents(owner, [course['id']]) if (course['id'], document['filename']) not in known]
                if missing and (not db.get_app_setting(key)) and (not db.active_index_job(owner, course['id'])):
                    job = db.add_index_job(owner, course['id'], missing, 'notes')
                    await INDEX_QUEUE.put(job)
                    db.set_app_setting(key, '1')
                    logger.info('Queued extraction-coverage upgrade for %s legacy files', len(missing))
    logger.info('Study Desk starting | model=%s', public_settings().get('model', 'not configured'))
    yield
    local_jobs.STOP.set()
    backup_scheduler.cancel()
    library_worker.cancel()
    await asyncio.gather(backup_scheduler,library_worker,return_exceptions=True)
    if maintenance_task:
        maintenance_task.cancel()
        await asyncio.gather(maintenance_task, return_exceptions=True)
    await chunk_uploads.close()
    await close_policy_client()
    if INDEX_WORKER:
        INDEX_WORKER.cancel()
        try:
            await INDEX_WORKER
        except asyncio.CancelledError:
            pass
    import document_ocr
    await asyncio.to_thread(document_ocr.close_pool)
    logger.info('Study Desk stopping')
app = FastAPI(title='Study Desk API', version='3.0.0', lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
app.add_middleware(observability.OperationMiddleware)
app.add_middleware(StudyRequests)

@app.exception_handler(__import__('sqlite3').IntegrityError)
async def capacity_error(request: Request, exc):
    if str(exc).startswith('capacity_limit:'):
        return JSONResponse({'detail': str(exc).replace('capacity_limit:', 'Capacity limit:')}, status_code=409)
    logger.error('Database constraint failed: %s', type(exc).__name__)
    return JSONResponse({'detail': 'This item conflicts with an existing record.'}, status_code=409)
app.add_middleware(GZipMiddleware, minimum_size=800)

@app.exception_handler(StarletteHTTPException)
async def http_error_page(request: Request, exc: StarletteHTTPException) -> Response:
    accepts_html = 'text/html' in request.headers.get('accept', '')
    if exc.status_code == 404 and accepts_html and (not request.url.path.startswith(('/api/', '/auth/', '/workspace/', '/admin/', '/progress/', '/groups/'))):
        return FileResponse(STATIC_DIR / '404.html', status_code=404)
    return JSONResponse(status_code=exc.status_code, content={'detail': exc.detail})

@app.exception_handler(Exception)
async def internal_error_page(request: Request, exc: Exception) -> Response:
    logger.exception('Unhandled error on %s', request.url.path)
    if 'text/html' in request.headers.get('accept', ''):
        response=FileResponse(STATIC_DIR / '500.html', status_code=500)
    else:
        response=JSONResponse(status_code=500, content={'detail': 'Internal server error.'})
    security_headers(request,response)
    response.headers['Cache-Control']='no-store'
    return response

class MathRequest(BaseModel):
    figure_mode: Literal['auto', 'none', 'math'] = 'auto'

    @model_validator(mode='after')
    def validate_math_mode(self):
        types = getattr(self, 'question_types', [])
        courses = getattr(self, 'course_ids', [])
        if len(types) > 7:
            raise ValueError('Select at most seven question types.')
        if len(courses) > 100 or any((len(value) > 100 for value in courses)):
            raise ValueError('Course selection is too large.')
        from math_figures import validate_request
        validate_request(self.figure_mode, getattr(self, 'difficulty', 'medium'), getattr(self, 'question_types', [getattr(self, 'question_type', 'short_answer')]))
        return self

class AskRequest(MathRequest):
    follow_up_record_id: str | None = Field(default=None, max_length=100)
    client_request_id: str = Field(default='', max_length=64, pattern='^[A-Za-z0-9_-]*$')
    topic: str = Field(min_length=3, max_length=200)
    scope: Literal['topic', 'syllabus'] = 'topic'
    difficulty: Difficulty = 'medium'
    question_types: list[QuestionType] = Field(default_factory=lambda: ['short_answer'])
    course_ids: list[str] = Field(default_factory=list)
    doc_types: list[DocumentType] = Field(default_factory=list, max_length=len(DOC_TYPES))

    @field_validator('topic')
    @classmethod
    def _clean(cls, value: str) -> str:
        value = ' '.join(sanitize_text(value, max_chars=200).split())
        if len(value) < 3:
            raise ValueError('topic must contain at least 3 characters')
        return value

class AskQuestionRequest(BaseModel):
    client_request_id: str = Field(default='', max_length=64, pattern='^[A-Za-z0-9_-]*$')
    question: str = Field(default='', max_length=MAX_ASSIGNMENT_CHARS)
    attachment_text: str = Field(default='', max_length=MAX_ASSIGNMENT_CHARS)
    attachment_name: str = Field(default='', max_length=140)
    doc_types: list[DocumentType] = Field(default_factory=list, max_length=len(DOC_TYPES))

class AnswerRequest(BaseModel):
    thread_id: str = Field(min_length=8, max_length=64)
    answer: str = Field(min_length=1, max_length=20000)

    @field_validator('thread_id')
    @classmethod
    def _thread(cls, value: str) -> str:
        value = value.strip()
        if not any((not (c.isalnum() or c in '-_') for c in value)):
            return value
        raise ValueError("thread_id must contain only letters, digits, '-' or '_'")

    @field_validator('answer')
    @classmethod
    def _answer(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError('answer cannot be blank')
        return value

class Source(BaseModel):
    ref: str
    text: str
    excerpt: str
    source_file: str
    source_title: str
    page: int
    kind: str
    doc_type: str = 'notes'
    chunk_id: str
    course_id: str = ''
    course_name: str = ''
    score: float

class PolicyDecision(BaseModel):
    allow: bool
    action: str
    reason: str
    engine: str
    decided_at: str
    latency_ms: float | None = None

class PublicStudyResponse(BaseModel):
    verification: dict[str, Any] = Field(default_factory=dict)

    @field_validator('verification', mode='before')
    @classmethod
    def safe_verification(cls, value):
        from verification_metadata import public_fields
        return public_fields(value)

class AskResponse(PublicStudyResponse):
    practice_context: dict[str, Any] = Field(default_factory=dict)
    criteria: list[dict[str, str]] = Field(default_factory=list)
    figure: dict[str, Any] | None = None
    bank_reused: bool = False
    rubric: list[dict[str, str]] = Field(default_factory=list)
    thread_id: str
    mode: Literal['practice', 'question']
    difficulty: Difficulty
    question: str
    question_type: str = 'short_answer'
    options: list[str] = Field(default_factory=list)
    opening_hint: str = ''
    status: Literal['awaiting_answer']
    attempts_used: int
    max_attempts: int
    sources: list[Source]
    attachment_name: str | None = None
    generation_seconds: float | None = None

class GenerationStatusResponse(BaseModel):
    request_id: str
    elapsed: float
    stage: str
    done: bool
    error: str = ''

class AnswerResponse(BaseModel):
    parts: list[PartAssessment] = Field(default_factory=list)
    thread_id: str
    feedback: str
    status: Literal['awaiting_answer', 'correct', 'revealed', 'blocked']
    is_correct: bool
    attempts_used: int
    max_attempts: int
    answer_key: str | None = None
    solution: str | None = None
    sources: list[Source]
    policy_decisions: list[PolicyDecision]

class SessionResponse(PublicStudyResponse):
    criteria: list[dict[str, str]] = Field(default_factory=list)
    figure: dict[str, Any] | None = None
    rubric: list[dict[str, str]] = Field(default_factory=list)
    options: list[str] = Field(default_factory=list)
    question_type: str = 'short_answer'
    thread_id: str
    mode: str
    difficulty: str
    topic: str
    question: str
    opening_hint: str
    status: str
    attempts_used: int
    max_attempts: int
    last_feedback: str
    history: list[dict[str, Any]]
    sources: list[Source]
    policy_decisions: list[PolicyDecision]

class ExtractResponse(BaseModel):
    filename: str
    text: str
    page_count: int
    ocr_used: bool
    truncated: bool
    chars: int
    warnings: list[str] = Field(default_factory=list)
    needs_review: bool = False

class HealthResponse(BaseModel):
    status: Literal['ok', 'degraded']

class CourseCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)

    @field_validator('name')
    @classmethod
    def _name(cls, value: str) -> str:
        value = ' '.join(value.split()).strip()
        if not value:
            raise ValueError('Course name cannot be blank.')
        return value

class CourseScopeRequest(BaseModel):
    scope_notes: str = Field(default='', max_length=4000)

class CourseReindexRequest(BaseModel):
    course_id: str = Field(min_length=1, max_length=64)

class Course(BaseModel):
    id: str
    name: str
    created_at: str
    documents: int = 0

class CourseListResponse(BaseModel):
    courses: list[Course]


class AdminFile(BaseModel):
    id: str
    course_id: str
    course_name: str
    filename: str
    size: int
    sha256: str
    modified_at: str
    page_count: int
    chunks: int
    pages: list[int]
    source_title: str
    kind: str
    doc_type: str = 'notes'
    indexed: bool
    syllabus_enabled: bool = True

class AdminFilesResponse(BaseModel):
    files: list[AdminFile]
    chunks: int

class UploadResponse(BaseModel):
    uploaded: list[AdminFile]
    ingest: dict[str, Any]
    already_present: int = 0
    job_id: str | None = None

class DocumentTypeRequest(BaseModel):
    doc_type: DocumentType

class DocumentUpdateRequest(BaseModel):
    filename: str | None = Field(default=None, min_length=1, max_length=180)
    course_id: str | None = Field(default=None, max_length=64)

class DocumentSyllabusRequest(BaseModel):
    enabled: bool

class FlashcardReviewRequest(BaseModel):
    rating: Literal['again', 'hard', 'good', 'easy', 'mastered']

class ProgressResetRequest(BaseModel):
    confirm: Literal['RESET']


class WorkspaceHealthResponse(BaseModel):
    user: dict[str, Any]
    courses: int
    documents: int
    chunks: int
    last_indexed_at: str | None
    max_attempts: int
    storage_bytes: int
    storage_limit_bytes: int

class WorkspaceSnapshotResponse(BaseModel):
    health: WorkspaceHealthResponse
    courses: list[Course]
    files: list[AdminFile]


class UserSettingsResponse(BaseModel):
    theme: Literal['light', 'dark']
    attempts_before_reveal: int = 3

class UserSettingsRequest(BaseModel):
    theme: Literal['light', 'dark'] = 'light'
    attempts_before_reveal: int = Field(default=3, ge=1, le=5)

def _config(thread_id: str) -> dict[str, Any]:
    return {'configurable': {'thread_id': thread_id}}

async def _restore_ungraded_attempt(config, values):
    """A failed grading call must not leave a thread stuck on its previous input."""
    restored = {**values, 'pending_answer': ''}
    await graph.aupdate_state(config, restored, as_node='generate_question')
    await graph.ainvoke(None, config)

def _sources(values: dict[str, Any]) -> list[Source]:
    return [Source(**source) for source in values.get('sources') or []]

def _decisions(values: dict[str, Any]) -> list[PolicyDecision]:
    return [PolicyDecision(**decision) for decision in values.get('policy_decisions') or []]


def _log_usage(user_id: str, kind: str) -> None:
    try:
        db.log_usage(user_id, kind)
    except Exception:
        logger.exception('Could not record usage event %s', kind)

def _storage_limit(user: dict[str, Any]) -> int:
    """The owner gets a larger personal library; friends keep the normal cap."""
    return OWNER_STORAGE_LIMIT_BYTES if bool(user.get('is_admin')) else MAX_USER_STORAGE_BYTES

def _is_trusted_local_owner(request: Request, user: dict[str, Any]) -> bool:
    """Allow owner large uploads only from a direct loopback connection."""
    if not bool(user.get('is_admin')):
        return False
    host = (request.client.host if request.client else '') or ''
    if host not in {'127.0.0.1', '::1', 'localhost'}:
        return False
    return True

def _assert_course_editable(user: dict[str, Any], course: dict[str, Any]) -> None:
    if course['user_id'] != user['id']:
        raise HTTPException(403, 'This course is outside the local workspace.')

def _source_summary(sources: list[dict[str, Any]], refs: list[str]) -> list[dict[str, Any]]:
    wanted = set(refs or [])
    summary = []
    for source in sources:
        ref = str(source.get('ref', ''))
        if wanted and ref not in wanted:
            continue
        summary.append({'ref': ref, 'course': source.get('course_name', ''), 'course_id': source.get('course_id', ''), 'title': source.get('source_title', ''), 'file': source.get('source_file', ''), 'page': source.get('page', 0)})
    return summary[:8]

def _record_fingerprint(question: str) -> str:
    normalized = ' '.join((question or '').lower().split())
    return hashlib.sha1(normalized.encode('utf-8')).hexdigest() if normalized else ''

def _owned_courses(user_id: str) -> list[dict[str, Any]]:
    return db.list_courses(user_id)

def _resolve_course_scope(user_id: str, requested: list[str] | None) -> list[str]:
    owned = {course['id'] for course in _owned_courses(user_id)}
    shared = set({})
    accessible = owned | shared
    if requested:
        invalid = [course_id for course_id in requested if course_id not in accessible]
        if invalid:
            raise HTTPException(status_code=400, detail='Unknown course selection.')
        return list(dict.fromkeys(requested))
    return sorted(accessible)

def _course_access_lost(user_id: str, course_ids: list[str] | None) -> bool:
    if not course_ids:
        return False
    owned = {course['id'] for course in _owned_courses(user_id)}
    return any((course_id not in owned and course_id not in {} for course_id in course_ids))

def _ingest_files_and_sync(user_id: str, course: dict[str, Any], filenames: list[str], doc_type: str='notes', progress: Any=None, *, force: bool=False) -> dict[str, Any]:
    result = ingest_files(user_id, course, filenames, doc_type, progress=progress, force=force)
    db.sync_documents(user_id, result['files'], prune=False, update_doc_type=False)
    curriculum.course_map(user_id, [course['id']])
    LAST_INGEST[user_id] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    return result

def _process_index_job(job_id: str) -> None:
    job = db.get_index_job(job_id)
    if not job:
        return
    db.update_index_job(job_id, 'running', progress=1)
    try:
        course = db.get_course(job['user_id'], job['course_id'])
        if not course:
            db.update_index_job(job_id, 'done', 'Course was removed before indexing.', progress=100)
            return
        documents = {doc['filename']: doc for doc in db.list_documents(job['user_id'], [job['course_id']])}
        by_type: dict[str, list[str]] = {}
        for filename in job.get('filenames', []):
            document = documents.get(filename)
            if document:
                by_type.setdefault(document.get('doc_type', 'notes'), []).append(filename)
        if not by_type:
            db.update_index_job(job_id, 'done', 'No files were available to index.', progress=100)
            return
        total_files = max(1, sum((len(names) for names in by_type.values())))
        processed = 0
        total_chunks = 0
        index_cache.detail(job_id, stage='starting', files_total=total_files, completed_files=0)
        for doc_type, filenames in by_type.items():
            offset = processed

            def report_progress(done: int, _total: int, offset: int=offset) -> None:
                db.update_index_job(job_id, 'running', progress=min(95, 5 + int(90 * (offset + done) / total_files)))
            next_cancel_check = 0

            def stage_progress(**values):
                nonlocal next_cancel_check
                if time.monotonic() >= next_cancel_check:
                    actor = db.get_user_by_id(job['user_id'])
                    if not actor or actor.get('deleting'):
                        raise ValueError('Account work stopped.')
                    next_cancel_check = time.monotonic() + 1
                if 'file_number' in values:
                    values['file_number'] += offset
                values['files_total'] = total_files
                if 'pages_total' in values and values['pages_total']:
                    number = index_cache.details(job_id).get('file_number', offset + 1)
                    fraction = values.get('pages_done', 0) / values['pages_total']
                    fraction = 0.2 + 0.6 * fraction if values.get('stage') == 'ocr' else 0.2 * fraction
                    db.update_index_job(job_id, 'running', progress=min(95, int(5 + 90 * (number - 1 + fraction) / total_files)))
                index_cache.detail(job_id, **values)
            token = index_cache.PROGRESS.set(stage_progress)
            try:
                result = _ingest_files_and_sync(job['user_id'], course, filenames, doc_type, progress=report_progress, force=job.get('doc_type') == 'rebuild')
            finally:
                index_cache.PROGRESS.reset(token)
            processed += len(filenames)
            total_chunks += int(result.get('chunks', 0))
        index_cache.detail(job_id, stage='done', completed_files=total_files)
        db.update_index_job(job_id, 'done', f'Indexed {total_chunks} chunks.', chunks=total_chunks, progress=100)
    except Exception as exc:
        actor = db.get_user_by_id(job['user_id'])
        if not actor or actor.get('deleting'):
            return
        index_cache.detail(job_id, stage='failed')
        logger.exception('Background indexing failed for job %s', job_id)
        db.update_index_job(job_id, 'failed', str(exc))

async def _index_worker_loop() -> None:
    assert INDEX_QUEUE is not None
    queue = INDEX_QUEUE
    slots = asyncio.Semaphore(2)
    tasks = set()

    async def run(job):
        try:
            async with practice_queue.request_slot('index:' + job['user_id']):
                async with slots:
                    await asyncio.to_thread(_process_index_job, job['id'])
        finally:
            queue.task_done()
    try:
        while True:
            job = await queue.get()
            task = asyncio.create_task(run(job))
            tasks.add(task)
            task.add_done_callback(tasks.discard)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

async def _enqueue_index_job(job: dict[str, Any]) -> None:
    global INDEX_QUEUE
    if INDEX_QUEUE is None:
        await asyncio.to_thread(_process_index_job, job['id'])
        return
    await INDEX_QUEUE.put(job)

async def _read_upload(file: UploadFile, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(status_code=413, detail='Uploaded file is too large.')
        chunks.append(chunk)
    return b''.join(chunks)

def _user_file_row(user_id: str, document: dict[str, Any], indexed: dict[tuple[str, str], dict[str, Any]]) -> AdminFile:
    key = (document['course_id'], document['filename'])
    meta = indexed.get(key, {})
    path = course_workspace(user_id, document['course_id']) / document['filename']
    modified = document['created_at']
    if path.is_file():
        modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec='seconds')
    return AdminFile(id=document['id'], course_id=document['course_id'], course_name=document.get('course_name', ''), filename=document['filename'], size=document['size'], sha256=document['sha256'], modified_at=modified, page_count=document.get('page_count', 0), chunks=meta.get('chunks', 0), pages=meta.get('pages', []), source_title=meta.get('source_title', document['filename']), kind=meta.get('kind', 'note'), doc_type=document.get('doc_type', 'notes'), indexed=bool(meta), syllabus_enabled=bool(document.get('syllabus_enabled', 1)))

async def _export_thread(user_id: str, thread_id: str) -> Response:
    snapshot = await graph.aget_state(_config(thread_id))
    if not snapshot.values or snapshot.values.get('user_id') != user_id:
        raise HTTPException(status_code=404, detail='Unknown thread_id.')
    values = snapshot.values
    lines = ['# Study Desk transcript', '', f"- Mode: {values.get('mode', 'practice')}", f"- Topic: {values.get('topic', '')}", f"- Difficulty: {values.get('difficulty', 'medium')}", f"- Attempts used: {values.get('user_attempts', 0)} of {values.get('max_attempts', 3)}", '', '## Question', '', values.get('current_question', ''), '']
    if values.get('figure'):
        lines += ['Figure description: ' + values['figure']['alt'], '', 'The diagram is available in the app, including Download SVG.', '']
    opening = values.get('opening_hint', '')
    if opening:
        lines += ['## Starting hint', '', opening, '']
    for item in values.get('history', []):
        lines += [f"## Attempt {item.get('attempt', '?')}", '', '**Your answer**', '', item.get('answer', ''), '', '**Tutor feedback**', '', item.get('feedback', ''), '']
    sources = values.get('sources') or []
    if sources:
        lines += ['## Sources', '']
        for source in sources:
            lines.append(f"- [{source.get('ref')}] {source.get('course_name', '')} {source.get('source_title', '')} ??page {source.get('page')} (`{source.get('source_file')}`)")
    content = '\n'.join(lines).strip() + '\n'
    filename = f"study-transcript-{values.get('mode', 'tutor')}-{thread_id[:8]}.md"
    return Response(content=content, media_type='text/markdown; charset=utf-8', headers={'Content-Disposition': f'attachment; filename="{filename}"'})

@app.get('/', include_in_schema=False)
async def index(request: Request):
    return FileResponse(STATIC_DIR / 'index.html')

@app.get('/health', response_model=HealthResponse, tags=['system'])
async def health() -> HealthResponse:
    return HealthResponse(status='ok' if public_settings().get('configured') else 'degraded')

@app.get('/settings', response_model=UserSettingsResponse, tags=['settings'])
async def get_user_settings(user: dict[str, Any]=Depends(require_user)) -> UserSettingsResponse:
    return UserSettingsResponse(**db.get_settings(user['id']))

@app.put('/settings', response_model=UserSettingsResponse, tags=['settings'])
async def put_user_settings(req: UserSettingsRequest, user: dict[str, Any]=Depends(require_user)) -> UserSettingsResponse:
    return UserSettingsResponse(**db.update_settings(user['id'], req.theme, req.attempts_before_reveal))

def _followup_context(user, identifier):
    record = db.get_study_record(user['id'], identifier)
    if not record:
        raise HTTPException(404, 'Unknown study record.')
    saved = learning_store.get('tutor', record['ref_id']) or {}
    if saved.get('user_id') != user['id']:
        saved = {}
    accessible = _resolve_course_scope(user['id'], [])
    courses = sorted({s['course_id'] for s in saved.get('sources', []) if s.get('course_id') in accessible})
    if not courses:
        courses = sorted({s['course_id'] for s in record.get('source_summary', []) if s.get('course_id') in accessible})
    if not courses:
        raise HTTPException(409, 'This saved record no longer has an accessible course link. Start practice from its current course documents.')
    topic = saved.get('topic') or saved.get('formula_focus') or record.get('question', '')[:200]
    if not topic:
        raise HTTPException(409, 'No covered learning objective remains linked to this record.')
    return {'topic': topic[:200], 'course_ids': courses, 'difficulty': record['difficulty'], 'question_types': [record['question_type']], 'previous_question': record['question'], 'focus_skill_id': saved.get('skill_id', '')}

@app.post('/practice/follow-up/{identifier}', response_model=AskResponse, tags=['tutor'])
@generation_limit
@generation_endpoint
async def follow_up(identifier: str, request: Request, user=Depends(require_user)):
    context = _followup_context(user, identifier)
    req = AskRequest(topic=context['topic'], course_ids=context['course_ids'], difficulty=context['difficulty'], question_types=context['question_types'], follow_up_record_id=identifier)
    result = await ask_question(req, request, user)
    return result.model_copy(update={'practice_context': {k: context[k] for k in ['topic', 'course_ids', 'difficulty', 'question_types']}})

def _record_generation_failure(user, request_id, reason, *, stage='request', difficulty='', question_type=''):
    try:
        import monitoring
        monitoring.record_generation('request_failed', user['id'], outcome='error', reason=str(reason), stage=stage, request_id=request_id, difficulty=difficulty, question_type=question_type)
    except Exception:
        logger.warning('Could not persist generation request failure', exc_info=True)

@app.get('/generation/status/{request_id}', response_model=GenerationStatusResponse, tags=['tutor'])
async def generation_status(request_id: str, user: dict[str, Any]=Depends(require_user)) -> GenerationStatusResponse:
    status = generation_progress.snapshot(request_id, user['id'])
    if status is None:
        raise HTTPException(status_code=404, detail='No active generation for this request.')
    return GenerationStatusResponse(**status)

@app.post('/ask', response_model=AskResponse, tags=['tutor'])
@generation_limit
@generation_endpoint
async def ask_question(req: AskRequest, request: Request, user: dict[str, Any]=Depends(require_user)) -> AskResponse:
    started = time.perf_counter()
    progress_id = generation_progress.start(user['id'], req.client_request_id)
    generation_progress.bind(progress_id)
    focus = _followup_context(user, req.follow_up_record_id) if req.follow_up_record_id else {}
    if focus:
        req = req.model_copy(update={key: focus[key] for key in ['topic', 'course_ids', 'difficulty', 'question_types']})
    courses = _resolve_course_scope(user['id'], req.course_ids)
    topic = 'Whole syllabus review' if req.scope == 'syllabus' else req.topic
    max_attempts = db.get_settings(user['id']).get('attempts_before_reveal', 3)
    version = curriculum.scope_version(user['id'], courses)

    async def generate():
        if _course_access_lost(user['id'], courses) or curriculum.scope_version(user['id'], courses) != version:
            raise TutorError('Course material changed. Please request a fresh question.')
        thread_id = uuid.uuid4().hex
        try:
            async with asyncio.timeout(180):
                async with nullcontext():
                    async with observability.operation('practice_generate', user['id'], thread_id, difficulty=req.difficulty, question_type=req.question_types[0]) as operation:
                        seed = initial_state(topic, user_id=user['id'], course_ids=courses, doc_types=req.doc_types, difficulty=req.difficulty, question_types=req.question_types, max_attempts=max_attempts, scope=req.scope, figure_mode=req.figure_mode)
                        if focus:
                            seed.update(follow_up_question=focus['previous_question'], focus_skill_id=focus['focus_skill_id'])
                        generation_progress.stage(generation_progress.STAGE_DRAFTING)
                        result = await graph.ainvoke(seed, _config(thread_id))
                        observability.describe(operation['id'], result, thread_id)
            if _course_access_lost(user['id'], courses) or curriculum.scope_version(user['id'], courses) != version:
                raise TutorError('Course material changed during generation. Please try again.')
        except BaseException:
            await graph.checkpointer.adelete_thread(thread_id)
            raise
        return (thread_id, result)
    try:
        async with asyncio.timeout(180), practice_queue.request_slot(user['id']):
            thread_id, result = await generate()
            if result and result.get('current_question'):
                learning_store.mark_served(user['id'], result['current_question'],result.get('options'))
        if _course_access_lost(user['id'], courses) or curriculum.scope_version(user['id'], courses) != version:
            raise TutorError('Course material changed. Please request a fresh question.')
    except BudgetExceeded as exc:
        generation_progress.finish(progress_id, 'Generation stopped.')
        _record_generation_failure(user, progress_id, str(exc), stage='budget', difficulty=req.difficulty, question_type=req.question_types[0])
        raise
    except TutorError as exc:
        generation_progress.finish(progress_id, str(exc))
        _record_generation_failure(user, progress_id, str(exc), difficulty=req.difficulty, question_type=req.question_types[0])
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except TimeoutError as exc:
        generation_progress.finish(progress_id, 'Generation timed out.')
        _record_generation_failure(user, progress_id, 'Generation timed out.', stage='timeout', difficulty=req.difficulty, question_type=req.question_types[0])
        raise HTTPException(status_code=503, detail='Question preparation took too long. Please try again.') from exc
    except Exception as exc:
        generation_progress.finish(progress_id, 'Generation failed.')
        _record_generation_failure(user, progress_id, f'{type(exc).__name__}: {exc}', stage='exception', difficulty=req.difficulty, question_type=req.question_types[0])
        logger.exception('Unexpected error while generating a question')
        raise HTTPException(status_code=503, detail='Could not generate a question. Please retry.') from exc
    if result is None:
        generation_progress.finish(progress_id, 'Could not generate a question.')
        raise HTTPException(status_code=503, detail='Could not generate a question. Please retry.')
    question = result.get('current_question', '')
    if not question:
        generation_progress.finish(progress_id, 'The tutor returned an empty question.')
        raise HTTPException(status_code=422, detail='The tutor returned an empty question.')
    _log_usage(user['id'], 'tutor_practice')
    elapsed = round(time.perf_counter() - started, 3)
    logger.info('pipeline stage=practice_total seconds=%.3f', elapsed)
    metadata = await study_extensions.attach_verification(result, thread_id, elapsed, user['id'], graph, _config)
    generation_progress.finish(progress_id)
    return AskResponse(verification=metadata, figure=result.get('figure'), bank_reused=bool(result.get('bank_id')), criteria=extended_criteria(question, result.get('question_type', 'short_answer')), rubric=public_rubric(question, result.get('question_type', 'short_answer')), generation_seconds=elapsed, thread_id=thread_id, mode='practice', difficulty=req.difficulty, question=question, question_type=result.get('question_type', 'short_answer'), options=list(result.get('options') or []), status='awaiting_answer', attempts_used=0, max_attempts=result.get('max_attempts', MAX_ATTEMPTS), sources=_sources(result))

@app.post('/ask/question', response_model=AskResponse, tags=['tutor'])
@generation_limit
@generation_endpoint
async def ask_my_question(req: AskQuestionRequest, request: Request, user: dict[str, Any]=Depends(require_user)) -> AskResponse:
    started = time.perf_counter()
    progress_id = generation_progress.start(user['id'], req.client_request_id)
    generation_progress.bind(progress_id)
    attachment = sanitize_text(req.attachment_text, max_chars=MAX_ASSIGNMENT_CHARS)
    question = sanitize_text(req.question, max_chars=MAX_ASSIGNMENT_CHARS)
    combined = question
    if attachment:
        combined = f"{question}\n\n--- Attached question material ({sanitize_text(req.attachment_name, max_chars=140) or 'upload'}) ---\n{attachment}"
    if len(combined) > MAX_ASSIGNMENT_CHARS:
        raise HTTPException(status_code=413, detail='Question text is too long.')
    if len(combined.strip())<5:
        raise HTTPException(422,'Enter a question or attach readable question text.')
    from security import scan_untrusted_text
    if scan_untrusted_text(combined):
        raise HTTPException(status_code=400, detail='The question contains instruction-like text that could hijack the tutor.')
    thread_id = uuid.uuid4().hex
    label = ' '.join(question.split())[:120] or 'Assignment question'
    max_attempts = db.get_settings(user['id']).get('attempts_before_reveal', 3)
    try:
        generation_progress.stage(generation_progress.STAGE_DRAFTING)
        async with nullcontext():
            result = await graph.ainvoke(initial_state(label, mode='question', question=combined, difficulty='medium', user_id=user['id'], course_ids=_resolve_course_scope(user['id'], None), doc_types=req.doc_types, max_attempts=max_attempts), _config(thread_id))
    except BudgetExceeded as exc:
        generation_progress.finish(progress_id, 'Generation stopped.')
        _record_generation_failure(user, progress_id, str(exc), stage='budget', question_type='assignment')
        raise
    except TutorError as exc:
        generation_progress.finish(progress_id, str(exc))
        _record_generation_failure(user, progress_id, str(exc), question_type='assignment')
        logger.warning('Assignment preparation failed: %s', exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        generation_progress.finish(progress_id, 'Generation failed.')
        _record_generation_failure(user, progress_id, f'{type(exc).__name__}: {exc}', stage='exception', question_type='assignment')
        logger.exception('Unexpected error while preparing an assignment question')
        raise HTTPException(status_code=503, detail='Could not prepare this question. Please retry.') from exc
    if not result.get('current_question'):
        generation_progress.finish(progress_id, 'The tutor returned an empty question.')
        raise HTTPException(status_code=422, detail='The tutor returned an empty question.')
    _log_usage(user['id'], 'tutor_question')
    generation_progress.finish(progress_id)
    return AskResponse(verification=await study_extensions.attach_verification(result, thread_id, round(time.perf_counter() - started, 3), user['id'], graph, _config), criteria=extended_criteria(result.get('current_question', ''), result.get('question_type', 'short_answer')), rubric=public_rubric(result.get('current_question', ''), result.get('question_type', 'short_answer')), thread_id=thread_id, mode='question', difficulty='medium', question=result['current_question'], question_type=result.get('question_type', 'short_answer'), options=list(result.get('options') or []), opening_hint=result.get('opening_hint', ''), status='awaiting_answer', attempts_used=0, max_attempts=result.get('max_attempts', MAX_ATTEMPTS), sources=_sources(result), attachment_name=req.attachment_name or None)

@app.post('/api/extract', response_model=ExtractResponse, tags=['tutor'])
async def extract_question_file(request: Request, file: UploadFile=File(...), user: dict[str, Any]=Depends(require_user)) -> ExtractResponse:
    enforce_rate_limit(request, EXTRACT_LIMIT, 'extract', user_id=user['id'])
    from upload_limits import QUESTION_FILE_BYTES
    data = await _read_upload(file, QUESTION_FILE_BYTES)
    try:
        result = await app.state.attachment_extractor.extract(user['id'],file.filename or 'question',data)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception('Could not extract the uploaded question')
        raise HTTPException(status_code=422, detail='Could not read this file.') from exc
    _log_usage(user['id'], 'extract')
    return ExtractResponse(**result)

@app.post('/answer', response_model=AnswerResponse, tags=['tutor'])
@grading_limit
async def submit_answer(req: AnswerRequest, request: Request, user: dict[str, Any]=Depends(require_user)) -> AnswerResponse:
    config = _config(req.thread_id)
    snapshot = await graph.aget_state(config)
    if not snapshot.values or snapshot.values.get('user_id') != user['id']:
        raise HTTPException(status_code=404, detail='Unknown thread_id.')
    if snapshot.values.get('status') != 'awaiting_answer':
        raise HTTPException(status_code=409, detail=f"This thread is '{snapshot.values.get('status')}' and cannot accept answers.")
    study_extensions.check_path(snapshot.values, user['id'])
    if _course_access_lost(user['id'], snapshot.values.get('course_ids')):
        raise HTTPException(status_code=409, detail='Course documents for this question are no longer available.')
    try:
        async with nullcontext():
            result = await graph.ainvoke(Command(resume=req.answer), config)
    except BudgetExceeded:
        raise
    except TutorError as exc:
        logger.warning('Answer grading failed for thread %s: %s', req.thread_id, exc)
        await _restore_ungraded_attempt(config, snapshot.values)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception('Unexpected error while grading an answer')
        await _restore_ungraded_attempt(config, snapshot.values)
        raise HTTPException(status_code=503, detail='Could not grade the answer.') from exc
    final_status = result.get('status')
    if final_status not in {'awaiting_answer', 'correct', 'revealed', 'blocked'}:
        raise HTTPException(status_code=422, detail='Invalid tutor state.')
    reveal = final_status == 'revealed'
    history = list(result.get('history') or [])
    last_entry = history[-1] if history else {}
    try:
        db.save_study_record(user['id'], {'id': f'practice:{req.thread_id}', 'kind': 'practice', 'ref_id': req.thread_id, 'question': result.get('current_question', ''), 'figure': result.get('figure'), 'question_type': result.get('question_type', 'short_answer'), 'difficulty': result.get('difficulty', 'medium'), 'options': list(result.get('options') or []), 'answer_key': result.get('canonical_answer', ''), 'solution': result.get('solution', ''), 'marking_guide': '', 'source_refs': last_entry.get('used_source_refs', []), 'source_summary': _source_summary(list(result.get('sources') or []), last_entry.get('used_source_refs', [])), 'attempts': int(result.get('user_attempts', 0)), 'first_marks': 0, 'latest_marks': 0, 'max_marks': 0, 'is_correct': final_status == 'correct', 'fingerprint': _record_fingerprint(result.get('current_question', ''))})
    except Exception:
        logger.exception('Could not save practice record %s', req.thread_id)
    _log_usage(user['id'], 'tutor_answer')
    return AnswerResponse(thread_id=req.thread_id, parts=[PartAssessment.model_validate(part) for part in result.get('part_results', [])], feedback=result.get('last_feedback', ''), status=final_status, is_correct=final_status == 'correct', attempts_used=result.get('user_attempts', 0), max_attempts=result.get('max_attempts', MAX_ATTEMPTS), answer_key=result.get('canonical_answer') if reveal else None, solution=result.get('solution') if reveal else None, sources=_sources(result), policy_decisions=_decisions(result))

@app.get('/session/{thread_id}', response_model=SessionResponse, tags=['tutor'])
async def get_session(thread_id: ThreadId, user: dict[str, Any]=Depends(require_user)) -> SessionResponse:
    snapshot = await graph.aget_state(_config(thread_id))
    if not snapshot.values or snapshot.values.get('user_id') != user['id']:
        raise HTTPException(status_code=404, detail='Unknown thread_id.')
    values = snapshot.values
    study_extensions.check_path(values, user['id'])
    if _course_access_lost(user['id'], values.get('course_ids')):
        raise HTTPException(409, 'A course in this session is no longer accessible.')
    return SessionResponse(verification=values.get('verification') or {}, figure=values.get('figure'), criteria=extended_criteria(values.get('current_question', ''), values.get('question_type', 'short_answer')), rubric=public_rubric(values.get('current_question', ''), values.get('question_type', 'short_answer')), options=values.get('options') or [], question_type=values.get('question_type', 'short_answer'), thread_id=thread_id, mode=values.get('mode', 'practice'), difficulty=values.get('difficulty', 'medium'), topic=values.get('topic', ''), question=values.get('current_question', ''), opening_hint=values.get('opening_hint', ''), status=values.get('status', 'unknown'), attempts_used=values.get('user_attempts', 0), max_attempts=values.get('max_attempts', MAX_ATTEMPTS), last_feedback=values.get('last_feedback', ''), history=values.get('history', []), sources=_sources(values), policy_decisions=_decisions(values))

@app.get('/session/{thread_id}/export', tags=['tutor'])
async def export_session(thread_id: ThreadId, user: dict[str, Any]=Depends(require_user)) -> Response:
    snapshot = await graph.aget_state(_config(thread_id))
    if snapshot.values and snapshot.values.get('user_id') == user['id']:
        study_extensions.check_path(snapshot.values, user['id'])
    return await _export_thread(user['id'], thread_id)

def _study_plan(dashboard: dict[str, Any]) -> list[dict[str, str]]:
    tasks: list[dict[str, str]] = []
    due = int(dashboard.get('flashcards_due') or 0)
    mistakes = int(dashboard.get('mistakes') or 0)
    weak = dashboard.get('weak_by_type') or []
    if due:
        tasks.append({'title': f"Review {due} mistake card{('s' if due != 1 else '')}", 'detail': 'Clear the due review queue before starting new material.', 'action': 'review'})
    if mistakes:
        tasks.append({'title': f"Retry {mistakes} open mistake{('s' if mistakes != 1 else '')}", 'detail': 'Work through one or two mistakes and mark them resolved.', 'action': 'mistakes'})
    if weak:
        weakest = min(weak, key=lambda row: (row.get('mark_percent') is None, row.get('mark_percent') if row.get('mark_percent') is not None else 100))
        tasks.append({'title': f"Practise {weakest['question_type'].replace('_', ' ')}", 'detail': f'Your recorded accuracy in this type is the weakest so far.', 'action': 'practice'})
    if not tasks:
        tasks.append({'title': 'Start a 15-minute practice session', 'detail': 'Choose a course, answer one question, and set a baseline.', 'action': 'practice'})
    return tasks[:1]

@app.get('/progress', tags=['progress'])
async def get_progress(user: dict[str, Any]=Depends(require_user)) -> dict[str, Any]:
    dashboard = db.study_dashboard(user['id'])
    return {'dashboard': dashboard, 'plan': _study_plan(dashboard), 'recent': [row for row in db.list_study_records(user['id'], 40) if row.get('kind') != 'exam'][:20], 'mistakes': [row for row in db.list_study_records(user['id'], 60, mistakes_only=True) if row.get('kind') != 'exam'][:30], 'flashcards': db.list_due_flashcards(user['id'], 20)}

@app.get('/progress/reset-preview', tags=['progress'])
async def progress_reset_preview(user: dict[str, Any]=Depends(require_user)) -> dict[str, int]:
    return db.progress_counts(user['id'])

@app.post('/progress/reset', tags=['progress'])
async def reset_progress(req: ProgressResetRequest, user: dict[str, Any]=Depends(require_user)) -> dict[str, int]:
    counts = db.reset_progress(user['id'])
    logger.info('Progress reset for user %s: %s records, %s flashcards', user['id'][:8], counts['records'], counts['flashcards'])
    return counts

@app.post('/progress/mistakes/resolve-all', tags=['progress'])
async def resolve_all_mistakes(user: dict[str, Any]=Depends(require_user)) -> dict[str, int]:
    return {'resolved': db.resolve_all_mistakes(user['id'])}

@app.post('/progress/mistakes/{record_id}/resolve', tags=['progress'])
async def resolve_mistake(record_id: str, user: dict[str, Any]=Depends(require_user)) -> dict[str, str]:
    if not db.resolve_study_record(user['id'], record_id):
        raise HTTPException(status_code=404, detail='Unknown mistake.')
    return {'status': 'resolved'}

@app.post('/progress/flashcards/{card_id}/review', tags=['progress'])
async def review_flashcard(card_id: str, req: FlashcardReviewRequest, user: dict[str, Any]=Depends(require_user)) -> dict[str, Any]:
    card = db.review_flashcard(user['id'], card_id, req.rating)
    if not card:
        raise HTTPException(status_code=404, detail='Unknown flashcard.')
    return card

@app.get('/workspace/courses/{course_id}/coverage', tags=['workspace'])
async def course_coverage(course_id: str, user: dict[str, Any]=Depends(require_user)):
    courses = _resolve_course_scope(user['id'], [course_id])
    result = await asyncio.to_thread(curriculum.public_map, user['id'], courses)
    result['editable'] = db.get_course(user['id'], course_id) is not None
    return result

@app.put('/workspace/courses/{course_id}/scope', tags=['workspace'])
async def update_course_scope(course_id: str, req: CourseScopeRequest, user: dict[str, Any]=Depends(require_user)):
    course = db.get_course(user['id'], course_id)
    if not course:
        raise HTTPException(status_code=403, detail='Only the course owner can edit its scope.')
    _assert_course_editable(user, course)
    notes = sanitize_text(req.scope_notes, max_chars=4000)
    db.set_app_setting(f"course_scope:{user['id']}:{course_id}", notes)
    db.bump_corpus_revision(user['id'])
    return {'scope_notes': notes}

@app.get('/workspace/courses', response_model=CourseListResponse, tags=['workspace'])
async def list_courses(user: dict[str, Any]=Depends(require_user)) -> CourseListResponse:
    courses = db.list_courses(user['id'])
    counts: dict[str, int] = {}
    for document in db.list_documents(user['id']):
        counts[document['course_id']] = counts.get(document['course_id'], 0) + 1
    return CourseListResponse(courses=[Course(id=course['id'], name=course['name'], created_at=course['created_at'], documents=counts.get(course['id'], 0)) for course in courses])

@app.post('/workspace/courses', response_model=Course, tags=['workspace'])
async def create_course(req: CourseCreateRequest, user: dict[str, Any]=Depends(require_user)) -> Course:
    try:
        course = db.create_course(user['id'], req.name)
    except Exception as exc:
        if 'UNIQUE' in str(exc).upper():
            raise HTTPException(status_code=409, detail='A course with this name exists.')
        raise
    course_workspace(user['id'], course['id']).mkdir(parents=True, exist_ok=True)
    return Course(**course, documents=0)

@app.delete('/workspace/courses/{course_id}', tags=['workspace'])
async def delete_course(course_id: str, user: dict[str, Any]=Depends(require_user)) -> dict[str, str]:
    course = db.get_course(user['id'], course_id)
    if not course:
        raise HTTPException(status_code=404, detail='Unknown course.')
    _assert_course_editable(user, course)
    documents = db.list_documents(user['id'], [course_id])
    async with WORKSPACE_LOCK:
        for document in documents:
            try:
                await asyncio.to_thread(delete_file, user['id'], course_id, document['filename'])
            except Exception:
                logger.warning('Could not remove chunks for %s', document['filename'], exc_info=True)
            db.delete_document(user['id'], document['filename'], course_id)
        directory = course_workspace(user['id'], course_id).resolve()
        root = user_workspace(user['id']).resolve()
        if directory.is_relative_to(root) and directory.is_dir():
            shutil.rmtree(directory)
        db.delete_course(user['id'], course_id)
        study_library.purge_course(user['id'],course_id)
        LAST_INGEST[user['id']] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    return {'status': 'deleted', 'course_id': course_id}

@app.get('/workspace/files', response_model=AdminFilesResponse, tags=['workspace'])
async def list_workspace_files(course_id: str | None=None, user: dict[str, Any]=Depends(require_user)) -> AdminFilesResponse:
    course_ids = _resolve_course_scope(user['id'], [course_id] if course_id else None)
    documents = db.list_documents(user['id'], course_ids)
    indexed = {(doc['course_id'], doc['source_file']): doc for doc in corpus_documents(user['id'], course_ids)}
    return AdminFilesResponse(files=[_user_file_row(user['id'], document, indexed) for document in documents], chunks=collection_count(user['id']))

def _document_file_path(user_id: str, document: dict[str, Any]) -> Path:
    directory = course_workspace(user_id, document['course_id']).resolve()
    target = (directory / document['filename']).resolve()
    if not target.is_relative_to(directory) or not target.is_file():
        raise HTTPException(status_code=404, detail='The original file is not available.')
    return target

def _document_preview_payload(document: dict[str, Any], file_url: str) -> dict[str, Any]:
    target = _document_file_path(document['user_id'], document)
    suffix = Path(document['filename']).suffix.lower()
    payload: dict[str, Any] = {'filename': document['filename'], 'size': document['size'], 'file_url': file_url}
    if suffix == '.pdf':
        payload.update({'mode': 'pdf', 'content': ''})
    elif suffix in __import__('upload_limits').IMAGE_EXTENSIONS:
        payload.update({'mode':'image','content':''})
    elif suffix in {'.md', '.markdown'}:
        text = target.read_text(encoding='utf-8', errors='replace')
        payload.update({'mode': 'markdown', 'content': MARKDOWN_PREVIEW.render(text)})
    elif suffix in {'.txt', '.csv', '.log', '.json'}:
        payload.update({'mode': 'text', 'content': target.read_text(encoding='utf-8', errors='replace')})
    elif suffix in {'.doc', '.docx'}:
        try:
            text = extract_office_text(target.read_bytes())
        except Exception:
            logger.exception('Could not extract Word preview for %s', document['filename'])
            text = ''
        if text.strip():
            payload.update({'mode': 'text', 'content': text[:400000]})
        else:
            payload.update({'mode': 'file', 'content': ''})
    else:
        payload.update({'mode': 'file', 'content': ''})
    return payload

@app.get('/workspace/documents/{document_id}/preview', tags=['workspace'])
async def preview_workspace_document(document_id: str, user: dict[str, Any]=Depends(require_user)) -> dict[str, Any]:
    document = db.get_document(user['id'], document_id)
    if not document:
        raise HTTPException(status_code=404, detail='Unknown document.')
    return _document_preview_payload(document, f'/workspace/documents/{document_id}/file')

@app.get('/workspace/documents/{document_id}/file', tags=['workspace'])
async def preview_workspace_document_file(document_id: str, user: dict[str, Any]=Depends(require_user)) -> FileResponse:
    document = db.get_document(user['id'], document_id)
    if not document:
        raise HTTPException(status_code=404, detail='Unknown document.')
    target = _document_file_path(user['id'], document)
    media_type = mimetypes.guess_type(document['filename'])[0] or 'application/octet-stream'
    return FileResponse(target, media_type=media_type, filename=document['filename'], content_disposition_type='inline')

@app.get('/workspace/documents/{document_id}/download', tags=['workspace'])
async def download_workspace_document(document_id: str, request: Request, user: dict[str, Any]=Depends(require_user)) -> FileResponse:
    enforce_rate_limit(request, DOWNLOAD_LIMIT, 'download', user_id=user['id'])
    document = db.get_document(user['id'], document_id)
    if not document:
        raise HTTPException(status_code=404, detail='Unknown document.')
    target = _document_file_path(user['id'], document)
    media_type = mimetypes.guess_type(document['filename'])[0] or 'application/octet-stream'
    return FileResponse(target, media_type=media_type, filename=document['filename'])

@app.put('/workspace/documents/{document_id}/syllabus', tags=['workspace'])
async def set_document_syllabus(document_id: str, req: DocumentSyllabusRequest, user: dict[str, Any]=Depends(require_user)):
    document = db.get_document(user['id'], document_id)
    if not document:
        raise HTTPException(404, 'Unknown document.')
    course = db.get_course(user['id'], document['course_id'])
    _assert_course_editable(user, course)
    async with WORKSPACE_LOCK:
        with db.connect() as connection:
            connection.execute('UPDATE documents SET syllabus_enabled=? WHERE id=? AND user_id=?', (int(req.enabled), document_id, user['id']))
    return {'document_id': document_id, 'syllabus_enabled': req.enabled}

@app.patch('/workspace/documents/{document_id}', tags=['workspace'])
async def update_workspace_document(document_id: str, req: DocumentUpdateRequest, user: dict[str, Any]=Depends(require_user)) -> dict[str, Any]:
    document = db.get_document(user['id'], document_id)
    if not document:
        raise HTTPException(status_code=404, detail='Unknown document.')
    source_course = db.get_course(user['id'], document['course_id'])
    if not source_course:
        raise HTTPException(status_code=404, detail='Unknown course.')
    _assert_course_editable(user, source_course)
    target_course = source_course
    if req.course_id and req.course_id != document['course_id']:
        target_course = db.get_course(user['id'], req.course_id)
        if not target_course:
            raise HTTPException(status_code=404, detail='Unknown destination course.')
        _assert_course_editable(user, target_course)
    new_name = sanitize_filename(req.filename or document['filename'])
    if not Path(new_name).suffix:
        new_name += Path(document['filename']).suffix
    if Path(new_name).suffix.lower() not in ALLOWED_CORPUS_EXTENSIONS:
        raise HTTPException(status_code=400, detail='Unsupported file type.')
    source_dir = course_workspace(user['id'], document['course_id']).resolve()
    target_dir = course_workspace(user['id'], target_course['id']).resolve()
    source_path = (source_dir / document['filename']).resolve()
    target_path = (target_dir / new_name).resolve()
    if not source_path.is_relative_to(source_dir) or not target_path.is_relative_to(target_dir):
        raise HTTPException(status_code=400, detail='Invalid file path.')
    if not source_path.is_file():
        raise HTTPException(status_code=404, detail='The original file is not available.')
    if target_path != source_path and target_path.exists():
        raise HTTPException(status_code=409, detail='A file with that name already exists in the destination.')
    if target_course['id'] != document['course_id']:
        retention.check_documents(user['id'], target_course['id'], 1, user_increment=0, check_jobs=False)
    target_dir.mkdir(parents=True, exist_ok=True)
    if target_path != source_path:
        source_path.replace(target_path)
    db.update_document_location(user['id'], document['id'], filename=new_name, course_id=target_course['id'])
    try:
        await asyncio.to_thread(update_file_identity, user['id'], document['course_id'], document['filename'], new_course_id=target_course['id'], new_course_name=target_course['name'], new_filename=new_name)
    except Exception:
        logger.exception('Could not update indexed metadata after moving %s', document['filename'])
    return {'status': 'updated', 'document': db.get_document(user['id'], document['id'])}

@app.get('/workspace/download-all', tags=['workspace'])
async def download_workspace_files(course_id: str | None=None, user: dict[str, Any]=Depends(require_user)) -> Response:
    courses = db.list_courses(user['id'])
    selected = [course for course in courses if not course_id or course['id'] == course_id]
    if course_id and (not selected):
        raise HTTPException(status_code=404, detail='Unknown course.')
    buffer = io.BytesIO()
    added = 0
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for course in selected:
            directory = course_workspace(user['id'], course['id']).resolve()
            for document in db.list_course_documents(course['id']):
                target = (directory / document['filename']).resolve()
                if target.is_relative_to(directory) and target.is_file():
                    archive.write(target, f"{course['name']}/{document['filename']}")
                    added += 1
    if not added:
        raise HTTPException(status_code=404, detail='No original files to download.')
    suffix = f"-{selected[0]['name']}" if course_id else ''
    return Response(buffer.getvalue(), media_type='application/zip', headers={'Content-Disposition': f'attachment; filename="study-desk-files{suffix}.zip"'})

@app.post('/workspace/files/local', response_model=UploadResponse, tags=['workspace'], include_in_schema=False)
@app.post('/workspace/files', response_model=UploadResponse, tags=['workspace'])
async def upload_workspace_files(request: Request, course_id: str=Form(...), doc_type: DocumentType=Form('notes'), files: list[UploadFile]=File(...), user: dict[str, Any]=Depends(require_user)) -> UploadResponse:
    local_owner_upload = request.url.path.endswith('/local')
    if local_owner_upload:
        if not _is_trusted_local_owner(request, user):
            raise HTTPException(status_code=404, detail='Not found.')
    elif not request.url.path.startswith('/workspace/uploads/'):
        enforce_rate_limit(request, UPLOAD_LIMIT, 'upload', user_id=user['id'])
    course = db.get_course(user['id'], course_id)
    if not course:
        raise HTTPException(status_code=404, detail='Unknown course.')
    _assert_course_editable(user, course)
    max_files = MAX_BATCH_FILES
    max_batch = MAX_BATCH_BYTES
    if not files or len(files) > max_files:
        raise HTTPException(status_code=400, detail=f'Upload between 1 and {max_files} files.')
    prepared: list[tuple[str, bytes, dict[str, Any]]] = []
    total = 0
    batch_names: set[str] = set()
    batch_digests: set[str] = set()
    for file in files:
        data = await _read_upload(file, min(MAX_UPLOAD_BYTES,max_batch))
        total += len(data)
        if total > max_batch:
            raise HTTPException(status_code=413, detail='Batch upload is too large.')
        validated = await asyncio.to_thread(validate_upload, file.filename or 'upload', data, corpus=True, max_bytes=min(MAX_UPLOAD_BYTES,max_batch))
        name = validated['filename']
        if validated.get('active_content'):
            logger.warning('Accepted PDF with active/embedded content: %s', name)
        if name in batch_names:
            raise HTTPException(status_code=400, detail=f"The batch contains the same filename twice: '{name}'.")
        batch_names.add(name)
        if validated['sha256'] in batch_digests:
            raise HTTPException(409,'The same file content was selected twice. Remove the duplicate before uploading.')
        batch_digests.add(validated['sha256'])
        prepared.append((name, data, validated))
    storage_limit = _storage_limit(user)
    if db.user_storage_bytes(user['id']) + total > storage_limit:
        raise HTTPException(status_code=413, detail=f'This upload would exceed the {storage_limit // 1024 ** 3} GB storage limit.')
    directory = course_workspace(user['id'], course_id)
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    try:
        async with WORKSPACE_LOCK:
            documents = db.list_documents(user['id'], [course_id])
            documents_by_name = {doc['filename']: doc for doc in documents}
            indexed_keys = {(doc['course_id'], doc['source_file']) for doc in corpus_documents(user['id'], [course_id])}
            to_write: list[tuple[str, bytes]] = []
            index_names: list[str] = []
            already_present = 0
            for name, data, _validated in prepared:
                target = (directory / name).resolve()
                if not target.is_relative_to(directory.resolve()):
                    raise HTTPException(status_code=400, detail='Invalid destination path.')
                digest = hashlib.sha256(data).hexdigest()
                if target.exists():
                    document = documents_by_name.get(name)
                    if document and document.get('sha256') == digest:
                        already_present += 1
                        if (course_id, name) not in indexed_keys:
                            index_names.append(name)
                        continue
                    try:
                        disk_digest = hashlib.sha256(target.read_bytes()).hexdigest()
                    except OSError:
                        disk_digest = ''
                    if disk_digest == digest:
                        already_present += 1
                        index_names.append(name)
                        continue
                    raise HTTPException(status_code=409, detail=f"A different file named '{name}' is already in this course. Rename the new file, or remove the existing document before uploading it again.")
                to_write.append((name, data))
                index_names.append(name)
            retention.check_documents(user['id'], course_id, len(to_write))
            for name, data in to_write:
                target = (directory / name).resolve()
                temp = target.with_name(f'.{name}.{uuid.uuid4().hex}.uploading')
                with open(temp, 'xb') as handle:
                    handle.write(data)
                os.replace(temp, target)
                written.append(target)
            records = []
            for name, data, validated in prepared:
                existing = db.get_document_by_name(user['id'], course_id, name)
                records.append({'course_id': course_id, 'course_name': course['name'], 'filename': name, 'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data), 'page_count': int(validated.get('page_count', 0) or 0), 'doc_type': existing.get('doc_type', doc_type) if existing else doc_type, 'chunks': 0, 'pages': []})
            if records:
                await asyncio.to_thread(db.sync_documents, user['id'], records, prune=False)
            for name, _data, validated in prepared:
                if validated.get('_pdf_pages'):
                    document = index_cache.identity(user['id'], course_id, name)
                    signature = index_cache.signature(validated['sha256'])
                    await asyncio.to_thread(index_cache.save_many, document, user['id'], 'text', signature, [(number, {'text': text}) for number, text in validated['_pdf_pages']])
            if index_names:
                job = db.add_index_job(user['id'], course_id, index_names, doc_type)
                await _enqueue_index_job(job)
                ingest = {'status': 'queued', 'chunks': 0, 'files': [], 'job_id': job['id']}
            else:
                job = None
                ingest = {'chunks': await asyncio.to_thread(collection_count, user['id']), 'files': [], 'status': 'already_indexed'}
    except HTTPException:
        for path in written:
            path.unlink(missing_ok=True)
            try:
                await asyncio.to_thread(delete_file, user['id'], course_id, path.name)
            except Exception:
                pass
        raise
    except Exception:
        for path in written:
            path.unlink(missing_ok=True)
            try:
                await asyncio.to_thread(delete_file, user['id'], course_id, path.name)
            except Exception:
                pass
        logger.exception('Batch upload failed')
        raise HTTPException(status_code=500, detail='The upload failed while indexing. Files created by this attempt were rolled back. Refresh the workspace before retrying.')
    documents = db.list_documents(user['id'], [course_id])
    indexed = {(doc['course_id'], doc['source_file']): doc for doc in corpus_documents(user['id'], [course_id])}
    by_name = {document['filename']: document for document in documents}
    uploaded = [_user_file_row(user['id'], by_name[name], indexed) for name, _data, _validated in prepared if name in by_name]
    _log_usage(user['id'], 'upload')
    return UploadResponse(uploaded=uploaded, ingest=ingest, already_present=already_present, job_id=job['id'] if job else None)

@app.post('/workspace/courses/{course_id}/import-zip', response_model=UploadResponse, tags=['workspace'])
async def import_course_zip(course_id: str, request: Request, file: UploadFile=File(...), doc_type: DocumentType=Form('notes'), user: dict[str, Any]=Depends(require_user)) -> UploadResponse:
    enforce_rate_limit(request, UPLOAD_LIMIT, 'import-zip', user_id=user['id'])
    course = db.get_course(user['id'], course_id)
    if not course:
        raise HTTPException(status_code=404, detail='Unknown course.')
    _assert_course_editable(user, course)
    data = await _read_upload(file, MAX_BATCH_BYTES)
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        if len(archive.infolist())>2000 or sum(m.file_size for m in archive.infolist())>MAX_BATCH_BYTES:
            raise HTTPException(413,'The ZIP exceeds its file-count or extracted-size limit.')
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=422, detail='This is not a valid zip archive.') from exc
    import course_bundle
    manifest=course_bundle.read_manifest(archive)
    if manifest:
        from math_format import validate as validate_math
        if len(learning_store.listing('revision_sheet',user['id'],20))+len(manifest['sheets'])>20:raise HTTPException(409,'Import would exceed 20 revision sheets. Export and remove older sheets first.')
        try:
            for sheet in manifest['sheets']:await asyncio.to_thread(validate_math,sheet['markdown'])
        except ValueError:raise HTTPException(422,'A personal sheet has invalid math formatting. Fix its delimiters before importing.')
    directory = course_workspace(user['id'], course_id)
    directory.mkdir(parents=True, exist_ok=True)
    records = []
    index_names = []
    wrote = []
    extracted_bytes = 0
    imported_sheets=[]
    job=None
    try:
        with archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                name = os.path.basename(member.filename)
                if not name or name.startswith('.') or '__MACOSX' in member.filename:
                    continue
                if member.file_size > MAX_UPLOAD_BYTES:
                    continue
                payload = archive.read(member)
                extracted_bytes += len(payload)
                if extracted_bytes > MAX_BATCH_BYTES:
                    raise HTTPException(status_code=413, detail='The extracted zip contents exceed the import size limit.')
                try:
                    validated = validate_upload(name, payload, corpus=True)
                except HTTPException:
                    continue
                target = (directory / validated['filename']).resolve()
                file_meta=manifest['files'].get(validated['filename']) if manifest else None
                if manifest and (not file_meta or hashlib.sha256(payload).hexdigest()!=file_meta['sha256']):raise HTTPException(422,'A course document does not match its manifest checksum. No files were imported.')
                if not target.is_relative_to(directory.resolve()):
                    continue
                if target.exists():
                    continue
                retention.check_documents(user['id'], course_id, len(records) + 1)
                target.write_bytes(payload)
                wrote.append(target)
                index_names.append(validated['filename'])
                records.append({'course_id': course_id, 'course_name': course['name'], 'filename': validated['filename'], 'sha256': hashlib.sha256(payload).hexdigest(), 'size': len(payload), 'page_count': int(validated.get('page_count', 0) or 0), 'doc_type': file_meta['doc_type'] if file_meta else doc_type})
                if len(records) >= MAX_BATCH_FILES:
                    break
        if not records:
            raise HTTPException(status_code=422, detail='No supported documents were found in the zip.')
        db.sync_documents(user['id'], records, prune=False)
        if manifest:
            with db.connect() as c:
                for record in records:c.execute('UPDATE documents SET syllabus_enabled=? WHERE user_id=? AND course_id=? AND filename=?',(int(manifest['files'][record['filename']]['syllabus_enabled']),user['id'],course_id,record['filename']))
            imported_sheets=course_bundle.restore_personal(user['id'],course_id,manifest)
        job = db.add_index_job(user['id'], course_id, index_names, doc_type)
        await _enqueue_index_job(job)
    except HTTPException:
        for path in wrote:
            path.unlink(missing_ok=True)
        for record in records:db.delete_document(user['id'],record['filename'],course_id)
        for key in imported_sheets:learning_store.remove('revision_sheet',key,user['id'])
        if job:
            with db.connect() as c:c.execute('DELETE FROM index_jobs WHERE id=? AND user_id=?',(job['id'],user['id']))
        raise
    except Exception:
        for path in wrote:
            path.unlink(missing_ok=True)
        for record in records:db.delete_document(user['id'],record['filename'],course_id)
        for key in imported_sheets:learning_store.remove('revision_sheet',key,user['id'])
        if job:
            with db.connect() as c:c.execute('DELETE FROM index_jobs WHERE id=? AND user_id=?',(job['id'],user['id']))
        logger.exception('ZIP import failed')
        raise HTTPException(status_code=422, detail='Could not import this zip archive.')
    docs = {doc['filename']: doc for doc in db.list_documents(user['id'], [course_id])}
    uploaded = [_user_file_row(user['id'], docs[name], {}) for name in index_names if name in docs]
    _log_usage(user['id'], 'upload')
    return UploadResponse(uploaded=uploaded, ingest={'status': 'queued', 'chunks': 0, 'files': [], 'job_id': job['id']}, job_id=job['id'])

@app.put('/workspace/files/{document_id}/type', tags=['workspace'])
async def update_workspace_file_type(document_id: str, req: DocumentTypeRequest, request: Request, user: dict[str, Any]=Depends(require_user)) -> dict[str, str]:
    enforce_rate_limit(request, DOC_TYPE_LIMIT, 'file-type', user_id=user['id'])
    async with WORKSPACE_LOCK:
        document = db.get_document(user['id'], document_id)
        if not document:
            raise HTTPException(404, 'Unknown document.')
        course = db.get_course(user['id'], document['course_id'])
        if course:
            _assert_course_editable(user, course)
        if db.active_index_job(user['id'], document['course_id']):
            raise HTTPException(409, 'Wait for this course to finish indexing before changing document types.')
        if document['doc_type'] != req.doc_type:
            def save_type():
                try:
                    update_file_doc_type(user['id'], document['course_id'], document['filename'], req.doc_type)
                    if not db.update_document_type(user['id'], document_id, req.doc_type):
                        raise RuntimeError('Document disappeared during type update')
                except Exception:
                    # Keep registry and retrieval aligned if either store fails.
                    try:
                        update_file_doc_type(user['id'], document['course_id'], document['filename'], document['doc_type'])
                    except Exception:
                        logger.exception('Could not restore indexed document type')
                    raise
            try:
                await asyncio.to_thread(save_type)
            except Exception:
                logger.exception('Could not save document type')
                raise HTTPException(503, 'Could not save the document type. Please retry.')
    return {'status': 'updated', 'doc_type': req.doc_type}

@app.delete('/workspace/files/{document_id}', tags=['workspace'])
async def delete_workspace_file(document_id: str, request: Request, user: dict[str, Any]=Depends(require_user)) -> dict[str, str]:
    enforce_rate_limit(request, UPLOAD_LIMIT, 'delete-file', user_id=user['id'])
    document = db.get_document(user['id'], document_id)
    if not document:
        raise HTTPException(status_code=404, detail='Unknown document.')
    course = db.get_course(user['id'], document['course_id'])
    if course:
        _assert_course_editable(user, course)
    directory = course_workspace(user['id'], document['course_id']).resolve()
    target = (directory / document['filename']).resolve()
    if not target.is_relative_to(directory):
        raise HTTPException(status_code=400, detail='Invalid file path.')
    async with WORKSPACE_LOCK:
        if target.is_symlink():
            raise HTTPException(status_code=400, detail='Symlinks cannot be removed.')
        target.unlink(missing_ok=True)
        db.delete_document(user['id'], document['filename'], document['course_id'])
        await asyncio.to_thread(delete_file, user['id'], document['course_id'], document['filename'])
        LAST_INGEST[user['id']] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    _log_usage(user['id'], 'delete')
    return {'status': 'deleted', 'document_id': document_id}

@app.post('/workspace/reindex', tags=['workspace'])
@index_limit
async def reindex_workspace(request: Request, req: CourseReindexRequest, user: dict[str, Any]=Depends(require_user)) -> dict[str, Any]:
    enforce_rate_limit(request, UPLOAD_LIMIT, 'reindex', user_id=user['id'])
    async with WORKSPACE_LOCK:
        course = db.get_course(user['id'], req.course_id)
        if not course:
            raise HTTPException(404, 'Choose an existing course before rebuilding its index.')
        _assert_course_editable(user, course)
        documents = db.list_documents(user['id'], [course['id']])
        if not documents:
            raise HTTPException(422, 'This course has no documents. Upload course material before rebuilding its index.')
        if db.active_index_job(user['id'], course['id']):
            raise HTTPException(409, 'This course is already being indexed. Wait for indexing to finish.')
        import growth_limits
        growth_limits.disk()
        job = db.add_index_job(user['id'], course['id'], [doc['filename'] for doc in documents], 'rebuild')
    await _enqueue_index_job(job)
    _log_usage(user['id'], 'reindex')
    return {'status': 'queued', 'job_id': job['id'], 'course_id': course['id']}

@app.get('/workspace/health', response_model=WorkspaceHealthResponse, tags=['workspace'])
async def workspace_health(user: dict[str, Any]=Depends(require_user)) -> WorkspaceHealthResponse:
    return WorkspaceHealthResponse(user={'id': user['id'], 'name': 'Local workspace', 'is_admin': True}, courses=len(_owned_courses(user['id'])), documents=len(db.list_documents(user['id'])), chunks=collection_count(user['id']), last_indexed_at=LAST_INGEST.get(user['id']) or _latest_document_time(user['id']), max_attempts=db.get_settings(user['id']).get('attempts_before_reveal', 3), storage_bytes=db.user_storage_bytes(user['id']), storage_limit_bytes=_storage_limit(user))

@app.get('/workspace/jobs', tags=['workspace'])
async def list_workspace_jobs(user: dict[str, Any]=Depends(require_user)) -> dict[str, Any]:
    return {'jobs': [{**job, 'processing': index_cache.details(job['id'])} for job in db.list_index_jobs(user['id'], 20)]}

@app.post('/workspace/jobs/{job_id}/retry', tags=['workspace'])
@index_limit
async def retry_workspace_job(job_id: str, request: Request, user: dict[str, Any]=Depends(require_user)) -> dict[str, str]:
    job = db.get_index_job(job_id)
    if not job or job['user_id'] != user['id']:
        raise HTTPException(status_code=404, detail='Unknown indexing job.')
    if job['status'] not in {'failed', 'done'}:
        raise HTTPException(status_code=409, detail='This job is still running.')
    db.update_index_job(job_id, 'queued', 'Retry requested.', progress=0)
    await _enqueue_index_job(job)
    return {'status': 'queued'}

@app.get('/workspace/snapshot', response_model=WorkspaceSnapshotResponse, tags=['workspace'])
async def workspace_snapshot(user: dict[str, Any]=Depends(require_user)) -> WorkspaceSnapshotResponse:
    courses = db.list_courses(user['id'])
    documents = db.list_documents(user['id'])
    course_counts: dict[str, int] = {}
    for document in documents:
        course_counts[document['course_id']] = course_counts.get(document['course_id'], 0) + 1
    indexed = {(doc['course_id'], doc['source_file']): doc for doc in corpus_documents(user['id'], [course['id'] for course in courses])}
    return WorkspaceSnapshotResponse(health=WorkspaceHealthResponse(user={'id': user['id'], 'name': 'Local workspace', 'is_admin': True}, courses=len(courses), documents=len(documents), chunks=collection_count(user['id']), last_indexed_at=LAST_INGEST.get(user['id']) or max((document['created_at'] for document in documents), default=None), max_attempts=db.get_settings(user['id']).get('attempts_before_reveal', 3), storage_bytes=db.user_storage_bytes(user['id']), storage_limit_bytes=_storage_limit(user)), courses=[Course(**course, documents=course_counts.get(course['id'], 0)) for course in courses], files=[_user_file_row(user['id'], document, indexed) for document in documents])

def _latest_document_time(user_id: str) -> str | None:
    documents = db.list_documents(user_id)
    if not documents:
        return None
    return max((document['created_at'] for document in documents))

@app.get('/favicon.ico', include_in_schema=False)
async def favicon() -> FileResponse:
    return FileResponse(STATIC_DIR / 'favicon.ico', media_type='image/x-icon')
import index_cache
import chunk_uploads
chunk_uploads.install(app, globals())
import rate_limits
rate_limits.install(app)
import explanations
explanations.install(app, globals())
import learning_api
learning_api.install(app)
import study_extensions
study_extensions.install(app, globals())
import bank_exam
bank_exam.install(app, globals())
if STATIC_DIR.is_dir():
    app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')
from ingress_security import IngressSecurity
app.add_middleware(IngressSecurity, services=globals())
from local_runtime import LocalBoundary, install_local
install_local(app)
app.add_middleware(LocalBoundary)
import compliance
compliance.install(app)
app.add_middleware(compliance.DataUseBoundary)
import attachment_batch
attachment_batch.install(app,globals())
import providers
providers.install(app)
import study_companion
study_companion.install(app,globals())
import local_jobs,study_library,backup_tools
study_library.install(app,globals())
backup_tools.install(app,globals())
import course_bundle
course_bundle.install(app,globals())
