"""Regressões do contrato com icacls; execução nativa também roda no Windows CI."""
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest
from smartpdv import storage


SID = 'S-1-5-21-123-456-789-1001'


def test_resolves_redirected_path_and_grants_before_removing_inheritance(tmp_path, monkeypatch):
    real = tmp_path/'physical-appdata'
    real.mkdir()
    redirected = tmp_path/'virtual-appdata'
    redirected.mkdir()
    original_resolve = Path.resolve
    physical = real.resolve()
    def resolve(path, *args, **kwargs):
        return physical if path == redirected else original_resolve(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'resolve', resolve)
    calls=[]
    def run(command, **kwargs):
        calls.append(command)
        assert kwargs['check'] and kwargs['capture_output']
        return SimpleNamespace(stdout=f'"DOMAIN\\user","{SID}"\n', stderr='')
    monkeypatch.setattr(storage.subprocess,'run',run)
    # Substituir somente a referência de os neste módulo, sem alterar pathlib.
    monkeypatch.setattr(storage,'os',SimpleNamespace(name='nt'))
    result=storage.secure_directory(redirected)
    assert result==real.resolve()
    assert calls==[
        ['whoami','/user','/fo','csv','/nh'],
        ['icacls',str(real.resolve()),'/grant:r',f'*{SID}:(OI)(CI)F'],
        ['icacls',str(real.resolve()),'/grant:r','*S-1-5-18:(OI)(CI)F'],
        ['icacls',str(real.resolve()),'/inheritance:r'],
    ]


def test_acl_failure_is_actionable_and_does_not_remove_inheritance(tmp_path, monkeypatch):
    calls=[]
    def run(command, **kwargs):
        calls.append(command)
        if command[0]=='whoami':
            return SimpleNamespace(stdout=f'"user","{SID}"\n')
        raise subprocess.CalledProcessError(3,command,stderr='Path not found')
    monkeypatch.setattr(storage.subprocess,'run',run)
    with pytest.raises(RuntimeError,match='icacls retornou 3: Path not found'):
        storage._secure_windows_directory(tmp_path)
    assert len(calls)==2
    assert all('/inheritance:r' not in c for c in calls)


@pytest.mark.parametrize('output',['','"user","not-a-sid"','"user","S-1-5-18"\n"other","S-1-5-19"'])
def test_invalid_identity_never_changes_acl(output, tmp_path, monkeypatch):
    calls=[]
    def run(command,**kwargs):
        calls.append(command)
        return SimpleNamespace(stdout=output)
    monkeypatch.setattr(storage.subprocess,'run',run)
    with pytest.raises(RuntimeError,match='SID'):
        storage._secure_windows_directory(tmp_path)
    assert len(calls)==1


@pytest.mark.skipif(storage.os.name!='nt',reason='Exige Windows e icacls reais')
def test_native_windows_acl_and_dpapi(tmp_path):
    path=storage.secure_directory(tmp_path/'native')
    storage.atomic_json(path/'config.json',{'token':storage.protect('test-only')})
    assert storage.unprotect(storage.load_json(path/'config.json')['token'])=='test-only'
