"""Bounded UI/native update bridge. Browser clients cannot supply executables or URLs."""
import asyncio
import hmac
import os
import time
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field
from typing import Literal
from starlette.responses import JSONResponse

class UpdateBoundary:
    def __init__(self, app, bridge): self.app, self.bridge = app, bridge
    async def __call__(self, scope, receive, send):
        mutation = scope['type'] == 'http' and scope['method'] in {'POST','PUT','PATCH','DELETE'} and not scope['path'].startswith('/desktop/update/') and scope['path'] != '/desktop/stop'
        if mutation:
            if self.bridge.frozen:
                return await JSONResponse({'detail':'An update is preparing to restart. Wait for Study Desk to reopen.'}, status_code=409)(scope, receive, send)
            self.bridge.active += 1
        try: return await self.app(scope, receive, send)
        finally:
            if mutation: self.bridge.active -= 1

class NativeResult(BaseModel):
    state: Literal['idle','checking','available','current','downloading','downloaded','installing','error']
    message: str = Field(default='', max_length=300)
    version: str = Field(default='', max_length=40)
    received: int = Field(default=0, ge=0)
    total: int = Field(default=0, ge=0)

class Bridge:
    def __init__(self):
        self.active=0;self.frozen=False;self.command=None;self.started=0
        self.status={'state':'idle','message':'Check for signed Study Desk updates.','current_version':os.getenv('STUDY_DESKTOP_VERSION','development')}
    def refresh(self):
        if self.command and time.monotonic()-self.started>120:
            self.command=None;self.frozen=False
            self.status.update(state='error',message='The desktop updater did not respond. Reopen Study Desk and try again.')
    def enqueue(self, action):
        self.command=action;self.started=time.monotonic()

def install(app):
    bridge=Bridge();app.state.update_bridge=bridge
    app.add_middleware(UpdateBoundary, bridge=bridge)

    def native(request):
        secret=os.getenv('STUDY_DESKTOP_SECRET','')
        if not secret or not hmac.compare_digest(request.headers.get('x-study-desktop','').encode(),secret.encode()):
            raise HTTPException(403,'This operation belongs to the desktop updater.')

    @app.get('/desktop/update/status')
    async def status():
        bridge.refresh()
        return bridge.status

    @app.get('/desktop/update/command')
    async def command(request:Request):
        native(request);bridge.refresh()
        action=bridge.command;bridge.command=None
        return {'action':action}

    @app.post('/desktop/update/result')
    async def result(body:NativeResult, request:Request):
        native(request)
        bridge.status.update(body.model_dump())
        if body.state=='error':bridge.frozen=False
        return {'ok':True}

    @app.post('/desktop/update/{action}')
    async def action(action:str):
        bridge.refresh()
        if action not in {'check','download','install'}:raise HTTPException(404,'Unknown update action.')
        allowed={'check':{'idle','current','available','downloaded','error'},'download':{'available'},'install':{'downloaded'}}
        if bridge.command or bridge.status['state'] not in allowed[action]:
            raise HTTPException(409,'Wait for the current update step to finish.')
        if action=='install':
            import app as application,db,backup
            # Freeze before the first await, so no new mutating request can race
            # the idle check/snapshot. Downloads do not freeze ordinary use.
            bridge.frozen=True
            try:
                async with application.WORKSPACE_LOCK:
                    with db.connect() as connection:
                        indexing=connection.execute("SELECT COUNT(*) FROM index_jobs WHERE status IN ('queued','running')").fetchone()[0]
                        uploads=connection.execute("SELECT COUNT(*) FROM upload_batches WHERE status IN ('receiving','processing')").fetchone()[0]
                    if bridge.active or indexing or uploads:
                        raise HTTPException(409,'Finish your current request, uploads and indexing before installing the update.')
                    bridge.status.update(state='installing',message='Creating and verifying a study-data backup…')
                    archive=await asyncio.to_thread(backup.create_backup,backup.backup_directory())
                    import zipfile,sqlite3,tempfile
                    def verify():
                        with zipfile.ZipFile(archive) as package:
                            if package.testzip() is not None:raise ValueError('Invalid backup')
                            with tempfile.TemporaryDirectory() as directory:
                                package.extract('app.db',directory)
                                connection=sqlite3.connect(os.path.join(directory,'app.db'))
                                try:
                                    if connection.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Invalid database snapshot')
                                finally:connection.close()
                    await asyncio.to_thread(verify)
            except Exception as exc:
                if not isinstance(exc,HTTPException):
                    __import__('logging').getLogger(__name__).exception('Pre-update backup verification failed')
                bridge.frozen=False;bridge.status.update(state='downloaded',message='Installation paused. Your existing app and data are unchanged.')
                if isinstance(exc,HTTPException):raise
                raise HTTPException(503,'The pre-update backup could not be verified. Check backup storage and try again.') from exc
        else:bridge.status.update(state='checking' if action=='check' else 'downloading',message='Checking the official update feed…' if action=='check' else 'Downloading and verifying the signed package…',received=0,total=0)
        bridge.enqueue(action)
        return bridge.status
