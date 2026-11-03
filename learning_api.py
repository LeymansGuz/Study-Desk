"""Read-only learning tools; no user-triggered model jobs or source editing."""
from __future__ import annotations
import asyncio
import uuid
from fastapi import APIRouter, Depends, HTTPException
import db
import learning_store as store
import retrieval
from auth import current_user
router = APIRouter(prefix='/learning', tags=['learning'])

def access(user, course):
    owner = user['id'] if db.get_course(user['id'], course) else {}.get(course)
    if not owner:
        raise HTTPException(404, 'Course not found.')
    return owner

def owner_only(user=Depends(current_user)):
    if not user.get('is_admin'):
        raise HTTPException(403, 'Quality diagnostics are available only to the site owner.')
    return user

async def close():
    """Read-only learning tools require no worker shutdown."""

@router.get('/dashboard')
async def dashboard(user=Depends(current_user)):
    courses = [{'id': c['id'], 'name': c['name']} for c in db.list_courses(user['id'])]
    for course, owner in {}.items():
        row = db.get_course(owner, course)
        if row:
            courses.append({'id': course, 'name': row['name']})
    return {'courses': courses, 'sessions': store.session_summaries(user['id']), 'is_owner': bool(user.get('is_admin'))}

@router.get('/courses/{course}/bank')
async def bank_counts(course: str, user=Depends(current_user)):
    access(user, course)
    return await asyncio.to_thread(store.bank_counts, user['id'], course)

@router.get('/quality')
async def quality(user=Depends(owner_only)):
    return {'checks': ['Course evidence and syllabus grounding', 'Blind solution and LLM consistency review', 'Calculator and bounded symbolic checks when applicable', 'Per-part grading expectations', 'OPA rules for grading, hints and answer disclosure', 'Repeated-question and quarantine checks'], 'benchmarks': store.listing('benchmark_run', user['id'], 8)}

@router.post('/benchmarks/reference')
async def benchmark(user=Depends(owner_only)):
    from quality_benchmark import run_reference
    result = await asyncio.to_thread(run_reference)
    store.put('benchmark_run', uuid.uuid4().hex, user['id'], result)
    return result

@router.get('/courses/{course}/extraction')
async def extraction(course: str, user=Depends(current_user)):
    owner = access(user, course)
    return {'documents': db.list_documents(owner, [course]), 'coverage': db.extraction_coverage(owner, [course]), 'shared': owner != user['id']}

@router.get('/courses/{course}/pages/{filename}/{page}/transcript')
async def transcript(course: str, filename: str, page: int, user=Depends(current_user)):
    owner = access(user, course)
    if '/' in filename or '\\' in filename or filename.startswith('.') or (not 1 <= page <= 2000):
        raise HTTPException(404, 'Source page not found.')
    document = next((d for d in db.list_documents(owner, [course]) if d['filename'] == filename), None)
    if not document:
        raise HTTPException(404, 'Source document not found.')

    def read():
        where = {'$and': [{'course_id': course}, {'source_file': filename}, {'page': page}]}
        rows = list(retrieval._all_records(retrieval._get_collection(owner), where))
        rows.sort(key=lambda row: int((row[2] or {}).get('chunk_index', 0)))
        return [{'number': index + 1, 'text': text} for index, (_, text, _) in enumerate(rows)]
    return {'filename': filename, 'page': page, 'chunks': await asyncio.to_thread(read), 'read_only': True, 'note': 'Already indexed extracted text; adjacent chunks can overlap. No new OCR is run.'}

def install(application):
    application.include_router(router)
