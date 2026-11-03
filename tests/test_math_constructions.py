import pytest
from advanced_math_figures import integration,geometry
from math_format import validate_fields
from working_checks import working_issues


@pytest.mark.parametrize('family,level',[('double_integral','hard'),('double_integral','insane'),('triple_integral','hard'),('triple_integral','insane')])
def test_integration_working_matches_the_selected_tasks(family,level):
    draft=integration(family,level,'long_answer',7)
    validate_fields((draft.question,draft.solution,draft.canonical_answer))
    assert not working_issues(draft.solution)
    if level=='hard':
        assert 'cut is unique' not in draft.solution and 'fraction of the total mass' not in draft.solution
    if family=='double_integral':
        assert 'transformed region' not in draft.solution
    if family=='triple_integral' and level=='insane':
        assert 'cumulative mass is strictly increasing' in draft.solution


def test_circle_second_configuration_is_explicit_and_working_is_derived():
    draft=geometry('circle','insane','calculation',7)
    assert 'PA is allowed to change' in draft.question
    assert 'Semiperimeter' not in draft.solution
    assert 'triangle area is' in draft.solution
    validate_fields((draft.question,draft.solution,draft.canonical_answer))
