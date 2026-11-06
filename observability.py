'Provider token accounting and bounded per-question operation traces; no prompts/answers stored.'
from __future__ import annotations
import auth
import asyncio
import json
import logging
import os
import time
import uuid
from contextvars import ContextVar
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import db
CURRENT = ContextVar('study_operation', default=None)
logger = logging.getLogger(__name__)
PEAK_DEFAULTS = {'input': ('DEEPSEEK_PEAK_INPUT_PRICE_PER_M_USD', '0.30'), 'output': ('DEEPSEEK_PEAK_OUTPUT_PRICE_PER_M_USD', '1.20'), 'cached_input': ('DEEPSEEK_PEAK_CACHE_INPUT_PRICE_PER_M_USD', '0.006')}
OFFPEAK_DEFAULTS = {'input': ('DEEPSEEK_OFFPEAK_INPUT_PRICE_PER_M_USD', '0.15'), 'output': ('DEEPSEEK_OFFPEAK_OUTPUT_PRICE_PER_M_USD', '0.60'), 'cached_input': ('DEEPSEEK_OFFPEAK_CACHE_INPUT_PRICE_PER_M_USD', '0.003')}
PEAK_WINDOWS = ((9 * 60, 12 * 60), (14 * 60, 18 * 60))
TAIPEI = ZoneInfo('Asia/Taipei')
PEAK_HOLIDAYS = {value.strip() for value in os.getenv('DEEPSEEK_PEAK_HOLIDAYS', '').split(',') if value.strip()}

def is_off_peak(at=None):
    """DeepSeek peak: Beijing weekdays 09:00-12:00 and 14:00-18:00.

    Weekends and dates listed in DEEPSEEK_PEAK_HOLIDAYS are off-peak.
    """
    local = (at or datetime.now(timezone.utc)).astimezone(TAIPEI)
    if local.weekday() >= 5 or local.date().isoformat() in PEAK_HOLIDAYS:
        return True
    minutes = local.hour * 60 + local.minute
    return not any((start <= minutes < end for start, end in PEAK_WINDOWS))

def _rate(period, key):
    env, default = (OFFPEAK_DEFAULTS if period == 'offpeak' else PEAK_DEFAULTS)[key]
    value = db.get_app_setting('billing_' + period + '_' + key, None)
    if value is None:
        value = db.get_app_setting('billing_' + key, None)
    return float(value if value is not None else os.getenv(env, default))

def rate_schedule(at=None):
    return {'peak': {key: _rate('peak', key) for key in PEAK_DEFAULTS}, 'offpeak': {key: _rate('offpeak', key) for key in OFFPEAK_DEFAULTS}, 'active': 'offpeak' if is_off_peak(at) else 'peak', 'timezone': 'Asia/Taipei', 'peak_windows': ['09:00-12:00', '14:00-18:00'], 'offpeak_rule': 'Weekends, configured holidays, and all other hours'}

def rates(at=None):
    active = 'offpeak' if is_off_peak(at) else 'peak'
    result = {key: _rate(active, key) for key in PEAK_DEFAULTS}
    result['period'] = active
    result['off_peak'] = active == 'offpeak'
    return result

def day():
    return (datetime.now(timezone.utc) + timedelta(hours=8)).date().isoformat()

def charge(input_tokens, output_tokens, cached=0, pricing=None):
    r = pricing or rates()
    cached = min(input_tokens, max(0, cached))
    return ((input_tokens - cached) * r['input'] + cached * r['cached_input'] + output_tokens * r['output']) / 1000000.0

