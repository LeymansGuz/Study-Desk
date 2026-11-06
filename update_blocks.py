"""Signed, content-defined update downloads. Reconstruct; never patch a live app.

An optional signed block map enables reuse of the last verified package. The
ordinary signed installer remains the installation and recovery authority.
"""
from __future__ import annotations
import hashlib,json,mmap,os,re,shutil,time
from pathlib import Path
from urllib.parse import urlsplit
from cryptography.exceptions import InvalidSignature
from desktop.verify_signature import verify

MAX_PACKAGE=1_500_000_000
MIN_BLOCK=32768
MAX_BLOCK=524288
MAP_LIMIT=4_000_000
ANCHOR=re.compile(b'\x00\x00')

def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def blocks(path):
    path=Path(path)
    if not path.stat().st_size:return []
    result=[]
    with path.open('rb') as stream,mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ) as data:
        start=0
        while start<len(data):
            match=ANCHOR.search(data,start+MIN_BLOCK,min(start+MAX_BLOCK,len(data)))
            end=match.end() if match else min(start+MAX_BLOCK,len(data))
            result.append({'offset':start,'size':end-start,'sha256':hashlib.sha256(data[start:end]).hexdigest()})
            start=end
    return result

def make_map(path,version):
    path=Path(path)
    return {'format':1,'version':version,'filename':re.sub(r'[^A-Za-z0-9._-]+','-',path.name).strip('.-'),'size':path.stat().st_size,'sha256':digest(path),'blocks':blocks(path)}

def validate_map(body,url,version):
    if not isinstance(body,dict) or body.get('format')!=1 or body.get('version')!=version:raise ValueError('Invalid block-map version')
    if body.get('filename')!=urlsplit(url).path.rsplit('/',1)[-1]:raise ValueError('Invalid block-map filename')
    size=body.get('size');rows=body.get('blocks')
    if type(size) is not int or not 0<size<=MAX_PACKAGE or not isinstance(rows,list) or not 0<len(rows)<=46000:raise ValueError('Invalid block-map size')
    if not re.fullmatch('[a-f0-9]{64}',str(body.get('sha256',''))):raise ValueError('Invalid package hash')
    offset=0
    for row in rows:
        if not isinstance(row,dict) or row.get('offset')!=offset or type(row.get('size')) is not int or not 0<row['size']<=MAX_BLOCK or not re.fullmatch('[a-f0-9]{64}',str(row.get('sha256',''))):raise ValueError('Invalid block layout')
        offset+=row['size']
    if offset!=size:raise ValueError('Incomplete block map')
    return body

def official(url,version):
    parsed=urlsplit(url)
    prefix=f'/LeymansGuz/Study-Desk/releases/download/v{version}'
    rest=parsed.path[len(prefix):] if parsed.path.startswith(prefix) else ''
    return parsed.scheme=='https' and parsed.hostname=='github.com' and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment and rest.startswith(('/','-')) and version in rest.rsplit('/',1)[-1]

def limited_get(client,url,limit,headers=None):
    with client.stream('GET',url,headers=headers or {}) as response:
        response.raise_for_status();data=bytearray()
        for chunk in response.iter_bytes():
            if len(data)+len(chunk)>limit:raise ValueError('Download exceeds its permitted size')
            data.extend(chunk)
        return response,bytes(data)

def reconstruct(manifest,old,output,fetch,progress=lambda **_:None,index=None):
    """Range callback returns exact bytes. Re-check cached and resumed blocks."""
    old=Path(old);output=Path(output)
    available=index if index is not None else {(r['sha256'],r['size']):r['offset'] for r in blocks(old)} if old.is_file() else {}
    reused=received=0
    previous_size=output.stat().st_size if output.exists() else 0
    with (old.open('rb') if old.is_file() else open(os.devnull,'rb')) as source,output.open('r+b' if output.exists() else 'w+b') as target:
        # A partial file is never trusted because a checkpoint says it exists.
        rows=manifest['blocks'];index=0
        while index<len(rows):
            row=rows[index];offset,size=row['offset'],row['size'];key=row['sha256'],size
            target.seek(offset);existing=target.read(size) if previous_size>=offset+size else b''
            if hashlib.sha256(existing).hexdigest()==row['sha256']:
                reused+=size;index+=1
            elif key in available:
                source.seek(available[key]);data=source.read(size)
                if hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('Cached update changed during reuse')
                target.seek(offset);target.write(data);reused+=size;index+=1
            else:
                # Coalesce missing adjacent blocks, limiting HTTP requests/memory.
                end=index+1;total=size
                while end<len(rows) and total+rows[end]['size']<=8*1024*1024 and (rows[end]['sha256'],rows[end]['size']) not in available:
                    total+=rows[end]['size'];end+=1
                data=fetch(offset,total)
                if len(data)!=total:raise ValueError('Incomplete update range')
                position=0
                for check in rows[index:end]:
                    part=data[position:position+check['size']]
                    if hashlib.sha256(part).hexdigest()!=check['sha256']:raise ValueError('Update block checksum failed')
                    position+=check['size']
                target.seek(offset);target.write(data);target.flush();received+=total;index=end
            progress(received=received,reused=reused,total=manifest['size'])
        target.truncate(manifest['size']);target.flush();os.fsync(target.fileno())
    if digest(output)!=manifest['sha256']:raise ValueError('Reconstructed package checksum failed')
    return {'received':received,'reused':reused,'total':manifest['size']}

