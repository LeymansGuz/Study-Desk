"""Persistent learning features. Private solutions never leave this store directly."""
from __future__ import annotations
import hashlib
import json
import time
import re
import db
from generation_control import stage_put

def init_schema():
    with db.connect() as conn:
        conn.executescript('\n        CREATE TABLE IF NOT EXISTS learning_objects (\n          kind TEXT NOT NULL, id TEXT NOT NULL, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,\n          payload TEXT NOT NULL, updated REAL NOT NULL, PRIMARY KEY(kind,id));\n        CREATE INDEX IF NOT EXISTS learning_owner ON learning_objects(user_id,kind,updated);\n        CREATE TABLE IF NOT EXISTS learning_receipts (\n          user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, key TEXT NOT NULL,\n          digest TEXT NOT NULL, status INTEGER NOT NULL, body TEXT NOT NULL, updated REAL NOT NULL,\n          PRIMARY KEY(user_id,key));\n        CREATE TABLE IF NOT EXISTS learning_exposures (\n          user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, item_id TEXT NOT NULL,\n          created REAL NOT NULL, PRIMARY KEY(user_id,item_id));\n        CREATE TABLE IF NOT EXISTS learning_outcomes (\n          user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, event TEXT NOT NULL,\n          skill TEXT NOT NULL, score REAL NOT NULL, attempt INTEGER NOT NULL, created REAL NOT NULL,\n          PRIMARY KEY(user_id,event,skill));\n        ')

@stage_put
def put(kind, identifier, user_id, payload):
    expired = []
    with db.connect() as conn:
        conn.execute('INSERT INTO learning_objects VALUES(?,?,?,?,?) ON CONFLICT(kind,id) DO UPDATE SET payload=excluded.payload,updated=excluded.updated', (kind, identifier, user_id, json.dumps(payload, ensure_ascii=False, allow_nan=False), time.time()))
        if kind in {'tutor', 'exam', 'explain', 'path'}:
            expired = _prune_sessions(conn, user_id)
    return expired

def _prune_sessions(conn, user_id):
    expired = [dict(row) for row in conn.execute("SELECT kind,id FROM learning_objects WHERE user_id=? AND kind IN ('tutor','exam','explain','path') AND COALESCE(json_extract(payload,'$.prepared'),0)=0 ORDER BY updated DESC,rowid DESC LIMIT -1 OFFSET 10", (user_id,))]
    conn.execute("DELETE FROM learning_objects WHERE user_id=? AND kind IN ('tutor','exam','explain','path') AND COALESCE(json_extract(payload,'$.prepared'),0)=0 AND rowid NOT IN (SELECT rowid FROM learning_objects WHERE user_id=? AND kind IN ('tutor','exam','explain','path') AND COALESCE(json_extract(payload,'$.prepared'),0)=0 ORDER BY updated DESC,rowid DESC LIMIT 10)", (user_id, user_id))
    for item in list(expired):
        if item['kind'] in {'path', 'exam'}:
            children = [dict(row) for row in conn.execute("SELECT kind,id FROM learning_objects WHERE user_id=? AND kind='tutor' AND (json_extract(payload,'$.path_id')=? OR json_extract(payload,'$.exam_id')=?)", (user_id, item['id'], item['id']))]
            conn.execute("DELETE FROM learning_objects WHERE user_id=? AND kind='tutor' AND (json_extract(payload,'$.path_id')=? OR json_extract(payload,'$.exam_id')=?)", (user_id, item['id'], item['id']))
            expired.extend(children)
    return expired

def prune_sessions():
    with db.connect() as conn:
        conn.execute("DELETE FROM learning_objects WHERE kind='tutor' AND COALESCE(json_extract(payload,'$.path_id'),'')<>'' AND NOT EXISTS (SELECT 1 FROM learning_objects p WHERE p.kind='path' AND p.id=json_extract(learning_objects.payload,'$.path_id') AND p.user_id=learning_objects.user_id)")
        conn.execute("DELETE FROM learning_objects WHERE kind='tutor' AND COALESCE(json_extract(payload,'$.exam_id'),'')<>'' AND NOT EXISTS (SELECT 1 FROM learning_objects p WHERE p.kind='exam' AND p.id=json_extract(learning_objects.payload,'$.exam_id') AND p.user_id=learning_objects.user_id)")
        owners = [row[0] for row in conn.execute("SELECT DISTINCT user_id FROM learning_objects WHERE kind IN ('tutor','exam','explain','path')")]
        for owner in owners:
            _prune_sessions(conn, owner)

def session_summaries(user_id):
    with db.connect() as conn:
        rows = conn.execute("SELECT id,kind,updated,json_extract(payload,'$.current_question') AS question, json_extract(payload,'$.topic') AS topic,json_extract(payload,'$.status') AS status FROM learning_objects WHERE user_id=? AND kind IN ('tutor','exam','explain','path') AND (kind<>'exam' OR json_extract(payload,'$.source')='verified_bank') AND COALESCE(json_extract(payload,'$.prepared'),0)=0 ORDER BY updated DESC,rowid DESC LIMIT 10", (user_id,)).fetchall()
    return [{'id': r['id'], 'kind': r['kind'], 'updated': r['updated'], 'question': (r['question'] or r['topic'] or 'Paper')[:180], 'status': r['status'] or 'paper'} for r in rows]

