"""General regression cases from balanced real-document evaluations."""
import pytest
from answer_parts import MathClaim
from math_checks import check_claim
from tools import EvidenceSupport


def test_partial_derivative_uses_explicit_variable_and_keeps_parameters():
    claim = MathClaim(kind='derivative', left='x**2*y**3', right='3*x**2*y**2',
                      variables=['x','y'], with_respect_to='y')
    assert check_claim(claim.model_dump())['status'] == 'passed'
    claim.right = '2*x*y**3'
    assert check_claim(claim.model_dump())['status'] == 'failed'


def test_antiderivative_and_legacy_calculus_checks():
    assert check_claim({'kind':'integral','left':'2*x*y','right':'x*y**2',
                        'variables':['x','y'],'with_respect_to':'y'})['status'] == 'passed'
    assert check_claim({'kind':'derivative','left':'x**2','right':'2*x',
                        'variables':['x']})['status'] == 'passed'
    with pytest.raises(ValueError):
        check_claim({'kind':'derivative','left':'x**2','right':'2*x',
                     'variables':['x'],'with_respect_to':'y'})


def test_verbose_evidence_label_does_not_mutate_the_evidence():
    quote = 'The original source supports this exact method.'
    item = EvidenceSupport(method='A supported method ' * 30, source_ref='S1', quote=quote)
    assert len(item.method) == 180
    assert item.quote == quote and item.source_ref == 'S1'
    with pytest.raises(ValueError):
        EvidenceSupport(method='ok', source_ref='S1', quote=quote)


def test_long_answers_have_a_ceiling_without_a_minimum_part_quota():
    from assessment_level import workload_issue, contract
    assert not workload_issue('Explain your reasoning for one coherent task.', 'long_answer', 'hard')
    assert not workload_issue('(a) Infer a result.\n\n(b) Use it to justify a conclusion.', 'long_answer', 'insane')
    assert not workload_issue('(a) State the relevant definition.\n(b) Apply it directly.', 'long_answer', 'easy')
    assert workload_issue('(a) First task.\n(b) Second task.\n(c) Third task.', 'long_answer', 'hard')
    text = contract('insane', [], question_type='long_answer')
    assert 'no minimum' in text.lower() or 'never a required count' in text
    assert 'not templates to copy' in text
    assert 'INCLUDED' in text


def test_missing_duplicate_conceptual_key_uses_only_explicit_part_answers():
    from tools import SolverAnswer
    result = SolverAnswer(question_type='essay', worked_solution='A complete evidence-based explanation is provided here.',
                          parts=[{'kind':'conceptual','answer':'The explicitly stated conclusion.'}])
    assert result.answer == 'The explicitly stated conclusion.'
    numeric = SolverAnswer(question_type='calculation',worked_solution='Adding two and two gives four directly.',
                           parts=[{'kind':'numeric','answer':'4','expression':'2+2'}])
    assert numeric.answer=='4'
    for kind, parts in [('mcq',[{'kind':'conceptual','answer':'A'}]),
                        ('essay',[]), ('calculation',[{'kind':'numeric','answer':'4'}])]:
        with pytest.raises(ValueError):
            SolverAnswer(question_type=kind, worked_solution='A complete independently derived solution.', parts=parts)


def test_variation_never_forces_extra_depth_at_easy():
    from assessment_level import variation_instruction
    assert 'one direct application' in variation_instruction('easy')
    assert 'Do not add independent experiments' in variation_instruction('medium')


def test_equation_checks_compare_zero_sets_without_inventing_identity_counterexamples():
    claim = dict(kind='equation_equivalence', left='(x+1)**2+(y-2)**2-((x-3)**2+(y-4)**2)',
                 right='2*x+y-5', variables=['x','y'])
    assert check_claim(claim)['status'] == 'passed'
    claim['right'] = '2*x+y-6'
    assert check_claim(claim)['status'] == 'unresolved'
    for left, right in [('x**2','x'), ('x*(x-1)','x-1'), ('0','x')]:
        assert check_claim(dict(kind='equation_equivalence',left=left,right=right,variables=['x']))['status'] != 'passed'
    # Plain equivalence still means an identity; no automatic reinterpretation.
    assert check_claim(dict(kind='equivalence',left='y-2',right='-2*(x-3)',variables=['x','y']))['status'] == 'failed'


