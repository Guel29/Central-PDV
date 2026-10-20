"""Teste interativo automatizado do laboratório em duas abas Chromium."""
import asyncio
import base64
import hashlib
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_development import laboratory
from test_system import PASSWORD
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from playwright.async_api import async_playwright


async def main():
    with tempfile.TemporaryDirectory(prefix='smartpdv-dev-browser-') as tmp:
        path=Path(tmp)
        central,runner,port,pin=await laboratory(path)
        cert=x509.load_pem_x509_certificate((path/'central.crt').read_bytes())
        public=cert.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)
        spki=base64.b64encode(hashlib.sha256(public).digest()).decode()
        url=f'https://127.0.0.1:{port}'
        try:
            async with async_playwright() as p:
                browser=await p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox','--ignore-certificate-errors-spki-list='+spki])
                context=await browser.new_context(viewport={'width':1440,'height':1000})
                page=await context.new_page()
                errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                version={'value':1,'seen':False}
                async def version_response(route):
                    version['seen']=True
                    await route.fulfill(json={'version':version['value']})
                await page.route('**/dev/version',version_response)
                await page.goto(url)
                await page.locator('input[name=name]').fill('desenvolvimento')
                await page.locator('input[name=password]').fill(PASSWORD)
                await page.locator('#login button').click()
                await page.locator('.card').nth(1).wait_for()
                await page.locator('#audio').click()
                operator=await context.new_page()
                operator.on('pageerror',lambda e:errors.append(str(e)))
                await operator.goto(url+'/dev/operator')
                await operator.locator('.operator-card').nth(1).wait_for()
                await operator.locator('.operator-card').nth(0).get_by_role('button',name='Solicitar liberação (F11)').click()
                await page.locator('.card.pending').wait_for()
                await operator.locator('.operator-card').nth(1).get_by_role('button',name='Solicitar liberação (F11)').click()
                await page.wait_for_function("() => document.querySelectorAll('.card.pending').length === 2")
                await page.locator('.card').nth(0).click()
                await page.locator('#remote[open]').wait_for()
                await page.locator('#screen').press_sequentially('TESTE')
                await page.locator('#screen').press('Enter')
                await operator.wait_for_function("() => document.querySelector('.operator-card pre').textContent.includes('TESTE') && document.querySelector('.operator-card pre').textContent.includes('LIBERADO')")
                await page.locator('#switch').select_option('2')
                await page.wait_for_function("() => document.getElementById('remote-title').textContent.includes('PDV 2')")
                bounds=await page.locator('#screen').bounding_box()
                width=min(bounds['width'],bounds['height']*16/9)
                height=width*9/16
                await page.locator('#screen').click(position={
                    'x':(bounds['width']-width)/2+width*.8,
                    'y':(bounds['height']-height)/2+height*.8})
                await operator.wait_for_function("() => document.querySelectorAll('.operator-card pre')[1].textContent.includes('LIBERADO')")
                await page.bring_to_front()
                await page.locator('#fullscreen').click()
                await page.wait_for_function('() => !!document.fullscreenElement')
                await page.locator('#fullscreen').click()
                await page.wait_for_function('() => !document.fullscreenElement')
                await page.locator('#close').click()
                await page.wait_for_function("() => !document.querySelector('.card.active') && !document.querySelector('.card.pending')")
                await operator.locator('.operator-card').nth(1).get_by_role('button',name='Desconectar',exact=True).click()
                await page.locator('.card.offline').wait_for()
                await operator.locator('.operator-card').nth(1).get_by_role('button',name='Reconectar',exact=True).click()
                await page.wait_for_function("() => !document.querySelector('.card.offline')")
                await operator.locator('.operator-card').nth(0).get_by_role('button',name='Limpar venda simulada').click()
                await operator.wait_for_function("() => document.querySelector('.operator-card pre').textContent.includes('(nenhum)')")
                # Alterar a resposta de versão simula a detecção de um arquivo editado.
                for _ in range(100):
                    if version['seen']:break
                    await asyncio.sleep(.1)
                assert version['seen']
                await asyncio.sleep(.2)
                async with page.expect_navigation(wait_until='domcontentloaded'):
                    version['value']=2
                await page.locator('.card').nth(1).wait_for()
                assert await page.locator('#login').is_hidden()
                await page.screenshot(path=str(path/'development-central.png'))
                assert errors==[],errors
                await page.locator('#logout').click()
                await page.locator('#login').wait_for(state='visible')
                await browser.close()
                print('PASS: duas abas, dois Agents reais com desktops simulados, chamados, teclado e mouse, liberação, alternância, tela cheia, desconectar/reconectar, reset, auto-reload, login preservado e logout; nenhum erro JS.')
        finally:
            await runner.cleanup()


if __name__=='__main__':
    asyncio.run(main())
