"""Crash-recoverable document replacement, with a staged versioned search index."""
from __future__ import annotations
import hashlib, json, os, re, shutil, uuid
from fastapi import HTTPException
import db


def root():
    return db.DB_PATH.parent / 'document-replacements'


def recover():
    """Registry hash is the commit marker; never publish an incomplete replacement."""
    root().mkdir(parents=True, exist_ok=True)
    for directory in root().iterdir():
        if not directory.is_dir() or directory.is_symlink() or not re.fullmatch('[0-9a-f]{32}',directory.name):continue
        journal = directory / 'journal.json'
        if not journal.is_file():
            shutil.rmtree(directory)
            continue
        value = json.loads(journal.read_text(encoding='utf-8'))
        import retrieval
        target = retrieval.course_workspace(value['user'], value['course']) / value['filename']
        document = db.get_document_by_name(value['user'], value['course'], value['filename'])
        backup = directory / 'previous'
        if document and document['sha256'] != value['sha256']:
            if backup.exists():
                os.replace(backup, target)
        shutil.rmtree(directory)


def replace(user, course, filename, data, expected_sha, doc_type):
    import retrieval
    with retrieval._user_ingest_lock(user):
        original = db.get_document_by_name(user, course['id'], filename)
        if not original or original['sha256'] != expected_sha:
            raise HTTPException(409, 'This document changed since you selected it. Refresh Workspace and choose again.')
        digest = hashlib.sha256(data).hexdigest()
        if digest == expected_sha:
            return original
        if db.active_index_job(user, course['id']):
            raise HTTPException(409, 'This document is being indexed. Wait until it finishes before replacing it.')
        directory = root() / uuid.uuid4().hex
        directory.mkdir(parents=True)
        staged = directory / filename
        target = retrieval.course_workspace(user, course['id']) / filename
        backup = directory / 'previous'
        try:
            with staged.open('xb') as handle:
                handle.write(data);handle.flush();os.fsync(handle.fileno())
            # Extraction/embedding happens while the original PDF and index still serve readers.
            chunks, record, manifest = retrieval._extract_index_file(staged, user, course['id'], course['name'], doc_type)
            value = {'user':user, 'course':course['id'], 'filename':filename, 'sha256':digest}
            with (directory / 'journal.tmp').open('x', encoding='utf-8') as handle:
                json.dump(value, handle);handle.flush();os.fsync(handle.fileno())
            os.replace(directory / 'journal.tmp',directory / 'journal.json')

            def publish(collection, manifests):
                try:
                    with db.connect() as connection:
                        connection.execute('BEGIN IMMEDIATE')
                        token = db.COMMIT_CONNECTION.set(connection)
                        try:
                            current = db.get_document_by_name(user, course['id'], filename)
                            if not current or current['sha256'] != expected_sha:
                                raise HTTPException(409, 'The original document changed. Refresh Workspace and retry.')
                            os.replace(target, backup)
                            os.replace(staged, target)
                            # Pin legacy bookmarks before the hash changes, without
                            # altering personal notes or their retention order.
                            connection.execute("UPDATE learning_objects SET payload=json_set(payload,'$.source_sha',?) WHERE kind='annotation' AND user_id=? AND json_extract(payload,'$.document_id')=? AND json_extract(payload,'$.source_sha') IS NULL", (expected_sha,user,current['id']))
                            db.sync_documents(user, [record], prune=False)
                            db.publish_index(user, collection, manifests, full=False)
                        finally:
                            db.COMMIT_CONNECTION.reset(token)
                except BaseException:
                    if backup.exists():os.replace(backup, target)
                    raise

            with retrieval.INGEST_LOCK:
                retrieval._publish_chunks(user, chunks, [manifest], replacements={(course['id'],filename)}, publish=publish)
            return db.get_document_by_name(user, course['id'], filename)
        finally:
            # Keep the recovery journal if restoring the previous file itself failed.
            current = db.get_document_by_name(user, course['id'], filename)
            if not backup.exists() or (current and current['sha256'] == digest):
                shutil.rmtree(directory)
