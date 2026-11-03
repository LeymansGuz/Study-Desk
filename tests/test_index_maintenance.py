"""Course-scoped maintenance must not rebuild or alter unrelated documents."""
import uuid
from collections import namedtuple
import pytest
from fastapi import HTTPException
import app, auth, db, growth_limits


@pytest.fixture
def maintenance(client, monkeypatch):
    course = db.create_course(auth.OWNER_ID, 'Maintenance '+uuid.uuid4().hex)
    captured = []
    async def enqueue(job): captured.append(job)
    monkeypatch.setattr(app, '_enqueue_index_job', enqueue)
    yield course, captured
    for job in captured: db.update_index_job(job['id'], 'done', progress=100)


def add_document(course, filename='notes.md', doc_type='notes'):
    db.sync_documents(auth.OWNER_ID, [{'course_id': course['id'], 'filename': filename,
        'sha256': 'a'*64, 'size': 100, 'doc_type': doc_type}], prune=False)
    return db.get_document_by_name(auth.OWNER_ID, course['id'], filename)


def test_rebuild_validates_scope_and_documents_before_storage(client, maintenance, monkeypatch):
    course, captured = maintenance
    def unexpected(*a, **k): pytest.fail('Invalid requests must not reach the disk check')
    monkeypatch.setattr(growth_limits, 'disk', unexpected)
    assert client.post('/workspace/reindex', json={}).status_code == 422
    assert client.post('/workspace/reindex', json={'course_id': 'missing'}).status_code == 404
    r = client.post('/workspace/reindex', json={'course_id': course['id']})
    assert r.status_code == 422 and 'no documents' in r.json()['detail']
    assert not captured


def test_rebuild_is_scoped_queued_and_rejects_duplicate(client, maintenance):
    course, captured = maintenance
    doc = add_document(course)
    other = db.create_course(auth.OWNER_ID, 'Other '+uuid.uuid4().hex)
    other_doc = add_document(other, 'syllabus.md', 'syllabus')
    response = client.post('/workspace/reindex', json={'course_id': course['id']})
    assert response.status_code == 200
    assert captured[0]['filenames'] == ['notes.md']
    assert captured[0]['course_id'] == course['id'] and captured[0]['doc_type'] == 'rebuild'
    assert response.json()['job_id'] == captured[0]['id']
    assert client.post('/workspace/reindex', json={'course_id': course['id']}).status_code == 409
    assert len(captured) == 1
    assert db.get_document_by_name(auth.OWNER_ID, other['id'], 'syllabus.md') == other_doc
    assert db.get_document_by_name(auth.OWNER_ID, course['id'], 'notes.md') == doc


def test_low_storage_creates_no_rebuild_job(client, maintenance, monkeypatch):
    course, captured = maintenance
    add_document(course)
    before = len(db.list_index_jobs(auth.OWNER_ID, 100))
    def low(*a, **k): raise HTTPException(507, 'Free some space, then retry.')
    monkeypatch.setattr(growth_limits, 'disk', low)
    response = client.post('/workspace/reindex', json={'course_id': course['id']})
    assert response.status_code == 507 and 'Free some space' in response.json()['detail']
    assert not captured and len(db.list_index_jobs(auth.OWNER_ID, 100)) == before


def test_rebuild_worker_preserves_document_types_and_scope(client, maintenance, monkeypatch):
    course, captured = maintenance
    add_document(course, 'outline.md', 'syllabus')
    add_document(course, 'notes.md', 'notes')
    db.set_app_setting(f'course_scope:{auth.OWNER_ID}:{course["id"]}', 'Exclude optional methods')
    calls=[]
    def ingest(user, selected, names, doc_type, **kwargs):
        calls.append((selected['id'], names, doc_type, kwargs['force']))
        return {'chunks': 2}
    monkeypatch.setattr(app, '_ingest_files_and_sync', ingest)
    assert client.post('/workspace/reindex', json={'course_id': course['id']}).status_code == 200
    app._process_index_job(captured[0]['id'])
    assert set((cid, names[0], typ, force) for cid,names,typ,force in calls) == {
        (course['id'], 'outline.md', 'syllabus', True), (course['id'], 'notes.md', 'notes', True)}
    assert db.get_app_setting(f'course_scope:{auth.OWNER_ID}:{course["id"]}') == 'Exclude optional methods'
    job=db.get_index_job(captured[0]['id'])
    assert job['status']=='done' and job['progress']==100


