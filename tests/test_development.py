import asyncio
import io

from aiohttp import ClientSession, Fingerprint, web
from PIL import Image
import pytest
from smartpdv.dev import DevelopmentCentral, SimulatedDesktop, initialize
from smartpdv.security import tls_context
from smartpdv.storage import atomic_json, load_json
from test_system import until


async def laboratory(path):
    config=initialize(path,port=0)
    central=DevelopmentCentral(path)
    runner=web.AppRunner(central.app)
    await runner.setup()
    site=web.TCPSite(runner,'127.0.0.1',0,ssl_context=tls_context(path))
    await site.start()
    port=site._server.sockets[0].getsockname()[1]
    # Agents devem usar a porta real escolhida pelo SO neste teste.
    await central.stop_agents(central.app)
    for number in (1,2):
        agent_path=path/f'agent-{number}'/'agent.json'
        agent_config=load_json(agent_path)
        agent_config['port']=port
        atomic_json(agent_path,agent_config)
        central.launch_agent(number)
    await until(lambda:all(s['online'] for s in central.state.values()))
    return central,runner,port,Fingerprint(bytes.fromhex(config['fingerprint']))


def test_development_controls_and_isolation(tmp_path):
    async def scenario():
        central,runner,port,pin=await laboratory(tmp_path)
        url=f'https://127.0.0.1:{port}'
        try:
            async with ClientSession() as client:
                response=await client.get(url+'/dev/state',ssl=pin)
                assert response.status==401
                response=await client.get(url+'/session',ssl=pin)
                assert response.status==200
                headers={'Origin':url,'Cookie':'session='+response.cookies['session'].value}
                for path in ('/dev/operator','/dev/panel.js','/dev/reload.js','/dev/version','/session'):
                    assert (await client.get(url+path,ssl=pin,headers=headers)).status==200
                assert 'SIMULAÇÃO' in await (await client.get(url+'/',ssl=pin)).text()
                async def action(command,number=1):
                    return await client.post(url+'/dev/action',ssl=pin,headers=headers,json={'number':number,'action':command})
                assert (await action('request')).status==200
                await until(lambda:central.state[1]['pending'])
                assert (await action('disconnect')).status==200
                await until(lambda:not central.state[1]['online'])
                assert central.state[2]['online']
                assert (await action('connect')).status==200
                await until(lambda:central.state[1]['online'])
                assert (await client.post(url+'/dev/action',ssl=pin,headers={**headers,'Origin':'https://evil.invalid'},json={'number':1,'action':'request'})).status==403
        finally:
            await runner.cleanup()
    asyncio.run(scenario())


def test_simulated_desktop_explicit_render_and_input():
    desktop=SimulatedDesktop(1)
    assert desktop.snapshot()['approved'] is False
    desktop.input({'kind':'key','action':'down','key':'A'})
    assert desktop.snapshot()['text']=='A'
    desktop.input({'kind':'mouse','action':'down','x':.8,'y':.8})
    assert desktop.snapshot()['approved'] is True
    assert Image.open(io.BytesIO(desktop.capture(True))).size==(960,540)
    assert Image.open(io.BytesIO(desktop.capture(False))).size==(320,180)
    desktop.request()
    assert desktop.requested() and not desktop.requested()


def test_dev_refuses_production_config(tmp_path):
    atomic_json(tmp_path/'central.json',{'host':'0.0.0.0'})
    with pytest.raises(ValueError,match='exclusivo'):
        initialize(tmp_path)


def test_print_physical_directory_without_password_prompt(tmp_path,monkeypatch,capsys):
    import sys
    import smartpdv.dev as dev
    monkeypatch.setattr(sys,'argv',['smartpdv.dev','--data',str(tmp_path),'--print-data-directory'])
    dev.main()
    assert capsys.readouterr().out.strip()==str(tmp_path.resolve())
