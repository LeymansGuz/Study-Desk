"""Trusted mathematical constructions. No model-generated SVG or executable code.

Public questions contain every given; SVG is an accessible companion. Answers
are computed from the same construction and never embedded in public metadata.
"""
from __future__ import annotations
import hashlib
import html
import math
import random
import re
from pydantic import BaseModel, Field
from typing import Literal

class MathFigure(BaseModel):
    family: Literal['line', 'quadratic', 'triangle', 'circle', 'cuboid', 'double_integral', 'triple_integral']
    title: str = Field(max_length=100)
    alt: str = Field(max_length=1500)
    svg: str = Field(max_length=20000)
    version: int = 1
RULES = {'double_integral': 'double integr|iterated integr|change.{0,25}order.{0,20}integr|jacobian|重積分|重积分', 'triple_integral': 'triple integr|spherical coordinates|cylindrical coordinates|三重積分|三重积分', 'line': 'gradient|slope|straight.line|linear function|斜率|直線方程', 'quadratic': 'quadratic|parabola|二次函數|二次函数|拋物線|抛物线', 'triangle': 'cosine rule|sine rule|angle.bisector|pythag|right.angled triangle|right triangle|畢氏|毕氏|勾股', 'circle': 'tangent|secant|chord|弦長|弦长', 'cuboid': 'cuboid|rectangular prism|長方體|长方体'}

def validate_request(mode, difficulty, types):
    if mode in {'none', 'auto'}:
        return
    if any((t not in {'mcq', 'calculation', 'short_answer', 'long_answer', 'proof'} for t in types)):
        raise ValueError('Math figures support MCQ, calculation, short answer, long answer and proof/derivation at every difficulty. Choose those settings or use Standard questions.')

def eligible(topic, sources):
    evidence = ' '.join((str(s.get('text', '')) for s in sources))
    if re.search('centroid|ortho[- ]?cent|circum[- ]?cent|in[- ]?cent|(?:four|4)\\s+cent(?:re|er)|四心|重心|垂心|外心|內心', topic, re.I):
        return []
    families = [kind for kind, pattern in RULES.items() if re.search(pattern, evidence, re.I)]
    integrations = [kind for kind in families if kind.endswith('_integral')]
    if re.search('triple|spherical|cylindrical|三重', topic, re.I):
        return [kind for kind in integrations if kind == 'triple_integral']
    if re.search('double|order.*integr|jacobian|二重', topic, re.I):
        return [kind for kind in integrations if kind == 'double_integral']
    if re.search('matrix|matrices|eigen|linear algebra', topic, re.I):
        return []
    if re.search('integr|積分|积分', topic, re.I):
        return integrations
    topics = {'line': 'gradient|slope|straight.line|linear|斜率|直線', 'quadratic': 'quadratic|parabola|二次|拋物|抛物', 'triangle': 'triangle|pythag|三角|畢氏|毕氏|勾股', 'circle': 'circle|chord|圓|圆', 'cuboid': 'cuboid|rectangular.prism|3d|solid.geometry|three.dimension|立體|立体|長方體|长方体'}
    matching = [kind for kind in families if re.search(topics.get(kind, '(?!)'), topic, re.I)]
    if not matching and re.search('graph|圖像|图像', topic, re.I):
        matching = [kind for kind in families if kind in {'line', 'quadratic'}]
    if not topic.strip():
        return integrations or families
    if re.search('^whole (?:course|syllabus)$|^geometry$', topic, re.I):
        return matching or integrations or families
    return matching

def _n(value):
    return f'{value:.3f}'.rstrip('0').rstrip('.') if isinstance(value, float) else str(value)

def _text(x, y, text, size=21):
    return f'<text x="{_n(x)}" y="{_n(y)}" font-size="{size}" text-anchor="middle" fill="currentColor">{html.escape(str(text))}</text>'

def _line(x, y, u, v, dashed=False):
    return f'<line x1="{_n(x)}" y1="{_n(y)}" x2="{_n(u)}" y2="{_n(v)}" stroke="currentColor" stroke-width="2.5"' + (' stroke-dasharray="7 5"' if dashed else '') + '/>'

