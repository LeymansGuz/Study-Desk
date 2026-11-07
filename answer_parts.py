"""Structured solution parts, calculator evidence, and safe progress feedback."""
from __future__ import annotations
import math
import re
import ast
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from calc import evaluate, solve_equation

class Calculation(BaseModel):
    name: str = Field(default='result', max_length=80)
    expression: str = Field(default='', max_length=2000)
    equation: str = Field(default='', max_length=2000)
    variable: str = Field(default='x', pattern='^[A-Za-z][A-Za-z0-9_]{0,11}$')
    low: float = -0.99
    high: float = 100
    unit: str = Field(default='', max_length=80)
    value: float | None = None

    @model_validator(mode='after')
    def one_numeric_plan(self):
        if self.expression.strip() and self.equation.strip():
            raise ValueError('Use either a fully substituted expression or a bracketed equation, not both. Keep descriptive algebra in the written solution.')
        return self

class MathClaim(BaseModel):
    kind: Literal['equivalence', 'equation_equivalence', 'derivative', 'root', 'integral', 'definite_integral', 'matrix','boolean'] = 'equivalence'
    left: str = Field(min_length=1, max_length=600)
    right: str = Field(min_length=1, max_length=600)
    variables: list[str] = Field(default_factory=lambda: ['x'], max_length=8, description='All free symbols in both expressions. For calculus, list parameters too and set with_respect_to explicitly.')
    with_respect_to: str = Field(default='', max_length=8, description='For derivative/integral checks, the differentiation variable, e.g. y for a partial derivative in y. Must occur in variables. Empty uses variables[0] for older saved checks.')
    samples: list[float] = Field(default_factory=lambda: [-2, -1, 0, 0.5, 1, 2], max_length=16)
    bounds: list[list[str]] = Field(default_factory=list, max_length=3)
    purpose: str = Field(default='', max_length=300)
    assumptions: list[str] = Field(default_factory=list, max_length=6, description='Only actual public hypotheses constraining linked variables, as Python comparisons, e.g. a>0 or c**2==a**2+b**2. Conditional checks require independent domain/premise review and never certify a general proof. Leave empty for unconditional algebraic identities.')

    @field_validator('samples')
    @classmethod
    def finite_samples(cls, values):
        if any((not math.isfinite(v) or abs(v) > 1000000.0 for v in values)):
            raise ValueError('Substitution points must be finite and reasonably bounded.')
        return values

class SolvedPart(BaseModel):
    label: str = Field(default='answer', max_length=24)
    answer: str = Field(default='', max_length=3000)
    expression: str = Field(default='', max_length=2000)
    equation: str = Field(default='', max_length=2000)
    variable: str = Field(default='x', pattern='^[A-Za-z][A-Za-z0-9_]{0,11}$')
    low: float = -0.99
    high: float = 100
    unit: str = Field(default='', max_length=80)
    requirements: str = Field(default='', max_length=1000)
    checks: list[MathClaim] = Field(default_factory=list, max_length=4)
    value: float | None = None
    calculations: list[Calculation] = Field(default_factory=list, max_length=8)
    kind: Literal['numeric', 'conceptual', 'symbolic', 'mixed'] = Field(default='conceptual',description='Classify the requested final output. Equations/loci, parameter formulas, matrices and proofs are symbolic, even with numeric constants. Numeric requires a substituted calculation for a requested scalar result. Mixed means both explanation and a requested calculated scalar result, not merely prose containing a number.')

    @model_validator(mode='before')
    @classmethod
    def infer_missing_kind(cls, value):
        if isinstance(value, dict) and 'kind' not in value:
            value = dict(value)
            answer = str(value.get('answer', '')).strip()
            if value.get('expression') or value.get('equation') or value.get('calculations') or re.fullmatch('[\\s$€£]*[-+]?\\d+(?:\\.\\d+)?(?:\\s*(?:%|[A-Za-z/]+))?', answer):
                value['kind'] = 'numeric'
        return value

    @model_validator(mode='after')
    def require_numeric_plan(self):
        if self.expression.strip() and self.equation.strip():
            raise ValueError('Use either an arithmetic expression or an equation for a result.')
        if self.kind in {'numeric', 'mixed'} and (not self.expression.strip()) and (not self.equation.strip()) and (not self.calculations):
            raise ValueError('Numeric/mixed parts require a substituted expression or calculations for the requested scalar result. For a locus/equation, formula, matrix or proof use kind=symbolic instead; constants inside an argument do not make it numeric. Never invent a scalar value to satisfy the schema.')
        return self

