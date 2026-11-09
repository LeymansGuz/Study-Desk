import asyncio
import itertools
from types import SimpleNamespace
import pytest
from pydantic import ValidationError
import tools
from calc import evaluate

@pytest.fixture(scope='module',autouse=True)
def initialize_isolated_database():
    import db
    db.init_db()

def test_grounding_requires_real_passage_quotes_not_a_boolean_or_inventory_claim():
    sources=[{'ref':'S1','text':'The rate of oxygen consumption is used to measure respiration.'}]
    candidate=review(used_source_refs=['S1'])
    assert tools.evidence_support_issue(candidate,sources)
    candidate.evidence_support=[tools.EvidenceSupport(method='A required method',source_ref='S1',quote=' '*20)]
    assert tools.evidence_support_issue(candidate,sources)
    candidate.evidence_support=[tools.EvidenceSupport(method='Photosynthesis light response',source_ref='S1',quote='Increasing light increases photosynthesis up to saturation.')]
    assert tools.evidence_support_issue(candidate,sources)
    candidate.evidence_support=[tools.EvidenceSupport(method='Measuring respiration',source_ref='S1',quote='The rate of oxygen consumption is used to measure respiration.')]
    assert not tools.evidence_support_issue(candidate,sources)
    # Mathematical symbol case cannot be normalized away in source evidence.
    source=[{'ref':'S1','text':'For real x the definition is f(x)=x*x.'}]
    candidate.evidence_support=[tools.EvidenceSupport(method='Function definition',source_ref='S1',quote='For real X the definition is f(X)=X*X.')]
    assert tools.evidence_support_issue(candidate,source)

def test_final_working_rejects_abandoned_computation_without_blocking_error_analysis():
    from working_checks import has_draft_working
    text='This is not yet the clean identity. A cleaner route: recompute: the correct candidate is different.'
    assert has_draft_working('Prove the constrained minimum and state its value.',text)
    assert not has_draft_working('Identify the error in this proposed calculation.',text)
    assert not has_draft_working('Prove the minimum.','Completing the square gives a nonnegative expression. Equality holds at the candidate.')
    solved=tools.SolverAnswer.model_validate({'answer':'4','worked_solution':'Adding two to two gives four directly.','parts':[]})
    assert solved.reasoning=='Adding two to two gives four directly.'

def test_reviewer_options_are_validated_before_mutating_a_public_candidate():
    draft=tools.QuestionDraft(question='What is two plus two?',question_type='mcq',options=['4','3','2','1'],
        canonical_answer='A. 4',solution='Two plus two is four by addition.')
    with pytest.raises(tools.CandidateError):tools._review_options(draft,['4','3'])
    assert draft.options==['4','3','2','1']
    invalid=draft.model_copy(update={'options':['4','3']})
    with pytest.raises(tools.CandidateError):tools._validate_choice_draft(invalid)


def test_conflicting_solver_selections_are_not_silently_rewritten_into_a_key():
    draft=tools.QuestionDraft(question='What is two plus two?',question_type='mcq',options=['4','3','2','1'],
        canonical_answer='A. 4',solution='Adding two and two gives four.')
    solved=tools.SolverAnswer(answer='C. 2',selected_option_index=0,worked_solution='Adding two and two gives four.',parts=[])
    with pytest.raises(tools.CandidateError,match='conflicting MCQ selections'):
        tools._use_solution(draft,solved)

