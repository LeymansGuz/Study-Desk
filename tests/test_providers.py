"""Provider boundary tests. All HTTP and key storage are simulated."""
import asyncio,json,time
import pytest,httpx
import providers,db,auth,observability,tools
from langchain_core.messages import HumanMessage

@pytest.fixture(autouse=True)
def isolated_provider_state(monkeypatch):
    db.init_db();auth.initialize();observability.initialize()
    old=db.get_app_setting('ai_connection_v1','{}');db.set_app_setting('ai_connection_v1','{}')
    providers.CATALOG.clear();providers.USAGE.clear();providers.LOCKS.clear()
    providers.ROUTES.clear()
    monkeypatch.setattr(providers,'read_key',lambda *a:'offline-test-key')
    yield
    db.set_app_setting('ai_connection_v1',old);providers.CATALOG.clear();providers.USAGE.clear();providers.LOCKS.clear()

def row(identifier='example/test:free',**extra):
    return {'id':identifier,'architecture':{'output_modalities':['text']},'pricing':{'prompt':'0','completion':'0'},'supported_parameters':['response_format'],**extra}

def mock_network(monkeypatch,handler):
    original=httpx.AsyncClient
    monkeypatch.setattr(providers.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))

def test_catalog_free_classification_and_non_text_filter():
    assert providers.metadata(row(),'openrouter')['price_status']=='free'
    assert providers.metadata(row(pricing={'prompt':'0','completion':'0','request':'0.01'}),'openrouter')['price_status']=='paid'
    assert providers.metadata(row(pricing={'prompt':'0'}),'openrouter')['price_status']=='unknown'
    assert providers.metadata(row(pricing={'prompt':'NaN','completion':'0'}),'openrouter')['price_status']=='unknown'
    assert providers.metadata(row(architecture={'output_modalities':['audio']}),'openrouter') is None
    assert providers.metadata(row('embedding-v1'),'openai') is None

@pytest.mark.parametrize('url',['http://remote.example/v1','https://user:password@example.org/v1','https://example.org/v1?key=secret','https://192.168.1.1/v1','file:///tmp/key'])
def test_unsafe_endpoint_rejected(url):
    with pytest.raises(ValueError):providers.validate_url(url)

def test_local_endpoint_allowed():
    assert providers.validate_url('http://127.0.0.1:11434/v1')=='http://127.0.0.1:11434/v1'

def test_free_request_pins_route_zero_price_and_accounts_usage(monkeypatch):
    bodies=[]
    def handler(request):
        if request.url.path.endswith('/endpoints'):return httpx.Response(200,json={'data':{'endpoints':[{'tag':'approved-host','provider_name':'Approved','pricing':{'prompt':'0','completion':'0'}}]}})
        if request.method=='GET':return httpx.Response(200,json={'data':[row()]})
        bodies.append(json.loads(request.content))
        return httpx.Response(200,json={'model':'example/test:free','choices':[{'message':{'content':'{"ok":true}'},'finish_reason':'stop'}],'usage':{'prompt_tokens':12,'completion_tokens':5}})
    mock_network(monkeypatch,handler)
    connection=providers.Connection('openrouter','example/test:free',providers.DEFINITIONS['openrouter'][1],'offline-test-key',(0,0,0),True,('approved-host',))
    response=asyncio.run(providers.Model(connection,0).ainvoke([HumanMessage(content='JSON')]))
    assert response.usage_metadata['input_tokens']==12
    assert bodies[0]['provider']=={'allow_fallbacks':False,'require_parameters':True,'only':['approved-host'],'max_price':{'prompt':0,'completion':0,'request':0,'image':0}}

def test_free_request_refuses_retired_or_paid_model_before_generation(monkeypatch):
    calls=[]
    def handler(request):
        calls.append(request.method)
        return httpx.Response(200,json={'data':[row(pricing={'prompt':'0.1','completion':'0.2'})]})
    mock_network(monkeypatch,handler)
    connection=providers.Connection('openrouter','example/test:free',providers.DEFINITIONS['openrouter'][1],'offline-test-key',(0,0,0),True)
    with pytest.raises(providers.ProviderError,match='no longer confirmed free'):
        asyncio.run(providers.Model(connection,0).ainvoke([HumanMessage(content='JSON')]))
    assert calls==['GET']

