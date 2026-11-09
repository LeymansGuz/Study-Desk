import asyncio
from types import SimpleNamespace
import pytest
import tools,providers,pipeline_runtime as runtime
import question_preflight as preflight

def test_independent_checks_borrow_spare_capacity_but_never_exceed_global_limit(monkeypatch):
    monkeypatch.setenv('MAX_CONCURRENT_LLM','3');monkeypatch.setattr(providers,'snapshot',lambda:None)
    async def run():
        active=0;peak=0
        async def check():
            nonlocal active,peak
            async with runtime.model_slot('test'):
                active+=1;peak=max(peak,active);await asyncio.sleep(.02);active-=1
        async with runtime.generation_slot():await asyncio.gather(check(),check())
        assert peak==2 and runtime.current_gate().active==0
    asyncio.run(asyncio.wait_for(run(),2))

def test_saturated_workflows_share_reserved_slots_without_deadlock(monkeypatch):
    monkeypatch.setenv('MAX_CONCURRENT_LLM','5');monkeypatch.setattr(providers,'snapshot',lambda:None)
    async def run():
        ready=asyncio.Event();started=0;active=0;peak=0
        async def check():
            nonlocal active,peak
            async with runtime.model_slot('test'):
                active+=1;peak=max(peak,active);await asyncio.sleep(.01);active-=1
        async def flow():
            nonlocal started
            async with runtime.generation_slot():
                started+=1
                if started==5:ready.set()
                await ready.wait();await asyncio.gather(check(),check())
        await asyncio.gather(*(flow() for _ in range(5)))
        assert peak<=5 and runtime.current_gate().active==0
    asyncio.run(asyncio.wait_for(run(),3))

def test_cancellation_releases_parallel_owned_and_borrowed_slots(monkeypatch):
    monkeypatch.setenv('MAX_CONCURRENT_LLM','2');monkeypatch.setattr(providers,'snapshot',lambda:None)
    async def run():
        async def check():
            async with runtime.model_slot('test'):await asyncio.sleep(10)
        async with runtime.generation_slot():
            tasks=[asyncio.create_task(check()) for _ in range(3)];await asyncio.sleep(.02)
            for task in tasks:task.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)
            assert runtime.current_gate().active==1
        assert runtime.current_gate().active==0
    asyncio.run(asyncio.wait_for(run(),2))

def test_blind_method_check_rejects_a_related_heading_without_required_theorem(monkeypatch):
    async def invoke(*a):return preflight.QuestionPreflight(setup=tools.SetupAssessment(evaluation_request='',background_facts=[],status='feasible',witness_or_conflict='Consistent test fixture conditions.'),reason='The required theorem is absent; a related heading is insufficient.',verdict='valid',source_clone=False,repeats_recent_task=False,originality_reason='No source exercise is reproduced.',is_on_topic=True,tested_concept='Test-only geometry',is_grounded=False)
    monkeypatch.setattr(tools,'_invoke_json',invoke)
    with pytest.raises(tools.EvidenceScopeError,match='not supported'):
        asyncio.run(preflight.check('Test-only geometry','Prove a result needing an absent theorem.',[],[{'ref':'S1','source_title':'Notes','kind':'notes','page':1,'text':'A related general geometry heading, without the theorem.'}]))

def test_unverifiable_preflight_quotes_still_fail_after_bounded_repair(monkeypatch):
    calls=[]
    async def invoke(*a):
        calls.append(1)
        return preflight.QuestionPreflight(setup=tools.SetupAssessment(evaluation_request='',background_facts=[],status='feasible',witness_or_conflict='Consistent test fixture conditions.'),reason='Claimed support.',verdict='valid',source_clone=False,repeats_recent_task=False,originality_reason='No source exercise is reproduced.',is_on_topic=True,tested_concept='Test-only method',is_grounded=True,used_source_refs=['S1'],evidence_support=[tools.EvidenceSupport(method='An absent method',source_ref='S1',quote='A quotation which is not in the source.')])
    monkeypatch.setattr(tools,'_invoke_json',invoke)
    with pytest.raises(tools.EvidenceScopeError):asyncio.run(preflight.check('Test-only method','Use the absent method.',[],[{'ref':'S1','source_title':'Notes','kind':'notes','page':1,'text':'Only another unrelated method is defined.'}]))
    assert len(calls)==2


def test_parallel_reviews_share_one_blind_premise_check(monkeypatch):
    calls=[]
    async def premise(question,options):calls.append('premise');return tools.PublicValidity(setup=tools.SetupAssessment(evaluation_request='',background_facts=[],status='feasible',witness_or_conflict='Consistent test fixture conditions.'),verdict='valid',reason='Complete public premises.')
    async def audit(draft,*a):calls.append('audit');return object()
    monkeypatch.setattr(tools,'ensure_public_validity',premise)
    monkeypatch.setattr(tools,'_audit_draft',audit)
    draft=tools.QuestionDraft(question='Prove the stated identity for all real x.',question_type='proof',canonical_answer='The two expressions agree.',solution='Expand and collect equal terms under the given hypotheses.')
    values=asyncio.run(preflight.paired_audits(draft,[], '', '', None))
    assert len(values)==2 and calls==['premise','audit','audit']


def test_scenario_review_and_solver_overlap_but_both_must_complete(monkeypatch):
    async def run():
        checking=asyncio.Event();solving=asyncio.Event()
        async def assess(*args):return object()
        async def approve(*args):
            checking.set();await solving.wait();return object()
        async def solve(*args,**kwargs):
            solving.set();await checking.wait();return 'independent answer'
        monkeypatch.setattr(preflight,'_assess',assess)
        monkeypatch.setattr(preflight,'_approve',approve)
        monkeypatch.setattr(tools,'solve_independently',solve)
        seed=tools.QuestionSeed(question='A supported public task.',question_type='short_answer')
        assert await preflight.solve_checked(seed,'Topic',[])=='independent answer'
    asyncio.run(asyncio.wait_for(run(),1))


def test_failed_joint_check_cancels_the_parallel_solver(monkeypatch):
    async def run():
        solving=asyncio.Event();cancelled=asyncio.Event()
        async def assess(*args):return object()
        async def approve(*args):
            await solving.wait();raise tools.CandidateError('Impossible background.')
        async def solve(*args,**kwargs):
            solving.set()
            try:await asyncio.sleep(10)
            finally:cancelled.set()
        monkeypatch.setattr(preflight,'_assess',assess)
        monkeypatch.setattr(preflight,'_approve',approve)
        monkeypatch.setattr(tools,'solve_independently',solve)
        seed=tools.QuestionSeed(question='An impossible public task.',question_type='short_answer')
        with pytest.raises(tools.CandidateError):await preflight.solve_checked(seed,'Topic',[])
        assert cancelled.is_set()
    asyncio.run(asyncio.wait_for(run(),1))