def test_false_premise_allegation_is_challenged_but_not_auto_approved(monkeypatch):
    calls=[]
    async def invoke(prompt,temperature,schema):
        calls.append(schema)
        if schema is tools.PublicValidity:return tools.PublicValidity(setup=tools.SetupAssessment(evaluation_request='',background_facts=[],status='feasible',witness_or_conflict='The identity t=t holds for every real t.'),reason='Alleged impossible identity.' if calls.count(schema)==1 else 'Identity verified.',verdict='defect' if calls.count(schema)==1 else 'valid')
        from premise_checks import IndependentSetup
        if schema is IndependentSetup:return IndependentSetup(status='feasible',witness_or_conflict='The identity has a joint interpretation.')
        assert schema is tools.PremiseChallenge
        return tools.PremiseChallenge(reason='The claimed contradiction is not valid under the stated givens.',verdict='withdrawn')
    monkeypatch.setattr(tools,'_invoke_json',invoke)
    value=asyncio.run(tools.ensure_public_validity('Prove the identity t=t under the stated real domain.'))
    assert value.verdict=='valid'  # withdrawal alone is insufficient; fresh approval is required
    from premise_checks import IndependentSetup
    assert calls==[tools.PublicValidity,tools.PremiseChallenge,tools.PublicValidity]

def test_confirmed_false_claim_is_still_withheld(monkeypatch):
    async def invoke(prompt,temperature,schema):
        if schema is tools.PublicValidity:return tools.PublicValidity(setup=tools.SetupAssessment(evaluation_request='',background_facts=[],status='feasible',witness_or_conflict='Consistent test fixture conditions.'),reason='Two is prime and even.',verdict='defect')
        return tools.PremiseChallenge(reason='The prime 2 satisfies the hypothesis but is not odd.',verdict='confirmed_defect')
    monkeypatch.setattr(tools,'_invoke_json',invoke)
    with pytest.raises(tools.CandidateError,match='conflicting'):
        asyncio.run(tools.ensure_public_validity('Prove every prime integer is odd (negative control).'))

def test_overlong_diagnostics_are_bounded_without_changing_semantic_payloads():
    payload={'reason':'x'*2500,'verdict':'uncertain','setup':{'evaluation_request':'','background_facts':[],'status':'uncertain','witness_or_conflict':'Unresolved fixture conditions.'}}
    bounded=tools.normalize_diagnostics(payload,tools.PublicValidity)
    review=tools.PublicValidity.model_validate(bounded)
    assert review.verdict=='uncertain' and len(review.reason)==700
    assert payload['reason']=='x'*2500
    public={'question':'x'*20000,'feasibility_witness':'Full argument','options':['A','B']}
    assert tools.normalize_diagnostics(public,tools.QuestionSeed)==public


def test_conditional_math_checks_do_not_invent_counterexamples_or_certify_proofs():
    from math_checks import check_claim
    conditional=dict(kind='equivalence',left='c**2',right='a**2+b**2',variables=['a','b','c'],
        assumptions=['c**2==a**2+b**2'],samples=[1,2,3])
    # Independent arbitrary values are not a triangle satisfying the hypothesis.
    result=check_claim(conditional)
    assert result['status']=='unresolved' and result['substitutions']==0
    # A real counterexample within a stated domain still fails.
    assert check_claim(dict(kind='equivalence',left='x**2',right='x',variables=['x'],
        assumptions=['x>0'],samples=[2]))['status']=='failed'
    # Even an identity with declared assumptions must get independent domain review.
    assert check_claim(dict(kind='equivalence',left='x+x',right='2*x',variables=['x'],
        assumptions=['x>0']))['domain_review_required'] is True
    with pytest.raises(ValueError):check_claim({**conditional,'assumptions':['__import__("os")==1']})


def test_counting_plans_against_enumerated_outcomes_and_bounds():
    for n in range(9):
        for k in range(n+1):
            assert evaluate(f'comb({n},{k})')==sum(1 for _ in itertools.combinations(range(n),k))
    for n in range(6):
        for k in range(n+1):
            assert evaluate(f'perm({n},{k})')==sum(1 for _ in itertools.permutations(range(n),k))
    assert evaluate('factorial(0)')==1 and evaluate('factorial(6)')==720
    for expression in ['factorial(171)','comb(1001,2)','comb(3.2,1)','perm(-2,1)','math.comb(3,1)','__import__("os")']:
        assert evaluate(expression) is None


