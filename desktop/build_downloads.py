"""Private CI build-tool gateway; never shipped as an app service."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import hashlib
import json
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
from urllib.parse import unquote, urlsplit

REPOSITORIES = {'tauri-apps/binary-releases', 'tauri-apps/nsis-tauri-utils',
                'linuxdeploy/linuxdeploy-plugin-appimage', 'AppImage/type2-runtime'}
MAX_BYTES = 250 * 1024**2


def asset(gh, root, repository, version, name):
    """Use GitHub's authenticated API, then verify its published asset digest."""
    if repository not in REPOSITORIES or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+-]*', version):
        raise ValueError('Unsupported build-tool release.')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+-]*', name):
        raise ValueError('Invalid build-tool asset name.')
    key = hashlib.sha256(json.dumps([repository, version, name]).encode()).hexdigest()
    folder = root / key
    target = folder / name
    if target.is_file():
        return target
    raw = subprocess.check_output([gh, 'api', f'repos/{repository}/releases/tags/{version}'], timeout=60)
    metadata = next((a for a in json.loads(raw)['assets'] if a['name'] == name), None)
    if not metadata or not 0 < metadata['size'] <= MAX_BYTES:
        raise ValueError('Missing or oversized build-tool asset.')
    digest = metadata.get('digest') or ''
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', digest):
        raise ValueError('Build-tool asset has no SHA-256 digest.')
    with tempfile.TemporaryDirectory(prefix='incoming-', dir=root) as stage:
        incoming = Path(stage) / name
        subprocess.run([gh, 'release', 'download', version, '--repo',
                        'https://github.com/' + repository, '--pattern', name,
                        '--dir', stage], check=True, capture_output=True, timeout=180)
        if incoming.stat().st_size != metadata['size'] or incoming.stat().st_size > MAX_BYTES:
            raise ValueError('Build-tool asset size differs from its release metadata.')
        with incoming.open('rb') as handle:
            calculated = hashlib.file_digest(handle, 'sha256').hexdigest()
        if digest != 'sha256:' + calculated:
            raise ValueError('Build-tool checksum mismatch.')
        folder.mkdir(parents=True, exist_ok=True)
        incoming.replace(target)
    return target


@contextmanager
def tools(environment, *, linux=False):
    """Only authenticated CI uses this loopback-only, short-lived gateway."""
    gh = shutil.which('gh')
    if not environment.get('GH_TOKEN') or not gh:
        yield environment
        return
    with tempfile.TemporaryDirectory(prefix='study-build-tools-') as directory:
        root = Path(directory)
        nonce = secrets.token_urlsafe(32)
        lock = threading.Lock()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                try:
                    if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}':
                        self.send_error(403)
                        return
                    parts = [unquote(s) for s in urlsplit(self.path).path.split('/')]
                    if len(parts) != 6 or parts[1] != nonce:
                        self.send_error(404)
                        return
                    with lock:
                        target = asset(gh, root, parts[2] + '/' + parts[3], parts[4], parts[5])
                    self.send_response(200)
                    self.send_header('Content-Length', str(target.stat().st_size))
                    self.send_header('Content-Type', 'application/octet-stream')
                    self.end_headers()
                    with target.open('rb') as source:
                        shutil.copyfileobj(source, self.wfile, 128 * 1024)
                except (ValueError, OSError, subprocess.SubprocessError) as exc:
                    print('Build-tool download failed:', type(exc).__name__, flush=True)
                    self.send_error(502, 'Build-tool download could not be verified')

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        env = dict(environment)
        env['TAURI_BUNDLER_TOOLS_GITHUB_MIRROR_TEMPLATE'] = (
            f'http://127.0.0.1:{server.server_port}/{nonce}/<owner>/<repo>/<version>/<asset>')
        try:
            if linux:
                runtime = asset(gh, root, 'AppImage/type2-runtime', 'continuous', 'runtime-x86_64')
                env['LDAI_RUNTIME_FILE'] = str(runtime)
                env['LDAI_VERBOSE'] = '1'
            yield env
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
