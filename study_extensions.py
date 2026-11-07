"""Authenticated verification, source lineage and concept learning paths."""
import asyncio, base64, io, re, threading, time, uuid
from contextlib import closing
from generation_control import generation_endpoint
from rate_limits import generation_limit, limiter, account_key
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, Field, ConfigDict, field_validator
import db, learning_store, observability, tools
PDF_LOCK = threading.Lock()

async def public_verification(values, elapsed):
    from graph import decide
    from verification_metadata import public_fields
    metadata = public_fields(values.get('verification'))
    cap = values.get('max_attempts', 3)
    hint, reveal = await asyncio.gather(decide('generate_hint', attempts=0, max_attempts=cap), decide('reveal_answer', attempts=0, max_attempts=cap))
    metadata.update(opa_passed=bool(hint['allow'] and (not reveal['allow']) and (hint.get('engine') == 'opa') and (reveal.get('engine') == 'opa')), latency=elapsed)
    return metadata

async def attach_verification(values, thread_id, elapsed, user_id, graph, config):
    metadata = await public_verification(values, elapsed)
    await graph.aupdate_state(config(thread_id), {'verification': metadata})
    saved = learning_store.get('tutor', thread_id, user_id)
    if saved:
        saved['verification'] = metadata
        learning_store.put('tutor', thread_id, user_id, saved)
    return metadata

class PathRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    topic: str = Field(min_length=2, max_length=200)
    course_ids: list[str] = Field(min_length=1, max_length=12)
    question_type: tools.QuestionType
    doc_types: list[str] = Field(default_factory=list, max_length=6)

    @field_validator('topic')
    @classmethod
    def specific_topic(cls, value):
        value = value.strip()
        if len(value) < 2 or value.casefold() in {'any syllabus topic', 'whole syllabus review', 'all topics', 'random topic'}:
            raise ValueError('Enter a specific topic for the mastery path.')
        return value

    @field_validator('doc_types')
    @classmethod
    def source_types(cls, value):
        if not set(value) <= {'syllabus','notes','past_paper','exercise','marking_scheme','exam_report'}:
            raise ValueError('Unknown document type.')
        return value


def check_path(values, user_id):
    if values.get('exam_id'):
        from bank_exam import check_session
        check_session(values, user_id)
    if not values.get('path_id'):
        return
    path = learning_store.get('path', values['path_id'], user_id)
    if not path or values.get('path_step', 0) > path.get('index', 0):
        raise HTTPException(409, 'Complete the preceding learning-path stage first.')

def pdf_page(path, page_number, text):
    import pypdfium2 as pdfium
    with PDF_LOCK, pdfium.PdfDocument(str(path)) as document:
        if not 1 <= page_number <= len(document):
            raise ValueError('Source page is unavailable.')
        with closing(document[page_number - 1]) as page:
            width, height = page.get_size()
            rectangles = []
            with closing(page.get_textpage()) as textpage:
                phrases = re.findall('[A-Za-z][A-Za-z0-9 ,;:()\\-]{35,120}', text[:6000])[:12]
                for phrase in sorted(phrases, key=len, reverse=True):
                    with closing(textpage.search(phrase.strip())) as search:
                        match = search.get_next()
                        if match:
                            count = textpage.count_rects(*match)
                            for index in range(min(count, 30)):
                                left, bottom, right, top = textpage.get_rect(index)
                                rectangles.append({'x': left / width, 'y': 1 - top / height, 'width': (right - left) / width, 'height': (top - bottom) / height})
                            break
            scale = min(1.5, 1600 / max(width, height))
            bitmap = page.render(scale=scale)
            try:
                output = io.BytesIO()
                bitmap.to_pil().save(output, format='PNG')
                image = base64.b64encode(output.getvalue()).decode()
            finally:
                bitmap.close()
    return {'image': 'data:image/png;base64,' + image, 'rectangles': rectangles, 'highlight_matched': bool(rectangles)}

