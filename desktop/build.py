"""Build a desktop backend or installer on the target OS. No AI calls."""
import argparse,hashlib,json,os,platform,shutil,subprocess,sys,tomllib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def run(args,**kwargs):subprocess.run([str(x) for x in args],cwd=ROOT,check=True,**kwargs)

def main():
    version=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    parser=argparse.ArgumentParser();parser.add_argument('--backend-only',action='store_true');parser.add_argument('--shell-only',action='store_true')
    options=parser.parse_args()
    if not options.shell_only:
        sys.path.insert(0,str(ROOT));import local_app
        private=ROOT/'build/native';private.mkdir(parents=True,exist_ok=True)
        node=shutil.which('node');opa=local_app.opa_binary()
        if not node:raise SystemExit('Install Node.js 20+ on the build machine.')
        if not opa:local_app.download_opa();opa=local_app.opa_binary()
        for source,name in [(node,'node'),(opa,'opa')]:
            target=private/(name+('.exe' if os.name=='nt' else ''));shutil.copy2(source,target)
        os.environ['STUDY_BUILD_BIN']=str(private)
        run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--distpath',ROOT/'dist/backend','--workpath',ROOT/'build/pyinstaller',ROOT/'desktop/backend.spec'])
        # Redistributable notices travel with every installer.
        notice=ROOT/'dist/backend/StudyDeskBackend/THIRD-PARTY-NOTICES.txt'
        notice.write_text('Study Desk bundles Python and packages listed in uv.lock (see source release), Node.js (https://nodejs.org/en/about/previous-releases), Open Policy Agent (Apache-2.0, https://github.com/open-policy-agent/opa), KaTeX (MIT), Marked (MIT), DOMPurify (Apache-2.0 OR MPL-2.0). Package license metadata is included in _internal. See DESKTOP.md in the source release for build/distribution requirements.\n',encoding='utf-8')
        import importlib.metadata as md
        licenses=notice.parent/'licenses';licenses.mkdir(exist_ok=True)
        shutil.copy2(ROOT/'desktop/src-tauri/windows/TAURI-NSIS-LICENSE.txt',licenses/'Tauri-NSIS-template-MIT.txt')
        for distribution in md.distributions():
            name=distribution.metadata.get('Name','package')
            for f in distribution.files or []:
                if '.dist-info/' in str(f).replace('\\','/') and any(x in f.name.lower() for x in ['license','copying','notice']):
                    source=distribution.locate_file(f)
                    if source.is_file():
                        relative=Path(*f.parts[f.parts.index(next(part for part in f.parts if part.endswith('.dist-info')))+1:])
                        target=licenses/name/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        (licenses/'Python-dependencies.json').write_text(json.dumps([{'name':d.metadata.get('Name'),'version':d.version,'license':d.metadata.get('License-Expression') or d.metadata.get('License'),'homepage':d.metadata.get('Home-page')} for d in md.distributions()],indent=2),encoding='utf-8')
        python_license=Path(sys.base_prefix)/'LICENSE.txt'
        if python_license.is_file():shutil.copy2(python_license,licenses/'Python-LICENSE.txt')
        else:
            with local_app.download_client().open(f'https://raw.githubusercontent.com/python/cpython/v{platform.python_version()}/LICENSE',timeout=60) as response:(licenses/'Python-LICENSE.txt').write_bytes(response.read())
        for name in ['PRIVACY.md','TERMS.md','THIRD-PARTY-NOTICES.md']:
            shutil.copy2(ROOT/name,notice.parent/name)
    # Native dependency notices must travel inside the packaged backend too.
    native_licenses=ROOT/'dist/backend/StudyDeskBackend/licenses/Rust';native_licenses.mkdir(parents=True,exist_ok=True)
    metadata=json.loads(subprocess.check_output(['cargo','metadata','--locked','--format-version','1','--manifest-path',str(ROOT/'desktop/src-tauri/Cargo.toml')],cwd=ROOT,text=True,encoding='utf-8'))
    inventory=[]
    for package in metadata['packages']:
        inventory.append({k:package.get(k) for k in ['name','version','license','repository']})
        folder=Path(package['manifest_path']).parent
        for source in folder.iterdir():
            if source.is_file() and source.name.lower().startswith(('license','copying','notice','copyright')):
                target=native_licenses/(package['name']+'-'+package['version'])/source.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        if package.get('license_file'):
            source=folder/package['license_file']
            if source.is_file():
                target=native_licenses/(package['name']+'-'+package['version'])/source.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    (native_licenses/'inventory.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
    if not options.shell_only:
        node_license=Path(node).parent/'LICENSE'
        if node_license.is_file():shutil.copy2(node_license,licenses/'Node-LICENSE.txt')
        node_version=subprocess.check_output([node,'--version'],text=True).strip()
        for name,url in [('Node-LICENSE.txt',f'https://raw.githubusercontent.com/nodejs/node/{node_version}/LICENSE'),
                         ('OPA-LICENSE.txt',f'https://raw.githubusercontent.com/open-policy-agent/opa/v{local_app.OPA_VERSION}/LICENSE')]:
            if not (licenses/name).exists():
                with local_app.download_client().open(url,timeout=60) as response:(licenses/name).write_bytes(response.read())
        version=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
        (notice.parent/'build-manifest.json').write_text(json.dumps({'version':version,'python':platform.python_version(),
            'platform':sys.platform,'architecture':platform.machine(),'node':node_version,'opa':local_app.OPA_VERSION,
            'uv_lock_sha256':hashlib.sha256((ROOT/'uv.lock').read_bytes()).hexdigest()},indent=2),encoding='utf-8')
        manifest=json.loads((notice.parent/'build-manifest.json').read_text(encoding='utf-8'))
        manifest['source_revision']=os.getenv('GITHUB_SHA','local')
        (notice.parent/'build-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        executable=notice.parent/('StudyDeskBackend.exe' if os.name=='nt' else 'StudyDeskBackend')
        run([executable,'--self-check'])
    if options.backend_only:return
    npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm')
    if not npm:raise SystemExit('Install npm on the build machine.')
    subprocess.run([npm,'ci'],cwd=ROOT/'desktop',check=True)
    command=[npm,'run','build']
    if sys.platform=='darwin':command+=['--','--bundles','app,dmg']
    elif sys.platform.startswith('linux'):command+=['--','--bundles','deb,appimage']
    subprocess.run(command,cwd=ROOT/'desktop',check=True)
    if sys.platform=='darwin':
        packaged=ROOT/'desktop/src-tauri/target/release/bundle/macos/Study Desk.app/Contents/Resources/backend/StudyDeskBackend'
        if not packaged.is_file():raise RuntimeError('macOS application is missing the bundled backend.')
        run([packaged,'--self-check'])
    artifacts=ROOT/'desktop/src-tauri/target/release/bundle'
    output=ROOT/'dist/installers';output.mkdir(parents=True,exist_ok=True)
    for source in artifacts.rglob('*'):
        if source.is_file() and (source.suffix in {'.exe','.msi','.dmg','.deb','.AppImage','.sig'} or source.name.endswith('.app.tar.gz')):
            name=source.name
            if '.app.tar.gz' in name:
                arch='aarch64' if platform.machine().lower() in {'arm64','aarch64'} else 'x64'
                name=f'Study-Desk_{version}_{arch}.app.tar.gz'+('.sig' if name.endswith('.sig') else '')
            if version in name:shutil.copy2(source,output/name)
    if not any(p.suffix in {'.exe','.msi','.dmg','.deb','.AppImage'} and version in p.name for p in output.iterdir()):
        raise RuntimeError('No installer for this release version was produced.')
    # Content-defined maps are separately signed and allow the next updater to
    # reuse unchanged bytes from its last verified package, even after offsets shift.
    sys.path.insert(0,str(ROOT))
    from update_blocks import make_map
    payloads=[p for p in output.iterdir() if p.suffix in {'.exe','.deb','.AppImage'} or p.name.endswith('.app.tar.gz')]
    for payload in payloads:
        blockmap=payload.with_name(payload.name+'.blocks.json')
        blockmap.write_text(json.dumps(make_map(payload,version),separators=(',',':')),encoding='utf-8')
        subprocess.run([npm,'exec','--','tauri','signer','sign','--app-version',version,str(blockmap)],cwd=ROOT/'desktop',check=True,stdout=subprocess.DEVNULL)
    lines=[hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name for p in output.iterdir() if p.is_file() and p.name!='SHA256SUMS.txt']
    (output/'SHA256SUMS.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Release artifacts:',output)

if __name__=='__main__':main()
