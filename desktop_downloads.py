"""Bounded native save-dialog bridge. Browser code cannot choose filesystem paths."""
import hmac,os,re,time,uuid
from urllib.parse import urlsplit,parse_qs
from fastapi import HTTPException,Request
from pydantic import BaseModel,Field

def allowed_path(path):
    if not isinstance(path,str) or len(path)>500 or any(c in path for c in ['\\','%','\r','\n']):return False
    url=urlsplit(path)
    if url.scheme or url.netloc or url.fragment:return False
    patterns=[r'/library/course/[A-Za-z0-9_-]+/export',r'/study/sheets/[A-Za-z0-9_-]+/export',r'/session/[A-Za-z0-9_-]+/export',r'/bank-exams/[A-Za-z0-9_-]+/summary/export',r'/workspace/documents/[A-Za-z0-9_-]+/download',r'/study/cards/export',r'/library/personal/export',r'/library/guide/[A-Za-z0-9_-]+',r'/workspace/download-all']
    if not any(re.fullmatch(p,url.path) for p in patterns):return False
    query=parse_qs(url.query,keep_blank_values=True)
    allowed={'course_id'} if url.path in {'/library/personal/export','/workspace/download-all'} else {'download'} if url.path.startswith('/library/guide/') else set()
    return set(query)<=allowed and all(len(v)==1 and re.fullmatch('[A-Za-z0-9_-]{1,100}',v[0]) for v in query.values())

class SaveRequest(BaseModel):
    route:str=Field(max_length=500)
    passphrase:str|None=Field(default=None,min_length=12,max_length=256)
class Result(BaseModel):
    id:str=Field(max_length=32)
    state:str=Field(pattern='^(saved|cancelled|error)$')
    message:str=Field(max_length=1000)

def install(app):
    jobs={}
    app.state.native_export_jobs=jobs
    def native(request):
        secret=os.getenv('STUDY_DESKTOP_SECRET','')
        if not secret or not hmac.compare_digest(secret,request.headers.get('x-study-desktop','')):raise HTTPException(403,'This action belongs to the desktop application.')
    def expire():
        now=time.monotonic()
        for key,value in list(jobs.items()):
            if now-value['started']>1800:jobs.pop(key)
    @app.post('/desktop/files/save')
    async def save(body:SaveRequest):
        expire()
        encrypted=body.route=='/library/backups/encrypted' and body.passphrase is not None
        if not allowed_path(body.route) and not encrypted:raise HTTPException(422,'This file cannot be exported from this control.')
        if body.passphrase is not None and not encrypted:raise HTTPException(422,'Invalid encrypted export request.')
        if any(v['state'] in {'queued','saving'} for v in jobs.values()):raise HTTPException(409,'Finish or cancel the current Save dialog first.')
        if len(jobs)>=8:jobs.pop(next(iter(jobs)))
        identifier=uuid.uuid4().hex;jobs[identifier]={'id':identifier,'route':body.route,'passphrase':body.passphrase,'state':'queued','message':'Preparing export…','started':time.monotonic()}
        return {'id':identifier}
    @app.get('/desktop/files/command')
    async def command(request:Request):
        native(request);expire()
        for job in jobs.values():
            if job['state']=='queued':
                job.update(state='saving',message='Preparing export and Save dialog…')
                return {'id':job['id'],'route':job['route'],'passphrase':job.pop('passphrase',None)}
        return {}
    @app.post('/desktop/files/result')
    async def result(body:Result,request:Request):
        native(request)
        if body.id in jobs:jobs[body.id].update(state=body.state,message=body.message)
        return {'ok':True}
    @app.get('/desktop/files/status/{identifier}')
    async def status(identifier:str):
        expire()
        if identifier not in jobs:raise HTTPException(404,'The save request expired. Please try again.')
        return {k:v for k,v in jobs[identifier].items() if k in {'state','message'}}
