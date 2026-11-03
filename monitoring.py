"""Bounded local generation diagnostics; no model calls."""
import json
import time
import uuid
import db

def initialize():
    with db.connect() as c:
        c.executescript("\n        CREATE TABLE IF NOT EXISTS quality_events(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,course_id TEXT NOT NULL,skill_id TEXT NOT NULL,event TEXT NOT NULL,created REAL NOT NULL);\n        CREATE INDEX IF NOT EXISTS quality_event_scope ON quality_events(user_id,course_id,skill_id,created);\n        CREATE TRIGGER IF NOT EXISTS retain_quality_events AFTER INSERT ON quality_events WHEN (SELECT COUNT(*) FROM quality_events)>10000 BEGIN DELETE FROM quality_events WHERE rowid IN (SELECT rowid FROM quality_events ORDER BY created ASC LIMIT (SELECT MAX(0,COUNT(*)-10000) FROM quality_events)); END;\n        CREATE TABLE IF NOT EXISTS generation_events(\n            id TEXT PRIMARY KEY,\n            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,\n            operation_id TEXT,\n            request_id TEXT NOT NULL DEFAULT '',\n            session_id TEXT NOT NULL DEFAULT '',\n            stage TEXT NOT NULL DEFAULT '',\n            outcome TEXT NOT NULL DEFAULT '',\n            reason TEXT NOT NULL DEFAULT '',\n            feedback TEXT NOT NULL DEFAULT '',\n            difficulty TEXT NOT NULL DEFAULT '',\n            question_type TEXT NOT NULL DEFAULT '',\n            skill_id TEXT NOT NULL DEFAULT '',\n            course_ids TEXT NOT NULL DEFAULT '[]',\n            source_count INTEGER NOT NULL DEFAULT 0,\n            question TEXT NOT NULL DEFAULT '',\n            canonical_answer TEXT NOT NULL DEFAULT '',\n            solution TEXT NOT NULL DEFAULT '',\n            review_json TEXT NOT NULL DEFAULT '{}',\n            detail_json TEXT NOT NULL DEFAULT '{}',\n            duration_ms REAL,\n            created REAL NOT NULL\n        );\n        CREATE INDEX IF NOT EXISTS generation_event_user_time ON generation_events(user_id,created DESC);\n        CREATE INDEX IF NOT EXISTS generation_event_outcome ON generation_events(outcome,created DESC);\n        CREATE TRIGGER IF NOT EXISTS retain_generation_events AFTER INSERT ON generation_events WHEN (SELECT COUNT(*) FROM generation_events)>20000 BEGIN DELETE FROM generation_events WHERE rowid IN (SELECT rowid FROM generation_events ORDER BY created ASC LIMIT (SELECT MAX(0,COUNT(*)-20000) FROM generation_events)); END;\n        \n        ")
        if 'request_id' not in {row['name'] for row in c.execute('PRAGMA table_info(quality_events)')}:
            c.execute("ALTER TABLE quality_events ADD COLUMN request_id TEXT NOT NULL DEFAULT ''")
        c.execute("UPDATE generation_events SET session_id=COALESCE((SELECT o.session_id FROM operations o WHERE o.id=generation_events.operation_id),'') WHERE session_id='' AND operation_id IS NOT NULL")

