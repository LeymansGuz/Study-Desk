"""Local schema additions and access checks for durable request replay."""
import db

def initialize():
    with db.connect() as c:
        if 'deleting' not in {r['name'] for r in c.execute('PRAGMA table_info(users)')}:
            c.execute('ALTER TABLE users ADD COLUMN deleting INTEGER NOT NULL DEFAULT 0')
    import usage_aggregates
    usage_aggregates.initialize()
    import growth_limits
    growth_limits.initialize()
    import auth
    auth.initialize()

def replay_access(user, path, payload):
    import app as application
    import learning_store
    from fastapi import HTTPException
    if path.startswith('/ask/path'):
        value = learning_store.get('path', payload.get('id', ''), user['id'])
        if not value:
            raise HTTPException(409, 'This learning path is unavailable.')
        if application._course_access_lost(user['id'], value.get('course_ids') or []):
            raise HTTPException(403, 'Course documents changed.')
        if payload.get('index', 0) != value.get('index', 0):
            raise HTTPException(409, 'Resume the current stage.')
    if path.startswith('/bank-exams'):
        from bank_exam import load
        value = load(payload.get('id', ''), user['id'])
        if not value or payload.get('index') != value.get('index'):
            raise HTTPException(409, 'Resume the current bank exam from Learning tools.')
    if path in {'/ask', '/ask/question', '/answer'} or path.startswith('/practice/follow-up/'):
        identifier = payload.get('thread_id')
        if identifier:
            session = learning_store.get('tutor', identifier, user['id'])
            if not session:
                raise HTTPException(409, 'This saved session is unavailable.')
            application.study_extensions.check_path(session, user['id'])
            if application._course_access_lost(user['id'], session.get('course_ids') or []):
                raise HTTPException(403, 'Course documents changed.')
