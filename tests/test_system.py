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
from smartpdv.security import create_certificate, tls_context, token_hash
from smartpdv.storage import atomic_json, load_json, protect, unprotect

TOKEN = 'test-only-agent-credential'


def prepare(path):
    fingerprint = create_certificate(path, '127.0.0.1')
    atomic_json(path / 'central.json', {'host':'127.0.0.1','port':0,'hostname':'127.0.0.1',
        'fingerprint':fingerprint,'pdvs':[{'number':1,'computer_id':'test-device','token_hash':token_hash(TOKEN)}],
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


async def local_session(client, url, fingerprint):
    response = await client.get(url+'/session',ssl=fingerprint)
    assert response.status == 200
    assert (await response.json())['direct_access']
    return {'Origin':url, 'Cookie':'session='+response.cookies['session'].value}


async def message_type(ws, expected):
    async def receive():
        while True:
            message = await ws.receive_json()
            if message['type'] == expected:
                return message
    return await asyncio.wait_for(receive(), 5)


def test_central_authorizes_direct_keyboard_and_mouse(tmp_path):
    async def scenario():
        pin=Fingerprint(bytes.fromhex(prepare(tmp_path)))
        # An earlier configuration can still contain the removed scanner flag.
        previous=load_json(tmp_path/'central.json')
        previous['peripherals']={'keyboard':True,'scanner':False,'mouse':True}
        atomic_json(tmp_path/'central.json',previous)
        central,runner,port=await start(tmp_path)
        assert central.config['peripherals']=={'keyboard':True,'mouse':True}
        url=f'https://127.0.0.1:{port}'
        try:
            async with ClientSession() as client:
                agent=await client.ws_connect(url+'/agent',ssl=pin,headers={'X-Computer-ID':'test-device','Authorization':'Bearer '+TOKEN})
                dashboard=await client.ws_connect(url+'/dashboard',ssl=pin,headers=await local_session(client,url,pin))
                await state(dashboard,lambda s:s['online'])
                await agent.send_json({'type':'request'})
                await state(dashboard,lambda s:s['pending'])
                await dashboard.send_json({'type':'start','number':1})
                assert (await agent.receive_json())=={'type':'session','active':True}
                await state(dashboard,lambda s:s['active'])
                down={'kind':'key','key':'Control','action':'down','code':'ControlLeft'}
                await dashboard.send_json({'type':'input','number':1,'event':down})
                assert (await agent.receive_json())['event']==down
                permissions={'keyboard':False,'mouse':False}
                await dashboard.send_json({'type':'peripherals','settings':permissions})
                assert (await agent.receive_json())=={'type':'input','event':{'kind':'release'}}
                await message_type(dashboard,'peripherals_saved')
                config=load_json(tmp_path/'central.json')
                assert config['peripherals']==permissions
                assert config['pdvs']==central.config['pdvs']
                assert Central(tmp_path).config['peripherals']==permissions
                # Removed barcode commands cannot bypass the keyboard permission.
                await dashboard.send_json({'type':'barcode','number':1,'code':'0012345678901'})
                await message_type(dashboard,'error')
                for event in (down,{'kind':'mouse','action':'down','x':.5,'y':.5,'button':0},{'kind':'wheel','delta':120}):
                    await dashboard.send_json({'type':'input','number':1,'event':event})
                await dashboard.send_json({'type':'input','number':1,'event':{'kind':'release'}})
                assert (await agent.receive_json())=={'type':'input','event':{'kind':'release'}}
                permissions={'keyboard':True,'mouse':False}
                await dashboard.send_json({'type':'peripherals','settings':permissions})
                await message_type(dashboard,'peripherals_saved')
                # Scanner-style keystrokes go through the ordinary remote keyboard.
                code='0012345678901'
                for key,physical in zip([*code,'Enter'],[*[f'Numpad{digit}' for digit in code],'NumpadEnter']):
                    for action in ('down','up'):
                        event={'kind':'key','action':action,'key':key,'code':physical}
                        await dashboard.send_json({'type':'input','number':1,'event':event})
                        assert (await agent.receive_json())=={'type':'input','event':event}
                await dashboard.send_json([])
                await message_type(dashboard,'error')
                await dashboard.send_json({'type':'peripherals','settings':{**permissions,'usb_all':True}})
                await message_type(dashboard,'error')
                assert load_json(tmp_path/'central.json')['peripherals']==permissions
                await dashboard.send_json({'type':'end','number':1,'result':'Liberado'})
                assert (await agent.receive_json())=={'type':'session','active':False}
                await state(dashboard,lambda s:not s['active'])
                assert code not in (tmp_path/'central.json').read_text()
                for log in (tmp_path/'logs').glob('*.jsonl'):
                    assert code not in log.read_text()
                await dashboard.close()
                await agent.close()
        finally:
            await runner.cleanup()
    asyncio.run(scenario())


@pytest.mark.parametrize('capable',[False,True])
def test_timed_sequence_requires_capability_owner_and_keyboard_permission(tmp_path,capable):
    from test_timed_keys import sequence
    async def scenario():
        pin=Fingerprint(bytes.fromhex(prepare(tmp_path)))
        central,runner,port=await start(tmp_path);url=f'https://127.0.0.1:{port}'
        burst=sequence()
        try:
            async with ClientSession() as client:
                headers={'X-Computer-ID':'test-device','Authorization':'Bearer '+TOKEN}
                if capable: headers['X-SmartPDV-Timed-Keys']='numeric-v1'
                agent=await client.ws_connect(url+'/agent',ssl=pin,headers=headers)
                owner=await client.ws_connect(url+'/dashboard',ssl=pin,headers=await local_session(client,url,pin))
                other=await client.ws_connect(url+'/dashboard',ssl=pin,headers=await local_session(client,url,pin))
                await state(owner,lambda s:s['online'])
                assert central.state[1]['timed_keys'] is capable
                await owner.send_json({'type':'start','number':1})
                assert (await agent.receive_json())=={'type':'session','active':True}
                await state(owner,lambda s:s['active'])
                await owner.send_json({'type':'input','number':1,'event':burst})
                await owner.send_json({'type':'input','number':1,'event':{'kind':'release'}})
                if capable: assert (await agent.receive_json())=={'type':'input','event':burst}
                assert (await agent.receive_json())['event']=={'kind':'release'}
                # A second console session cannot inject into another owner's PDV.
                await other.send_json({'type':'input','number':1,'event':burst})
                await other.send_json({'type':'peripherals','settings':{'keyboard':False,'mouse':True}})
                assert (await agent.receive_json())['event']=={'kind':'release'}
                await message_type(other,'peripherals_saved')
                await owner.send_json({'type':'input','number':1,'event':burst})
                await owner.send_json({'type':'input','number':1,'event':{'kind':'release'}})
                assert (await agent.receive_json())['event']=={'kind':'release'}
                await owner.send_json({'type':'end','number':1})
                assert (await agent.receive_json())=={'type':'session','active':False}
                await owner.close();await other.close();await agent.close()
                assert central.state[1]['timed_keys'] is False
                for path in tmp_path.rglob('*'):
                    if path.is_file() and path.suffix in ('.json','.jsonl'):
                        assert '001234567890' not in path.read_text()
        finally: await runner.cleanup()
    asyncio.run(scenario())


def test_authorization_save_failure_keeps_previous_settings(tmp_path,monkeypatch):
    def failed_write(*args):
        raise OSError('storage unavailable')
    async def scenario():
        pin=Fingerprint(bytes.fromhex(prepare(tmp_path)))
        central,runner,port=await start(tmp_path)
        url=f'https://127.0.0.1:{port}'
        monkeypatch.setattr('smartpdv.central.atomic_json',failed_write)
        try:
            async with ClientSession() as client:
                dashboard=await client.ws_connect(url+'/dashboard',ssl=pin,headers=await local_session(client,url,pin))
                await dashboard.send_json({'type':'peripherals','settings':{'keyboard':False,'mouse':False}})
                assert 'anteriores' in (await message_type(dashboard,'error'))['message']
                assert central.config['peripherals']=={'keyboard':True,'mouse':True}
                assert 'peripherals' not in load_json(tmp_path/'central.json')
                await dashboard.close()
        finally:
            await runner.cleanup()
    asyncio.run(scenario())


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
                headers=await local_session(client,url,pin)
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
                await agent.send_json({'type':'input_status','accepted':False,'error_code':5})
                assert await dashboard.receive_json() == {'type':'input_status','number':1,'accepted':False,'error_code':5}
                await agent.send_json({'type':'input_status','accepted':'untrusted','error_code':5})
                await agent.send_json({'type':'input_status','accepted':True,'error_code':0})
                assert await dashboard.receive_json() == {'type':'input_status','number':1,'accepted':True,'error_code':0}
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
                owner=await client.ws_connect(url+'/dashboard',ssl=pin,headers=await local_session(client,url,pin))
                await state(owner,lambda s:s['online'])
                await owner.send_json({'type':'start','number':1})
                assert (await agent.receive_json())['active']
                expected_owner=central.state[1]['owner']
                observer=await client.ws_connect(url+'/dashboard',ssl=pin,headers=await local_session(client,url,pin))
                await state(observer,lambda s:s['active'])
                await observer.send_json({'type':'start','number':1})
                while (await observer.receive_json())['type'] != 'error':
                    pass
                assert central.state[1]['owner']==expected_owner
                await observer.send_json({'type':'barcode','number':1,'code':'0012345678901'})
                await message_type(observer,'error')
                await owner.send_json({'type':'input','number':1,'event':{'kind':'release'}})
                assert (await agent.receive_json())=={'type':'input','event':{'kind':'release'}}
                await owner.close()
                assert not (await agent.receive_json())['active']
                await observer.close()
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
            from smartpdv.version import VERSION
            assert central.state[1]['agent_version']==VERSION
            assert central.state[1]['keyboard_protocol'] is None  # FakeDesktop is not native Windows.
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
    {'kind':'key','action':'down','key':'x'*500},
    {'kind':'key','action':'down','key':'1','code':[]},
    {'kind':'key','action':'down','key':'1','code':'Numpad1\n'},None])
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
                headers=await local_session(client,url,pin)
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
    central_dir=tmp_path/'central'
    answers=iter(['127.0.0.1'])
    monkeypatch.setattr(cli,'ask',lambda *args:next(answers))
    cli.setup_central(central_dir)
    config=load_json(central_dir/'central.json')
    assert 'supervisors' not in config
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
    with pytest.raises(SystemExit):
        cli.setup_central(central_dir)


