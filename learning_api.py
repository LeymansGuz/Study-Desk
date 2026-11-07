"""Read-only learning tools; no user-triggered model jobs or source editing."""
from __future__ import annotations
import asyncio
from fastapi import APIRouter, Depends, HTTPException
import db
import learning_store as store
from auth import current_user
router = APIRouter(prefix='/learning', tags=['learning'])

def access(user, course):
    owner = user['id'] if db.get_course(user['id'], course) else None
    if not owner:
        raise HTTPException(404, 'Course not found.')
    return owner

@router.get('/dashboard')
async def dashboard(user=Depends(current_user)):
    courses = [{'id': c['id'], 'name': c['name']} for c in db.list_courses(user['id'])]
    return {'courses': courses, 'sessions': store.session_summaries(user['id']), 'is_owner': bool(user.get('is_admin'))}

@router.get('/courses/{course}/bank')
async def bank_counts(course: str, user=Depends(current_user)):
    access(user, course)
    return await asyncio.to_thread(store.bank_counts, user['id'], course)

def install(application):
    application.include_router(router)