def record_generation(event, user_id, *, outcome='', reason='', feedback='', stage='', difficulty='', question_type='', skill_id='', sources=None, draft=None, review=None, detail=None, duration_ms=None, session_id='', request_id=''):
    """Persist bounded, structured evidence for later quality analysis.

    Stores the public question, accepted key, full verifier JSON and source
    references. It never stores system prompts or full course chunks.
    """
    if not user_id or not db.get_user_by_id(user_id):
        return
    import observability
    current = observability.CURRENT.get() or {}
    request_id = request_id or current.get('root_id') or current.get('id') or ''
    session_id = session_id or current.get('session_id') or ''
    operation_id = current.get('id') or ''
    question = str(getattr(draft, 'question', '') or '')[:12000]
    answer = str(getattr(draft, 'canonical_answer', '') or '')[:4000]
    solution = str(getattr(draft, 'solution', '') or '')[:20000]
    assessment_context = str(getattr(draft, 'assessment_context', '') or '')
    if difficulty == '':
        import re
        match = re.search('Requested difficulty: (\\w+)', assessment_context)
        difficulty = match.group(1) if match else ''
    if question_type == '':
        question_type = str(getattr(draft, 'question_type', '') or '')
    if skill_id == '':
        skill_id = str(current.get('skill_id') or '')[:120]
    course_ids = sorted({str(s.get('course_id', '')) for s in sources or [] if s.get('course_id')})
    source_detail = [{k: s.get(k) for k in ('ref', 'source_file', 'page', 'course_id', 'kind')} for s in (sources or [])[:20]]
    try:
        review_json = review.model_dump_json() if hasattr(review, 'model_dump_json') else json.dumps(review or {}, default=str)
    except Exception:
        review_json = '{}'
    payload = dict(detail or {})
    payload.setdefault('policy_version', __import__('assessment_level').POLICY_VERSION)
    payload.setdefault('source_refs', source_detail)
    if draft is not None:
        payload.setdefault('verification', getattr(draft, 'verification', {}) or {})
    with db.connect() as c:
        c.execute('INSERT INTO generation_events(\n            id,user_id,operation_id,request_id,session_id,stage,outcome,reason,feedback,\n            difficulty,question_type,skill_id,course_ids,source_count,question,canonical_answer,\n            solution,review_json,detail_json,duration_ms,created\n        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (uuid.uuid4().hex, user_id, operation_id, str(request_id)[:80], str(session_id)[:80], str(stage)[:80], str(outcome)[:40], str(reason)[:3000], str(feedback)[:12000], str(difficulty)[:24], str(question_type)[:32], str(skill_id)[:120], json.dumps(course_ids), len(sources or []), question, answer, solution, review_json[:30000], json.dumps(payload, default=str)[:20000], None if duration_ms is None else float(duration_ms), time.time()))

def generation_summary(hours=24):
    since = time.time() - max(1, min(24 * 30, int(hours))) * 3600
    with db.connect() as c:
        rows = [dict(r) for r in c.execute('SELECT outcome, stage, COUNT(*) events FROM generation_events WHERE created>=? GROUP BY outcome,stage ORDER BY events DESC', (since,))]
        reasons = [dict(r) for r in c.execute("SELECT reason, COUNT(*) events FROM generation_events WHERE created>=? AND outcome IN ('rejected','error') AND reason<>'' GROUP BY reason ORDER BY events DESC LIMIT 12", (since,))]
        total = c.execute('SELECT COUNT(*) FROM generation_events WHERE created>=?', (since,)).fetchone()[0]
    return {'hours': hours, 'events': total, 'outcomes': rows, 'rejection_reasons': reasons}

def candidate(user_id, sources, skill_id, event):
    if not user_id or not db.get_user_by_id(user_id):
        return
    if event not in {'verified', 'duplicate', 'scope', 'rejected'}:
        event = 'rejected'
    import observability
    current = observability.CURRENT.get() or {}
    request_id = current.get('root_id') or current.get('id') or uuid.uuid4().hex
    with db.connect() as c:
        for course in sorted({str(s.get('course_id', '')) for s in sources if s.get('course_id')}):
            c.execute('INSERT INTO quality_events(id,user_id,course_id,skill_id,event,created,request_id) VALUES(?,?,?,?,?,?,?)', (uuid.uuid4().hex, user_id, course, skill_id or '', event, time.time(), request_id))

def paused_skills(user_id, course_ids):
    with db.connect() as c:
        rows = c.execute("SELECT course_id,skill_id,COUNT(DISTINCT CASE WHEN event IN ('rejected','scope') THEN CASE WHEN request_id='' THEN id ELSE request_id END END) failures,SUM(event='verified') successes,MAX(created) recent FROM quality_events WHERE user_id=? AND created>? GROUP BY course_id,skill_id HAVING failures>=3 AND successes=0", (user_id, time.time() - 1200)).fetchall()
    return {r['skill_id'] for r in rows if r['skill_id'] and (not course_ids or r['course_id'] in course_ids)}
