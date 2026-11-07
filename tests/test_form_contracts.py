"""Public form choices must agree with upload and edit request schemas."""
import uuid
from typing import get_args
import pytest
import app,auth,db
from study_catalog import DOC_TYPES,DocumentType
from chunk_uploads import BatchSpec
def add_document(course):
    db.sync_documents(auth.OWNER_ID,[{'course_id':course['id'],'filename':'notes.md','sha256':'a'*64,'size':100,'doc_type':'notes'}],prune=False)
    return db.get_document_by_name(auth.OWNER_ID,course['id'],'notes.md')

@pytest.mark.parametrize('doc_type', sorted(DOC_TYPES))
def test_all_document_types_save_in_place(client,monkeypatch,doc_type):
    course=db.create_course(auth.OWNER_ID,'Types '+uuid.uuid4().hex)
    document=add_document(course)
    calls=[]
    monkeypatch.setattr(app,'update_file_doc_type',lambda *args:calls.append(args) or 1)
    response=client.put('/workspace/files/'+document['id']+'/type',json={'doc_type':doc_type})
    assert response.status_code==200,response.text
    assert db.get_document(auth.OWNER_ID,document['id'])['doc_type']==doc_type
    if doc_type!='notes':assert calls[-1][-1]==doc_type
    assert set(client.get('/local/catalog').json()['document_types'])==DOC_TYPES


def test_type_update_failure_preserves_registry(client,monkeypatch):
    course=db.create_course(auth.OWNER_ID,'Failure '+uuid.uuid4().hex)
    document=add_document(course)
    def fail(*args):raise RuntimeError('private storage detail')
    monkeypatch.setattr(app,'update_file_doc_type',fail)
    response=client.put('/workspace/files/'+document['id']+'/type',json={'doc_type':'syllabus'})
    assert response.status_code==503
    assert 'private storage' not in response.text
    assert db.get_document(auth.OWNER_ID,document['id'])['doc_type']=='notes'


def test_type_update_rejects_active_index_and_invalid_role(client,monkeypatch):
    course=db.create_course(auth.OWNER_ID,'Busy '+uuid.uuid4().hex)
    document=add_document(course)
    job=db.add_index_job(auth.OWNER_ID,course['id'],['notes.md'],'notes')
    try:
        assert client.put('/workspace/files/'+document['id']+'/type',json={'doc_type':'syllabus'}).status_code==409
        assert client.put('/workspace/files/'+document['id']+'/type',json={'doc_type':'unknown'}).status_code==422
    finally:db.update_index_job(job['id'],'done')
    assert db.get_document(auth.OWNER_ID,document['id'])['doc_type']=='notes'


def test_document_role_schemas_share_one_definition():
    assert set(get_args(DocumentType))==DOC_TYPES
    assert app.DocumentTypeRequest.model_fields['doc_type'].annotation==DocumentType
    assert BatchSpec.model_fields['doc_type'].annotation==DocumentType
    for schema in [app.AskRequest,app.AskQuestionRequest]:
        assert get_args(schema.model_fields['doc_types'].annotation)[0]==DocumentType


def test_visible_choices_match_backend_schemas():
    from html.parser import HTMLParser
    from pathlib import Path
    from study_catalog import Difficulty,QuestionType
    class Choices(HTMLParser):
        def __init__(self):super().__init__();self.current=None;self.values={}
        def handle_starttag(self,tag,attrs):
            attrs=dict(attrs)
            if tag=='select':self.current=attrs.get('id');self.values.setdefault(self.current,set())
            if tag=='option' and self.current and 'value' in attrs:self.values[self.current].add(attrs['value'])
        def handle_endtag(self,tag):
            if tag=='select':self.current=None
    parser=Choices();parser.feed(Path('static/index.html').read_text(encoding='utf-8'))
    for element in ['question-type','exam-type']:
        assert parser.values[element]-{'any'}==set(get_args(QuestionType))
    for element in ['difficulty','exam-difficulty']:
        assert parser.values[element]-{'any'}==set(get_args(Difficulty))


def test_date_formatter_checks_calendar_and_keeps_api_iso_dates():
    from pathlib import Path
    import subprocess,shutil
    node=shutil.which('node')
    assert node,'Node is required for the bundled math renderer'
    source=Path('static/local.js').read_text(encoding='utf-8')
    source=source[source.index('const studyDates='):source.index('async function api(')]
    check=source+"""
const assert=require('node:assert/strict');
assert.equal(studyDates.iso('21/11/2027'),'2027-11-21');
assert.equal(studyDates.display('2027-11-21'),'21/11/2027');
assert.equal(studyDates.iso(''),null);
assert.equal(studyDates.iso('29/02/2028'),'2028-02-29');
for(const value of ['31/02/2027','29/02/2027','2027-11-21','32/01/2027','01/13/2027'])assert.throws(()=>studyDates.iso(value));
"""
    result=subprocess.run([node,'-e',check],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr


def test_registry_failure_restores_indexed_type(client,monkeypatch):
    course=db.create_course(auth.OWNER_ID,'Rollback '+uuid.uuid4().hex)
    document=add_document(course);calls=[]
    monkeypatch.setattr(app,'update_file_doc_type',lambda *args:calls.append(args[-1]) or 1)
    def fail(*args):raise RuntimeError('SQLite fixture failure')
    monkeypatch.setattr(db,'update_document_type',fail)
    response=client.put('/workspace/files/'+document['id']+'/type',json={'doc_type':'syllabus'})
    assert response.status_code==503
    assert calls==['syllabus','notes']
    assert db.get_document(auth.OWNER_ID,document['id'])['doc_type']=='notes'
