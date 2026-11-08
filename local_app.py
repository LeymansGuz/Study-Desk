"""Personal workspace setup and process control. No model calls are made here."""
from __future__ import annotations
import argparse
import contextlib
import ctypes
import getpass
import hashlib
import json
import os
import platform
import re
import secrets
import ssl
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error
import webbrowser
from pathlib import Path

ROOT=Path(__file__).resolve().parent
RUNTIME=ROOT/'data/runtime'
STATE=RUNTIME/'services.json'
OPA_VERSION='1.21.3'
HTTP=urllib.request.build_opener(urllib.request.ProxyHandler({}))

def download_client():
    import certifi
    context=ssl.create_default_context()
    context.load_verify_locations(cafile=certifi.where())
    return urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=context))

def private_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp')
    with open(temporary,'w',encoding='utf-8') as handle:
        os.chmod(temporary,0o600)
        json.dump(value,handle)
    temporary.replace(path)

def read_json(path):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):return {}

@contextlib.contextmanager
def control_lock():
    RUNTIME.mkdir(parents=True,exist_ok=True)
    with open(RUNTIME/'control.lock','a+b') as lock:
        lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:raise RuntimeError('Another setup/start/stop command is running. Wait for it to finish.')
        try:yield
        finally:
            lock.seek(0)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(lock,fcntl.LOCK_UN)

def fingerprint(pid):
    """Process birth identity prevents stale PID files from killing other apps."""
    if not isinstance(pid,int) or pid<=0:return None
    if os.name=='nt':
        from ctypes import wintypes as w
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];kernel.OpenProcess.restype=w.HANDLE
        kernel.GetProcessTimes.argtypes=[w.HANDLE,*([ctypes.POINTER(w.FILETIME)]*4)]
        kernel.GetExitCodeProcess.argtypes=[w.HANDLE,ctypes.POINTER(w.DWORD)]
        kernel.CloseHandle.argtypes=[w.HANDLE]
        handle=kernel.OpenProcess(0x1000,False,pid)
        if not handle:return None
        try:
            code=w.DWORD()
            if not kernel.GetExitCodeProcess(handle,ctypes.byref(code)) or code.value!=259:return None
            times=[w.FILETIME() for _ in range(4)]
            if not kernel.GetProcessTimes(handle,*[ctypes.byref(t) for t in times]):return None
            return str(times[0].dwHighDateTime<<32|times[0].dwLowDateTime)
        finally:kernel.CloseHandle(handle)
    if sys.platform.startswith('linux'):
        try:
            fields=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
            return None if fields[0]=='Z' else fields[19]
        except OSError:return None
    try:
        result=subprocess.run(['ps','-p',str(pid),'-o','lstart='],capture_output=True,text=True,timeout=3)
        return result.stdout.strip() or None
    except (OSError,subprocess.TimeoutExpired):return None

def alive(record):
    return bool(record.get('birth') and fingerprint(record.get('pid'))==record['birth'])

def owned_state():
    state=read_json(STATE)
    if state and state.get('root')!=str(ROOT):raise RuntimeError('Runtime state belongs to a different folder; no processes were changed.')
    return state

def port_free(port):
    with socket.socket() as listener:
        if os.name=='nt':listener.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        try:listener.bind(('127.0.0.1',port));return True
        except OSError:return False

def configuration():
    from dotenv import dotenv_values
    values=dotenv_values(ROOT/'.env')
    def port(name,default):
        raw=values.get(name) or str(default)
        if not raw.isdigit() or not 1024<=int(raw)<=65535:raise RuntimeError(f'{name} must be a port between 1024 and 65535 in .env.')
        return int(raw)
    web,opa=port('LOCAL_PORT',8002),port('LOCAL_OPA_PORT',8182)
    if web==opa:raise RuntimeError('LOCAL_PORT and LOCAL_OPA_PORT must be different.')
    return values,web,opa