def initialize():
    with db.connect() as c:
        c.executescript("\n        CREATE TABLE IF NOT EXISTS billing_totals(user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,input_tokens INTEGER NOT NULL DEFAULT 0,output_tokens INTEGER NOT NULL DEFAULT 0,cost_usd REAL NOT NULL DEFAULT 0);\n        CREATE TABLE IF NOT EXISTS billing_daily(user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,day TEXT NOT NULL,input_tokens INTEGER NOT NULL DEFAULT 0,output_tokens INTEGER NOT NULL DEFAULT 0,cost_usd REAL NOT NULL DEFAULT 0,PRIMARY KEY(user_id,day));\n        CREATE TABLE IF NOT EXISTS usage_totals(user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,kind TEXT NOT NULL,count INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(user_id,kind));\n        CREATE TABLE IF NOT EXISTS usage_daily(user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,day TEXT NOT NULL,kind TEXT NOT NULL,count INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(user_id,day,kind));\n        CREATE TABLE IF NOT EXISTS model_daily(user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,day TEXT NOT NULL,calls INTEGER NOT NULL DEFAULT 0,errors INTEGER NOT NULL DEFAULT 0,missing_usage INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(user_id,day));\n        CREATE TABLE IF NOT EXISTS operations(id TEXT PRIMARY KEY,root_id TEXT NOT NULL,parent_id TEXT,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,kind TEXT NOT NULL,session_id TEXT,question_number TEXT NOT NULL DEFAULT '',question TEXT NOT NULL DEFAULT '',difficulty TEXT NOT NULL DEFAULT '',question_type TEXT NOT NULL DEFAULT '',background INTEGER NOT NULL DEFAULT 0,status TEXT NOT NULL DEFAULT 'running',http_status INTEGER,started_at REAL NOT NULL,finished_at REAL,latency_ms REAL,input_tokens INTEGER NOT NULL DEFAULT 0,output_tokens INTEGER NOT NULL DEFAULT 0,cost_usd REAL NOT NULL DEFAULT 0,model_calls INTEGER NOT NULL DEFAULT 0,missing_usage INTEGER NOT NULL DEFAULT 0,cache_hit INTEGER NOT NULL DEFAULT 0,error_type TEXT NOT NULL DEFAULT '',error_detail TEXT NOT NULL DEFAULT '');\n        CREATE INDEX IF NOT EXISTS operations_started ON operations(started_at DESC);\n        CREATE INDEX IF NOT EXISTS operations_session ON operations(session_id,question_number);\n        CREATE TABLE IF NOT EXISTS model_calls(id TEXT PRIMARY KEY,operation_id TEXT REFERENCES operations(id) ON DELETE CASCADE,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,stage TEXT NOT NULL,model TEXT NOT NULL,created_at REAL NOT NULL,latency_ms REAL,input_tokens INTEGER NOT NULL,output_tokens INTEGER NOT NULL,cached_input_tokens INTEGER NOT NULL DEFAULT 0,cost_usd REAL,usage_known INTEGER NOT NULL,outcome TEXT NOT NULL DEFAULT 'success',input_rate REAL NOT NULL,output_rate REAL NOT NULL,cached_rate REAL NOT NULL,error_detail TEXT NOT NULL DEFAULT '');\n        CREATE INDEX IF NOT EXISTS model_calls_operation ON model_calls(operation_id);\n        ")
        if 'error_detail' not in {row['name'] for row in c.execute('PRAGMA table_info(operations)')}:
            c.execute("ALTER TABLE operations ADD COLUMN error_detail TEXT NOT NULL DEFAULT ''")
        if 'error_detail' not in {row['name'] for row in c.execute('PRAGMA table_info(model_calls)')}:
            c.execute("ALTER TABLE model_calls ADD COLUMN error_detail TEXT NOT NULL DEFAULT ''")
        if not c.execute("SELECT 1 FROM app_settings WHERE key IN ('billing_peak_input','billing_peak_output','billing_peak_cached_input')").fetchone():
            c.execute("DELETE FROM app_settings WHERE key IN ('billing_input','billing_output','billing_cached_input')")
        if not c.execute("SELECT 1 FROM app_settings WHERE key='billing_baseline_v1'").fetchone():
            r = rates()
            c.execute('INSERT OR REPLACE INTO billing_totals SELECT user_id,SUM(input_tokens),SUM(output_tokens),(SUM(input_tokens)*?+SUM(output_tokens)*?)/1000000.0 FROM token_usage GROUP BY user_id', (r['input'], r['output']))
            c.execute("INSERT OR REPLACE INTO billing_daily SELECT user_id,date(created_at,'+8 hours'),SUM(input_tokens),SUM(output_tokens),(SUM(input_tokens)*?+SUM(output_tokens)*?)/1000000.0 FROM token_usage GROUP BY user_id,date(created_at,'+8 hours')", (r['input'], r['output']))
            c.execute('INSERT OR REPLACE INTO usage_totals SELECT user_id,kind,COUNT(*) FROM usage_events GROUP BY user_id,kind')
            c.execute("INSERT OR REPLACE INTO usage_daily SELECT user_id,date(created_at,'+8 hours'),kind,COUNT(*) FROM usage_events GROUP BY user_id,date(created_at,'+8 hours'),kind")
            c.execute("INSERT INTO app_settings VALUES('billing_baseline_v1','1',?)", (db.utc_now(),))
        if not c.execute("SELECT 1 FROM app_settings WHERE key='model_daily_baseline_v1'").fetchone():
            c.execute("INSERT OR IGNORE INTO model_daily SELECT user_id,date(created_at,'+8 hours'),COUNT(*),0,0 FROM token_usage GROUP BY user_id,date(created_at,'+8 hours')")
            c.execute("INSERT INTO app_settings VALUES('model_daily_baseline_v1','1',?)", (db.utc_now(),))

