from explanations import CHECK_VERSION
import asyncio,json,uuid
from datetime import date,timedelta
import pytest
import auth,db,learning_store as store,study_companion as study

@pytest.fixture
def explanation(client,monkeypatch):
    import curriculum
    course=db.create_course(auth.OWNER_ID,'Companion '+uuid.uuid4().hex[:8])
    monkeypatch.setattr(curriculum,'scope_version',lambda *a:'current-version')
    item={'id':uuid.uuid4().hex,'topic':'Diffusion','check_version':CHECK_VERSION,'depth':'brief','course_ids':[course['id']],'version':'current-version','markdown':'## Core Concept\n\nDiffusion moves particles down their concentration gradient. [S1]','sources':[{'ref':'S1','file':'notes.pdf','course_id':course['id'],'page':1}]}
    store.put('explain',item['id'],auth.OWNER_ID,item)
    return item

def test_sheet_reuses_checked_content_and_edit_conflicts_do_not_destroy_text(client,explanation):
    first=client.post('/study/sheets/from/'+explanation['id']);assert first.status_code==200,first.text
    item=first.json();assert item['markdown']==explanation['markdown'] and not item['edited']
    changed={**{'revision':1,'markdown':item['markdown']+'\nMy own draft.','notes':'Remember the gradient.'}}
    saved=client.put('/study/sheets/'+item['id'],json=changed);assert saved.status_code==200 and saved.json()['edited']
    assert client.put('/study/sheets/'+item['id'],json=changed).status_code==409
    assert client.post('/study/sheets/from/'+explanation['id']).json()['notes']=='Remember the gradient.'
    assert 'not been independently checked' in client.get('/study/sheets/'+item['id']+'/export').text
    assert client.get('/study/search?q=gradient').json()['items']
    assert client.get('/study/sheets/not-owned').status_code==404
    assert client.delete('/study/sheets/'+item['id']).status_code==200

def test_stale_course_evidence_blocks_new_recall_and_marks_sheets_historical(client,explanation,monkeypatch):
    import curriculum
    item=client.post('/study/sheets/from/'+explanation['id']).json()
    monkeypatch.setattr(curriculum,'scope_version',lambda *a:'changed')
    assert client.get('/study/sheets/'+item['id']).json()['historical']
    assert client.post('/study/sheets/from/'+explanation['id']).status_code==409
    assert client.post('/study/recall',json={'explanation_id':explanation['id'],'answer':'My explanation about diffusion.'}).status_code==409

def test_recall_independent_review_can_withhold_feedback(monkeypatch):
    async def invoke(prompt,temperature,schema):
        if schema is study.RecallFeedback:return schema(verdict='understood',correct=['Correct description.'],improve=[],next_step='Practise this concept next.')
        return schema(grounded=True,accurate=False,fair=True,reason='Wrong correction')
    monkeypatch.setattr(study.tools,'_invoke_json',invoke)
    with pytest.raises(study.StageFailure,match='could not be verified'):
        asyncio.run(study.assess('My explanation',{'markdown':'The checked explanation.'},'Source evidence'))

def test_daily_plan_is_local_bounded_and_validated(client,explanation):
    tomorrow=(date.today()+timedelta(days=1)).isoformat()
    assert client.put('/study/plan',json={'minutes':10,'exam_date':tomorrow}).status_code==200
    result=client.get('/study/today');assert result.status_code==200,result.text
    assert len(result.json()['items'])<=5 and result.json()['preferences']['minutes']==10 and result.json()['days_to_exam']==1
    assert client.put('/study/plan',json={'minutes':500}).status_code==422
    assert client.put('/study/plan',json={'minutes':10,'exam_date':(date.today()-timedelta(days=1)).isoformat()}).status_code==422

def test_recall_requires_ai_notice_and_rejects_free_connection(client):
    import compliance
    db.set_app_setting('data_use_acknowledgement','')
    try:assert client.post('/study/recall',json={}).status_code==428
    finally:db.set_app_setting('data_use_acknowledgement',compliance.VERSION)
    previous=db.get_app_setting('ai_connection_v1','{}')
    try:
        db.set_app_setting('ai_connection_v1',json.dumps({'provider':'openrouter','model':'fixture/free:free','base_url':'https://openrouter.ai/api/v1','free_only':True}))
        assert client.post('/study/recall',json={}).json()['code']=='free_model_scope'
    finally:db.set_app_setting('ai_connection_v1',previous)

