"""Frozen desktop backend entry point; never loads the developer's .env."""
import os
import sys

def main():
    import multiprocessing
    multiprocessing.freeze_support()
    if '--self-check' in sys.argv:
        from desktop_checks import run
        run();return
    if '--math-worker' in sys.argv:
        import json
        from math_checks import check_claim
        results=[]
        for claim in json.load(sys.stdin):
            try:results.append(check_claim(claim))
            except Exception:results.append({'status':'unresolved','reason':'Unsupported or invalid expression.'})
        print(json.dumps(results));return
    import argparse,atexit,json,logging,logging.handlers,secrets,socket,subprocess,time,threading
    from pathlib import Path
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-dir',required=True);parser.add_argument('--port',type=int,required=True)
    parser.add_argument('--parent-pid',type=int,required=True)
    args=parser.parse_args()
    secret=os.environ.get('STUDY_DESKTOP_SECRET','')
    if len(secret)<32:raise SystemExit('Open Study Desk using the desktop application.')
    data=Path(args.data_dir).resolve();data.mkdir(parents=True,exist_ok=True)
    resources=Path(__file__).resolve().parent
    binary_dir=resources/'bin'
    # All providers are configured here, before importing app modules. Installed
    # releases contain no .env, study data, private course files or developer key.
    for key in list(os.environ):
        if key.startswith(('OPENAI_','DEEPSEEK_','LANGCHAIN_','LANGSMITH_','OPA_')):os.environ.pop(key,None)
    os.environ.update(APP_DB_PATH=str(data/'app.db'),USERS_DIR=str(data/'users'),CHROMA_DIR=str(data/'chroma'),
        OPENAI_BASE_URL='https://api.deepseek.com/v1',OPENAI_MODEL='deepseek-flash',OPENAI_API_KEY='',
        LANGSMITH_TRACING='false',LANGCHAIN_TRACING_V2='false',AUTO_MAINTENANCE='true',MANAGED_LOGGING='true',
        STUDY_DESKTOP='true',APP_ALLOWED_HOSTS='localhost,127.0.0.1,::1',
        STUDY_NODE_BINARY=str(binary_dir/('node.exe' if os.name=='nt' else 'node')),
        HF_HOME=str(data/'model-cache'),XDG_CACHE_HOME=str(data/'cache'),ANONYMIZED_TELEMETRY='false')
    os.chdir(data)
    log=data/'logs';log.mkdir(exist_ok=True)
    handler=logging.handlers.RotatingFileHandler(log/'desktop.log',maxBytes=5_000_000,backupCount=3,encoding='utf-8')
    logging.basicConfig(level=logging.INFO,handlers=[handler],format='%(asctime)s %(levelname)s %(name)s %(message)s',force=True)
    if os.name=='nt':
        # All workers and OPA die if this backend is terminated unexpectedly.
        import ctypes
        from ctypes import wintypes as w
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        class Basic(ctypes.Structure):
            _fields_=[('time1',ctypes.c_int64),('time2',ctypes.c_int64),('flags',w.DWORD),('min',ctypes.c_size_t),('max',ctypes.c_size_t),('active',w.DWORD),('affinity',ctypes.c_size_t),('priority',w.DWORD),('scheduling',w.DWORD)]
        class IO(ctypes.Structure):_fields_=[('values',ctypes.c_uint64*6)]
        class Limits(ctypes.Structure):_fields_=[('basic',Basic),('io',IO),('p1',ctypes.c_size_t),('p2',ctypes.c_size_t),('p3',ctypes.c_size_t),('p4',ctypes.c_size_t)]
        kernel.CreateJobObjectW.restype=w.HANDLE
        kernel.SetInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD]
        kernel.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE]
        kernel.GetCurrentProcess.restype=w.HANDLE
        job=kernel.CreateJobObjectW(None,None);limits=Limits();limits.basic.flags=0x2000
        if not job or not kernel.SetInformationJobObject(job,9,ctypes.byref(limits),ctypes.sizeof(limits)) or not kernel.AssignProcessToJobObject(job,kernel.GetCurrentProcess()):
            raise RuntimeError('The operating system could not isolate desktop worker processes.')
    from desktop_runtime import load_key
    try:os.environ['OPENAI_API_KEY']=load_key()
    except Exception:logging.warning('System credential store unavailable; configure/unlock it in Settings.')
    with socket.socket() as s:s.bind(('127.0.0.1',0));opa_port=s.getsockname()[1]
    token=secrets.token_urlsafe(32)
    authfile=data/'policy-auth.json';authfile.write_text(json.dumps({'local_security':{'token':token}}),encoding='utf-8');os.chmod(authfile,0o600)
    os.environ.update(OPA_URL=f'http://127.0.0.1:{opa_port}',OPA_BEARER_TOKEN=token,OPA_DECISION_PATH='tutor/decision')
    opa_log=(log/'policy.log').open('ab')
    opa=subprocess.Popen([str(binary_dir/('opa.exe' if os.name=='nt' else 'opa')),'run','--server','--addr',f'127.0.0.1:{opa_port}',
        '--authentication=token','--authorization=basic','--skip-version-check','--log-level=error',str(resources/'policy'),str(authfile)],
        stdout=opa_log,stderr=opa_log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    def cleanup():
        if opa.poll() is None:
            opa.terminate()
            try:opa.wait(timeout=5)
            except subprocess.TimeoutExpired:opa.kill()
        authfile.unlink(missing_ok=True)
    atexit.register(cleanup)
    import urllib.request
    direct=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(100):
        try:
            with direct.open(urllib.request.Request(os.environ['OPA_URL']+'/health',headers={'Authorization':'Bearer '+token}),timeout=1):break
        except Exception:
            if opa.poll() is not None:raise RuntimeError('The bundled policy service could not start.')
            time.sleep(.1)
    else:raise RuntimeError('The bundled policy service did not become ready.')
    import app,uvicorn
    from desktop_runtime import DesktopSession,install
    app.app.add_middleware(DesktopSession,secret=secret);install(app.app)
    server=uvicorn.Server(uvicorn.Config(app.app,host='127.0.0.1',port=args.port,proxy_headers=False,access_log=False,log_config=None,timeout_graceful_shutdown=20))
    app.app.state.local_shutdown=lambda:setattr(server,'should_exit',True)
    import psutil
    parent=psutil.Process(args.parent_pid);birth=parent.create_time()
    def watch_parent():
        while not server.should_exit:
            try:
                if not parent.is_running() or parent.create_time()!=birth:break
            except psutil.Error:break
            time.sleep(1)
        server.should_exit=True
    threading.Thread(target=watch_parent,daemon=True).start()
    try:server.run()
    finally:cleanup()

if __name__=='__main__':main()
