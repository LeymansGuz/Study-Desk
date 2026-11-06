import retrieval,db

def test_reindex_embeds_only_changed_text_and_preserves_atomic_publication(monkeypatch):
    batches=[];published=[]
    class Collection:
        def add(self,**kwargs):batches.append(kwargs)
        def count(self):return sum(len(b['ids']) for b in batches)
    class Client:
        def create_collection(self,**kwargs):return Collection()
        def delete_collection(self,*a):raise AssertionError('Valid replacement should be published')
    monkeypatch.setattr(retrieval,'_client',lambda:Client())
    monkeypatch.setattr(retrieval,'_get_collection',lambda *a:object())
    monkeypatch.setattr(retrieval,'_all_records',lambda *a,**k:iter([('old','Unchanged paragraph',{'course_id':'c','source_file':'notes.md'},[1.,2.]),('other','Other file',{'course_id':'c','source_file':'other.md'},[3.,4.])]))
    monkeypatch.setattr(retrieval,'prune_index_versions',lambda *a:None)
    monkeypatch.setattr(db,'publish_index',lambda *a,**k:published.append(a))
    import growth_limits
    monkeypatch.setattr(growth_limits,'disk',lambda *a:None)
    chunks=[{'id':'new-a','text':'Unchanged paragraph','metadata':{'course_id':'c','source_file':'notes.md'}},{'id':'new-b','text':'Changed paragraph','metadata':{'course_id':'c','source_file':'notes.md'}}]
    retrieval._publish_chunks('test',chunks,[],replacements={('c','notes.md')})
    calculated=[d for batch in batches if 'embeddings' not in batch for d in batch['documents']]
    reused=[d for batch in batches if 'embeddings' in batch for d in batch['documents']]
    assert calculated==['Changed paragraph'] and set(reused)=={'Unchanged paragraph','Other file'}
    assert len(published)==1
    assert all('embedding' not in row for row in chunks)
