"""Resumable exams assembled exclusively from current verified bank items."""
import secrets
import uuid
import io
from typing import Literal
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, Field
import curriculum
import db
import learning_store as store
from generation_control import atomic_generation
from tools import Difficulty, QuestionType
from fastapi.responses import StreamingResponse


class ExamRequest(BaseModel):
    course_id: str = Field(min_length=1, max_length=64)
    count: int = Field(default=5, ge=1, le=10)
    difficulty: Difficulty | Literal['any'] = 'any'
    question_type: QuestionType | Literal['any'] = 'any'


def load(identifier, user_id):
    exam = store.get('exam', identifier, user_id)
    if not exam or exam.get('source') != 'verified_bank':
        raise HTTPException(404, 'This bank exam is unavailable.')
    if any((q.get('assessment_version') or 0)<__import__('assessment_level').POLICY_VERSION for q in exam['items']):
        raise HTTPException(409,'A question in this paper needs current validation. Start a new bank exam.')
    course = exam['course_ids'][0]
    if not db.get_course(user_id, course) or exam['version'] != curriculum.scope_version(user_id, [course]):
        raise HTTPException(409, 'Course material changed. Start a new bank exam.')
    if any(store.is_quarantined(q['current_question']) for q in exam['items']):
        raise HTTPException(409, 'A bank question is unavailable. Start a new bank exam.')
    return exam


def check_session(values, user_id):
    exam = load(values['exam_id'], user_id)
    if values.get('path_step', 0) > exam['index']:
        raise HTTPException(409, 'Complete the preceding bank question first.')