def _path(points):
    return '<polyline points="' + ' '.join((f'{_n(x)},{_n(y)}' for x, y in points)) + '" fill="none" stroke="currentColor" stroke-width="3"/>'

def _svg(body, title, alt):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 520 360" role="img"><title>{html.escape(title)}</title><desc>{html.escape(alt)}</desc><g>{body}</g></svg>'

def _graph(kind, rng, objective):
    if kind == 'line':
        m = rng.choice([-3, -2, -1, 1, 2, 3])
        b = rng.randint(-3, 3)
        x1, x2 = (-1, 2)
        y1, y2 = (m * x1 + b, m * x2 + b)
        given = f'The straight line passes through A({x1}, {y1}) and B({x2}, {y2}).'
        if objective == 'easy':
            task = 'Find the change in x when moving from A to B.'
            expression = f'{x2}-({x1})'
            method = 'Subtract the x-coordinate of A from the x-coordinate of B.'
        elif objective == 'medium':
            task = 'Find the gradient of AB.'
            expression = f'({y2}-({y1}))/({x2}-({x1}))'
            method = 'Use the change in y divided by the change in x, in the same point order.'
        else:
            target = rng.choice([4, 5, 6])
            target_y = m * target + b
            task = f'Find the x-coordinate of the point on the line whose y-coordinate is {target_y}.'
            expression = f'({target_y}-({b}))/({m})'
            method = f'Calculate the gradient {m} from A and B, obtain y={m}x+({b}), then set y={target_y} and solve for x.'
        f = lambda x: m * x + b
        labels = [(x1, y1, 'A'), (x2, y2, 'B')]
        bounds = (-4, 4, -16, 16)
    else:
        h = rng.choice([-2, -1, 1, 2])
        r = rng.choice([1, 2])
        a = rng.choice([1, 2])
        k = -a * r * r
        term = f'x - {h}' if h >= 0 else f'x + {-h}'
        coefficient = '' if a == 1 else str(a)
        given = f'The graph is $y = {coefficient}({term})^2 - {abs(k)}$.'
        if objective == 'easy':
            task = 'Find the y-coordinate of the turning point.'
            expression = str(k)
            method = f'Vertex form y=a(x-h)^2+k gives the turning point ({h}, {k}).'
        elif objective == 'medium':
            task = 'Find the distance between its two x-intercepts.'
            expression = f'2*sqrt(-({k})/{a})'
            method = f'Set y=0. Then (x-({h}))^2={r * r}, so the roots are {h - r} and {h + r}. Subtract the smaller root from the larger.'
        else:
            task = 'Find the area of the triangle whose vertices are the turning point and the two x-intercepts.'
            expression = f'0.5*(2*sqrt(-({k})/{a}))*abs({k})'
            method = f'Solve y=0 for both x-intercepts. Their separation is the base; the perpendicular height to the x-axis is |{k}|. Use half the base times the height.'
        f = lambda x: a * (x - h) ** 2 + k
        labels = []
        bounds = (-5, 5, -10, 20)
    xmin, xmax, ymin, ymax = bounds
    X = lambda x: 65 + (x - xmin) / (xmax - xmin) * 390
    Y = lambda y: 305 - (y - ymin) / (ymax - ymin) * 255
    body = _line(X(xmin), Y(0), X(xmax), Y(0)) + _line(X(0), Y(ymin), X(0), Y(ymax)) + _text(480, Y(0) - 10, 'x') + _text(X(0) + 20, 35, 'y')
    for x in range(xmin, xmax + 1):
        body += _line(X(x), Y(0) - 4, X(x), Y(0) + 4) + _text(X(x), Y(0) + 24, x, 16)
    step = 4 if kind == 'line' else 5
    for y in range(ymin, ymax + 1):
        if y and y % step == 0:
            body += _line(X(0) - 4, Y(y), X(0) + 4, Y(y)) + _text(X(0) - 22, Y(y) + 5, y, 16)
    segment = []
    for i in range(301):
        x = xmin + (xmax - xmin) * i / 300
        y = f(x)
        if ymin <= y <= ymax:
            segment.append((X(x), Y(y)))
        elif segment:
            body += _path(segment)
            segment = []
    if segment:
        body += _path(segment)
    for x, y, label in labels:
        body += f'<circle cx="{X(x)}" cy="{Y(y)}" r="4" fill="currentColor"/>' + _text(X(x) + 20, Y(y) - 13, label)
    return (given, task, expression, method, body, 'Straight-line graph' if kind == 'line' else 'Quadratic graph', given + ' Axes are labelled x and y.', '')

