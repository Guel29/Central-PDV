import asyncio,base64,hashlib,sys,tempfile,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_system import prepare,start,TOKEN,FakeDesktop
from aiohttp import ClientSession,Fingerprint
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from playwright.async_api import async_playwright

async def main():
 with tempfile.TemporaryDirectory(prefix='smartpdv-ui-') as tmp:
  path=Path(tmp);pin=prepare(path);central,runner,port=await start(path)
  cert=x509.load_pem_x509_certificate((path/'central.crt').read_bytes())
  public=cert.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)
  spki=base64.b64encode(hashlib.sha256(public).digest()).decode()
  try:
   async with ClientSession() as client,async_playwright() as p:
    agent=await client.ws_connect(f'https://127.0.0.1:{port}/agent',ssl=Fingerprint(bytes.fromhex(pin)),headers={'X-Computer-ID':'test-device','Authorization':'Bearer '+TOKEN})
    commands=asyncio.Queue()
    async def read_agent():
     async for msg in agent:
      if msg.type.name=='TEXT':
       import json
       await commands.put(json.loads(msg.data))
    reader=asyncio.create_task(read_agent())
    browser=await p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox','--ignore-certificate-errors-spki-list='+spki])
    page=await browser.new_page(viewport={'width':1440,'height':1000})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    await page.goto(f'https://127.0.0.1:{port}')
    await page.locator('.card').wait_for()
    await page.locator('#audio').click()
    await page.evaluate('''() => { window.beepCount=0; const original=AudioContext.prototype.createOscillator; AudioContext.prototype.createOscillator=function(...args){window.beepCount++;return original.apply(this,args);}; }''')
    await agent.send_json({'type':'frame','jpeg':base64.b64encode(FakeDesktop().capture(False)).decode()})
    await agent.send_json({'type':'request'})
    await page.locator('.card.pending').wait_for()
    await page.wait_for_function('() => window.beepCount === 3')
    await page.wait_for_function('() => window.beepCount >= 6',timeout=15000)
    await page.screenshot(path=str(path/'dashboard.png'))
    await page.locator('.card.pending').click()
    assert (await asyncio.wait_for(commands.get(),5))=={'type':'session','active':True}
    await page.locator('#remote[open]').wait_for()
    await page.locator('#screen').press('Enter')
    assert (await asyncio.wait_for(commands.get(),5))['type']=='input'
    assert (await asyncio.wait_for(commands.get(),5))['type']=='input'
    await page.locator('#close').click()
    async def ended():
     while True:
      command=await commands.get()
      if command.get('type')=='session':
       assert command['active'] is False
       return
    await asyncio.wait_for(ended(),5)
    await page.locator('.card:not(.active):not(.pending)').wait_for()
    await agent.close()
    await reader
    await page.locator('.card.offline').wait_for()
    assert errors==[],errors
    await browser.close()
    print('PASS Chromium: entrada direta, card, F11 request, alarm enable, remote session, keyboard forwarding, triple beep and 10-second repeat, end, offline; no JS errors')
  finally:
   await runner.cleanup()
asyncio.run(main())
