"""Run the C# managed TLS/binary client against a real Central and TCP fixture.

Pass a command prefix (mono + optional config + probe exe), or the Windows probe exe.
"""
import asyncio
import json
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_usb_bridge import scenario, grant, wait_until
from test_system import TOKEN


async def check(c,h,client,url,pin,auth,agent,dashboard,counters):
    lease=await grant(dashboard,agent)
    with tempfile.TemporaryDirectory(prefix='usb-csharp-probe-') as tmp:
        pairing=Path(tmp)/'pairing.json'
        pairing.write_text(json.dumps(dict(number=1,computer_id='test-device',central='127.0.0.1',
            port=int(url.rsplit(':',1)[1]),fingerprint=c.config['fingerprint'],token=TOKEN)))
        proc=await asyncio.create_subprocess_exec(*sys.argv[1:],str(pairing),lease['lease'])
        try:
            assert await asyncio.wait_for(proc.wait(),30)==0
        finally:
            if proc.returncode is None:
                proc.kill()
                await proc.wait()
        await wait_until(lambda:c.usb.lease is None)
        assert counters['connections']==1


if __name__=='__main__':
    if len(sys.argv)<2:
        raise SystemExit('Pass the compiled C# probe command')
    with tempfile.TemporaryDirectory(prefix='usb-interop-') as tmp:
        asyncio.run(scenario(Path(tmp),check))
