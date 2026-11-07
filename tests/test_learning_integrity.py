from explanations import CHECK_VERSION
import uuid,time
import auth,db,learning_store as store,study_library as library,curriculum

def test_same_question_on_multiple_days_is_not_three_independent_questions(client):
    skill=uuid.uuid4().hex
    for i in range(3):store.outcome(auth.OWNER_ID,'same'+str(i),skill,1,1,question_key='one-question')
    with db.connect() as c:c.execute('UPDATE learning_outcomes SET created=? WHERE skill=? AND event=?',(time.time()-90000,skill,'same0'))
    result=store.mastery(auth.OWNER_ID)[skill]
    assert result['delayed_success'] and result['independent_questions']==1

def test_crossing_midnight_does_not_establish_delayed_retention(client):
    skill=uuid.uuid4().hex
    for i in range(3):store.outcome(auth.OWNER_ID,'midnight'+str(i),skill,1,1,question_key='distinct-'+str(i))
    boundary=(int(time.time()//86400))*86400
    with db.connect() as c:
        c.execute('UPDATE learning_outcomes SET created=? WHERE skill=?',(boundary+60,skill))
        c.execute('UPDATE learning_outcomes SET created=? WHERE skill=? AND event=?',(boundary-60,skill,'midnight0'))
    assert not store.mastery(auth.OWNER_ID)[skill]['delayed_success']

def test_guide_preserves_unchanged_sections_and_rejects_changed_sources(client,monkeypatch):
    cid=db.create_course(auth.OWNER_ID,'Lineage '+uuid.uuid4().hex)['id']
    doc=db.add_document(user_id=auth.OWNER_ID,course_id=cid,filename='first.md',sha256='a'*64,size=20,page_count=1)
    payload={'topic':'First concept','check_version':CHECK_VERSION,'course_ids':[cid],'version':curriculum.scope_version(auth.OWNER_ID,[cid]),'markdown':'Checked concept. [S1]','sources':[{'ref':'S1','file':'first.md','page':1,'course_id':cid}]}
    library.save_checked_section(auth.OWNER_ID,payload)
    monkeypatch.setattr(curriculum,'course_map',lambda *a:{'sections':[]})
    db.add_document(user_id=auth.OWNER_ID,course_id=cid,filename='unrelated.md',sha256='b'*64,size=20,page_count=1)
    assert client.get('/library/guide/'+cid).json()['sections'][0]['topic']=='First concept'
    with db.connect() as c:c.execute('UPDATE documents SET sha256=? WHERE id=?',('c'*64,doc['id']))
    assert not client.get('/library/guide/'+cid).json()['sections']

def test_mistake_context_returns_no_private_answer(client):
    cid=db.create_course(auth.OWNER_ID,'Review '+uuid.uuid4().hex)['id'];thread=uuid.uuid4().hex;record=uuid.uuid4().hex
    store.put('tutor',thread,auth.OWNER_ID,{'topic':'Diffusion','course_ids':[cid],'current_question':'Explain the gradient.','canonical_answer':'Private key','status':'awaiting_answer'})
    db.save_study_record(auth.OWNER_ID,{'id':record,'ref_id':thread,'question':'Explain the gradient.','is_correct':False,'attempts':1})
    response=client.get('/library/review-context/'+record)
    assert response.status_code==200 and response.json()=={'topic':'Diffusion','course_id':cid}
    assert 'Private key' not in response.text

def test_course_purge_removes_derived_search_text_notes_and_guide(client):
    cid=db.create_course(auth.OWNER_ID,'Purge '+uuid.uuid4().hex)['id']
    store.put('annotation','purge-note',auth.OWNER_ID,{'course_id':cid,'text':'Private note'})
    store.put('course_guide',cid,auth.OWNER_ID,{'course_id':cid,'sections':[]})
    with db.connect() as c:c.execute('INSERT INTO library_search VALUES(?,?,?,?,?,?)',(auth.OWNER_ID,cid,'generation','document',1,'Private source text'))
    library.purge_course(auth.OWNER_ID,cid)
    assert store.get('annotation','purge-note',auth.OWNER_ID) is None and store.get('course_guide',cid,auth.OWNER_ID) is None
    with db.connect() as c:assert not c.execute('SELECT 1 FROM library_search WHERE course=?',(cid,)).fetchone()
