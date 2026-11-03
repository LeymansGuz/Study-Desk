"""Small independent reference suite across domains, with no model calls.

The built-in answers are hand-worked reference facts. Passing these cases does
not establish the correctness of every generated question in a real course.
"""
import time
from answer_parts import SolvedPart, evaluate_parts, verified_numeric_parts
from math_checks import check_claim
from public_rubric import rubric

def run_reference():
    started = time.perf_counter()
    cases = []

    def case(name, operation, expected):
        start = time.perf_counter()
        try:
            actual = operation()
            passed = actual == expected
            error = ''
        except Exception as exc:
            actual, passed, error = (None, False, type(exc).__name__)
        cases.append({'name': name, 'passed': passed, 'expected': expected, 'actual': actual, 'error': error, 'seconds': round(time.perf_counter() - start, 4)})
    from calc import evaluate, solve_equation
    case('Compound growth: 100 at 10% for two years', lambda: round(evaluate('100*1.1**2'), 6), 121.0)
    case('Cash-flow discounting: 121 due in two years at 10%', lambda: round(evaluate('121/1.1**2'), 6), 100.0)
    case('Root substitution: x^2 - 4 on [0,3]', lambda: round(solve_equation('x**2-4', 'x', 0, 3), 5), 2.0)
    case('Derivative of x^3', lambda: check_claim({'kind': 'derivative', 'left': 'x**3', 'right': '3*x**2'})['status'], 'passed')
    case('Calculus: antiderivative checked by differentiation', lambda: check_claim({'kind': 'integral', 'left': '2*x', 'right': 'x**2+5'})['status'], 'passed')
    case('Calculus: incorrect antiderivative is rejected', lambda: check_claim({'kind': 'integral', 'left': '2*x', 'right': 'x**3'})['status'], 'failed')
    case('Matrices: product respects row-column order', lambda: check_claim({'kind': 'matrix', 'left': '[[1,2],[3,4]]*[[2],[1]]', 'right': '[[4],[10]]'})['status'], 'passed')
    case('Matrices: wrong dimensions are rejected', lambda: check_claim({'kind': 'matrix', 'left': '[[1,2]]', 'right': '[[1],[2]]'})['status'], 'failed')
    case('Wrong derivative must fail', lambda: check_claim({'kind': 'derivative', 'left': 'x**3', 'right': '3*x'})['status'], 'failed')
    case('Absolute value is not x on the real line', lambda: check_claim({'left': 'abs(x)', 'right': 'x'})['status'], 'failed')
    case('Boundary counterexample to sqrt(x^2)=x', lambda: check_claim({'left': 'sqrt(x**2)', 'right': 'x'})['status'], 'failed')
    case('Equivalent expressions still require denominator review', lambda: check_claim({'left': '(x**2-1)/(x-1)', 'right': 'x+1'})['domain_review_required'], True)
    case('A proof explicitly requires justification', lambda: rubric('Prove that the sum of two even integers is even.')[0]['mode'], 'justification')
    case('A value-only question must not require working', lambda: rubric('Calculate 2 + 3.')[0]['mode'], 'answer')
    parts = evaluate_parts([SolvedPart(label='a', expression='2+3'), SolvedPart(label='b', expression='3*4')])
    case('All correct multipart values get full credit', lambda: verified_numeric_parts('(a) Calculate 2+3. (b) Calculate 3*4.', '(a) 5 (b) 12', parts, []) is not None, True)
    case('A wrong multipart value cannot get full credit', lambda: verified_numeric_parts('(a) Calculate 2+3. (b) Calculate 3*4.', '(a) 5 (b) 13', parts, []) is not None, False)
    case('Intermediate numbers do not bypass requested proof', lambda: verified_numeric_parts('(a) Show your working for 2+3. (b) Show your working for 3*4.', '(a) 5 (b) 12', parts, []) is not None, False)
    import curriculum
    case('Optional extension is outside assessed scope', lambda: bool(curriculum.NOT_ASSESSED.search('Optional extension: stochastic calculus')), True)
    case('Calculator instructions are not topic exclusions', lambda: bool(curriculum.NOT_ASSESSED.search('A calculator is not required')), False)
    from semantic_duplicates import duplicate
    case('Changing numbers alone is a repeated problem', lambda: duplicate('Calculate the future value of 100 at 5% for 2 years.', ['Calculate the future value of 200 at 6% for 3 years.']), True)
    return {'suite': 'Independent reference checks v2', 'cases': cases, 'passed': sum((c['passed'] for c in cases)), 'total': len(cases), 'seconds': round(time.perf_counter() - started, 3), 'scope': 'Local finance, calculus, matrix, grading, syllabus and repetition safeguards. Passing does not certify all generated questions; automatic source-grounded solution validation runs separately.'}
