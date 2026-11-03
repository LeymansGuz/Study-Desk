import asyncio
import os
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
import compliance,db,desktop_updates,desktop_runtime

def test_ai_notice_is_required_versioned_and_withdrawable(client):
    db.set_app_setting('data_use_acknowledgement','')
    try:
        assert client.post('/ask',json={}).status_code==428
        assert client.get('/local/legal').json()['accepted'] is False
        assert client.get('/local/legal/privacy').status_code==200
        assert client.get('/local/legal/not-a-document').status_code==404
        assert client.post('/local/legal',json={'version':'old','accepted':True}).status_code==409
        assert client.post('/local/legal',json={'version':compliance.VERSION,'accepted':True}).json()['accepted']
        assert client.post('/local/legal',json={'version':compliance.VERSION,'accepted':False}).status_code==200
        assert client.post('/explain',json={}).status_code==428
    finally:db.set_app_setting('data_use_acknowledgement',compliance.VERSION)

def test_upload_requires_rights_confirmation(client):
    assert client.post('/workspace/uploads',json={},headers={'X-Study-Upload-Rights':''}).status_code==428

def desktop_app(monkeypatch):
    monkeypatch.setenv('STUDY_DESKTOP_SECRET','a'*64)
    app=FastAPI();desktop_updates.install(app)
    return app

def test_browser_cannot_inject_native_results_or_urls(monkeypatch):
    app=desktop_app(monkeypatch)
    with TestClient(app) as client:
        assert client.post('/desktop/update/result',json={'state':'downloaded'}).status_code==403
        assert client.get('/desktop/update/command').status_code==403
        assert client.post('/desktop/update/install').status_code==409
        assert client.post('/desktop/update/shell',json={'url':'https://example.com/x.exe'}).status_code==404
        assert client.post('/desktop/update/check').status_code==200
        assert client.post('/desktop/update/check').status_code==409
        assert client.get('/desktop/update/command',headers={'X-Study-Desktop':'a'*64}).json()=={'action':'check'}
        assert client.get('/desktop/update/command',headers={'X-Study-Desktop':'a'*64}).json()=={'action':None}

def test_busy_and_failed_backup_do_not_install_or_freeze_app(monkeypatch,client):
    import backup
    app=desktop_app(monkeypatch);bridge=app.state.update_bridge
    bridge.status['state']='downloaded';bridge.active=1
    with TestClient(app) as updater:
        assert updater.post('/desktop/update/install').status_code==409
        assert not bridge.frozen and bridge.command is None
        bridge.active=0
        def broken(*args):raise OSError('private path must not leak')
        monkeypatch.setattr(backup,'create_backup',broken)
        response=updater.post('/desktop/update/install')
        assert response.status_code==503 and 'private path' not in response.text
        assert not bridge.frozen and bridge.command is None

def test_verified_backup_precedes_install_command(monkeypatch,client,tmp_path):
    import backup
    monkeypatch.setattr(backup,'backup_directory',lambda:tmp_path)
    app=desktop_app(monkeypatch);bridge=app.state.update_bridge;bridge.status['state']='downloaded'
    with TestClient(app) as updater:
        assert updater.post('/desktop/update/install').status_code==200
        assert bridge.frozen and bridge.command=='install'
        assert len(list(tmp_path.glob('*.zip')))==1
        assert updater.post('/ordinary-mutation').status_code==409
        assert updater.post('/desktop/update/result',headers={'X-Study-Desktop':'a'*64},json={'state':'error','message':'Install failed.'}).status_code==200
        assert not bridge.frozen

def test_unclaimed_native_command_expires_without_freezing():
    bridge=desktop_updates.Bridge();bridge.frozen=True;bridge.command='install';bridge.started=-200
    bridge.refresh()
    assert not bridge.frozen and bridge.command is None and bridge.status['state']=='error'
