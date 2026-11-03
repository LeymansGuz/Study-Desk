"""Local boundary, archive, recovery and error-path regressions. No paid calls."""
import asyncio,io,json,zipfile
import pytest
from fastapi import HTTPException
import app,db,backup,security

def test_backup_verification_matches_local_schema(client):
    a=backup.create_backup(backup.backup_directory())
    b=backup.create_backup(backup.backup_directory())
    assert a!=b and a.is_file() and b.is_file()
    assert backup.verify_latest()['users']==1

def test_document_and_secret_paths_not_exposed(client):
    for path in ['/.env','/data/app.db','/data/runtime/services.json','/static/../.env','/docs','/openapi.json']:
        assert client.get(path).status_code==404
    r=client.get('/settings')
    assert r.headers['cache-control']=='no-store'
    assert "script-src 'self'" in r.headers['content-security-policy']
    assert 'cdn.jsdelivr.net' not in r.headers['content-security-policy']

def test_clean_html_errors(client):
    r=client.get('/missing-page',headers={'Accept':'text/html'})
    assert r.status_code==404 and 'Open workspace' in r.text
    async def broken():raise RuntimeError('private-diagnostic-marker')
    app.app.add_api_route('/__audit_error',broken)
    try:
        from fastapi.testclient import TestClient
        with TestClient(app.app,base_url='http://localhost',client=('127.0.0.1',8),raise_server_exceptions=False) as c:
            r=c.get('/__audit_error',headers={'Accept':'text/html'})
        assert r.status_code==500 and 'Something went wrong' in r.text
        assert r.headers['cache-control']=='no-store'
        assert "script-src 'self'" in r.headers['content-security-policy']
        assert 'private-diagnostic-marker' not in r.text
    finally:app.app.router.routes[:]=[r for r in app.app.router.routes if getattr(r,'path','')!='/__audit_error']

def test_shutdown_requires_private_controller_token(client,monkeypatch):
    monkeypatch.setenv('STUDY_LOCAL_CONTROL_TOKEN','controller-only')
    assert client.post('/local/control/stop').status_code==403
    assert client.post('/local/control/stop',headers={'X-Local-Control':'wrong'}).status_code==403
    calls=[]
    monkeypatch.setattr(app.app.state,'local_shutdown',lambda:calls.append('stopped'),raising=False)
    response=client.post('/local/control/stop',headers={'X-Local-Control':'controller-only'})
    assert response.status_code==200
    assert 'controller-only' not in client.get('/local/runtime').text

def test_oversized_word_package_rejected_before_parser(monkeypatch):
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('word/document.xml','x'*20000)
    monkeypatch.setattr(security,'MAX_UPLOAD_BYTES',10000)
    monkeypatch.setattr(security,'extract_office_text',lambda _:pytest.fail('Parser must not receive a ZIP bomb'))
    with pytest.raises(HTTPException) as error:security.validate_upload('notes.docx',data.getvalue())
    assert error.value.status_code==413

def test_word_xml_external_entities_rejected_before_parser(monkeypatch):
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w') as z:z.writestr('word/document.xml','<!DOCTYPE x [<!ENTITY secret SYSTEM "file:///private-data">]><x>&secret;</x>')
    monkeypatch.setattr(security,'extract_office_text',lambda _:pytest.fail('External entities must not reach native parsing'))
    with pytest.raises(HTTPException) as error:security.validate_upload('notes.docx',data.getvalue())
    assert error.value.status_code==400

def test_zip_import_rejects_unpacked_budget(client,monkeypatch):
    course=client.post('/workspace/courses',json={'name':'Archive audit'}).json()['id']
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('notes.txt','x'*20000)
    monkeypatch.setattr(app,'MAX_BATCH_BYTES',10000)
    response=client.post('/workspace/courses/'+course+'/import-zip',files={'file':('notes.zip',data.getvalue(),'application/zip')})
    assert response.status_code==413,response.text

def test_streamed_body_limit_and_wrong_origin(client):
    r=client.put('/settings',content=iter([b'x'*1000000,b'x'*1000001]),headers={'Content-Type':'application/json'})
    assert r.status_code==413
    assert client.put('/settings',headers={'Origin':'null'},json={'theme':'dark'}).status_code==403
    assert client.put('/settings',headers={'Origin':'http://localhost:8000'},json={'theme':'dark'}).status_code==403
