import asyncio
import base64
import datetime as dt
import io
import json
from pathlib import Path
import ssl
import time

from aiohttp import ClientSession, ClientResponseError, Fingerprint, ServerFingerprintMismatch, web
from PIL import Image
import pytest
from smartpdv.central import Central
from smartpdv.agent import Agent, lan_address
from smartpdv.security import create_certificate, password_hash, tls_context, token_hash
from smartpdv.storage import atomic_json, load_json, protect, unprotect

PASSWORD = 'test-only-long-password'
TOKEN = 'test-only-agent-credential'


def prepare(path):
    fingerprint = create_certificate(path, '127.0.0.1')
    atomic_json(path / 'central.json', {'host':'127.0.0.1','port':0,'hostname':'127.0.0.1',
        'fingerprint':fingerprint,'pdvs':[{'number':1,'computer_id':'test-device','token_hash':token_hash(TOKEN)}],
        'supervisors':[{'name':'supervisor','password_hash':password_hash(PASSWORD),'control':True},
                       {'name':'viewer','password_hash':password_hash(PASSWORD),'control':False}],
        'alarm':{'enabled':True,'repeat_seconds':10},'dashboard':{'columns':4},
        'logs':{'retention_days':7,'max_bytes':1}})
    return fingerprint


async def start(path, port=0):
    central = Central(path)
    runner = web.AppRunner(central.app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', port, ssl_context=tls_context(path))
    await site.start()
    return central, runner, site._server.sockets[0].getsockname()[1]


async def state(ws, predicate):
    async def receive():
        while True:
            data = await ws.receive_json()
            if data['type'] == 'state' and predicate(data['pdvs'][0]):
                return data['pdvs'][0]
    return await asyncio.wait_for(receive(), 5)


async def login(client, url, fingerprint, name='supervisor'):
    response = await client.post(url+'/login', ssl=fingerprint, headers={'Origin':url},
                                 json={'name':name,'password':PASSWORD})
    assert response.status == 200
    return {'Origin':url, 'Cookie':'session='+response.cookies['session'].value}


def test_tls_auth_and_full_workflow(tmp_path):
    async def scenario():
        pin = Fingerprint(bytes.fromhex(prepare(tmp_path)))
        central, runner, port = await start(tmp_path)
        url=f'https://127.0.0.1:{port}'
        try:
            async with ClientSession() as client:
                assert (await client.get(url+'/health',ssl=pin)).status == 200
                for path in ('/','/app.js','/style.css'):
                    r=await client.get(url+path,ssl=pin)
                    assert r.status == 200 and len(await r.read()) > 100
                with pytest.raises(ClientResponseError):
                    await client.ws_connect(url+'/agent',ssl=pin)
                with pytest.raises(ServerFingerprintMismatch):
                    await client.get(url+'/health',ssl=Fingerprint(b'0'*32))
                headers=await login(client,url,pin)
                with pytest.raises(ClientResponseError):
                    await client.ws_connect(url+'/dashboard',ssl=pin,headers={**headers,'Origin':'https://evil.invalid'})
                dashboard=await client.ws_connect(url+'/dashboard',ssl=pin,headers=headers)
                await state(dashboard,lambda s:not s['online'])
                agent=await client.ws_connect(url+'/agent',ssl=pin,headers={'X-Computer-ID':'test-device','Authorization':'Bearer '+TOKEN})
                await state(dashboard,lambda s:s['online'])
                await agent.send_json({'type':'request'})
                await state(dashboard,lambda s:s['pending'])
                await dashboard.send_json({'type':'input','number':1,'event':{'kind':'key','key':'Enter','action':'down'}})
                await dashboard.send_json({'type':'start','number':1})
                assert await agent.receive_json() == {'type':'session','active':True}
                await state(dashboard,lambda s:s['active'] and not s['pending'])
                event={'kind':'mouse','action':'move','x':.5,'y':.4,'button':0}
                await dashboard.send_json({'type':'input','number':1,'event':event})
                assert await agent.receive_json() == {'type':'input','event':event}
                await dashboard.send_json({'type':'end','number':1,'result':'Liberado'})
                assert await agent.receive_json() == {'type':'session','active':False}
                await state(dashboard,lambda s:not s['active'] and not s['pending'])
                await agent.close()
                await state(dashboard,lambda s:not s['online'])
                logs=list((tmp_path/'logs').glob('*.jsonl'))
                entry=json.loads(logs[0].read_text())
                assert entry['result']=='Liberado'
                assert set(entry)=={'pdv','requested_at','supervisor','attended_at','result'}
                await dashboard.close()
        finally:
            await runner.cleanup()
    asyncio.run(scenario())


def test_permissions_and_session_ownership(tmp_path):
    async def scenario():
        pin=Fingerprint(bytes.fromhex(prepare(tmp_path)))
        central,runner,port=await start(tmp_path)
        url=f'https://127.0.0.1:{port}'
        try:
            async with ClientSession() as client:
                agent=await client.ws_connect(url+'/agent',ssl=pin,headers={'X-Computer-ID':'test-device','Authorization':'Bearer '+TOKEN})
                viewer=await client.ws_connect(url+'/dashboard',ssl=pin,headers=await login(client,url,pin,'viewer'))
                await state(viewer,lambda s:s['online'])
                await viewer.send_json({'type':'start','number':1})
                await asyncio.sleep(.1)
                assert not central.state[1]['active']
                owner=await client.ws_connect(url+'/dashboard',ssl=pin,headers=await login(client,url,pin))
                await state(owner,lambda s:s['online'])
                await owner.send_json({'type':'start','number':1})
                assert (await agent.receive_json())['active']
                await owner.close()
                assert not (await agent.receive_json())['active']
                await viewer.close()
                await agent.close()
        finally:
            await runner.cleanup()
    asyncio.run(scenario())


class FakeDesktop:
    def __init__(self):
        self.request=False
        self.closed=False
        self.events=[]
    def requested(self):
        result=self.request
        self.request=False
        return result
    def capture(self, active):
        output=io.BytesIO()
        Image.new('RGB',(16,9),'yellow').save(output,'JPEG')
        return output.getvalue()
    def input(self,event):
        self.events.append(event)
    def release(self):
        pass
    def close(self):
        self.closed=True


async def until(predicate):
    for _ in range(150):
        if predicate():
            return
        await asyncio.sleep(.05)
    raise AssertionError('Timed out waiting for expected state')


def test_agent_reconnect_after_central_restart(tmp_path):
    async def scenario():
        pin=prepare(tmp_path)
        central,runner,port=await start(tmp_path)
        atomic_json(tmp_path/'agent.json',{'number':1,'computer_id':'test-device','central':'127.0.0.1',
                    'port':port,'fingerprint':pin,'token':protect(TOKEN),'f11':True})
        desktop=FakeDesktop()
        agent=Agent(tmp_path/'agent.json',desktop)
        task=asyncio.create_task(agent.run())
        try:
            await until(lambda: central.state[1]['thumbnail'] is not None)
            desktop.request=True
            await until(lambda: central.state[1]['pending'])
            # Stop the same live service and restore it with the same TLS identity.
            await central.agents[1].close()
            await runner.cleanup()
            central,runner,_=await start(tmp_path,port)
            await until(lambda: central.state[1]['online'] and central.state[1]['pending'])
            assert not central.state[1]['active']
        finally:
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)
            await runner.cleanup()
        assert desktop.closed
    asyncio.run(scenario())