def _triangle(rng, objective):
    a, b, c = rng.choice([(3, 4, 5), (5, 12, 13), (8, 15, 17), (7, 24, 25)])
    scale = rng.choice([1, 2, 3])
    a *= scale
    b *= scale
    c *= scale
    body = _path([(110, 75), (110, 275), (420, 275), (110, 75)]) + _path([(110, 253), (132, 253), (132, 275)]) + _text(90, 63, 'A') + _text(90, 303, 'B') + _text(440, 303, 'C')
    if objective == 'easy':
        given = f'ABC is right-angled at B. AB = {a} cm and BC = {b} cm.'
        task = 'Find the area of triangle ABC.'
        expression = f'{a}*{b}/2'
        unit = 'cm^2'
        method = 'The two legs are perpendicular. Area = AB times BC divided by 2.'
    elif objective == 'medium':
        given = f'ABC is right-angled at B. AB = {a} cm and AC = {c} cm.'
        task = 'Find BC.'
        expression = f'sqrt({c}**2-{a}**2)'
        unit = 'cm'
        method = 'AC is the hypotenuse. By Pythagoras, BC squared = AC squared minus AB squared.'
    else:
        given = f'ABC is right-angled at B. AB = {a} cm and BC = {b} cm.'
        task = 'Find the perimeter of triangle ABC.'
        expression = f'{a}+{b}+sqrt({a}**2+{b}**2)'
        unit = 'cm'
        method = 'Use Pythagoras to calculate AC, then add AB, BC and AC.'
    body += _text(65, 185, f'{a} cm')
    body += _text(305, 160, f'{c} cm') if objective == 'medium' else _text(265, 310, f'{b} cm')
    return (given, task, expression, method, body, 'Right-angled triangle', given + ' B has a right-angle mark.', unit)

def _circle(rng, objective):
    d, half, r = rng.choice([(3, 4, 5), (5, 12, 13), (8, 15, 17)])
    scale = rng.choice([1, 2])
    d *= scale
    r *= scale
    cy = 165
    radius = 125
    my = cy + radius * d / r
    dx = radius * math.sqrt(1 - (d / r) ** 2)
    body = f'<circle cx="260" cy="165" r="125" fill="none" stroke="currentColor" stroke-width="3"/>'
    body += _line(260 - dx, my, 260 + dx, my) + _line(260, cy, 260, my) + _line(260, cy, 260 + dx, my) + _path([(260, my - 15), (275, my - 15), (275, my)])
    body += _text(244, cy - 10, 'O') + _text(246, my + 28, 'M') + _text(250 - dx, my + 25, 'A') + _text(270 + dx, my + 25, 'B') + _text(300, cy + radius * d / r / 2 - 22, f'{r} cm') + _text(222, (cy + my) / 2, f'{d} cm')
    given = f'AB is a chord of a circle with centre O and radius {r} cm. OM = {d} cm is perpendicular to AB at its midpoint M.'
    if objective == 'easy':
        task = 'Find the diameter of the circle.'
        expression = f'2*{r}'
        unit = 'cm'
        method = 'The diameter is twice the radius.'
    elif objective == 'medium':
        task = 'Find the length of chord AB.'
        expression = f'2*sqrt({r}**2-{d}**2)'
        unit = 'cm'
        method = 'Use Pythagoras in OMB to find half the chord, then double it.'
    else:
        task = 'Find the area of triangle OAB.'
        expression = f'{d}*sqrt({r}**2-{d}**2)'
        unit = 'cm^2'
        method = 'Find the half-chord by Pythagoras. AB is twice this length and OM is the perpendicular height; use half base times height.'
    return (given, task, expression, method, body, 'Circle and chord', given, unit)

