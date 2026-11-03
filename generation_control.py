"""Queue-aware generation deadlines and atomic publication of learning artifacts.

Network calls never hold a SQLite writer lock. Learning writes are staged during
the pipeline and flushed in one real transaction. Billing/diagnostics stay durable.
"""
import asyncio
import copy
import functools
import inspect
import logging
import threading
from contextvars import ContextVar
from starlette.responses import JSONResponse
from fastapi import HTTPException
import db
from pipeline_runtime import generation_slot
CURRENT = ContextVar('generation_publication', default=None)
logger = logging.getLogger(__name__)

class Publication:

    def __init__(self):
        self.phase = 'collecting'
        self.writes = []
        self.overlay = {}
        self.after = []
        self.cleanup = []
        self.lock = threading.RLock()
        self.connection_context = None
        self.connection_token = None
        self.connection = None

    def defer(self, callback):
        with self.lock:
            if self.phase == 'closed':
                raise RuntimeError('Generation was cancelled; publication is closed.')
            if self.phase == 'collecting':
                self.writes.append(callback)
                return True
            return False

    def begin_publish(self):
        if self.connection_context is None:
            self.connection_context = db.connect()
            self.connection = self.connection_context.__enter__()
            self.connection.execute('BEGIN IMMEDIATE')
            self.connection_token = db.COMMIT_CONNECTION.set(self.connection)

    def finish(self, error=None):
        context = self.connection_context
        self.connection_context = None
        if context is not None:
            if self.connection_token is not None:
                db.COMMIT_CONNECTION.reset(self.connection_token)
                self.connection_token = None
            context.__exit__(type(error) if error else None, error, error.__traceback__ if error else None)

    def commit(self):
        self.phase = 'committing'
        self.begin_publish()
        try:
            for callback in self.writes:
                callback()
        except BaseException as exc:
            self.finish(exc)
            raise
        self.finish()
        self.phase = 'closed'

    async def rollback(self):
        self.phase = 'closed'
        self.writes.clear()
        self.overlay.clear()
        self.after.clear()
        self.finish(RuntimeError('Generation publication rolled back.'))
        token = CURRENT.set(None)
        try:
            for callback in reversed(self.cleanup):
                try:
                    result = callback()
                    if inspect.isawaitable(result):
                        await result
                except Exception:
                    logger.exception('Provisional generation cleanup failed')
        finally:
            CURRENT.reset(token)

def defer(callback):
    unit = CURRENT.get()
    return unit is not None and unit.defer(callback)

def publish_now():
    """Start the short publication transaction only after all model work."""
    unit = CURRENT.get()
    if unit is not None:
        unit.begin_publish()

def after_commit(callback):
    unit = CURRENT.get()
    if unit is not None:
        if unit.phase == 'closed':
            raise RuntimeError('Publication is closed.')
        unit.after.append(callback)
        return True
    return False

async def atomic_generation(factory):
    if CURRENT.get() is not None:
        return await factory()
    unit = Publication()
    token = CURRENT.set(unit)
    try:
        async with generation_slot():
            result = await factory()
            if getattr(result, 'status_code', 200) >= 400:
                raise HTTPException(result.status_code, 'Generation was withheld.')
        try:
            unit.commit()
        except Exception as exc:
            exc.pipeline_stage='publication'
            raise
    except BaseException:
        await unit.rollback()
        raise
    finally:
        CURRENT.reset(token)
    for callback in unit.after:
        try:
            callback()
        except Exception:
            logger.exception('Background scheduling failed after publication')
    return result

def generation_endpoint(function):

    @functools.wraps(function)
    async def wrapped(*args, **kwargs):

        async def prepare():
            result = await function(*args, **kwargs)
            if not isinstance(result, JSONResponse):
                import json, hashlib
                from fastapi.encoders import jsonable_encoder
                encoded = json.dumps(jsonable_encoder(result), ensure_ascii=False, allow_nan=False, separators=(',', ':'))
                request = kwargs.get('request')
                if request is None:
                    bound = inspect.signature(function).bind_partial(*args, **kwargs)
                    request = bound.arguments.get('request')
                if request is not None and request.headers.get('Idempotency-Key'):
                    from usage_log import current_user_id
                    import learning_store
                    user = current_user_id()
                    if user:
                        digest = hashlib.sha256(request.url.path.encode() + await request.body()).hexdigest()
                        learning_store.save_receipt(user, request.headers['Idempotency-Key'], digest, 200, encoded)
            return result
        try:
            return await atomic_generation(prepare)
        except BaseException as exc:
            if isinstance(exc, asyncio.CancelledError):
                raise
            if isinstance(exc, HTTPException) and exc.status_code not in {422, 500, 503, 504}:
                raise
            if not isinstance(exc, Exception):
                raise
            from generation_errors import describe
            payload,status=describe(exc)
            logger.warning('generation_failure stage=%s code=%s reason=%s',payload['stage'],payload['code'],payload['reason'])
            return JSONResponse(payload,status_code=status)
    wrapped.__signature__ = inspect.signature(function, eval_str=True)
    return wrapped

def stage_put(function):

    @functools.wraps(function)
    def wrapped(kind, identifier, user_id, payload):
        unit = CURRENT.get()
        if unit is not None and unit.phase != 'committing':
            saved = copy.deepcopy(payload)
            if unit.defer(lambda: function(kind, identifier, user_id, saved)):
                unit.overlay[kind, identifier] = (user_id, saved)
                return []
        return function(kind, identifier, user_id, payload)
    return wrapped
