"""Durable tutor snapshots and serialized, replayable HTTP study requests."""
import asyncio
import hashlib
import json
import logging
from collections import OrderedDict
from langchain_core.messages import messages_from_dict, messages_to_dict
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
import learning_store as store
logger = logging.getLogger(__name__)

class DurableGraph:

    def __init__(self, graph):
        self.inner = graph
        self.locks = OrderedDict()

    def __getattr__(self, key):
        return getattr(self.inner, key)

    def _id(self, config):
        return config['configurable']['thread_id']

    async def aget_state(self, config, **kwargs):
        snapshot = await self.inner.aget_state(config, **kwargs)
        saved = store.get('tutor', self._id(config))
        if snapshot.values and snapshot.values.get('user_id') and (not saved):
            await self.inner.checkpointer.adelete_thread(self._id(config))
            return await self.inner.aget_state(config, **kwargs)
        if not snapshot.values:
            value = saved
            if value:
                value['messages'] = messages_from_dict(value.get('messages', []))
                node = 'generate_question' if value.get('status') == 'awaiting_answer' else 'grade_answer'
                await self.inner.aupdate_state(config, value, as_node=node)
                if node == 'generate_question':
                    await self.inner.ainvoke(None, config)
                snapshot = await self.inner.aget_state(config)
        return snapshot

    async def ainvoke(self, value, config, **kwargs):
        from generation_control import CURRENT
        publication = CURRENT.get()
        if publication is not None:
            publication.cleanup.append(lambda: self.inner.checkpointer.adelete_thread(self._id(config)))
        if value is not None and (not isinstance(value, dict)):
            await self.aget_state(config)
        try:
            result = await self.inner.ainvoke(value, config, **kwargs)
        except BaseException:
            if isinstance(value, dict) and value.get('user_id'):
                await self.inner.checkpointer.adelete_thread(self._id(config))
            raise
        if result and result.get('user_id'):
            from tools import db_user_active
            if not db_user_active(result['user_id']):
                await self.inner.checkpointer.adelete_thread(self._id(config))
                from fastapi import HTTPException
                raise HTTPException(403, 'This account is no longer available for study work.')
        if result and result.get('user_id') and result.get('current_question'):
            saved = {k: v for k, v in result.items() if not k.startswith('__')}
            from pipeline_runtime import BACKGROUND
            saved['prepared'] = bool(saved.get('path_id') or saved.get('exam_id') or (BACKGROUND.get() and (not saved.get('user_attempts'))))
            saved['messages'] = messages_to_dict(saved.get('messages', []))
            expired = store.put('tutor', self._id(config), saved['user_id'], saved)
            for item in expired:
                if item['kind'] == 'tutor':
                    await self.inner.checkpointer.adelete_thread(item['id'])
            try:
                if saved.get('mode') == 'practice' and saved.get('user_attempts', 0) == 0:
                    import curriculum
                    store.bank_add(saved['user_id'], saved, curriculum.scope_version(saved['user_id'], saved.get('course_ids', [])))
                if saved.get('user_attempts', 0):
                    parts = saved.get('part_results') or []
                    score = sum(({'correct': 1.0, 'partial': 0.5}.get(p.get('verdict'), 0) for p in parts)) / len(parts) if parts else float(saved['status'] == 'correct')
                    store.outcome(saved['user_id'], f"{self._id(config)}:{saved['user_attempts']}", saved.get('skill_id', ''), score, saved['user_attempts'])
            except Exception:
                logger.exception('Optional bank/mastery update failed; the durable study session is saved')
        return result

