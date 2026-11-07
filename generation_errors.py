"""Public-safe stage failures. Provider payloads, prompts and traces stay private."""
import asyncio
from fastapi import HTTPException
PUBLIC_REASONS = frozenset({'The worked solution contains discarded draft reasoning.','Add your DeepSeek API key in Settings to enable AI study tools.','The proposed task did not meet the requested reasoning or workload requirements.','A worked interpretation contradicts its stated financial comparison.','The public question does not use the requested true/false format.','True/false options must be exactly True and False.','The independent Solver did not provide a true/false verdict.','The public question has conflicting or insufficient givens.','The selected course passages do not support the requested topic or required methods.','The additional figure audit did not confirm correctness, source support and difficulty.','The independent Solver did not identify one answer option.','A displayed calculation disagrees with its evaluated expression.','The public question has a false premise or unanswerable setup.','The question copies a substantial source span, including number-only variants. Design a different reasoning task, not a paraphrase or reskin.','The question is structurally too close to a source exercise. Change the inference and information flow, not only names or numbers.','The independent Solver and Verifier disagree on the correct option.','A changed premise needs a fresh independent solution.', 'The solver did not answer every question part.', 'Essential information is missing or ambiguous. Add the missing givens or diagram relationships before solving.', 'The candidate clones a source exercise.', 'Question verification did not complete.', 'No relevant course evidence was found. Add/index notes or choose a covered topic.', 'The model service rejected the request; check its configuration.', 'The assignment question is too short to work with.', 'The model service could not complete this step. Please retry.', 'No fresh supported section remains for this topic. Try another topic.', 'The question did not match the requested topic.', 'The candidate has missing or ambiguous givens.', 'The model step could not be completed safely. Please retry.', 'The additional symbolic review did not confirm the answer.', 'The reviewer did not supply a complete correction.', 'The generated multiple-choice question did not have exactly four options; please retry.', 'The complete proof, assumptions or case coverage was not verified.', 'The grader did not assess every published criterion. Your attempt was not counted; please retry.', 'A symbolic or substitution check found a mathematical counterexample.', 'Model calls cannot run while the publication transaction is open.', 'The question disclosed its answer.', 'The draft repeated a recent problem.', 'The multiple-choice options contained two equivalent answers; please retry.', 'This account is no longer available for study work.', 'The required methods are not supported by the course evidence.', 'The proposed proof claim is false or needs different premises.', 'The true/false answer key was neither True nor False; please retry.', 'The multiple-choice answer key did not match any option; please retry.', 'The corrected MCQ options are invalid.', 'No candidate was produced.', 'The model service could not complete this step.', 'The grader could not assess every subpart. Your attempt was not counted; please retry.', 'The solver did not cover the public question parts with the required labels.', 'OPENAI_API_KEY is missing. Put it in the local .env, then restart the API.', 'This account is not available for study work.', 'The MCQ key did not identify one correct option.', 'Repeated drafts were too similar to recent questions. Choose another topic or try again.', 'The verifier did not explicitly check source originality.', 'The candidate did not meet the course-relative difficulty and topic-method requirements.', 'The repaired question exceeds its workload limit.', 'OPENAI_API_KEY is still a placeholder; set the real key.', 'Essential information is missing. Add the full givens and any diagram relationships, then try again.', 'The final candidate still failed verification after repair.', 'This question template is paused for review.'})
from study_catalog import PRIMARY_SOURCE_REASON
PUBLIC_REASONS |= frozenset({PRIMARY_SOURCE_REASON})
PUBLIC_REASONS |= frozenset({'The isolated syntax repair did not produce pure Python.','A calculator expression is invalid and cannot be safely syntax-repaired.','The numeric plan uses unsupported operations or unresolved variables.'})
LABELS={'recall':'Recall check','premise':'Question consistency','topic':'Topic alignment','writer':'Question drafting','solver':'Independent solution','verifier':'Answer verification','calculator':'Mathematical checks','formatting':'Math formatting','retrieval':'Course evidence','publication':'Saving the question','provider':'AI service','generation':'Question generation','policy':'Policy checks'}

