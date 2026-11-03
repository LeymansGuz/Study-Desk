"""User-owned AI connections, bounded discovery, immutable workflow configuration.

Keys live in the OS credential store. Catalog presence is never a quality or
regional-access certification; unknown prices are never represented as free.
"""
from __future__ import annotations
import asyncio
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
import ipaddress
import json
import math
import os
import re
import time
import weakref
from contextlib import asynccontextmanager
from urllib.parse import urlsplit
import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field

DEFINITIONS = {
    'openrouter': ('OpenRouter', 'https://openrouter.ai/api/v1'),
    'deepseek': ('DeepSeek', 'https://api.deepseek.com/v1'),
    'openai': ('OpenAI API', 'https://api.openai.com/v1'),
    'anthropic': ('Claude API', 'https://api.anthropic.com/v1'),
    'custom': ('Custom compatible endpoint', ''),
}
ACTIVE = ContextVar('ai_connection', default=None)
WORKFLOW = ContextVar('ai_connection_budget',default=None)
CATALOG = {}  # At most one bounded entry per provider, no credentials persisted.
ROUTES = {}
LOCKS = weakref.WeakKeyDictionary()
WORKFLOWS = weakref.WeakKeyDictionary()
USAGE = {}
# A free default is populated only after the Hong Kong endpoint and full-pipeline
# evaluation have passed. This is deliberately not an arbitrary free router.
RECOMMENDED_FREE = ''
RECOMMENDED_ROUTES = ()

class ProviderError(RuntimeError):
    def __init__(self, message, status_code=503):
        super().__init__(message)
        self.status_code = status_code

@dataclass(frozen=True)
class Connection:
    provider: str
    model: str
    base_url: str
    api_key: str = field(repr=False)
    pricing: tuple | None = None  # input/output/cache USD per million tokens
    free_only: bool = False
    routes: tuple = ()
    json_mode: bool = True
    reasoning: str = 'auto'
    structured_outputs: bool = False

def validate_url(value):
    value = value.strip().rstrip('/')
    parsed = urlsplit(value)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or not parsed.hostname:
        raise ValueError('Use an endpoint URL without credentials, query parameters or a fragment.')
    try:
        address = ipaddress.ip_address(parsed.hostname)
        local = address.is_loopback
        if not local and not address.is_global:
            raise ValueError('Use a public HTTPS endpoint or a loopback local-model server.')
    except ValueError as exc:
        if 'endpoint' in str(exc): raise
        local = parsed.hostname == 'localhost'
    if parsed.scheme != 'https' and not (parsed.scheme == 'http' and local):
        raise ValueError('Remote endpoints require HTTPS. HTTP is allowed only on this computer.')
    if len(value) > 300: raise ValueError('The endpoint URL is too long.')
    return value

def selection():
    import db
    try: return json.loads(db.get_app_setting('ai_connection_v1', '{}'))
    except (ValueError, TypeError): return {}

def credential(provider, base_url=''):
    import desktop_runtime
    service = desktop_runtime.SERVICE if provider == 'deepseek' else 'StudyDesk.' + provider
    if provider == 'custom':
        import hashlib
        service += '.' + hashlib.sha256(base_url.encode()).hexdigest()[:24]
    return service, desktop_runtime.ACCOUNT

def read_key(provider, base_url=''):
    env_name = {'openrouter':'OPENROUTER_API_KEY','anthropic':'ANTHROPIC_API_KEY','openai':'OPENAI_DIRECT_API_KEY'}.get(provider)
    try:
        import desktop_runtime
        saved=desktop_runtime.credential_store().get_password(*credential(provider, base_url)) or ''
        if saved:return saved
    except Exception:pass
    if os.getenv('STUDY_DESKTOP') != 'true':
        if env_name and os.getenv(env_name): return os.environ[env_name].strip()
        if provider == 'deepseek' and os.getenv('OPENAI_API_KEY') and 'deepseek.com' in os.getenv('OPENAI_BASE_URL','https://api.deepseek.com/v1'):
            return os.environ['OPENAI_API_KEY'].strip()
    return ''

