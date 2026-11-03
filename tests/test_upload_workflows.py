import asyncio,io,json,uuid
from pathlib import Path
import pytest
from fastapi import HTTPException
from PIL import Image
from pypdf import PdfWriter
import app,auth,db,attachment_batch,extraction
from security import validate_upload
from upload_limits import MIB

def screenshot():
 out=io.BytesIO();Image.new('RGB',(120,80),'white').save(out,format='PNG');return out.getvalue()

def events(response):return [json.loads(s[6:]) for s in response.text.split('\n\n') if s.startswith('data: ')]

def test_shared_limits_and_large_batch_preflight(client):
 limits=client.get('/local/upload-limits').json()
 assert limits['workspace_files']==50 and limits['workspace_bytes']==500*MIB and limits['question_chars']==30000
 course=client.post('/workspace/courses',json={'name':'Batch limits '+uuid.uuid4().hex[:6]}).json()['id']
 spec={'course_id':course,'files':[{'name':f'{n}.txt','size':10} for n in range(50)]}
 response=client.post('/workspace/uploads',json=spec);assert response.status_code==201,response.text
 client.delete('/workspace/uploads/'+response.json()['id'])
 spec['files'].append({'name':'extra.txt','size':10});assert client.post('/workspace/uploads',json=spec).status_code==422
 for name,size in [('large.pdf',201*MIB),('large.png',21*MIB)]:
  spec['files']=[{'name':name,'size':size}];assert client.post('/workspace/uploads',json=spec).status_code==413

def test_screenshot_type_and_pixel_validation_without_ocr():
 assert validate_upload('notes.png',screenshot())['page_count']==1
 with pytest.raises(HTTPException):validate_upload('notes.jpg',screenshot())
 with pytest.raises(HTTPException):validate_upload('bad.png',b'not an image')
 out=io.BytesIO();Image.new('1',(4001,4000)).save(out,format='PNG')
 with pytest.raises(HTTPException) as e:validate_upload('huge.png',out.getvalue())
 assert e.value.status_code==413

def test_batch_stream_order_and_repeat_cache_preserve_context(client,monkeypatch):
 calls=[]
 def extract(name,data):
  calls.append(name);return dict(filename=name,text='Find the derivative of x squared at x equals three.',page_count=1,ocr_used=False,truncated=False,chars=50,warnings=[],needs_review=False)
 monkeypatch.setattr(attachment_batch,'extract_assignment_file',extract)
 suffix=uuid.uuid4().hex
 files=[('files',('a.txt',suffix.encode())),('files',('b.txt',(suffix+'b').encode()))]
 first=events(client.post('/api/extract/batch',files=files));assert [e['stage'] for e in first]==['reading','ready','reading','ready','complete']
 second=events(client.post('/api/extract/batch',files=files));assert all(e['cached'] for e in second if e['stage']=='ready')
 assert calls==['a.txt','b.txt']

def test_batch_limits_and_page_budget_reject_before_ocr(client,monkeypatch):
 def forbidden(*a):raise AssertionError('OCR must not run')
 monkeypatch.setattr(attachment_batch,'extract_assignment_file',forbidden)
 assert client.post('/api/extract/batch',files=[('files',(f'{n}.txt',str(n))) for n in range(6)]).status_code==413
 assert client.post('/api/extract/batch',files=[('files',('a.txt','same')),('files',('b.txt','same'))]).status_code==409
 writer=PdfWriter()
 for _ in range(21):writer.add_blank_page(width=72,height=72)
 data=io.BytesIO();writer.write(data)
 assert client.post('/api/extract/batch',files={'files':('too-many.pdf',data.getvalue(),'application/pdf')}).status_code==413

def test_batch_refuses_context_overflow_without_silent_truncation(client,monkeypatch):
 def extract(name,data):return dict(filename=name,text='a'*16000,page_count=1,ocr_used=False,truncated=False,chars=16000,warnings=[],needs_review=False)
 monkeypatch.setattr(attachment_batch,'extract_assignment_file',extract)
 token=uuid.uuid4().hex
 result=events(client.post('/api/extract/batch',files=[('files',('a.txt',token)),('files',('b.txt',token+'b'))]))
 assert result[-1]['stage']=='error' and 'too long' in result[-1]['message']
 assert not any(e['stage']=='complete' for e in result)

def test_workspace_image_ocr_is_checkpointed_and_previewable(client,monkeypatch,tmp_path):
 import retrieval,index_cache,document_ocr
 calls=[];course=db.create_course(auth.OWNER_ID,'Image notes '+uuid.uuid4().hex[:6])
 file=app.course_workspace(auth.OWNER_ID,course['id'])/'notes.png';file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(screenshot())
 record=db.add_document(user_id=auth.OWNER_ID,course_id=course['id'],filename=file.name,sha256='f'*64,size=file.stat().st_size,page_count=1)
 def ocr(image):calls.append(True);return {'text':'Course note text describing functions and their properties.','confidence':.95,'needs_review':False}
 monkeypatch.setattr(document_ocr,'ocr_layout',ocr)
 token=retrieval._EXTRACTION_CONTEXT.set((record['id'],auth.OWNER_ID,'test-image-signature'))
 try:
  assert retrieval._read_pages(file)==retrieval._read_pages(file)
  assert len(calls)==1
 finally:retrieval._EXTRACTION_CONTEXT.reset(token)
 assert client.get('/workspace/documents/'+record['id']+'/preview').json()['mode']=='image'

def test_concurrent_retry_shares_one_extraction_worker(monkeypatch):
 import time
 calls=[]
 def extract(name,data):
  calls.append(name);time.sleep(.05)
  return dict(filename=name,text='Find the derivative.',page_count=1,ocr_used=False,truncated=False,chars=20,warnings=[],needs_review=False)
 monkeypatch.setattr(attachment_batch,'extract_assignment_file',extract)
 async def run():
  worker=attachment_batch.Extractor()
  values=await asyncio.gather(worker.extract('owner','question.txt',b'same'),worker.extract('owner','renamed.txt',b'same'))
  assert len(calls)==1 and values[1]['filename']=='renamed.txt' and values[1]['cached']
 asyncio.run(run())

def test_cancelled_request_keeps_worker_reserved_until_ocr_finishes(monkeypatch):
 import time
 def extract(name,data):
  time.sleep(.1);return dict(filename=name,text='Readable local question',page_count=1,ocr_used=True,truncated=False,chars=23,warnings=[],needs_review=False)
 monkeypatch.setattr(attachment_batch,'extract_assignment_file',extract)
 async def run():
  worker=attachment_batch.Extractor();request=asyncio.create_task(worker.extract('owner','a.txt',b'question'))
  await asyncio.sleep(.02);request.cancel()
  with pytest.raises(asyncio.CancelledError):await request
  assert worker.busy()
  await asyncio.sleep(.15);assert not worker.busy()
 asyncio.run(run())
