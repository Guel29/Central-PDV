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
    await page.locator('#windows-key').click()
    assert (await asyncio.wait_for(commands.get(),5))=={'type':'input','event':{'kind':'release'}}
    for action in ('down','up'):
     assert (await asyncio.wait_for(commands.get(),5))=={'type':'input','event':{'kind':'key','key':'Meta','code':'MetaLeft','action':action}}
    await page.locator('#screen').press('Enter')
    for action in ('down','up'):
     assert (await asyncio.wait_for(commands.get(),5))=={'type':'input','event':{'kind':'key','key':'Enter','code':'Enter','action':action}}
    await page.locator('#screen').press('Numpad1')
    for action in ('down','up'):
     event=(await asyncio.wait_for(commands.get(),5))['event']
     assert event['code']=='Numpad1' and event['action']==action

    await page.locator('#close').click()
    async def ended():
     while True:
      command=await commands.get()
      if command.get('type')=='session':
       assert command['active'] is False
       return
    await asyncio.wait_for(ended(),5)
    await page.locator('.card:not(.active):not(.pending)').wait_for()
    await page.locator('#peripherals-panel > summary').click()
    await page.locator('#allow-keyboard').uncheck()
    await page.locator('#allow-mouse').uncheck()
    await page.locator('#save-peripherals').click()
    await page.wait_for_function("() => document.querySelector('#peripherals-status').textContent.includes('salvas')")
    assert central.config['peripherals']=={'keyboard':False,'mouse':False,'scanner':True}
    await page.locator('.card').click()
    assert (await asyncio.wait_for(commands.get(),5))=={'type':'session','active':True}
    await page.locator('#remote[open]').wait_for()
    await page.locator('#screen').press('1')  # Disabled keyboard must not reach the Agent.
    code='0012345678901'
    await page.locator('#barcode').fill(code)
    assert (await asyncio.wait_for(commands.get(),5))=={'type':'input','event':{'kind':'release'}}  # Screen blur.
    await page.locator('#barcode').press('Enter')
    expected=[{'kind':'release'}]
    expected.extend({'kind':'key','action':action,'key':key} for key in [*code,'Enter'] for action in ('down','up'))
    expected.append({'kind':'release'})
    for event in expected:
     assert (await asyncio.wait_for(commands.get(),5))=={'type':'input','event':event}
    await page.wait_for_function("() => document.querySelector('#barcode-status').textContent.includes('Confirme')")
    assert await page.locator('#barcode').input_value()==''
    # Real browser keyboard events retain keypad identity in the EAN field.
    physical='0012'
    # Headless Chromium has NumLock off; provide trusted CDP digit events
    # with the physical keypad code, as produced with NumLock enabled.
    cdp=await page.context.new_cdp_session(page)
    for digit in physical:
     packet=dict(code='Numpad'+digit,key=digit,windowsVirtualKeyCode=96+int(digit),isKeypad=True,location=3)
     await cdp.send('Input.dispatchKeyEvent',dict(type='keyDown',text=digit,**packet))
     await cdp.send('Input.dispatchKeyEvent',dict(type='keyUp',**packet))
    await page.locator('#barcode').press('NumpadEnter')
    assert (await asyncio.wait_for(commands.get(),5))=={'type':'input','event':{'kind':'release'}}
    for key,physical_code in zip([*physical,'Enter'],[*['Numpad'+digit for digit in physical],'NumpadEnter']):
     for action in ('down','up'):
      assert (await asyncio.wait_for(commands.get(),5))=={'type':'input','event':{'kind':'key','key':key,'action':action,'code':physical_code}}
    assert (await asyncio.wait_for(commands.get(),5))=={'type':'input','event':{'kind':'release'}}
    await page.wait_for_function("() => document.querySelector('#barcode-status').textContent.includes('Confirme')")
    await page.locator('#close').click()
    await asyncio.wait_for(ended(),5)
    await page.locator('#allow-scanner').uncheck()
    await page.locator('#save-peripherals').click()
    await page.wait_for_function("() => document.querySelector('#peripherals-status').textContent.includes('salvas')")
    await page.locator('.card').click()
    assert (await asyncio.wait_for(commands.get(),5))=={'type':'session','active':True}
    await page.locator('#remote[open]').wait_for()
    assert await page.locator('#barcode').is_disabled()
    await page.locator('#close').click()
    await asyncio.wait_for(ended(),5)
    await page.reload()
    await page.locator('.card').wait_for()
    assert not await page.locator('#allow-keyboard').is_checked()
    assert not await page.locator('#allow-scanner').is_checked()
    assert not await page.locator('#allow-mouse').is_checked()
    assert await page.locator('#diagnose').count()==0
    await agent.close()
    await reader
    await page.locator('.card.offline').wait_for()
    assert errors==[],errors
    await browser.close()
    print('PASS Chromium: entrada direta, cards, alarmes, atendimento, teclado, autorizações persistentes, bloqueio de teclado, EAN com zeros iniciais e teclas físicas do teclado numérico, botão Windows remoto, leitor desativado, encerramento e offline; no JS errors')
  finally:
   await runner.cleanup()
asyncio.run(main())
