"""Private-plan repair must preserve public tasks and independent explanation gates."""
import asyncio
import pytest
import explanations as explain
import tools
from answer_parts import SolvedPart


def test_parameter_plan_is_resolved_without_changing_the_public_question(monkeypatch):
    calls=[]
    async def solve(question,options=None,**kwargs):
        calls.append((question,kwargs))
        return tools.SolverAnswer(answer='p**n',worked_solution='All n independent diagonal events must occur, so multiply their probabilities.',
            parts=[SolvedPart(kind='numeric',expression='p**n',answer='p**n')] if len(calls)==1 else
                  [SolvedPart(kind='symbolic',answer='p**n',expression='')])
    monkeypatch.setattr(tools,'solve_independently',solve)
    question='Express the probability in terms of the supplied parameters p and n.'
    solved,draft=asyncio.run(tools.solve_supplied_checked(question))
    assert len(calls)==2 and all(q==question for q,_ in calls)
    assert 'symbolic' in calls[1][1]['repair_feedback']
    assert draft.question==question and solved.answer=='p**n'
    assert draft.answer_parts[0].kind=='symbolic'


def test_unresolved_plan_is_withheld_after_one_private_retry(monkeypatch):
    calls=[]
    async def solve(*args,**kwargs):
        calls.append(1)
        return tools.SolverAnswer(answer='p**n',worked_solution='The formula follows by multiplying independent event probabilities.',parts=[SolvedPart(kind='numeric',expression='p**n')])
    monkeypatch.setattr(tools,'solve_independently',solve)
    with pytest.raises(tools.CandidateError,match='unresolved variables'):
        asyncio.run(tools.solve_supplied_checked('Find the probability in terms of p and n.'))
    assert len(calls)==2


def draft(**updates):
    data=dict(core_concept='Addition combines the quantities described in the provided evidence. [S1]',
        key_formulas='No additional formula is specified in the supplied notes. [S1]',
        worked_example='Hypothetically two items and two more items make four items. This applies the covered combination rule. [S1]',
        common_pitfalls='Keep track of all the quantities in the stated example. [S1]',
        example_question='Combine two items with two more items and state the total.',source_refs=['S1'],claims=[])
    return explain.ExplanationDraft(**(data|updates))


def review(**updates):
    data={name:True for name in ['all_claims_grounded','topic_matches','formulas_valid','example_matches_independent_solution',
        'calculations_match','assumptions_and_domains_valid','source_refs_valid','complete_sections','original_example','depth_matches']}
    return explain.ExplanationReview(**(data|updates))


def setup(monkeypatch,*,bad_flag=None):
    calls={'draft':0,'solver':0,'review':0}
    async def invoke(prompt,temperature,schema):
        if schema is explain.ExplanationDraft:calls['draft']+=1;return draft()
        assert schema is explain.ExplanationReview
        calls['review']+=1
        if bad_flag:return review(**{bad_flag:False},issues='A specific evidence defect must be repaired.')
        return review(all_claims_grounded=calls['review']>1,issues='Correct the unsupported core statement.' if calls['review']==1 else '')
    async def solved(question,*a,**k):
        calls['solver']+=1
        value=tools.SolverAnswer(answer='4',worked_solution='Combining two items with two items gives a total of four items.',parts=[SolvedPart(kind='numeric',expression='2+2',answer='4')])
        return value,tools.QuestionDraft(question=question,canonical_answer='4',solution=value.reasoning)
    import writer_evidence
    async def evidence(*args):return 'Covered addition principle [S1].'
    monkeypatch.setattr(writer_evidence,'writer_context',evidence)
    monkeypatch.setattr(tools,'_invoke_json',invoke)
    monkeypatch.setattr(tools,'solve_supplied_checked',solved)
    monkeypatch.setattr(explain,'record_check',lambda *a,**k:None)
    return calls


def run_explanation():
    return asyncio.run(explain.generate('Combining quantities','brief',[{'ref':'S1','source_title':'Test notes','page':1,'kind':'notes','text':'Addition combines quantities to obtain their total.'}],'Use only these notes.'))


def test_explanation_prose_repair_reuses_unchanged_blind_solution_but_rechecks(monkeypatch):
    calls=setup(monkeypatch)
    text,refs,example_question=run_explanation()
    assert calls=={'draft':2,'solver':1,'review':2}
    assert refs==['S1'] and all('## '+heading in text for heading in ['Core Concept','Key Formulas','Worked Example','Common Pitfalls'])


@pytest.mark.parametrize('flag',['original_example','complete_sections','all_claims_grounded','formulas_valid','example_matches_independent_solution'])
def test_failed_explanation_gates_never_become_approval(monkeypatch,flag):
    from generation_errors import StageFailure
    calls=setup(monkeypatch,bad_flag=flag)
    with pytest.raises(StageFailure,match='could not be verified'):run_explanation()
    assert calls['review']==2 and calls['draft']==2


