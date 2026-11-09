"""A correct local answer cannot certify an impossible background scenario."""
import asyncio
import pytest
from pydantic import ValidationError
import tools
import question_preflight as preflight
from premise_checks import SetupAssessment, validate_setup


def certificate(status='feasible', **updates):
    updates.setdefault('evaluation_request','')
    return SetupAssessment(background_facts=[],status=status, witness_or_conflict='All asserted conditions have a joint interpretation.', **updates)


def test_missing_or_unresolved_scenario_never_counts_as_approval():
    for value in [None, certificate('uncertain'), certificate('inconsistent')]:
        with pytest.raises(tools.CandidateError) as caught:
            validate_setup(value, 'Compute the requested local answer.')
        assert caught.value.pipeline_stage == 'premise'
    with pytest.raises(ValidationError):
        tools.PublicValidity(verdict='valid', reason='The local target is answerable.')


def test_only_an_exact_public_diagnosis_request_allows_inconsistent_background():
    request='Explain why this pedigree is impossible.'
    diagnosis=certificate('inconsistent', evaluation_request=request)
    assert validate_setup(diagnosis, 'The stated family has conflicting genotypes. '+request) is diagnosis
    with pytest.raises(tools.CandidateError):
        validate_setup(diagnosis, 'Which genotype does the daughter have?')
    assert validate_setup(certificate(), 'Solve this equation, allowing no solution.')


def test_valid_target_verdict_does_not_override_impossible_setup(monkeypatch):
    async def invoke(*args):
        return tools.PublicValidity(verdict='valid', reason='The daughter genotype is still calculable.',
            setup=certificate('inconsistent'))
    monkeypatch.setattr(tools, '_invoke_json', invoke)
    question='An affected son has a non-carrier mother under ordinary X-linked inheritance. Test-only.'
    with pytest.raises(tools.CandidateError, match='cannot all hold'):
        asyncio.run(tools.ensure_public_validity(question))
    assert (question, ()) not in tools._PUBLIC_VALIDITY_CACHE


def test_preflight_rejects_impossible_setup_before_solver_or_source_approval(monkeypatch):
    async def invoke(*args):
        return preflight.QuestionPreflight(setup=certificate('inconsistent'), verdict='valid',
            reason='The requested value can still be computed.', is_on_topic=True, tested_concept='Inheritance',
            is_grounded=True, repeats_recent_task=False, source_clone=False, originality_reason='Original task.')
    monkeypatch.setattr(tools, '_invoke_json', invoke)
    async def joint(assessment,*args):validate_setup(assessment,args[0])
    monkeypatch.setattr(preflight,'ensure_joint_setup',joint)
    monkeypatch.setattr(tools,'evidence_support_issue',lambda *a:'')
    with pytest.raises(tools.CandidateError, match='cannot all hold'):
        asyncio.run(preflight.check('Inheritance', 'Contradictory parent genotypes. Test-only preflight.', [], []))


def test_original_objection_is_preserved_and_withdrawal_requires_fresh_approval(monkeypatch):
    seen=[]
    async def invoke(prompt, temperature, schema):
        return tools.PublicValidity(verdict='valid',reason='All givens coexist.', setup=certificate())
    async def challenge(question, options, allegation):
        seen.append(allegation)
        return tools.PremiseChallenge(verdict='uncertain', reason='The original conflict has not been resolved.')
    monkeypatch.setattr(tools, '_invoke_json', invoke)
    monkeypatch.setattr(preflight, 'challenge_defect', challenge)
    with pytest.raises(tools.CandidateError, match='could not be established'):
        asyncio.run(tools.ensure_public_validity('A new disputed setup.', allegation='The family violates inheritance.'))
    assert seen == ['The family violates inheritance.']


def test_final_draft_gate_runs_before_a_favorable_answer_review(monkeypatch):
    calls=[]
    async def reject(*args, **kwargs):
        calls.append('setup')
        validate_setup(certificate('inconsistent'), args[0])
    async def forbidden(*args, **kwargs):
        pytest.fail('An impossible final draft reached the answer reviewer.')
    monkeypatch.setattr(tools, 'ensure_public_validity', reject)
    monkeypatch.setattr(tools, '_audit_draft', forbidden)
    draft=tools.QuestionDraft(question='A closed system loses no mass: 2 g plus 3 g produces 6 g. What is 2+3?',
        question_type='short_answer', canonical_answer='5', solution='Add the reactant masses to get 5.')
    with pytest.raises(tools.CandidateError):
        asyncio.run(tools._verify_draft(draft))
    assert calls == ['setup']


def test_receipt_exposes_only_the_boolean_not_private_feasibility_notes():
    from verification_metadata import public_fields
    assert public_fields({'premise_passed':True,'witness_or_conflict':'private', 'key':'secret'}) == {'premise_passed':True}