def test_disk_reserve_is_fixed_by_default_and_has_actionable_errors(tmp_path, monkeypatch):
    usage=namedtuple('Usage','total used free')
    monkeypatch.delenv('APP_MIN_FREE_DISK_BYTES',raising=False)
    monkeypatch.delenv('APP_MIN_FREE_DISK_PERCENT',raising=False)
    monkeypatch.setattr(growth_limits.shutil,'disk_usage',lambda _:usage(1024**4,0,2*1024**3))
    growth_limits.disk(path=tmp_path)
    with pytest.raises(HTTPException) as caught: growth_limits.disk(2*1024**3,path=tmp_path)
    assert caught.value.status_code==507 and 'contact the owner' not in caught.value.detail
    assert 'Free some space' in caught.value.detail
    monkeypatch.setenv('APP_MIN_FREE_DISK_PERCENT','20')
    with pytest.raises(HTTPException): growth_limits.disk(path=tmp_path)


def test_supported_flash_default_and_legacy_setting_are_provider_scoped(monkeypatch):
    import tools
    monkeypatch.setenv('OPENAI_API_KEY','sk-offline-not-a-real-key')
    monkeypatch.setenv('OPENAI_BASE_URL','https://api.deepseek.com/v1')
    monkeypatch.delenv('OPENAI_MODEL',raising=False)
    tools.get_settings.cache_clear()
    assert tools.get_settings().model=='deepseek-flash'
    monkeypatch.setenv('OPENAI_MODEL','deepseek-chat')
    tools.get_settings.cache_clear()
    assert tools.get_settings().model=='deepseek-flash'
    monkeypatch.setenv('OPENAI_BASE_URL','https://example.test/v1')
    tools.get_settings.cache_clear()
    assert tools.get_settings().model=='deepseek-chat'
    tools.get_settings.cache_clear()


def test_forced_rebuild_republishes_cached_document_without_touching_other_courses(client, maintenance, monkeypatch, tmp_path):
    import hashlib, index_cache, retrieval
    course, _ = maintenance
    original = add_document(course)
    path=tmp_path/'notes.md'; path.write_text('Covered principles',encoding='utf-8')
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    manifest={'course_id':course['id'],'filename':'notes.md','extraction_signature':index_cache.signature(digest),'indexed_pages':[1]}
    db.publish_index(auth.OWNER_ID,'offline-fixture',[manifest],full=False)
    monkeypatch.setattr(retrieval,'course_workspace',lambda *a:tmp_path)
    monkeypatch.setattr(retrieval,'corpus_documents',lambda *a:[{'course_id':course['id'],'source_file':'notes.md'}])
    calls=[]
    def extract(*a):
        calls.append('extract')
        return ([{'text':'Covered principles'}],{**original,'chunks':1},manifest)
    def publish(user,chunks,manifests,**kwargs):
        calls.append(kwargs)
        return ('rebuilt-fixture',1)
    monkeypatch.setattr(retrieval,'_extract_index_file',extract)
    monkeypatch.setattr(retrieval,'_publish_chunks',publish)
    retrieval._ingest_file_set(auth.OWNER_ID,course,['notes.md'])
    assert not calls  # Normal indexing reuses an unchanged published document.
    retrieval._ingest_file_set(auth.OWNER_ID,course,['notes.md'],force=True)
    assert calls==['extract',{'replacements':{(course['id'],'notes.md')}}]


def test_deepseek_json_stages_explicitly_disable_hidden_thinking(monkeypatch):
    import asyncio, tools
    from pydantic import BaseModel
    from langchain_core.messages import AIMessage
    class Probe(BaseModel): value: str
    calls=[]
    class Model:
        async def ainvoke(self, *args, **kwargs):
            calls.append(kwargs)
            return AIMessage(content='{"value":"checked"}')
    monkeypatch.setattr(tools,'_get_llm',lambda *a:Model())
    monkeypatch.setattr(tools,'get_settings',lambda:tools.LLMSettings('deepseek-flash','https://api.deepseek.com/v1','offline'))
    assert asyncio.run(tools._invoke_json('Return JSON with value.',0,Probe)).value=='checked'
    assert calls[0]['extra_body']['thinking']=={'type':'disabled'}
    assert calls[0]['extra_body']['max_tokens']==calls[0]['max_tokens']
    monkeypatch.setattr(tools,'get_settings',lambda:tools.LLMSettings('custom','https://example.test/v1','offline'))
    asyncio.run(tools._invoke_json('Return JSON with value.',0,Probe))
    assert 'extra_body' not in calls[1]
