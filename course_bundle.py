"""Portable original documents plus unverified personal study work."""
import hashlib,json,tempfile,zipfile,uuid
from pathlib import Path
from fastapi import HTTPException,Depends
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
import db,learning_store as store,curriculum

MANIFEST='study-desk-course.json'
TYPES={'notes','syllabus','past_paper','exercise','marking_scheme','exam_report'}

def read_manifest(archive):
    if MANIFEST not in archive.namelist():return None
    if archive.getinfo(MANIFEST).file_size>1500000:raise HTTPException(413,'Course manifest exceeds 1.5 MB.')
    try:
        value=json.loads(archive.read(MANIFEST))
        if value.get('format')!='study-desk-course-v1':raise ValueError()
        files=value['files']
        if not isinstance(files,list) or len(files)>500:raise ValueError()
        names=set()
        for row in files:
            if not isinstance(row,dict) or not isinstance(row.get('filename'),str) or len(row['filename'])>255 or row['filename'] in names or row.get('doc_type') not in TYPES or type(row.get('syllabus_enabled')) is not bool:raise ValueError()
            names.add(row['filename'])
            if not __import__('re').fullmatch('[a-f0-9]{64}',str(row.get('sha256',''))):raise ValueError()
        from study_library import PersonalSheet
        sheets=[PersonalSheet.model_validate(r).model_dump() for r in value.get('sheets',[])]
        if len(sheets)>20:raise ValueError()
        return {**value,'files':{r['filename']:r for r in files},'sheets':sheets}
    except (ValueError,TypeError,KeyError,AttributeError):raise HTTPException(422,'Invalid Study Desk course manifest. No documents were imported.')

def restore_personal(owner,course,manifest):
    """Imported sheets never retain trusted citations or verification status."""
    if not manifest:return []
    added=[]
    for row in manifest['sheets']:
        key=uuid.uuid4().hex
        store.put('revision_sheet',key,owner,{'id':key,**row,'course_ids':[course],'version':curriculum.scope_version(owner,[course]),'checked_markdown':'','sources':[],'revision':1,'edited':True,'imported':True,'explanation_id':''})
        added.append(key)
    return added

def install(app,services):
    @app.get('/library/course/{course_id}/export')
    async def export(course_id:str,user=Depends(services['require_user'])):
        import asyncio
        course=db.get_course(user['id'],course_id)
        if not course:raise HTTPException(404,'Choose an available course.')
        docs=db.list_documents(user['id'],[course_id])
        if not docs:raise HTTPException(409,'Upload documents before exporting a course bundle.')
        if len(docs)>services['MAX_BATCH_FILES'] or sum(d['size'] for d in docs)>services['MAX_BATCH_BYTES']:raise HTTPException(413,'This course exceeds the single-import batch limit. Use the original-files ZIP export and transfer smaller batches.')
        def create():
            fd,name=tempfile.mkstemp(prefix='study-course-',suffix='.zip');__import__('os').close(fd);target=Path(name)
            try:
                files=[]
                with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
                    for doc in docs:
                        path=services['_document_file_path'](user['id'],doc)
                        if not path.is_file():raise HTTPException(409,'An original document is missing. Restore it before exporting.')
                        archive.write(path,'documents/'+doc['filename'])
                        with path.open('rb') as stream:checksum=hashlib.file_digest(stream,'sha256').hexdigest()
                        files.append({'filename':doc['filename'],'sha256':checksum,'doc_type':doc['doc_type'],'syllabus_enabled':bool(doc.get('syllabus_enabled',True))})
                    sheets=[{k:r[k] for k in ['topic','markdown','notes']} for r in store.listing('revision_sheet',user['id'],20) if r.get('course_ids')==[course_id]]
                    archive.writestr(MANIFEST,json.dumps({'format':'study-desk-course-v1','name':course['name'],'files':files,'sheets':sheets},ensure_ascii=False))
                return target
            except BaseException:target.unlink(missing_ok=True);raise
        async with services['WORKSPACE_LOCK']:target=await asyncio.to_thread(create)
        return FileResponse(target,filename='study-desk-course.zip',media_type='application/zip',background=BackgroundTask(target.unlink,missing_ok=True))
