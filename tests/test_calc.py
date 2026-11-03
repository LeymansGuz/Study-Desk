import math

import calc


def test_general_arithmetic():
    assert calc.evaluate("add(2, 3)") == 5
    assert calc.evaluate("subtract(9, 4)") == 5
    assert calc.evaluate("multiply(3, 7)") == 21
    assert calc.evaluate("divide(8, 2)") == 4
    assert calc.evaluate("power(2, 5)") == 32
    assert calc.evaluate("2 + 3 * 4") == 14


def test_general_math_functions():
    assert calc.evaluate("sqrt(81)") == 9
    assert calc.evaluate("abs(-4)") == 4
    assert math.isclose(calc.evaluate("exp(0)"), 1.0)
    assert math.isclose(calc.evaluate("log(exp(1))"), 1.0)


def test_rejects_unsafe_expressions():
    assert calc.evaluate("__import__('os').system('echo no')") is None
    assert calc.evaluate("open('x')") is None
    assert calc.evaluate("unknown(1)") is None


def test_numeric_parts_compute_every_required_result():
    from answer_parts import SolvedPart, evaluate_parts, canonical_from_parts
    parts = evaluate_parts([SolvedPart(label="a", expression="200"), SolvedPart(label="b", expression="25.5")])
    assert canonical_from_parts(parts, "") == "(a) 200; (b) 25.5"


def test_model_proposed_numbers_cannot_override_computed_values():
    from answer_parts import SolvedPart, evaluate_parts
    part = evaluate_parts([SolvedPart(expression="1000 * 1.05**3", value=9999)])[0]
    assert math.isclose(part.value, 1157.625)


def test_general_trig_and_constants():
    import math
    assert math.isclose(calc.evaluate("sin(pi/2)"), 1.0)
    assert math.isclose(calc.evaluate("cos(0)"), 1.0)
    assert math.isclose(calc.evaluate("log(e)"), 1.0)
    assert calc.evaluate("ceil(2.1)") == 3
