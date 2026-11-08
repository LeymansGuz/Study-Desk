"""CI tool downloads stay local, bounded and verified before caching."""
import hashlib
import json
from pathlib import Path
import urllib.request
import urllib.error
import pytest
from desktop import build_downloads as downloads


def fixture_asset(monkeypatch, *, corrupt=False, digest=True, oversized=False):
    payload = b'official-test-tool'
    metadata = {'name': 'tool.zip', 'size': downloads.MAX_BYTES + 1 if oversized else len(payload),
                'digest': 'sha256:' + hashlib.sha256(payload).hexdigest() if digest else None}
    monkeypatch.setattr(downloads.subprocess, 'check_output', lambda *a, **k: json.dumps({'assets': [metadata]}).encode())
    calls = []
    def run(args, **kwargs):
        calls.append(args)
        target = Path(args[args.index('--dir') + 1]) / 'tool.zip'
        target.write_bytes(b'X' + payload[1:] if corrupt else payload)
    monkeypatch.setattr(downloads.subprocess, 'run', run)
    return payload, calls


def test_only_verified_assets_are_cached(tmp_path, monkeypatch):
    payload, calls = fixture_asset(monkeypatch)
    path = downloads.asset('gh', tmp_path, 'tauri-apps/binary-releases', 'test-v1', 'tool.zip')
    assert path.read_bytes() == payload
    assert downloads.asset('gh', tmp_path, 'tauri-apps/binary-releases', 'test-v1', 'tool.zip') == path
    assert len(calls) == 1


@pytest.mark.parametrize('kwargs', [{'corrupt': True}, {'digest': False}, {'oversized': True}])
def test_invalid_assets_never_enter_cache(tmp_path, monkeypatch, kwargs):
    fixture_asset(monkeypatch, **kwargs)
    with pytest.raises(ValueError):
        downloads.asset('gh', tmp_path, 'tauri-apps/binary-releases', 'test-v1', 'tool.zip')
    assert not list(tmp_path.rglob('tool.zip'))


@pytest.mark.parametrize('repo,tag,name', [
    ('untrusted/repo', 'v1', 'tool.zip'),
    ('tauri-apps/binary-releases', '../v1', 'tool.zip'),
    ('tauri-apps/binary-releases', 'v1', '../tool.zip'),
    ('tauri-apps/binary-releases', '--help', 'tool.zip'),
])
def test_untrusted_download_paths_never_reach_gh(tmp_path, monkeypatch, repo, tag, name):
    monkeypatch.setattr(downloads.subprocess, 'check_output', lambda *a, **k: pytest.fail('Untrusted request reached gh'))
    with pytest.raises(ValueError):
        downloads.asset('gh', tmp_path, repo, tag, name)


def test_gateway_is_private_and_stops_after_build(monkeypatch):
    monkeypatch.setattr(downloads.shutil, 'which', lambda *a: 'gh')
    def asset(*args):
        target = args[1] / 'verified.zip'
        target.write_bytes(b'checked tool')
        return target
    monkeypatch.setattr(downloads, 'asset', asset)
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with downloads.tools({'GH_TOKEN': 'private-test-token'}) as env:
        url = env['TAURI_BUNDLER_TOOLS_GITHUB_MIRROR_TEMPLATE'].replace('<owner>', 'tauri-apps').replace('<repo>', 'binary-releases').replace('<version>', 'v1').replace('<asset>', 'tool.zip')
        assert 'private-test-token' not in url
        with client.open(url, timeout=2) as response:
            assert response.read() == b'checked tool'
        with pytest.raises(urllib.error.HTTPError) as err:
            client.open(urllib.request.Request(url, headers={'Host': 'untrusted.example'}), timeout=2)
        assert err.value.code == 403
    with pytest.raises(urllib.error.URLError):
        client.open(url, timeout=2)


def test_normal_source_build_requires_no_github_key(monkeypatch):
    original = {'PATH': 'source-build'}
    with downloads.tools(original) as env:
        assert env == original and 'TAURI_BUNDLER_TOOLS_GITHUB_MIRROR_TEMPLATE' not in env
