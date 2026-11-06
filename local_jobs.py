"""Persistent, bounded local-only jobs. No provider calls or executable plugins."""
import asyncio,json,threading,uuid
from fastapi import HTTPException
import db,learning_store as store,curriculum

LOCK=threading.Lock()
STOP=threading.Event()

def initialize():
    STOP.clear()
    with db.connect() as c:
        c.execute('CREATE VIRTUAL TABLE IF NOT EXISTS library_search USING fts5(owner UNINDEXED,course UNINDEXED,generation UNINDEXED,document UNINDEXED,page UNINDEXED,body,tokenize="unicode61")')
        c.execute("UPDATE learning_objects SET payload=json_set(payload,'$.status','interrupted','$.message','The app stopped. Retry when ready.') WHERE kind='local_job' AND json_extract(payload,'$.status')='running'")
        c.execute("DELETE FROM library_search WHERE document NOT IN (SELECT id FROM documents) OR generation NOT IN (SELECT json_extract(value,'$.generation') FROM app_settings WHERE key LIKE 'search_index:%' AND json_valid(value))")

def submit(owner,kind,course_id=''):
    if kind not in {'search_index','backup'}:raise HTTPException(422,'Unknown local job.')
    with LOCK:
        jobs=store.listing('local_job',owner,20)
        for job in jobs:
            if job.get('kind')==kind and job.get('course_id','')==course_id and job['status'] in {'queued','running'}:return job
        if sum(j['status'] in {'queued','running'} for j in jobs)>=5:raise HTTPException(429,'Five local jobs are already pending. Wait for one to finish.')
        value={'id':uuid.uuid4().hex,'kind':kind,'course_id':course_id,'status':'queued','progress':0,'message':'Waiting for an idle local worker.'}
        store.put('local_job',value['id'],owner,value)
        return value

def update(owner,job,**fields):
    job={**(store.get('local_job',job['id'],owner) or job),**fields};store.put('local_job',job['id'],owner,job);return job

def index_course(owner,job):
    import retrieval
    course=job['course_id'];version=curriculum.scope_version(owner,[course])
    docs={d['filename']:d for d in db.list_documents(owner,[course])}
    if not docs:raise ValueError('Upload and index course documents first.')
    generation=job['id'];count=0;batch=[]
    try:
        for _,text,metadata in retrieval._all_records(retrieval._get_collection(owner),{'course_id':course}):
            if STOP.is_set():raise InterruptedError()
            document=docs.get(metadata.get('source_file',''))
            if not document or not text:continue
            if count>=100000 or len(text)>40000:raise ValueError('This course exceeds the local search-index capacity. Split it into smaller courses.')
            batch.append((owner,course,generation,document['id'],int(metadata.get('page',1)),text));count+=1
            if len(batch)>=128:
                with db.connect() as c:c.executemany('INSERT INTO library_search VALUES(?,?,?,?,?,?)',batch)
                batch=[];update(owner,job,progress=min(95,count//100),message=f'Indexed {count} source chunks locally.')
        if batch:
            with db.connect() as c:c.executemany('INSERT INTO library_search VALUES(?,?,?,?,?,?)',batch)
        if not count:raise ValueError('No extracted text is available. Finish document indexing first.')
        if version!=curriculum.scope_version(owner,[course]):raise ValueError('Course documents changed during indexing. Retry the search index.')
        with db.connect() as c:
            if (store.get('local_job',job['id'],owner) or {}).get('status')=='cancelled':raise InterruptedError()
            c.execute("INSERT INTO app_settings(key,value,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",('search_index:'+owner+':'+course,json.dumps({'generation':generation,'version':version,'chunks':count}),db.utc_now()))
            c.execute('DELETE FROM library_search WHERE owner=? AND course=? AND generation<>?',(owner,course,generation))
        return f'{count} chunks indexed. Search makes no AI calls.'
    except BaseException:
        with db.connect() as c:c.execute('DELETE FROM library_search WHERE owner=? AND generation=?',(owner,generation))
        raise

async def execute(owner,job,services):
    update(owner,job,status='running',message='Preparing local work.')
    try:
        if job['kind']=='search_index':
            async with services['WORKSPACE_LOCK']:message=await asyncio.to_thread(index_course,owner,job)
        else:
            import backup
            async with services['WORKSPACE_LOCK']:
                with db.connect() as c:busy=c.execute("SELECT COUNT(*) FROM index_jobs WHERE status IN ('queued','running')").fetchone()[0]
                if not busy:await asyncio.to_thread(backup.create_backup,backup.backup_directory())
            if busy:
                update(owner,job,status='queued',message='Waiting for document indexing to finish.')
                await asyncio.sleep(5)
                return
            message='Backup created in your configured folder.'
        if (store.get('local_job',job['id'],owner) or {}).get('status')!='cancelled':update(owner,job,status='done',progress=100,message=message)
    except asyncio.CancelledError:
        # to_thread work must finish before the app closes its resources.
        raise
    except InterruptedError:update(owner,job,status='interrupted',message='The app stopped. Retry when ready.')
    except Exception as exc:
        if job.get('course_id') and not db.get_course(owner,job['course_id']):
            store.remove('local_job',job['id'],owner)
            return
        import logging
        logging.getLogger(__name__).exception('Local job failed: %s',job['kind'])
        message=str(exc) if isinstance(exc,ValueError) else 'Local processing failed. Check available storage, then retry.'
        update(owner,job,status='failed',message=message[:300])

async def worker(services):
    while True:
        with db.connect() as c:rows=c.execute("SELECT user_id,payload FROM learning_objects WHERE kind='local_job' AND json_extract(payload,'$.status')='queued' ORDER BY updated LIMIT 1").fetchall()
        if rows:
            active=asyncio.create_task(execute(rows[0]['user_id'],json.loads(rows[0]['payload']),services))
            try:await asyncio.shield(active)
            except asyncio.CancelledError:
                await active
                raise
        else:await asyncio.sleep(1)

def search(owner,course,query):
    import re
    info=json.loads(db.get_app_setting('search_index:'+owner+':'+course,'{}'))
    if info.get('version')!=curriculum.scope_version(owner,[course]):raise HTTPException(409,'Build or refresh this course’s text-search index first.')
    words=re.findall(r'[^\W_]+',query,flags=re.UNICODE)[:8]
    if not words:raise HTTPException(422,'Enter words to search for.')
    expression=' AND '.join('"'+w+'"*' for w in words)
    with db.connect() as c:
        rows=c.execute("SELECT document,page,snippet(library_search,5,'','', ' … ',30) AS excerpt FROM library_search WHERE library_search MATCH ? AND owner=? AND course=? AND generation=? ORDER BY rank LIMIT 25",(expression,owner,course,info['generation'])).fetchall()
    result=[]
    for row in rows:
        document=db.get_document(owner,row['document'])
        if document:result.append({**dict(row),'filename':document['filename']})
    return result
