"""Read legacy SQLite data as inert rows, without importing its executable library."""
from contextlib import contextmanager,closing
from pathlib import Path
import json,os,sqlite3,tempfile,threading,time
import numpy as np

LOCK=threading.Lock()

@contextmanager
def migration_lock(directory):
    with LOCK,(Path(directory)/'migration.lock').open('a+b') as stream:
        stream.seek(0);stream.write(b'0');stream.flush();started=time.monotonic()
        while True:
            try:
                stream.seek(0)
                if os.name=='nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic()-started>300:raise RuntimeError('Another local index migration is still running. Reopen Study Desk later.')
                time.sleep(.1)
        try:yield
        finally:
            stream.seek(0)
            if os.name=='nt':msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(stream,fcntl.LOCK_UN)

def migrate(client):
    from vector_store import Client
    with migration_lock(client.directory):
        with client.connect() as c:
            if c.execute("SELECT 1 FROM migrations WHERE name='legacy-sqlite-v1'").fetchone():return
            if c.execute('SELECT COUNT(*) FROM collections').fetchone()[0]:raise ValueError('Existing vector data cannot be overwritten by a legacy import. Restore a complete backup instead.')
        with tempfile.TemporaryDirectory(prefix='vector-migration-',dir=client.directory) as folder:
            copy=Path(folder)/'legacy.sqlite3'
            original=(client.directory/'chroma.sqlite3').resolve()
            import growth_limits
            growth_limits.disk(original.stat().st_size*3+1024*1024)
            with closing(sqlite3.connect(original.as_uri()+'?mode=ro',uri=True)) as source,closing(sqlite3.connect(copy)) as target:
                source.execute('PRAGMA trusted_schema=OFF');source.backup(target)
            legacy=sqlite3.connect(copy);legacy.row_factory=sqlite3.Row
            try:
                legacy.execute('PRAGMA trusted_schema=OFF')
                for name in ['collections','segments','embeddings','embedding_metadata','embeddings_queue']:
                    row=legacy.execute('SELECT type FROM sqlite_master WHERE name=?',(name,)).fetchone()
                    if not row or row[0]!='table':raise ValueError('Unsupported legacy vector schema. Original data remains unchanged.')
                legacy.execute('CREATE INDEX IF NOT EXISTS study_queue_lookup ON embeddings_queue(id,seq_id)')
                staged=Client(Path(folder)/'new')
                for collection in legacy.execute('SELECT id,name,dimension FROM collections'):
                    if collection['dimension'] not in {None,384}:raise ValueError('A legacy index uses a different embedding model. Rebuild that index from its original documents.')
                    # Config, embedding-function definitions and tenant/RBAC records
                    # are deliberately never interpreted or copied.
                    dest=staged.create_collection(collection['name'],{'hnsw:space':'cosine'})
                    cursor=legacy.execute("SELECT e.id,e.embedding_id FROM embeddings e JOIN segments s ON s.id=e.segment_id WHERE s.collection=? AND s.scope='METADATA' ORDER BY e.id",(collection['id'],))
                    count=0
                    while batch:=cursor.fetchmany(256):
                        payload={r['id']:{} for r in batch}
                        for row in legacy.execute('SELECT * FROM embedding_metadata WHERE id IN (SELECT value FROM json_each(?))',(json.dumps(list(payload)),)):
                            payload[row['id']][row['key']]=next((row[k] for k in ['string_value','int_value','float_value','bool_value'] if k in row.keys() and row[k] is not None),None)
                        reusable=[];missing=[]
                        for row in batch:
                            metadata=payload[row['id']];document=metadata.pop('chroma:document','')
                            if not isinstance(document,str):raise ValueError('Invalid legacy document text.')
                            metadata={k:v for k,v in metadata.items() if not k.startswith('chroma:') and v is not None}
                            record=(row['embedding_id'],document,metadata)
                            vector=legacy.execute("SELECT vector,encoding FROM embeddings_queue WHERE id=? AND topic LIKE ? AND vector IS NOT NULL ORDER BY seq_id DESC LIMIT 1",(row['embedding_id'],'%'+collection['id']+'%')).fetchone()
                            if vector and vector['encoding']=='FLOAT32':
                                value=np.frombuffer(vector['vector'],dtype='<f4')
                                if value.shape!=(384,) or not np.isfinite(value).all():raise ValueError('Invalid legacy vector. Original data remains unchanged.')
                                reusable.append((*record,value))
                            else:missing.append(record)
                        for rows in [reusable,missing]:
                            if rows:dest.add(ids=[r[0] for r in rows],documents=[r[1] for r in rows],metadatas=[r[2] for r in rows],**({'embeddings':[r[3] for r in rows]} if rows is reusable else {}))
                        count+=len(batch)
                    if dest.count()!=count:raise ValueError('Legacy vector migration failed its count check.')
                with staged.connect() as c:c.execute('INSERT INTO migrations VALUES(?,?)',('legacy-sqlite-v1',time.time()))
                os.replace(staged.path,client.path)
            finally:legacy.close()