def test_input_rejection_report_keeps_remote_session_connected(tmp_path):
    class RejectingDesktop(FakeDesktop):
        def input(self,event):
            raise OSError(5, 'Test-only access denied')
    async def scenario():
        fingerprint=prepare(tmp_path)
        central,runner,port=await start(tmp_path)
        atomic_json(tmp_path/'agent.json',{'number':1,'computer_id':'test-device','central':'127.0.0.1',
                    'port':port,'fingerprint':fingerprint,'token':protect(TOKEN),'f11':False})
        agent=Agent(tmp_path/'agent.json',RejectingDesktop())
        task=asyncio.create_task(agent.run())
        try:
            await until(lambda: central.state[1]['online'])
            async with ClientSession() as client:
                url=f'https://127.0.0.1:{port}'
                pin=Fingerprint(bytes.fromhex(fingerprint))
                headers=await local_session(client,url,pin)
                async with client.ws_connect(url+'/dashboard',ssl=pin,headers=headers) as dashboard:
                    await dashboard.send_json({'type':'start','number':1})
                    await state(dashboard,lambda s:s['active'])
                    await dashboard.send_json({'type':'input','number':1,'event':{'kind':'key','key':'1','action':'down'}})
                    async def report():
                        while True:
                            data=await dashboard.receive_json()
                            if data['type']=='input_status': return data
                    assert await asyncio.wait_for(report(),5)=={'type':'input_status','number':1,'accepted':False,'error_code':5}
                    assert central.state[1]['online'] and central.state[1]['active']
                    await dashboard.send_json({'type':'end','number':1})
                    await state(dashboard,lambda s:not s['active'])
                    assert central.state[1]['online']
        finally:
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)
            await runner.cleanup()
    asyncio.run(scenario())