def review(**changes):
    fields=dict(difficulty_issue='none',public_claim_valid=True,is_consistent=True,source_clone=False,givens_complete=True,
        proof_is_valid=True,difficulty_matches=True,topic_methods_match=True,is_grounded=True,
        answer_leaked=False,is_on_topic=True,calculations_match=True,originality_reason='A new task.',correct_option_index=0)
    fields.update(changes)
    return tools.Verification(**fields)


def test_verifier_decisions_cannot_silently_default_to_false():
    with pytest.raises(ValidationError):
        tools.Verification(is_consistent=True,givens_complete=True)


def test_mcq_calculator_metadata_does_not_overwrite_the_option_key():
    from answer_parts import SolvedPart
    draft=tools.QuestionDraft(question='How many distinct arrangements has LEVEL?',question_type='mcq',
        options=['30','60','120','20'],canonical_answer='pending',solution='A solution will be computed independently.')
    solved=tools.SolverAnswer(answer='30',reasoning='There are five letters with two repeated pairs, so divide 120 by four.',
        parts=[SolvedPart(label='answer',kind='numeric',answer='$30$',expression='factorial(5)/(factorial(2)*factorial(2))')],option_evaluations=[tools.OptionEvaluation(index=i,option_text=v,finding='Checked against the derived count.',is_correct=i==0) for i,v in enumerate(draft.options)])
    tools._use_solution(draft,solved)
    assert draft.canonical_answer=='A. 30'
    assert draft.answer_parts[0].value==30


def test_false_label_survives_solver_and_numeric_metadata():
    from answer_parts import SolvedPart
    draft=tools.QuestionDraft(question='A light microscope always gives an upright image. True or false?',
        question_type='true_false',options=['True','False'],canonical_answer='pending',solution='A solution will be computed independently.')
    solved=tools.SolverAnswer(answer='False. The image is inverted.',
        reasoning='A light microscope forms an inverted image, so the stated claim is false.',
        parts=[SolvedPart(label='answer',kind='conceptual',answer='False')])
    tools._use_solution(draft,solved)
    assert draft.canonical_answer=='False'
    assert tools.choice_answer_correct('False',draft.options,draft.canonical_answer,'true_false') is True


def test_malformed_outer_json_is_not_mistaken_for_an_inner_method_object():
    with pytest.raises(ValueError,match='outer JSON'):
        tools.parse_json_object(r'{"method_plan":[{"method":"circle"}],"question":"Use \sqrt{2}."}')
    with pytest.raises(ValueError,match='control character'):
        tools.parse_json_object(r'{"question":"Use \frac{1}{2}."}')


def test_too_easy_feedback_increases_depth_without_adding_unrelated_parts():
    message=tools.difficulty_repair(review(difficulty_matches=False,difficulty_issue='too_easy'))
    assert 'Increase dependent reasoning' in message and 'Do not add unrelated tasks' in message


def test_diagnostic_aliases_preserve_a_negative_verdict():
    value=tools.PublicValidity.model_validate({'is_valid':False,'explanation':'The observations conflict under the stated controlled conditions.','setup':{'evaluation_request':'','background_facts':[],'status':'inconsistent','witness_or_conflict':'The observed values conflict.'}})
    assert value.verdict=='defect'
    with pytest.raises(ValidationError):tools.PublicValidity.model_validate({'is_valid':'false','explanation':'Untrusted string flag.'})
    topic=tools.TopicAlignment(is_on_topic=False,tested_concept='x'*200,reason='y'*600)
    assert topic.is_on_topic is False and len(topic.tested_concept)==150 and len(topic.reason)==400


def test_true_false_format_and_negation_are_unambiguous():
    assert tools.question_type_issue('Which statement best evaluates this claim?','true_false',['True','False'])
    assert not tools.question_type_issue('The statement is true or false: every integer is prime.','true_false',['True','False'])
    assert tools.parse_true_false('It is not true.')=='False'
    assert tools.parse_true_false('It is not false.')=='True'


