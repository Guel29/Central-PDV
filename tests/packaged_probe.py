"""Verifica o servidor do executável Windows instalado, sem ignorar TLS."""
import json
from pathlib import Path
import ssl
import sys
import time
import traceback
import urllib.request

certificate,url=sys.argv[1:3]
report=Path(sys.argv[3]) if len(sys.argv)>3 else None
context=ssl.create_default_context(cafile=certificate)
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=context))
for attempt in range(40):
    try:
        with opener.open(url+'/health',timeout=1) as response:
            assert json.load(response)['status']=='ok'
        with opener.open(url+'/session',timeout=1) as response:
            assert json.load(response)['direct_access'] is True
        with opener.open(url,timeout=1) as response:
            html=response.read().decode('utf-8')
            assert 'SMART' in html and 'id="login"' not in html
        print('PASS installed Central: HTTPS, session bootstrap, dashboard assets, no login')
        break
    except OSError:
        startup=Path(certificate).parent/'startup-error.txt'
        if attempt==39 or startup.exists():
            if report:
                report.write_text(traceback.format_exc(),encoding='utf-8')
            raise
        time.sleep(1)
