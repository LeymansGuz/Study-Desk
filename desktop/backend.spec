# Runtime source and public assets only. Never collect the repository directory,
# .env, audit/, data/, credentials, study documents or developer tool caches.
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

root=Path(SPECPATH).parent
datas=[(str(root/'static'),'static'),(str(root/'scripts/check-math.cjs'),'scripts'),
       (str(root/'policy/tutor.rego'),'policy'),(str(root/'policy/local_authz.rego'),'policy'),
       (str(root/'LICENSE'),'.')]
datas += [(str(root/name),'.') for name in ['PRIVACY.md','TERMS.md','THIRD-PARTY-NOTICES.md']]
binaries=[]
hidden=[p.stem for p in root.glob('*.py') if not p.stem.startswith(('test_','evaluate_')) and p.stem not in {'run','service_host','local_app','desktop_backend'}]
for package in ['rapidocr_onnxruntime','extractous','keyring.backends']:
    data,native,modules=collect_all(package)
    datas+=data;binaries+=native;hidden+=modules
for package in ['langchain_core','langchain_openai','langgraph','langsmith','fsrs','keyring','onnxruntime','tokenizers']:
    datas+=copy_metadata(package,recursive=True)
for package in ['langgraph','langchain_openai','uvicorn','onnxruntime']:
    hidden+=collect_submodules(package,filter=lambda name:'.tests' not in name)
import os
native=Path(os.environ['STUDY_BUILD_BIN'])
binaries += [(str(native/('node.exe' if os.name=='nt' else 'node')),'bin'),
          (str(native/('opa.exe' if os.name=='nt' else 'opa')),'bin')]
a=Analysis([str(root/'desktop_backend.py')],pathex=[str(root)],binaries=binaries,datas=datas,
    hiddenimports=hidden,hookspath=[],runtime_hooks=[],excludes=['pytest','tkinter','IPython','matplotlib'],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='StudyDeskBackend',debug=False,strip=False,upx=False,console=True)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='StudyDeskBackend')
