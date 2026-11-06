import asyncio,threading,time
from concurrent.futures import ThreadPoolExecutor
import pytest
from answer_parts import SolvedPart,MathClaim
import tools

def test_working_repair_cannot_change_the_key_or_hide_another_wrong_equality(monkeypatch):
    import working_repair
    async def clean(*a):return 'Adding the two quantities gives $2+2=4$.'
    monkeypatch.setattr(working_repair,'repair',clean)
    solved=tools.SolverAnswer(answer='4',worked_solution='Adding the two quantities gives $2+2=5$.',parts=[SolvedPart(kind='numeric',expression='2+2')])
    draft=tools.QuestionDraft(question='Calculate two plus two.',question_type='calculation',canonical_answer='4',solution='The independent solution is awaiting checks.')
    asyncio.run(tools._use_solution_checked(draft,solved))
    assert draft.canonical_answer=='4' and draft.answer_parts[0].value==4
    async def bad(*a):return 'The resulting sum is $2+2=7$.'
    monkeypatch.setattr(working_repair,'repair',bad)
    with pytest.raises(tools.CandidateError,match='displayed calculation'):asyncio.run(tools._use_solution_checked(draft,solved))

def test_parallel_auditors_share_one_request_local_symbolic_calculation(monkeypatch):
    import math_checks,pipeline_runtime
    calls=[];started=threading.Event()
    def calculate(parts):calls.append(1);started.set();time.sleep(.03);return [{'status':'unresolved','reason':'Needs independent proof review.'}]
    monkeypatch.setattr(math_checks,'_verify_claims',calculate)
    shared={};parts=[SolvedPart(kind='symbolic',checks=[MathClaim(left='x+x',right='2*x')])]
    def invoke():
        token=pipeline_runtime.LOCAL_CHECKS.set(shared)
        try:return math_checks.verify_claims(parts)
        finally:pipeline_runtime.LOCAL_CHECKS.reset(token)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(invoke);assert started.wait(1);second=pool.submit(invoke)
        assert first.result()==second.result()
    assert len(calls)==1

def test_context_prefers_topical_support_over_unrelated_exam_neighbors():
    import curriculum
    anchor={'chunk_id':'a','text':'A coordinate geometry problem uses the distance between two points.'}
    useful={'chunk_id':'u','text':'The coordinate distance formula is sqrt((x2-x1)**2+(y2-y1)**2).'}
    unrelated={'chunk_id':'b','text':'Probability of independent coin tosses.'}
    catalog={'sections':[{'id':'exam','course_id':'c','source_file':'paper.pdf','doc_type':'past_paper','sources':[anchor,unrelated]}, {'id':'notes','course_id':'c','source_file':'notes.pdf','doc_type':'notes','sources':[useful]}, {'id':'blocked','course_id':'c','source_file':'hidden.pdf','doc_type':'notes','excluded':True,'sources':[{'chunk_id':'bad','text':'Coordinate distance formula.'}]}]}
    unit={**catalog['sections'][0],'keywords':['coordinate','distance']}
    rows=curriculum.topical_evidence(catalog,unit,{'coordinate','distance'},{'notes','past_paper'},[useful,anchor])
    assert rows[0]['chunk_id']=='u' and 'b' not in [r['chunk_id'] for r in rows] and 'bad' not in [r['chunk_id'] for r in rows]
    assert all(r['chunk_id']!='u' for r in curriculum.topical_evidence(catalog,unit,{'coordinate'},{'past_paper'},[useful]))

def test_numeric_binding_catches_a_wrong_metadata_value_appended_to_a_correct_coordinate():
    from answer_parts import Calculation,evaluate_parts,numeric_binding_issues
    bad=evaluate_parts([SolvedPart(kind='mixed',answer=r'$P=(-\frac{13}{5},0)=(-2.6,0)$; no second point exists.',calculations=[Calculation(name='x_coordinate',expression='13/3')])])
    assert numeric_binding_issues(bad)
    good=evaluate_parts([SolvedPart(kind='mixed',answer=r'$P=(-\frac{13}{5},0)=(-2.6,0)$; no second point exists.',calculations=[Calculation(name='x_coordinate',expression='-13/5')])])
    assert not numeric_binding_issues(good)
    assert numeric_binding_issues(evaluate_parts([SolvedPart(kind='numeric',answer='$5$',expression='4')]))
    assert not numeric_binding_issues(evaluate_parts([SolvedPart(kind='numeric',answer='$0.33$',expression='1/3')]))
    assert not numeric_binding_issues(evaluate_parts([SolvedPart(kind='numeric',answer=r'$925.47\,\mathrm{USD}$',expression='500*1.08**8')]))
    assert not numeric_binding_issues(evaluate_parts([SolvedPart(kind='numeric',answer=r'$6.17\%$',expression='((1+.06/12)**12-1)*100')]))

def test_exhaustive_boolean_checks_reject_wrong_classifications_and_unsafe_code():
    from math_checks import check_claim
    formula='Equivalent(Equivalent(p,q),Equivalent(p,Not(q)))'
    assert check_claim({'kind':'boolean','left':formula,'right':'False','variables':['p','q']})['status']=='passed'
    assert check_claim({'kind':'boolean','left':formula,'right':'Xor(p,q)','variables':['p','q']})['status']=='failed'
    assert check_claim({'kind':'boolean','left':'Implies(p,q)','right':'Or(Not(p),q)','variables':['p','q']})['status']=='passed'
    with pytest.raises(ValueError):check_claim({'kind':'boolean','left':'__import__("os")','right':'False','variables':['p']})

def test_mcq_cannot_silently_rewrite_an_option_into_a_true_statement():
    options=['False exactly when inputs agree.','False only in one row.','Always true.','Sometimes true.']
    solved=tools.SolverAnswer(answer='A. Always false.',selected_option_index=0,worked_solution='The proposition is false in every valuation.',option_evaluations=[tools.OptionEvaluation(index=i,option_text='Always false.' if i==0 else option,finding='A proposed finding.',is_correct=i==0) for i,option in enumerate(options)])
    draft=tools.QuestionDraft(question='Which option describes this proposition?',question_type='mcq',options=options,canonical_answer='pending',solution='Pending independent checks.')
    with pytest.raises(tools.CandidateError,match='rewrote'):tools._use_solution(draft,solved)

def test_supplied_question_cannot_be_returned_with_repaired_public_options(monkeypatch):
    import db,providers,supplied_questions,math_format
    db.init_db();monkeypatch.setattr(providers,'snapshot',lambda:None)
    options=['4','5','6','7']
    monkeypatch.setattr(supplied_questions,'classify',lambda *a:('mcq','What is two plus two?',options))
    async def solve(*a,**k):return tools.SolverAnswer(answer='A. 4',selected_option_index=0,worked_solution='Adding the two quantities gives four.',option_evaluations=[tools.OptionEvaluation(index=i,option_text=v,finding='Checked literal value.',is_correct=i==0) for i,v in enumerate(options)])
    async def verify(draft,**k):return draft.model_copy(update={'options':['A changed option','5','6','7']})
    async def check(*a):pass
    monkeypatch.setattr(tools,'solve_independently',solve);monkeypatch.setattr(tools,'_verify_draft',verify);monkeypatch.setattr(tools,'VERIFY_ANSWERS',True);monkeypatch.setattr(math_format,'check',check)
    with pytest.raises(tools.CandidateError,match='original input'):asyncio.run(tools.prepare_assignment_question('What is two plus two? A.4 B.5 C.6 D.7'))
