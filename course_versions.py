"""Course-local freshness with a compatibility snapshot for existing saved work."""
import hashlib,json,time
import db

def initialize():
    with db.connect() as c:
        c.execute('CREATE TABLE IF NOT EXISTS course_scope_versions(user_id TEXT NOT NULL,scope TEXT NOT NULL,state TEXT NOT NULL,version TEXT NOT NULL,updated REAL NOT NULL,PRIMARY KEY(user_id,scope))')

def state(user,course_ids):
    import retrieval
    result=[]
    for owner,selected in retrieval._course_scopes(user,course_ids):
        ids=sorted(selected or [r['id'] for r in db.list_courses(owner)])
        if not ids:
            result.append((owner,[]));continue
        marks=','.join('?' for _ in ids)
        with db.connect() as c:
            docs=[tuple(r) for r in c.execute(f'SELECT id,course_id,filename,sha256,doc_type,syllabus_enabled FROM documents WHERE user_id=? AND course_id IN ({marks}) ORDER BY course_id,id',(owner,*ids))]
            manifests=[tuple(r) for r in c.execute(f'SELECT course_id,filename,manifest_json FROM extraction_manifests WHERE user_id=? AND course_id IN ({marks}) ORDER BY course_id,filename',(owner,*ids))]
            settings=[(cid,db.get_app_setting(f'course_scope:{owner}:{cid}'),db.get_app_setting(f'concept_review:{owner}:{cid}')) for cid in ids]
        result.append((owner,ids,docs,manifests,settings))
    return hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()

def version(user,course_ids,legacy):
    key=json.dumps(sorted(course_ids));fingerprint=state(user,course_ids)
    with db.connect() as c:
        row=c.execute('SELECT state,version FROM course_scope_versions WHERE user_id=? AND scope=?',(user,key)).fetchone()
        if row and row['state']==fingerprint:return row['version']
        value=hashlib.sha256((row['version']+fingerprint).encode()).hexdigest()[:24] if row else legacy(user,course_ids)
        c.execute('INSERT INTO course_scope_versions VALUES(?,?,?,?,?) ON CONFLICT(user_id,scope) DO UPDATE SET state=excluded.state,version=excluded.version,updated=excluded.updated',(user,key,fingerprint,value,time.time()))
        c.execute('DELETE FROM course_scope_versions WHERE user_id=? AND rowid NOT IN (SELECT rowid FROM course_scope_versions WHERE user_id=? ORDER BY updated DESC LIMIT 1000)',(user,user))
        return value

def warm():
    """Snapshot before indexing starts; unchanged legacy bank items remain usable."""
    import curriculum
    with db.connect() as c:
        owners=[r[0] for r in c.execute('SELECT id FROM users')]
    for owner in owners:
        combinations={(r['id'],) for r in db.list_courses(owner)}
        with db.connect() as c:
            for row in c.execute("SELECT DISTINCT json_extract(payload,'$.course_ids') FROM learning_objects WHERE user_id=? AND json_type(payload,'$.course_ids')='array'",(owner,)):
                values=json.loads(row[0]);
                if values and all(isinstance(v,str) for v in values):combinations.add(tuple(sorted(values)))
        for ids in combinations:version(owner,list(ids),curriculum._legacy_scope_version)