def _cuboid(rng, objective):
    l, w, h = (rng.randint(3, 9), rng.randint(3, 7), rng.randint(3, 8))
    points = {'A': (100, 270), 'B': (345, 270), 'C': (425, 200), 'D': (180, 200), 'E': (100, 120), 'F': (345, 120), 'G': (425, 50), 'H': (180, 50)}
    body = ''
    for first, second in [('A', 'B'), ('B', 'C'), ('C', 'D'), ('D', 'A'), ('E', 'F'), ('F', 'G'), ('G', 'H'), ('H', 'E'), ('A', 'E'), ('B', 'F'), ('C', 'G'), ('D', 'H')]:
        body += _line(*points[first], *points[second], dashed=first == 'D' or second == 'D')
    for label, (x, y) in points.items():
        body += _text(x - 12, y + 22, label, 19)
    body += _text(220, 310, f'{l} cm') + _text(413, 263, f'{w} cm') + _text(70, 202, f'{h} cm')
    given = f'ABCDEFGH is a cuboid. ABCD is the base, EFGH is the top, and AE, BF, CG, DH are vertical edges. AB = {l} cm, BC = {w} cm and AE = {h} cm.'
    if objective == 'easy':
        task = 'Find its volume.'
        expression = f'{l}*{w}*{h}'
        unit = 'cm^3'
        method = 'Multiply the three mutually perpendicular dimensions.'
    elif objective == 'medium':
        task = 'Find the length of space diagonal AG. Give your answer to 3 decimal places.'
        expression = f'sqrt({l}**2+{w}**2+{h}**2)'
        unit = 'cm'
        method = 'First find base diagonal AC by Pythagoras, then apply Pythagoras to right-angled triangle ACG.'
        body += _line(*points['A'], *points['G'], dashed=True)
    else:
        task = 'Find the angle between AG and the base plane ABCD, in degrees to 3 decimal places.'
        expression = f'atan({h}/sqrt({l}**2+{w}**2))*180/{math.pi}'
        unit = 'degrees'
        method = 'The projection of AG onto the base is AC. Compute AC using Pythagoras, then use tan(angle CAG) = CG / AC.'
        body += _line(*points['A'], *points['G'], dashed=True) + _line(*points['A'], *points['C'], dashed=True)
    return (given, task, expression, method, body, 'Cuboid', given + ' Dashed lines indicate hidden or internal segments.', unit)

def construct(family, difficulty='medium', question_type='calculation', seed=None):
    """Pure construction, usable for deterministic offline checks and recovery."""
    from calc import evaluate
    from answer_parts import SolvedPart, evaluate_parts
    from tools import QuestionDraft
    if family not in RULES:
        raise ValueError('Unsupported figure family.')
    validate_request('math', difficulty, [question_type])
    rng = random.Random(seed)
    if question_type == 'proof':
        from proof_figures import construct as proof
        return proof(family, difficulty, seed)
    if family.endswith('_integral'):
        from advanced_math_figures import integration
        return integration(family, difficulty, question_type, seed)
    if difficulty in {'hard', 'insane'}:
        from advanced_math_figures import geometry
        return geometry(family, difficulty, question_type, seed)
    result = _graph(family, rng, difficulty) if family in {'line', 'quadratic'} else {'triangle': _triangle, 'circle': _circle, 'cuboid': _cuboid}[family](rng, difficulty)
    given, task, expression, method, body, title, alt, unit = result
    value = evaluate(expression)
    if value is None or not math.isfinite(value):
        raise ValueError('Construction did not yield a finite answer.')
    if question_type == 'long_answer':
        task += ' Explain the relationship and justify your method in a structured response.'
    public_question = given + ' ' + task
    if family == 'quadratic' and difficulty == 'hard':
        unit = 'square units'
    if question_type != 'mcq':
        public_question += ' Show your working.' if difficulty != 'easy' else ''
    if family not in {'line', 'quadratic'}:
        public_question += ' The diagram is not to scale.'
    options = []
    answer = _n(round(value, 3)) + (f' {unit}' if unit else '')
    if question_type == 'mcq':
        correct = round(value, 3)
        values = [correct]
        candidates = [value / 2, value * 2, value + 1, value - 1, value + 2, value - 2]
        if value == 0:
            candidates = [-1, 1, 2, -2]
        positive = bool(unit) or family in {'triangle', 'circle', 'cuboid'}
        for candidate in candidates:
            number = round(candidate, 3)
            if number not in values and (not positive or number > 0) and (unit != 'degrees' or number < 90):
                values.append(number)
            if len(values) == 4:
                break
        if len(values) != 4:
            raise ValueError('Could not produce four distinct options.')
        rng.shuffle(values)
        options = [_n(v) + (f' {unit}' if unit else '') for v in values]
        answer = 'ABCD'[values.index(correct)] + '. ' + answer
    parts = evaluate_parts([SolvedPart(label='answer', kind='numeric', expression=expression, unit=unit, requirements=task)])
    figure = MathFigure(family=family, title=title, alt=alt, svg=_svg(body, title, alt))
    solution = method + f'\nCalculation: {expression}\nFinal answer: {answer}'
    return QuestionDraft(question=public_question, canonical_answer=answer, solution=solution, question_type=question_type, options=options, answer_parts=parts, formula_focus=title, figure=figure.model_dump())

