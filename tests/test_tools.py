from tools import (
    Assessment,
    choice_answer_correct,
    compose_hint,
    parse_json_object,
    safe_hint,
)


def test_choice_grading_uses_selected_letter_not_llm():
    options = [
        "A. The rate is lower",
        "B. The rate is higher",
        "C. They are equal",
        "D. Not enough information",
    ]
    assert choice_answer_correct("B. The rate is higher", options, "B") is True
    assert choice_answer_correct("A. The rate is lower", options, "B") is False
    assert choice_answer_correct("B", options, "B") is True


def test_true_false_grading_is_deterministic():
    assert choice_answer_correct("True", ["True", "False"], "True", "true_false") is True
    assert choice_answer_correct("False", ["True", "False"], "True", "true_false") is False


def test_parse_json_with_markdown_fence():
    raw = 'Here is the result:\n```json\n{"is_correct": false, "verdict": "incorrect"}\n```'
    assert parse_json_object(raw) == {"is_correct": False, "verdict": "incorrect"}


def test_leak_detector_catches_verbatim_answer():
    hint = "The final answer is 10.4506, so you are close."
    assert safe_hint(hint, "C = 10.4506", "Black-Scholes") != hint


def test_leak_detector_allows_socratic_question():
    hint = "Which term in the Black-Scholes formula grows when volatility rises?"
    assert safe_hint(hint, "C = 10.4506", "Black-Scholes") == hint


def test_compose_hint_has_no_answer_key_before_attempt_three():
    assessment = Assessment(
        is_correct=False,
        verdict="incorrect",
        hint="What does put-call parity imply about the difference C - P?",
    )
    feedback = compose_hint(
        assessment=assessment,
        canonical_answer="P = 2.8308",
        formula_focus="put-call parity",
        attempt=1,
        max_attempts=3,
    )
    assert "2.8308" not in feedback
    assert "Attempt 1 of 3" in feedback
    assert "2 attempts left" in feedback
