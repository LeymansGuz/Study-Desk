"""Novel practice, stable explanations and deliberate bank review are different policies."""
import asyncio,uuid
import pytest
import auth,db,curriculum,graph,learning_store as store
from practice_novelty import history,question_key


def test_retained_history_survives_reindex_and_source_filter_changes(client):
    skill='stable-'+uuid.uuid4().hex
    db.record_exposure(auth.OWNER_ID,'old-index-version',skill,'Find the rate for this original situation.',['old-chunk'])
    assert any(row['skill_id']==skill for row in history(auth.OWNER_ID))
    assert not db.recent_exposures(auth.OWNER_ID,'new-index-version')


def test_number_only_repeat_is_blocked_anywhere_in_retained_history(monkeypatch):
    import semantic_duplicates as duplicate
    def forbidden(*a):pytest.fail('A normalized repeat needs no embedding inference')
    monkeypatch.setattr(duplicate,'vector',forbidden)
    previous=['Compute the balance of a loan with principal 200 and rate 4 after 8 years.']
    previous+=['Unrelated original exercise identifier '+str(i) for i in range(1999)]
    assert duplicate.duplicate('Compute the balance of a loan with principal 500 and rate 7 after 3 years.',previous)


def test_whole_course_rotates_skills_and_anchor_chunks_across_versions(client,monkeypatch):
    suffix=uuid.uuid4().hex;cid='course-'+suffix;units=[]
    for i in range(4):
        sources=[{'chunk_id':f'{suffix}-{i}-{j}','text':f'Coverage concept {i} establishes its supported method and interpretation, paragraph {j}.',
            'course_id':cid,'source_file':f'unit-{i}.md','page':1,'doc_type':'notes','kind':'notes','source_title':'Study notes','ref':'S1','chunk_index':j} for j in range(2)]
        units.append({'id':f'{suffix}-skill-{i}','course_id':cid,'source_file':f'unit-{i}.md','title':'Covered concept',
            'keywords':['coverage'],'doc_type':'notes','sources':sources})
    catalog={'version':'old','sections':units,'pending_documents':[]}
    monkeypatch.setattr(curriculum,'course_map',lambda *a:catalog)
    monkeypatch.setattr(curriculum,'scope_rules',lambda *a:'')
    monkeypatch.setattr(curriculum,'overview',lambda *a:'Covered methods only.')
    monkeypatch.setattr(curriculum,'assessment_support',lambda *a:[])
    monkeypatch.setattr(curriculum,'topical_evidence',lambda *a:[])
    selected=[];anchors=[]
    for i in range(8):
        if i==4:catalog['version']='after-reindex'
        value=curriculum.plan_context(auth.OWNER_ID,[cid],'Any syllabus topic',whole=True)
        plan=value['plans'][0];selected.append(plan['skill_id']);anchor=plan['sources'][0]['chunk_id'];anchors.append(anchor)
        db.record_exposure(auth.OWNER_ID,value['scope_key'],plan['skill_id'],'Distinct practice task '+str(i),[anchor])
    assert len(set(selected[:4]))==len(set(selected[4:]))==4
    assert len(set(anchors))==8


def test_unseen_bank_does_not_return_a_number_reskin_from_an_old_scope(client,monkeypatch):
    course=db.create_course(auth.OWNER_ID,'Novelty '+uuid.uuid4().hex)['id']
    question='Find the area of a rectangle with length 8 and width 4.'
    db.record_exposure(auth.OWNER_ID,'outdated-version','old-skill','Find the area of a rectangle with length 6 and width 3.',['old'])
    item={'current_question':question,'version':'new-version','difficulty':'medium','question_type':'calculation',
          'course_ids':[course],'topic':'Area','sources':[],'assessment_version':__import__('assessment_level').POLICY_VERSION}
    store.put('bank',auth.OWNER_ID+':'+store.fingerprint(question),auth.OWNER_ID,item)
    assert store.bank_take(auth.OWNER_ID,'new-version',[course],'medium',['calculation'],None,'Area') is None


def test_generated_number_reskin_is_withheld_without_writing_a_new_exposure(client,monkeypatch):
    from tools import QuestionDraft,TutorError
    q='Determine the roots of x squared minus five x plus six.'
    db.record_exposure(auth.OWNER_ID,'old-scope','prior-skill',q,['old'])
    async def draft(*a,**k):return QuestionDraft(question=q,canonical_answer='2 and 3',solution='Factor the polynomial into the two linear factors.',question_type='calculation')
    monkeypatch.setattr(graph,'draft_question',draft)
    monkeypatch.setattr(graph,'plan_context',lambda *a,**k:(_ for _ in ()).throw(ValueError('No alternative supported section')))
    state=graph.initial_state('Polynomial roots',user_id=auth.OWNER_ID,figure_mode='none')
    state.update(bank_checked=True,scope_key='new-scope',skill_id='new-skill')
    before=len(history(auth.OWNER_ID))
    with pytest.raises(TutorError,match='recent problem'):
        asyncio.run(graph.generate_question(state))
    assert len(history(auth.OWNER_ID))==before


def test_duplicate_embedding_work_is_bounded_for_long_history(monkeypatch):
    import numpy as np
    import semantic_duplicates as duplicates
    calls=[]
    def vector(value):
        calls.append(value);result=np.zeros(50);result[min(len(calls)-1,49)]=1;return result
    monkeypatch.setattr(duplicates,'vector',vector)
    prior=['Prior unrelated biology memory item code '+str(i) for i in range(2000)]
    assert not duplicates.duplicate('Evaluate the newly defined coordinate transformation and interpret its invariant.',prior)
    assert len(calls)<=49


