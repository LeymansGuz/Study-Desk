"""Local extraction with one worker, bounded text cache and streamed progress."""
import asyncio, hashlib, json, time
from collections import OrderedDict
from fastapi import Depends, File, HTTPException, Request, UploadFile
from starlette.responses import StreamingResponse
from upload_limits import QUESTION_FILES, QUESTION_BYTES, QUESTION_FILE_BYTES, QUESTION_PAGES
from security import MAX_ASSIGNMENT_CHARS
from extraction import extract_assignment_file

class Extractor:
    def __init__(self):
        self.gate=asyncio.Semaphore(1);self.pending=set();self.inflight={};self.cache=OrderedDict();self.chars=0
    def busy(self):return bool(self.pending)
    async def extract(self,user,filename,data):
        from security import sanitize_filename,ALLOWED_ASSIGNMENT_EXTENSIONS
        filename=sanitize_filename(filename,ALLOWED_ASSIGNMENT_EXTENSIONS)
        key=(user,filename.rsplit('.',1)[-1].lower(),hashlib.sha256(data).hexdigest())
        cached=self.cache.get(key)
        if cached and time.monotonic()-cached[0]<1800:
            self.cache.move_to_end(key)
            return {**cached[1],'filename':filename,'cached':True}
        if key in self.inflight:
            return {**(await asyncio.shield(self.inflight[key])),'filename':filename,'cached':True}
        if len(self.pending)>=2:raise HTTPException(409,'Attachment reading is busy. Wait for the current extraction to finish.')
        async def run():
            async with self.gate:
                result=await asyncio.to_thread(extract_assignment_file,filename,data)
                if key in self.cache:self.chars-=len(self.cache.pop(key)[1]['text'])
                self.cache[key]=(time.monotonic(),result);self.chars+=len(result['text'])
                while len(self.cache)>32 or self.chars>2_000_000:self.chars-=len(self.cache.popitem(last=False)[1]['text'])
                return {**result,'cached':False}
        task=asyncio.create_task(run());self.pending.add(task);self.inflight[key]=task
        def finished(task):
            self.pending.discard(task)
            self.inflight.pop(key,None)
            if not task.cancelled():task.exception()
        task.add_done_callback(finished)
        return await asyncio.shield(task)

def install(app,services):
    extractor=Extractor();app.state.attachment_extractor=extractor
    @app.get('/local/upload-limits')
    async def limits():
        result=__import__('upload_limits').public()
        result.update(workspace_files=services['MAX_BATCH_FILES'],workspace_bytes=services['MAX_BATCH_BYTES'],document_bytes=services['MAX_UPLOAD_BYTES'],question_chars=MAX_ASSIGNMENT_CHARS)
        return result
    @app.post('/api/extract/batch')
    async def batch(request:Request, files:list[UploadFile]=File(...),user=Depends(services['require_user'])):
        services['enforce_rate_limit'](request,services['EXTRACT_LIMIT'],'extract',user_id=user['id'])
        if len(files)>QUESTION_FILES:raise HTTPException(413,'Attach at most 5 files for one question.')
        if len(extractor.pending)>=2:raise HTTPException(409,'Attachment reading is busy. Try again when the current extraction finishes.')
        from security import sanitize_filename,ALLOWED_ASSIGNMENT_EXTENSIONS
        prepared=[];total=0;digests=set();page_budget=0
        for file in files:
            name=sanitize_filename(file.filename or 'question',ALLOWED_ASSIGNMENT_EXTENSIONS)
            data=await services['_read_upload'](file,QUESTION_FILE_BYTES);total+=len(data)
            if total>QUESTION_BYTES:raise HTTPException(413,'Keep question attachments within 50 MB total.')
            if name.lower().endswith('.pdf'):
                import io
                from pypdf import PdfReader
                try:page_budget+=len(PdfReader(io.BytesIO(data)).pages)
                except Exception as exc:raise HTTPException(415,'Could not read this question PDF.') from exc
            else:page_budget+=1
            if page_budget>QUESTION_PAGES:raise HTTPException(413,'Use at most 20 relevant pages across one question. Course material belongs in Workspace.')
            digest=hashlib.sha256(data).hexdigest()
            if digest in digests:raise HTTPException(409,'The same attachment was added twice. Remove the duplicate.')
            digests.add(digest);prepared.append((name,data))
        async def events():
            results=[];pages=0;chars=0
            try:
                for index,(name,data) in enumerate(prepared):
                    yield 'data: '+json.dumps({'stage':'reading','index':index,'filename':name})+'\n\n'
                    result=await extractor.extract(user['id'],name,data)
                    pages+=result['page_count'];chars+=len(result['text'])+len(name)+10
                    if pages>QUESTION_PAGES:raise HTTPException(413,'Use at most 20 relevant pages across one question. Course material belongs in Workspace.')
                    if chars>MAX_ASSIGNMENT_CHARS:raise HTTPException(413,'The combined extracted question is too long. Remove unrelated pages or attachments.')
                    results.append(result)
                    yield 'data: '+json.dumps({'stage':'ready','index':index,'chars':result['chars'],'cached':result.get('cached',False)})+'\n\n'
                yield 'data: '+json.dumps({'stage':'complete','files':results})+'\n\n'
            except HTTPException as error:yield 'data: '+json.dumps({'stage':'error','message':error.detail})+'\n\n'
            except Exception:
                __import__('logging').getLogger(__name__).exception('Local attachment extraction failed')
                yield 'data: '+json.dumps({'stage':'error','message':'Could not read this attachment. Try a clearer screenshot or text-based document.'})+'\n\n'
        return StreamingResponse(events(),media_type='text/event-stream',headers={'Cache-Control':'no-store','X-Accel-Buffering':'no'})