def get(kind, identifier, user_id=None):
    from generation_control import CURRENT
    import copy
    unit = CURRENT.get()
    if unit is not None and unit.phase == 'collecting' and ((kind, identifier) in unit.overlay):
        owner, payload = unit.overlay[kind, identifier]
        return copy.deepcopy(payload) if user_id is None or owner == user_id else None
    with db.connect() as conn:
        row = conn.execute('SELECT * FROM learning_objects WHERE kind=? AND id=?', (kind, identifier)).fetchone()
    return json.loads(row['payload']) if row and (user_id is None or row['user_id'] == user_id) else None

def remove(kind, identifier, user_id):
    from generation_control import CURRENT, defer
    unit = CURRENT.get()
    if defer(lambda: remove(kind, identifier, user_id)):
        unit.overlay[kind, identifier] = (user_id, None)
        return
    with db.connect() as conn:
        conn.execute('DELETE FROM learning_objects WHERE kind=? AND id=? AND user_id=?', (kind, identifier, user_id))

def listing(kind, user_id, limit=100):
    with db.connect() as conn:
        rows = conn.execute('SELECT id,payload,updated FROM learning_objects WHERE kind=? AND user_id=? ORDER BY updated DESC,rowid DESC LIMIT ?', (kind, user_id, min(10000, limit))).fetchall()
    return [{'id': row['id'], **json.loads(row['payload']), 'updated': row['updated']} for row in rows]

def fingerprint(text):
    return hashlib.sha256(' '.join(text.lower().split()).encode()).hexdigest()

def template_id(text):
    return fingerprint(re.sub('\\b\\d+(?:\\.\\d+)?\\b', '#', text))

def is_quarantined(text):
    value = get('quarantine', template_id(text))
    return bool(value and value.get('active'))

def outcome(user_id, event, skill, score, attempt):
    if not skill:
        return
    with db.connect() as conn:
        conn.execute('INSERT OR IGNORE INTO learning_outcomes VALUES(?,?,?,?,?,?)', (user_id, event, skill, max(0.0, min(1.0, score)), attempt, time.time()))

def mastery(user_id):
    with db.connect() as conn:
        rows = conn.execute('SELECT * FROM learning_outcomes WHERE user_id=? ORDER BY created', (user_id,)).fetchall()
    result = {}
    for row in rows:
        item = result.setdefault(row['skill'], {'skill_id': row['skill'], 'score': 0.5, 'attempts': 0, 'successes': 0})
        weight = 0.4 if row['attempt'] == 1 else 0.12
        item['score'] = (1 - weight) * item['score'] + weight * row['score']
        item['attempts'] += 1
        item['successes'] += int(row['score'] == 1 and row['attempt'] == 1)
        interval = min(30, 2 ** min(5, item['successes'])) if row['score'] == 1 else 0.25
        item['due_at'] = row['created'] + interval * 86400
    return result

def priority(skill, mastery_scores):
    value = mastery_scores.get(skill)
    if not value:
        return 1.3
    overdue = min(1.0, max(0.0, (time.time() - value['due_at']) / 86400))
    return 1 - value['score'] + overdue

def bank_add(user_id, state, version):
    if not state.get('current_question') or not state.get('sources') or state.get('mode') != 'practice':
        return None
    question_hash = fingerprint(state['current_question'])
    identifier = f'{user_id}:{question_hash}'
    prior = get('bank', identifier)
    if prior and prior.get('quarantined') or is_quarantined(state['current_question']):
        return None
    fields = ['current_question', 'question_type', 'options', 'canonical_answer', 'answer_parts', 'solution', 'formula_focus', 'sources', 'skill_id', 'scope_key', 'course_overview', 'difficulty', 'course_ids', 'doc_types', 'topic', 'scope', 'figure_mode', 'figure', 'assessment_version', 'verification']
    payload = {key: state.get(key) for key in fields}
    payload.update(version=version, verified_at=time.time(), quarantined=False, fingerprint=question_hash, template_id=template_id(state['current_question']))
    import curriculum
    payload['evidence_versions'] = {cid: curriculum.scope_version(user_id, [cid]) for cid in {s.get('course_id') for s in state['sources'] if s.get('course_id')}}
    put('bank', identifier, user_id, payload)
    return identifier