def snapshot():
    config = selection()
    if not config: return None  # Preserve existing source/.env and desktop keys.
    provider = config['provider']
    return Connection(provider, config['model'], config['base_url'], read_key(provider, config['base_url']),
                      tuple(config['pricing']) if config.get('pricing') is not None else None,
                      config.get('free_only',False), tuple(config.get('routes',())),config.get('json_mode',True),config.get('reasoning','auto'),config.get('structured_outputs',False))

def limited(connection):
    return bool(connection and connection.provider=='openrouter' and (connection.free_only or connection.model.endswith(':free') or connection.pricing==(0,0,0)))

class ConnectionBoundary:
    def __init__(self, app): self.app=app
    async def __call__(self, scope, receive, send):
        # All descendants, including sequential mastery steps and parallel tasks,
        # inherit the same snapshot for this HTTP workflow.
        ai_request=scope['type']=='http' and scope.get('method')=='POST' and any(scope['path']==p or scope['path'].startswith(p+'/') for p in ('/ask','/answer','/explain','/practice/follow-up','/benchmarks/reference'))
        token = ACTIVE.set(snapshot() if ai_request else None)
        budget_token=WORKFLOW.set({'checked':False,'calls':0,'minimum':8 if scope.get('path')=='/ask' else 3 if scope.get('path')=='/explain' else 1} if ai_request else None)
        try:
            if ai_request and limited(ACTIVE.get()):
                from starlette.responses import JSONResponse
                message='Free models currently support Brief overview in Explain a concept only. Question generation, grading and deeper explanations require a suitable paid connection in Settings.'
                if scope['path']!='/explain':return await JSONResponse({'detail':message,'code':'free_model_scope'},status_code=422)(scope,receive,send)
                chunks=[];size=0
                while True:
                    part=await receive()
                    if part['type']!='http.request':return
                    size+=len(part.get('body',b''))
                    if size>32768:return await JSONResponse({'detail':'This explanation request is too large.'},status_code=413)(scope,receive,send)
                    chunks.append(part.get('body',b''))
                    if not part.get('more_body'):break
                body=b''.join(chunks)
                try:payload=json.loads(body)
                except ValueError:payload={}
                if not isinstance(payload,dict) or payload.get('depth','brief')!='brief':return await JSONResponse({'detail':message,'code':'free_model_scope'},status_code=422)(scope,receive,send)
                original_receive=receive;delivered=False
                async def replay():
                    nonlocal delivered
                    if not delivered:delivered=True;return {'type':'http.request','body':body,'more_body':False}
                    return await original_receive()
                receive=replay
            return await self.app(scope, receive, send)
        finally:
            ACTIVE.reset(token)
            WORKFLOW.reset(budget_token)

def headers(connection):
    if connection.provider == 'anthropic':
        return {'x-api-key':connection.api_key,'anthropic-version':'2023-06-01'}
    return {'Authorization':'Bearer '+connection.api_key} if connection.api_key else {}

def _number(value):
    try:
        n=float(value)
        return n if math.isfinite(n) and n>=0 else None
    except (TypeError,ValueError): return None

