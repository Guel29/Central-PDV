"""Integration against the compiled net48 Agent. No physical input/capture is claimed."""
import asyncio
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from aiohttp import ClientSession, Fingerprint
from smartpdv.storage import atomic_json, protect
from test_system import TOKEN, prepare, start, state, local_session

async def scenario(executable):
    with tempfile.TemporaryDirectory(prefix='smartpdv-legacy-') as folder:
        root=Path(folder)
        central_dir=root/'central'
        central_dir.mkdir()
        fingerprint=prepare(central_dir)
        central,runner,port=await start(central_dir)
        processes=[]
        try:
            agent_dir=root/'agent'
            config={'number':1,'computer_id':'test-device','central':'127.0.0.1','port':port,
                    'fingerprint':fingerprint,'token':protect(TOKEN),'f11':True}
            atomic_json(agent_dir/'agent.json',config)
            pin=Fingerprint(bytes.fromhex(fingerprint))
            url=f'https://127.0.0.1:{port}'
            async with ClientSession() as client:
                headers=await local_session(client,url,pin)
                async with client.ws_connect(url+'/dashboard',ssl=pin,headers=headers) as dashboard:
                    p=subprocess.Popen([executable,'--network-probe','--data',str(agent_dir)],stdin=subprocess.DEVNULL)
                    processes.append(p)
                    await state(dashboard,lambda s:s['online'] and s['pending'])
                    await dashboard.send_json({'type':'start','number':1})
                    await state(dashboard,lambda s:s['active'])
                    await dashboard.send_json({'type':'input','number':1,'event':{'kind':'key','key':'Enter','action':'down'}})
                    await dashboard.send_json({'type':'end','number':1,'result':'Liberado'})
                    code=await asyncio.wait_for(asyncio.to_thread(p.wait),15)
                    assert code==0, list(agent_dir.glob('*error*'))
                    assert json.loads((agent_dir/'network-probe.json').read_text())==dict(tls=True,started=True,input=True,ended=True)
                    await state(dashboard,lambda s:not s['online'])
            # A wrong certificate must be rejected, without changing Central settings.
            bad=root/'wrong-pin'
            atomic_json(bad/'agent.json',{**config,'fingerprint':'00'*32})
            p=subprocess.Popen([executable,'--network-probe','--data',str(bad)],stdin=subprocess.DEVNULL)
            processes.append(p)
            assert await asyncio.wait_for(asyncio.to_thread(p.wait),15)==1
            assert not (bad/'network-probe.json').exists()
            assert not central.state[1]['online']
            print('PASS net48 Agent: pinned TLS, pairing, call, session, input transport, end, rejection of wrong certificate')
        finally:
            for p in processes:
                if p.poll() is None: p.kill(); p.wait()
            await runner.cleanup()

if __name__=='__main__':
    asyncio.run(scenario(str(Path(sys.argv[1]).resolve())))