class PartAssessment(BaseModel):
    label: str = Field(max_length=24)
    verdict: str = Field(pattern='^(correct|partial|incorrect|not_answered)$')
    feedback: str = Field(default='', max_length=600)

    @field_validator('label')
    @classmethod
    def clean_label(cls, value):
        return normalize_label(value)

    @field_validator('verdict', mode='before')
    @classmethod
    def clean_verdict(cls, value):
        value = str(value).lower().strip().replace(' ', '_')
        return {'partially_correct': 'partial', 'partly_correct': 'partial', 'unanswered': 'not_answered', 'missing': 'not_answered', 'not_attempted': 'not_answered', 'wrong': 'incorrect'}.get(value, value)

def part_labels(question: str) -> list[str]:
    labels = re.findall('(?<!\\w)(?:\\(([a-h]|[ivx]{1,4})\\)|(?:^|\\n)\\s*([a-h])[.)])\\s*', question, re.I)
    return list(dict.fromkeys(((a or b).lower() for a, b in labels)))

def normalize_label(label: str) -> str:
    return re.sub('^(?:part|subpart)\\s*', '', label.strip().lower()).strip(' ()[].:')

def evaluate_parts(parts: list[SolvedPart]) -> list[SolvedPart]:
    result = []
    seen = set()
    for original in parts:
        part = original.model_copy(deep=True)
        part.label = normalize_label(part.label) or 'answer'
        if part.label in seen:
            raise ValueError('The solution repeats a part label.')
        seen.add(part.label)
        part.value = None
        if part.expression.strip() or part.equation.strip():
            if part.equation.strip():
                if not all((math.isfinite(value) and abs(value) <= 1000000000000.0 for value in (part.low, part.high))):
                    raise ValueError('The equation bracket is invalid.')
                value = solve_equation(part.equation, part.variable, part.low, part.high)
            else:
                value = evaluate(part.expression)
            if value is None or not math.isfinite(value):
                raise ValueError(f'Part {part.label} has an invalid arithmetic expression.')
            part.value = value
        for calculation in part.calculations:
            calculation.value = None
            if calculation.expression.strip() and calculation.equation.strip():
                raise ValueError('A numeric result must use an expression or an equation, not both.')
            if calculation.equation.strip():
                if not all((math.isfinite(value) and abs(value) <= 1000000000000.0 for value in (calculation.low, calculation.high))):
                    raise ValueError('The equation bracket is invalid.')
                value = solve_equation(calculation.equation, calculation.variable, calculation.low, calculation.high)
            else:
                value = evaluate(calculation.expression)
            if value is None or not math.isfinite(value):
                raise ValueError(f'Part {part.label} has an invalid numeric result.')
            calculation.value = value
        result.append(part)
    return result

def numeric_answer(part: SolvedPart) -> str:
    values = []
    if part.value is not None:
        values.append(f'{part.value:.10g} {part.unit}'.strip())
    values.extend((f'{item.name}: {item.value:.10g} {item.unit}'.strip() for item in part.calculations))
    if not values:
        return part.answer.strip()
    prose = part.answer.strip()
    if part.kind == 'numeric' and _number_and_unit(prose) is not None:
        prose = ''
    return '; '.join(([prose] if prose else []) + values)

def canonical_from_parts(parts: list[SolvedPart], fallback: str) -> str:
    if not parts:
        return fallback
    answers = [numeric_answer(part) for part in parts]
    if not all((answer.strip() for answer in answers)):
        raise ValueError('A solution part has no answer.')
    rows = [f'({part.label}) {answer}' if len(parts) > 1 else answer for part, answer in zip(parts, answers)]
    return '; '.join(rows)