def metadata(row, provider):
    identifier=str(row.get('id',''))[:200]
    architecture=row.get('architecture') or {}
    modalities=architecture.get('output_modalities')
    if modalities is not None and 'text' not in modalities: return None
    if re.search(r'embed|rerank|whisper|tts|dall-e|image-generation|moderation|safeguard|lyria|audio|transcrib|realtime|gpt-image|sora',identifier,re.I): return None
    pricing=row.get('pricing') or {}
    values=[_number(pricing.get(k)) for k in ('prompt','completion')]
    rates=None
    state='unknown'
    if provider=='openrouter' and all(v is not None for v in values):
        # Unknown non-token charges cannot be certified free.
        charges=[_number(v) for k,v in pricing.items() if k not in {'discount'}]
        state='free' if charges and all(v==0 for v in charges) else 'paid' if any(v and v>0 for v in charges) else 'unknown'
        cached=_number(pricing.get('input_cache_read'))
        rates=[values[0]*1e6,values[1]*1e6,(cached if cached is not None else values[0])*1e6]
    return {'id':identifier,'name':str(row.get('name',identifier))[:200], 'price_status':state,
            'pricing':rates,'context_length':row.get('context_length'),
            'json_mode': 'response_format' in (row.get('supported_parameters') or []) if provider=='openrouter' else True,
            'structured_outputs':'structured_outputs' in (row.get('supported_parameters') or []),
            'tested': provider=='openrouter' and identifier==RECOMMENDED_FREE,
            'region':'Hong Kong endpoint checked' if provider=='openrouter' and identifier==RECOMMENDED_FREE else 'Check model and hosting-provider eligibility'}

async def discover(provider, base_url='', refresh=False):
    if provider not in DEFINITIONS: raise ProviderError('Choose a supported connection.',422)
    url=validate_url(base_url) if provider=='custom' else DEFINITIONS[provider][1]
    key=read_key(provider,url)
    if not key and provider!='custom': raise ProviderError('Save an API key for this provider before refreshing models.',422)
    identity=(provider,url)
    cached=CATALOG.get(provider)
    if cached and cached['identity']==identity and time.time()-cached['at']<(30 if refresh else 3600): return cached
    connection=Connection(provider,'',url,key)
    rows=[];after=None
    try:
        async with httpx.AsyncClient(timeout=15,trust_env=False,follow_redirects=False) as client:
            for _ in range(5):
                params={'limit':100,**({'after_id':after} if after else {})} if provider=='anthropic' else {}
                response=await client.get(url+'/models',headers=headers(connection),params=params)
                check_response(response)
                body=response.json()
                for row in body.get('data',[])[:500]:
                    item=metadata(row,provider)
                    if item and item['id']:rows.append(item)
                if provider!='anthropic' or not body.get('has_more') or not body.get('last_id'): break
                after=body['last_id']
    except (httpx.HTTPError,ValueError) as exc: raise ProviderError('Could not refresh models. Check the endpoint, connection and API key.') from exc
    result={'identity':identity,'at':time.time(),'models':rows[:500]}
    CATALOG[provider]=result
    return result

async def endpoints(model):
    from urllib.parse import quote
    if not re.fullmatch(r'[A-Za-z0-9_.:/-]{1,200}',model) or '..' in model.split('/'):
        raise ProviderError('Choose a valid catalog model ID.',422)
    cached=ROUTES.get(model)
    if cached and time.time()-cached['at']<300:return cached['endpoints']
    key=read_key('openrouter')
    try:
        async with httpx.AsyncClient(timeout=15,trust_env=False,follow_redirects=False) as client:
            response=await client.get(DEFINITIONS['openrouter'][1]+'/models/'+quote(model,safe='/')+'/endpoints',headers={'Authorization':'Bearer '+key})
            check_response(response);rows=response.json().get('data',{}).get('endpoints',[])
        result=[]
        for row in rows[:100]:
            prices=row.get('pricing') or {}
            parsed=[_number(v) for k,v in prices.items() if k!='discount']
            free=bool(parsed) and all(v==0 for v in parsed) and 'prompt' in prices and 'completion' in prices
            result.append({'id':str(row.get('tag',''))[:120],'name':str(row.get('provider_name',''))[:120],'free':free,'parameters':row.get('supported_parameters') or []})
    except (httpx.HTTPError,ValueError) as exc:raise ProviderError('Could not check hosting endpoints. Refresh models and retry.') from exc
    if len(ROUTES)>=20:ROUTES.pop(next(iter(ROUTES)))
    ROUTES[model]={'at':time.time(),'endpoints':result}
    return result

