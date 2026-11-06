import io,json,uuid
from datetime import date,timedelta
from pathlib import Path
import pytest
import auth,db,curriculum,learning_store as store,study_library as library,local_jobs,backup_tools

@pytest.fixture
def course(client,monkeypatch):
    course=db.create_course(auth.OWNER_ID,'Library '+uuid.uuid4().hex)
    monkeypatch.setattr(curriculum,'scope_version',lambda *a:'library-v1')
    monkeypatch.setattr(curriculum,'course_map',lambda *a:{'sections':[{'id':'topic-1','title':'Concentration gradients','source_file':'notes.pdf','pages':[1],'excluded':False},{'id':'topic-2','title':'Equilibrium','source_file':'notes.pdf','pages':[2],'excluded':False}]})
    return course

def test_schedule_rolls_over_and_reports_unrealistic_workload(client,course):
    value=client.post('/library/schedule',json={'course_id':course['id'],'exam_date':date.today().isoformat(),'minutes':5}).json()
    assert value['over_capacity'] and len(value['upcoming'])==2
    first=value['upcoming'][0]
    response=client.patch('/library/schedule/'+course['id'],json={'topic_id':first['id'],'done':True})
    assert response.status_code==200 and len(response.json()['upcoming'])==1
    plan=client.get('/library/schedule/'+course['id']).json()['plan']
    rolled=library.schedule_view(plan,date.today()+timedelta(days=1))
    assert rolled['exam_passed'] and rolled['upcoming'][0]['date']==(date.today()+timedelta(days=1)).isoformat()
    assert client.patch('/library/schedule/'+course['id'],json={'topic_id':'made-up','done':True}).status_code==404

def test_schedule_requires_valid_course_date_and_topics(client,course):
    assert client.post('/library/schedule',json={'course_id':'missing','exam_date':date.today().isoformat()}).status_code==404
    assert client.post('/library/schedule',json={'course_id':course['id'],'exam_date':(date.today()-timedelta(days=1)).isoformat()}).status_code==422
    assert client.post('/library/schedule',json={'course_id':course['id'],'exam_date':date.today().isoformat(),'topics':['x'*201]}).status_code==422

def test_adaptive_suggestions_do_not_create_uncovered_topics(client,course,monkeypatch):
    monkeypatch.setattr(store,'mastery',lambda *a:{'topic-1':{'score':.2,'attempts':5,'due_at':0},'topic-2':{'score':.95,'attempts':4,'successes':4,'independent_questions':4,'delayed_success':True,'due_at':0}})
    data=client.get('/library/recommend/'+course['id']).json()
    assert {r['topic'] for r in data['items']}=={'Concentration gradients','Equilibrium'}
    assert next(r for r in data['items'] if r['skill_id']=='topic-1')['difficulty']=='easy'
    assert next(r for r in data['items'] if r['skill_id']=='topic-2')['difficulty']=='hard'

def test_recommendations_do_not_treat_repeated_same_day_success_as_retention(client,course,monkeypatch):
    monkeypatch.setattr(store,'mastery',lambda *a:{'topic-1':{'score':.99,'attempts':20,'successes':20,'independent_questions':1,'delayed_success':False,'due_at':0}})
    data=client.get('/library/recommend/'+course['id']).json()
    assert next(r for r in data['items'] if r['skill_id']=='topic-1')['difficulty']=='medium'

def test_guide_excludes_personal_edits_and_stale_sources(client,course):
    cid=course['id'];key=uuid.uuid4().hex
    store.put('revision_sheet',key,auth.OWNER_ID,{'id':key,'topic':'Gradient','course_ids':[cid],'version':'library-v1','checked_markdown':'Checked source text. [S1]','markdown':'Wrong personal edit','sources':[{'ref':'S1','file':'notes.pdf','page':1}]})
    store.put('explain',key,auth.OWNER_ID,{'id':key,'topic':'Old text','course_ids':[cid],'version':'stale','markdown':'Old unsupported text','sources':[]})
    response=client.get('/library/guide/'+cid)
    assert response.status_code==200,response.text
    assert len(response.json()['sections'])==1 and response.json()['sections'][0]['markdown']=='Checked source text. [S1]'
    text=client.get('/library/guide/'+cid+'?download=true').text
    assert 'Wrong personal edit' not in text and 'Old unsupported text' not in text and 'notes.pdf' in text

