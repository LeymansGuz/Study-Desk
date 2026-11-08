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

def test_opa_download_recovers_from_gateway_error_and_still_checks_hash(local_root,monkeypatch):
    import io,hashlib,urllib.error
    calls=[];payload=b'verified-test-binary';checksum=hashlib.sha256(payload).hexdigest().encode()
    class Client:
        def open(self,request,**kwargs):
            calls.append(request.full_url)
            if len(calls)==1:raise urllib.error.HTTPError(request.full_url,504,'Gateway timeout',{},None)
            response=io.BytesIO(checksum if '.sha256' in request.full_url else payload)
            response.geturl=lambda:request.full_url
            return response
    monkeypatch.setattr(control,'download_client',lambda:Client())
    monkeypatch.setattr(control.time,'sleep',lambda *a:None)
    control.download_opa()
    assert '?study_setup_retry=' in calls[1]
    assert len(calls)==3
    assert (local_root/'.tools'/('opa.exe' if os.name=='nt' else 'opa')).read_bytes()==payload


def test_opa_download_retry_is_bounded_and_never_installs_partial_binary(local_root,monkeypatch):
    import urllib.error
    calls=[]
    class Client:
        def open(self,request,**kwargs):
            calls.append(request.full_url)
            raise urllib.error.HTTPError(request.full_url,504,'Gateway timeout',{},None)
    monkeypatch.setattr(control,'download_client',lambda:Client())
    monkeypatch.setattr(control.time,'sleep',lambda *a:None)
    with pytest.raises(urllib.error.HTTPError):control.download_opa()
    assert len(calls)==3 and not (local_root/'.tools').exists()


def test_opa_download_does_not_retry_nontransient_errors(local_root,monkeypatch):
    import urllib.error
    calls=[]
    class Client:
        def open(self,request,**kwargs):
            calls.append(request.full_url)
            raise urllib.error.HTTPError(request.full_url,404,'Missing asset',{},None)
    monkeypatch.setattr(control,'download_client',lambda:Client())
    with pytest.raises(urllib.error.HTTPError):control.download_opa()
    assert len(calls)==1 and not (local_root/'.tools').exists()

@pytest.mark.parametrize('corrupt',[False,True])
def test_opa_api_fallback_keeps_checksum_gate(local_root,monkeypatch,corrupt):
    import urllib.error,hashlib
    from pathlib import Path
    payload=b'expected-opa-binary';calls=[]
    class Client:
        def open(self,request,**kwargs):
            raise urllib.error.HTTPError(request.full_url,504,'Gateway timeout',{},None)
    def download(args,**kwargs):
        calls.append(args)
        assert 'test-ci-token' not in str(args)
        name=args[args.index('--pattern')+1];target=Path(args[args.index('--dir')+1])/name
        target.write_bytes(hashlib.sha256(payload).hexdigest().encode() if name.endswith('.sha256') else b'wrong-binary' if corrupt else payload)
    monkeypatch.setenv('GH_TOKEN','test-ci-token')
    monkeypatch.setattr(control,'download_client',lambda:Client())
    monkeypatch.setattr(control.shutil,'which',lambda name:'gh')
    monkeypatch.setattr(control.subprocess,'run',download)
    monkeypatch.setattr(control.time,'sleep',lambda *a:None)
    if corrupt:
        with pytest.raises(RuntimeError,match='checksum did not match'):control.download_opa()
        assert not (local_root/'.tools').exists()
    else:
        control.download_opa()
        assert (local_root/'.tools'/('opa.exe' if os.name=='nt' else 'opa')).read_bytes()==payload
    assert len(calls)==2
