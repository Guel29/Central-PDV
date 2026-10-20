import sys

from smartpdv import desktop_entry
from smartpdv.storage import atomic_json


def test_background_does_not_open_setup_when_unconfigured(tmp_path,monkeypatch):
    monkeypatch.setattr(sys,'argv',['SmartPDV-Agent.exe','--background','--data',str(tmp_path)])
    def unexpected():
        raise AssertionError('Background não deve iniciar wizard sem cadastro')
    monkeypatch.setattr(desktop_entry.cli,'main',unexpected)
    desktop_entry.launch('agent')
    assert not (tmp_path/'agent.json').exists()


def test_background_runs_configured_agent_without_extra_cli_flags(tmp_path,monkeypatch):
    atomic_json(tmp_path/'agent.json',{'number':1})
    monkeypatch.setattr(sys,'argv',['SmartPDV-Agent.exe','--background','--data',str(tmp_path)])
    calls=[]
    monkeypatch.setattr(desktop_entry.cli,'main',lambda:calls.append(sys.argv[:]))
    desktop_entry.launch('agent')
    assert calls==[['SmartPDV-Agent.exe','agent','--data',str(tmp_path)]]


def test_manual_first_launch_configures_then_runs(tmp_path,monkeypatch):
    monkeypatch.setattr(sys,'argv',['SmartPDV-Agent.exe','--data',str(tmp_path)])
    calls=[]
    def main():
        calls.append(sys.argv[:])
        if 'setup' in sys.argv:
            atomic_json(tmp_path/'agent.json',{'number':1})
    monkeypatch.setattr(desktop_entry.cli,'main',main)
    desktop_entry.launch('agent')
    assert calls[0][1:3]==['agent','setup']
    assert calls[1][1:]==['agent','--data',str(tmp_path)]