def test_numeric_binding_understands_fraction_styles_without_reading_function_arguments():
    from answer_parts import SolvedPart, evaluate_parts, numeric_binding_issues
    for fraction in [r'\frac{7}{8}', r'\dfrac{7}{8}', r'\tfrac{7}{8}']:
        part = SolvedPart(kind='numeric', answer='$f_{xy}(1,2)='+fraction+'$', expression='7/8')
        assert not numeric_binding_issues(evaluate_parts([part]))
        part.expression = '6/8'
        assert numeric_binding_issues(evaluate_parts([part]))
    unknown = SolvedPart(kind='numeric',answer='$f(1,2)$',expression='5')
    assert not numeric_binding_issues(evaluate_parts([unknown]))


def test_solver_receives_the_public_type_without_seeing_a_proposed_key(monkeypatch):
    import asyncio
    import tools
    prompts = []
    async def invoke(prompt, temperature, schema):
        prompts.append(prompt)
        return tools.SolverAnswer(question_type='short_answer',answer='The supported inference.',
                                  worked_solution='The inference follows from the stated public observation.')
    monkeypatch.setattr(tools,'_invoke_json',invoke)
    asyncio.run(tools.solve_independently('Which observation distinguishes these cases?', question_type='short_answer'))
    assert 'Public response format: short_answer' in prompts[0]
    assert 'do not require four MCQ options' in prompts[0]


@pytest.mark.parametrize('verdict,final_valid,accepted', [('withdrawn',True,True),('withdrawn',False,False),('confirmed_defect',True,False),('uncertain',True,False)])
def test_false_premise_objections_require_fresh_solving_and_verification(monkeypatch,verdict,final_valid,accepted):
    import asyncio
    import tools,math_format,question_preflight
    audits=[]
    solves=[]
    def review(valid):
        return tools.Verification(issues='' if valid else 'An alleged public contradiction.',
            public_claim_valid=valid,is_consistent=valid,source_clone=False,givens_complete=True,
            proof_is_valid=True,difficulty_matches=True,topic_methods_match=True,
            difficulty_issue='none',is_grounded=True,answer_leaked=False,is_on_topic=True,
            calculations_match=True)
    async def audit(*args,**kwargs):
        audits.append(1)
        return review(False if len(audits)==1 else final_valid)
    async def solve(*args,**kwargs):
        solves.append(1)
        return tools.SolverAnswer(answer='4',worked_solution='Adding two and two gives four directly.')
    async def challenge(*args):return tools.PremiseChallenge(reason='Independent literal-premise finding.',verdict=verdict)
    async def formatting(*args):pass
    monkeypatch.setattr(tools,'_audit_draft',audit)
    monkeypatch.setattr(tools,'solve_independently',solve)
    monkeypatch.setattr(question_preflight,'challenge_defect',challenge)
    monkeypatch.setattr(math_format,'check',formatting)
    draft=tools.QuestionDraft(question='Calculate two plus two.',question_type='short_answer',
                              canonical_answer='5',solution='A proposed but untrusted independent solution.')
    independent=tools.SolverAnswer(answer='5',worked_solution='A proposed but incorrect independent solution.')
    if accepted:
        result=asyncio.run(tools._verify_draft(draft,independent=independent))
        assert result.canonical_answer=='4' and len(audits)==2 and len(solves)==1
        assert result.question=='Calculate two plus two.'
    else:
        with pytest.raises(tools.CandidateError):asyncio.run(tools._verify_draft(draft,independent=independent))
        assert len(solves)==int(verdict=='withdrawn')


