import asyncio
import pytest
import app, auth, db, learning_store as store
from tests.test_learning_workflows import course, add_bank


def test_completed_paper_summary_and_private_key_boundary(client, course):
    add_bank(course,'Find the real solution of $11x=22$.')
    add_bank(course,'Find the real solution of $13x=26$.')
    r=client.post('/bank-exams',json={'course_id':course,'count':2})
    assert r.status_code==200,r.text
    paper=r.json();identifier=paper['id']
    assert paper['summary'] is None
    assert client.get(f'/bank-exams/{identifier}/summary/export').status_code==409
    thread=paper['question']['thread_id']
    asyncio.run(app.graph.aupdate_state(app._config(thread),{'status':'correct','user_attempts':1}))
    r=client.post(f'/bank-exams/{identifier}/next');assert r.status_code==200,r.text
    thread=r.json()['question']['thread_id']
    asyncio.run(app.graph.aupdate_state(app._config(thread),{'status':'revealed','user_attempts':3}))
    r=client.get('/bank-exams/'+identifier)
    summary=r.json()['summary']
    assert (summary['solved'],summary['total'],summary['first_attempt_correct'],summary['needs_review'],summary['attempts'])==(1,2,1,1,4)
    assert summary['solved_percent']==50
    assert all('canonical_answer' not in row and 'solution' not in row for row in summary['questions'])
    export=client.get(f'/bank-exams/{identifier}/summary/export')
    assert export.status_code==200 and 'Solved: 1 / 2' in export.text


def test_safe_stage_reason_preserves_diagnosis_without_trace():
    from generation_errors import describe
    from tools import CandidateError
    error=CandidateError('The question did not match the requested topic.')
    error.pipeline_stage='verifier'
    payload,status=describe(error)
    assert status==422 and payload['stage']=='verifier'
    assert payload['reason']==str(error)
    secret=RuntimeError('Bearer sk-PRIVATE-SECRET in C:\\private\\backend.py Traceback')
    secret.pipeline_stage='writer'
    payload,status=describe(secret)
    assert payload['stage']=='writer' and 'sk-' not in str(payload) and 'backend.py' not in str(payload)


def test_timeout_names_the_active_stage():
    from generation_errors import describe
    error=TimeoutError();error.pipeline_stage='solver'
    payload,status=describe(error)
    assert status==504 and payload['stage']=='solver'
    assert payload['code']=='generation_timeout'
