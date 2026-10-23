"""Source preparation integrity, not driver or USB integration tests."""
import importlib.util
import io
from pathlib import Path
import tarfile
import pytest

spec = importlib.util.spec_from_file_location('usb_source_prepare',
    Path(__file__).resolve().parents[1]/'tools/usb-win7/prepare.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


def fake_git(monkeypatch, *, head=None, member='driver/source.c'):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as tar:
        info = tarfile.TarInfo(member)
        data = b'committed source, not local working tree'
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    def git(*args):
        if 'rev-parse' in args:
            return (head or prepare.COMMIT).encode()+b'\n'
        assert args[-3:] == ('archive','--format=tar',prepare.COMMIT)
        return stream.getvalue()
    monkeypatch.setattr(prepare, 'git', git)


def test_pins_windows7_revision_and_hashes_export(monkeypatch, tmp_path):
    assert prepare.COMMIT == '44063583a5c3e20ec459bddadc9aae37f73bda10'
    fake_git(monkeypatch)
    result = prepare.prepare(tmp_path/'checkout',tmp_path/'out')
    import hashlib
    data = (tmp_path/'out/driver/source.c').read_bytes()
    assert result['sha256'] == {'driver/source.c':hashlib.sha256(data).hexdigest()}
    assert result['status'] == 'SOURCE_ONLY_NOT_SIGNED_NOT_INSTALLABLE'


def test_wrong_revision_is_not_exported(monkeypatch, tmp_path):
    fake_git(monkeypatch, head='0'*40)
    with pytest.raises(ValueError):
        prepare.prepare(tmp_path/'checkout', tmp_path/'out')
    assert not (tmp_path/'out').exists()


def test_existing_output_is_never_overwritten(monkeypatch, tmp_path):
    fake_git(monkeypatch)
    out = tmp_path/'out'
    out.mkdir()
    (out/'user-work').write_text('preserve')
    with pytest.raises(FileExistsError):
        prepare.prepare(tmp_path/'checkout',out)
    assert (out/'user-work').read_text() == 'preserve'


def test_archive_cannot_escape_destination(monkeypatch, tmp_path):
    fake_git(monkeypatch, member='../../escape')
    with pytest.raises(tarfile.FilterError):
        prepare.prepare(tmp_path/'checkout',tmp_path/'out')
    assert not (tmp_path/'escape').exists()
    assert not (tmp_path/'out').exists()
