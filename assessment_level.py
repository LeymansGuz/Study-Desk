"""Single source of truth for useful, course-relative practice difficulty.

Difficulty describes the student's inference, not the number of metadata rows,
subparts or equations. Workload ceilings prevent an artificial mini-examination.
"""
import re

POLICY_VERSION = 24

DIFFICULTY_GUIDE = {
    'easy': 'Easy: one familiar concept and one direct reasoning step; a concise revision warm-up.',
    'medium': 'Medium: one coherent setup, at most two dependent reasoning decisions and one small twist or method choice.',
    'hard': 'Hard: a focused course-exam application connecting covered ideas through a meaningful inference or justified method choice. A short two-decision solution is enough; no mandatory extra part.',
    'insane': 'Insane: one bounded stretch above Hard on this covered objective. Test careful interpretation of a subtle condition, plausible misconception, counterexample or reverse inference. One discriminating insight is sufficient; do not require a longer chain, a new strategy or research novelty.',
}

TYPE_REQUIREMENTS = {
    'long_answer': 'Long answer: a structured worked response on ONE central objective. Use an unlabelled coherent task or at most two connected labelled parts, each in its own paragraph with one main deliverable. A second part is optional and must use the earlier conclusion. Give intermediate values when they remove repetitive arithmetic; no hidden task lists.',
    'essay': 'Essay: one focused argument or explanation in connected paragraphs, supported by course evidence. Bound the comparison/evaluation. Do not turn it into a multipart worksheet; accept defensible alternative arguments.',
    'calculation': 'Calculation: one main numeric/symbolic result with concrete givens, units and covered methods. Say Show your working only if the method is assessed. Do not add steps merely to lengthen the answer.',
    'proof': 'Proof/derivation: ONE true focused claim with complete natural hypotheses and a concise logically sufficient argument. Match depth to the requested level; do not add an unrelated second proof.',
    'short_answer': 'Short answer: one focused conclusion in a few sentences or a short calculation, not an essay or task list.',
}


def variation_instruction(difficulty):
    """Vary the learning task without asking Easy to invent a hard scenario."""
    if difficulty == 'easy':
        return 'Use a familiar covered setting and one direct application. Vary the task from source examples without adding an experiment, unfamiliar context or extra result.'
    if difficulty == 'medium':
        return 'Use one familiar setup with a small interpretation or method choice. Do not add independent experiments or comparisons merely for variety.'
    return 'Choose one focused covered inference: a justified application, comparison or bounded inverse problem. Use only the depth required by this level; do not stack variations.'


def type_requirements(kind, difficulty):
    if kind == 'long_answer' and difficulty == 'easy':
        return ('Long answer: one familiar objective with concise connected working. '
                'Do not add a second calculation merely to make the response long. '
                'Labels may organize the same task; no minimum subpart count.')
    if kind == 'calculation' and difficulty == 'easy':
        return 'Calculation: one direct application of a covered formula with explicit givens and units. Do not force two steps at Easy.'
    if kind == 'proof' and difficulty == 'easy':
        return 'Proof: justify one immediate consequence of a covered definition or identity in one concise step. No unsupported prerequisites.'
    return TYPE_REQUIREMENTS.get(kind, '')


def part_limit(difficulty, question_type):
    if question_type in {'mcq', 'true_false', 'essay'} or (difficulty == 'insane' and question_type == 'calculation'):
        return 1
    return 2


def contract(difficulty, sources, context='', question_type=''):
    guide = DIFFICULTY_GUIDE.get(difficulty)
    if not guide:
        return ''
    common = (
        'The supplied course documents define topics, methods, notation and permitted knowledge; '
        'institution labels never define scope. Respect syllabus exclusions. Notes/syllabus establish '
        'coverage, past papers assessed methods, marking schemes accepted reasoning, and exam reports '
        'misconceptions when those documents exist. Never invent missing evidence. Source exercises '
        'are references, not templates to copy or lightly reskin. New data are expected. '
        'Difficulty is relative to this course: count meaningful inferences, not algebra lines, '
        'method_plan rows, words or subpart labels. Do not demand extra tasks to hit a numeric quota. '
        'No unsupported prerequisite, long arithmetic, exhaustive cases or deliberately awkward data. '
    )
    bounds = (
        'Insane uses one bounded insight; that insight is '
        'INCLUDED in the concise solution, not an additional task or numeric step quota. A theorem name plus direct '
        'substitution alone is insufficient. One careful inference can be challenging without a long '
        'proof. Judge the insight in the selected learning objective, not against a whole-course final examination. '
        'Basic topics must not acquire unsupported advanced prerequisites to reach Insane. '
        'For MCQ, true/false and short answers, judge the discriminating insight and plausible misconception, '
        'not response length or a minimum number of steps. A concise covered comparison can be challenging '
        'for a student even when an expert recognizes the answer immediately. Do not require another '
        'inference after the requested subtle condition has already been tested. Pure definition recall '
        'without application or a meaningful distinction remains below Hard/Insane. '
        'Hard needs a substantive application or justification rather than recall alone; '
        'it need not combine several chapters. Never require an advanced method just to increase depth. '
        'Proving a single coherent claim may require checking definitions/cases; these are not '
        'independent deliverables. For a multipart task, later reasoning must use an earlier conclusion. '
    ) if difficulty in {'hard', 'insane'} else ''
    subject = ' '.join(str(row.get('text', '')) for row in sources or [])
    calibration = ''
    if difficulty in {'hard', 'insane'}:
        if re.search(r'biolog|ecolog|genetic|homeosta|enzyme|physiolog|nursing|psycholog', subject, re.I):
            calibration += 'Life/behavioural sciences: infer from explicitly hypothetical consistent observations using covered mechanisms; distinguish evidence from causation and avoid unevidenced facts. '
        if re.search(r'physic|mechanic|electromagn|electric circuit|standing wave|thermodynam', subject, re.I):
            calibration += 'Physics: select a covered model and justify the requested prediction; check units, signs and frames. Supply all necessary diagram data in text when no checked figure exists. '
    workload = type_requirements(question_type, difficulty)
    if difficulty == 'insane':
        workload += ' Insane MCQ and Calculation require EXACTLY 1 part. Proof and Long Answer have a MAXIMUM of 2 parts; this is a ceiling, never a required count. '
    return ('Document-grounded assessment. Requested difficulty: ' + difficulty + '. ' +
            guide + ' ' + common + bounds + calibration + workload +
            ' Check both depth and workload: a correct but excessively demanding question does not match. ')


def workload_issue(question, kind, difficulty):
    from answer_parts import part_labels
    labels = part_labels(question)
    if len(labels) > part_limit(difficulty, kind):
        return 'Keep one focused task; extended answers may have at most two connected parts. Do not add unrelated or hidden subparts.'
    words = len(question.split())
    # A stem can need context to be self-contained. Word count is only an outer
    # abuse/verbosity bound; the reviewers judge actual workload and depth.
    ceiling = {'easy':180, 'medium':300, 'hard':400, 'insane':400}.get(difficulty, 400)
    if words > ceiling:
        return f'Keep the public question within {ceiling} words and its focused workload ceiling. Supply helpful intermediate values instead of repetitive requests.'
    return ''