def test_capm_interpretation_rule_is_narrow_and_handles_negation():
    from subject_guidance import interpretation_issues
    assert interpretation_issues('Use CAPM and the SML.','Y plots below the SML, so it is underpriced.')
    assert not interpretation_issues('Use CAPM and the SML.','Y plots below the SML, so it is overpriced.')
    assert not interpretation_issues('Use CAPM and the SML.','Calling an asset below the SML underpriced is incorrect.')
    assert not interpretation_issues('Explain a physical graph.','The point is below the line and the item is underpriced.')


def test_required_schema_is_in_the_high_priority_system_message(monkeypatch):
    captured=[]
    class FakeModel:
        async def ainvoke(self,messages,**kwargs):
            captured.extend(messages)
            return SimpleNamespace(content='{"verdict":"valid","reason":"The stated conditions are compatible.","setup":{"evaluation_request":"","background_facts":[],"status":"feasible","witness_or_conflict":"All stated conditions coexist."}}',usage_metadata={},response_metadata={})
    monkeypatch.setattr(tools,'_get_llm',lambda *args:FakeModel())
    monkeypatch.setattr(tools,'get_settings',lambda:SimpleNamespace(base_url='https://api.deepseek.com/v1'))
    result=asyncio.run(tools._invoke_json('Check this public task.',0,tools.PublicValidity))
    assert result.verdict=='valid'
    assert captured[0].type=='system' and '"verdict"' in captured[0].content and 'required' in captured[0].content


def test_truncated_writer_retry_keeps_writer_schema_instead_of_solver_task(monkeypatch):
    captured=[]
    class LengthFinishReasonError(Exception):pass
    class FakeModel:
        async def ainvoke(self,messages,**kwargs):
            captured.append(messages)
            if len(captured)==1:raise LengthFinishReasonError('truncated')
            return SimpleNamespace(content='{"question":"What is two plus two?","question_type":"short_answer"}',usage_metadata={},response_metadata={})
    monkeypatch.setattr(tools,'_get_llm',lambda *args:FakeModel())
    monkeypatch.setattr(tools,'get_settings',lambda:SimpleNamespace(base_url='https://api.deepseek.com/v1'))
    result=asyncio.run(tools._invoke_json('Write a practice question.',0,tools.QuestionSeed))
    assert result.question=='What is two plus two?'
    retry=captured[1][-1].content
    assert 'feasibility_witness under 120 words' in retry
    assert 'Do NOT output Solver parts' in retry
    assert 'Use under 250 words of final working' not in retry


def test_invalid_public_claim_is_screened_before_expensive_solving(monkeypatch):
    import math_format,question_preflight
    async def no_op(*args,**kwargs):pass
    async def reject(*args,**kwargs):raise tools.CandidateError('Confirmed impossible public claim.')
    async def must_not_solve(*args,**kwargs):pytest.fail('Invalid public claim reached the Solver')
    monkeypatch.setattr(tools,'ensure_topic_alignment',no_op)
    monkeypatch.setattr(math_format,'check',no_op)
    monkeypatch.setattr(tools,'ensure_public_validity',reject)
    monkeypatch.setattr(question_preflight,'check',reject)
    monkeypatch.setattr(question_preflight,'_assess',reject)
    monkeypatch.setattr(tools,'solve_independently',must_not_solve)
    seed=tools.QuestionSeed(question='Prove every prime integer is odd.',question_type='proof')
    with pytest.raises(tools.CandidateError,match='Confirmed impossible'):
        asyncio.run(tools._finish_seed(seed,'Primes',[],'insane',[],'','Requested difficulty: insane'))


