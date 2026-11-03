import asyncio
import uuid
import pytest
import app
import db
import auth

def test_local_owner_without_account_or_hosted_routes(client):
    assert client.get('/').status_code==200
    assert client.get('/local/profile').json()['is_admin'] is True
    assert not client.cookies
    for route in ['/login','/auth/me','/auth/register','/admin','/groups/rooms','/notifications','/feedback']:
        assert client.get(route).status_code in {404,405},route
    with db.connect() as c:
        tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert not tables & {'auth_sessions','feedback','notifications','invite_codes','group_rooms'}

def test_remote_and_cross_origin_requests_are_denied(client):
    assert client.get('/',headers={'Host':'evil.example'}).status_code==403
    assert client.post('/workspace/courses',headers={'Origin':'https://evil.example'},json={'name':'bad'}).status_code==403
    assert client.post('/workspace/courses',headers={'Sec-Fetch-Site':'cross-site'},json={'name':'bad'}).status_code==403
    from fastapi.testclient import TestClient
    with TestClient(app.app,base_url='http://localhost',client=('192.168.1.25',1234)) as remote:
        assert remote.get('/').status_code==403

def test_course_settings_and_statistics(client):
    course=client.post('/workspace/courses',json={'name':'Local '+uuid.uuid4().hex[:8]})
    assert course.status_code==200,course.text
    identifier=course.json()['id']
    response=client.put('/workspace/courses/'+identifier+'/scope',json={'scope_notes':'Use only documented methods.'})
    assert response.status_code==200,response.text
    assert response.json()['scope_notes']=='Use only documented methods.'
    response=client.put('/settings',json={'theme':'dark','attempts_before_reveal':3})
    assert response.status_code==200,response.text
    assert client.get('/settings').json()['theme']=='dark'
    assert client.get('/local/statistics').status_code==200
    assert client.get('/progress').status_code==200

def test_document_saved_and_syllabus_toggle(client,monkeypatch):
    monkeypatch.setattr(app,'corpus_documents',lambda *a,**k:[])
    monkeypatch.setattr(app,'collection_count',lambda *a,**k:0)
    def index(job_id):
        db.update_index_job(job_id,status='done',message='Offline indexing fixture')
    monkeypatch.setattr(app,'_process_index_job',index)
    identifier=client.post('/workspace/courses',json={'name':'Documents '+uuid.uuid4().hex[:8]}).json()['id']
    response=client.post('/workspace/files',data={'course_id':identifier,'doc_type':'notes'},files=[('files',('notes.txt',b'Local course notes: use linear equations to find the unknown value.','text/plain'))])
    assert response.status_code==200,response.text
    rows=client.get('/workspace/files?course_id='+identifier).json()['files']
    assert len(rows)==1
    document=rows[0]['id']
    assert client.put('/workspace/documents/'+document+'/syllabus',json={'enabled':False}).status_code==200
    assert client.get('/workspace/files?course_id='+identifier).json()['files'][0]['syllabus_enabled'] is False
    assert client.get('/workspace/documents/'+document+'/download').content.startswith(b'Local course')
    assert client.get('/workspace/health').status_code==200
    assert client.get('/workspace/snapshot').status_code==200

def test_generation_and_resume_use_local_identity(client,monkeypatch):
    import graph
    import study_extensions
    from tools import QuestionDraft
    monkeypatch.setattr(graph,'plan_context',lambda *a,**k:{'plans':[{'sources':[],'skill_id':'local','topic':'Linear equations'}],'scope_key':'','overview':'Local fixture','recent_questions':[]})
    async def draft(*a,**k):
        return QuestionDraft(question='Solve the equation $2x+1=5$ for the real number $x$.',canonical_answer='2',solution='Subtract one from each side, then divide by two. This gives x=2.',formula_focus='Linear equations')
    async def decide(action,**kwargs):return {'allow':action not in {'reveal_answer','access_solution_key'},'action':action,'reason':'Offline policy fixture','engine':'opa','decided_at':db.utc_now()}
    monkeypatch.setattr(graph,'draft_question',draft)
    monkeypatch.setattr(graph,'decide',decide)
    monkeypatch.setattr(app,'decide',decide)
    identifier=client.post('/workspace/courses',json={'name':'Algebra '+uuid.uuid4().hex[:8]}).json()['id']
    response=client.post('/ask',json={'topic':'Linear equations','difficulty':'medium','question_types':['short_answer'],'course_ids':[identifier],'figure_mode':'none'})
    assert response.status_code==200,response.text
    thread=response.json()['thread_id']
    assert client.get('/session/'+thread).status_code==200
    assert client.get('/learning/dashboard').json()['sessions']
    assert db.get_user_by_id(auth.OWNER_ID)['is_admin']==1

def test_study_records_review_and_retention_have_only_local_dependencies(client):
    identifier='local-record-'+uuid.uuid4().hex
    db.save_study_record(auth.OWNER_ID,{'id':identifier,'kind':'practice','ref_id':'fixture',
        'question':'Find the real solution of 2x+1=5.','answer_key':'2',
        'solution':'Subtract one and divide by two.','is_correct':False,'attempts':1})
    result=client.get('/progress').json()
    assert any(row['id']==identifier for row in result['mistakes'])
    card=next(row for row in result['flashcards'] if row['record_id']==identifier)
    reviewed=client.post('/progress/flashcards/'+card['id']+'/review',json={'rating':'good'})
    assert reviewed.status_code==200,reviewed.text
    import retention
    retention.sweep()

def test_local_schema_has_no_credentials_and_backup_is_local(client):
    with db.connect() as c:
        columns={r['name'] for r in c.execute('PRAGMA table_info(users)')}
    assert not columns & {'password_hash','password_salt','otp_hash','otp_salt'}
    import backup
    assert backup.backup_directory()==db.DB_PATH.parent/'backups'
    result=client.post('/local/backup')
    assert result.status_code==200,result.text
    from pathlib import Path
    assert Path(result.json()['backup']).is_file()

def test_shipped_math_renderer_can_compile():
    from math_format import check
    asyncio.run(check('The result is $x^2+1$ and $\\frac{1}{2}$.'))

def test_launcher_keeps_storage_in_this_edition(monkeypatch):
    import local_app,os
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    for name in ['APP_DB_PATH','USERS_DIR','CHROMA_DIR']:
        monkeypatch.setenv(name,'S:/some-other-app/data')
    env=local_app.environment()
    assert Path(env['APP_DB_PATH'])==root/'data/app.db'
    assert Path(env['USERS_DIR'])==root/'data/users'
    assert Path(env['CHROMA_DIR'])==root/'data/chroma'
    assert env['OPA_URL']=='http://127.0.0.1:8182'
