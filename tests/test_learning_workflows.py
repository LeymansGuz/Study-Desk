"""Offline integration checks for staged generation and bank-only exams."""
import asyncio
import uuid
import pytest
import app, auth, curriculum, db, graph, learning_store as store
from tools import QuestionDraft, TutorError


@pytest.fixture
def course(client, monkeypatch):
    identifier=client.post('/workspace/courses',json={'name':'Flow '+uuid.uuid4().hex[:8]}).json()['id']
    monkeypatch.setattr(curriculum,'scope_version',lambda *a,**k:'flow-version')
    monkeypatch.setattr(graph,'plan_context',lambda *a,**k:{'plans':[{'sources':[],'skill_id':'flow','topic':'Equations'}], 'overview':'Course evidence','scope_key':'flow','recent_questions':[]})
    async def decide(action,**kwargs):
        return {'allow':action not in {'reveal_answer','access_solution_key'},'engine':'opa','action':action,'reason':'Offline policy','decided_at':db.utc_now()}
    monkeypatch.setattr(graph,'decide',decide)
    monkeypatch.setattr(app,'decide',decide)
    return identifier


def complete(thread):
    asyncio.run(app.graph.aupdate_state(app._config(thread),{'status':'correct'}))
    saved=store.get('tutor',thread,auth.OWNER_ID)
    saved['status']='correct'
    store.put('tutor',thread,auth.OWNER_ID,saved)


def test_mastery_requires_specific_topic_and_type(client,course):
    for topic in ['  ','Any syllabus topic','Whole syllabus review']:
        assert client.post('/ask/path',json={'topic':topic,'course_ids':[course],'question_type':'calculation'}).status_code==422
    assert client.post('/ask/path',json={'topic':'Equations','course_ids':[course]}).status_code==422


def test_mastery_generates_one_selected_type_at_a_time_and_rolls_back(client,course,monkeypatch):
    calls=[]
    async def draft(topic,sources,difficulty,types,**kwargs):
        calls.append((difficulty,types))
        return QuestionDraft(question=f'Solve the equation $x+{len(calls)}=5$ for real $x$.',question_type=types[0],canonical_answer='4',solution='Subtract the constant from five.',formula_focus='Equations')
    monkeypatch.setattr(graph,'draft_question',draft)
    r=client.post('/ask/path',json={'topic':'Equations','course_ids':[course],'question_type':'calculation','doc_types':['notes']})
    assert r.status_code==200,r.text
    data=r.json();identifier=data['id']
    assert calls==[('easy',['calculation'])]
    assert len(store.get('path',identifier,auth.OWNER_ID)['threads'])==1
    assert client.post(f'/ask/path/{identifier}/next').status_code==409
    complete(data['question']['thread_id'])
    assert client.get('/ask/path/'+identifier).json()['can_advance']
    async def failure(*a,**k):raise TutorError('Synthetic stage failure')
    monkeypatch.setattr(graph,'draft_question',failure)
    before=store.get('path',identifier,auth.OWNER_ID)
    with db.connect() as c:count=c.execute("SELECT COUNT(*) FROM learning_objects WHERE kind='tutor'").fetchone()[0]
    assert client.post(f'/ask/path/{identifier}/next').status_code==422
    assert store.get('path',identifier,auth.OWNER_ID)==before
    with db.connect() as c:assert c.execute("SELECT COUNT(*) FROM learning_objects WHERE kind='tutor'").fetchone()[0]==count
    monkeypatch.setattr(graph,'draft_question',draft)
    r=client.post(f'/ask/path/{identifier}/next')
    assert r.status_code==200,r.text
    assert calls[-1]==('medium',['calculation']) and len(calls)==2
    complete(r.json()['question']['thread_id'])
    r=client.post(f'/ask/path/{identifier}/next')
    assert r.status_code==200,r.text
    assert calls[-1]==('insane',['calculation']) and len(calls)==3


def add_bank(course,question,**updates):
    payload={'mode':'practice','current_question':question,'question_type':'short_answer','difficulty':'medium',
        'canonical_answer':'2','solution':'Subtract one and divide by two.','sources':[{'ref':'S1','course_id':course,'chunk_id':'test','source_file':'Notes.md','page':1,'text':'Solve linear equations.','excerpt':'Solve linear equations.','source_title':'Notes','kind':'note','score':1.0,'doc_type':'notes'}],
        'course_ids':[course],'assessment_version':__import__('assessment_level').POLICY_VERSION,'topic':'Equations','verification':{'solver_passed':True,'opa_passed':True}}
    payload.update(updates)
    return store.bank_add(auth.OWNER_ID,payload,'flow-version')


