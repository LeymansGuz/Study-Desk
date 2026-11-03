import hashlib
import json
import pytest
from desktop.collect_release import PLATFORMS, check_tag, collect


@pytest.fixture
def builds(tmp_path):
    source=tmp_path/'builds'
    for name,(system,architectures,suffixes) in PLATFORMS.items():
        folder=source/name
        folder.mkdir(parents=True)
        checks=[]
        for suffix in sorted(suffixes):
            payload={'.exe':b'MZ', '.deb':b'!<arch>\n', '.AppImage':b'\x7fELF', '.dmg':b'koly'}[suffix]+b'\0'*508
            asset=folder/('Study Desk-'+name+'-0.2.2'+suffix)
            asset.write_bytes(payload)
            checks.append(hashlib.sha256(payload).hexdigest()+'  '+asset.name)
        (folder/'SHA256SUMS.txt').write_text('\n'.join(checks),encoding='utf-8')
        (folder/('build-manifest-'+name+'.json')).write_text(json.dumps(dict(
            version='0.2.2',source_revision='same-commit',platform=system,architecture=sorted(architectures)[0])),encoding='utf-8')
    return source


def test_release_requires_all_four_platforms_before_staging(builds,tmp_path):
    next((builds/'macos-intel').glob('build-manifest*')).unlink()
    destination=tmp_path/'release'
    with pytest.raises(ValueError,match='Missing or duplicate'):collect(builds,destination,'0.2.2','same-commit')
    assert not destination.exists()


def test_release_rejects_builds_from_another_commit(builds,tmp_path):
    path=next((builds/'linux').glob('build-manifest*'))
    data=json.loads(path.read_text());data['source_revision']='older-commit';path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='mismatch'):collect(builds,tmp_path/'release','0.2.2','same-commit')


def test_release_rejects_corrupt_installer_bytes(builds,tmp_path):
    next((builds/'windows').glob('*.exe')).write_bytes(b'corrupted')
    with pytest.raises(ValueError,match='corrupted'):collect(builds,tmp_path/'release','0.2.2','same-commit')


def test_complete_release_has_independently_recomputed_checksums(builds,tmp_path):
    destination=tmp_path/'release'
    files=collect(builds,destination,'0.2.2','same-commit')
    assert len(files)==9
    assert all(' ' not in p.name for p in destination.iterdir())
    for line in (destination/'SHA256SUMS.txt').read_text().splitlines():
        digest,name=line.split('  ',1)
        assert digest==hashlib.sha256((destination/name).read_bytes()).hexdigest()
    check_tag('v0.2.2-beta.1','0.2.2')
    with pytest.raises(ValueError):check_tag('v0.2.1','0.2.2')
