"""A scenario must be possible, not merely have an answerable local sub-question."""
from typing import Literal, ClassVar
import re
from pydantic import BaseModel, Field


SCENARIO_CONTRACT = (
    '\nSCENARIO FEASIBILITY IS SEPARATE FROM TARGET ANSWERABILITY. '
    'Every asserted background condition must be jointly possible under the stated model. '
    'A locally answerable target, a correct definition or one plausible option NEVER excuses '
    'contradictory incidental givens. Do not call an impossible setup decorative or irrelevant. '
    'Use the setup field to decide this independently of the requested answer. '
    'For feasible, give a concise checkable joint witness/interpretation satisfying the asserted '
    'conditions, not merely a solution of the requested sub-question. For inconsistent, identify '
    'the decisive conflicting givens and rule; do not invent mutation, measurement error, '
    'outside intervention, missing data or a changed assumption to rescue the scenario. '
    'Do not confuse constraints being queried with asserted existence: solving an equation may '
    'legitimately return no solution. An evaluated true/false proposition, a quoted student claim '
    'or an assumption introduced for proof by contradiction is not automatically a background fact. '
    'A consistent underdetermined scenario is not contradictory; respect requests for possible, '
    'conditional or general answers. For a purely conceptual task explain its consistent '
    'interpretation without manufacturing numerical givens. '
    'Only an explicit request to evaluate/refute a proposition, solve constraints without an '
    'existence guarantee, or identify/explain inconsistency can permit an unsatisfied condition '
    'as an intentional evaluation task: quote that actual request in evaluation_request. '
    'An explicit existence/feasibility test is also legitimate: its conditions are proposed '
    'constraints to test, not an assertion that a satisfying object exists. '
    'FIRST identify task intent: always quote an explicit evaluate-the-claim, true/false, '
    'solve-an-equation, temporary-contradiction, diagnosis or existence-test request in '
    'evaluation_request, even '
    'when you classify its interpretation as feasible. Extract EVERY asserted condition '
    'into background_facts as verbatim public substrings, including initial AND final '
    'observations, controls, exclusions, conservation conditions and stated relationships. '
    'Do not omit an inconvenient fact because it is unnecessary for the requested answer. '
    'Do not include the requested answer, answer choices, evaluated claims or temporary '
    'proof assumptions among asserted background facts. '
    'An ordinary MCQ asking about one individual, parameter or definition is NOT such permission. '
    'Keep the witness/contradiction as a short final finding, not exploratory reasoning.'
)


class SetupAssessment(BaseModel):
    evaluation_request: str = Field(max_length=500,
        description='FIRST identify whether the user explicitly asks to evaluate/refute a claim, solve constraints allowing an empty solution, diagnose inconsistency, or test existence. If yes quote that exact request even when classified feasible; otherwise empty. An ordinary MCQ about a detail is NOT permission to ignore contradictory background facts. A prove-X request does NOT permit X to be false.')
    background_facts: list[str] = Field(max_length=24,
        description='ALL asserted background conditions as exact public substrings, including every observation and constraint. Empty only for a task with no asserted background. Do not omit target-irrelevant conditions.')
    witness_or_conflict: str = Field(min_length=10, max_length=900)
    status: Literal['feasible', 'inconsistent', 'uncertain']
    conflict_quotes: list[str] = Field(default_factory=list, max_length=4,
        description='Exact short public substrings identifying conflicting background facts, not answer choices.')


class IndependentSetup(BaseModel):
    SYSTEM_PROMPT: ClassVar[str] = (
        'Check ONLY joint feasibility of the supplied asserted background facts. '
        'No requested answer, options, Writer solution or first reviewer finding is provided. '
        'Every condition must hold simultaneously. Track every initial/final value, boundary, '
        'control, exclusion and relationship. A subset witness is not a witness for the whole set. '
        'Apply the stated model; never invent mutation, reactions, measurement error, storage '
        'or intervention to rescue contradictory conditions. For feasible give one concise '
        'joint interpretation satisfying ALL facts. For inconsistent name the conflicting '
        'conditions and rule. Preserve logical scope: a statement that a student CLAIMS X '
        'does not assert X is true; a temporary proof-by-contradiction assumption need not '
        'be realizable. Report the consistency of the claim/proof scenario, not truth of '
        'the quoted proposition. A redundant or already-given answer is NOT a contradiction. '
        'Feasible means at least one joint assignment exists, not that every parameter '
        'assignment yields the same answer. Do NOT assess answer uniqueness here. '
        'A free parameter or conditional answer is not an inconsistent setup. Preserve '
        'all stated units, rate periods and conventions literally. '
        'Uncertainty is not approval. Output only the final finding, no abandoned objections.')
    witness_or_conflict: str = Field(min_length=10, max_length=900)
    status: Literal['feasible', 'inconsistent', 'uncertain']


_JOINT_CACHE = {}


