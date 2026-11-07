"""LangGraph Socratic tutor workflow with RAG, lineage, and OPA enforcement.

Flow:
    START -> retrieve_context -> generate_question -> await_answer
          -> grade_answer -> (await_answer | END)

The graph pauses at `await_answer` with an interrupt.  Each student submission
resumes the same checkpointed thread.  OPA is consulted before the full solution
is placed in the grading prompt and before any answer reveal.
"""
from __future__ import annotations
import asyncio
import logging
import math
import time
from curriculum import plan_context
from typing import Annotated, Any, Literal, TypedDict
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import interrupt
import db
import learning_store
import generation_progress
from answer_parts import SolvedPart
from policy import decide
from retrieval import TOP_K, search
from tools import MAX_ATTEMPTS, TutorError, CandidateError, DuplicateQuestionError, Assessment, compose_correct, compose_hint, compose_reveal, choice_answer_correct, draft_question, evaluate_answer, generate_choice_hint, prepare_assignment_question
logger = logging.getLogger(__name__)

TutorStatus = Literal['generating', 'awaiting_answer', 'correct', 'revealed', 'blocked']

class TutorState(TypedDict, total=False):
    verification: dict
    exam_id: str
    path_id: str
    path_step: int
    assessment_version: int
    figure_mode: str
    figure: dict[str, Any] | None
    messages: Annotated[list[AnyMessage], add_messages]
    mode: Literal['practice', 'question']
    topic: str
    incoming_question: str
    difficulty: str
    question_types: list[str]
    user_id: str
    course_ids: list[str]
    doc_types: list[str]
    scope: str
    scope_key: str
    skill_id: str
    course_overview: str
    recent_questions: list[str]
    current_question: str
    question_type: str
    options: list[str]
    canonical_answer: str
    answer_parts: list[dict[str, Any]]
    criterion_results: list[dict[str, Any]]
    part_results: list[dict[str, Any]]
    solution: str
    formula_focus: str
    opening_hint: str
    pending_answer: str
    user_attempts: int
    max_attempts: int
    status: TutorStatus
    last_feedback: str
    last_verdict: str
    history: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    policy_decisions: list[dict[str, Any]]
    bank_id: str
    follow_up_question: str
    focus_skill_id: str
    bank_checked: bool
    bank_candidate: dict[str, Any] | None

def initial_state(topic: str, mode: Literal['practice', 'question']='practice', question: str='', difficulty: str='medium', question_types: list[str] | None=None, user_id: str='', course_ids: list[str] | None=None, doc_types: list[str] | None=None, max_attempts: int=MAX_ATTEMPTS, scope: str='topic', figure_mode: str='auto') -> TutorState:
    return {'figure_mode': figure_mode, 'messages': [], 'mode': mode, 'scope': scope, 'topic': topic.strip(), 'incoming_question': question.strip(), 'difficulty': difficulty, 'question_types': list(question_types or ['short_answer']), 'user_id': user_id, 'course_ids': list(course_ids or []), 'doc_types': list(doc_types or []), 'current_question': '', 'question_type': 'short_answer', 'options': [], 'canonical_answer': '', 'solution': '', 'formula_focus': '', 'opening_hint': '', 'pending_answer': '', 'user_attempts': 0, 'max_attempts': max(1, min(5, int(max_attempts))), 'status': 'generating', 'last_feedback': '', 'last_verdict': '', 'history': [], 'sources': [], 'policy_decisions': []}

