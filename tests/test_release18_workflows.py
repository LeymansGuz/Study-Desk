"""Native export boundaries and concise-card integrity; no paid calls."""
import uuid,time
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
import auth,db,learning_store as store
from desktop_downloads import allowed_path,install
from recall_cards import concise

@pytest.mark.parametrize('path',['/study/cards/export','/library/personal/export?course_id=abc','/workspace/documents/abc/download','/library/guide/course?download=true','/session/thread/export'])
def test_native_export_allowlist(path):assert allowed_path(path)

@pytest.mark.parametrize('path',['https://evil.test/export','//evil.test','/settings','/desktop/stop','/workspace/documents/abc/file','/study/cards/export?secret=key','/library/personal/export?course_id=a&course_id=b','/session/a%2Fb/export','/study/cards/export#other'])
def test_native_export_rejects_arbitrary_paths(path):assert not allowed_path(path)

def test_native_save_queue_cancel_errors_and_private_command(monkeypatch):
    monkeypatch.setenv('STUDY_DESKTOP_SECRET','a'*64)
    application=FastAPI();install(application)
    with TestClient(application) as c:
        assert c.get('/desktop/files/command').status_code==403
        assert c.post('/desktop/files/save',json={'route':'https://evil.test'}).status_code==422
        job=c.post('/desktop/files/save',json={'route':'/study/cards/export'}).json()['id']
        assert c.post('/desktop/files/save',json={'route':'/study/cards/export'}).status_code==409
        headers={'X-Study-Desktop':'a'*64}
        command=c.get('/desktop/files/command',headers=headers).json();assert command['id']==job
        assert c.get('/desktop/files/command',headers=headers).json()=={}
        assert c.post('/desktop/files/result',json={'id':job,'state':'cancelled','message':'Cancelled'}).status_code==403
        c.post('/desktop/files/result',headers=headers,json={'id':job,'state':'cancelled','message':'Cancelled'})
        assert c.get('/desktop/files/status/'+job).json()=={'state':'cancelled','message':'Cancelled'}
        secret='correct horse battery staple'
        job=c.post('/desktop/files/save',json={'route':'/library/backups/encrypted','passphrase':secret}).json()['id']
        assert secret not in c.get('/desktop/files/status/'+job).text
        assert c.get('/desktop/files/command',headers=headers).json()['passphrase']==secret
        assert 'passphrase' not in application.state.native_export_jobs[job]

def test_empty_exports_return_readable_errors(client):
    course=db.create_course(auth.OWNER_ID,'Empty export '+uuid.uuid4().hex)['id']
    for path in ['/library/course/'+course+'/export','/library/personal/export?course_id='+course]:
        result=client.get(path);assert result.status_code==409 and result.json()['detail']

def test_short_cards_save_deduplicate_and_export_without_full_questions(client):
    body={'cards':[{'front':'What is diffusion?','back':'Net particle movement down a concentration gradient.'}]}
    first=client.post('/study/cards/save',json=body);assert first.status_code==200,first.text
    assert client.post('/study/cards/save',json=body).json()['saved']==0
    source=db.save_study_record(auth.OWNER_ID,{'id':uuid.uuid4().hex,'question':'long question '*40,'answer_key':'lengthy answer '*60,'is_correct':False})
    result=client.get('/study/cards/export');assert result.status_code==200
    assert 'What is diffusion?' in result.text and 'long question' not in result.text
    assert db.get_study_record(auth.OWNER_ID,source['id'])
    invalid=client.post('/study/cards/save',json={'cards':[{'front':'word '*30,'back':'Answer'}]});assert invalid.status_code==422