def check_response(response):
    status=response.status_code
    if status<300:return
    messages={401:'The provider rejected this API key. Replace it in Settings.',403:'This provider/model is unavailable to this account or region. Check eligibility in Settings.',404:'This model or endpoint is unavailable. Refresh models and choose a replacement.',402:'The provider allowance or balance is exhausted. Wait for renewal or choose another connection in Settings.',429:'The provider rate limit or free allowance was reached. Wait for its reset before retrying.'}
    retry=response.headers.get('retry-after','')
    message=messages.get(status,'The provider could not complete this request. Try again later.')
    if status==429 and retry.isdigit(): message+=f' Suggested wait: {min(int(retry),86400)} seconds.'
    raise ProviderError(message,status)

@asynccontextmanager
async def workflow_slot():
    connection=ACTIVE.get()
    if connection is None or not connection.free_only:
        yield
        return
    lock=WORKFLOWS.setdefault(asyncio.get_running_loop(),asyncio.Lock())
    async with lock:
        # Acquired before the generation deadline: another free workflow cannot
        # consume this account's known remaining allowance during validation.
        yield

def allowance_id(connection):
    import hashlib
    return hashlib.sha256((connection.provider+connection.api_key).encode()).hexdigest()

def local_allowance(connection):
    day=datetime.now(timezone.utc).date().isoformat()
    identity=allowance_id(connection)
    item=USAGE.setdefault(identity,{'day':day,'calls':0,'next':0,'blocked_until':0})
    if item['day']!=day:item.update(day=day,calls=0,blocked_until=0)
    # Bound account state even after repeated credential changes.
    if len(USAGE)>16:
        for old in list(USAGE)[:-16]:USAGE.pop(old,None)
    return item

async def remaining(connection):
    if connection.provider!='openrouter': return {}
    try:
        async with httpx.AsyncClient(timeout=10,trust_env=False,follow_redirects=False) as client:
            response=await client.get(connection.base_url+'/key',headers=headers(connection))
            check_response(response)
            data=response.json().get('data',{})
            counter=data.get('free_model_daily_requests')
            if isinstance(counter,dict):
                return {'source':'provider','remaining':counter.get('remaining'),'limit':counter.get('limit'),'resets_at':counter.get('resets_at')}
            return {'source':'local estimate','calls_this_run':local_allowance(connection)['calls'],'note':'Other apps and earlier app runs can consume this account allowance. Check OpenRouter for the authoritative quota.'}
    except (ProviderError,httpx.HTTPError,ValueError):
        return {'source':'unknown','note':'The provider did not return an allowance. No unlimited-use claim is made.'}

