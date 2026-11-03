"""Verify Tauri/minisign update payloads independently before publication."""
import base64
import hashlib
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

def verify(path, signature, public_key, version=None):
    public_lines=base64.b64decode(public_key,validate=True).decode('utf-8').splitlines()
    key=base64.b64decode(public_lines[1],validate=True)
    lines=base64.b64decode(signature,validate=True).decode('utf-8').splitlines()
    packet=base64.b64decode(lines[1],validate=True)
    if len(key)!=42 or len(packet)!=74 or packet[2:10]!=key[2:10]:raise ValueError('Wrong updater signing key')
    verifier=Ed25519PublicKey.from_public_bytes(key[10:])
    if packet[:2]==b'ED':
        digest=hashlib.blake2b()
        with path.open('rb') as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
        message=digest.digest()
    elif packet[:2]==b'Ed':message=path.read_bytes()
    else:raise ValueError('Unknown minisign algorithm')
    verifier.verify(packet[10:],message)
    prefix='trusted comment: '
    if not lines[2].startswith(prefix):raise ValueError('Invalid trusted comment')
    verifier.verify(base64.b64decode(lines[3],validate=True),packet[10:]+lines[2][len(prefix):].encode('utf-8'))
    if version is not None:
        versions=[field[len('version:'):] for field in lines[2][len(prefix):].split('\t') if field.startswith('version:')]
        if versions!=[version]:raise ValueError('Updater signature does not match the announced version')
