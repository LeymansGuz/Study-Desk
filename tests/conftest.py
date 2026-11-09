import os
import tempfile
from pathlib import Path
import pytest

ROOT=Path(tempfile.mkdtemp(prefix='study-local-tests-'))
os.environ.update(APP_DB_PATH=str(ROOT/'app.db'),USERS_DIR=str(ROOT/'users'),CHROMA_DIR=str(ROOT/'chroma'),
                  AUTO_MAINTENANCE='false',MANAGED_LOGGING='false',AUTO_UPGRADE_PIPELINE='false',
                  LANGCHAIN_TRACING_V2='false',LANGSMITH_TRACING='false',PREFETCH_NEXT_QUESTION='false',
                  APP_MIN_FREE_DISK_PERCENT='0',APP_MIN_FREE_DISK_BYTES='0',APP_ALLOWED_HOSTS='localhost,127.0.0.1,::1')

@pytest.fixture(autouse=True)
def no_paid_calls(monkeypatch):
    from langchain_openai import ChatOpenAI,OpenAIEmbeddings
    def blocked(*a,**k): raise AssertionError('Provider calls are disabled in offline tests.')
    async def async_blocked(*a,**k): return blocked()
    import httpx
    original_async=httpx.AsyncHTTPTransport.handle_async_request
    original_sync=httpx.HTTPTransport.handle_request
    async def guarded_async(self,request):
        if request.url.host not in {'localhost','127.0.0.1','::1'}:return blocked()
        return await original_async(self,request)
    def guarded_sync(self,request):
        if request.url.host not in {'localhost','127.0.0.1','::1'}:return blocked()
        return original_sync(self,request)
    monkeypatch.setattr(httpx.AsyncHTTPTransport,'handle_async_request',guarded_async)
    monkeypatch.setattr(httpx.HTTPTransport,'handle_request',guarded_sync)
    monkeypatch.setattr(ChatOpenAI,'ainvoke',async_blocked)
    monkeypatch.setattr(ChatOpenAI,'invoke',blocked)
    for name in ['embed_documents','embed_query']: monkeypatch.setattr(OpenAIEmbeddings,name,blocked)
    for name in ['aembed_documents','aembed_query']: monkeypatch.setattr(OpenAIEmbeddings,name,async_blocked)
    import rate_limits
    monkeypatch.setattr(rate_limits.limiter,'enabled',False)

@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    import app
    import compliance,db
    db.init_db()
    db.set_app_setting('data_use_acknowledgement',compliance.VERSION)
    with TestClient(app.app,base_url='http://localhost',client=('127.0.0.1',1234),headers={'X-Study-Upload-Rights':'confirmed'}) as c: yield c
