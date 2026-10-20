import asyncio
from types import SimpleNamespace

from aiohttp import ClientSession, Fingerprint, web
import pytest
from smartpdv.central import Central
from test_system import prepare,start


@pytest.mark.parametrize('remote,local,expected',[
    ('127.0.0.1','127.0.0.1',True),('::1','::1',True),
    ('192.168.1.10','192.168.1.10',True),
    ('192.168.1.20','192.168.1.10',False),('8.8.8.8','192.168.1.10',False)])
def test_console_is_local_to_central(remote,local,expected):
    request=SimpleNamespace(remote=remote,transport=SimpleNamespace(get_extra_info=lambda _: (local,8443)))
    assert Central.is_console(request)==expected
    if not expected:
        with pytest.raises(web.HTTPForbidden):
            Central.require_console(Central.__new__(Central),request)


def test_direct_access_has_no_user_registration_or_password(tmp_path):
    async def scenario():
        pin=Fingerprint(bytes.fromhex(prepare(tmp_path)))
        central,runner,port=await start(tmp_path)
        url=f'https://127.0.0.1:{port}'
        try:
            async with ClientSession() as client:
                page=await client.get(url,ssl=pin)
                assert 'id="login"' not in await page.text()
                session=await client.get(url+'/session',ssl=pin)
                assert session.status==200 and (await session.json())['direct_access']
                for path in ('/login','/users','/logout'):
                    assert (await client.post(url+path,ssl=pin,json={})).status==404
                assert (await client.get(url+'/session',ssl=pin,headers={'Origin':'https://evil.invalid'})).status==403
                assert (await client.get(url+'/session',ssl=pin,headers={'Sec-Fetch-Site':'cross-site'})).status==403
        finally:
            await runner.cleanup()
    asyncio.run(scenario())