def test_new_failure_reasons_are_safe_and_specific():
    import tools
    from generation_errors import describe
    error, status = describe(tools.CandidateError('The reported numeric answer disagrees with its calculated outputs.'))
    assert status==422 and error['stage']=='calculator'
    assert 'numeric answer disagrees' in error['reason']
    error, status = describe(RuntimeError('private-provider-payload-and-secret'))
    assert 'private-provider' not in str(error)
    error, status=describe(tools.EvidenceScopeError('The public task needs methods not supported by the retrieved course passages.'))
    assert error['stage']=='retrieval' and 'not supported' in error['reason']


def test_recovered_numeric_key_still_rejects_a_wrong_explicit_part_answer():
    import asyncio
    import tools
    solved=tools.SolverAnswer(question_type='calculation',worked_solution='The proposed sum is untrusted until checked.',
                             parts=[{'kind':'numeric','answer':'5','expression':'2+2'}])
    draft=tools.QuestionDraft(question='Calculate two plus two.',question_type='calculation',
                              canonical_answer='pending',solution='Pending independent checks.')
    with pytest.raises(tools.CandidateError,match='reported numeric answer'):
        asyncio.run(tools._use_solution_checked(draft,solved))


def test_repair_feedback_does_not_escalate_hard_to_insane_or_force_more_parts():
    from types import SimpleNamespace
    from tools import difficulty_repair
    review=SimpleNamespace(difficulty_issue='too_easy')
    hard=difficulty_repair(review,'hard')
    assert 'ONE meaningful application' in hard and 'do not demand an Insane extension' in hard
    insane=difficulty_repair(review,'insane')
    assert 'short discriminating insight is enough' in insane
    assert 'at most two' not in difficulty_repair(review,'easy')


def test_shuffling_remaps_positional_working_without_revealing_the_key(monkeypatch):
    import tools
    from answer_parts import SolvedPart
    monkeypatch.setattr(tools.random.SystemRandom,'shuffle',lambda self,items:items.reverse())
    draft=tools.QuestionDraft(question='Select the correct result.',question_type='mcq',options=['4','5','6','7'],
        canonical_answer='A. 4',solution='The first option is correct. The second option is wrong. Only A is correct.',
        answer_parts=[SolvedPart(answer='The first option is correct.',requirements='Select the first option.')])
    tools.shuffle_choice_draft(draft)
    assert draft.canonical_answer=='D. 4'
    assert 'fourth option is correct' in draft.solution and 'third option is wrong' in draft.solution
    assert 'Only D is correct' in draft.solution
    assert 'fourth option' in draft.answer_parts[0].requirements
    assert 'mcq_shuffle' not in draft.verification


def test_exploratory_proof_transcripts_are_repaired_not_published():
    from working_checks import has_draft_working
    text='This does not break the required property. It actually holds for this example? Try another construction.'
    assert has_draft_working('Prove or disprove this general claim.',text)
    assert not has_draft_working('Identify the error in this proposed working.',text)
    assert not has_draft_working('Prove this claim.','Checking the defining properties establishes the claim directly.')


@pytest.mark.parametrize('name',['AskResponse','SessionResponse'])
def test_public_study_responses_strip_private_verification_on_new_and_saved_sessions(name):
    import app
    payload=dict(verification={'solver_passed':True,'latency':2.5,'mcq_shuffle':{'new_key':'PRIVATE ANSWER','new_index':2},
                               'canonical_answer':'PRIVATE ANSWER','issues':'PRIVATE ANSWER','solver_kind':{'untrusted':'value'}},
                 thread_id='test-session-123',mode='practice',difficulty='hard',question='A public question?',
                 status='awaiting_answer',attempts_used=0,max_attempts=3,sources=[],topic='A topic',
                 opening_hint='',last_feedback='',history=[],policy_decisions=[])
    result=getattr(app,name)(**payload)
    assert result.verification=={'solver_passed':True,'latency':2.5}
    assert 'PRIVATE ANSWER' not in result.model_dump_json()
