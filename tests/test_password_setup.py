import pytest
from smartpdv import __main__ as cli
from smartpdv.dev import initialize
from smartpdv.security import verify_password
from smartpdv.storage import load_json, atomic_json


def answers(monkeypatch, values):
    iterator=iter(values)
    monkeypatch.setattr(cli,'ask',lambda *args:next(iterator))


def test_eight_characters_accepted_in_all_setup_flows(tmp_path,monkeypatch):
    password='Abcd1234'  # Credencial exclusiva deste teste.
    development=initialize(tmp_path/'development',password)
    assert verify_password(password,development['supervisors'][0]['password_hash'])
    central_dir=tmp_path/'central'
    answers(monkeypatch,['127.0.0.1','admin',password])
    cli.setup_central(central_dir)
    answers(monkeypatch,['supervisor',password,'s'])
    cli.add_supervisor(central_dir)
    users=load_json(central_dir/'central.json')['supervisors']
    assert len(users)==2
    assert all(verify_password(password,u['password_hash']) for u in users)


def test_seven_characters_rejected_in_all_setup_flows(tmp_path,monkeypatch):
    password='Abcd123'
    with pytest.raises(ValueError,match='8 caracteres'):
        initialize(tmp_path/'development',password)
    central_dir=tmp_path/'central'
    answers(monkeypatch,['127.0.0.1','admin',password])
    with pytest.raises(SystemExit):
        cli.setup_central(central_dir)
    assert not (central_dir/'central.json').exists()
    atomic_json(central_dir/'central.json',{'supervisors':[]})
    answers(monkeypatch,['supervisor',password])
    with pytest.raises(SystemExit):
        cli.add_supervisor(central_dir)
    assert load_json(central_dir/'central.json')['supervisors']==[]