def test_source_clone_is_rejected_before_spending_on_a_solver(monkeypatch):
    from generation_errors import StageFailure
    copied='A deposit of one hundred dollars earns interest annually. Calculate the balance after two years.'
    async def invoke(*args,**kwargs):return draft(example_question=copied)
    async def forbidden(*a,**k):pytest.fail('Source copying must be caught before solving')
    import writer_evidence
    async def evidence(*args):return 'Covered compounding principle [S1].'
    monkeypatch.setattr(writer_evidence,'writer_context',evidence)
    monkeypatch.setattr(tools,'_invoke_json',invoke);monkeypatch.setattr(tools,'solve_supplied_checked',forbidden)
    monkeypatch.setattr(explain,'record_check',lambda *a,**k:None)
    with pytest.raises(StageFailure):
        asyncio.run(explain.generate('Interest','brief',[{'ref':'S1','source_title':'Test notes','page':1,'kind':'notes','text':copied}],'Covered compounding methods.'))


def test_supplied_true_false_options_are_parsed_and_keep_their_order():
    from supplied_questions import classify
    kind,body,options=classify('The displayed assertion holds for every input.\nA. False\nB. True')
    assert kind=='true_false' and options==['False','True']
    assert body=='The displayed assertion holds for every input.'


def test_supplied_mcq_is_not_shuffled_or_publicly_repaired(monkeypatch):
    question='Calculate two plus two.';options=['3','4','5','6'];calls=[]
    solved=tools.SolverAnswer(answer='B. 4',worked_solution='Adding two and two gives four, so the matching option body is four.',question_type='mcq')
    async def checked(body,actual,**kwargs):
        assert body==question and actual==options
        return solved,tools.QuestionDraft(question=body,question_type='mcq',options=actual,canonical_answer='B. 4',solution=solved.reasoning)
    async def verify(draft,**kwargs):calls.append(kwargs);return draft
    def shuffled(*a):pytest.fail('A supplied option order must remain unchanged')
    monkeypatch.setattr(tools,'solve_supplied_checked',checked)
    monkeypatch.setattr(tools,'_verify_draft',verify)
    monkeypatch.setattr(tools,'shuffle_choice_draft',shuffled)
    text=question+'\n'+'\n'.join(chr(65+i)+'. '+value for i,value in enumerate(options))
    value=asyncio.run(tools.prepare_assignment_question.__wrapped__(text))
    assert value.options==options and value.question==question
    assert calls[0]['allow_public_repair'] is False


def test_deep_profile_changes_work_deadline_without_counting_queue_time():
    import pipeline_runtime as runtime
    class Timer:
        deadline=None
        def reschedule(self,value):self.deadline=value
    timer=Timer();token=runtime.TRACE.set({'timer':timer,'started':10})
    try:
        runtime.set_tutor_profile(extended=False);assert timer.deadline is None
        runtime.set_tutor_profile(extended=True)
        assert timer.deadline==10+max(runtime.GENERATION_TIMEOUT_SECONDS,runtime.COMPLEX_TIMEOUT_SECONDS)
    finally:runtime.TRACE.reset(token)



def test_currency_prefix_does_not_hide_a_wrong_rounded_numeric_key():
    from answer_parts import evaluate_parts,numeric_binding_issues
    expression='200*1.005**36+200*(1.005**36-1)/0.005'
    assert numeric_binding_issues(evaluate_parts([SolvedPart(kind='numeric',expression=expression,answer='USD 8107.69')]))
    assert not numeric_binding_issues(evaluate_parts([SolvedPart(kind='numeric',expression=expression,answer='USD 8,106.56')]))


def test_explanation_sources_are_stable_but_do_not_fill_with_one_overlapping_page():
    rows=[]
    for i in range(9):
        rows.append({'chunk_id':str(i),'ref':'S'+str(i+1),'text':('Core shared explanation of the same concept. '*4) if i<8 else 'A complementary application states distinct assumptions and limitations.',
            'score':.9 if i<8 else .88,'source_file':'same.md' if i<8 else 'other.md','page':1,'kind':'notes','source_title':'Notes','doc_type':'notes'})
    allowed={r['chunk_id'] for r in rows}
    first=explain.select_sources(rows,allowed)
    assert first==explain.select_sources(rows,allowed)
    assert any(r['source_file']=='other.md' for r in first[:3])
    assert len(first)<=8
    assert not explain.select_sources(rows,set())


def test_generated_seed_finisher_still_runs_without_supplied_task_variables(monkeypatch):
    seed=tools.QuestionSeed(question='Calculate the product of two and three.',question_type='calculation',feasibility_witness='The product is six.')
    solved=tools.SolverAnswer(answer='6',worked_solution='Multiply the two given numbers: two times three equals six.',parts=[SolvedPart(kind='numeric',expression='2*3',answer='6')])
    async def checked(*a,**k):return solved
    async def verify(draft,*a,**k):return draft
    import question_preflight
    monkeypatch.setattr(question_preflight,'solve_checked',checked)
    monkeypatch.setattr(tools,'_verify_draft',verify)
    result=asyncio.run(tools._finish_seed(seed,'Multiplication',[], 'medium',[], '', 'Requested difficulty: medium'))
    assert result.canonical_answer=='6'


