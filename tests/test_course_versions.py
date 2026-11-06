import uuid
import auth,db,curriculum,course_versions

def make_course():return db.create_course(auth.OWNER_ID,'Version '+uuid.uuid4().hex)['id']

def test_legacy_versions_are_preserved_and_other_courses_do_not_invalidate(client):
    first,second=make_course(),make_course()
    before=curriculum._legacy_scope_version(auth.OWNER_ID,[first])
    course_versions.warm()
    assert curriculum.scope_version(auth.OWNER_ID,[first])==before
    db.add_document(user_id=auth.OWNER_ID,course_id=second,filename='other.md',sha256='a'*64,size=10,page_count=1)
    db.bump_corpus_revision(auth.OWNER_ID)
    assert curriculum.scope_version(auth.OWNER_ID,[first])==before

def test_content_roles_rules_and_reindex_publications_invalidate_their_scope(client):
    course=make_course();owner=auth.OWNER_ID
    before=curriculum.scope_version(owner,[course])
    doc=db.add_document(user_id=owner,course_id=course,filename='notes.md',sha256='a'*64,size=10,page_count=1)
    added=curriculum.scope_version(owner,[course]);assert before!=added
    db.update_document_type(owner,doc['id'],'syllabus')
    role=curriculum.scope_version(owner,[course]);assert role!=added
    db.set_app_setting(f'course_scope:{owner}:{course}','Exclude optional extensions.')
    scoped=curriculum.scope_version(owner,[course]);assert role!=scoped
    with db.connect() as c:c.execute('INSERT INTO extraction_manifests VALUES(?,?,?,?)',(owner,course,'notes.md','{"publication_id":"new-index"}'))
    assert curriculum.scope_version(owner,[course])!=scoped

def test_combined_scopes_change_if_either_selected_course_changes(client):
    first,second,other=make_course(),make_course(),make_course();owner=auth.OWNER_ID
    before=curriculum.scope_version(owner,[first,second])
    db.add_document(user_id=owner,course_id=other,filename='other.md',sha256='a'*64,size=10,page_count=1)
    db.bump_corpus_revision(owner)
    assert curriculum.scope_version(owner,[second,first])==before
    db.add_document(user_id=owner,course_id=first,filename='notes.md',sha256='b'*64,size=10,page_count=1)
    assert curriculum.scope_version(owner,[first,second])!=before