def test_rejected_figure_does_not_pay_for_a_second_audit(monkeypatch):
    import math_figures,math_format,originality,question_preflight
    async def no_op(*args,**kwargs):pass
    calls=[]
    async def audit(*args,**kwargs):
        calls.append(1)
        return review(difficulty_matches=False,difficulty_issue='too_easy')
    draft=tools.QuestionDraft(question='Find the requested area from the stated lengths.',question_type='calculation',
        canonical_answer='4',solution='Multiplication gives the stated area of four.')
    monkeypatch.setattr(math_figures,'eligible',lambda *a:['test'])
    monkeypatch.setattr(math_figures,'construct',lambda *a:draft)
    monkeypatch.setattr(originality,'source_copy_reason',lambda *a:'')
    monkeypatch.setattr(math_format,'check',no_op)
    monkeypatch.setattr(tools,'ensure_public_validity',no_op)
    monkeypatch.setattr(tools,'_audit_draft',audit)
    monkeypatch.setattr(question_preflight,'check',no_op)
    with pytest.raises(tools.CandidateError,match='difficulty'):
        asyncio.run(math_figures.draft_visual('Area',[{'ref':'S1','text':'Area methods.'}],'hard',['calculation'],[],''))
    assert len(calls)==1


def test_isolated_topic_guard_rejects_a_related_but_different_concept(monkeypatch):
    async def answer(*args,**kwargs):
        return tools.TopicAlignment(is_on_topic=False,tested_concept='Respiration',reason='The task does not test photosynthesis.')
    monkeypatch.setattr(tools,'_invoke_json',answer)
    with pytest.raises(tools.CandidateError,match='requested topic'):
        asyncio.run(tools.ensure_topic_alignment('Photosynthesis','Explain oxygen consumption in a respirometer as temperature changes.'))


def test_unsupported_evidence_stops_before_drafting_and_is_cached(monkeypatch):
    import writer_evidence
    calls=[]
    async def answer(*args,**kwargs):
        calls.append(1)
        return writer_evidence.EvidenceBrief(topic_supported=False,principles=[],constraints='No calculus method is established in this history passage.')
    monkeypatch.setattr(tools,'_invoke_json',answer)
    sources=[{'ref':'S1','text':'This history course covers World War II alliances.','course_id':'scope-test','chunk_id':'scope-control','source_file':'History','source_title':'History','page':1,'kind':'note'}]
    for _ in range(2):
        with pytest.raises(tools.EvidenceScopeError):
            asyncio.run(writer_evidence.writer_context('Calculus',sources,'History only.'))
    assert len(calls)==1


def test_working_checks_catch_false_intermediates_without_guessing_symbols():
    from working_checks import working_issues
    assert len(working_issues(r'$B_{27}=10000(1.005)^{81}\approx14973.54$'))==1
    assert not working_issues(r'$B_{27}=10000(1.005)^{81}\approx14977.90$')
    assert not working_issues(r'The claim $2+2=5$ is wrong.')
    assert not working_issues(r'$f(x)=a x^2$')
    assert not working_issues(r'A planar graph has $e=30$ and $2e=60$.')


def test_retrieval_matches_plural_requests_to_singular_method_evidence():
    from curriculum import terms
    assert terms('Quadratic equations') <= terms('A quadratic equation has a discriminant.')
    assert terms('Conditional probabilities') <= terms('A conditional probability is defined here.')
    assert terms('time series')==terms('time series') and 'series' in terms('time series')


def test_complex_timeout_extends_once_from_slot_acquisition(monkeypatch):
    import pipeline_runtime as runtime
    monkeypatch.setattr(runtime,'GENERATION_TIMEOUT_SECONDS',.015)
    monkeypatch.setattr(runtime,'COMPLEX_TIMEOUT_SECONDS',.07)
    async def run():
        async with runtime.generation_slot():
            runtime.set_generation_profile('insane',['proof'])
            await asyncio.sleep(.03)
            # Re-selecting the profile must not reset the original clock.
            before=runtime.TRACE.get()['timer'].when()
            runtime.set_generation_profile('insane',['proof'])
            assert runtime.TRACE.get()['timer'].when()==before
        with pytest.raises(TimeoutError):
            async with runtime.generation_slot():await asyncio.sleep(.03)
    asyncio.run(run())


