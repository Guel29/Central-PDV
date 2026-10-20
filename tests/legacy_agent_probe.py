"""Integration against the compiled net48 Agent. No physical input/capture is claimed."""
import asyncio
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from aiohttp import ClientSession, Fingerprint
from smartpdv.storage import atomic_json, protect
from test_system import TOKEN, prepare, start, local_session

async def state(ws,predicate):
    async def receive():
        while True:
            data=await ws.receive_json()
            if data["type"]=="state" and predicate(data["pdvs"][0]): return
    await asyncio.wait_for(receive(),20)

async def scenario(executable):
    with tempfile.TemporaryDirectory(prefix='smartpdv-legacy-') as folder:
        root=Path(folder)
        central_dir=root/'central'
        central_dir.mkdir()
        fingerprint=prepare(central_dir)
        central,runner,port=await start(central_dir)
        processes=[]
        phase="startup"
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
                    phase='waiting for Agent request'
                    await state(dashboard,lambda s:s['online'] and s['pending'])
                    await dashboard.send_json({'type':'start','number':1})
                    phase='waiting for active session'
                    await state(dashboard,lambda s:s['active'])
                    await dashboard.send_json({'type':'input','number':1,'event':{'kind':'key','key':'Enter','action':'down'}})
                    await dashboard.send_json({'type':'end','number':1,'result':'Liberado'})
                    phase="waiting for Agent session result"
                    code=await asyncio.wait_for(asyncio.to_thread(p.wait),15)
                    assert code==0, list(agent_dir.glob('*error*'))
                    assert json.loads((agent_dir/'network-probe.json').read_text())==dict(tls=True,started=True,input=True,ended=True)
                    phase='waiting for Agent disconnect'
                    await state(dashboard,lambda s:not s['online'])
            # A wrong certificate must be rejected, without changing Central settings.
            phase='wrong certificate rejection'
            bad=root/'wrong-pin'
            atomic_json(bad/'agent.json',{**config,'fingerprint':'00'*32})
            p=subprocess.Popen([executable,'--network-probe','--data',str(bad)],stdin=subprocess.DEVNULL)
            processes.append(p)
            assert await asyncio.wait_for(asyncio.to_thread(p.wait),15)==1
            assert not (bad/'network-probe.json').exists()
            assert not central.state[1]['online']
            print('PASS net48 Agent: pinned TLS, pairing, call, session, input transport, end, rejection of wrong certificate')
        except Exception as ex:
            errors=[json.loads(f.read_text()) for f in root.glob('*/legacy-startup-error.json')]
            raise RuntimeError(f"Legacy probe phase={phase}; exception={type(ex).__name__}; startup={errors}; state={[(s['online'],s['pending'],s['active']) for s in central.state.values()]}") from ex
        finally:
            for p in processes:
                if p.poll() is None: p.kill(); p.wait()
            await runner.cleanup()

if __name__=='__main__':
    asyncio.run(scenario(str(Path(sys.argv[1]).resolve())))
