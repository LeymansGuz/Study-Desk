"""Local study organisation; source text and imported notes never become verified bank items."""
from __future__ import annotations
import asyncio,csv,hashlib,json,time,uuid
from datetime import date,timedelta
from typing import Literal
from fastapi import Depends,HTTPException,UploadFile,File
from fastapi.responses import Response
from pydantic import BaseModel,Field,ConfigDict
import db,curriculum,learning_store as store,local_jobs

class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid')

class Schedule(Strict):
    course_id:str=Field(min_length=1,max_length=64)
    exam_date:date
    minutes:int=Field(default=30,ge=5,le=180)
    topics:list[str]=Field(default_factory=list,max_length=80)

class Completion(Strict):
    topic_id:str=Field(max_length=64)
    done:bool

class Annotation(Strict):
    document_id:str=Field(max_length=64)
    page:int=Field(ge=1,le=100000)
    text:str=Field(default='',max_length=4000)
    label:str=Field(default='',max_length=120)

class JobRequest(Strict):
    kind:Literal['search_index','backup']
    course_id:str=Field(default='',max_length=64)

class PersonalSheet(Strict):
    topic:str=Field(min_length=1,max_length=200)
    markdown:str=Field(min_length=1,max_length=40000)
    notes:str=Field(default='',max_length=8000)

class PersonalBundle(Strict):
    format:Literal['study-desk-personal-v1']
    course_id:str=Field(min_length=1,max_length=64)
    sheets:list[PersonalSheet]=Field(default_factory=list,max_length=20)

def schedule_view(value,today=None):
    today=today or date.today();end=date.fromisoformat(value['exam_date'])
    remaining=[r for r in value['topics'] if r['id'] not in value['done']]
    days=max(1,(end-today).days+1);capacity=days*value['minutes']
    rows=[];used=0
    # Recalculate from today, automatically rolling missed work forward.
    for item in remaining:
        offset=used//value['minutes'];when=today+timedelta(days=offset)
        rows.append({**item,'date':when.isoformat(),'over_capacity':when>end});used+=15
    return {**value,'upcoming':rows,'total_minutes':len(remaining)*15,'available_minutes':capacity,'over_capacity':len(remaining)*15>capacity,'exam_passed':end<today,'note':'15-minute estimates per topic. Reviewed is self-reported, not a mastery grade. Missed topics move forward automatically.'}

def identifier(*items):return hashlib.sha256('|'.join(items).encode()).hexdigest()[:32]

def purge_course(owner,course):
    """Remove derived library text and metadata with its original course."""
    with db.connect() as c:
        c.execute('DELETE FROM library_search WHERE owner=? AND course=?',(owner,course))
        c.execute("DELETE FROM app_settings WHERE key=?",('search_index:'+owner+':'+course,))
        c.execute("DELETE FROM learning_objects WHERE user_id=? AND kind IN ('course_guide','syllabus_plan','annotation','local_job','revision_sheet') AND (json_extract(payload,'$.course_id')=? OR EXISTS (SELECT 1 FROM json_each(json_extract(payload,'$.course_ids')) WHERE value=?))",(owner,course,course))
        c.execute('DELETE FROM course_scope_versions WHERE user_id=? AND EXISTS (SELECT 1 FROM json_each(scope) WHERE value=?)',(owner,course))

def save_checked_section(owner,payload):
    """Keep bounded checked guide sections alongside atomic publication."""
    from generation_control import defer
    if defer(lambda:save_checked_section(owner,payload)):return
    cid=payload['course_ids'][0]
    import source_lineage
    versions=source_lineage.fingerprints(owner,cid)
    with db.connect() as c:
        if db.COMMIT_CONNECTION.get() is None:c.execute('BEGIN IMMEDIATE')
        row=c.execute("SELECT payload FROM learning_objects WHERE kind='course_guide' AND id=? AND user_id=?",(cid,owner)).fetchone()
        value=json.loads(row[0]) if row else {}
        entries=value.get('sections',[]) if value.get('version')==payload['version'] else [r for r in value.get('sections',[]) if source_lineage.current(r,versions)]
        entry={k:payload[k] for k in ['topic','markdown','sources']}
        entry['source_versions']=source_lineage.pin(entry,versions)
        entries=[r for r in entries if r['topic'].casefold()!=entry['topic'].casefold()]+[entry]
        guide={'course_id':cid,'version':payload['version'],'sections':entries[-20:]}
        c.execute('INSERT INTO learning_objects VALUES(?,?,?,?,?) ON CONFLICT(kind,id) DO UPDATE SET payload=excluded.payload,updated=excluded.updated',('course_guide',cid,owner,json.dumps(guide,ensure_ascii=False),time.time()))

