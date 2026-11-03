"""Short-lived, user-scoped progress snapshots for interactive generation."""
from __future__ import annotations
import contextvars
import time
import uuid
_REQUEST_ID: contextvars.ContextVar[str] = contextvars.ContextVar('generation_request_id', default='')
_ACTIVE: dict[str, dict] = {}
_TTL_SECONDS = 180
_MAX_ENTRIES = 128
STAGE_ANALYZING = 'Analyzing your course material...'
STAGE_DRAFTING = 'Drafting the question...'
STAGE_SOLVING = 'AI is independently solving the math to ensure accuracy...'
STAGE_VERIFYING = 'Verifying against your notes and formatting...'
STAGE_ALMOST = 'Almost done...'

def _prune(now: float) -> None:
    for key, item in list(_ACTIVE.items()):
        if item['done'] and now - item['updated'] > 60:
            _ACTIVE.pop(key, None)
        elif now - item['started'] > _TTL_SECONDS:
            _ACTIVE.pop(key, None)
    while len(_ACTIVE) > _MAX_ENTRIES:
        oldest = min(_ACTIVE, key=lambda key: _ACTIVE[key]['updated'])
        _ACTIVE.pop(oldest, None)

def start(user_id: str, request_id: str='') -> str:
    request_id = request_id or uuid.uuid4().hex
    now = time.monotonic()
    _prune(now)
    _ACTIVE[request_id] = {'user_id': user_id, 'started': now, 'updated': now, 'stage': STAGE_ANALYZING, 'done': False, 'error': ''}
    return request_id

def bind(request_id: str):
    return _REQUEST_ID.set(request_id)

def unbind(token) -> None:
    _REQUEST_ID.reset(token)

def stage(message: str) -> None:
    request_id = _REQUEST_ID.get()
    item = _ACTIVE.get(request_id)
    if not item or item['done']:
        return
    item['stage'] = message
    item['updated'] = time.monotonic()

def finish(request_id: str, error: str='') -> None:
    item = _ACTIVE.get(request_id)
    if not item:
        return
    now = time.monotonic()
    item['stage'] = STAGE_ALMOST if not error else item['stage']
    item['done'] = True
    item['error'] = error[:300]
    item['updated'] = now

def snapshot(request_id: str, user_id: str) -> dict | None:
    item = _ACTIVE.get(request_id)
    if not item or item['user_id'] != user_id:
        return None
    now = time.monotonic()
    if now - item['started'] > _TTL_SECONDS:
        _ACTIVE.pop(request_id, None)
        return None
    return {'request_id': request_id, 'elapsed': round(now - item['started'], 2), 'stage': item['stage'], 'done': item['done'], 'error': item['error']}