async def retrieve_context(state: TutorState) -> dict[str, Any]:
    """Retrieve course chunks for this user and optional course scope."""
    generation_progress.stage(generation_progress.STAGE_ANALYZING)
    if state.get('mode') == 'question':
        query = (state.get('incoming_question') or '')[:2000]
    else:
        query = (state.get('topic') or '').strip()
    if state.get('mode') == 'practice' and state.get('user_id'):
        started = time.perf_counter()
        import curriculum
        banked = None if state.get('follow_up_question') else await asyncio.to_thread(learning_store.bank_take, state['user_id'], curriculum.scope_version(state['user_id'], state.get('course_ids', [])), state.get('course_ids', []), state.get('difficulty', 'medium'), state.get('question_types') or ['short_answer'], state.get('doc_types'), state.get('topic', ''), state.get('scope') == 'syllabus', figure_mode=state.get('figure_mode', 'none'))
        if banked:
            logger.info('pipeline stage=retrieval bank_hit=true seconds=%.3f', time.perf_counter() - started)
            return {'bank_checked': True, 'bank_candidate': banked}
        try:
            context = await asyncio.to_thread(plan_context, state['user_id'], list(state.get('course_ids') or []), query, whole=state.get('scope') == 'syllabus', doc_types=state.get('doc_types') or None, figure_mode=state.get('figure_mode', 'auto'), target_skill_id=state.get('focus_skill_id'))
        except ValueError as exc:
            raise TutorError(str(exc)) from exc
        plan = context['plans'][0]
        logger.info('pipeline stage=retrieval seconds=%.3f', time.perf_counter() - started)
        return {'bank_checked': True, 'bank_candidate': None, 'sources': plan['sources'], 'skill_id': plan['skill_id'], 'scope_key': context['scope_key'], 'topic': plan['topic'], 'course_overview': context['overview'], 'recent_questions': [*context['recent_questions'], *([state['follow_up_question']] if state.get('follow_up_question') else [])]}
    selected_types = list(state.get('doc_types') or [])
    sources = await asyncio.to_thread(search, query, state.get('user_id', ''), TOP_K, None, list(state.get('course_ids') or []), selected_types or None)
    return {'sources': sources}