def test_bank_exam_never_calls_generation_and_hides_solutions(client,course,monkeypatch):
    add_bank(course,'Solve $2x+1=5$ for real $x$.')
    add_bank(course,'Solve $3x-2=4$ for real $x$.')
    async def forbidden(*a,**k):raise AssertionError('Bank exams must not generate')
    monkeypatch.setattr(graph,'draft_question',forbidden)
    r=client.post('/bank-exams',json={'course_id':course,'count':2,'question_type':'short_answer'})
    assert r.status_code==200,r.text
    data=r.json();identifier=data['id']
    assert 'solution' not in data['question'] and 'canonical_answer' not in r.text
    assert client.post(f'/bank-exams/{identifier}/next').status_code==409
    complete(data['question']['thread_id'])
    r=client.post(f'/bank-exams/{identifier}/next')
    assert r.status_code==200,r.text
    assert r.json()['index']==1
    assert r.json()['question']['question']!=data['question']['question']
    assert client.get('/bank-exams/'+identifier).status_code==200
    complete(r.json()['question']['thread_id'])
    assert client.get('/bank-exams/'+identifier).json()['completed']


def test_bank_filters_quarantine_and_stale_evidence(client,course):
    identifier=add_bank(course,'Find the real solution to $7x=14$.')
    assert store.bank_counts(auth.OWNER_ID,course)['total']==1
    assert client.post('/bank-exams',json={'course_id':course,'count':2}).status_code==409
    assert client.post('/bank-exams',json={'course_id':course,'count':1,'difficulty':'insane'}).status_code==409
    value=store.get('bank',identifier,auth.OWNER_ID);value['evidence_versions']={course:'old'}
    store.put('bank',identifier,auth.OWNER_ID,value)
    assert store.bank_counts(auth.OWNER_ID,course)['total']==0
    assert client.post('/bank-exams',json={'course_id':course,'count':1}).status_code==409
    value['evidence_versions']={course:'flow-version'};value['quarantined']=True
    store.put('bank',identifier,auth.OWNER_ID,value)
    assert client.post('/bank-exams',json={'course_id':course,'count':1}).status_code==409


def test_prepared_children_do_not_expire_live_path(client):
    parent=uuid.uuid4().hex
    store.put('path',parent,auth.OWNER_ID,{'topic':'Retention','threads':[]})
    for _ in range(12):
        store.put('tutor',uuid.uuid4().hex,auth.OWNER_ID,{'prepared':True,'path_id':parent})
    assert store.get('path',parent,auth.OWNER_ID)
    with db.connect() as c:assert c.execute("SELECT COUNT(*) FROM learning_objects WHERE kind='tutor' AND json_extract(payload,'$.path_id')=?",(parent,)).fetchone()[0]==12


def test_syllabus_is_explicit_prompt_context():
    context=curriculum.overview({'sections':[{'course_id':'c','source_file':'Syllabus.pdf','doc_type':'syllabus','keywords':['equations'],'sources':[{'text':'Only covered linear equations are examinable.'}]}]})
    assert 'Official syllabus text defines the allowed scope' in context
    assert 'Only covered linear equations are examinable.' in context


def test_cached_usage_is_reported(client):
    import observability
    observability.provider_call(auth.OWNER_ID,'offline-test','fixture',100,10,60,1)
    data=client.get('/local/statistics').json()
    assert data['period']['cached_input_tokens']>=60


def test_bank_exam_start_is_idempotent(client,course):
    add_bank(course,'Solve $5x=10$ for real $x$.')
    headers={'Idempotency-Key':'bank-exam-start-once'}
    body={'course_id':course,'count':1,'question_type':'short_answer'}
    first=client.post('/bank-exams',json=body,headers=headers)
    assert first.status_code==200,first.text
    second=client.post('/bank-exams',json=body,headers=headers)
    assert second.status_code==200,second.text
    assert second.headers.get('Idempotent-Replayed')=='true'
    assert second.json()['id']==first.json()['id']