def public_fact_ledger(assessment, question, sources=()):
    """Source definitions are evidence, never invented public observations."""
    from tools import CandidateError
    normalize=lambda value:' '.join(value.split())
    public=normalize(question)
    passages=[normalize(source.get('text','')) for source in sources]
    boundaries=[match.end() for match in re.finditer(r'[.!?]["\u201d\x27]?(?:\s+|$)',public)]
    facts=[]
    for fact in assessment.background_facts:
        quote=normalize(fact)
        if quote and quote in public:
            # A clipped quotation can turn "evaluate the claim: X" into an
            # assertion of X. Preserve its original grammatical sentence.
            start=public.index(quote);end=start+len(quote)
            left=max((point for point in boundaries if point<=start),default=0)
            right=min((point for point in boundaries if point>=end),default=len(public))
            scoped=public[left:right].strip()
            if scoped not in facts:facts.append(scoped)
        elif quote and any(quote in source for source in passages):
            continue  # A verbatim source-only rule is not an asserted public datum.
        else:
            error=CandidateError('The question setup was not independently checked.',
                feedback='background_facts must quote only the public task verbatim, with attribution/if/proof qualifiers intact. Do not put source definitions or paraphrases there.')
            error.pipeline_stage='premise'
            raise error
    return assessment.model_copy(update={'background_facts':facts})


async def ensure_joint_setup(assessment, question):
    """Second examiner sees the fact ledger, never the distracting local target."""
    import hashlib
    import json
    import tools
    from security import wrap_untrusted, MAX_ASSIGNMENT_CHARS
    assessment=public_fact_ledger(assessment,question)
    if not assessment.background_facts:
        validate_setup(assessment,question)
        return assessment
    facts=json.dumps(assessment.background_facts, ensure_ascii=False)
    key=hashlib.sha256(facts.encode()).hexdigest()
    if key not in _JOINT_CACHE:
        result=await tools._invoke_json(wrap_untrusted('asserted_background_conditions',facts,
            max_chars=MAX_ASSIGNMENT_CHARS*2),0,IndependentSetup)
        if len(_JOINT_CACHE)>=256:_JOINT_CACHE.pop(next(iter(_JOINT_CACHE)))
        _JOINT_CACHE[key]=result
    result=_JOINT_CACHE[key]
    if {assessment.status,result.status} == {'inconsistent','feasible'}:
        # Do not lose an earlier concrete objection just because a second model
        # found a witness. Challenge it with the same target-free facts.
        objection=(wrap_untrusted('asserted_background_conditions',facts,
                   max_chars=MAX_ASSIGNMENT_CHARS*2)+'\n'+
                   wrap_untrusted('alleged_conflict',assessment.witness_or_conflict if assessment.status=='inconsistent' else result.witness_or_conflict,max_chars=900)+
                   '\nIndependently check this alleged conflict against ALL these conditions. '
                   'A redundant requested answer is not a contradiction. Confirm only a real '
                   'conflict; withdraw a mistaken allegation. Uncertainty is not approval.')
        challenge=await tools._invoke_json(objection,0,tools.PremiseChallenge)
        if challenge.verdict == 'uncertain':
            error=tools.CandidateError('The question setup could not be established as consistent.',
                feedback=challenge.reason)
            error.pipeline_stage='premise'
            raise error
        result=result.model_copy(update={'status':'inconsistent' if challenge.verdict=='confirmed_defect' else 'feasible',
            'witness_or_conflict':challenge.reason})
        _JOINT_CACHE[key]=result
    checked=assessment.model_copy(update={'status':result.status,
        'witness_or_conflict':result.witness_or_conflict})
    validate_setup(checked,question)
    return checked


def validate_setup(assessment, question):
    """Fail closed on a missing/uncertain certificate, preserving intentional diagnosis."""
    from tools import CandidateError
    if assessment is None:
        error = CandidateError('The question setup was not independently checked.',
            feedback='Return an explicit setup status and joint feasibility witness; target answerability alone is insufficient.')
    elif assessment.status == 'uncertain':
        error = CandidateError('The question setup could not be established as consistent.',
            feedback=assessment.witness_or_conflict + ' Resolve the stated conditions without adding rescue assumptions.')
    elif assessment.status == 'inconsistent':
        normalize = lambda value: ' '.join(value.split())
        diagnostic = normalize(assessment.evaluation_request)
        if diagnostic and diagnostic in normalize(question):
            return assessment
        error = CandidateError('The question states conditions that cannot all hold together.',
            feedback=assessment.witness_or_conflict + ' Replace the inconsistent candidate; a correct local answer cannot rescue impossible background givens.')
    else:
        return assessment
    error.pipeline_stage = 'premise'
    raise error


def record_setup(assessment, question, options):
    """Keep the short certificate private and separate from publication receipts."""
    import logging
    from types import SimpleNamespace
    try:
        import monitoring
        from usage_log import current_user_id
        monitoring.record_generation('premise_checked', current_user_id(), stage='premise',
            outcome='checked', draft=SimpleNamespace(question=question), review=assessment,
            detail={'options': options or []})
    except Exception:
        logging.getLogger(__name__).warning('Could not record premise certificate', exc_info=True)