def test_mcq_identity_includes_bodies_but_not_display_order():
    from practice_novelty import task_text
    q='Which statement is correct?'
    a=['A. Water moves toward lower potential.','B. All cells have a wall.','C. Diffusion always requires ATP.','D. All solutes cross freely.']
    reordered=['D. All solutes cross freely.','A. Water moves toward lower potential.','C. Diffusion always requires ATP.','B. All cells have a wall.']
    assert task_text(q,a)==task_text(q,reordered)
    assert question_key(task_text(q,a))!=question_key(task_text(q,['A different inference','Second claim','Third claim','Fourth claim']))
    assert store.fingerprint(q,a)==store.fingerprint(q,reordered)


def test_metadocuments_cannot_be_primary_whole_course_topics(client,monkeypatch):
    source={'chunk_id':'report-only','text':'Forty percent of students placed their work in the wrong answer box.'}
    unit={'id':'report-skill','course_id':'reports','source_file':'report.pdf','title':'Performance statistics',
          'doc_type':'exam_report','sources':[source]}
    monkeypatch.setattr(curriculum,'course_map',lambda *a:{'version':'report-version','sections':[unit],'pending_documents':[]})
    with pytest.raises(ValueError,match='primary question sources'):
        curriculum.plan_context(auth.OWNER_ID,['reports'],'Any syllabus topic',whole=True)


def test_independent_preflight_checks_prior_inference_and_does_not_reuse_old_approval(monkeypatch):
    import question_preflight as preflight
    async def joint(assessment,*a):return assessment
    monkeypatch.setattr(preflight,"ensure_joint_setup",joint)
    import question_preflight as preflight
    import tools
    token=uuid.uuid4().hex;calls=[];source='Multiplication computes a product from its explicitly given factors.'
    async def invoke(prompt,temperature,schema):
        calls.append(prompt)
        return preflight.QuestionPreflight(source_comparisons=[],setup=tools.SetupAssessment(evaluation_request='',background_facts=[],status='feasible',witness_or_conflict='Consistent test fixture conditions.'),reason='The domain method is covered.',verdict='valid',is_on_topic=True,
            tested_concept='Multiplication',is_grounded=True,source_clone=False,
            repeats_recent_task='previously seen multiplication' in prompt,
            originality_reason='Same multiplication inference.' if 'previously seen multiplication' in prompt else 'No prior task.',
            used_source_refs=['S1'],evidence_support=[tools.EvidenceSupport(method='Multiplication',source_ref='S1',quote=source)])
    monkeypatch.setattr(tools,'_invoke_json',invoke)
    sources=[{'ref':'S1','text':source,'source_title':'Notes','kind':'notes','page':1}]
    question='Calculate the given product. '+token
    asyncio.run(preflight.check('Multiplication',question,[],sources))
    with pytest.raises(tools.DuplicateQuestionError):
        asyncio.run(preflight.check('Multiplication',question,[],sources,['A previously seen multiplication task calculates the given product.']))
    assert len(calls)==2


def test_explained_example_is_seen_for_practice_without_repeated_history_rows(client):
    from explanations import remember_example
    question='An original explained application '+uuid.uuid4().hex+' asks for a supported conclusion.'
    remember_example(auth.OWNER_ID,['example-course'],'version-a',question)
    before=history(auth.OWNER_ID)
    assert any(row['question']==question for row in before)
    remember_example(auth.OWNER_ID,['example-course'],'version-a',question)
    assert len(history(auth.OWNER_ID))==len(before)


def test_unpublished_explanation_example_rolls_back(client):
    from explanations import remember_example
    from generation_control import atomic_generation
    question='An unpublished example '+uuid.uuid4().hex+' must not consume an exposure.'
    async def fail():
        remember_example(auth.OWNER_ID,['example-course'],'v',question)
        raise ValueError('Synthetic publication failure')
    with pytest.raises(ValueError):asyncio.run(atomic_generation(fail))
    assert not any(row['question']==question for row in history(auth.OWNER_ID))


def test_a_new_companion_claim_cannot_cancel_a_copied_source_target(monkeypatch):
    import tools,question_preflight as preflight
    source='Exercise: prove that the stated regular bipartite graph has a perfect matching.'
    target='Claim A: the stated regular bipartite graph has a perfect matching.'
    calls=[]
    async def invoke(*args):
        calls.append(1)
        return preflight.QuestionPreflight(setup=tools.SetupAssessment(evaluation_request='',background_facts=[],
            status='feasible',witness_or_conflict='The graph hypotheses are consistent.'),verdict='valid',
            reason='A new second claim is added.',is_on_topic=True,tested_concept='Matching',is_grounded=True,
            source_clone=False,repeats_recent_task=False,originality_reason='The combined task has a new claim.',
            source_comparisons=[preflight.SourceTaskComparison(public_target=target,source_ref='S1',
                source_task=source,is_source_task=True,same_setup=True,same_inference=True)])
    monkeypatch.setattr(tools,'_invoke_json',invoke)
    with pytest.raises(tools.CandidateError,match='clones a source'):
        asyncio.run(preflight.check('A covered concept from: matching',target+' Claim B: a new unrelated property holds.',[],[{'ref':'S1','text':source,'source_title':'Notes','kind':'notes','page':1}]))
    assert calls == [1]
