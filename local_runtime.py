"""Loopback-only boundary and local operational API."""
import asyncio
import ipaddress
import os
import hmac
from urllib.parse import urlsplit
from starlette.responses import JSONResponse
from fastapi import Depends, Request, HTTPException
import auth
import db

class LocalBoundary:

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = {k.decode().lower(): v.decode() for k, v in scope['headers']}
        client = (scope.get('client') or ('', 0))[0]
        try:
            local = ipaddress.ip_address(client).is_loopback
        except ValueError:
            local = False
        host = headers.get('host', '')
        try:
            hostname = urlsplit('//' + host).hostname
        except ValueError:
            hostname = ''
        origin = headers.get('origin')
        valid_origin = not origin or origin in {'http://' + host, 'https://' + host}
        if not local or hostname not in {'localhost', '127.0.0.1', '::1'} or (not valid_origin) or (headers.get('sec-fetch-site') == 'cross-site'):
            return await JSONResponse({'detail': 'Open this workspace directly on localhost.'}, status_code=403)(scope, receive, send)
        return await self.app(scope, receive, send)

def install_local(app):

    @app.get('/local/catalog')
    async def catalog(user=Depends(auth.current_user)):
        from study_catalog import public
        return public()

    @app.get('/local/runtime')
    async def runtime():
        return {'instance':os.getenv('STUDY_LOCAL_INSTANCE',''), 'ready':True}

    @app.post('/local/control/stop')
    async def stop_service(request:Request):
        expected=os.getenv('STUDY_LOCAL_CONTROL_TOKEN','')
        headers=request.headers.getlist('x-local-control')
        if not expected or len(headers)!=1 or not hmac.compare_digest(headers[0].encode('utf-8'),expected.encode('utf-8')):
            raise HTTPException(403,'Use the local stop command to stop this workspace.')
        callback=getattr(app.state,'local_shutdown',None)
        if callback is None:raise HTTPException(409,'This process is not managed by the local launcher.')
        asyncio.get_running_loop().call_later(.1,callback)
        return {'status':'stopping'}

    @app.get('/local/profile')
    async def profile(user=Depends(auth.current_user)):
        return {'name': 'Local workspace', 'is_admin': True, 'desktop':os.getenv('STUDY_DESKTOP')=='true'}

    @app.get('/local/statistics')
    async def statistics(user=Depends(auth.current_user)):
        import observability
        result = await asyncio.to_thread(observability.statistics, 30, 1)
        result['generation'] = __import__('monitoring').generation_summary(24)
        result['pipeline'] = __import__('monitoring').profile_summary(user['id'])
        return result

    @app.post('/local/backup')
    async def backup(request:Request,user=Depends(auth.current_user)):
        import backup as service
        import app as application
        from security import SlidingWindowLimiter,enforce_rate_limit
        if not hasattr(app.state,'backup_limit'):app.state.backup_limit=SlidingWindowLimiter(2,300)
        enforce_rate_limit(request,app.state.backup_limit,'local-backup',user_id=user['id'])
        async with application.WORKSPACE_LOCK:
            with db.connect() as c:
                running=c.execute("SELECT COUNT(*) FROM index_jobs WHERE status IN ('queued','running')").fetchone()[0]
            if running:raise HTTPException(409,'Wait for document indexing to finish before creating a backup.')
            result = await asyncio.to_thread(service.create_backup,service.backup_directory())
        return {'backup': str(result)}

    @app.get('/local/backup/verify')
    async def verify_backup(user=Depends(auth.current_user)):
        import backup as service
        try:return await asyncio.to_thread(service.verify_latest)
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
