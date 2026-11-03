import os
from fastapi import FastAPI
from fastapi.testclient import TestClient
import desktop_runtime as desktop

def test_desktop_session_exchange_is_single_use_and_never_exposes_key():
    app=FastAPI();secret='a'*64
    app.add_middleware(desktop.DesktopSession,secret=secret)
    @app.get('/')
    async def home():return {'ok':True}
    @app.get('/desktop/ready')
    async def ready():return {'ready':True}
    with TestClient(app) as client:
        assert client.get('/').status_code==403
        assert client.get('/desktop/ready',headers={'X-Study-Desktop':secret}).status_code==200
        assert client.get('/',headers={'X-Study-Desktop':secret}).status_code==403
        assert client.get('/desktop/launch?token=wrong').status_code==403
        response=client.get('/desktop/launch?token='+secret,follow_redirects=False)
        assert response.status_code==303 and 'HttpOnly' in response.headers['set-cookie']
        assert client.get('/').status_code==200
        client.cookies.clear()
        assert client.get('/desktop/launch?token='+secret).status_code==403
        assert client.get('/').status_code==403

def test_provider_key_uses_secure_store_and_not_database_or_response(monkeypatch):
    calls=[]
    class Store:
        def set_password(self,service,account,key):calls.append((service,account,key))
    monkeypatch.setattr(desktop,'credential_store',lambda:Store())
    monkeypatch.setenv('OPENAI_API_KEY','')
    app=FastAPI();desktop.install(app)
    import app as application
    monkeypatch.setattr(application,'INDEX_QUEUE',None)
    with TestClient(app) as client:
        key='sk-isolated-test-not-real'
        assert client.post('/desktop/provider',json={'api_key':'a b c d e'}).status_code==422
        result=client.post('/desktop/provider',json={'api_key':key})
        assert result.status_code==200 and key not in result.text
        assert calls==[(desktop.SERVICE,desktop.ACCOUNT,key)]
        assert client.get('/desktop/provider').json()['configured'] is True
    import tools
    tools.get_settings.cache_clear();tools._get_llm.cache_clear()

def test_plaintext_credential_backend_is_rejected(monkeypatch):
    import keyring
    class Plaintext:pass
    monkeypatch.setattr(keyring,'get_keyring',lambda:Plaintext())
    import pytest
    with pytest.raises(RuntimeError,match='credential store'):desktop.credential_store()