def environment(opa_port=8182):
    from dotenv import dotenv_values
    values=dotenv_values(ROOT/'.env')
    # Project configuration wins over provider keys inherited from another app.
    env=dict(os.environ)
    for key in list(env):
        if key.startswith(('OPENAI_','LANGCHAIN_','LANGSMITH_','OPA_')):env.pop(key,None)
    env.update({k:v for k,v in values.items() if v is not None})
    env.update(APP_DB_PATH=str(ROOT/'data/app.db'),USERS_DIR=str(ROOT/'data/users'),CHROMA_DIR=str(ROOT/'data/chroma'),
        APP_ALLOWED_HOSTS='localhost,127.0.0.1,::1',OPA_URL=f'http://127.0.0.1:{opa_port}',OPA_DECISION_PATH='tutor/decision',
        LANGSMITH_TRACING='false',LANGCHAIN_TRACING_V2='false',PYTHONUTF8='1')
    return env

def request(url,*,token='',method='GET',control=False):
    headers={}
    if token:headers['X-Local-Control' if control else 'Authorization']=token if control else 'Bearer '+token
    req=urllib.request.Request(url,headers=headers,method=method,data=b'' if method=='POST' else None)
    with HTTP.open(req,timeout=3) as response:return json.load(response)

def opa_binary():
    private=ROOT/'.tools'/('opa.exe' if os.name=='nt' else 'opa')
    return str(private) if private.is_file() else shutil.which('opa')

def download_opa():
    machine=platform.machine().lower()
    arch='arm64' if machine in {'arm64','aarch64'} else 'amd64' if machine in {'amd64','x86_64'} else None
    system={'win32':'windows','darwin':'darwin'}.get(sys.platform,'linux' if sys.platform.startswith('linux') else None)
    if not arch or not system or (system=='windows' and arch!='amd64'):raise RuntimeError('Install OPA manually for this platform: https://www.openpolicyagent.org/docs')
    asset=f'opa_{system}_{arch}'+('_static' if system=='linux' else '.exe' if system=='windows' else '')
    base=f'https://github.com/open-policy-agent/opa/releases/download/v{OPA_VERSION}/{asset}'
    client=download_client()
    def fetch(url,limit):
        for attempt in range(3):
            # A fresh URL on retry avoids a cached gateway error. Trust still comes
            # from HTTPS and the release checksum, never from retry success alone.
            target=url if not attempt else url+'?study_setup_retry='+str(time.monotonic_ns())
            req=urllib.request.Request(target,headers={'User-Agent':'StudyDesk-Setup/1.0'})
            try:
                with client.open(req,timeout=90) as response:
                    if not response.geturl().startswith('https://'):raise RuntimeError('OPA download redirected to an insecure connection.')
                    data=response.read(limit+1)
                if len(data)>limit:raise RuntimeError('OPA download exceeded its size limit.')
                return data
            except (urllib.error.URLError,TimeoutError,ConnectionError) as exc:
                transient=not isinstance(exc,urllib.error.HTTPError) or exc.code in {408,429,500,502,503,504}
                if not transient:raise
                if attempt==2:
                    # CI's scoped GitHub token can use the official release API
                    # when the public browser-download gateway is unavailable.
                    # gh handles authenticated redirects; never forward a token
                    # ourselves to an asset CDN. The same checksum gate follows.
                    gh=shutil.which('gh')
                    if not gh or not os.getenv('GH_TOKEN'):raise
                    import tempfile
                    with tempfile.TemporaryDirectory(prefix='study-opa-') as stage:
                        name=url.rsplit('/',1)[-1]
                        subprocess.run([gh,'release','download','v'+OPA_VERSION,'--repo',
                            'https://github.com/open-policy-agent/opa','--pattern',name,
                            '--dir',stage],check=True,capture_output=True,timeout=120)
                        with (Path(stage)/name).open('rb') as handle:data=handle.read(limit+1)
                    if len(data)>limit:raise RuntimeError('OPA download exceeded its size limit.')
                    return data
                time.sleep(attempt+1)
    checksum=fetch(base+'.sha256',4096).decode('ascii').split()[0]
    if not re.fullmatch('[0-9a-fA-F]{64}',checksum):raise RuntimeError('OPA checksum was invalid; nothing was installed.')
    payload=fetch(base,150*1024**2)
    if hashlib.sha256(payload).hexdigest()!=checksum.lower():raise RuntimeError('OPA checksum did not match; nothing was installed.')
    target=ROOT/'.tools'/('opa.exe' if os.name=='nt' else 'opa');target.parent.mkdir(exist_ok=True)
    part=target.with_suffix('.download');part.write_bytes(payload);part.chmod(0o700);part.replace(target)
    return str(target)

