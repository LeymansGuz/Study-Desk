"""Local-only SQLite vectors with exact cosine retrieval and bounded NumPy batches.

No HTTP server, tenant/RBAC layer, plugin loader, pickle or model configuration
deserialization. Metadata is inert JSON and SQL values are always bound.
"""
from pathlib import Path
from contextlib import contextmanager
import json,sqlite3,time,re
import numpy as np

def _json(value):return json.dumps(value,ensure_ascii=False,allow_nan=False)

def _where(where,_depth=0):
    if _depth>12:raise ValueError('Vector filter is too deeply nested.')
    if not where:return '1',[]
    if not isinstance(where,dict) or len(where)!=1:raise ValueError('Invalid vector metadata filter.')
    key,value=next(iter(where.items()))
    if key in {'$and','$or'}:
        if not isinstance(value,list) or not 1<=len(value)<=100:raise ValueError('Invalid filter clauses.')
        clauses=[_where(v,_depth+1) for v in value]
        return '('+(' AND ' if key=='$and' else ' OR ').join(v[0] for v in clauses)+')',[p for v in clauses for p in v[1]]
    if not re.fullmatch('[a-zA-Z0-9_:-]{1,64}',key):raise ValueError('Invalid metadata key.')
    column={'course_id':'course','source_file':'file','doc_type':'doc_type'}.get(key)
    params=[] if column else ['$.'+key]
    column=column or 'json_extract(metadata,?)'
    if not isinstance(value,dict):value={'$eq':value}
    if len(value)!=1:raise ValueError('Invalid filter comparison.')
    operator,operand=next(iter(value.items()))
    if operator in {'$in','$nin'}:
        if not isinstance(operand,list) or len(operand)>1000:raise ValueError('Invalid filter values.')
        return column+(' NOT IN ' if operator=='$nin' else ' IN ')+'(SELECT value FROM json_each(?))',params+[_json(operand)]
    operators={'$eq':'=','$ne':'!=','$gt':'>','$gte':'>=','$lt':'<','$lte':'<='}
    if operator not in operators or not isinstance(operand,(str,int,float,bool)):raise ValueError('Invalid filter operator/value.')
    return column+operators[operator]+'?',params+[operand]

class Client:
    def __init__(self,path):
        self.directory=Path(path);self.directory.mkdir(parents=True,exist_ok=True)
        self.path=self.directory/'vectors.sqlite3'
        with self.connect() as c:
            c.executescript('''CREATE TABLE IF NOT EXISTS collections(name TEXT PRIMARY KEY,metadata TEXT NOT NULL,dimension INTEGER);
            CREATE TABLE IF NOT EXISTS records(collection TEXT NOT NULL REFERENCES collections(name) ON DELETE CASCADE,
            id TEXT NOT NULL,document TEXT NOT NULL,metadata TEXT NOT NULL,vector BLOB NOT NULL,
            course TEXT,file TEXT,doc_type TEXT,UNIQUE(collection,id));
            CREATE INDEX IF NOT EXISTS vectors_course ON records(collection,course);
            CREATE INDEX IF NOT EXISTS vectors_file ON records(collection,course,file);
            CREATE TABLE IF NOT EXISTS migrations(name TEXT PRIMARY KEY,completed REAL NOT NULL);''')
        if (self.directory/'chroma.sqlite3').exists():
            from vector_migration import migrate
            migrate(self)

    @contextmanager
    def connect(self):
        c=sqlite3.connect(self.path,timeout=30);c.row_factory=sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON');c.execute('PRAGMA trusted_schema=OFF')
        try:
            with c:yield c
        finally:c.close()

    def heartbeat(self):
        with self.connect() as c:c.execute('SELECT 1').fetchone()
        return time.time_ns()

    def create_collection(self,name,metadata=None):
        if not isinstance(name,str) or not 1<=len(name)<=200:raise ValueError('Invalid collection name.')
        with self.connect() as c:c.execute('INSERT INTO collections(name,metadata) VALUES(?,?)',(name,_json(metadata or {})))
        return Collection(self,name)

    def get_or_create_collection(self,name,metadata=None):
        with self.connect() as c:exists=c.execute('SELECT 1 FROM collections WHERE name=?',(name,)).fetchone()
        if not exists:
            try:return self.create_collection(name,metadata)
            except sqlite3.IntegrityError:pass
        return Collection(self,name)

    def list_collections(self):
        with self.connect() as c:return [Collection(self,r[0]) for r in c.execute('SELECT name FROM collections ORDER BY name')]

    def delete_collection(self,name):
        with self.connect() as c:c.execute('DELETE FROM collections WHERE name=?',(name,))