def test_anthropic_uses_messages_api_and_system_field(monkeypatch):
    captured=[]
    def handler(request):
        captured.append((str(request.url),json.loads(request.content),dict(request.headers)))
        return httpx.Response(200,json={'content':[{'type':'thinking','thinking':'hidden'},{'type':'text','text':'{"ok":true}'}],'stop_reason':'end_turn','usage':{'input_tokens':15,'output_tokens':4}})
    mock_network(monkeypatch,handler)
    from langchain_core.messages import SystemMessage
    c=providers.Connection('anthropic','claude-test','https://api.anthropic.com/v1','offline-test-key')
    r=asyncio.run(providers.Model(c,0).ainvoke([SystemMessage(content='instructions'),HumanMessage(content='JSON')]))
    assert r.content=='{"ok":true}' and captured[0][0].endswith('/messages')
    assert captured[0][1]['system']=='instructions' and captured[0][2]['x-api-key']=='offline-test-key'

def test_provider_failure_is_safe_and_not_retried(monkeypatch):
    count=[]
    def handler(request):
        count.append(1);return httpx.Response(429,json={'error':{'message':'private provider payload'}},headers={'Retry-After':'60'})
    mock_network(monkeypatch,handler)
    c=providers.Connection('openai','example','https://api.openai.com/v1','offline-test-key')
    with pytest.raises(providers.ProviderError,match='Suggested wait: 60') as caught:
        asyncio.run(providers.Model(c,0).ainvoke([HumanMessage(content='JSON')]))
    assert len(count)==1 and 'private provider payload' not in str(caught.value)

def test_openai_responses_is_stateless_and_counts_cached_tokens(monkeypatch):
    captured=[]
    def handler(request):
        captured.append((str(request.url),json.loads(request.content)))
        return httpx.Response(200,json={'status':'completed','output':[{'type':'reasoning','summary':[]},{'type':'message','content':[{'type':'output_text','text':'{"ok":true}'}]}],'usage':{'input_tokens':30,'output_tokens':5,'input_tokens_details':{'cached_tokens':20}}})
    mock_network(monkeypatch,handler)
    c=providers.Connection('openai','example','https://api.openai.com/v1','offline-test-key')
    r=asyncio.run(providers.Model(c,0).ainvoke([HumanMessage(content='JSON')]))
    assert r.content=='{"ok":true}' and r.usage_metadata['input_token_details']['cache_read']==20
    assert captured[0][0].endswith('/responses') and captured[0][1]['store'] is False

def test_connection_snapshot_keeps_original_key_and_model(monkeypatch):
    db.set_app_setting('ai_connection_v1',json.dumps({'provider':'openai','model':'old','base_url':'https://api.openai.com/v1'}))
    first=providers.snapshot();token=providers.ACTIVE.set(first)
    try:
        db.set_app_setting('ai_connection_v1',json.dumps({'provider':'openai','model':'new','base_url':'https://api.openai.com/v1'}))
        assert tools.get_settings().model=='old'
        assert providers.snapshot().model=='new'
    finally:providers.ACTIVE.reset(token)

def test_unknown_price_never_uses_deepseek_rates():
    token=providers.ACTIVE.set(providers.Connection('openai','example','https://api.openai.com/v1','offline'))
    try:
        identifier,cost=observability.provider_call(auth.OWNER_ID,'Test', 'example',100,20,0,1)
        with db.connect() as c:row=c.execute('SELECT model,cost_usd,input_tokens FROM model_calls WHERE id=?',(identifier,)).fetchone()
        assert cost is None and row['cost_usd'] is None and row['input_tokens']==100 and row['model']=='openai:example'
    finally:providers.ACTIVE.reset(token)

def test_activation_requires_price_and_region_acknowledgement(client):
    payload={'provider':'openai','model':'example','free_only':False}
    assert client.post('/local/providers',json=payload).status_code==422
    payload['eligible']=True
    assert client.post('/local/providers',json=payload).status_code==422
    payload['accept_charges']=True
    assert client.post('/local/providers',json=payload).status_code==200
    assert 'offline-test-key' not in client.get('/local/providers').text

