"""Opt-in local backup scheduling and authenticated streaming encryption."""
import asyncio,hashlib,json,os,struct,tempfile,time
from pathlib import Path
from typing import Literal
from fastapi import Depends,HTTPException,UploadFile,File,Form,Request
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel,Field,SecretStr,ConfigDict
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
import backup,db,local_jobs
from rate_limits import limiter,account_key

MAGIC=b'SDENC1\r\n'
BLOCK=1024*1024

def cipher(password,salt):
    return AESGCM(hashlib.scrypt(password.encode('utf-8'),salt=salt,n=32768,r=8,p=1,maxmem=64*1024*1024,dklen=32))

def encrypt(source,target,password):
    salt=os.urandom(16);prefix=os.urandom(8);header=MAGIC+salt+prefix;box=cipher(password,salt)
    try:
        with Path(source).open('rb') as src,Path(target).open('wb') as out:
            out.write(header);counter=0
            while True:
                data=src.read(BLOCK);nonce=prefix+counter.to_bytes(4,'big');packet=box.encrypt(nonce,data,header+struct.pack('>I',counter))
                out.write(struct.pack('>I',len(packet)));out.write(packet);counter+=1
                if not data:break
    except BaseException:
        Path(target).unlink(missing_ok=True);raise

def decrypt(source,target,password):
    try:
        with Path(source).open('rb') as src,Path(target).open('wb') as out:
            header=src.read(32)
            if header[:8]!=MAGIC or len(header)!=32:raise ValueError('This is not an encrypted Study Desk backup.')
            box=cipher(password,header[8:24]);counter=0
            while True:
                length=src.read(4)
                if len(length)!=4:raise ValueError('The encrypted backup is incomplete.')
                length=struct.unpack('>I',length)[0]
                if not 16<=length<=BLOCK+16:raise ValueError('Invalid encrypted backup block.')
                data=box.decrypt(header[24:]+counter.to_bytes(4,'big'),src.read(length),header+struct.pack('>I',counter));counter+=1
                if not data:
                    if src.read(1):raise ValueError('Unexpected content after the encrypted backup.')
                    break
                out.write(data)
    except BaseException:
        Path(target).unlink(missing_ok=True);raise

class BackupPlan(BaseModel):
    model_config=ConfigDict(extra='forbid')
    interval:Literal['off','daily','weekly']='off'

class Password(BaseModel):
    model_config=ConfigDict(extra='forbid')
    passphrase:SecretStr

def password_value(value):
    value=value.get_secret_value() if isinstance(value,SecretStr) else value
    if not 12<=len(value)<=256:raise HTTPException(422,'Use a passphrase of 12–256 characters. Keep it separately; it cannot be recovered.')
    return value

def queue_due():
    plan=json.loads(db.get_app_setting('scheduled_backup','{}'));interval=plan.get('interval','off')
    if interval!='off' and time.time()-float(plan.get('last_queued',0))>={'daily':86400,'weekly':604800}[interval]:
        import auth
        try:local_jobs.submit(auth.OWNER_ID,'backup')
        except HTTPException as exc:
            if exc.status_code==429:return False
            raise
        db.set_app_setting('scheduled_backup',json.dumps({**plan,'last_queued':time.time()}));return True
    return False

async def scheduler():
    while True:
        try:queue_due()
        except Exception:
            import logging
            logging.getLogger(__name__).exception('Scheduled local backup could not be queued; retrying later')
        await asyncio.sleep(60)

def install(app,services):
    require=services['require_user']
    @app.get('/library/backups/plan')
    async def get_plan(user=Depends(require)):
        return {**json.loads(db.get_app_setting('scheduled_backup','{"interval":"off"}')),'note':'Runs while Study Desk is open. Scheduled archives are local, unencrypted and retain at most ten copies for 30 days. Encrypted exports are separate.'}

    @app.put('/library/backups/plan')
    async def set_plan(body:BackupPlan,user=Depends(require)):
        value={**body.model_dump(),'last_queued':0};db.set_app_setting('scheduled_backup',json.dumps(value));return value

    @app.post('/library/backups/encrypted')
    @limiter.limit('2/5minutes',key_func=account_key)
    async def export(body:Password,request:Request,user=Depends(require)):
        password=password_value(body.passphrase)
        async with services['WORKSPACE_LOCK']:
            with db.connect() as c:busy=c.execute("SELECT COUNT(*) FROM index_jobs WHERE status IN ('queued','running')").fetchone()[0]
            if busy:raise HTTPException(409,'Wait for document indexing before exporting a backup.')
            source=await asyncio.to_thread(backup.create_backup)
        target=source.with_suffix('.sdbackup')
        try:await asyncio.to_thread(encrypt,source,target,password)
        finally:source.unlink(missing_ok=True)
        return FileResponse(target,filename='study-desk-encrypted.sdbackup',media_type='application/octet-stream',background=BackgroundTask(target.unlink,missing_ok=True))

    @app.post('/library/backups/restore')
    @limiter.limit('2/5minutes',key_func=account_key)
    async def restore(request:Request,file:UploadFile=File(...),passphrase:str=Form(...),user=Depends(require)):
        password=password_value(passphrase)
        with tempfile.TemporaryDirectory(prefix='study-encrypted-') as folder:
            source=Path(folder)/'encrypted';target=Path(folder)/'backup.zip';size=0
            with source.open('wb') as out:
                while chunk:=await file.read(BLOCK):
                    size+=len(chunk)
                    if size>256*1024*1024:raise HTTPException(413,'Encrypted restore supports archives up to 256 MB.')
                    out.write(chunk)
            try:
                await asyncio.to_thread(decrypt,source,target,password)
                await asyncio.to_thread(backup.stage_restore,target.read_bytes())
            except (InvalidTag,ValueError):raise HTTPException(422,'The passphrase is wrong or the backup is damaged. No restore was staged.')
        return {'message':'Backup validated and staged. Restart Study Desk to apply it. Existing data will be replaced; your current provider keys remain in your system credential store.'}