def test_recall_success_is_saved_and_duplicate_request_replays(client,explanation,monkeypatch):
    explanation['recall_context']='[S1] Diffusion moves particles from a higher to a lower concentration.'
    store.put('explain',explanation['id'],auth.OWNER_ID,explanation)
    calls=[]
    async def invoke(prompt,temperature,schema):
        calls.append(schema)
        if schema is study.RecallFeedback:return schema(verdict='understood',correct=['You described the concentration gradient correctly.'],improve=[],next_step='Apply this idea to a new situation. [S1]')
        return schema(grounded=True,accurate=True,fair=True)
    monkeypatch.setattr(study.tools,'_invoke_json',invoke)
    body={'explanation_id':explanation['id'],'answer':'Particles spread down their concentration gradient.'};headers={'Idempotency-Key':uuid.uuid4().hex}
    first=client.post('/study/recall',json=body,headers=headers);assert first.status_code==200,first.text
    again=client.post('/study/recall',json=body,headers=headers)
    assert again.status_code==200 and len(calls)==2
    assert client.get('/study/recall/history/'+explanation['id']).json()['items'][0]['answer']==body['answer']
    assert store.get('recall',first.json()['id'],auth.OWNER_ID)['feedback']['verdict']=='understood'

def test_sheet_refresh_requires_consent_for_edits_and_preserves_personal_notes(client,explanation):
    item=client.post('/study/sheets/from/'+explanation['id']).json()
    changed=client.put('/study/sheets/'+item['id'],json={'revision':1,'markdown':'My edited sheet.','notes':'Keep this note.'}).json()
    explanation['markdown']+='\n\nA newly checked explanation.'
    store.put('explain',explanation['id'],auth.OWNER_ID,explanation)
    assert client.post('/study/sheets/from/'+explanation['id']).json()['refresh_available']
    assert client.get('/study/sheets/'+item['id']).json()['markdown']=='My edited sheet.'
    assert client.post('/study/sheets/from/'+explanation['id']+'?replace=true&revision=1').status_code==409
    refreshed=client.post('/study/sheets/from/'+explanation['id']+'?replace=true&revision='+str(changed['revision'])).json()
    assert refreshed['notes']=='Keep this note.' and not refreshed['edited']

def test_revision_sheet_retention_has_a_fixed_cap(client,explanation):
    import retention
    retention.initialize()
    for i in range(23):
        example={**explanation,'id':uuid.uuid4().hex,'topic':'Topic '+str(i)}
        store.put('explain',example['id'],auth.OWNER_ID,example)
        assert client.post('/study/sheets/from/'+example['id']).status_code==200
    assert len(client.get('/study/sheets').json()['items'])==20

def test_recall_rejects_invented_source_reference_before_review(monkeypatch):
    calls=[]
    async def invoke(prompt,temperature,schema):
        calls.append(schema)
        return study.RecallFeedback(verdict='needs_work',correct=[],improve=['A correction. [S404]'],next_step='Review the source.')
    monkeypatch.setattr(study.tools,'_invoke_json',invoke)
    with pytest.raises(study.StageFailure,match='valid source references'):asyncio.run(study.assess('My explanation',{'markdown':'Checked explanation'},'[S1] Course evidence'))
    assert len(calls)==1

def test_anki_export_converts_math_and_escapes_html():
    value=study.anki_field(r'Inline $x^2$ and $$x+1$$, price \$5 <script>')
    assert r'\(x^2\)' in value and r'\[x+1\]' in value and '$5' in value
    assert '<script>' not in value and '&lt;script&gt;' in value


def test_legacy_checks_do_not_authorize_new_recall(client,explanation):
    legacy=dict(explanation);legacy.pop('check_version')
    store.put('explain',legacy['id'],auth.OWNER_ID,legacy)
    result=client.get('/explain/'+legacy['id'])
    assert result.status_code==200 and result.json()['historical']
    assert client.post('/study/recall',json={'explanation_id':legacy['id'],'answer':'An otherwise complete explanation of diffusion.'}).status_code==409
    assert store.get('explain',legacy['id'],auth.OWNER_ID)['markdown']==legacy['markdown']
