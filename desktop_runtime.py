"""Desktop-only credential management and a per-launch HTTP session boundary."""
import hmac
import os
import threading
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

COOKIE='study_desktop_session'
SERVICE='StudyDesk.DeepSeek'
ACCOUNT='api-key'

def credential_store():
    import keyring
    store=keyring.get_keyring()
    trusted=('keyring.backends.Windows','keyring.backends.macOS','keyring.backends.SecretService',
             'keyring.backends.libsecret','keyring.backends.kwallet')
    if not type(store).__module__.startswith(trusted):
        raise RuntimeError('An operating-system credential store is unavailable. Unlock or configure your system keyring and reopen Study Desk.')
    return store

def load_key():
    return credential_store().get_password(SERVICE,ACCOUNT) or ''

class DesktopSession:
    def __init__(self,app,secret):
        self.app=app;self.secret=secret;self.exchanged=False;self.lock=threading.Lock()

    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        request=Request(scope)
        authenticated=hmac.compare_digest(request.cookies.get(COOKIE,'').encode(),self.secret.encode())
        if request.url.path=='/desktop/launch':
            token=request.query_params.get('token','')
            with self.lock:
                valid=not self.exchanged and hmac.compare_digest(token.encode(),self.secret.encode())
                if valid:self.exchanged=True
            if valid:
                response=RedirectResponse('/',status_code=303)
                response.set_cookie(COOKIE,self.secret,httponly=True,samesite='strict',path='/')
                response.headers.update({'Cache-Control':'no-store','Referrer-Policy':'no-referrer'})
                return await response(scope,receive,send)
        # Host process readiness/shutdown uses a header; browser requests use an
        # HttpOnly cookie. Neither mechanism ever contains the provider API key.
        control=hmac.compare_digest(request.headers.get('x-study-desktop','').encode(),self.secret.encode())
        if not authenticated and not (control and request.url.path in {'/desktop/ready','/desktop/stop'}):
            return await JSONResponse({'detail':'Open this workspace from the Study Desk application.'},status_code=403)(scope,receive,send)
        return await self.app(scope,receive,send)

class ProviderKey(BaseModel):
    api_key: str = Field(min_length=8,max_length=256)

def install(app):
    @app.get('/desktop/provider')
    async def provider():
        return {'desktop':True,'configured':bool(os.getenv('OPENAI_API_KEY')),'provider':'DeepSeek'}

    @app.post('/desktop/provider')
    async def save_provider(body:ProviderKey):
        key=body.api_key.strip()
        if len(key)<8 or not key.isascii() or any(c.isspace() or ord(c)<32 for c in key):
            raise HTTPException(422,'Enter the API key without spaces or line breaks.')
        import app as application
        if application.INDEX_QUEUE and application.INDEX_QUEUE.qsize():
            raise HTTPException(409,'Wait for indexing to finish before changing your key.')
        try:
            import asyncio
            await asyncio.to_thread(credential_store().set_password,SERVICE,ACCOUNT,key)
        except Exception as exc:
            raise HTTPException(503,'The system credential store could not save your key. Unlock your keyring and try again.') from exc
        os.environ['OPENAI_API_KEY']=key
        import tools
        tools.get_settings.cache_clear();tools._get_llm.cache_clear()
        return {'configured':True,'message':'API key saved in your system credential store. New AI requests use this key.'}

    @app.get('/desktop/ready')
    async def ready():return {'ready':True}

    @app.post('/desktop/stop')
    async def stop():
        import asyncio
        callback=getattr(app.state,'local_shutdown',None)
        if callback:asyncio.get_running_loop().call_later(.1,callback)
        return {'stopping':True}