async def generate_question(state: TutorState) -> dict[str, Any]:
    from practice_novelty import task_text
    from pipeline_runtime import set_generation_profile
    set_generation_profile(state.get('difficulty','medium'),state.get('question_types'))
    """Generate a practice question, or privately solve a supplied question."""
    generation_progress.stage(generation_progress.STAGE_DRAFTING)
    sources = list(state.get('sources') or [])
    difficulty = state.get('difficulty', 'medium')
    opening_hint = ''
    if state.get('mode') == 'question':
        draft = await prepare_assignment_question(state.get('incoming_question', ''), sources, difficulty)
        opening_hint = draft.opening_hint
        logger.info('Prepared assignment question with %s retrieved sources', len(sources))
    else:
        topic = (state.get('topic') or '').strip()
        if not topic:
            raise ValueError('A topic is required to generate a question.')
        user_id = state.get('user_id', '')
        import curriculum
        banked = state.get('bank_candidate')
        if user_id and (not state.get('bank_checked')) and (not state.get('follow_up_question')):
            banked = await asyncio.to_thread(learning_store.bank_take, user_id, curriculum.scope_version(user_id, state.get('course_ids', [])), state.get('course_ids', []), difficulty, state.get('question_types') or ['short_answer'], state.get('doc_types'), state.get('topic', ''), state.get('scope') == 'syllabus', figure_mode=state.get('figure_mode', 'none'))
        if banked:
            if banked.get('question_type') == 'mcq' and banked.get('options'):
                from tools import QuestionDraft, shuffle_choice_draft
                shuffled = shuffle_choice_draft(QuestionDraft(question=banked['current_question'], question_type='mcq', options=list(banked.get('options') or []), canonical_answer=banked.get('canonical_answer', ''), solution=banked.get('solution', '')))
                banked['options'] = shuffled.options
                banked['canonical_answer'] = shuffled.canonical_answer
                banked['solution'] = shuffled.solution
            db.record_exposure(user_id, banked['scope_key'], banked['skill_id'], task_text(banked['current_question'],banked.get('options')), [s['chunk_id'] for s in banked['sources']])
            return {'bank_candidate': None, 'bank_checked': True, **{key: value for key, value in banked.items() if key in TutorState.__annotations__}, 'bank_id': banked['fingerprint'], 'status': 'awaiting_answer', 'user_attempts': 0, 'part_results': [], 'history': [], 'pending_answer': '', 'last_feedback': '', 'messages': [AIMessage(content=banked['current_question'])]}
        recent_questions = list(state.get('recent_questions') or [])
        from practice_novelty import history
        retained=await asyncio.to_thread(history,user_id)
        seen_questions=list(dict.fromkeys([*recent_questions,*(row['question'] for row in retained)]))
        draft = None
        skill_id = state.get('skill_id', '')
        rejected_skills = []
        retry_feedback = ''
        for variation_attempt in range(3):
            try:
                writer = draft_question
                if state.get('figure_mode') == 'auto' and variation_attempt == 0:
                    from functools import partial
                    from math_figures import draft_automatic
                    writer = partial(draft_automatic, draft_question)
                elif state.get('figure_mode') == 'math':
                    from math_figures import draft_visual
                    writer = draft_visual
                from tools import DRAFT_FEEDBACK, NOVELTY_HISTORY
                feedback_token = DRAFT_FEEDBACK.set(retry_feedback)
                novelty_token=NOVELTY_HISTORY.set(seen_questions)
                try:
                    draft = await writer(topic, sources, difficulty, list(state.get('question_types') or ['short_answer']), avoid_questions=recent_questions, course_context=state.get('course_overview', ''))
                finally:
                    DRAFT_FEEDBACK.reset(feedback_token)
                    NOVELTY_HISTORY.reset(novelty_token)
                from semantic_duplicates import duplicate
                if await asyncio.to_thread(duplicate,task_text(draft.question,draft.options),seen_questions):
                    raise DuplicateQuestionError('The draft repeated a recent problem.',feedback='This proposed task repeats a retained question: '+draft.question[:1800]+' Change the inference or information flow, not just names or numbers.')
                if learning_store.is_quarantined(draft.question):
                    raise CandidateError('This question template is paused for review.')
                import monitoring
                monitoring.candidate(user_id, sources, skill_id, 'verified')
                break
            except CandidateError as failure:
                from tools import ArithmeticRepairError
                if isinstance(failure, ArithmeticRepairError):
                    raise
                from pipeline_runtime import set_repair_profile
                set_repair_profile()
                retry_feedback = failure.feedback
                failed_draft=getattr(failure,'draft',None) or draft
                if failed_draft is not None:
                    recent_questions=list(dict.fromkeys([*recent_questions,task_text(failed_draft.question,failed_draft.options)]))[-32:]
                    seen_questions=list(dict.fromkeys([*seen_questions,task_text(failed_draft.question,failed_draft.options)]))
                import monitoring
                reason = 'duplicate' if isinstance(failure, DuplicateQuestionError) else 'scope' if 'support' in str(failure).lower() or 'scope' in str(failure).lower() else 'rejected'
                monitoring.candidate(user_id, sources, skill_id, reason)
                if variation_attempt == 2 or not user_id:
                    raise
                rejected_skills.append(skill_id)
                try:
                    context = await asyncio.to_thread(plan_context, user_id, list(state.get('course_ids') or []), state.get('topic', topic), whole=state.get('scope') == 'syllabus', doc_types=state.get('doc_types') or None, exclude_skill_ids=rejected_skills, figure_mode=state.get('figure_mode', 'auto'), target_skill_id=state.get('focus_skill_id'))
                except ValueError as exc:
                    # A narrow topic can have one sound evidence set yet many original tasks.
                    # Keep it for the remaining bounded, feedback-guided attempt; never return a repeat.
                    continue
                plan = context['plans'][0]
                skill_id, sources, topic = (plan['skill_id'], plan['sources'], plan['topic'])
        if draft is None:
            raise TutorError('Repeated drafts were too similar to recent questions. Choose another topic or try again.')
        if user_id and state.get('scope_key'):
            db.record_exposure(user_id, state['scope_key'], skill_id, task_text(draft.question,draft.options), [source['chunk_id'] for source in sources])
        logger.info('Generated verified question difficulty=%s with %s sources', difficulty, len(sources))
    return {'sources': sources, 'topic': draft.formula_focus[:200] if state.get('scope') == 'syllabus' and draft.formula_focus else state.get('topic', ''), 'verification': draft.verification, 'assessment_version': __import__('assessment_level').POLICY_VERSION, 'figure': draft.figure, 'skill_id': locals().get('skill_id', state.get('skill_id', '')), 'messages': [AIMessage(content=draft.question)], 'current_question': draft.question, 'question_type': draft.question_type, 'options': draft.options, 'canonical_answer': draft.canonical_answer, 'answer_parts': [part.model_dump() for part in draft.answer_parts], 'part_results': [], 'solution': draft.solution, 'formula_focus': draft.formula_focus, 'opening_hint': opening_hint, 'pending_answer': '', 'user_attempts': 0, 'max_attempts': state.get('max_attempts', MAX_ATTEMPTS), 'status': 'awaiting_answer', 'last_feedback': '', 'last_verdict': '', 'history': [], 'policy_decisions': []}

