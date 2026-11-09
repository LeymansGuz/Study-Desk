"""Local workflow integrity: no model calls, no live user data."""
import hashlib,json,uuid
from datetime import date,timedelta
import pytest
import app,auth,db,curriculum,learning_store as store,retrieval
import document_replacement as replacement


@pytest.fixture
def document(client,monkeypatch):
    course=db.create_course(auth.OWNER_ID,'Replace '+uuid.uuid4().hex)
    target=retrieval.course_workspace(auth.OWNER_ID,course['id'])/'notes.md'
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b'Original course text')
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    db.sync_documents(auth.OWNER_ID,[dict(course_id=course['id'],filename=target.name,sha256=digest,size=target.stat().st_size,doc_type='syllabus',page_count=4)],prune=False)
    document=db.get_document_by_name(auth.OWNER_ID,course['id'],target.name)
    with db.connect() as connection:connection.execute('UPDATE documents SET syllabus_enabled=0 WHERE id=?',(document['id'],))
    def extract(path,user,cid,name,role):
        assert target.read_bytes()==b'Original course text'
        record=dict(course_id=cid,filename=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),size=path.stat().st_size,doc_type=role,page_count=2)
        return [],record,dict(course_id=cid,filename=path.name,pages=[],sha256=record['sha256'])
    monkeypatch.setattr(retrieval,'_extract_index_file',extract)
    def publish(user,chunks,manifests,**kwargs):kwargs['publish']('replacement-index',manifests)
    monkeypatch.setattr(retrieval,'_publish_chunks',publish)
    return course,document,target


def test_replacement_publishes_document_and_index_together(document):
    course,old,path=document
    result=replacement.replace(auth.OWNER_ID,course,path.name,b'Updated course text',old['sha256'],'syllabus')
    assert result['id']==old['id'] and result['doc_type']=='syllabus' and not result['syllabus_enabled']
    assert path.read_bytes()==b'Updated course text' and result['page_count']==2
    assert db.get_app_setting('index_collection:'+auth.OWNER_ID)=='replacement-index'
    assert not list(replacement.root().iterdir())


@pytest.mark.parametrize('stage',['extract','index','commit'])
def test_failed_replacement_retains_original_file_registry_and_index(document,monkeypatch,stage):
    course,old,path=document
    prior=db.get_app_setting('index_collection:'+auth.OWNER_ID)
    def fail(*a,**k):raise RuntimeError('Forced failure')
    monkeypatch.setattr({'extract':retrieval,'index':retrieval,'commit':db}[stage],{'extract':'_extract_index_file','index':'_publish_chunks','commit':'publish_index'}[stage],fail)
    with pytest.raises(RuntimeError):replacement.replace(auth.OWNER_ID,course,path.name,b'Updated text',old['sha256'],'syllabus')
    assert path.read_bytes()==b'Original course text'
    current=db.get_document(auth.OWNER_ID,old['id'])
    assert current['sha256']==old['sha256'] and current['size']==old['size']
    assert db.get_app_setting('index_collection:'+auth.OWNER_ID)==prior
    assert not list(replacement.root().iterdir())


def test_replacement_rejects_stale_decision_before_extraction(document,monkeypatch):
    course,old,path=document
    monkeypatch.setattr(retrieval,'_extract_index_file',lambda *a:pytest.fail('Stale decision must not extract'))
    with pytest.raises(Exception) as exc:replacement.replace(auth.OWNER_ID,course,path.name,b'Updated text','outdated','syllabus')
    assert exc.value.status_code==409 and path.read_bytes()==b'Original course text'


@pytest.mark.parametrize('committed',[False,True])
def test_restart_recovers_file_using_database_commit_marker(document,committed):
    course,old,path=document
    directory=replacement.root()/uuid.uuid4().hex;directory.mkdir(parents=True)
    (directory/'previous').write_bytes(path.read_bytes());path.write_bytes(b'New revision')
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    (directory/'journal.json').write_text(json.dumps(dict(user=auth.OWNER_ID,course=course['id'],filename=path.name,sha256=digest)),encoding='utf-8')
    if committed:
        with db.connect() as c:c.execute('UPDATE documents SET sha256=? WHERE id=?',(digest,old['id']))
    replacement.recover()
    assert path.read_bytes()==(b'New revision' if committed else b'Original course text')
    replacement.recover()  # recovery is idempotent
    assert not directory.exists()


def test_course_plan_inherits_daily_time_unless_explicit_override(client,monkeypatch):
    course=db.create_course(auth.OWNER_ID,'Plan '+uuid.uuid4().hex)['id']
    monkeypatch.setattr(curriculum,'scope_version',lambda *a:'plan-test')
    assert client.put('/study/plan',json={'minutes':45}).status_code==200
    body=dict(course_id=course,exam_date=(date.today()+timedelta(days=10)).isoformat(),topics=['Equilibrium'])
    assert client.post('/library/schedule',json=body).json()['minutes']==45
    client.put('/study/plan',json={'minutes':60})
    assert client.get('/library/schedule/'+course).json()['plan']['minutes']==60
    client.post('/library/schedule',json={**body,'minutes':20})
    client.put('/study/plan',json={'minutes':30})
    assert client.get('/library/schedule/'+course).json()['plan']['minutes']==20


