"""Versioned, local acknowledgement before sending study content to an AI provider."""
from pathlib import Path
from fastapi import HTTPException
from pydantic import BaseModel
from starlette.responses import JSONResponse
from starlette.requests import Request
import db

VERSION = '2026-11-04-providers'
DOCUMENTS = {'privacy': 'PRIVACY.md', 'terms': 'TERMS.md', 'licenses': 'THIRD-PARTY-NOTICES.md'}
AI_PREFIXES = ('/ask', '/answer', '/explain', '/study/recall', '/practice/follow-up')

class Acknowledgement(BaseModel):
    version: str
    accepted: bool

def accepted():
    return db.get_app_setting('data_use_acknowledgement', '') == VERSION

class DataUseBoundary:
    def __init__(self, app): self.app = app
    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http' and scope['method'] == 'POST':
            path = scope['path']
            if any(path == p or path.startswith(p + '/') for p in AI_PREFIXES) and not accepted():
                return await JSONResponse({'detail': 'Review and accept the AI data-use notice in Settings before using AI study tools.', 'code': 'data_use_acknowledgement_required'}, status_code=428)(scope, receive, send)
        return await self.app(scope, receive, send)

def install(app):
    @app.get('/local/legal')
    async def state():
        return {'version': VERSION, 'accepted': accepted()}

    @app.get('/local/legal/{document}')
    async def document(document: str):
        if document not in DOCUMENTS: raise HTTPException(404, 'Document not found.')
        return {'markdown': (Path(__file__).resolve().parent / DOCUMENTS[document]).read_text(encoding='utf-8')}

    @app.post('/local/legal')
    async def acknowledge(body: Acknowledgement):
        if body.version != VERSION: raise HTTPException(409, 'The notice changed. Review the current notice.')
        db.set_app_setting('data_use_acknowledgement', VERSION if body.accepted else '')
        return {'version': VERSION, 'accepted': body.accepted}