def test_storage_atomic_and_credentials(tmp_path):
    path=tmp_path/'config.json'
    atomic_json(path,{'version':1})
    with pytest.raises(TypeError):
        atomic_json(path,{'bad':object()})
    assert load_json(path)=={'version':1}
    assert not list(tmp_path.glob('.pending-*'))
    assert unprotect(protect('test-only'))=='test-only'


def test_log_rotation_retention(tmp_path):
    prepare(tmp_path)
    central=Central(tmp_path)
    logs=tmp_path/'logs'
    logs.mkdir()
    old=logs/'2000-01-01-000.jsonl'
    old.write_text('{}\n')
    central.log({'pdv':1})
    central.log({'pdv':2})
    assert not old.exists()
    assert len(list(logs.glob('*.jsonl')))==2


@pytest.mark.parametrize('event',[
    {'kind':'mouse','action':'move','x':-1,'y':.5},
    {'kind':'mouse','action':'move','x':float('nan'),'y':.5},
    {'kind':'key','action':'execute','key':'Enter'},
    {'kind':'key','action':'down','key':'x'*500},None])
def test_input_validation(event):
    assert not Central.valid_input(event)


def test_public_destination_rejected():
    with pytest.raises(ValueError):
        lan_address('8.8.8.8')


def test_duplicate_agent_and_session_expiration(tmp_path):
    async def scenario():
        pin=Fingerprint(bytes.fromhex(prepare(tmp_path)))
        central,runner,port=await start(tmp_path)
        url=f'https://127.0.0.1:{port}'
        try:
            async with ClientSession() as client:
                identity={'X-Computer-ID':'test-device','Authorization':'Bearer '+TOKEN}
                agent=await client.ws_connect(url+'/agent',ssl=pin,headers=identity)
                with pytest.raises(ClientResponseError) as failure:
                    await client.ws_connect(url+'/agent',ssl=pin,headers=identity)
                assert failure.value.status==409
                headers=await login(client,url,pin)
                dashboard=await client.ws_connect(url+'/dashboard',ssl=pin,headers=headers)
                await state(dashboard,lambda s:s['online'])
                await dashboard.send_json({'type':'start','number':1})
                assert (await agent.receive_json())['active']
                await state(dashboard,lambda s:s['active'])
                token=headers['Cookie'].split('=',1)[1]
                central.sessions[token]['expires']=0
                await central.publish()
                assert (await agent.receive_json())=={'type':'session','active':False}
                assert not central.state[1]['active']
                await dashboard.close()
                await agent.close()
        finally:
            await runner.cleanup()
    asyncio.run(scenario())