class StudyRequests:
    """ASGI middleware: serialize writes per account and replay completed requests.

    Receipts are committed before sending a response. Browser reconnection uses
    the same key; simultaneous different keys still cannot race an attempt.
    """

    def __init__(self, app):
        self.app = app
        self.locks = OrderedDict()

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '')
        if scope['type'] != 'http' or scope['method'] not in {'POST', 'DELETE'} or (not (path in {'/ask', '/ask/question', '/answer', '/explain', '/ask/path','/study/recall'} or (path.startswith('/progress/flashcards/') and path.endswith('/review')) or path.startswith('/ask/path/') or path.startswith('/practice/follow-up/') or path == '/bank-exams' or path.startswith('/bank-exams/'))):
            return await self.app(scope, receive, send)
        from auth import current_user
        request = Request(scope, receive)
        try:
            user = await current_user(request)
        except Exception:
            return await self.app(scope, receive, send)
        body = await request.body()
        if len(body) > 100000:
            return await JSONResponse({'detail': 'Request too large.'}, 413)(scope, receive, send)
        key = request.headers.get('Idempotency-Key', '')
        if len(key) > 128:
            return await JSONResponse({'detail': 'Invalid request identifier.'}, 400)(scope, receive, send)
        digest = hashlib.sha256(path.encode() + body).hexdigest()
        lock = self.locks.setdefault(user['id'], asyncio.Lock())
        async with lock:
            if key:
                try:
                    prior = store.receipt(user['id'], key, digest)
                except ValueError as exc:
                    return await JSONResponse({'detail': str(exc)}, 409)(scope, receive, send)
                if prior:
                    if prior['status'] == 102:
                        message = 'Open Learning tools to resume the saved session; this request will not be submitted twice.'
                        return await JSONResponse({'detail': message}, 409)(scope, receive, send)
                    if prior['status'] < 400:
                        import study_persistence
                        from fastapi import HTTPException
                        try:
                            study_persistence.replay_access(user, path, json.loads(prior['body']))
                        except HTTPException as error:
                            return await JSONResponse({'detail': error.detail}, error.status_code)(scope, receive, send)
                    if path == '/explain' and prior['status'] < 400:
                        import app as application
                        import curriculum
                        payload = json.loads(prior['body'])
                        if application._course_access_lost(user['id'], payload['course_ids']):
                            return await JSONResponse({'detail': 'Course access changed. This explanation cannot be replayed.'}, 403)(scope, receive, send)
                        if payload['version'] != curriculum.scope_version(user['id'], payload['course_ids']):
                            return await JSONResponse({'detail': 'Course material changed. Start a fresh explanation request.'}, 409)(scope, receive, send)
                    return await Response(prior['body'], prior['status'], media_type='application/json', headers={'Idempotent-Replayed': 'true'})(scope, receive, send)
                store.save_receipt(user['id'], key, digest, 102, '')
            delivered = False

            async def replay():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {'type': 'http.request', 'body': body, 'more_body': False}
                return await receive()
            messages = []

            async def capture(message):
                messages.append(message)
            try:
                await self.app(scope, replay, capture)
            except BaseException:
                if key:
                    with store.db.connect() as connection:
                        connection.execute('DELETE FROM learning_receipts WHERE user_id=? AND key=? AND status=102', (user['id'], key))
                raise
            status = next((m['status'] for m in messages if m['type'] == 'http.response.start'), 500)
            if status < 400 and (path == '/ask' or path.startswith('/practice/follow-up/')):
                data = b''.join((m.get('body', b'') for m in messages if m['type'] == 'http.response.body'))
                try:
                    store.mark_served(user['id'], json.loads(data)['question'])
                except (KeyError, ValueError):
                    pass
            if key and status < 400:
                data = b''.join((m.get('body', b'') for m in messages if m['type'] == 'http.response.body'))
                store.save_receipt(user['id'], key, digest, status, data.decode())
            elif key:
                with store.db.connect() as connection:
                    connection.execute('DELETE FROM learning_receipts WHERE user_id=? AND key=?', (user['id'], key))
            for message in messages:
                await send(message)
        if len(self.locks) > 2048:
            for owner, candidate in list(self.locks.items()):
                if owner != user['id'] and (not candidate.locked()) and (not getattr(candidate, '_waiters', None)):
                    self.locks.pop(owner, None)
                    break
