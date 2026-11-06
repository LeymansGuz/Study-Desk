"""Check native CI artifacts before publishing a complete desktop prerelease."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
PLATFORMS = {
    'windows': ('win32', {'amd64', 'x86_64'}, {'.exe'}),
    'macos-arm64': ('darwin', {'arm64', 'aarch64'}, {'.dmg'}),
    'macos-intel': ('darwin', {'x86_64', 'amd64'}, {'.dmg'}),
    'linux': ('linux', {'x86_64', 'amd64'}, {'.deb', '.AppImage'}),
}


def version():
    return tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))['project']['version']


def check_tag(tag, release_version):
    if not re.fullmatch(r'v'+re.escape(release_version)+r'(?:-[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*)?', tag):
        raise ValueError('Release tag must match the source version, for example v'+release_version+'-beta.1')


def check_format(path):
    with path.open('rb') as file:
        header = file.read(8)
        if path.suffix == '.dmg':
            file.seek(-512, 2)
            valid = file.read(4) == b'koly'
        else:
            valid = header.startswith({'.exe': b'MZ', '.deb': b'!<arch>\n', '.AppImage': b'\x7fELF'}[path.suffix])
    if not valid:
        raise ValueError('Incorrect native installer format: '+path.name)


def collect(source, destination, release_version, revision, *, signed=False, tag=None):
    source, destination = Path(source), Path(destination)
    if not revision:
        raise ValueError('The exact build commit is required.')
    files, names, platforms = [], set(), {}
    for platform, (system, architectures, suffixes) in PLATFORMS.items():
        manifests = list(source.rglob('build-manifest-'+platform+'.json'))
        if len(manifests) != 1:
            raise ValueError('Missing or duplicate platform build: '+platform)
        manifest_path = manifests[0]
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if (manifest['version'] != release_version or manifest.get('source_revision') != revision
                or manifest['platform'] != system or manifest['architecture'].lower() not in architectures):
            raise ValueError('Build version, commit or architecture mismatch: '+platform)
        checksums = {}
        for line in (manifest_path.parent/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
            digest, name = line.split('  ', 1)
            checksums[name] = digest
        installers = [p for p in manifest_path.parent.iterdir() if p.suffix in suffixes]
        if {p.suffix for p in installers} != suffixes:
            raise ValueError('Missing native installer formats: '+platform)
        for path in installers:
            if release_version not in path.name or checksums.get(path.name) != hashlib.sha256(path.read_bytes()).hexdigest():
                raise ValueError('Stale or corrupted installer: '+path.name)
            check_format(path)
        extras=[]
        if signed:
            updates = [p for p in manifest_path.parent.iterdir() if (p.name.endswith('.app.tar.gz') if system=='darwin' else p.suffix in ({'.exe'} if system=='win32' else {'.AppImage','.deb'}))]
            if len(updates)!=(2 if system=='linux' else 1):raise ValueError('Missing or duplicate updater payload: '+platform)
            for payload in updates:
                signature=payload.with_name(payload.name+'.sig')
                if not signature.is_file() or checksums.get(signature.name)!=hashlib.sha256(signature.read_bytes()).hexdigest():raise ValueError('Missing or corrupted updater signature: '+platform)
                if checksums.get(payload.name)!=hashlib.sha256(payload.read_bytes()).hexdigest():raise ValueError('Corrupted updater payload: '+platform)
                from desktop.verify_signature import verify
                public_key=json.loads((ROOT/'desktop/src-tauri/tauri.conf.json').read_text(encoding='utf-8'))['plugins']['updater']['pubkey']
                verify(payload,signature.read_text(encoding='utf-8').strip(),public_key,release_version)
                if payload not in installers:extras.append(payload)
                extras.append(signature)
                from update_blocks import validate_map
                blockmap=payload.with_name(payload.name+'.blocks.json')
                block_signature=blockmap.with_name(blockmap.name+'.sig')
                if not blockmap.is_file() or not block_signature.is_file():raise ValueError('Missing differential metadata: '+platform)
                for file in [blockmap,block_signature]:
                    if checksums.get(file.name)!=hashlib.sha256(file.read_bytes()).hexdigest():raise ValueError('Corrupt differential metadata')
                verify(blockmap,block_signature.read_text().strip(),public_key,release_version)
                published=re.sub(r'[^A-Za-z0-9._-]+','-',payload.name).strip('.-')
                validate_map(json.loads(blockmap.read_text()),f'https://github.com/LeymansGuz/Study-Desk/releases/download/{tag}/{published}',release_version)
                extras.extend([blockmap,block_signature])
                published=re.sub(r'[^A-Za-z0-9._-]+','-',payload.name).strip('.-')
                target={'windows':'windows-x86_64-nsis','macos-arm64':'darwin-aarch64-app','macos-intel':'darwin-x86_64-app','linux':'linux-x86_64-'+('deb' if payload.suffix=='.deb' else 'appimage')}[platform]
                platforms[target]={'url':f'https://github.com/LeymansGuz/Study-Desk/releases/download/{tag}/{published}','signature':signature.read_text(encoding='utf-8').strip()}
        for path in installers+extras+[manifest_path]:
            # GitHub normalizes special characters in asset names. Choose stable
            # portable names before hashing so downloaded checksums still work.
            published_name = re.sub(r'[^A-Za-z0-9._-]+', '-', path.name).strip('.-')
            if published_name in names:
                raise ValueError('Duplicate release asset: '+path.name)
            names.add(published_name)
            files.append((path,published_name))
    # Publish nothing unless every requested platform has passed validation.
    destination.mkdir(parents=True, exist_ok=True)
    if any(destination.iterdir()):
        raise ValueError('Release staging directory must be empty.')
    for path,published_name in files:
        shutil.copy2(path, destination/published_name)
    if signed:
        from datetime import datetime,timezone
        (destination/'latest.json').write_text(json.dumps({'version':release_version,'notes':'A signed Study Desk update is available. See the GitHub release for details.','pub_date':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'platforms':platforms},indent=2)+'\n',encoding='utf-8')
    lines = [hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name for p in sorted(destination.iterdir())]
    (destination/'SHA256SUMS.txt').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return files


if __name__ == '__main__':
    release_version = version()
    check_tag(os.environ.get('RELEASE_TAG', ''), release_version)
    if sys.argv[1:] != ['--check-tag']:
        if len(sys.argv) != 3:
            raise SystemExit('Usage: collect_release.py INPUT OUTPUT, or --check-tag')
        collect(sys.argv[1], sys.argv[2], release_version, os.environ.get('GITHUB_SHA', ''),signed=True,tag=os.environ['RELEASE_TAG'])
