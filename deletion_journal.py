"""Bounded deletion hashes survive database restore; no names/emails retained."""
import hashlib, sqlite3, time
import db
from contextlib import contextmanager

def digest(identifier):
    return hashlib.sha256(identifier.encode()).hexdigest()

@contextmanager
def connect():
    c = sqlite3.connect(db.DB_PATH.parent / 'deletion-journal.sqlite')
    c.execute('CREATE TABLE IF NOT EXISTS deletions(hash TEXT PRIMARY KEY,created REAL NOT NULL)')
    c.execute('CREATE TABLE IF NOT EXISTS floor(value REAL NOT NULL)')
    if not c.execute('SELECT 1 FROM floor').fetchone():
        c.execute('INSERT INTO floor VALUES(0)')
    try:
        yield c
        c.commit()
    except BaseException:
        c.rollback()
        raise
    finally:
        c.close()

def record(identifier):
    with connect() as c:
        c.execute('INSERT OR IGNORE INTO deletions VALUES(?,?)', (digest(identifier), time.time()))
        removed = c.execute('SELECT MAX(created) FROM deletions WHERE hash NOT IN (SELECT hash FROM deletions ORDER BY created DESC LIMIT 10000)').fetchone()[0]
        floor = max(time.time() - 90 * 86400, removed or 0)
        c.execute('UPDATE floor SET value=MAX(value,?)', (floor,))
        c.execute('DELETE FROM deletions WHERE created<?', (floor,))
        c.execute('DELETE FROM deletions WHERE hash NOT IN (SELECT hash FROM deletions ORDER BY created DESC LIMIT 10000)')

def hashes():
    with connect() as c:
        return {r[0] for r in c.execute('SELECT hash FROM deletions')}

def validate_archive(zf):
    from datetime import datetime
    with connect() as c:
        floor = c.execute('SELECT value FROM floor').fetchone()[0]
    stamp = datetime(*zf.getinfo('app.db').date_time).timestamp()
    if stamp < floor:
        raise ValueError('This backup predates the retained deletion journal and cannot be restored safely.')