def test_agent_version_clears_on_reconnect_and_invalid_report(tmp_path):
    async def scenario():
        pin=Fingerprint(bytes.fromhex(prepare(tmp_path)))
        central,runner,port=await start(tmp_path)
        url=f'https://127.0.0.1:{port}'
        identity={'X-Computer-ID':'test-device','Authorization':'Bearer '+TOKEN}
        try:
            async with ClientSession() as client:
                dashboard=await client.ws_connect(url+'/dashboard',ssl=pin,headers=await local_session(client,url,pin))
                for headers,version,protocol in (
                    ({'X-SmartPDV-Version':'0.1.6','X-SmartPDV-Keyboard':'scan-code-v1'},'0.1.6','scan-code-v1'),
                    ({},None,None),
                    ({'X-SmartPDV-Version':'<script>1.2.3</script>','X-SmartPDV-Keyboard':'arbitrary'},None,None)):
                    agent=await client.ws_connect(url+'/agent',ssl=pin,headers={**identity,**headers})
                    report=await state(dashboard,lambda s:s['online'])
                    assert report['agent_version']==version
                    assert report['keyboard_protocol']==protocol
                    assert 'X-Computer-ID' not in report and 'token' not in report
                    await agent.close()
                    report=await state(dashboard,lambda s:not s['online'])
                    assert report['agent_version'] is None
                    assert report['keyboard_protocol'] is None
                await dashboard.close()
        finally:
            await runner.cleanup()
    asyncio.run(scenario())