def install(app,services):
    require=services['require_user']
    def course(owner,cid):
        value=db.get_course(owner,cid)
        if not value:raise HTTPException(404,'Choose an available course.')
        return value
    def sections(owner,cid):
        return [r for r in curriculum.course_map(owner,[cid])['sections'] if not r.get('excluded')][:80]

    @app.get('/library/catalog/{course_id}')
    async def catalog(course_id:str,user=Depends(require)):
        course(user['id'],course_id)
        units=await asyncio.to_thread(sections,user['id'],course_id)
        return {'items':[{k:r.get(k) for k in ['id','title','source_file','pages']} for r in units],'limit':80}

    @app.post('/library/schedule')
    async def schedule(body:Schedule,user=Depends(require)):
        course(user['id'],body.course_id)
        if not 0<=(body.exam_date-date.today()).days<=730:raise HTTPException(422,'Choose an exam date within the next two years.')
        topics=list(dict.fromkeys(t.strip() for t in body.topics if t.strip()))
        if any(len(t)>200 for t in topics):raise HTTPException(422,'Keep each topic under 200 characters.')
        if not topics:topics=[r['title'] for r in await asyncio.to_thread(sections,user['id'],body.course_id)]
        if not topics:raise HTTPException(409,'Index course documents or enter one topic per line.')
        value={'id':body.course_id,'course_id':body.course_id,'exam_date':body.exam_date.isoformat(),'minutes':body.minutes,'version':curriculum.scope_version(user['id'],[body.course_id]),'topics':[{'id':identifier(body.course_id,t),'title':t} for t in topics],'done':[]}
        previous=store.get('syllabus_plan',body.course_id,user['id'])
        if previous:value['done']=[x for x in previous['done'] if x in {t['id'] for t in value['topics']}]
        store.put('syllabus_plan',body.course_id,user['id'],value);return schedule_view(value)

    @app.get('/library/schedule/{course_id}')
    async def get_schedule(course_id:str,user=Depends(require)):
        course(user['id'],course_id);value=store.get('syllabus_plan',course_id,user['id'])
        return {'plan':schedule_view(value) if value else None,'historical':bool(value and value['version']!=curriculum.scope_version(user['id'],[course_id]))}

    @app.patch('/library/schedule/{course_id}')
    async def complete(course_id:str,body:Completion,user=Depends(require)):
        course(user['id'],course_id)
        with db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute("SELECT payload FROM learning_objects WHERE kind='syllabus_plan' AND id=? AND user_id=?",(course_id,user['id'])).fetchone()
            value=json.loads(row[0]) if row else None
            if not value or body.topic_id not in {t['id'] for t in value['topics']}:raise HTTPException(404,'Unknown planned topic.')
            done=set(value['done']);done.add(body.topic_id) if body.done else done.discard(body.topic_id);value['done']=sorted(done)
            c.execute("UPDATE learning_objects SET payload=?,updated=? WHERE kind='syllabus_plan' AND id=? AND user_id=?",(json.dumps(value),time.time(),course_id,user['id']))
        return schedule_view(value)

    @app.get('/library/recommend/{course_id}')
    async def recommend(course_id:str,user=Depends(require)):
        course(user['id'],course_id);units=await asyncio.to_thread(sections,user['id'],course_id)
        scores=store.mastery(user['id']);key=curriculum.scope_key([course_id],curriculum.scope_version(user['id'],[course_id]));exposures=db.skill_exposure_counts(user['id'],key)
        units.sort(key=lambda x:(-store.priority(x['id'],scores),exposures.get(x['id'],0),x['id']))
        result=[]
        for unit in units[:5]:
            score=scores.get(unit['id']);level='easy' if score and score['score']<.45 else 'hard' if score and score['score']>.85 and score.get('successes',0)>=3 and score.get('independent_questions',0)>=3 and score.get('delayed_success') else 'medium'
            result.append({'topic':unit['title'],'difficulty':level,'reason':'Revisit an assessed gap' if score and score['score']<.65 else 'Course-covered topic with limited practice' if not score else 'Extend a previously practised concept','skill_id':unit['id']})
        return {'items':result,'note':'Suggestions use local outcomes and exposure. They do not certify mastery or infer prerequisites.'}

    @app.get('/library/guide/{course_id}')
    async def guide(course_id:str,download:bool=False,user=Depends(require)):
        current=course(user['id'],course_id);version=curriculum.scope_version(user['id'],[course_id])
        explanations=[x for x in store.listing('explain',user['id'],10) if x.get('course_ids')==[course_id] and x.get('version')==version]
        sheets=[x for x in store.listing('revision_sheet',user['id'],20) if x.get('course_ids')==[course_id] and x.get('version')==version and not x.get('imported')]
        unique={x['topic'].casefold():{'topic':x['topic'],'markdown':x.get('checked_markdown',x['markdown']),'sources':x.get('sources',[])} for x in sheets+explanations}
        saved_guide=store.get('course_guide',course_id,user['id']) or {}
        import source_lineage
        versions=source_lineage.fingerprints(user['id'],course_id)
        for entry in saved_guide.get('sections',[]):
            if saved_guide.get('version')==version or source_lineage.current(entry,versions):unique.setdefault(entry['topic'].casefold(),entry)
        units=await asyncio.to_thread(sections,user['id'],course_id)
        covered={(s.get('source_file',s.get('file')),s.get('page')) for x in unique.values() for s in x['sources']}
        gaps=[{'topic':x['title'],'source_file':x['source_file'],'pages':x['pages']} for x in units if not any((x['source_file'],p) in covered for p in x['pages'])]
        if download:
            text='# '+current['name']+' — revision guide\n\nCompiled from saved checked explanations. Source sections without an explanation are listed as gaps; this is not complete syllabus coverage.\n\n'
            for value in unique.values():
                refs='\n'.join('- ['+s['ref']+'] '+s.get('source_file',s.get('file',''))+', page '+str(s.get('page',1)) for s in value['sources'])
                text+='## '+value['topic']+'\n\n'+value['markdown']+'\n\n### Section sources\n'+refs+'\n\n'
            text+='## Sections still to explain\n\n'+'\n'.join('- '+r['topic'] for r in gaps)
            return Response(text,media_type='text/markdown',headers={'Content-Disposition':'attachment; filename="course-revision-guide.md"'})
        return {'sections':list(unique.values()),'gaps':gaps,'source_sections':len(units),'note':'Uses saved checked text; personal edits and imported notes are excluded. Explain any missing section individually with the normal verifier.'}

    @app.post('/library/jobs')
    async def start_job(body:JobRequest,user=Depends(require)):
        if body.kind=='search_index':course(user['id'],body.course_id)
        return local_jobs.submit(user['id'],body.kind,body.course_id)

    @app.get('/library/jobs')
    async def jobs(user=Depends(require)):return {'items':store.listing('local_job',user['id'],20)}

    @app.post('/library/jobs/{job_id}/{action}')
    async def change_job(job_id:str,action:Literal['retry','cancel'],user=Depends(require)):
        with local_jobs.LOCK:
            value=store.get('local_job',job_id,user['id'])
            if not value:raise HTTPException(404,'Unknown local job.')
            if action=='cancel' and value['status']!='queued':raise HTTPException(409,'Only queued work can be cancelled. Running local work finishes safely before shutdown.')
            if action=='retry' and value['status'] not in {'failed','interrupted','cancelled'}:raise HTTPException(409,'This job does not need a retry.')
            if value['course_id']:course(user['id'],value['course_id'])
            return local_jobs.update(user['id'],value,status='queued' if action=='retry' else 'cancelled',message='Waiting for local worker.' if action=='retry' else 'Cancelled.',progress=0)

    @app.get('/library/documents/search')
    async def search(course_id:str,q:str='',user=Depends(require)):
        course(user['id'],course_id)
        if not 2<=len(q.strip())<=120:raise HTTPException(422,'Enter 2–120 characters.')
        return {'items':await asyncio.to_thread(local_jobs.search,user['id'],course_id,q)}

    @app.get('/library/annotations')
    async def annotations(course_id:str,user=Depends(require)):
        course(user['id'],course_id)
        return {'items':[x for x in store.listing('annotation',user['id'],200) if x['course_id']==course_id and db.get_document(user['id'],x['document_id'])]}

    @app.get('/library/review-context/{record_id}')
    async def review_context(record_id:str,user=Depends(require)):
        record=db.get_study_record(user['id'],record_id)
        if not record:raise HTTPException(404,'This study result is unavailable.')
        saved=store.get('tutor',record['ref_id'],user['id']) or {}
        if not saved:
            for cid in {s.get('course_id') for s in record.get('source_summary',[]) if s.get('course_id')}:
                if not db.get_course(user['id'],cid):continue
                saved=next((q for q in store.bank_items(user['id'],cid) if q['current_question']==record['question']),{})
                if saved:break
        ids=saved.get('course_ids') or []
        if not ids or not db.get_course(user['id'],ids[0]) or not saved.get('topic'):raise HTTPException(409,'The original topic context is unavailable. Choose the concept in Explain a concept; your study result is kept.')
        return {'topic':saved['topic'][:200],'course_id':ids[0]}

    @app.post('/library/annotations')
    async def annotate(body:Annotation,user=Depends(require)):
        document=db.get_document(user['id'],body.document_id)
        if not document:raise HTTPException(404,'Unknown document.')
        if body.page>max(1,document['page_count']):raise HTTPException(422,'Choose a page within this document.')
        value={**body.model_dump(),'id':identifier(body.document_id,str(body.page)),'course_id':document['course_id'],'filename':document['filename']}
        store.put('annotation',value['id'],user['id'],value);return value

    @app.delete('/library/annotations/{annotation_id}')
    async def delete_annotation(annotation_id:str,user=Depends(require)):
        store.remove('annotation',annotation_id,user['id']);return {'ok':True}

    @app.post('/library/cards/import')
    async def import_cards(file:UploadFile=File(...),user=Depends(require)):
        data=await file.read(2_000_001)
        if len(data)>2_000_000:raise HTTPException(413,'Use a UTF-8 TSV file under 2 MB.')
        try:rows=list(csv.reader((x for x in data.decode('utf-8-sig').splitlines() if not x.startswith('#')),delimiter='\t'))
        except (UnicodeError,csv.Error):raise HTTPException(422,'Use UTF-8 tab-separated front and back text.')
        if not rows or len(rows)>200 or any(len(r)!=2 or not all(v.strip() for v in r) or any(len(v)>5000 for v in r) for r in rows):raise HTTPException(422,'Provide 1–200 rows with two nonempty fields, up to 5,000 characters each.')
        rows=list(dict.fromkeys(tuple(r) for r in rows))
        incoming={'import:'+identifier(front,back) for front,back in rows}
        with db.connect() as c:
            total=c.execute('SELECT COUNT(*) FROM flashcards WHERE user_id=?',(user['id'],)).fetchone()[0]
            existing={r[0] for r in c.execute('SELECT record_id FROM flashcards WHERE user_id=?',(user['id'],))}
            if total+len(incoming-existing)>200:raise HTTPException(409,'Import exceeds the 200-card capacity. Export cards, then use Manage review cards to remove older cards.')
        # Plain text only. Anki directives/HTML are not executed or promoted to verified material.
        for front,back in rows:
            key='import:'+identifier(front,back)
            db.save_study_record(user['id'],{'id':key,'ref_id':key,'question':front,'answer_key':back,'solution':'Personal imported card; not AI-verified.','is_correct':False,'attempts':0,'source_summary':[]})
        return {'imported':len(rows),'note':'Imported as personal FSRS review cards, not verified bank questions.'}

    @app.get('/library/cards')
    async def cards(user=Depends(require)):
        with db.connect() as c:rows=c.execute('SELECT id,front,status FROM flashcards WHERE user_id=? ORDER BY created_at DESC LIMIT 200',(user['id'],)).fetchall()
        return {'items':[dict(r) for r in rows]}

    @app.delete('/library/cards/{card_id}')
    async def delete_card(card_id:str,user=Depends(require)):
        with db.connect() as c:
            row=c.execute('SELECT record_id FROM flashcards WHERE user_id=? AND id=?',(user['id'],card_id)).fetchone()
            if not row:raise HTTPException(404,'Unknown card.')
            c.execute('DELETE FROM flashcards WHERE user_id=? AND id=?',(user['id'],card_id))
            if row['record_id'].startswith('import:'):c.execute('DELETE FROM study_records WHERE user_id=? AND id=?',(user['id'],row['record_id']))
        return {'ok':True}

    @app.get('/library/personal/export')
    async def export_personal(course_id:str,user=Depends(require)):
        course(user['id'],course_id)
        items=[{k:x[k] for k in ['topic','markdown','notes']} for x in store.listing('revision_sheet',user['id'],20) if x.get('course_ids')==[course_id]]
        return Response(json.dumps({'format':'study-desk-personal-v1','sheets':items},ensure_ascii=False),media_type='application/json',headers={'Content-Disposition':'attachment; filename="personal-study-sheets.json"'})

    @app.post('/library/personal/import')
    async def import_personal(body:PersonalBundle,user=Depends(require)):
        course(user['id'],body.course_id)
        from math_format import check
        for item in body.sheets:await check(item.markdown)
        for item in body.sheets:
            identifier_=uuid.uuid4().hex
            store.put('revision_sheet',identifier_,user['id'],{'id':identifier_,'topic':item.topic,'course_ids':[body.course_id],'version':curriculum.scope_version(user['id'],[body.course_id]),'markdown':item.markdown,'checked_markdown':'','notes':item.notes,'sources':[],'revision':1,'edited':True,'imported':True,'explanation_id':''})
        return {'imported':len(body.sheets),'note':'Imported as personal unverified sheets. No external verification claims are trusted.'}