PUBLIC_REASONS |= frozenset({'Choose an AI provider and save its key and model in Settings before using AI study tools.','Add this provider’s API key in Settings before using AI study tools.'})
PUBLIC_REASONS |= frozenset({
    'The public task needs methods not supported by the retrieved course passages.',
    'The required methods could not be linked to exact course evidence.',
    'The reported numeric answer disagrees with its calculated outputs.',
    'The independent Solver returned conflicting MCQ selections.',
    'The independent Solver did not evaluate all four public options.',
    'The option evaluations rewrote a public option.',
    'The public MCQ does not have exactly one defensible option.',
    'The option evaluations disagree with the final selection.',
    'Keep one focused task; extended answers may have at most two connected parts. Do not add unrelated or hidden subparts.',
    *(f'Keep the public question within {limit} words and its focused workload ceiling. Supply helpful intermediate values instead of repetitive requests.' for limit in (180,300,400)),
})
LABELS['adversarial_review'] = 'Additional answer verification'

class StageFailure(RuntimeError):
    """A deliberately constructed, public-safe diagnosis, never a raw provider error."""
    def __init__(self, stage, reason):
        super().__init__(reason)
        self.pipeline_stage=stage
        self.public_reason=reason

def describe(exc):
    chain=[];current=exc
    while current is not None and len(chain)<8 and current not in chain:
        chain.append(current);current=current.__cause__ or current.__context__
    stage=next((getattr(e,'pipeline_stage','') for e in chain if getattr(e,'pipeline_stage','')), 'generation')
    reason=next((e.public_reason for e in chain if isinstance(e,StageFailure)), '')
    reason=reason or next((str(e) for e in chain if str(e) in PUBLIC_REASONS), '')
    if reason in {'The public task needs methods not supported by the retrieved course passages.',
                  'The required methods could not be linked to exact course evidence.'}:
        stage='retrieval'
    timed_out=any(isinstance(e,TimeoutError) or isinstance(e,HTTPException) and e.status_code==504 for e in chain)
    if reason:
        lower=reason.lower()
        if 'calculator' in lower or 'arithmetic' in lower or 'symbolic' in lower or 'numeric plan' in lower or 'numeric answer' in lower or 'displayed calculation' in lower or 'worked interpretation' in lower:stage='calculator'
        elif 'source' in lower and ('evidence' in lower or 'section' in lower):stage='retrieval' if stage in {'generation','retrieval'} else stage
    # Formatting diagnostics contain user text after KaTeX's colon: expose only known safe categories.
    formatting=' '.join(str(e).lower() for e in chain)
    if 'unclosed mathematical delimiter' in formatting:
        stage='formatting';reason='Unclosed mathematical delimiter.'
    elif 'mathematical formatting' in formatting:
        stage='formatting';reason='Mathematical formatting could not compile.'
    if timed_out:
        reason='This stage exceeded the generation time limit. Your previous study work is kept.'
    elif not reason:
        if any('delimiter' in str(e).lower() or 'katex' in str(e).lower() for e in chain):
            stage='formatting';reason='The mathematical notation could not be rendered safely.'
        elif any(getattr(e,'status_code',None)==429 for e in chain):
            stage='provider';reason='The AI provider is temporarily rate-limiting requests.'
        elif any(getattr(e,'status_code',None) in {401,403} for e in chain):
            stage='provider';reason='The AI provider rejected the configured credentials.'
        else:reason='An internal step could not complete safely. The diagnostic log contains the technical details.'
    label=LABELS.get(stage,LABELS['generation'])
    return {'error':f'{label}: {reason}', 'stage':stage, 'reason':reason, 'code':'generation_timeout' if timed_out else 'generation_rejected'}, 504 if timed_out else 422
