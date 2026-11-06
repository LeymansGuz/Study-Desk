"""Document-level freshness for checked guide sections, never imported claims."""
import hashlib,json
import db

def fingerprints(owner,course):
    docs=db.list_documents(owner,[course])
    with db.connect() as c:manifests={r[0]:r[1] for r in c.execute('SELECT filename,manifest_json FROM extraction_manifests WHERE user_id=? AND course_id=?',(owner,course))}
    rules=[db.get_app_setting(f'course_scope:{owner}:{course}'),db.get_app_setting(f'concept_review:{owner}:{course}'),[(d['id'],d['sha256'],manifests.get(d['filename'],'')) for d in docs if d['doc_type']=='syllabus']]
    return {d['filename']:hashlib.sha256(json.dumps([d['id'],d['sha256'],d['doc_type'],bool(d.get('syllabus_enabled',True)),manifests.get(d['filename'],''),rules],sort_keys=True).encode()).hexdigest() for d in docs}

def pin(entry,versions):
    names={s.get('source_file',s.get('file','')) for s in entry.get('sources',[])}
    return {name:versions[name] for name in names} if names and all(name in versions for name in names) else {}

def current(entry,versions):
    pins=entry.get('source_versions') or {}
    return bool(pins) and all(versions.get(name)==value for name,value in pins.items())
