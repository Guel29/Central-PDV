"""UI + real transport fixture, no physical Windows USB emulation."""
import asyncio
import base64
import hashlib
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tempfile
from aiohttp import ClientSession, Fingerprint
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from playwright.async_api import async_playwright
from test_usb_bridge import scenario, grant, IMPORT, IMPORTED, INSTANCE


async def check(c,h,client,url,pin,auth,agent,dashboard,counters):
    # This test opens its own dashboard; release the fixture's initial attendance.
    await dashboard.send_json({'type':'end','number':1})
    while (await agent.receive_json()).get('type') != 'session':
        pass
    cert=x509.load_pem_x509_certificate((c.directory/'central.crt').read_bytes())
    key=cert.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)
    spki=base64.b64encode(hashlib.sha256(key).digest()).decode()
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),
            args=['--no-sandbox','--ignore-certificate-errors-spki-list='+spki],headless=True)
        page=await browser.new_page()
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('dialog',lambda dialog:dialog.accept())
        await page.goto(url)
        await page.locator('.card').wait_for()
        await page.locator('#usb-refresh').click()
        await page.wait_for_function('() => document.querySelector("#usb-device").options.length===1')
        await page.locator('#usb-select').click()
        await page.wait_for_function('() => document.querySelector("#usb-status").textContent.includes("disponível")')
        await page.locator('.card').click()
        assert (await agent.receive_json())=={'type':'session','active':True}
        await page.locator('#remote[open]').wait_for()
        await page.locator('#usb-connect').click()
        while True:
            command=await agent.receive_json()
            if command.get('type')=='usb_connect':
                break
        assert command['instance']==INSTANCE
        await page.wait_for_function('() => document.querySelector("#usb-remote-status").textContent.includes("conectando")')
        ws=await client.ws_connect(url+'/usb-stream',ssl=pin,headers={**auth,'X-USB-Lease':command['lease']})
        await ws.send_bytes(IMPORT+b'1-2'.ljust(32,b'\0'))
        assert (await ws.receive()).data==IMPORTED
        assert len((await ws.receive()).data)==312
        await agent.send_json({'type':'usb_status','lease':command['lease'],'ok':True})
        await page.wait_for_function('() => document.querySelector("#usb-remote-status").textContent.includes("conectado") && !document.querySelector("#usb-remote-status").textContent.includes("desconectado")')
        await page.locator('#usb-disconnect').click()
        await page.wait_for_function('() => document.querySelector("#usb-remote-status").textContent.includes("desconectado")')
        assert (await ws.receive()).type.name in ('CLOSE','CLOSED')
        assert not errors,errors
        await browser.close()
    print('PASS USB UI: enumerate/select, real grant/import, connected report and disconnect; no JS errors. Physical USB/VR untested.')


if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='smartpdv-usb-browser-') as tmp:
        asyncio.run(scenario(Path(tmp),check))