def accumulate(c, user_id, inputs, outputs, cost):
    c.execute('INSERT INTO billing_totals VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET input_tokens=input_tokens+excluded.input_tokens,output_tokens=output_tokens+excluded.output_tokens,cost_usd=cost_usd+excluded.cost_usd', (user_id, inputs, outputs, cost))
    c.execute('INSERT INTO billing_daily VALUES(?,?,?,?,?) ON CONFLICT(user_id,day) DO UPDATE SET input_tokens=input_tokens+excluded.input_tokens,output_tokens=output_tokens+excluded.output_tokens,cost_usd=cost_usd+excluded.cost_usd', (user_id, day(), inputs, outputs, cost))

def event(c, user_id, kind):
    c.execute('INSERT INTO usage_totals VALUES(?,?,1) ON CONFLICT(user_id,kind) DO UPDATE SET count=count+1', (user_id, kind))
    c.execute('INSERT INTO usage_daily VALUES(?,?,?,1) ON CONFLICT(user_id,day,kind) DO UPDATE SET count=count+1', (user_id, day(), kind))

def provider_call(user_id, stage, model, inputs, outputs, cached, latency, known=True, outcome='success', error_detail=''):
    current = CURRENT.get()
    identifier = uuid.uuid4().hex
    r = rates()
    import providers
    connection=providers.ACTIVE.get()
    pricing_known=True
    if connection is not None:
        model=connection.provider+':'+connection.model
        if connection.pricing is not None:
            r=dict(zip(('input','output','cached_input'),connection.pricing))
        elif connection.provider=='deepseek' and connection.model=='deepseek-v4-pro':
            r=dict(zip(('input','output','cached_input'),(0.66,1.98,0.022) if is_off_peak() else (1.32,3.96,0.044)))
        elif connection.provider!='deepseek':
            pricing_known=False
            r={'input':0,'output':0,'cached_input':0}
    cost = charge(inputs, outputs, cached, r) if known and pricing_known else None
    accounted=known and pricing_known
    stage = str(stage)[:80]
    model = str(model)[:120]
    with db.connect() as c:
        c.execute('INSERT INTO model_calls VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (identifier, current['id'] if current else None, user_id, stage, model, time.time(), latency, inputs, outputs, cached, cost, int(known), outcome, r['input'], r['output'], r['cached_input'], str(error_detail)[:2000]))
        c.execute('INSERT INTO model_daily VALUES(?,?,1,?,?) ON CONFLICT(user_id,day) DO UPDATE SET calls=calls+1,errors=errors+excluded.errors,missing_usage=missing_usage+excluded.missing_usage', (user_id, day(), int(outcome != 'success'), int(not accounted)))
        if known and (inputs or outputs):
            c.execute('INSERT INTO token_usage(user_id,input_tokens,output_tokens,created_at) VALUES(?,?,?,?)', (user_id, inputs, outputs, db.utc_now()))
            accumulate(c, user_id, inputs, outputs, cost or 0)
        if current:
            c.execute('UPDATE operations SET model_calls=model_calls+1,input_tokens=input_tokens+?,output_tokens=output_tokens+?,cost_usd=cost_usd+?,missing_usage=missing_usage+? WHERE id=?', (inputs, outputs, cost or 0, int(not accounted), current['id']))
    return (identifier, cost)

def invalid_call(identifier, error_detail=''):
    if identifier:
        with db.connect() as c:
            row = c.execute('SELECT user_id,created_at,outcome FROM model_calls WHERE id=?', (identifier,)).fetchone()
            if row and row['outcome'] == 'success':
                call_day = (datetime.fromtimestamp(row['created_at'], timezone.utc) + timedelta(hours=8)).date().isoformat()
                c.execute('UPDATE model_daily SET errors=errors+1 WHERE user_id=? AND day=?', (row['user_id'], call_day))
            c.execute("UPDATE model_calls SET outcome='invalid_output',error_detail=? WHERE id=?", (str(error_detail)[:2000], identifier))

@asynccontextmanager
async def operation(kind, user_id, session_id=None, question_number='', **details):
    if not user_id or not db.get_user_by_id(user_id):
        yield {'id': None}
        return
    parent = CURRENT.get()
    identifier = uuid.uuid4().hex
    from pipeline_runtime import BACKGROUND
    current = {'id': identifier, 'root_id': parent['root_id'] if parent else identifier, 'user_id': user_id, 'session_id': session_id or ''}
    with db.connect() as c:
        c.execute('INSERT INTO operations(id,root_id,parent_id,user_id,kind,session_id,question_number,difficulty,question_type,background,started_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)', (identifier, current['root_id'], parent['id'] if parent else None, user_id, kind, session_id, question_number, details.get('difficulty', ''), details.get('question_type', ''), int(BACKGROUND.get()), time.time()))
    token = CURRENT.set(current)
    started = time.perf_counter()
    status = 'success'
    error = ''
    error_detail = ''
    try:
        yield current
    except BaseException as exc:
        status = 'cancelled' if isinstance(exc, asyncio.CancelledError) else 'failed'
        error = type(exc).__name__
        if not isinstance(exc, asyncio.CancelledError):
            error_detail = str(exc)[:2000]
        raise
    finally:
        CURRENT.reset(token)
        with db.connect() as c:
            c.execute("UPDATE operations SET finished_at=?,latency_ms=?,status=CASE WHEN status='running' THEN ? ELSE status END,error_type=?,error_detail=CASE WHEN ?<>'' THEN ? ELSE error_detail END WHERE id=?", (time.time(), (time.perf_counter() - started) * 1000, status, error, error_detail, error_detail, identifier))

def describe(identifier, result, session_id=None, question_number=''):
    if not identifier:
        return
    with db.connect() as c:
        c.execute("UPDATE operations SET session_id=COALESCE(?,session_id),question=?,difficulty=CASE WHEN ?<>'' THEN ? ELSE difficulty END,question_type=CASE WHEN ?<>'' THEN ? ELSE question_type END,cache_hit=? WHERE id=?", (session_id, '', result.get('difficulty', ''), result.get('difficulty', ''), result.get('question_type', ''), result.get('question_type', ''), int(bool(result.get('bank_id') or result.get('bank_reused'))), identifier))
        if session_id:
            c.execute('UPDATE operations SET session_id=? WHERE root_id=? AND session_id IS NULL', (session_id, identifier))

class OperationMiddleware:

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '')
        kind = {'/ask': 'practice_request', '/ask/question': 'assignment_generate', '/answer': 'practice_grade', '/exam/draft': 'exam_setup', '/api/extract': 'attachment_extract'}.get(path)
        if not kind and path.startswith('/exam/') and path.endswith(('/answer', '/hint', '/reveal')):
            kind = 'exam_' + path.rsplit('/', 1)[1]
        if scope['type'] != 'http' or scope.get('method') != 'POST' or (not kind):
            return await self.app(scope, receive, send)
        from starlette.requests import Request
        request = Request(scope, receive)
        user = auth.maybe_user(request)
        if not user:
            return await self.app(scope, receive, send)
        body = await request.body()
        payload = {}
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            pass
        if not isinstance(payload, dict):
            payload = {}
        delivered = False
        response = bytearray()
        http_status = 500

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': body, 'more_body': False}
            return await receive()

        async def capture(message):
            nonlocal http_status
            if message['type'] == 'http.response.start':
                http_status = message['status']
            if message['type'] == 'http.response.body' and len(response) < 2000000:
                response.extend(message.get('body', b''))
            await send(message)
        session = payload.get('thread_id') or (path.split('/')[2] if path.startswith('/exam/') and path != '/exam/draft' else None)
        session = str(session)[:64] if session else None
        types = payload.get('question_types')
        question_type = str(types[0])[:32] if isinstance(types, list) and types else ''
        async with operation(kind, user['id'], session, str(payload.get('question_number', ''))[:24], difficulty=str(payload.get('difficulty', ''))[:16], question_type=question_type) as op:
            await self.app(scope, replay, capture)
            error_detail = ''
            if http_status >= 400:
                try:
                    body = json.loads(response)
                    error_detail = str(body.get('detail') or body.get('error') or '')[:2000]
                except (ValueError, TypeError):
                    pass
            with db.connect() as c:
                c.execute('UPDATE operations SET http_status=?,status=?,error_detail=? WHERE id=?', (http_status, 'success' if http_status < 400 else 'failed', error_detail, op['id']))
            try:
                result = json.loads(response)
                session = result.get('thread_id') or result.get('exam_id') or session
                if session and (not result.get('question')):
                    import learning_store
                    saved = learning_store.get('tutor', session, user['id'])
                    if saved:
                        result = {**saved, **result}
                describe(op['id'], result, session)
            except (ValueError, TypeError):
                pass