def test_known_insufficient_free_allowance_blocks_before_generation(monkeypatch):
    methods=[]
    def handler(request):
        methods.append(request.method)
        return httpx.Response(200,json={'data':{'free_model_daily_requests':{'remaining':2,'limit':50}}})
    mock_network(monkeypatch,handler)
    c=providers.Connection('openrouter','example/test:free',providers.DEFINITIONS['openrouter'][1],'offline',(0,0,0),True,('approved-host',))
    token=providers.WORKFLOW.set({'checked':False,'calls':0,'minimum':8})
    try:
        with pytest.raises(providers.ProviderError,match='too low'):
            asyncio.run(providers.Model(c,0).ainvoke([HumanMessage(content='JSON')]))
        assert methods==['GET']
    finally:providers.WORKFLOW.reset(token)

def test_free_workflow_wait_is_outside_generation_deadline(monkeypatch):
    import pipeline_runtime
    monkeypatch.setattr(pipeline_runtime,'GENERATION_TIMEOUT_SECONDS',.15)
    async def run():
        token=providers.ACTIVE.set(providers.Connection('openrouter','example',providers.DEFINITIONS['openrouter'][1],'offline',(0,0,0),True))
        entered=asyncio.Event()
        async def hold():
            async with providers.workflow_slot():entered.set();await asyncio.sleep(.3)
        try:
            task=asyncio.create_task(hold());await entered.wait()
            started=time.monotonic()
            async with pipeline_runtime.generation_slot():await asyncio.sleep(.001)
            assert time.monotonic()-started>.25
            await task
        finally:providers.ACTIVE.reset(token)
    asyncio.run(run())

def test_truncated_response_logs_tokens_and_stops_without_retry(monkeypatch):
    from pydantic import BaseModel
    from langchain_core.messages import AIMessage
    from generation_errors import StageFailure
    from usage_log import CURRENT_USER_ID
    class ExplanationDraft(BaseModel):ok:bool
    calls=[]
    async def truncated(*a,**kwargs):
        calls.append(1)
        return AIMessage(content='',usage_metadata={'input_tokens':17,'output_tokens':9,'total_tokens':26},response_metadata={'finish_reason':'length'})
    monkeypatch.setattr(providers.Model,'ainvoke',truncated)
    config=providers.ACTIVE.set(providers.Connection('openrouter','fixture/free:free',providers.DEFINITIONS['openrouter'][1],'offline',(0,0,0)))
    user=CURRENT_USER_ID.set(auth.OWNER_ID)
    try:
        with pytest.raises(StageFailure,match='response budget'):
            asyncio.run(tools._invoke_json('Return JSON.',0,ExplanationDraft))
        with db.connect() as c:row=c.execute("SELECT input_tokens,output_tokens,cost_usd,outcome FROM model_calls WHERE model='openrouter:fixture/free:free' ORDER BY created_at DESC LIMIT 1").fetchone()
        assert len(calls)==1 and row['input_tokens']==17 and row['output_tokens']==9 and row['cost_usd']==0 and row['outcome']!='success'
    finally:providers.ACTIVE.reset(config);CURRENT_USER_ID.reset(user)

def test_free_scope_blocks_question_generation_grading_and_deep_explanation(client):
    db.set_app_setting('ai_connection_v1',json.dumps({'provider':'openrouter','model':'fixture/free:free','base_url':providers.DEFINITIONS['openrouter'][1],'pricing':[0,0,0],'free_only':False}))
    for path,payload in [('/ask',{}),('/ask/question',{}),('/ask/path',{}),('/answer',{}),('/explain',{'depth':'deep'})]:
        response=client.post(path,json=payload)
        assert response.status_code==422 and response.json()['code']=='free_model_scope'
    # A brief request reaches ordinary endpoint validation instead of the scope
    # rejection, and its body has been replayed intact.
    response=client.post('/explain',json={'topic':'Diffusion','depth':'brief','course_ids':[]})
    assert response.status_code==422 and response.json().get('code')!='free_model_scope'

def test_free_scope_cannot_be_bypassed_at_model_stage(monkeypatch):
    from pydantic import BaseModel
    from generation_errors import StageFailure
    class QuestionSeed(BaseModel):question:str
    token=providers.ACTIVE.set(providers.Connection('openrouter','fixture/free:free',providers.DEFINITIONS['openrouter'][1],'offline',(0,0,0),False))
    try:
        with pytest.raises(StageFailure,match='restricted to verified brief'):
            asyncio.run(tools._invoke_json('Generate a question.',0,QuestionSeed))
    finally:providers.ACTIVE.reset(token)