class Collection:
    def __init__(self,client,name):self.client=client;self.name=name

    @property
    def metadata(self):
        with self.client.connect() as c:
            row=c.execute('SELECT metadata FROM collections WHERE name=?',(self.name,)).fetchone()
            if row is None:raise ValueError('The vector collection is unavailable.')
            return json.loads(row[0])

    def count(self):
        with self.client.connect() as c:return c.execute('SELECT COUNT(*) FROM records WHERE collection=?',(self.name,)).fetchone()[0]

    def add(self,ids,documents,metadatas=None,embeddings=None):
        if not ids:return
        if len(ids)>1000 or len(set(ids))!=len(ids):raise ValueError('Invalid vector batch or duplicate identifiers.')
        if embeddings is None:
            from local_embeddings import embed
            embeddings=embed(documents)
        vectors=np.asarray(embeddings,dtype=np.float32)
        if vectors.ndim!=2 or vectors.shape[0]!=len(ids) or not 1<=vectors.shape[1]<=4096 or not np.isfinite(vectors).all():raise ValueError('Invalid embedding vectors.')
        vectors=vectors/np.maximum(np.linalg.norm(vectors,axis=1,keepdims=True),1e-12)
        metadatas=metadatas if metadatas is not None else [{} for _ in ids]
        if len(documents)!=len(ids) or len(metadatas)!=len(ids):raise ValueError('Mismatched vector batch.')
        rows=[]
        for key,text,metadata,vector in zip(ids,documents,metadatas,vectors):
            if not isinstance(key,str) or not isinstance(text,str) or not isinstance(metadata,dict):raise ValueError('Invalid vector record.')
            rows.append((self.name,key,text,_json(metadata),vector.astype('<f4').tobytes(),metadata.get('course_id'),metadata.get('source_file'),metadata.get('doc_type')))
        with self.client.connect() as c:
            row=c.execute('SELECT dimension FROM collections WHERE name=?',(self.name,)).fetchone()
            if row is None or row[0] not in {None,vectors.shape[1]}:raise ValueError('Embedding dimension does not match this collection.')
            c.execute('UPDATE collections SET dimension=? WHERE name=?',(vectors.shape[1],self.name))
            c.executemany('INSERT INTO records VALUES(?,?,?,?,?,?,?,?)',rows)

    def _filter(self,where=None,ids=None):
        clause,params=_where(where);clause='collection=? AND '+clause;params=[self.name,*params]
        if ids is not None:clause+=' AND id IN (SELECT value FROM json_each(?))';params.append(_json(ids))
        return clause,params

    def get(self,where=None,include=None,limit=None,offset=0,ids=None):
        include=['documents','metadatas'] if include is None else include
        clause,params=self._filter(where,ids)
        with self.client.connect() as c:
            rows=c.execute('SELECT id,document,metadata'+(',vector' if 'embeddings' in include else '')+' FROM records WHERE '+clause+' ORDER BY rowid LIMIT ? OFFSET ?',params+[limit if limit is not None else -1,offset]).fetchall()
        result={'ids':[r['id'] for r in rows]}
        if 'documents' in include:result['documents']=[r['document'] for r in rows]
        if 'metadatas' in include:result['metadatas']=[json.loads(r['metadata']) for r in rows]
        if 'embeddings' in include:result['embeddings']=[np.frombuffer(r['vector'],dtype='<f4').copy() for r in rows]
        return result

    def update(self,ids,metadatas):
        if len(ids)!=len(metadatas):raise ValueError('Mismatched metadata batch.')
        with self.client.connect() as c:
            for key,patch in zip(ids,metadatas):
                row=c.execute('SELECT metadata FROM records WHERE collection=? AND id=?',(self.name,key)).fetchone()
                if row is None:continue
                value={**json.loads(row[0]),**patch}
                c.execute('UPDATE records SET metadata=?,course=?,file=?,doc_type=? WHERE collection=? AND id=?',(_json(value),value.get('course_id'),value.get('source_file'),value.get('doc_type'),self.name,key))

    def delete(self,ids=None,where=None):
        if ids is None and where is None:raise ValueError('A deletion filter is required.')
        clause,params=self._filter(where,ids)
        with self.client.connect() as c:c.execute('DELETE FROM records WHERE '+clause,params)

    def query(self,query_texts=None,query_embeddings=None,n_results=4,where=None,include=None):
        if query_embeddings is None:
            from local_embeddings import embed
            query_embeddings=embed(query_texts)
        include=['documents','metadatas','distances'] if include is None else include
        if not 1<=n_results<=2000:raise ValueError('Invalid vector result limit.')
        output={k:[] for k in ['ids',*include]}
        clause,params=self._filter(where)
        for query in query_embeddings:
            query=np.asarray(query,dtype=np.float32)
            if query.ndim!=1 or not np.isfinite(query).all():raise ValueError('Invalid query vector.')
            query=query/max(float(np.linalg.norm(query)),1e-12);best=[]
            with self.client.connect() as c:
                c.execute('BEGIN')
                cursor=c.execute('SELECT rowid,vector FROM records WHERE '+clause,params)
                while rows:=cursor.fetchmany(2048):
                    vectors=np.frombuffer(b''.join(r['vector'] for r in rows),dtype='<f4').reshape(len(rows),-1)
                    if vectors.shape[1]!=len(query):raise ValueError('Query embedding dimension mismatch.')
                    scores=vectors@query;indices=np.argpartition(scores,-min(n_results,len(rows)))[-n_results:]
                    best=sorted(best+[(float(scores[i]),rows[i]['rowid']) for i in indices],key=lambda v:(-v[0],v[1]))[:n_results]
                selected={r['rowid']:r for r in c.execute('SELECT rowid,id,document,metadata FROM records WHERE rowid IN (SELECT value FROM json_each(?))',(_json([r[1] for r in best]),))}
                output['ids'].append([selected[rowid]['id'] for _,rowid in best])
                if 'documents' in include:output['documents'].append([selected[rowid]['document'] for _,rowid in best])
                if 'metadatas' in include:output['metadatas'].append([json.loads(selected[rowid]['metadata']) for _,rowid in best])
                if 'distances' in include:output['distances'].append([max(0.,min(2.,1-score)) for score,_ in best])
        return output