def statistics(days=30, page=1):
    start = datetime.fromisoformat(day()).replace(tzinfo=timezone(timedelta(hours=8))) - timedelta(days=min(90, max(1, days)) - 1)
    cutoff = start.timestamp()
    offset = (max(1, page) - 1) * 20
    with db.connect() as c:
        totals = dict(c.execute('SELECT COALESCE(SUM(input_tokens),0) input_tokens,COALESCE(SUM(output_tokens),0) output_tokens,COALESCE(SUM(cost_usd),0) cost_usd FROM operational_billing_totals').fetchone())
        today = dict(c.execute('SELECT COALESCE(SUM(input_tokens),0) input_tokens,COALESCE(SUM(output_tokens),0) output_tokens,COALESCE(SUM(cost_usd),0) cost_usd FROM operational_billing_daily WHERE day=?', (day(),)).fetchone())
        calls = dict(c.execute('SELECT COALESCE(SUM(input_tokens),0) input_tokens,COALESCE(SUM(output_tokens),0) output_tokens,COALESCE(SUM(cost_usd),0) cost_usd FROM operational_billing_daily WHERE day>=?', (start.date().isoformat(),)).fetchone())
        calls.update(dict(c.execute('SELECT COALESCE(SUM(calls),0) calls,COALESCE(SUM(missing_usage),0) missing_usage,COALESCE(SUM(errors),0) failed_calls FROM operational_model_daily WHERE day>=?', (start.date().isoformat(),)).fetchone()))
        calls['cached_input_tokens'] = c.execute('SELECT COALESCE(SUM(cached_input_tokens),0) FROM model_calls WHERE created_at>=?', (cutoff,)).fetchone()[0]
        outcomes = [dict(r) for r in c.execute("SELECT kind,COUNT(*) requests,SUM(status='failed') failures,SUM(cache_hit) cache_hits,AVG(latency_ms) average_ms FROM operations WHERE started_at>=? AND parent_id IS NULL GROUP BY kind", (cutoff,))]
        latency = [r[0] for r in c.execute("SELECT latency_ms FROM operations WHERE started_at>=? AND parent_id IS NULL AND status='success' AND latency_ms IS NOT NULL ORDER BY latency_ms", (cutoff,))]
        base = " FROM operations o LEFT JOIN users u ON u.id=o.user_id WHERE o.started_at>=? AND (o.model_calls>0 OR o.kind IN ('practice_request','practice_grade','exam_answer','assignment_generate'))"
        grouping = ' GROUP BY o.user_id,COALESCE(o.session_id,o.id),o.question_number'
        count = c.execute('SELECT COUNT(*) FROM (SELECT 1' + base + grouping + ')', (cutoff,)).fetchone()[0]
        averages = dict(c.execute('SELECT COUNT(*) items,AVG(item_cost) cost_usd,SUM(missing) missing_usage FROM (SELECT SUM(o.cost_usd) item_cost,SUM(o.missing_usage) missing' + base + grouping + ')', (cutoff,)).fetchone())
        if averages['missing_usage']:
            averages['cost_usd'] = None
        page = min(page, max(1, (count + 19) // 20))
        offset = (page - 1) * 20
        rows = [dict(r) for r in c.execute("SELECT MIN(o.id) id,GROUP_CONCAT(DISTINCT o.kind) kind,o.session_id,o.question_number,'' question,MAX(o.difficulty) difficulty,MAX(o.question_type) question_type,MAX(o.background) background,COUNT(DISTINCT CASE WHEN o.status='failed' THEN o.root_id END) failures,MAX(o.started_at) started_at,SUM(o.latency_ms) latency_ms,SUM(o.input_tokens) input_tokens,SUM(o.output_tokens) output_tokens,SUM((SELECT COALESCE(SUM(mc.cached_input_tokens),0) FROM model_calls mc WHERE mc.operation_id=o.id)) cached_input_tokens,SUM(o.cost_usd) cost_usd,SUM(o.model_calls) model_calls,SUM(o.missing_usage) missing_usage,MAX(o.cache_hit) cache_hit,u.username" + base + grouping + ' ORDER BY MAX(o.started_at) DESC LIMIT 20 OFFSET ?', (cutoff, offset))]
        stages = [dict(r) for r in c.execute("SELECT stage,model,COUNT(*) calls,SUM(input_tokens) input_tokens,SUM(output_tokens) output_tokens,SUM(cost_usd) cost_usd,SUM(outcome<>'success') repairs_or_failures,AVG(latency_ms) average_ms FROM model_calls WHERE created_at>=? GROUP BY stage,model ORDER BY SUM(cost_usd) DESC LIMIT 20", (cutoff,))]
        daily = [dict(r) for r in c.execute('SELECT day,SUM(input_tokens) input_tokens,SUM(output_tokens) output_tokens,SUM(cost_usd) cost_usd FROM operational_billing_daily WHERE day>=? GROUP BY day ORDER BY day DESC LIMIT 90', (start.date().isoformat(),))]
        storage = {name: c.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0] for name in ['users', 'courses', 'documents', 'study_records', 'flashcards', 'operations', 'model_calls', 'generation_events', 'quality_events', 'learning_objects', 'index_jobs']}
        storage['document_bytes'] = c.execute('SELECT COALESCE(SUM(size),0) FROM documents').fetchone()[0]
        storage['saved_sessions'] = c.execute("SELECT COUNT(*) FROM learning_objects WHERE kind IN ('tutor','exam','explain','path') AND COALESCE(json_extract(payload,'$.prepared'),0)=0").fetchone()[0]
        storage['pending_index_jobs'] = c.execute("SELECT COUNT(*) FROM index_jobs WHERE status IN ('queued','running')").fetchone()[0]
        storage['failed_index_jobs'] = c.execute("SELECT COUNT(*) FROM index_jobs WHERE status='failed'").fetchone()[0]
    pct = lambda p: round(latency[min(len(latency) - 1, int((len(latency) - 1) * p))], 1) if latency else None
    return {'timezone': 'Asia/Taipei', 'days': days, 'rates': rates(), 'rate_schedule': rate_schedule(), 'totals': totals, 'today': today, 'period': calls, 'outcomes': outcomes, 'latency': {'p50_ms': pct(0.5), 'p95_ms': pct(0.95)}, 'averages': averages, 'operations': rows, 'page': page, 'page_size': 20, 'total_operations': count, 'stages': stages, 'daily': daily, 'storage': storage, 'notes': ['Costs are estimates using the rate snapshot for each model call; adjust rates to match your provider. Hosting and storage fees are not included.', 'All model attempts, validation repairs and background preparation are counted. Missing provider usage is flagged, not assumed free.', 'Summary tokens/costs use retained daily rollups. Stage details and latency use retained traces, so they may cover a shorter window at high volume.', 'Recent traces: up to 90 days and 50,000 operations / 100,000 model calls. Daily totals: 365 days; lifetime totals are preserved.']}