def numeric_binding_issues(parts, fallback=''):
    """Detect contradictory reported/calculated outputs before key assembly.

    This is a conservative check of parseable final-answer expressions, not an
    NLP solver. Unparseable formula/prose still requires the independent audits.
    Do not interpret fraction denominators or coordinate components as unrelated
    numeric literals; compare whole evaluable expressions.
    """
    from working_checks import numeric_expression
    issues=[]
    for part in parts:
        calculated=([part.value] if part.value is not None else [])+[c.value for c in part.calculations]
        if not calculated:continue
        answer=part.answer.strip() or (fallback if len(parts)==1 else '')
        currency_prefix=bool(re.match(r'^[A-Z]{3}\s*(?=\$?[-+]?\d)',answer)) or part.unit.strip().upper() in {'USD','HKD','CNY','RMB','EUR','GBP','JPY','AUD','CAD','CHF','SGD','NZD'}
        if currency_prefix:
            answer=re.sub(r'^[A-Z]{3}\s*','',answer,count=1)
            answer=re.sub(r'(?<=\d),(?=\d{3}(?:[,.$]|$))','',answer)
        expressions=re.findall(r'\$\$?(.*?)\$\$?',answer,re.S) or [answer]
        reported=[]
        for expression in expressions:
            expression=re.sub(r'\\(?:mathrm|text)\{[^}]*\}','',expression)
            expression=expression.replace('\\left','').replace('\\right','')
            expression=re.sub(r'\\[,;!: ]','',expression).replace('\\%','%')
            expression=numeric_expression(expression)
            pieces = re.split(r'=|;|:|\\approx|\\simeq',expression)
            # Function arguments such as f_xy(1,2) are not reported outputs.
            # Coordinate tuples are outputs: split those through the inert AST
            # rather than splitting every comma, including nested arguments.
            if len(pieces) > 1:
                pieces = pieces[1:]
            candidates = []
            for piece in pieces:
                try:
                    node = ast.parse(piece.strip(), mode='eval').body
                except (SyntaxError, ValueError, RecursionError):
                    candidates.append(piece)
                else:
                    if isinstance(node, ast.Tuple):
                        candidates.extend(ast.unparse(item) for item in node.elts)
                    else:
                        candidates.append(piece)
            for piece in candidates:
                candidate=piece.strip().rstrip('.% °')
                candidate=re.sub(r'\s+[A-Za-z][A-Za-z /]*$','',candidate)
                while candidate.startswith('(') and candidate.count('(')>candidate.count(')'):candidate=candidate[1:]
                while candidate.endswith(')') and candidate.count(')')>candidate.count('('):candidate=candidate[:-1]
                value=evaluate(candidate)
                if value is None:continue
                decimal=re.fullmatch(r'[-+]?\d+\.(\d+)',candidate)
                tolerance=.50001*10**(-len(decimal[1])) if decimal else max(1e-9,abs(value)*1e-9)
                reported.append((value,tolerance))
        if reported:
            for value in calculated:
                if not any(abs(value-number)<=tolerance for number,tolerance in reported):
                    issues.append(f'Part {part.label}: calculated output {value:.10g} conflicts with the parseable reported answer. Re-derive the requested outputs; do not append an unrelated intermediate value.')
    return issues

def calculator_evidence(parts: list[SolvedPart]) -> str:
    rows = []
    for part in parts:
        if part.value is not None:
            rows.append(f"Part {part.label}: {part.expression or part.equation + ' = 0'} -> {part.value:.12g} {part.unit}".strip())
        for item in part.calculations:
            rows.append(f"Part {part.label}/{item.name}: {item.expression or item.equation + ' = 0'} -> {item.value:.12g} {item.unit}".strip())
    return '\n'.join(rows)

def grading_key(part: SolvedPart, include_working=False):
    if include_working:
        return part.model_dump()
    return {'label': part.label, 'answer': part.answer, 'unit': part.unit, 'value': part.value, 'requirements': part.requirements, 'results': [{'name': item.name, 'value': item.value, 'unit': item.unit} for item in part.calculations]}