def test_repeated_explanation_reuses_checked_text_but_depth_and_version_invalidate(client,monkeypatch):
    import auth,db,curriculum,retrieval,uuid
    cid=db.create_course(auth.OWNER_ID,'Cache '+uuid.uuid4().hex)['id']
    db.sync_documents(auth.OWNER_ID,[{'course_id':cid,'filename':'notes.md','sha256':'a'*64,'size':100,'doc_type':'notes'}],prune=False)
    source={'ref':'S1','chunk_id':'cache-chunk','text':'Double integration evaluates an integral over a planar region.',
        'course_id':cid,'source_file':'notes.md','source_title':'Notes','page':1,'kind':'notes','doc_type':'notes','score':.9}
    version=['cache-v1'];calls=[]
    monkeypatch.setattr(curriculum,'course_map',lambda *a:{'version':version[0],'sections':[{'sources':[source]}],'pending_documents':[]})
    monkeypatch.setattr(curriculum,'scope_version',lambda *a:version[0])
    monkeypatch.setattr(curriculum,'overview',lambda *a:'Course scope')
    monkeypatch.setattr(retrieval,'search',lambda *a:[source])
    async def generate(*args):calls.append(args);return '## Core Concept\n\nChecked content.', ['S1'], 'Find a new integrated total on the supplied region.'
    monkeypatch.setattr(explain,'generate',generate)
    body={'topic':'Double integration','course_ids':[cid],'depth':'brief'}
    first=client.post('/explain',json=body);assert first.status_code==200,first.text
    second=client.post('/explain',json=body|{'topic':'  DOUBLE   integration  '})
    assert second.status_code==200,second.text
    assert second.json()['cached'] and second.json()['id']==first.json()['id'] and len(calls)==1
    deep=client.post('/explain',json=body|{'depth':'deep'});assert deep.status_code==200,deep.text
    assert len(calls)==2
    version[0]='cache-v2'
    fresh=client.post('/explain',json=body);assert fresh.status_code==200,fresh.text
    assert len(calls)==3 and fresh.json()['id']!=first.json()['id']


def test_supplied_question_tail_is_not_silently_dropped(monkeypatch):
    prompts=[]
    async def invoke(prompt,temperature,schema):
        prompts.append(prompt)
        return tools.SolverAnswer(answer='4',worked_solution='Use the final explicitly supplied premise to obtain four.')
    monkeypatch.setattr(tools,'_invoke_json',invoke)
    marker='ESSENTIAL_FINAL_GIVEN: the requested value equals four.'
    question='Read the following complete task. '+('Explanatory context. '*850)+marker
    assert 16000<len(question)<30000
    asyncio.run(tools.solve_independently(question))
    assert marker in prompts[0]


def test_short_heading_is_a_grounding_defect_not_a_schema_retry():
    from types import SimpleNamespace
    support=tools.EvidenceSupport(method='A claimed timing method',source_ref='S1',quote='Timeline')
    value=SimpleNamespace(evidence_support=[support],used_source_refs=['S1'])
    reason=tools.evidence_support_issue(value,[{'ref':'S1','text':'Timeline'}])
    assert 'heading' in reason and 'unsupported' in reason


def test_repair_deadline_grace_is_once_only_and_never_shortens_complex_work():
    import pipeline_runtime as runtime
    class Timer:
        def __init__(self):self.deadline=70;self.calls=0
        def when(self):return self.deadline
        def reschedule(self,value):self.calls+=1;self.deadline=value
    timer=Timer();token=runtime.TRACE.set({'timer':timer,'started':10})
    try:
        runtime.set_repair_profile();first=timer.deadline
        runtime.set_repair_profile()
        assert timer.calls==1 and first>=70
    finally:runtime.TRACE.reset(token)
    timer=Timer();timer.deadline=100;token=runtime.TRACE.set({'timer':timer,'started':10})
    try:runtime.set_repair_profile();assert timer.deadline==100
    finally:runtime.TRACE.reset(token)


def test_currency_grouping_keeps_the_requested_cent_precision():
    from answer_parts import evaluate_parts,numeric_binding_issues
    part=SolvedPart(kind='numeric',unit='USD',expression='8106.557097901457',answer=r'$8,106.56\,\mathrm{USD}$')
    assert not numeric_binding_issues(evaluate_parts([part]))
    wrong=part.model_copy(update={'answer':r'$8,107.69\,\mathrm{USD}$'})
    assert numeric_binding_issues(evaluate_parts([wrong]))