def install(app, ns):
    require_user = ns['require_user']
    graph = ns['graph']
    config = ns['_config']

    async def snapshot(identifier, user):
        value = await graph.aget_state(config(identifier))
        if not value.values or value.values.get('user_id') != user['id']:
            raise HTTPException(404, 'Unknown study session.')
        check_path(value.values, user['id'])
        if ns['_course_access_lost'](user['id'], value.values.get('course_ids')):
            raise HTTPException(409, 'A course in this session is no longer accessible.')
        return value.values

    @app.get('/session/{identifier}/evidence/{ref}', tags=['tutor'])
    async def evidence(identifier: str, ref: str, user=Depends(require_user)):
        values = await snapshot(identifier, user)
        source = next((s for s in values.get('sources', []) if s.get('ref') == ref), None)
        if not source:
            raise HTTPException(404, 'Unknown source reference.')
        course = db.get_course(user['id'], source['course_id']) or None
        if not course:
            raise HTTPException(404, 'Source course is unavailable.')
        document = next((d for d in db.list_documents(course['user_id'], [course['id']]) if d['filename'] == source['source_file']), None)
        if not document:
            raise HTTPException(404, 'Original source document is unavailable.')
        path = ns['_document_file_path'](course['user_id'], document)
        prefix = f"/workspace/documents/{document['id']}" if course['user_id'] == user['id'] else f"/workspace/shared/{course['id']}/documents/{document['id']}"
        result = {'question': values['current_question'], 'source': source, 'original_url': prefix + '/file#page=' + str(source['page']), 'highlight_matched': False}
        if path.suffix.lower() == '.pdf':
            try:
                result.update(await asyncio.to_thread(pdf_page, path, int(source['page']), source['text']))
            except (ValueError, RuntimeError):
                result['notice'] = 'This page could not be rendered. Open the original document.'
        return result

    def load_path(identifier, user):
        path = learning_store.get('path', identifier, user['id'])
        if not path:
            raise HTTPException(404, 'Unknown learning path.')
        if ns['_course_access_lost'](user['id'], path['course_ids']):
            raise HTTPException(409, 'A course in this path is no longer accessible.')
        return path

    async def public_path(identifier, path, user):
        index = path['index']
        values = await snapshot(path['threads'][index], user)
        response = {'id': identifier, 'topic': path['topic'], 'index': index, 'stages': ['Foundation', 'Application', 'Synthesis'], 'completed': index == 2 and values.get('status') == 'correct', 'can_advance': values.get('status') == 'correct' and index < 2, 'question_type': path.get('question_type', values['question_type'])}
        response['question'] = ns['AskResponse'](verification=values.get('verification') or {}, thread_id=path['threads'][index], mode='practice', difficulty=values['difficulty'], question=values['current_question'], question_type=values['question_type'], options=values.get('options') or [], status='awaiting_answer', attempts_used=values.get('user_attempts', 0), max_attempts=values['max_attempts'], sources=ns['_sources'](values), criteria=ns['extended_criteria'](values['current_question'], values['question_type']), figure=values.get('figure')).model_dump()
        response['current_status'] = values.get('status')
        response['history'] = [{k: r[k] for k in ['attempt', 'answer', 'feedback'] if k in r} for r in values.get('history', [])]
        return response

    async def generate_stage(identifier, path, index, user):
        """One normal, fully verified generation; publish the stage only on success."""
        import curriculum
        version = curriculum.scope_version(user['id'], path['course_ids'])
        if version != path['version']:
            raise HTTPException(409, 'Course material changed. Start a fresh mastery path.')
        thread = uuid.uuid4().hex
        started = time.perf_counter()
        try:
            level = ('easy', 'medium', 'insane')[index]
            async with observability.operation('learning_path_item', user['id'], identifier,
                    question_number=str(index + 1), difficulty=level, question_type=path['question_type']):
                state = ns['initial_state'](path['topic'], user_id=user['id'], course_ids=path['course_ids'],
                    difficulty=level, question_types=[path['question_type']], doc_types=path.get('doc_types', []),
                    max_attempts=db.get_settings(user['id']).get('attempts_before_reveal', 3))
                state.update(path_id=identifier, path_step=index)
                values = await graph.ainvoke(state, config(thread))
                if not values.get('current_question') or values.get('question_type') != path['question_type']:
                    raise tools.TutorError('The requested question type could not be prepared.')
                if version != curriculum.scope_version(user['id'], path['course_ids']):
                    raise HTTPException(409, 'Course material changed. Start a fresh mastery path.')
                await attach_verification(values, thread, round(time.perf_counter()-started,3), user['id'], graph, config)
                learning_store.mark_served(user['id'], values['current_question'])
                updated = {**path, 'threads': [*path['threads'][:index], thread], 'index': index}
                learning_store.put('path', identifier, user['id'], updated)
                return await public_path(identifier, updated, user)
        except BaseException:
            await graph.checkpointer.adelete_thread(thread)
            raise

    @app.post('/ask/path', tags=['tutor'])
    @generation_limit
    @generation_endpoint
    async def start_path(req: PathRequest, request: Request, user=Depends(require_user)):
        import curriculum
        courses = ns['_resolve_course_scope'](user['id'], req.course_ids)
        identifier = uuid.uuid4().hex
        payload = {'user_id': user['id'], 'topic': req.topic, 'course_ids': courses,
            'question_type': req.question_type, 'doc_types': req.doc_types,
            'version': curriculum.scope_version(user['id'], courses), 'threads': [], 'index': 0, 'status': 'awaiting_answer'}
        return await generate_stage(identifier, payload, 0, user)

    @app.get('/ask/path/{identifier}', tags=['tutor'])
    async def get_path(identifier: str, user=Depends(require_user)):
        return await public_path(identifier, load_path(identifier, user), user)

    @app.post('/ask/path/{identifier}/next', tags=['tutor'])
    @generation_limit
    @generation_endpoint
    async def next_path(identifier: str, request: Request, user=Depends(require_user)):
        path = load_path(identifier, user)
        values = await snapshot(path['threads'][path['index']], user)
        if values.get('status') != 'correct':
            raise HTTPException(409, 'Pass this stage before continuing.')
        if path['index'] == 2:
            return await public_path(identifier, path, user)
        # Older saved paths already contain later verified stages.
        index = path['index'] + 1
        if index < len(path['threads']):
            updated = {**path, 'index': index}
            learning_store.put('path', identifier, user['id'], updated)
            return await public_path(identifier, updated, user)
        return await generate_stage(identifier, path, index, user)