def feedback_summary(parts: list[PartAssessment]) -> str:
    """Labels and verdicts reveal no unattempted answer or hidden working."""
    names = {'correct': 'Correct', 'partial': 'Partly correct', 'incorrect': 'Needs correction', 'not_answered': 'Not answered yet'}
    return '\n'.join((f'- **Part ({part.label}): {names[part.verdict]}.**' + (f' {part.feedback}' if part.feedback else '') for part in parts))

def _number_and_unit(text):
    text = text.strip().strip('.;').strip()
    match = re.fullmatch('([$€£]?)\\s*([-+]?(?:(?:\\d{1,3}(?:,\\d{3})+|\\d+)(?:\\.\\d+)?|\\.\\d+)(?:[eE][-+]?\\d+)?)\\s*([%A-Za-z/²³^\\- ]*)', text)
    if not match or (match[1] and match[3].strip()):
        return None
    try:
        value = float(match[2].replace(',', ''))
    except ValueError:
        return None
    return (value, match[1] or match[3].strip()) if math.isfinite(value) else None

def _unit(unit):
    unit = ' '.join(unit.casefold().split())
    return {'dollar': '$', 'dollars': '$', 'usd': '$', 'us dollars': '$', 'percent': '%', 'percentage points': '%', 'metres': 'm', 'meters': 'm', 'metre': 'm', 'meter': 'm', 'seconds': 's', 'second': 's'}.get(unit, unit)

def verified_numeric_parts(question, answer, parts, previous):
    """Fast full credit only for complete, labeled, standalone final values.

    Never match numbers inside working or a conclusion. Never bypass requested
    proof/justification, mixed answers, multiple results per part, or unit checks.
    All other cases go to the normal grader for meaningful partial feedback.
    """
    labels = part_labels(question)
    if len(labels) < 2 or {part.label for part in parts} != set(labels):
        return None
    work = '\\b(?:prove|derive|justify|explain|interpret|compare|discuss|describe|classify|identify|whether|which|why|demonstrate|show|working|reasoning|proof|derivation|give\\s+reasons|round\\s+to\\s+(?:the\\s+)?nearest\\s+(?:integer|dollar))\\b'
    if re.search(work, question, re.I):
        return None
    occurrences = list(re.finditer('\\(([a-h]|[ivx]{1,4})\\)', answer, re.I))
    if not occurrences or answer[:occurrences[0].start()].strip():
        return None
    supplied = {}
    for index, match in enumerate(occurrences):
        label = match[1].lower()
        if label in supplied or label not in labels:
            return None
        end = occurrences[index + 1].start() if index + 1 < len(occurrences) else len(answer)
        supplied[label] = answer[match.end():end]
    accepted = {normalize_label(item['label']) for item in previous or [] if item.get('verdict') == 'correct'}
    result = []
    for part in parts:
        if part.label not in supplied:
            if part.label not in accepted:
                return None
            result.append(PartAssessment(label=part.label, verdict='correct', feedback='Correct on your earlier attempt.'))
            continue
        parsed = _number_and_unit(supplied[part.label])
        value_expected = part.value
        unit_expected = part.unit
        if value_expected is None and len(part.calculations) == 1:
            value_expected, unit_expected = (part.calculations[0].value, part.calculations[0].unit)
        if not parsed or part.kind != 'numeric' or value_expected is None or (len(part.calculations) > 1):
            return None
        if part.answer.strip() and _number_and_unit(part.answer) is None:
            return None
        value, unit = parsed
        expected_unit = _unit(unit_expected)
        if _unit(unit) != expected_unit:
            return None
        tolerance = 0.00500001 if expected_unit in {'$', '€', '£'} else max(1e-09, abs(value_expected) * 1e-06)
        if abs(value - value_expected) > tolerance:
            return None
        result.append(PartAssessment(label=part.label, verdict='correct', feedback='Your final value and units are correct.'))
    return sorted(result, key=lambda part: labels.index(part.label))
