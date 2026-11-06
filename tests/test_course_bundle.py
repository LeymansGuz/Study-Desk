import hashlib,io,json,uuid,zipfile
import pytest
import app,auth,db,learning_store as store,course_bundle

def archive(content,checksum=None):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        z.writestr('documents/notes.md',content)
        z.writestr(course_bundle.MANIFEST,json.dumps({'format':'study-desk-course-v1','files':[{'filename':'notes.md','sha256':checksum or hashlib.sha256(content).hexdigest(),'doc_type':'syllabus','syllabus_enabled':False}],'sheets':[]}))
    return out.getvalue()

def test_bundle_preserves_document_roles_and_scope_flags(client,monkeypatch):
    course=db.create_course(auth.OWNER_ID,'Bundle '+uuid.uuid4().hex)
    async def enqueue(job):pass
    monkeypatch.setattr(app,'_enqueue_index_job',enqueue)
    response=client.post('/workspace/courses/'+course['id']+'/import-zip',files={'file':('course.zip',archive(b'# Outcomes\n\nExplain diffusion and gradients.\n'),'application/zip')})
    assert response.status_code==200,response.text
    doc=db.list_documents(auth.OWNER_ID,[course['id']])[0]
    assert doc['doc_type']=='syllabus' and not doc['syllabus_enabled']
    downloaded=client.get('/library/course/'+course['id']+'/export')
    assert downloaded.status_code==200,downloaded.text
    with zipfile.ZipFile(io.BytesIO(downloaded.content)) as z:
        manifest=course_bundle.read_manifest(z)
        assert manifest['files']['notes.md']['doc_type']=='syllabus' and not manifest['files']['notes.md']['syllabus_enabled']

def test_bad_bundle_hash_leaves_no_documents(client):
    course=db.create_course(auth.OWNER_ID,'Bad bundle '+uuid.uuid4().hex)
    response=client.post('/workspace/courses/'+course['id']+'/import-zip',files={'file':('bad.zip',archive(b'# Notes\n\nSome original study material.','0'*64),'application/zip')})
    assert response.status_code==422 and not db.list_documents(auth.OWNER_ID,[course['id']])
    assert not list(app.course_workspace(auth.OWNER_ID,course['id']).glob('*.md'))

def test_bundle_enqueue_failure_rolls_back_registry_and_files(client,monkeypatch):
    course=db.create_course(auth.OWNER_ID,'Failed bundle '+uuid.uuid4().hex)
    async def enqueue(job):raise RuntimeError('simulated queue failure')
    monkeypatch.setattr(app,'_enqueue_index_job',enqueue)
    result=client.post('/workspace/courses/'+course['id']+'/import-zip',files={'file':('course.zip',archive(b'# Study notes\n\nOriginal explanations for the lesson.'),'application/zip')})
    assert result.status_code>=400 and not db.list_documents(auth.OWNER_ID,[course['id']])
    with db.connect() as c:assert c.execute('SELECT COUNT(*) FROM index_jobs WHERE course_id=?',(course['id'],)).fetchone()[0]==0

def test_bundle_rejects_forged_checked_sheet_fields():
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w') as z:z.writestr(course_bundle.MANIFEST,json.dumps({'format':'study-desk-course-v1','files':[],'sheets':[{'topic':'Fake','markdown':'Text','verified':True}]}))
    with zipfile.ZipFile(io.BytesIO(data.getvalue())) as z:
        with pytest.raises(Exception):course_bundle.read_manifest(z)