def dependencies():
    node=shutil.which('node')
    if not node:raise RuntimeError('Node.js is missing. Install Node.js 20+ from https://nodejs.org/ and rerun setup.')
    try:major=int(subprocess.check_output([node,'--version'],text=True,timeout=10).strip().lstrip('v').split('.')[0])
    except (OSError,ValueError,subprocess.SubprocessError):raise RuntimeError('Node.js could not start. Rerun setup after checking the Node.js installation.')
    if major<20:raise RuntimeError('Node.js 20 or newer is required.')
    opa=opa_binary()
    if not opa:raise RuntimeError('OPA is missing. Rerun setup, or install OPA manually from https://www.openpolicyagent.org/docs.')
    try:subprocess.run([opa,'version'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
    except (OSError,subprocess.SubprocessError):raise RuntimeError('OPA could not start. Rerun setup to repair the installation.')
    return opa

def setup(interactive=True,offline=False):
    if any(alive(owned_state().get(k,{})) for k in ['web','opa']):raise RuntimeError('Stop the local app before running setup.')
    env=ROOT/'.env'
    if not env.exists():shutil.copyfile(ROOT/'.env.example',env);env.chmod(0o600)
    if not opa_binary():
        if offline:raise RuntimeError('OPA is missing and offline setup cannot download it.')
        print(f'Downloading OPA {OPA_VERSION} and checking SHA-256…',flush=True);download_opa()
    dependencies()
    from dotenv import dotenv_values,set_key
    values=dotenv_values(env)
    if interactive and not values.get('OPENAI_API_KEY'):
        key=getpass.getpass('Your DeepSeek API key (hidden; Enter to configure later): ').strip()
        if key:set_key(str(env),'OPENAI_API_KEY',key)
    print('Setup complete. Start Study Desk with:')
    print('  Windows: Start.cmd')
    print('  macOS/Linux: uv run --no-dev python local_app.py start')
    print('No AI requests were made.')

def spawn(command,env,log_name):
    RUNTIME.mkdir(parents=True,exist_ok=True)
    log=RUNTIME/(log_name+'.log')
    if log.exists() and log.stat().st_size>5*1024**2:log.replace(log.with_suffix('.log.1'))
    flags=(subprocess.CREATE_NO_WINDOW|subprocess.CREATE_NEW_PROCESS_GROUP) if os.name=='nt' else 0
    with open(log,'ab') as output:
        return subprocess.Popen(command,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=output,stderr=output,
            creationflags=flags,start_new_session=os.name!='nt',close_fds=True)

def terminate_owned(record):
    if not alive(record):return
    os.kill(record['pid'],signal.SIGTERM)
    deadline=time.monotonic()+8
    while alive(record) and time.monotonic()<deadline:time.sleep(.1)
    if alive(record) and os.name!='nt':os.kill(record['pid'],signal.SIGKILL)

def owned_children(record):
    if not alive(record):return []
    import psutil
    try:
        children=[{'pid':p.pid,'birth':fingerprint(p.pid)} for p in psutil.Process(record['pid']).children(recursive=True)]
        return children if alive(record) else []
    except (psutil.NoSuchProcess,psutil.AccessDenied):return []

def stop():
    state=owned_state()
    if not state:print('Study Desk is stopped.');return
    web=state.get('web',{})
    children=owned_children(web)
    if alive(web):
        try:request(f"http://127.0.0.1:{state['web_port']}/local/control/stop",token=state['control'],method='POST',control=True)
        except Exception:pass
        deadline=time.monotonic()+30
        while alive(web) and time.monotonic()<deadline:time.sleep(.2)
        terminate_owned(web)
    # OCR/SymPy workers belong to this web process, not to another local app.
    for child in reversed(children):terminate_owned(child)
    terminate_owned(state.get('opa',{}))
    STATE.unlink(missing_ok=True);(RUNTIME/'web.json').unlink(missing_ok=True);(RUNTIME/'policy-auth.json').unlink(missing_ok=True)
    print('Study Desk and its private policy service are stopped. Your data is kept.')

def start(open_browser=True,timeout=75):
    old=owned_state()
    if alive(old.get('web',{})):
        try:healthy=request(f"http://127.0.0.1:{old['web_port']}/local/runtime").get('instance')==old['instance'] and alive(old.get('opa',{}))
        except Exception:healthy=False
        if not healthy:raise RuntimeError('The local app needs attention. Stop it, then start it again. See data/runtime logs.')
        print(f"Already running: http://127.0.0.1:{old['web_port']}")
        if open_browser:webbrowser.open(f"http://127.0.0.1:{old['web_port']}")
        return
    if alive(old.get('opa',{})):stop()
    values,web_port,opa_port=configuration();opa=dependencies()
    if not (ROOT/'.env').exists():raise RuntimeError('Run setup first.')
    for port in [web_port,opa_port]:
        if not port_free(port):raise RuntimeError(f'Port {port} is used by another service. No process was stopped. Set LOCAL_PORT / LOCAL_OPA_PORT in .env.')
    instance=secrets.token_hex(16);opa_token=secrets.token_urlsafe(32);control=secrets.token_urlsafe(32)
    env=environment(opa_port);env.update(STUDY_LOCAL_INSTANCE=instance,STUDY_LOCAL_CONTROL_TOKEN=control,OPA_BEARER_TOKEN=opa_token)
    auth_file=RUNTIME/'policy-auth.json';private_json(auth_file,{'local_security':{'token':opa_token}})
    state={'root':str(ROOT),'instance':instance,'control':control,'web_port':web_port,'opa_port':opa_port}
    try:
        process=spawn([opa,'run','--server','--addr',f'127.0.0.1:{opa_port}','--authentication=token','--authorization=basic','--skip-version-check','--log-level=error',str(ROOT/'policy/tutor.rego'),str(ROOT/'policy/local_authz.rego'),str(auth_file)],env,'opa')
        state['opa']={'pid':process.pid,'birth':fingerprint(process.pid)};private_json(STATE,state)
        deadline=time.monotonic()+15
        while True:
            try:request(f'http://127.0.0.1:{opa_port}/health',token=opa_token);break
            except Exception:
                if process.poll() is not None or time.monotonic()>deadline:raise RuntimeError('The private policy service could not start. See data/runtime/opa.log.')
                time.sleep(.2)
        spawn([sys.executable,str(ROOT/'service_host.py'),str(web_port),instance],env,'web')
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            record=read_json(RUNTIME/'web.json')
            if record.get('instance')==instance:
                state['web']=record;private_json(STATE,state)
                if not alive(record):raise RuntimeError('Study Desk exited during startup. See data/runtime/web-runtime.log and rerun setup to repair dependencies.')
                try:
                    result=request(f'http://127.0.0.1:{web_port}/local/runtime')
                    if result.get('instance')==instance:
                        print(f'Ready: http://127.0.0.1:{web_port}')
                        if not values.get('OPENAI_API_KEY'):print('AI key is not configured. Rerun setup to enter it; document browsing remains available.')
                        if open_browser:webbrowser.open(f'http://127.0.0.1:{web_port}')
                        return
                except Exception:pass
            time.sleep(.25)
        raise RuntimeError('Study Desk did not become ready. See data/runtime/web.log, then stop and rerun setup.')
    except BaseException:
        record=read_json(RUNTIME/'web.json')
        if record.get('instance')==instance:state['web']=record
        private_json(STATE,state);stop();raise

def status(quiet=False):
    state=owned_state();web=alive(state.get('web',{}));opa=alive(state.get('opa',{}))
    if not quiet:print(f"Study Desk: {'running' if web else 'stopped'}; private policy service: {'running' if opa else 'stopped'}."+(f" http://127.0.0.1:{state['web_port']}" if web else ''))
    return web or opa

def main(argv=None):
    parser=argparse.ArgumentParser(description='Set up, start, stop or check Study Desk Local.')
    parser.add_argument('action',choices=['setup','start','stop','status']);parser.add_argument('--no-browser',action='store_true');parser.add_argument('--non-interactive',action='store_true');parser.add_argument('--offline',action='store_true');parser.add_argument('--quiet',action='store_true')
    args=parser.parse_args(argv)
    try:
        with control_lock():
            if args.action=='setup':setup(not args.non_interactive,args.offline)
            elif args.action=='start':start(not args.no_browser)
            elif args.action=='stop':stop()
            else:return 0 if status(args.quiet) else 1
        return 0
    except KeyboardInterrupt:print('Cancelled. Your study data has been kept.',file=sys.stderr);return 130
    except (RuntimeError,OSError) as exc:print(f'Cannot {args.action}: {exc}',file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