def install(app, ns):
    graph, config = ns['graph'], ns['_config']
    require_user = ns['require_user']

    async def public(identifier, exam, user):
        values = (await graph.aget_state(config(exam['threads'][exam['index']]))).values
        if not values or values.get('user_id') != user['id']:
            raise HTTPException(409, 'This bank exam has expired.')
        question = ns['AskResponse'](thread_id=exam['threads'][exam['index']], mode='practice',
            difficulty=values['difficulty'], question=values['current_question'], question_type=values['question_type'],
            options=values.get('options') or [], status='awaiting_answer', attempts_used=values.get('user_attempts',0),
            max_attempts=values['max_attempts'], sources=ns['_sources'](values),
            verification=values.get('verification') or {}, figure=values.get('figure')).model_dump()
        terminal = values['status'] in {'correct','revealed','blocked'}
        completed = terminal and exam['index']==len(exam['items'])-1
        return {'id':identifier, 'index':exam['index'], 'count':len(exam['items']), 'question':question,
            'current_status':values['status'], 'history':values.get('history') or [],
            'completed':completed, 'can_advance':terminal and exam['index']<len(exam['items'])-1,
            'summary': await paper_summary(exam, user) if completed else None}

    async def paper_summary(exam, user):
        rows=[]
        if len(exam['threads']) != len(exam['items']):
            raise HTTPException(409, 'Finish every question before viewing the paper summary.')
        for index, thread in enumerate(exam['threads']):
            values=(await graph.aget_state(config(thread))).values
            if not values or values.get('user_id')!=user['id']:
                raise HTTPException(409, 'A question in this paper is unavailable.')
            if values.get('status') not in {'correct','revealed','blocked'}:
                raise HTTPException(409, 'Finish every question before viewing the paper summary.')
            rows.append({'number':index+1,'thread_id':thread,'question':values['current_question'],
                'difficulty':values['difficulty'],'question_type':values['question_type'],
                'status':values['status'],'attempts':values.get('user_attempts',0),
                'solved':values['status']=='correct',
                'first_attempt_correct':values['status']=='correct' and values.get('user_attempts')==1,
                'parts':values.get('part_results') or []})
        solved=sum(r['solved'] for r in rows)
        return {'total':len(rows),'solved':solved,'first_attempt_correct':sum(r['first_attempt_correct'] for r in rows),
            'needs_review':len(rows)-solved,'solved_percent':round(100*solved/len(rows),1),
            'attempts':sum(r['attempts'] for r in rows),'questions':rows,
            'scoring_note':'Each question counts equally. This is a practice completion summary, not an exam-mark prediction.'}

    @app.get('/bank-exams/{identifier}/summary/export')
    async def export_summary(identifier:str,user=Depends(require_user)):
        summary=await paper_summary(load(identifier,user['id']),user)
        lines=['# Verified bank paper summary',f"Solved: {summary['solved']} / {summary['total']} ({summary['solved_percent']}%)",
            f"Correct on first attempt: {summary['first_attempt_correct']}",summary['scoring_note']]
        for row in summary['questions']:
            lines.extend([f"\n## Question {row['number']}",row['question'],
                f"Result: {row['status']}; attempts: {row['attempts']}; difficulty: {row['difficulty']}; type: {row['question_type']}"])
        return StreamingResponse(io.BytesIO('\n\n'.join(lines).encode('utf-8')),media_type='text/markdown',
            headers={'Content-Disposition':'attachment; filename="study-paper-summary.md"','Cache-Control':'no-store'})

    async def prepare(identifier, exam, index, user):
        item = exam['items'][index]
        thread = uuid.uuid4().hex
        # Skip retrieval and generation nodes: this is an already verified bank item.
        state = ns['initial_state'](item.get('topic') or 'Bank practice', user_id=user['id'],
            course_ids=exam['course_ids'], difficulty=item['difficulty'], question_types=[item['question_type']],
            max_attempts=db.get_settings(user['id']).get('attempts_before_reveal',3))
        fields = ['current_question','question_type','options','canonical_answer','solution','answer_parts',
            'formula_focus','sources','skill_id','scope_key','course_overview','figure','assessment_version','verification']
        state.update({k:item[k] for k in fields if item.get(k) is not None})
        state.update(exam_id=identifier,path_step=index,status='awaiting_answer')
        try:
            await graph.aupdate_state(config(thread), state, as_node='generate_question')
            await graph.ainvoke(None, config(thread))
            if exam['version'] != curriculum.scope_version(user['id'], exam['course_ids']) or any(store.is_quarantined(q['current_question']) for q in exam['items']):
                raise HTTPException(409, 'Course evidence or bank eligibility changed. Start a new bank exam.')
            updated = {**exam,'threads':[*exam['threads'][:index],thread],'index':index}
            store.put('exam',identifier,user['id'],updated)
            store.mark_served(user['id'],item['current_question'])
            return await public(identifier,updated,user)
        except BaseException:
            await graph.checkpointer.adelete_thread(thread)
            raise

    @app.post('/bank-exams')
    async def start(req:ExamRequest, request:Request, user=Depends(require_user)):
        if not db.get_course(user['id'],req.course_id):
            raise HTTPException(404,'Choose an available course.')
        items = [q for q in store.bank_items(user['id'],req.course_id)
            if (req.difficulty=='any' or q['difficulty']==req.difficulty)
            and (req.question_type=='any' or q['question_type']==req.question_type)]
        if len(items)<req.count:
            raise HTTPException(409,f'Only {len(items)} verified questions match. Choose fewer questions or broaden the filters.')
        exam = {'source':'verified_bank','user_id':user['id'],'course_ids':[req.course_id],
            'version':curriculum.scope_version(user['id'],[req.course_id]),
            'items':secrets.SystemRandom().sample(items,req.count),'threads':[],'index':0,'topic':'Verified bank exam'}
        return await atomic_generation(lambda:prepare(uuid.uuid4().hex,exam,0,user))

    @app.get('/bank-exams/{identifier}')
    async def resume(identifier:str,user=Depends(require_user)):
        return await public(identifier,load(identifier,user['id']),user)

    @app.post('/bank-exams/{identifier}/next')
    async def advance(identifier:str,request:Request,user=Depends(require_user)):
        exam=load(identifier,user['id'])
        current=await public(identifier,exam,user)
        if current['completed']:
            return current
        if not current['can_advance']:
            raise HTTPException(409,'Finish this question before continuing.')
        return await atomic_generation(lambda:prepare(identifier,exam,exam['index']+1,user))
