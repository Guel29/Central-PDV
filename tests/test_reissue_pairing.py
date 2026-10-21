import asyncio
import copy

from aiohttp import ClientSession, ClientResponseError, Fingerprint
import pytest

from smartpdv import __main__ as cli
from smartpdv.security import token_hash
from smartpdv.storage import atomic_json, load_json, unprotect
from test_system import TOKEN, prepare, start


def configured(tmp_path, monkeypatch):
    pin=prepare(tmp_path)
    original=load_json(tmp_path/'central.json')
    original['pdvs'].append({'number':2,'computer_id':'second-test-device','token_hash':token_hash('other-test-credential')})
    atomic_json(tmp_path/'central.json',original)
    monkeypatch.setattr(cli,'ask',lambda *args:'1')
    return pin,original


def test_reissue_deleted_pairing_keeps_identity_settings_and_other_pdvs(tmp_path,monkeypatch,capsys):
    pin,original=configured(tmp_path,monkeypatch)
    export=cli.reissue_pairing(tmp_path)
    pair=load_json(export);current=load_json(tmp_path/'central.json')
    expected=copy.deepcopy(original)
    expected['pdvs'][0]['token_hash']=token_hash(pair['token'])
    assert current==expected
    assert pair['computer_id']==original['pdvs'][0]['computer_id']
    assert pair['fingerprint']==pin and pair['central']==original['hostname']
    assert pair['token']!=TOKEN
    assert pair['token'] not in (tmp_path/'central.json').read_text()
    assert pair['token'] not in capsys.readouterr().out
    # The unchanged legacy setup format can import this newly issued pairing.
    answers=iter([str(export),'',''])
    monkeypatch.setattr(cli,'ask',lambda *args:next(answers))
    cli.setup_agent(tmp_path/'agent')
    agent=load_json(tmp_path/'agent'/'agent.json')
    assert unprotect(agent['token'])==pair['token']
    assert agent['computer_id']==pair['computer_id']


def test_reissue_failure_does_not_revoke_existing_agent(tmp_path,monkeypatch):
    _,original=configured(tmp_path,monkeypatch)
    real=cli.atomic_json
    def failed_write(path,value):
        if path.name=='central.json': raise OSError('test storage failure')
        real(path,value)
    monkeypatch.setattr(cli,'atomic_json',failed_write)
    with pytest.raises(OSError): cli.reissue_pairing(tmp_path)
    assert load_json(tmp_path/'central.json')==original
    assert not (tmp_path/'pairing'/'pdv-1.json').exists()


def test_reissue_rejects_unknown_pdv_without_writing(tmp_path,monkeypatch):
    _,original=configured(tmp_path,monkeypatch)
    monkeypatch.setattr(cli,'ask',lambda *args:'99')
    with pytest.raises(SystemExit,match='não cadastrado'): cli.reissue_pairing(tmp_path)
    assert load_json(tmp_path/'central.json')==original
    assert not (tmp_path/'pairing').exists()


def test_reissue_rejects_running_central_without_writing(tmp_path,monkeypatch):
    configured(tmp_path,monkeypatch)
    async def scenario():
        central,runner,port=await start(tmp_path)
        config=load_json(tmp_path/'central.json');config['port']=port
        atomic_json(tmp_path/'central.json',config)
        try:
            with pytest.raises(SystemExit,match='Feche a Central'): cli.reissue_pairing(tmp_path)
            assert load_json(tmp_path/'central.json')==config
            assert not (tmp_path/'pairing').exists()
        finally: await runner.cleanup()
    asyncio.run(scenario())


def test_reissued_token_rejects_old_agent_and_accepts_new_over_tls(tmp_path,monkeypatch):
    pin,_=configured(tmp_path,monkeypatch)
    export=cli.reissue_pairing(tmp_path)
    pair=load_json(export)
    async def scenario():
        central,runner,port=await start(tmp_path)
        try:
            async with ClientSession() as client:
                url=f'https://127.0.0.1:{port}/agent';ssl=Fingerprint(bytes.fromhex(pin))
                with pytest.raises(ClientResponseError) as failure:
                    await client.ws_connect(url,ssl=ssl,headers={'X-Computer-ID':pair['computer_id'],'Authorization':'Bearer '+TOKEN})
                assert failure.value.status==401
                agent=await client.ws_connect(url,ssl=ssl,headers={'X-Computer-ID':pair['computer_id'],'Authorization':'Bearer '+pair['token']})
                assert central.state[1]['online']
                await agent.close()
        finally: await runner.cleanup()
    asyncio.run(scenario())
