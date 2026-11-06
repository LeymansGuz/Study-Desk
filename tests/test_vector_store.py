import json,sqlite3
import numpy as np
import pytest
from vector_store import Client

def test_persistence_filters_updates_exact_cosine_and_delete(tmp_path):
    client=Client(tmp_path);c=client.create_collection('owner',{'created_at':3})
    c.add(ids=['a','b','c'],documents=['alpha','beta','gamma'],metadatas=[{'course_id':'one','source_file':'notes.md','enabled':True},{'course_id':'two'},{'course_id':'one','score':2}],embeddings=[[1,0],[0,1],[1,1]])
    result=c.query(query_embeddings=[[1,0]],where={'course_id':'one'},n_results=3)
    assert result['ids']==[['a','c']] and result['distances'][0]==pytest.approx([0,1-1/2**.5])
    assert Client(tmp_path).get_or_create_collection('owner').count()==3
    assert c.get(where={'$and':[{'course_id':{'$in':['one']}},{'score':{'$gte':2}}]})['ids']==['c']
    c.update(ids=['a'],metadatas=[{'doc_type':'syllabus'}])
    assert c.get(where={'doc_type':'syllabus'})['metadatas'][0]['source_file']=='notes.md'
    c.delete(where={'course_id':'two'});assert c.count()==2
    assert c.get(ids=['c'],include=['embeddings'])['embeddings'][0]==pytest.approx([1/2**.5]*2)
    client.delete_collection('owner');assert client.list_collections()==[]

def test_writes_are_atomic_and_values_cannot_become_sql_or_code(tmp_path):
    c=Client(tmp_path).create_collection('safe')
    c.add(ids=['a'],documents=['first'],embeddings=[[1,0]])
    with pytest.raises(sqlite3.IntegrityError):c.add(ids=['b','a'],documents=['second','duplicate'],embeddings=[[0,1],[1,0]])
    assert c.count()==1
    with pytest.raises(ValueError):c.get(where={'x);DROP TABLE records;--':'value'})
    with pytest.raises(ValueError):c.add(ids=['bad'],documents=['nan'],embeddings=[[float('nan'),0]])
    with pytest.raises(ValueError):c.add(ids=['bad'],documents=['dimension'],embeddings=[[1,0,0]])
    c.update(ids=['a'],metadatas=[{'source_file':"x' OR 1=1--",'config':{'trust_remote_code':True}}])
    assert c.get(where={'source_file':"x' OR 1=1--"})['ids']==['a']
    assert c.count()==1

def legacy_fixture(path,*,invalid_vector=False):
    path.mkdir(exist_ok=True)
    with sqlite3.connect(path/'chroma.sqlite3') as c:
        c.executescript('''CREATE TABLE collections(id,name,dimension,config_json_str);
        CREATE TABLE segments(id,scope,collection);
        CREATE TABLE embeddings(id,segment_id,embedding_id);
        CREATE TABLE embedding_metadata(id,key,string_value,int_value,float_value,bool_value);
        CREATE TABLE embeddings_queue(seq_id,id,topic,vector,encoding);''')
        c.execute('INSERT INTO collections VALUES(?,?,?,?)',('col','owner',384,json.dumps({'embedding_function':{'name':'attacker.remote.module','trust_remote_code':True}})))
        c.execute('INSERT INTO segments VALUES(?,?,?)',('seg','METADATA','col'))
        c.execute('INSERT INTO embeddings VALUES(?,?,?)',(1,'seg','chunk'))
        for key,value in [('chroma:document','Document remains inert.'),('course_id','course'),('source_file','notes.md')]:c.execute('INSERT INTO embedding_metadata VALUES(?,?,?,NULL,NULL,NULL)',(1,key,value))
        vector=np.ones(384,dtype='<f4')
        if invalid_vector:vector[0]=np.nan
        c.execute('INSERT INTO embeddings_queue VALUES(?,?,?,?,?)',(1,'chunk','persistent://default/col',vector.tobytes(),'FLOAT32'))

def test_readonly_legacy_migration_preserves_data_and_ignores_code_configuration(tmp_path):
    legacy_fixture(tmp_path)
    before=(tmp_path/'chroma.sqlite3').read_bytes()
    client=Client(tmp_path);c=client.get_or_create_collection('owner')
    assert c.count()==1 and c.get()['documents']==['Document remains inert.']
    assert c.get()['metadatas']==[{'course_id':'course','source_file':'notes.md'}]
    assert (tmp_path/'chroma.sqlite3').read_bytes()==before
    assert Client(tmp_path).get_or_create_collection('owner').count()==1

def test_failed_legacy_migration_never_publishes_partial_rows(tmp_path):
    legacy_fixture(tmp_path,invalid_vector=True)
    before=(tmp_path/'chroma.sqlite3').read_bytes()
    with pytest.raises(ValueError,match='Invalid legacy vector'):Client(tmp_path)
    with sqlite3.connect(tmp_path/'vectors.sqlite3') as c:assert c.execute('SELECT COUNT(*) FROM records').fetchone()[0]==0
    assert (tmp_path/'chroma.sqlite3').read_bytes()==before