def bank_items(user_id, course):
    """One eligibility rule shared by counts and bank-only exams."""
    import curriculum
    current = curriculum.scope_version(user_id, [course])
    unique = {}
    with db.connect() as c:
        paused = {r[0] for r in c.execute("SELECT id FROM learning_objects WHERE kind='quarantine' AND json_extract(payload,'$.active')=1")}
    for row in listing('bank', user_id, 10000):
        sources = row.get('sources') or []
        versions = row.get('evidence_versions') or {}
        valid = versions.get(course) == current if versions else row.get('course_ids') == [course] and row.get('version') == current
        if (valid and row.get('verified_at') and not row.get('quarantined')
                and (row.get('assessment_version') or 0) >= __import__('assessment_level').POLICY_VERSION
                and {s.get('course_id') for s in sources} == {course}
                and not any(s.get('quality_review_required') for s in sources)
                and template_id(row.get('current_question', '')) not in paused):
            unique.setdefault(row.get('fingerprint') or fingerprint(row['current_question']), row)
    return list(unique.values())


def bank_counts(user_id, course):
    from typing import get_args
    from tools import Difficulty, QuestionType
    difficulties, question_types = list(get_args(Difficulty)), list(get_args(QuestionType))
    counts = {(d, t): 0 for d in difficulties for t in question_types}
    for row in bank_items(user_id, course):
        key = row.get('difficulty'), row.get('question_type')
        if key in counts:
            counts[key] += 1
    return {'course_id': course, 'total': sum(counts.values()), 'difficulties': difficulties,
        'question_types': question_types, 'counts': [{'difficulty': d, 'question_type': t, 'count': n} for (d,t), n in counts.items()]}


def bank_take(user_id, version, courses, difficulty, types, doc_types, topic, whole=False, figure_mode='none'):
    """Reserve a validated, unexposed item atomically; reserve before returning it."""
    import curriculum
    with db.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        paused = {r['id'] for r in conn.execute("SELECT id FROM learning_objects WHERE kind='quarantine' AND json_extract(payload,'$.active')=1")}
        placeholders = ','.join(('?' for _ in types))
        if not placeholders:
            return None
        rows = conn.execute(f"SELECT id,payload FROM learning_objects WHERE kind=? AND user_id=? AND json_extract(payload,'$.version')=? AND json_extract(payload,'$.difficulty')=? AND json_extract(payload,'$.question_type') IN ({placeholders}) AND id NOT IN (SELECT item_id FROM learning_exposures WHERE user_id=?) ORDER BY updated", ('bank', user_id, version, difficulty, *types, user_id))
        for row in rows:
            item = json.loads(row['payload'])
            if (item.get('assessment_version') or 0) < __import__('assessment_level').POLICY_VERSION:
                continue
            if figure_mode != 'auto' and ((item.get('figure_mode') or 'none') != figure_mode or (figure_mode == 'math' and (not item.get('figure')))):
                continue
            if item.get('quarantined') or item.get('template_id') in paused or item['version'] != version or (sorted(item['course_ids']) != sorted(courses)):
                continue
            if item['difficulty'] != difficulty or item['question_type'] not in types:
                continue
            if doc_types and any((source['doc_type'] not in doc_types for source in item['sources'])):
                continue
            if not whole and curriculum.terms(topic) != curriculum.terms(item.get('requested_topic', item['topic'])):
                continue
            from generation_control import defer
            parameters = (user_id, row['id'], time.time())

            def publish_exposure(parameters=parameters):
                with db.connect() as connection:
                    connection.execute('INSERT INTO learning_exposures VALUES(?,?,?)', parameters)
            if not defer(publish_exposure):
                conn.execute('INSERT INTO learning_exposures VALUES(?,?,?)', parameters)
            return item
    return None

def mark_served(user_id, question):
    from generation_control import defer
    if defer(lambda: mark_served(user_id, question)):
        return
    with db.connect() as conn:
        conn.execute('INSERT OR IGNORE INTO learning_exposures VALUES(?,?,?)', (user_id, f'{user_id}:{fingerprint(question)}', time.time()))

def quarantine(question, user_id=None):
    identifier = fingerprint(question)
    with db.connect() as conn:
        rows = conn.execute('SELECT id,user_id,payload FROM learning_objects WHERE kind=? AND (json_extract(payload,?)=? OR json_extract(payload,?)=?)', ('bank', '$.fingerprint', identifier, '$.template_id', template_id(question))).fetchall()
    owner = user_id or (rows[0]['user_id'] if rows else None)
    if owner:
        put('quarantine', template_id(question), owner, {'active': True})
    for row in rows:
        payload = json.loads(row['payload'])
        payload['quarantined'] = True
        put('bank', row['id'], row['user_id'], payload)

def receipt(user_id, key, digest):
    with db.connect() as conn:
        row = conn.execute('SELECT * FROM learning_receipts WHERE user_id=? AND key=?', (user_id, key)).fetchone()
    if not row:
        return None
    if row['digest'] != digest:
        raise ValueError('This request identifier was already used for different content.')
    return dict(row)

def save_receipt(user_id, key, digest, status, body):
    from generation_control import defer
    if defer(lambda: save_receipt(user_id, key, digest, status, body)):
        return
    with db.connect() as conn:
        conn.execute('INSERT OR REPLACE INTO learning_receipts VALUES(?,?,?,?,?,?)', (user_id, key, digest, status, body, time.time()))
