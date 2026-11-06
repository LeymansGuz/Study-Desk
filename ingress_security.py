import auth
"""Host and streaming-body boundaries, before parsing/idempotency/logging."""
import os
import re
from urllib.parse import urlsplit
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.datastructures import MutableHeaders
from security import security_headers

class IngressSecurity:

    def __init__(self, app, services):
        self.app = app
        self.services = services

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        request = Request(scope)
        path = scope['path']
        started = False

        async def protected_send(message):
            nonlocal started
            if message['type'] == 'http.response.start':
                started = True
                headers = MutableHeaders(scope=message)
                defaults = Response()
                security_headers(request, defaults)
                for key, value in defaults.headers.items():
                    if key.lower() not in {'content-length', 'content-type'} and key not in headers:
                        headers[key] = value
                if not path.startswith('/static/'):
                    headers['Cache-Control'] = 'no-store'
                    if path.endswith('/file'):
                        headers['X-Frame-Options']='SAMEORIGIN'
                        headers['Content-Security-Policy']=headers.get('Content-Security-Policy','').replace("frame-ancestors 'none'","frame-ancestors 'self'")
            await send(message)

        async def deny(status, detail):
            return await JSONResponse({'detail': detail}, status_code=status)(scope, receive, protected_send)
        hosts = request.headers.getlist('host')
        authority = hosts[0] if len(hosts) == 1 else ''
        try:
            parsed = urlsplit('//' + authority)
            host = parsed.hostname
            parsed.port
        except ValueError:
            host = None
        allowed = {h.strip().lower() for h in os.getenv('APP_ALLOWED_HOSTS', 'localhost,127.0.0.1,::1').split(',')}
        if not host or host.lower() not in allowed or any((ch in authority for ch in '@/\\#?%')):
            return await deny(400, 'Invalid host header.')
        method = scope.get('method', 'GET')
        if method in {'POST', 'PUT', 'PATCH', 'DELETE'} and request.headers.get('sec-fetch-site') == 'cross-site':
            return await deny(403, 'Cross-site changes are not allowed.')
        limit = 2000000
        if path=='/library/backups/restore' and method=='POST':
            limit=256*1024*1024+1000000
        upload = path in {'/workspace/files', '/workspace/files/local', '/api/extract', '/api/extract/batch', '/admin/restore'} or path.endswith('/import-zip')
        if upload and method in {'POST', 'PUT', 'PATCH'}:
            user = auth.maybe_user(request)
            if not user or not user.get('is_verified'):
                return await deny(401, 'Sign in to continue.')
            if path == '/admin/restore':
                if not user.get('is_admin'):
                    return await deny(403, 'Owner access required.')
                limit = 2 * 1024 ** 3 + 2000000
            elif path == '/workspace/files/local':
                if not self.services['_is_trusted_local_owner'](request, user):
                    return await deny(404, 'Not found.')
                limit = self.services['MAX_BATCH_BYTES'] + 2000000
            elif path in {'/api/extract','/api/extract/batch'}:
                from upload_limits import QUESTION_BYTES,QUESTION_FILE_BYTES
                limit = (QUESTION_BYTES if path.endswith('/batch') else QUESTION_FILE_BYTES)+1000000
            else:
                limit = self.services['MAX_BATCH_BYTES'] + 2000000
        elif path.startswith('/workspace/uploads/') and method == 'PUT':
            limit = 5 * 1024 ** 2
        lengths = request.headers.getlist('content-length')
        if lengths and (len(lengths) != 1 or not re.fullmatch('[0-9]{1,20}', lengths[0])):
            return await deny(400, 'Invalid content length.')
        if lengths and int(lengths[0]) > limit:
            return await deny(413, 'Request body is too large.')
        seen = 0
        too_large = False

        async def bounded_receive():
            nonlocal seen, too_large
            message = await receive()
            if message['type'] == 'http.request':
                seen += len(message.get('body', b''))
                if seen > limit:
                    too_large = True
                    raise HTTPException(413, 'Request body is too large.')
            return message
        try:
            await self.app(scope, bounded_receive, protected_send)
        except HTTPException as exc:
            if started:
                raise
            await deny(exc.status_code, str(exc.detail))
        except Exception:
            if not too_large or started:
                raise
            await deny(413, 'Request body is too large.')
