"""Feedback-derived regression checks, without provider calls or private records."""
import pytest
from answer_parts import MathClaim, SolvedPart
from math_checks import check_claim
from assessment_level import contract, POLICY_VERSION

@pytest.mark.parametrize('answer,expected', [('(exp(2)-3)/2','passed'),('(exp(2)-1)/2','failed')])
def test_definite_integral_keeps_lower_endpoint(answer,expected):
    claim=MathClaim(kind='definite_integral',left='x*exp(x*y)',right=answer,
                    variables=['x','y'],bounds=[['y','0','2'],['x','0','1']])
    assert check_claim(claim.model_dump())['status']==expected

def test_ordered_variable_bounds_and_jacobian():
    claim={'kind':'definite_integral','left':'r**3','right':'4*pi',
           'variables':['r','t'],'bounds':[['r','0','2'],['t','0','pi']]}
    assert check_claim(claim)['status']=='passed'
    claim['right']='2*pi'
    assert check_claim(claim)['status']=='failed'

def test_self_dependent_bound_is_not_evaluated():
    with pytest.raises(ValueError):
        check_claim({'kind':'definite_integral','left':'x','right':'1','variables':['x'],'bounds':[['x','0','x']]})

def test_incorrect_supplied_integral_shortcut_is_detected():
    claim={'kind':'definite_integral','left':'cos(t)**4','right':'(9*pi+8*sqrt(3))/48',
           'variables':['t'],'bounds':[['t','0','pi/3']]}
    assert check_claim(claim)['status']=='failed'

def test_insane_is_dependent_reasoning_not_more_parts():
    text=contract('insane',[],question_type='long_answer')
    assert POLICY_VERSION>=12
    assert 'one bounded insight' in text
    assert 'later reasoning must use an earlier conclusion' in text
    assert 'MAXIMUM of 2 parts' in text
    medium=contract('medium',[])
    assert 'at most two dependent reasoning decisions' in medium
    assert 'one coherent setup' in medium

def test_independent_checker_rejects_wrong_integral(monkeypatch):
    from math_checks import verify_claims
    part=SolvedPart(kind='symbolic',answer='A claimed result',checks=[MathClaim(kind='definite_integral',left='x',right='1',variables=['x'],bounds=[['x','0','1']])])
    assert verify_claims([part])[0]['status']=='failed'

def test_shuffle_remaps_prose_without_changing_mathematical_labels(monkeypatch):
    import tools
    draft=tools.QuestionDraft(question='Which option gives the stated result?',question_type='mcq',
          options=['A. First body','B. Second body','C. Third body','D. Fourth body'],
          canonical_answer='A. First body',solution='The matrix $A$ is invertible. Only A is correct; option B is wrong.\nFinal answer: A. First body')
    monkeypatch.setattr(tools.random.SystemRandom,'shuffle',lambda self,items:items.reverse())
    tools.shuffle_choice_draft(draft)
    assert draft.canonical_answer=='D. First body'
    assert 'Only D is correct; option C is wrong.' in draft.solution
    assert '$A$' in draft.solution
    assert draft.options==['Fourth body','Third body','Second body','First body']