def prepare(request,client=None,progress=lambda **_:None):
    import httpx
    url,version=request['url'],request['version']
    if not official(url,version):raise ValueError('Only official versioned release downloads are accepted')
    cache=Path(request['cache']).resolve();cache.mkdir(parents=True,exist_ok=True)
    old=cache/'previous.package';partial=cache/'download.part';mapfile=cache/'blocks.json'
    owned=client is None
    if owned:client=httpx.Client(follow_redirects=True,trust_env=False,timeout=httpx.Timeout(60,connect=20))
    started=time.monotonic()
    try:
        manifest=None
        try:
            _,body=limited_get(client,url+'.blocks.json',MAP_LIMIT)
            _,signature=limited_get(client,url+'.blocks.json.sig',8192)
            mapfile.write_bytes(body)
            verify(mapfile,signature.decode().strip(),request['public_key'],version)
            manifest=validate_map(json.loads(body),url,version)
        except (httpx.HTTPError,ValueError,KeyError,UnicodeError,InvalidSignature,IndexError,TypeError):
            # Missing/invalid acceleration metadata cannot bypass package signing.
            manifest=None
        stats=None
        if manifest and ((old.exists() and old.stat().st_size<=MAX_PACKAGE) or partial.exists()):
            allocated=partial.stat().st_size if partial.exists() else 0
            if shutil.disk_usage(cache).free<max(0,manifest['size']-allocated)+100_000_000:raise ValueError('Not enough free space to stage the update')
            def fetch(offset,size):
                if time.monotonic()-started>850:raise TimeoutError('Update download timed out')
                response,data=limited_get(client,url,size,{'Range':f'bytes={offset}-{offset+size-1}'})
                if response.status_code!=206 or response.headers.get('content-range')!=f'bytes {offset}-{offset+size-1}/{manifest["size"]}':raise ValueError('The download host did not honor byte ranges')
                return data
            index={(r['sha256'],r['size']):r['offset'] for r in blocks(old)} if old.exists() and old.stat().st_size<=MAX_PACKAGE else {}
            reusable=sum(r['size'] for r in manifest['blocks'] if (r['sha256'],r['size']) in index)
            try:
                if reusable<manifest['size']*.05 and not partial.exists():raise ValueError('A full transfer is more efficient for this package')
                stats=reconstruct(manifest,old,partial,fetch,progress,index)
            except (httpx.HTTPError,ValueError):
                progress(received=0,reused=0,total=0,fallback=True)
        if stats is None:
            received=0
            with client.stream('GET',url) as response:
                response.raise_for_status()
                total=int(response.headers.get('content-length','0'))
                if not 0<=total<=MAX_PACKAGE:raise ValueError('Invalid update size')
                if shutil.disk_usage(cache).free<(total or MAX_PACKAGE)+100_000_000:raise ValueError('Not enough free space to stage the update')
                with partial.open('wb') as stream:
                    for chunk in response.iter_bytes(1024*1024):
                        received+=len(chunk)
                        if received>MAX_PACKAGE or time.monotonic()-started>850:raise ValueError('Update download exceeded its limit')
                        stream.write(chunk);progress(received=received,reused=0,total=total)
                    stream.flush();os.fsync(stream.fileno())
            if total and received!=total:raise ValueError('Incomplete package')
            stats={'received':received,'reused':0,'total':received}
        verify(partial,request['signature'],request['public_key'],version)
        if manifest and (digest(partial)!=manifest['sha256'] or partial.stat().st_size!=manifest['size']):raise ValueError('Package does not match its signed block map')
        # Only a complete signed package replaces the reusable cache. Keep at most
        # one previous package plus one interrupted staging file.
        os.replace(partial,old)
        return {**stats,'path':str(old),'version':version}
    finally:
        mapfile.unlink(missing_ok=True)
        if owned:client.close()

def worker(path):
    request_path=Path(path)
    if request_path.stat().st_size>16384:raise ValueError('Invalid update request')
    request=json.loads(request_path.read_text(encoding='utf-8'))
    if request.get('parent_pid'):
        import psutil,threading
        parent=psutil.Process(request['parent_pid']);birth=parent.create_time()
        def watch_parent():
            while True:
                try:
                    if not parent.is_running() or parent.create_time()!=birth:os._exit(1)
                except psutil.Error:os._exit(1)
                time.sleep(1)
        threading.Thread(target=watch_parent,daemon=True).start()
    last=[0.0]
    def emit(**state):
        if time.monotonic()-last[0]>.5 or state.get('fallback'):
            print(json.dumps({'progress':state}),flush=True);last[0]=time.monotonic()
    try:print(json.dumps({'complete':prepare(request,progress=emit)}),flush=True)
    except Exception:
        print(json.dumps({'error':'Update preparation failed. No update was installed. Check connection and free space, then retry.'}),flush=True)
        raise SystemExit(1)
    finally:request_path.unlink(missing_ok=True)