def test_search_index_is_atomic_case_insensitive_and_invalidation_safe(client,course,monkeypatch):
    import retrieval
    doc=db.add_document(user_id=auth.OWNER_ID,course_id=course['id'],filename='notes.pdf',sha256='0'*64,size=10,page_count=2)
    monkeypatch.setattr(retrieval,'_get_collection',lambda *a:object())
    monkeypatch.setattr(retrieval,'_all_records',lambda *a:[('a','Net DIFFUSION follows concentration gradients.',{'source_file':'notes.pdf','page':2})])
    job={'id':uuid.uuid4().hex,'kind':'search_index','course_id':course['id'],'status':'running'}
    store.put('local_job',job['id'],auth.OWNER_ID,job)
    assert '1 chunks' in local_jobs.index_course(auth.OWNER_ID,job)
    result=client.get('/library/documents/search',params={'course_id':course['id'],'q':'diffusion concentration'})
    assert result.status_code==200,result.text
    assert result.json()['items'][0]['document']==doc['id']
    assert client.get('/library/documents/search',params={'course_id':course['id'],'q':'" OR * )'}).status_code in {200,422}
    monkeypatch.setattr(curriculum,'scope_version',lambda *a:'changed')
    assert client.get('/library/documents/search',params={'course_id':course['id'],'q':'diffusion'}).status_code==409

def test_index_failure_never_publishes_partial_results(client,course,monkeypatch):
    import retrieval
    db.add_document(user_id=auth.OWNER_ID,course_id=course['id'],filename='notes.pdf',sha256='0'*64,size=10,page_count=2)
    monkeypatch.setattr(retrieval,'_get_collection',lambda *a:object())
    def records(*a):
        yield 'a','Useful text',{'source_file':'notes.pdf','page':1}
        raise RuntimeError('broken extraction store')
    monkeypatch.setattr(retrieval,'_all_records',records)
    job={'id':uuid.uuid4().hex,'kind':'search_index','course_id':course['id'],'status':'running'};store.put('local_job',job['id'],auth.OWNER_ID,job)
    with pytest.raises(RuntimeError):local_jobs.index_course(auth.OWNER_ID,job)
    assert not db.get_app_setting('search_index:'+auth.OWNER_ID+':'+course['id'])
    with db.connect() as c:assert c.execute('SELECT COUNT(*) FROM library_search WHERE generation=?',(job['id'],)).fetchone()[0]==0

def test_page_notes_validate_ownership_pages_and_upsert(client,course):
    doc=db.add_document(user_id=auth.OWNER_ID,course_id=course['id'],filename='notes.pdf',sha256='0'*64,size=10,page_count=2)
    body={'document_id':doc['id'],'page':2,'text':'My note','label':'Review'}
    assert client.post('/library/annotations',json={**body,'page':3}).status_code==422
    first=client.post('/library/annotations',json=body).json()
    again=client.post('/library/annotations',json={**body,'text':'Updated'}).json()
    assert first['id']==again['id']
    assert client.get('/library/annotations',params={'course_id':course['id']}).json()['items'][0]['text']=='Updated'
    assert client.post('/library/annotations',json={**body,'document_id':'missing'}).status_code==404

def test_personal_import_cannot_forge_verification(client,course):
    response=client.post('/library/personal/import',json={'format':'study-desk-personal-v1','course_id':course['id'],'sheets':[{'topic':'Local notes','markdown':'Not verified.'}]})
    assert response.status_code==200,response.text
    result=next(x for x in store.listing('revision_sheet',auth.OWNER_ID,20) if x.get('topic')=='Local notes')
    assert result['imported'] and result['edited'] and not result['sources'] and not result['checked_markdown']
    assert 'Local notes' not in client.get('/library/guide/'+course['id']).text
    assert client.post('/library/personal/import',json={'format':'study-desk-personal-v1','course_id':course['id'],'sheets':[{'topic':'Attempt','markdown':'Text','verified':True}]}).status_code==422

@pytest.mark.parametrize('damage',['wrong_password','truncate','tamper'])
def test_encrypted_backup_rejects_bad_data_and_removes_partial_output(tmp_path,damage):
    source=tmp_path/'original';source.write_bytes(b'private data'*100000);encrypted=tmp_path/'encrypted';target=tmp_path/'restored'
    backup_tools.encrypt(source,encrypted,'long private passphrase')
    if damage=='truncate':encrypted.write_bytes(encrypted.read_bytes()[:-20])
    if damage=='tamper':
        data=bytearray(encrypted.read_bytes());data[80]^=1;encrypted.write_bytes(data)
    with pytest.raises(Exception):backup_tools.decrypt(encrypted,target,'wrong long passphrase' if damage=='wrong_password' else 'long private passphrase')
    assert not target.exists()