def test_bookmarks_flag_replaced_sources_and_out_of_range_pages(client,document):
    course,old,path=document
    response=client.post('/library/annotations',json={'document_id':old['id'],'page':4,'text':'Personal note'})
    assert response.status_code==200
    with db.connect() as c:c.execute("UPDATE learning_objects SET payload=json_remove(payload,'$.source_sha') WHERE kind='annotation' AND id=?",(response.json()['id'],))
    replacement.replace(auth.OWNER_ID,course,path.name,b'Updated text',old['sha256'],'syllabus')
    note=client.get('/library/annotations?course_id='+course['id']).json()['items'][0]
    assert note['source_changed'] and not note['page_available'] and note['text']=='Personal note'


def test_progress_separates_first_attempt_from_eventual_success(client):
    before=db.study_dashboard(auth.OWNER_ID)
    db.save_study_record(auth.OWNER_ID,dict(id=uuid.uuid4().hex,kind='practice',question='Unique '+uuid.uuid4().hex,attempts=2,first_marks=0,latest_marks=1,max_marks=1,is_correct=True))
    after=db.study_dashboard(auth.OWNER_ID)
    assert after['correct']==before['correct']+1
    assert after['first_attempt_correct']==before['first_attempt_correct']


def send_batch(client,course,items):
    import time
    spec={'course_id':course['id'],'files':[{'name':name,'size':len(data),**meta} for name,data,meta in items]}
    response=client.post('/workspace/uploads',json=spec)
    assert response.status_code==201,response.text
    identifier=response.json()['id']
    for index,(name,data,meta) in enumerate(items):
        if meta.get('conflict')=='skip':continue
        response=client.put(f'/workspace/uploads/{identifier}/files/{index}?offset=0',content=data,headers={'X-Chunk-SHA256':hashlib.sha256(data).hexdigest()})
        assert response.status_code==200,response.text
    assert client.post(f'/workspace/uploads/{identifier}/complete').status_code==202
    for _ in range(300):
        value=client.get('/workspace/uploads/'+identifier).json()
        if value['status'] in {'complete','failed'}:return value
        time.sleep(.01)
    pytest.fail('Batch did not finish')


def test_reviewed_batch_keeps_success_when_another_file_fails(client,document,monkeypatch):
    course,old,path=document
    async def enqueue(job):db.update_index_job(job['id'],'done',progress=100)
    monkeypatch.setattr(app,'_enqueue_index_job',enqueue)
    monkeypatch.setattr(app,'corpus_documents',lambda *a,**k:[])
    result=send_batch(client,course,[('notes.md',b'Updated content',{'conflict':'replace','expected_sha':old['sha256'],'doc_type':'notes'}),('exercise.md',b'Exercise: explain this concept.',{'doc_type':'exercise'}),('bad.pdf',b'not a real PDF',{'doc_type':'notes'})])
    assert result['status']=='complete',result
    outcomes=result['result']['outcomes']
    assert [x['status'] for x in outcomes]==['ready','indexing','failed']
    assert db.get_document(auth.OWNER_ID,old['id'])['doc_type']=='syllabus'
    assert db.get_document_by_name(auth.OWNER_ID,course['id'],'exercise.md')['doc_type']=='exercise'
    assert db.get_document_by_name(auth.OWNER_ID,course['id'],'bad.pdf') is None


def test_keep_both_skip_and_identical_upload_are_idempotent(client,document,monkeypatch):
    course,old,path=document
    async def enqueue(job):db.update_index_job(job['id'],'done',progress=100)
    monkeypatch.setattr(app,'_enqueue_index_job',enqueue)
    monkeypatch.setattr(app,'corpus_documents',lambda *a,**k:[])
    items=[('notes.md',b'Alternative notes',{'conflict':'keep','doc_type':'exercise'})]
    first=send_batch(client,course,items)
    second=send_batch(client,course,items)
    assert first['result']['uploaded'][0]['id']==second['result']['uploaded'][0]['id']
    assert len(db.list_documents(auth.OWNER_ID,[course['id']]))==2
    same=send_batch(client,course,[('notes.md',path.read_bytes(),{'conflict':'replace','expected_sha':'outdated','doc_type':'notes'})])
    assert same['result']['outcomes'][0]['status']=='unchanged'
    skip=send_batch(client,course,[('notes.md',b'Unused text',{'conflict':'skip','doc_type':'notes'})])
    assert skip['result']['outcomes'][0]['status']=='skipped'
    assert path.read_bytes()==b'Original course text'


def test_review_grade_does_not_inflate_independent_mastery(client,monkeypatch):
    import asyncio
    from durable_learning import DurableGraph
    class Graph:
        async def ainvoke(self,*a,**k):
            return dict(user_id=auth.OWNER_ID,current_question='Review question',mode='practice',user_attempts=1,status='correct',exam_id='deliberate-review',messages=[])
    monkeypatch.setattr(store,'outcome',lambda *a,**k:pytest.fail('Repeated bank review must not increase independent mastery'))
    asyncio.run(DurableGraph(Graph()).ainvoke({}, {'configurable':{'thread_id':uuid.uuid4().hex}}))