class Model:
    def __init__(self, connection, temperature): self.connection=connection;self.temperature=temperature
    async def ainvoke(self, messages, max_tokens=4500, **kwargs):
        from langchain_core.messages import AIMessage
        c=self.connection
        if not c.api_key and c.provider!='custom': raise ProviderError('Add this provider’s API key in Settings before using AI study tools.',422)
        if not c.model:raise ProviderError('Choose a model in Settings before using AI study tools.',422)
        if c.free_only:
            workflow=WORKFLOW.get()
            if workflow is not None:
                if workflow['calls']>=24:raise ProviderError('This workflow reached its bounded free-call budget. No unverified question was accepted.',429)
                if not workflow['checked']:
                    quota=await remaining(c)
                    left=_number(quota.get('remaining'))
                    if left is not None and left<workflow['minimum']:
                        raise ProviderError('The known remaining free allowance is too low for this verified workflow. Wait for renewal or select a connection in Settings.',429)
                    workflow['checked']=True
                workflow['calls']+=1
            catalog=await discover(c.provider,c.base_url)
            entry=next((m for m in catalog['models'] if m['id']==c.model),None)
            if not entry or entry['price_status']!='free':raise ProviderError('This selected model is no longer confirmed free. Refresh models in Settings.',422)
            available=await endpoints(c.model)
            if not c.routes or not all(any(e['id']==r and e['free'] for e in available) for r in c.routes):
                raise ProviderError('The pinned free hosting endpoint is no longer available at zero price. Choose an eligible replacement in Settings.',422)
        converted=[{'role':'system' if getattr(m,'type','')=='system' else 'assistant' if getattr(m,'type','')=='ai' else 'user','content':m.content} for m in messages]
        body={'model':c.model,'messages':converted,'max_tokens':max_tokens}
        if c.provider=='anthropic':
            body['system']='\n'.join(m['content'] for m in converted if m['role']=='system')
            body['messages']=[m for m in converted if m['role']!='system']
        elif c.provider=='openai':
            body={'model':c.model,'input':converted,'max_output_tokens':max_tokens,'store':False}
            if c.json_mode:body['text']={'format':{'type':'json_object'}}
        else:
            if c.structured_outputs and kwargs.get('response_schema'):
                body['response_format']={'type':'json_schema','json_schema':{'name':kwargs.get('schema_name','StudyResult'),'schema':kwargs['response_schema']}}
            elif c.json_mode:body['response_format']={'type':'json_object'}
            if c.provider=='openrouter':
                body['provider']={'allow_fallbacks':False,'require_parameters':True}
                if c.routes:body['provider']['only']=list(c.routes)
                if c.free_only:body['provider']['max_price']={'prompt':0,'completion':0,'request':0,'image':0}
                body['reasoning']={'exclude':True}
                if c.reasoning=='off':body['reasoning']['enabled']=False
                elif c.reasoning=='low':body['reasoning']['effort']='low'
            elif c.provider=='deepseek':body.update(temperature=self.temperature,thinking={'type':'disabled'})
        lock=LOCKS.setdefault(asyncio.get_running_loop(),asyncio.Lock())
        # One call at a time on free connections; no speculative paid fallback.
        async def send():
            state=local_allowance(c)
            if c.free_only:
                if state['blocked_until']>time.time():raise ProviderError('The free provider allowance is unavailable. Wait for its reset or choose a connection in Settings.',429)
                delay=state['next']-time.monotonic()
                if delay>0:await asyncio.sleep(min(delay,4))
                state['next']=time.monotonic()+3.1
            state['calls']+=1
            try:
                async with httpx.AsyncClient(timeout=55,trust_env=False,follow_redirects=False) as client:
                    path='/messages' if c.provider=='anthropic' else '/responses' if c.provider=='openai' else '/chat/completions'
                    response=await client.post(c.base_url+path,headers=headers(c),json=body)
                if response.status_code in {402,429} and c.free_only:
                    delay=response.headers.get('retry-after','60')
                    state['blocked_until']=time.time()+min(int(delay) if delay.isdigit() else 60,86400)
                check_response(response)
                result=response.json()
            except (httpx.HTTPError,ValueError) as exc: raise ProviderError('The provider connection failed or returned an unreadable response. Your study work is preserved.') from exc
            usage=result.get('usage') or {}
            if c.provider=='anthropic':
                text=''.join(b.get('text','') for b in result.get('content',[]) if b.get('type')=='text')
                stop=result.get('stop_reason')
            elif c.provider=='openai':
                text=''.join(block.get('text','') for item in result.get('output',[]) if item.get('type')=='message' for block in item.get('content',[]) if block.get('type')=='output_text')
                stop='max_tokens' if result.get('status')=='incomplete' and (result.get('incomplete_details') or {}).get('reason')=='max_output_tokens' else result.get('status')
            else:
                choices=result.get('choices') or []
                if not choices:raise ProviderError('The provider returned no answer. No question was accepted.')
                text=choices[0].get('message',{}).get('content') or ''
                stop=choices[0].get('finish_reason')
            input_count=int(usage.get('prompt_tokens',usage.get('input_tokens',0)) or 0)
            if c.provider=='anthropic':input_count+=int(usage.get('cache_read_input_tokens',0) or 0)+int(usage.get('cache_creation_input_tokens',0) or 0)
            output_count=int(usage.get('completion_tokens',usage.get('output_tokens',0)) or 0)
            cached=int((usage.get('prompt_tokens_details') or usage.get('input_tokens_details') or {}).get('cached_tokens',usage.get('cache_read_input_tokens',0)) or 0)
            return AIMessage(content=text,usage_metadata={'input_tokens':input_count,'output_tokens':output_count,'total_tokens':input_count+output_count,'input_token_details':{'cache_read':cached}},response_metadata={'model_name':c.provider+':'+str(result.get('model',c.model)),'usage':usage,'finish_reason':stop,'hosting_provider':str(result.get('provider',''))[:120]})
        if c.free_only:
            async with lock:return await send()
        return await send()