def test_encrypted_backup_multi_block_roundtrip(tmp_path):
    source=tmp_path/'original';source.write_bytes(b'private data'*100000);encrypted=tmp_path/'encrypted';target=tmp_path/'restored'
    backup_tools.encrypt(source,encrypted,'long private passphrase');backup_tools.decrypt(encrypted,target,'long private passphrase')
    assert source.read_bytes()==target.read_bytes() and b'private data' not in encrypted.read_bytes()

def test_jobs_deduplicate_and_restart_is_explicit(client,course):
    value=local_jobs.submit(auth.OWNER_ID,'search_index',course['id'])
    assert local_jobs.submit(auth.OWNER_ID,'search_index',course['id'])['id']==value['id']
    store.put('local_job',value['id'],auth.OWNER_ID,{**value,'status':'running'})
    local_jobs.initialize()
    assert store.get('local_job',value['id'],auth.OWNER_ID)['status']=='interrupted'
    assert client.post('/library/jobs/'+value['id']+'/cancel').status_code==409
    assert client.post('/library/jobs/'+value['id']+'/retry').status_code==200
    client.post('/library/jobs/'+value['id']+'/cancel')

def test_backup_schedule_defaults_off_and_requires_opt_in(client):
    assert client.put('/library/backups/plan',json={'interval':'monthly'}).status_code==422
    assert client.put('/library/backups/plan',json={'interval':'off'}).status_code==200
    assert client.get('/library/backups/plan').json()['interval']=='off'
    assert client.post('/library/backups/encrypted',json={'passphrase':'short'}).status_code==422

def test_scheduled_backup_runs_once_and_retries_a_full_queue(client,monkeypatch):
    from fastapi import HTTPException
    def full(*a):raise HTTPException(429,'Full queue')
    db.set_app_setting('scheduled_backup',json.dumps({'interval':'weekly','last_queued':0}))
    try:
        monkeypatch.setattr(local_jobs,'submit',full)
        assert backup_tools.queue_due() is False
        assert json.loads(db.get_app_setting('scheduled_backup'))['last_queued']==0
        calls=[];monkeypatch.setattr(local_jobs,'submit',lambda *a:calls.append(a))
        assert backup_tools.queue_due() is True and backup_tools.queue_due() is False
        assert len(calls)==1
    finally:db.set_app_setting('scheduled_backup',json.dumps({'interval':'off'}))

def test_checked_guide_survives_explanation_history_and_invalidates_old_version(client,course):
    data={'topic':'Diffusion','course_ids':[course['id']],'version':'library-v1','markdown':'Checked text. [S1]','sources':[{'ref':'S1','file':'notes.pdf','page':1}]}
    library.save_checked_section(auth.OWNER_ID,data)
    assert 'Checked text.' in client.get('/library/guide/'+course['id']).text
    library.save_checked_section(auth.OWNER_ID,{**data,'version':'new','topic':'New checked topic'})
    value=store.get('course_guide',course['id'],auth.OWNER_ID)
    assert len(value['sections'])==1 and value['sections'][0]['topic']=='New checked topic'

def test_checked_guide_rolls_back_with_failed_generation(client,course):
    import asyncio
    from generation_control import atomic_generation
    async def fail():
        library.save_checked_section(auth.OWNER_ID,{'topic':'Never published','course_ids':[course['id']],'version':'library-v1','markdown':'Text','sources':[]})
        raise ValueError('forced failure')
    with pytest.raises(ValueError):asyncio.run(atomic_generation(fail))
    assert store.get('course_guide',course['id'],auth.OWNER_ID) is None

def test_imported_cards_are_idempotent_and_removable(client):
    content=('Unique '+uuid.uuid4().hex+'\tPersonal answer\n').encode()
    first=client.post('/library/cards/import',files={'file':('cards.tsv',content,'text/tab-separated-values')})
    assert first.status_code==200,first.text
    before=len(client.get('/library/cards').json()['items'])
    assert client.post('/library/cards/import',files={'file':('cards.tsv',content,'text/tab-separated-values')}).status_code==200
    cards=client.get('/library/cards').json()['items'];assert len(cards)==before
    target=next(x for x in cards if x['front'] in content.decode())
    assert client.delete('/library/cards/'+target['id']).status_code==200
    assert client.delete('/library/cards/'+target['id']).status_code==404
