"""Single local owner identity. No passwords, cookies or account endpoints."""
from fastapi import Request
import db
from usage_log import set_current_user
OWNER_ID = 'local-owner'

def initialize():
    with db.connect() as c:
        c.execute('INSERT OR IGNORE INTO users (id,email,name,username,created_at,is_admin,is_verified) VALUES (?,?,?,?,?,?,?)', (OWNER_ID, 'local@localhost', 'Local workspace', 'local', db.utc_now(), 1, 1))

def maybe_user(request: Request):
    return db.get_user_by_id(OWNER_ID)

async def current_user(request: Request):
    user = maybe_user(request)
    request.state.user = user
    set_current_user(OWNER_ID)
    return user