class SaveConnection(BaseModel):
    provider: str=Field(max_length=30)
    model: str=Field(default='',max_length=200)
    base_url: str=Field(default='',max_length=300)
    api_key: str=Field(default='',max_length=512)
    activate: bool=True
    accept_charges: bool=False
    eligible: bool=False
    free_only: bool=True
    json_mode: bool=True
    reasoning: str=Field(default='auto',pattern='^(auto|off|low)$')
    route: str=Field(default='',max_length=120)

def install(app):
    import db
    @app.get('/local/providers')
    async def status():
        config=selection()
        legacy=not config and bool(os.getenv('OPENAI_API_KEY'))
        active=config.get('provider','deepseek' if legacy else 'openrouter')
        scope='brief_only' if config.get('provider')=='openrouter' and (config.get('free_only') or config.get('model','').endswith(':free') or config.get('pricing')==[0,0,0]) else 'full'
        return {'providers':[{'id':k,'name':v[0]} for k,v in DEFINITIONS.items()],
                'selected':{k:v for k,v in config.items() if k!='pricing'} or {'provider':active,'model':os.getenv('OPENAI_MODEL','deepseek-flash') if legacy else RECOMMENDED_FREE,'base_url':os.getenv('OPENAI_BASE_URL',DEFINITIONS['deepseek'][1]) if legacy else DEFINITIONS['openrouter'][1]},
                'configured':bool(config.get('model') and read_key(active,config.get('base_url',''))) or legacy,
                'scope':scope,
                'free_recommendation':RECOMMENDED_FREE,'recommendation_status':'tested' if RECOMMENDED_FREE else 'Free models are experimental. Allowance and response quality vary; choose a supported paid connection if verification repeatedly fails.'}

    @app.get('/local/providers/models')
    async def models(provider:str,base_url:str='',refresh:bool=False):
        try:
            result=await discover(provider,base_url,refresh)
            return {'models':result['models'],'fetched_at':result['at'],'warning':'Catalog availability is not proof of regional eligibility or Study Desk quality.'}
        except (ProviderError,ValueError) as exc:raise HTTPException(getattr(exc,'status_code',422),str(exc)) from exc

    @app.get('/local/providers/endpoints')
    async def hosting(model:str):
        try:return {'endpoints':await endpoints(model)}
        except ProviderError as exc:raise HTTPException(exc.status_code,str(exc)) from exc

    @app.post('/local/providers')
    async def save(body:SaveConnection):
        if body.provider not in DEFINITIONS:raise HTTPException(422,'Choose a supported connection.')
        try:url=validate_url(body.base_url) if body.provider=='custom' else DEFINITIONS[body.provider][1]
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        key=body.api_key.strip()
        if key:
            if len(key)<8 or not key.isascii() or any(ch.isspace() or ord(ch)<32 for ch in key):raise HTTPException(422,'Enter an API key without spaces or line breaks.')
            try:
                import desktop_runtime
                await asyncio.to_thread(desktop_runtime.credential_store().set_password,*credential(body.provider,url),key)
            except Exception as exc:raise HTTPException(503,'The system credential store could not save this key. Unlock it and retry.') from exc
            CATALOG.pop(body.provider,None)
        if not body.activate:return {'message':'Key saved securely. Refresh models to choose a connection; no generation request was made.'}
        if not body.model.strip() or any(ord(c)<32 for c in body.model):raise HTTPException(422,'Choose a model or enter a valid model ID.')
        if not body.eligible:raise HTTPException(422,'Confirm the model and hosting provider permit use in your location.')
        catalog=CATALOG.get(body.provider)
        entry=next((m for m in catalog['models'] if m['id']==body.model),None) if catalog and catalog['identity']==(body.provider,url) and time.time()-catalog['at']<3600 else None
        if body.free_only and (body.provider!='openrouter' or not entry or entry['price_status']!='free'):
            raise HTTPException(422,'Refresh models and select a confirmed free OpenRouter model, or turn off Free only and acknowledge possible charges.')
        if not body.free_only and not body.accept_charges:raise HTTPException(422,'Acknowledge possible provider charges before saving this connection.')
        routes=[]
        if body.provider=='openrouter':
            route=body.route or (RECOMMENDED_ROUTES[0] if body.model==RECOMMENDED_FREE and RECOMMENDED_ROUTES else '')
            if route:
                try:available=await endpoints(body.model)
                except ProviderError as exc:raise HTTPException(exc.status_code,str(exc)) from exc
                if not any(e['id']==route and (e['free'] or not body.free_only) for e in available):raise HTTPException(422,'Choose an available hosting endpoint matching your price filter.')
                routes=[route]
            elif body.free_only:raise HTTPException(422,'Choose the eligible free hosting endpoint. Free requests must not route to arbitrary providers.')
        if not read_key(body.provider,url) and body.provider!='custom':raise HTTPException(422,'Save a key for this connection first.')
        config={'provider':body.provider,'model':body.model.strip(),'base_url':url,'free_only':body.free_only,
                'pricing':entry['pricing'] if entry else None,'json_mode':body.json_mode and (entry['json_mode'] if entry else True),'reasoning':body.reasoning,
                'structured_outputs':body.json_mode and entry.get('structured_outputs',False) if entry else False,
                'routes':routes}
        db.set_app_setting('ai_connection_v1',json.dumps(config))
        return {'message':'Connection saved. New study requests use this model; running workflows keep their original connection.','scope':'brief_only' if limited(snapshot()) else 'full'}

    @app.get('/local/providers/allowance')
    async def allowance():
        connection=snapshot()
        return await remaining(connection) if connection else {'source':'unknown','note':'This connection does not expose a free-model allowance.'}

    @app.post('/local/providers/test')
    async def test(body:dict):
        import compliance
        if not compliance.accepted():raise HTTPException(428,'Accept the data-use notice before making a provider test request.')
        if body.get('allow_request') is not True:raise HTTPException(422,'Confirm that this small test can consume allowance or incur provider charges.')
        connection=snapshot()
        if not connection:raise HTTPException(422,'Save a connection before testing it.')
        state=local_allowance(connection)
        if time.time()-state.get('last_test',0)<30:raise HTTPException(429,'Wait 30 seconds before testing again.')
        state['last_test']=time.time()
        token=ACTIVE.set(connection)
        try:
            from langchain_core.messages import HumanMessage
            started=time.perf_counter()
            result=await Model(connection,0).ainvoke([HumanMessage(content='Return exactly one JSON object: {"ok":true}. This is an API format check, not a study question.')],max_tokens=256)
            import auth,usage_log
            previous=usage_log.CURRENT_USER_ID.set(auth.OWNER_ID)
            try:usage_log.record_response_usage(result,'ConnectionTest',(time.perf_counter()-started)*1000)
            finally:usage_log.CURRENT_USER_ID.reset(previous)
            if json.loads(result.content)!={'ok':True}:raise ProviderError('The model did not return the requested JSON format.',422)
            return {'message':'Connection and JSON check passed. This is not a question-quality or regional-terms certification.'}
        except (ProviderError,ValueError) as exc:raise HTTPException(getattr(exc,'status_code',422),str(exc) if isinstance(exc,ProviderError) else 'The model did not return the requested JSON format.') from exc
        finally:ACTIVE.reset(token)

    app.add_middleware(ConnectionBoundary)
