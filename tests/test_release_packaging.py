import hashlib
import json
import pytest
from pathlib import Path
from desktop.collect_release import PLATFORMS, check_tag, collect


def test_backend_build_fails_before_packaging_if_cargo_is_missing(monkeypatch):
    from desktop import build
    monkeypatch.setattr(build.sys,'argv',['build.py','--backend-only'])
    monkeypatch.setattr(build.shutil,'which',lambda name:None)
    calls=[]
    monkeypatch.setattr(build.subprocess,'run',lambda *a,**k:calls.append(1))
    with pytest.raises(SystemExit,match='Install Rust stable'):
        build.main()
    assert not calls


@pytest.fixture
def builds(tmp_path):
    source=tmp_path/'builds'
    for name,(system,architectures,suffixes) in PLATFORMS.items():
        folder=source/name
        folder.mkdir(parents=True)
        checks=[]
        for suffix in sorted(suffixes):
            payload={'.exe':b'MZ', '.deb':b'!<arch>\n', '.AppImage':b'\x7fELF', '.dmg':b'koly'}[suffix]+b'\0'*508
            asset=folder/('Study Desk-'+name+'-0.2.2'+suffix)
            asset.write_bytes(payload)
            checks.append(hashlib.sha256(payload).hexdigest()+'  '+asset.name)
        (folder/'SHA256SUMS.txt').write_text('\n'.join(checks),encoding='utf-8')
        (folder/('build-manifest-'+name+'.json')).write_text(json.dumps(dict(
            version='0.2.2',source_revision='same-commit',platform=system,architecture=sorted(architectures)[0])),encoding='utf-8')
    return source


def test_release_requires_all_four_platforms_before_staging(builds,tmp_path):
    next((builds/'macos-intel').glob('build-manifest*')).unlink()
    destination=tmp_path/'release'
    with pytest.raises(ValueError,match='Missing or duplicate'):collect(builds,destination,'0.2.2','same-commit')
    assert not destination.exists()

def test_windows_template_has_only_the_reviewed_upstream_compression_change():
    root=Path(__file__).resolve().parents[1]
    template=(root/'desktop/src-tauri/windows/installer.nsi').read_text(encoding='utf-8')
    upstream='Unicode true'+template.split('Unicode true',1)[1]
    assert upstream.count('SetCompressor /FINAL "{{compression}}"')==1
    upstream=upstream.replace('SetCompressor /FINAL "{{compression}}"','SetCompressor /SOLID "{{compression}}"')
    assert hashlib.sha256(upstream.encode()).hexdigest()=='d00089d3b1a2c4a30d7b6e098079100cb8f25e980f84d4515aca4597b95e967d'
    config=json.loads((root/'desktop/src-tauri/tauri.conf.json').read_text())
    assert config['bundle']['windows']['nsis']['template']=='./windows/installer.nsi'
    assert json.loads((root/'desktop/package.json').read_text())['devDependencies']['@tauri-apps/cli']=='2.12.4'


def test_release_rejects_builds_from_another_commit(builds,tmp_path):
    path=next((builds/'linux').glob('build-manifest*'))
    data=json.loads(path.read_text());data['source_revision']='older-commit';path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='mismatch'):collect(builds,tmp_path/'release','0.2.2','same-commit')


def test_release_rejects_corrupt_installer_bytes(builds,tmp_path):
    next((builds/'windows').glob('*.exe')).write_bytes(b'corrupted')
    with pytest.raises(ValueError,match='corrupted'):collect(builds,tmp_path/'release','0.2.2','same-commit')


def test_complete_release_has_independently_recomputed_checksums(builds,tmp_path):
    destination=tmp_path/'release'
    files=collect(builds,destination,'0.2.2','same-commit')
    assert len(files)==9
    assert all(' ' not in p.name for p in destination.iterdir())
    for line in (destination/'SHA256SUMS.txt').read_text().splitlines():
        digest,name=line.split('  ',1)
        assert digest==hashlib.sha256((destination/name).read_bytes()).hexdigest()
    check_tag('v0.2.2-beta.1','0.2.2')
    with pytest.raises(ValueError):check_tag('v0.2.1','0.2.2')

def signed_fixture(path,version='0.2.2'):
    import base64
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    private=Ed25519PrivateKey.generate();keyid=b'fixture1'
    public=base64.b64encode(b'untrusted comment: fixture\n'+base64.b64encode(b'Ed'+keyid+private.public_key().public_bytes_raw())+b'\n').decode()
    def sign(payload):
        signature=private.sign(hashlib.blake2b(payload).digest())
        comment='timestamp:0\tversion:'+version
        text='untrusted comment: fixture\n'+base64.b64encode(b'ED'+keyid+signature).decode()+'\ntrusted comment: '+comment+'\n'+base64.b64encode(private.sign(signature+comment.encode())).decode()+'\n'
        return base64.b64encode(text.encode()).decode()
    return public,sign

def test_independent_signature_checks_bytes_key_and_version(tmp_path):
    from desktop.verify_signature import verify
    path=tmp_path/'update.exe';path.write_bytes(b'example payload')
    public,sign=signed_fixture(path)
    signature=sign(path.read_bytes());verify(path,signature,public,'0.2.2')
    with pytest.raises(ValueError,match='version'):verify(path,signature,public,'0.2.3')
    path.write_bytes(b'tampered')
    with pytest.raises(Exception):verify(path,signature,public,'0.2.2')

def test_signed_release_requires_every_platform_signature(builds,tmp_path,monkeypatch):
    import desktop.collect_release as release
    public,sign=signed_fixture(tmp_path)
    config=tmp_path/'source/desktop/src-tauri/tauri.conf.json';config.parent.mkdir(parents=True)
    config.write_text(json.dumps({'plugins':{'updater':{'pubkey':public}}}))
    monkeypatch.setattr(release,'ROOT',tmp_path/'source')
    for platform in PLATFORMS:
        folder=builds/platform
        if platform.startswith('macos'):(folder/('Study-Desk_'+platform+'_0.2.2.app.tar.gz')).write_bytes(b'fixture app archive')
        updates=[p for p in folder.iterdir() if p.suffix in {'.exe','.AppImage','.deb'} or p.name.endswith('.app.tar.gz')]
        from update_blocks import make_map
        for payload in updates:
            payload.with_name(payload.name+'.sig').write_text(sign(payload.read_bytes()))
            blockmap=payload.with_name(payload.name+'.blocks.json');blockmap.write_text(json.dumps(make_map(payload,'0.2.2')))
            blockmap.with_name(blockmap.name+'.sig').write_text(sign(blockmap.read_bytes()))
        (folder/'SHA256SUMS.txt').write_text('\n'.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name for p in folder.iterdir() if p.name!='SHA256SUMS.txt'))
    destination=tmp_path/'signed-release'
    release.collect(builds,destination,'0.2.2','same-commit',signed=True,tag='v0.2.2-beta.1')
    manifest=json.loads((destination/'latest.json').read_text())
    assert len(manifest['platforms'])==5
    next((builds/'macos-intel').glob('*.app.tar.gz.sig')).unlink()
    with pytest.raises(ValueError,match='signature'):release.collect(builds,tmp_path/'bad-release','0.2.2','same-commit',signed=True,tag='v0.2.2-beta.1')