def test_mcq_solver_verifier_disagreement_is_withheld(monkeypatch):
    async def premise(*a,**k):pass
    monkeypatch.setattr(tools,"ensure_public_validity",premise)
    async def check(*a):pass
    async def audit(*a,**k):return review(correct_option_index=1)
    import math_format
    monkeypatch.setattr(math_format,'check',check)
    monkeypatch.setattr(tools,'_audit_draft',audit)
    draft=tools.QuestionDraft(question='What is the value of 2+2?',question_type='mcq',
        options=['4','5','6','7'],canonical_answer='A. 4',solution='Adding two and two gives four.')
    with pytest.raises(tools.CandidateError,match='disagree on the correct option'):
        asyncio.run(tools._verify_draft(draft,independent=SimpleNamespace(missing_givens=[])))


def test_false_proof_is_rejected_without_waiting_for_a_rewritten_claim(monkeypatch):
    async def check(*a):pass
    async def audit(*a,**k):return review(public_claim_valid=False,is_consistent=False,proof_is_valid=False,corrected_question='')
    import math_format
    import question_preflight
    async def confirm(*a):
        return tools.PremiseChallenge(reason='The prime two is an admissible counterexample.',verdict='confirmed_defect')
    async def validity(*a):
        return tools.PublicValidity(setup=tools.SetupAssessment(evaluation_request='',background_facts=[],status='feasible',witness_or_conflict='Consistent test fixture conditions.'),verdict='defect',reason='The prime two is an admissible counterexample.')
    monkeypatch.setattr(tools,'ensure_public_validity',validity)
    monkeypatch.setattr(question_preflight,'challenge_defect',confirm)
    monkeypatch.setattr(math_format,'check',check)
    monkeypatch.setattr(tools,'_audit_draft',audit)
    draft=tools.QuestionDraft(question='Prove that every prime integer is odd.',question_type='proof',
        canonical_answer='Every prime integer is odd.',solution='An invalid proposed proof that ignores the prime two.')
    with pytest.raises(tools.CandidateError,match='proof claim is false'):
        asyncio.run(tools._verify_draft(draft,independent=SimpleNamespace(missing_givens=[])))

def test_valid_question_gets_fresh_blind_solve_without_reviewer_providing_a_solution(monkeypatch):
    async def premise(*a,**k):pass
    monkeypatch.setattr(tools,"ensure_public_validity",premise)
    calls=[]
    async def check(*a):pass
    async def audit(*a,**k):
        calls.append('audit')
        return review(is_consistent=calls.count('audit')>1,issues='The selected key contradicts the public arithmetic.' if calls.count('audit')==1 else '',corrected_solution='')

    async def solve(question,options,**kwargs):
        calls.append('solve');return tools.SolverAnswer(answer='A. 4',selected_option_index=0,worked_solution='Two plus two equals four.',parts=[],option_evaluations=[tools.OptionEvaluation(index=i,option_text=v,finding='Checked against the sum.',is_correct=i==0) for i,v in enumerate(['4','5','6','7'])])
    import math_format
    monkeypatch.setattr(math_format,'check',check);monkeypatch.setattr(tools,'_audit_draft',audit);monkeypatch.setattr(tools,'solve_independently',solve)
    draft=tools.QuestionDraft(question='What is two plus two?',question_type='mcq',options=['4','5','6','7'],canonical_answer='B. 5',solution='An inconsistent proposed arithmetic answer.')
    result=asyncio.run(tools._verify_draft(draft,independent=SimpleNamespace(missing_givens=[])))
    assert result.canonical_answer=='A. 4' and calls==['audit','solve','audit']

def test_positive_audit_cannot_also_report_a_material_defect():
    with pytest.raises(ValidationError,match='approved audit'):review(issues='The keyed option is wrong and no option is correct.')