async def await_answer(state: TutorState) -> dict[str, Any]:
    """Pause the graph until the caller resumes it with a student answer."""
    answer = interrupt({'type': 'student_answer_required', 'question': state.get('current_question', ''), 'attempt': state.get('user_attempts', 0) + 1, 'max_attempts': state.get('max_attempts', MAX_ATTEMPTS)})
    answer_text = str(answer).strip()
    if not answer_text:
        raise ValueError('The student answer cannot be empty.')
    return {'messages': [HumanMessage(content=answer_text)], 'pending_answer': answer_text}

async def grade_answer(state: TutorState) -> dict[str, Any]:
    """Grade one attempt and enforce the OPA policy gates."""
    answer = (state.get('pending_answer') or '').strip()
    attempt = state.get('user_attempts', 0) + 1
    max_attempts = state.get('max_attempts', MAX_ATTEMPTS)
    canonical_answer = state.get('canonical_answer', '')
    solution = state.get('solution', '')
    sources = list(state.get('sources') or [])
    decisions = list(state.get('policy_decisions') or [])
    judge_decision, access_decision = await asyncio.gather(decide('judge_answer', attempts=attempt, max_attempts=max_attempts), decide('access_solution_key', attempts=attempt, max_attempts=max_attempts))
    decisions.extend([judge_decision, access_decision])
    if not judge_decision['allow']:
        feedback = f"Grading is blocked because the policy engine could not authorize the private grading step. The tutor is failing closed and did not send the answer key to the model.\n\nPolicy reason: {judge_decision['reason']}"
        history = list(state.get('history') or [])
        history.append({'attempt': attempt, 'answer': answer, 'verdict': 'blocked_by_policy', 'feedback': feedback, 'used_source_refs': [], 'policy': [judge_decision, access_decision]})
        return {'messages': [AIMessage(content=feedback)], 'user_attempts': attempt, 'status': 'blocked', 'last_feedback': feedback, 'last_verdict': 'blocked_by_policy', 'pending_answer': '', 'history': history, 'policy_decisions': decisions}
    allow_solution = bool(access_decision['allow'])
    hint_level = min(3, max(1, math.ceil(3 * attempt / max(1, max_attempts)) + (1 if state.get('mode') == 'question' else 0)))
    choice_correct = None
    if state.get('question_type') in {'mcq', 'true_false'}:
        choice_correct = choice_answer_correct(answer, list(state.get('options') or []), canonical_answer, state.get('question_type', 'mcq'))
    if choice_correct is not None:
        if choice_correct or attempt >= max_attempts:
            hint = ''
        else:
            try:
                hint = await generate_choice_hint(question=state.get('current_question', ''), options=list(state.get('options') or []), student_answer=answer, answer_key=canonical_answer, question_type=state.get('question_type', 'mcq'), attempt=attempt, max_attempts=max_attempts)
            except Exception:
                hint = 'That choice is not the answer key. Re-read the question and compare each option with the relevant definition or calculation.'
        assessment = Assessment(is_correct=choice_correct, verdict='correct' if choice_correct else 'incorrect', reasoning='The selected option matches the answer key.' if choice_correct else 'The selected option does not match the answer key.', hint=hint, used_source_refs=[])
    else:
        assessment = await evaluate_answer(question=state.get('current_question', ''), canonical_answer=canonical_answer, solution=solution, student_answer=answer, attempt=attempt, max_attempts=max_attempts, sources=sources, allow_solution=allow_solution, difficulty=state.get('difficulty', 'medium'), hint_level=hint_level, answer_parts=[SolvedPart.model_validate(part) for part in state.get('answer_parts', [])], previous_parts=state.get('part_results', []), question_type=state.get('question_type', 'short_answer'))
    if assessment.is_correct:
        confirm_decision = await decide('confirm_correct', attempts=attempt, max_attempts=max_attempts)
        decisions.append(confirm_decision)
        feedback = compose_correct(assessment=assessment, canonical_answer=canonical_answer, solution=solution, include_solution=allow_solution and bool(confirm_decision['allow']), sources=sources)
        status: TutorStatus = 'correct'
    elif attempt >= max_attempts:
        reveal_decision = await decide('reveal_answer', attempts=attempt, max_attempts=max_attempts)
        decisions.append(reveal_decision)
        if reveal_decision['allow'] and allow_solution:
            feedback = compose_reveal(canonical_answer=canonical_answer, solution=solution, max_attempts=max_attempts, sources=sources, assessment=assessment)
            status = 'revealed'
        else:
            feedback = f"The attempt limit has been reached, but the policy engine did not authorize releasing the answer key. The tutor is failing closed.\n\nPolicy reason: {reveal_decision['reason']}"
            status = 'blocked'
    else:
        hint_decision = await decide('generate_hint', attempts=attempt, max_attempts=max_attempts)
        decisions.append(hint_decision)
        feedback = compose_hint(assessment=assessment, canonical_answer=canonical_answer, formula_focus=state.get('formula_focus', ''), attempt=attempt, max_attempts=max_attempts, sources=sources)
        if not hint_decision['allow']:
            feedback = f"The policy engine did not authorize a model-generated hint, so here is a generic Socratic prompt: What is the first formula or no-arbitrage relationship that applies to this question?\n\nPolicy reason: {hint_decision['reason']}"
        status = 'awaiting_answer'
    history = list(state.get('history') or [])
    history.append({'attempt': attempt, 'answer': answer, 'verdict': assessment.verdict, 'feedback': feedback, 'used_source_refs': assessment.used_source_refs, 'parts': [part.model_dump() for part in assessment.parts], 'criteria': [row.model_dump() for row in assessment.criteria], 'policy': [judge_decision, access_decision, *([confirm_decision] if assessment.is_correct else [reveal_decision] if attempt >= max_attempts else [hint_decision])]})
    return {'messages': [AIMessage(content=feedback)], 'user_attempts': attempt, 'status': status, 'last_feedback': feedback, 'last_verdict': assessment.verdict, 'part_results': [part.model_dump() for part in assessment.parts], 'criterion_results': [row.model_dump() for row in assessment.criteria], 'pending_answer': '', 'history': history, 'policy_decisions': decisions}

def route_after_grade(state: TutorState) -> str:
    if state.get('status') == 'awaiting_answer':
        return 'await_answer'
    return END

def build_graph():
    builder = StateGraph(TutorState)
    builder.add_node('retrieve_context', retrieve_context)
    builder.add_node('generate_question', generate_question)
    builder.add_node('await_answer', await_answer)
    builder.add_node('grade_answer', grade_answer)
    builder.add_edge(START, 'retrieve_context')
    builder.add_edge('retrieve_context', 'generate_question')
    builder.add_edge('generate_question', 'await_answer')
    builder.add_edge('await_answer', 'grade_answer')
    builder.add_conditional_edges('grade_answer', route_after_grade, {'await_answer': 'await_answer', END: END})
    return builder.compile(checkpointer=InMemorySaver())
from durable_learning import DurableGraph
graph = DurableGraph(build_graph())