def test_target_blind_review_catches_a_conflict_despite_positive_first_review(monkeypatch):
    import premise_checks as checks
    question='At steady state there is no storage. Inflow is 3 plus 2; outflow is 6. Compute the easy local target.'
    assessment=certificate().model_copy(update={'background_facts':[
        'At steady state there is no storage.', 'Inflow is 3 plus 2; outflow is 6.']})
    seen=[]
    async def invoke(prompt,temperature,schema):
        seen.append(prompt)
        assert schema is checks.IndependentSetup
        assert 'Compute the easy local target' not in prompt
        assert 'Inflow is 3 plus 2; outflow is 6.' in prompt
        return checks.IndependentSetup(witness_or_conflict='Steady state with no storage requires outflow 5, not 6.',status='inconsistent')
    monkeypatch.setattr(tools,'_invoke_json',invoke)
    checks._JOINT_CACHE.clear()
    with pytest.raises(tools.CandidateError,match='cannot all hold'):
        asyncio.run(checks.ensure_joint_setup(assessment,question))
    assert len(seen)==1


def test_no_scenario_does_not_add_a_call_and_source_rules_are_not_public_data(monkeypatch):
    import premise_checks as checks
    async def forbidden(*a):pytest.fail('A task without an asserted scenario incurred a duplicate review.')
    monkeypatch.setattr(tools,'_invoke_json',forbidden)
    assessment=certificate()
    assert asyncio.run(checks.ensure_joint_setup(assessment,'Define a concept.')) == assessment
    with_source=assessment.model_copy(update={'background_facts':['A source-only definition.']})
    filtered=checks.public_fact_ledger(with_source,'Define a concept.',[{'text':'A source-only definition.'}])
    assert filtered.background_facts == []
    with pytest.raises(tools.CandidateError):checks.public_fact_ledger(with_source,'Define a concept.')


def test_clipped_claim_keeps_its_original_qualifier():
    from premise_checks import public_fact_ledger
    task='Evaluate the claim: every prime integer is odd. Which statement is correct?'
    value=certificate().model_copy(update={'background_facts':['every prime integer is odd']})
    scoped=public_fact_ledger(value,task)
    assert scoped.background_facts == ['Evaluate the claim: every prime integer is odd.']
    assert 'Which statement' not in scoped.background_facts[0]


def test_cached_joint_witness_cannot_erase_an_original_conflict(monkeypatch):
    import premise_checks as checks
    import hashlib,json
    question='A test-only object has mutually disputed stated constraints.'
    assessment=certificate('inconsistent').model_copy(update={'background_facts':[question]})
    key=hashlib.sha256(json.dumps([question],ensure_ascii=False).encode()).hexdigest()
    checks._JOINT_CACHE[key]=checks.IndependentSetup(status='feasible',witness_or_conflict='A disputed witness is proposed.')
    async def invoke(prompt,temperature,schema):
        assert schema is tools.PremiseChallenge
        return tools.PremiseChallenge(verdict='confirmed_defect',reason='The proposed witness does not meet both constraints.')
    monkeypatch.setattr(tools,'_invoke_json',invoke)
    with pytest.raises(tools.CandidateError,match='could not be established'):
        asyncio.run(checks.ensure_joint_setup(assessment,question))


def test_inconsistency_has_a_safe_specific_user_message():
    from generation_errors import describe
    try:
        validate_setup(certificate('inconsistent'), 'An ordinary local target.')
    except tools.CandidateError as error:
        response, status=describe(error)
    assert status == 422 and response['stage'] == 'premise'
    assert 'cannot all hold together' in response['reason']
    assert 'Traceback' not in response['error']


def test_free_brief_explanations_can_validate_premises_without_enabling_generation(client, monkeypatch):
    import json
    import providers
    from types import SimpleNamespace
    calls=[]
    class Model:
        async def ainvoke(self, *args, **kwargs):
            calls.append(1)
            payload=tools.PublicValidity(verdict='valid', reason='A consistent example.',setup=certificate())
            return SimpleNamespace(content=json.dumps(payload.model_dump()),usage_metadata={},response_metadata={})
    monkeypatch.setattr(providers.Model,'ainvoke',Model.ainvoke)
    token=providers.ACTIVE.set(providers.Connection('openrouter','fixture/free:free',
        providers.DEFINITIONS['openrouter'][1],'offline',(0,0,0)))
    try:
        assert asyncio.run(tools._invoke_json('Check an explanation example.',0,tools.PublicValidity)).verdict == 'valid'
        from generation_errors import StageFailure
        with pytest.raises(StageFailure,match="restricted"):
            asyncio.run(tools._invoke_json('Generate a practice question.',0,tools.QuestionSeed))
    finally:
        providers.ACTIVE.reset(token)
    assert calls == [1]
