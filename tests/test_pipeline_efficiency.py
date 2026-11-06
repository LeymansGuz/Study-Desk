import asyncio
from types import SimpleNamespace
import pytest
from langchain_core.messages import AIMessage
import tools,providers,pipeline_runtime as runtime

def model_fixture(monkeypatch,responses):
    requests=[]
    class Model:
        async def ainvoke(self,messages,**kwargs):
            requests.append((messages,kwargs));return responses[len(requests)-1]
    monkeypatch.setattr(providers,'snapshot',lambda:None)
    monkeypatch.setattr(tools,'_get_llm',lambda *a:Model())
    monkeypatch.setattr(tools,'get_settings',lambda:SimpleNamespace(base_url='https://api.deepseek.com/v1'))
    return requests

def test_provider_length_uses_one_compact_retry_at_the_same_output_limit(monkeypatch):
    requests=model_fixture(monkeypatch,[AIMessage(content='{"question":',response_metadata={'finish_reason':'length'}),AIMessage(content='{"question":"Calculate two plus two.","question_type":"calculation"}',response_metadata={'finish_reason':'stop'})])
    result=asyncio.run(tools._invoke_json('Write a practice question.',0,tools.QuestionSeed))
    assert result.question=='Calculate two plus two.' and len(requests)==2
    assert requests[0][1]['max_tokens']==requests[1][1]['max_tokens']
    assert 'previous response exceeded' in requests[1][0][-1].content.lower()

def test_repeated_truncation_is_withheld_after_only_one_retry(monkeypatch):
    requests=model_fixture(monkeypatch,[AIMessage(content='{"question":',response_metadata={'finish_reason':'length'})]*2)
    from generation_errors import StageFailure
    with pytest.raises(StageFailure,match='compact result'):asyncio.run(tools._invoke_json('Write a question.',0,tools.QuestionSeed))
    assert len(requests)==2

def test_hard_writer_has_room_for_the_required_method_plan(monkeypatch):
    requests=model_fixture(monkeypatch,[AIMessage(content='{"question":"Calculate two plus two.","question_type":"calculation"}',response_metadata={'finish_reason':'stop'})])
    asyncio.run(tools._invoke_json('For HARD include method_plan with exactly two or three dependent decisions.',0,tools.QuestionSeed))
    assert requests[0][1]['max_tokens']==2600
    assert tools.GENERATOR_SYSTEM in requests[0][0][0].content

def test_solver_reports_final_selection_after_its_worked_solution():
    fields=list(tools.SolverAnswer.model_fields)
    assert fields.index('reasoning')<fields.index('selected_option_index')<fields.index('answer')
    assert 'never unasked intermediate' in tools.SolverAnswer.SYSTEM_PROMPT
    alias=tools.SolverAnswer.model_validate({'final_answer':'4','worked_solution':'The complete addition gives four.','parts':[]})
    assert alias.answer=='4'

def test_solver_receives_one_complete_user_task_not_a_trailing_rules_only_message(monkeypatch):
    requests=model_fixture(monkeypatch,[AIMessage(content='{"answer":"4","worked_solution":"Adding two and two gives four.","parts":[]}',response_metadata={'finish_reason':'stop'})])
    asyncio.run(tools._invoke_json('PUBLIC QUESTION: What is two plus two?',0,tools.SolverAnswer))
    users=[message for message in requests[0][0] if message.type=='human']
    assert len(users)==1
    assert 'Calculator contract:' in users[0].content and users[0].content.endswith('PUBLIC QUESTION: What is two plus two?')

def test_invalid_math_is_rejected_before_paying_for_topic_check(monkeypatch):
    import math_format
    calls=[]
    async def invalid(*a):raise tools.CandidateError('Invalid mathematical formatting.')
    async def paid(*a):calls.append(1)
    monkeypatch.setattr(math_format,'check',invalid)
    monkeypatch.setattr(tools,'ensure_topic_alignment',paid)
    seed=tools.QuestionSeed(question='Calculate an invalid $ expression.',question_type='calculation')
    with pytest.raises(tools.CandidateError):asyncio.run(tools._finish_seed(seed,'Arithmetic',[],'medium',[],'',''))
    assert not calls

def test_stage_profile_records_elapsed_intervals_without_prompt_text(monkeypatch):
    now=iter([1.,3.]);monkeypatch.setattr(runtime.time,'perf_counter',lambda:next(now))
    trace={'stage':'retrieval','stage_started':0.};token=runtime.TRACE.set(trace)
    try:
        runtime.mark_stage('writer');runtime.mark_stage('solver')
        assert trace['stage_ms']=={'retrieval':1000.,'writer':2000.}
        assert trace['stage']=='solver' and 'prompt' not in trace
    finally:runtime.TRACE.reset(token)
