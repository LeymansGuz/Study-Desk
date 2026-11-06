import json,random
from pathlib import Path
import httpx,pytest
from update_blocks import blocks,make_map,validate_map,reconstruct,prepare,official
from test_release_packaging import signed_fixture

def data(size=4*1024*1024):return random.Random(1743).randbytes(size)

def test_shifted_blocks_reuse_bytes_and_reconstruct_exactly(tmp_path):
    old=tmp_path/'old';new=tmp_path/'Study-Desk_9.0.0.exe';old.write_bytes(data());payload=old.read_bytes();new.write_bytes(b'new release header'+payload[:900000]+b'x'*12000+payload[912000:])
    manifest=make_map(new,'9.0.0');out=tmp_path/'staged';calls=[]
    def fetch(offset,size):calls.append(size);return new.read_bytes()[offset:offset+size]
    result=reconstruct(manifest,old,out,fetch)
    assert out.read_bytes()==new.read_bytes()
    assert result['received']==sum(calls)<new.stat().st_size*.20
    assert result['reused']+result['received']==new.stat().st_size

def test_interrupted_reconstruction_reuses_verified_partial_blocks(tmp_path):
    old=tmp_path/'old';new=tmp_path/'Study-Desk_9.0.0.exe';raw=data(12*1024*1024);old.write_bytes(raw)
    target=raw[:1000000]+b'change'*10000+raw[1060000:9000000]+b'more'*20000+raw[9080000:];new.write_bytes(target)
    manifest=make_map(new,'9.0.0');out=tmp_path/'staged';calls=[]
    def interrupted(offset,size):
        calls.append(size)
        if len(calls)==2:raise OSError('simulated disconnect')
        return target[offset:offset+size]
    with pytest.raises(OSError):reconstruct(manifest,old,out,interrupted)
    resumed=[]
    result=reconstruct(manifest,old,out,lambda offset,size:(resumed.append(size) or target[offset:offset+size]))
    assert out.read_bytes()==target and result['received']==sum(resumed)<sum(calls)

@pytest.mark.parametrize('mode',['normal','missing_map','bad_map_signature','ignored_range','bad_range'])
def test_signed_prepare_and_safe_full_download_fallback(tmp_path,mode):
    version='9.0.0';url='https://github.com/LeymansGuz/Study-Desk/releases/download/v9.0.0-beta.1/Study-Desk_9.0.0.exe'
    raw=data();target=raw[:700000]+b'changes'+raw[700007:];asset=tmp_path/'Study-Desk_9.0.0.exe';asset.write_bytes(target)
    public,sign=signed_fixture(tmp_path,version);mapping=json.dumps(make_map(asset,version)).encode();requests=[]
    def network(request):
        requests.append(request)
        if request.url.path.endswith('.blocks.json.sig'):return httpx.Response(200,content=('invalid' if mode=='bad_map_signature' else sign(mapping)).encode())
        if request.url.path.endswith('.blocks.json'):return httpx.Response(404 if mode=='missing_map' else 200,content=mapping)
        if request.headers.get('range'):
            start,end=map(int,request.headers['range'][6:].split('-'))
            if mode=='ignored_range':return httpx.Response(200,content=target)
            body=target[start:end+1] if mode!='bad_range' else b'bad'
            return httpx.Response(206,content=body,headers={'content-range':f'bytes {start}-{end}/{len(target)}'})
        return httpx.Response(200,content=target)
    cache=tmp_path/'cache';cache.mkdir();(cache/'previous.package').write_bytes(raw)
    with httpx.Client(transport=httpx.MockTransport(network)) as client:
        result=prepare({'url':url,'version':version,'signature':sign(target),'public_key':public,'cache':str(cache)},client)
    assert Path(result['path']).read_bytes()==target
    if mode=='normal':assert result['received']<len(target)*.20
    else:assert result['received']==len(target)
    assert not (cache/'download.part').exists()

def test_invalid_package_signature_never_replaces_cached_package(tmp_path):
    url='https://github.com/LeymansGuz/Study-Desk/releases/download/v9.0.0/a9.0.0.exe';public,sign=signed_fixture(tmp_path,'9.0.0')
    cache=tmp_path/'cache';cache.mkdir();(cache/'previous.package').write_bytes(b'old verified app')
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(404) if '.blocks.json' in r.url.path else httpx.Response(200,content=b'tampered'))) as client:
        with pytest.raises(Exception):prepare({'url':url,'version':'9.0.0','signature':sign(b'correct payload'),'public_key':public,'cache':str(cache)},client)
    assert (cache/'previous.package').read_bytes()==b'old verified app'

def test_first_download_can_resume_without_an_older_cached_package(tmp_path):
    target=data();asset=tmp_path/'app9.0.0.exe';asset.write_bytes(target);manifest=make_map(asset,'9.0.0')
    mapping=json.dumps(manifest).encode();public,sign=signed_fixture(tmp_path,'9.0.0');cache=tmp_path/'cache';cache.mkdir()
    prefix=sum(r['size'] for r in manifest['blocks'][:4]);(cache/'download.part').write_bytes(target[:prefix])
    seen=[]
    def network(request):
        if request.url.path.endswith('.blocks.json.sig'):return httpx.Response(200,content=sign(mapping).encode())
        if request.url.path.endswith('.blocks.json'):return httpx.Response(200,content=mapping)
        seen.append(request.headers.get('range'));start,end=map(int,seen[-1][6:].split('-'))
        return httpx.Response(206,content=target[start:end+1],headers={'content-range':f'bytes {start}-{end}/{len(target)}'})
    with httpx.Client(transport=httpx.MockTransport(network)) as client:
        result=prepare({'url':'https://github.com/LeymansGuz/Study-Desk/releases/download/v9.0.0/app9.0.0.exe','version':'9.0.0','signature':sign(target),'public_key':public,'cache':str(cache)},client)
    assert result['reused']==prefix and result['received']==len(target)-prefix and all(seen)

def test_block_map_cannot_change_package_identity_or_allocate_unbounded_files(tmp_path):
    asset=tmp_path/'app9.0.0.exe';asset.write_bytes(data(100000));body=make_map(asset,'9.0.0');url='https://github.com/LeymansGuz/Study-Desk/releases/download/v9.0.0/app9.0.0.exe'
    validate_map(body,url,'9.0.0')
    for change in [{'version':'8.0.0'},{'filename':'../app.exe'},{'size':10**12},{'blocks':[]}]:
        with pytest.raises(ValueError):validate_map({**body,**change},url,'9.0.0')
    assert official(url,'9.0.0')
    assert not official(url.replace('github.com','evil.test'),'9.0.0')
    assert not official(url+'?override=1','9.0.0')