def test_initial_setup_and_pairing(tmp_path, monkeypatch):
    from smartpdv import __main__ as cli
    from smartpdv.security import verify_password
    central_dir=tmp_path/'central'
    answers=iter(['127.0.0.1','admin',PASSWORD])
    monkeypatch.setattr(cli,'ask',lambda *args:next(answers))
    cli.setup_central(central_dir)
    config=load_json(central_dir/'central.json')
    assert verify_password(PASSWORD,config['supervisors'][0]['password_hash'])
    monkeypatch.setattr(cli,'ask',lambda *args:'4')
    cli.add_pdv(central_dir)
    config=load_json(central_dir/'central.json')
    pairing_path=central_dir/'pairing'/'pdv-4.json'
    pairing=load_json(pairing_path)
    assert token_hash(pairing['token'])==config['pdvs'][0]['token_hash']
    answers=iter([str(pairing_path),'',''])
    monkeypatch.setattr(cli,'ask',lambda *args:next(answers))
    agent_dir=tmp_path/'agent'
    cli.setup_agent(agent_dir)
    agent_config=load_json(agent_dir/'agent.json')
    assert agent_config['computer_id']==config['pdvs'][0]['computer_id']
    assert unprotect(agent_config['token'])==pairing['token']
    assert agent_config['number']==4
    answers=iter(['view-only',PASSWORD,'n'])
    monkeypatch.setattr(cli,'ask',lambda *args:next(answers))
    cli.add_supervisor(central_dir)
    assert load_json(central_dir/'central.json')['supervisors'][1]['control'] is False
    with pytest.raises(SystemExit):
        cli.setup_central(central_dir)