def test_edited_or_expired_proposal_cannot_claim_verification(client,monkeypatch):
    import curriculum
    monkeypatch.setattr(curriculum,'scope_version',lambda *a:'now')
    identifier=uuid.uuid4().hex;cards=[{'front':'Prompt?','back':'Answer.'}]
    store.put('card_proposal',identifier,auth.OWNER_ID,{'cards':cards,'created':time.time(),'version':'now','course_ids':[]})
    assert client.post('/study/cards/save',json={'proposal_id':identifier,'cards':[{'front':'Different?','back':'Answer.'}]}).status_code==422
    assert client.post('/study/cards/save',json={'proposal_id':'not-owned','cards':cards}).status_code==409
    value=store.get('card_proposal',identifier,auth.OWNER_ID);value['created']=0;store.put('card_proposal',identifier,auth.OWNER_ID,value)
    assert client.post('/study/cards/save',json={'proposal_id':identifier,'cards':cards}).status_code==409

def test_saved_session_preview_hides_attachment_boilerplate():
    text='--- Attached question material (1 attachment)\n---\n### Screenshot-2026.png\nFind $x>0$ when the account doubles.'
    assert store.session_preview(text)=='Find x>0 when the account doubles.'

def test_card_size_rule_never_truncates_conditions():
    assert concise('When is the formula valid?','For positive real inputs only.')
    assert not concise('word '*26,'Answer')
    assert not concise('Prompt?','**Answer:** ')

def test_revision_sheet_transfer_preserves_text_without_verification(client):
    course=db.create_course(auth.OWNER_ID,'Sheet transfer '+uuid.uuid4().hex)['id']
    key=uuid.uuid4().hex
    store.put('revision_sheet',key,auth.OWNER_ID,{'id':key,'topic':'Conditions','course_ids':[course],'markdown':'Use $x>0$.','notes':'Check the domain.'})
    exported=client.get('/library/personal/export',params={'course_id':course})
    assert exported.status_code==200
    bundle=exported.json();bundle['course_id']=course
    imported=client.post('/library/personal/import',json=bundle)
    assert imported.status_code==200,imported.text
    copied=next(v for v in store.listing('revision_sheet',auth.OWNER_ID) if v.get('imported') and v.get('topic')=='Conditions')
    assert copied['markdown']=='Use $x>0$.' and copied['notes']=='Check the domain.'
    assert not copied['checked_markdown'] and copied['edited']

def test_checked_card_proposal_requires_independent_review_and_current_source(client,monkeypatch):
    import curriculum,tools,recall_cards
    monkeypatch.setattr(curriculum,'scope_version',lambda *a:'current')
    question='What is diffusion?'
    course=uuid.uuid4().hex;session=uuid.uuid4().hex
    store.put('tutor',session,auth.OWNER_ID,{'status':'revealed','course_ids':[course]})
    record=db.save_study_record(auth.OWNER_ID,{'id':uuid.uuid4().hex,'ref_id':session,'question':question,'answer_key':'Down a concentration gradient.','is_correct':False})
    with db.connect() as c:card=c.execute('SELECT id FROM flashcards WHERE record_id=?',(record['id'],)).fetchone()['id']
    original={'current_question':question,'solution':'Net particle movement down a concentration gradient.','course_ids':[course]}
    monkeypatch.setattr(store,'bank_items',lambda *a:[original])
    calls=[];review_pass=[False]
    async def invoke(context,temperature,schema):
        calls.append(schema)
        if schema is recall_cards.Draft:return schema(cards=[{'front':question,'back':original['solution']}])
        return schema(passed=review_pass[0])
    monkeypatch.setattr(tools,'_invoke_json',invoke)
    before=len(store.listing('card_proposal',auth.OWNER_ID))
    rejected=client.post('/study/cards/propose',json={'card_id':card})
    assert rejected.status_code==422,rejected.text
    assert len(store.listing('card_proposal',auth.OWNER_ID))==before
    review_pass[0]=True
    result=client.post('/study/cards/propose',json={'card_id':card});assert result.status_code==200,result.text
    proposal=result.json();assert calls==[recall_cards.Draft,recall_cards.Review]*2
    monkeypatch.setattr(store,'is_quarantined',lambda *a:True)
    assert client.post('/study/cards/save',json={'proposal_id':proposal['id'],'cards':proposal['cards']}).status_code==409
    monkeypatch.setattr(store,'is_quarantined',lambda *a:False)
    assert client.post('/study/cards/save',json={'proposal_id':proposal['id'],'cards':proposal['cards']}).status_code==200