async def draft_visual(topic, sources, difficulty, types, avoid_questions, course_context, strict_duplicates=False):
    from tools import CandidateError, TutorError, _audit_draft, problem_similarity
    validate_request('math', difficulty, types)
    families = eligible(topic, sources)
    from assessment_level import contract
    from tools import DIFFICULTY_GUIDE
    assessment = contract(difficulty, sources, course_context, types[0] if len(types) == 1 else '') or 'Requested difficulty: ' + difficulty + '. ' + DIFFICULTY_GUIDE[difficulty]
    if not families:
        raise CandidateError('No checked figure construction matches the methods in the selected documents. Use Standard questions for covered topics without a supported figure renderer.')
    random.shuffle(families)
    drafts = []
    for family in families:
        for attempt in range(1 if strict_duplicates else 8):
            import asyncio
            candidate = await asyncio.to_thread(construct, family, difficulty, random.choice(types))
            if candidate.question not in (avoid_questions or []) and (not (strict_duplicates and any((problem_similarity(candidate.question, old) >= 0.82 for old in avoid_questions or [])))):
                drafts.append(candidate)
                break
        if strict_duplicates and drafts:
            break
    if not drafts:
        raise CandidateError('No unused mathematical construction remains for these settings. Choose another covered topic.')
    drafts.sort(key=lambda draft: max((problem_similarity(draft.question, q) for q in avoid_questions or []), default=0))
    draft = drafts[0]
    from originality import source_copy_reason
    reason = source_copy_reason(draft.question, sources)
    if reason:
        raise CandidateError(reason)
    if strict_duplicates and any((problem_similarity(draft.question, old) >= 0.82 for old in avoid_questions or [])):
        raise CandidateError('The figure construction repeats a recent reasoning pattern; a fresh standard candidate is required.')
    draft.assessment_context = assessment
    if difficulty == 'insane':
        from tools import _difficulty_issue
        issue = _difficulty_issue(draft, difficulty)
        if issue:
            raise CandidateError(issue)
    from math_format import check
    await check(draft.question, *draft.options, draft.canonical_answer, draft.solution)
    from question_preflight import check as preflight
    await preflight(topic,draft.question,draft.options,sources)
    independent = None
    if draft.question_type in {'long_answer','proof'} or difficulty in {'hard','insane'}:
        from tools import ensure_public_validity
        await ensure_public_validity(draft.question,draft.options)
    if draft.question_type == 'proof':
        from tools import solve_independently
        independent = await solve_independently(draft.question, draft.options)
        if independent.missing_givens:
            raise CandidateError('The figure proof has missing or ambiguous givens.')
        draft.solution += '\n\nIndependent derivation:\n' + independent.reasoning
    review = await _audit_draft(draft, sources, course_context, topic, independent)
    from answer_parts import calculator_evidence
    numeric=bool(calculator_evidence(draft.answer_parts))
    if review.source_clone:
        raise CandidateError('The figure question clones a source exercise.')
    if draft.question_type == 'proof' and (not review.proof_is_valid):
        raise CandidateError('The independent audit did not verify a complete logical proof, including domains and cases.')
    valid = {s['ref'] for s in sources}
    if assessment and (not (review.difficulty_matches and review.topic_methods_match)):
        raise CandidateError('The independent audit did not approve the requested course difficulty or tested methods. No weaker substitute was returned.')
    from answer_parts import calculator_evidence
    arithmetic_ok = not calculator_evidence(draft.answer_parts) or review.calculations_match
    if not (review.public_claim_valid and review.givens_complete and review.is_consistent and arithmetic_ok and review.is_on_topic and review.is_grounded and (not review.answer_leaked) and review.used_source_refs and (set(review.used_source_refs) <= valid)):
        import logging
        missing = [key for key in ['is_consistent', 'is_on_topic', 'is_grounded'] if not getattr(review, key)]
        if not arithmetic_ok:
            missing.append('calculations_match')
        if review.answer_leaked:
            missing.append('answer_leaked')
        if not review.used_source_refs or not set(review.used_source_refs) <= valid:
            missing.append('source_references')
        logging.getLogger(__name__).info('Figure audit rejected: %s', ','.join(missing))
        raise CandidateError('The figure did not pass its source, topic or answer-consistency checks. No unverified item was returned.')
    if review.corrected_question or review.corrected_canonical_answer or review.corrected_solution or review.corrected_options or review.corrected_parts:
        raise CandidateError('The independent audit requested a construction change; the whole figure candidate was rejected.')
    if review.correct_option_index is not None and draft.question_type == 'mcq' and (review.correct_option_index != 'ABCD'.index(draft.canonical_answer[0])):
        raise CandidateError('The independent MCQ audit disagreed with the computed key.')
    if difficulty in {'hard','insane'}:
        second=await _audit_draft(draft.model_copy(update={'assessment_context':draft.assessment_context+'\nFresh adversarial audit: verify every displayed step, actual dependent reasoning and source-supported methods; a correct numeric key alone does not establish a valid solution.'}),sources,course_context,topic,None)
        if not (second.public_claim_valid and second.givens_complete and second.is_consistent and second.is_on_topic and second.is_grounded and (not numeric or second.calculations_match) and (draft.question_type!='proof' or second.proof_is_valid) and (draft.question_type!='mcq' or second.correct_option_index=='ABCD'.index(draft.canonical_answer[0])) and second.difficulty_matches and second.topic_methods_match and not second.source_clone and not second.answer_leaked and second.used_source_refs and set(second.used_source_refs)<={s['ref'] for s in sources}):
            raise CandidateError('The additional figure audit did not confirm correctness, source support and difficulty.',feedback=second.issues+' '+second.difficulty_reason)
    draft.source_refs = list(review.used_source_refs)
    draft.verification = {'solver_passed': True, 'solver_kind': 'checked_construction', 'source_passed': True, 'verifier_passed': True, 'math_format_passed': True, 'originality_passed': True}
    from tools import shuffle_choice_draft
    return shuffle_choice_draft(draft)

async def draft_automatic(writer, topic, sources, difficulty, types, avoid_questions, course_context):
    """Renderer choice follows evidence; unsupported topics retain the standard pipeline."""
    from tools import CandidateError
    supported = [kind for kind in types if kind in {'mcq', 'calculation', 'short_answer', 'long_answer', 'proof'}]
    if supported and topic.strip() and (not re.search('^whole (?:course|syllabus)$|^geometry$', topic, re.I)) and eligible(topic, sources):
        try:
            return await draft_visual(topic, sources, difficulty, supported, avoid_questions, course_context, strict_duplicates=True)
        except CandidateError as exc:
            import logging
            logging.getLogger(__name__).info('pipeline automatic_figure_rejected reason=%s', str(exc)[:350])
    return await writer(topic, sources, difficulty, types, avoid_questions=avoid_questions, course_context=course_context)
