import hashlib,json,os,socket,subprocess,sys
from pathlib import Path
import pytest
import local_app as control

@pytest.fixture
def local_root(tmp_path,monkeypatch):
    monkeypatch.setattr(control,'ROOT',tmp_path)
    monkeypatch.setattr(control,'RUNTIME',tmp_path/'data/runtime')
    monkeypatch.setattr(control,'STATE',tmp_path/'data/runtime/services.json')
    (tmp_path/'.env').write_text('LOCAL_PORT=8002\nLOCAL_OPA_PORT=8182\nOPENAI_API_KEY=\n')
    return tmp_path

def test_env_does_not_inherit_hosted_key_or_storage(local_root,monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','do-not-use-other-project-key')
    monkeypatch.setenv('APP_DB_PATH','/another-project/app.db')
    env=control.environment()
    assert env['OPENAI_API_KEY']==''
    assert env['APP_DB_PATH']==str(local_root/'data/app.db')
    assert env['OPA_URL']=='http://127.0.0.1:8182'
    assert env['LANGSMITH_TRACING']=='false'

def test_stale_pid_is_not_terminated(local_root):
    record={'pid':os.getpid(),'birth':'different-process-birth'}
    assert not control.alive(record)
    control.terminate_owned(record)
    assert control.fingerprint(os.getpid())

def test_state_from_another_project_is_rejected(local_root):
    control.private_json(control.STATE,{'root':'a different project'})
    with pytest.raises(RuntimeError,match='different folder'):control.stop()

def test_busy_port_does_not_kill_or_launch_anything(local_root,monkeypatch):
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0));port=listener.getsockname()[1];listener.listen()
        (local_root/'.env').write_text(f'LOCAL_PORT={port}\nLOCAL_OPA_PORT=8182\n')
        monkeypatch.setattr(control,'dependencies',lambda:'unused-opa')
        monkeypatch.setattr(control,'spawn',lambda *a:pytest.fail('Must not launch on a busy port'))
        with pytest.raises(RuntimeError,match='used by another service'):control.start(False)

def test_download_hash_mismatch_installs_nothing(local_root,monkeypatch):
    import io
    monkeypatch.setattr(control.platform,'machine',lambda:'AMD64')
    class FakeHTTP:
        def open(self,request,**kwargs):
            response=io.BytesIO(b'0'*64 if request.full_url.endswith('.sha256') else b'not-the-expected-binary')
            response.geturl=lambda:request.full_url
            return response
    monkeypatch.setattr(control,'download_client',lambda:FakeHTTP())
    with pytest.raises(RuntimeError,match='checksum did not match'):control.download_opa()
    assert not (local_root/'.tools').exists()

def test_setup_keeps_existing_settings_and_never_calls_ai(local_root,monkeypatch):
    original=(local_root/'.env').read_bytes()
    monkeypatch.setattr(control,'opa_binary',lambda:'installed-opa')
    monkeypatch.setattr(control,'dependencies',lambda:'installed-opa')
    control.setup(interactive=False,offline=True)
    assert (local_root/'.env').read_bytes()==original

def test_control_lock_prevents_duplicate_operations(local_root):
    with control.control_lock():
        with pytest.raises(RuntimeError,match='Another setup'): 
            with control.control_lock():pass

def test_alive_process_fingerprint():
    assert control.alive({'pid':os.getpid(),'birth':control.fingerprint(os.getpid())})

def test_owned_worker_cleanup_is_scoped_to_children():
    import time
    process=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
    try:
        own={'pid':os.getpid(),'birth':control.fingerprint(os.getpid())}
        children=control.owned_children(own)
        child=next(p for p in children if p['pid']==process.pid)
        for descendant in reversed(control.owned_children(child)):control.terminate_owned(descendant)
        control.terminate_owned(child)
        process.wait(timeout=10)
        assert control.alive(own)
    finally:
        if process.poll() is None:process.terminate();process.wait(timeout=10)
