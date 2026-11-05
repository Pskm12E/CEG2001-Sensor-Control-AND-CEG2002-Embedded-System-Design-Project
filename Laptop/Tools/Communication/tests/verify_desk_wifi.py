"""Read-only hardware test: laptop USB -> desk Pico -> private Wi-Fi ESP -> MSP -> Uno.
No motor, STOP, calibration, spray, reset or flash commands are dispatched.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sys
import time

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tmp/pico-tools-python'))
import serial
from serial.tools import list_ports

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--pico',default='COM11')
args=ap.parse_args()
device=next((p for p in list_ports.comports() if p.device==args.pico),None)
if not device or (device.vid,device.pid)!=(0x2e8a,0x000a):
    raise SystemExit('Expected RP2040 Pico USB; nothing opened')
stamp=datetime.now(timezone(timedelta(hours=8)))
report={'tested_at':stamp.isoformat(),'scope':__doc__,'checks':[],'exchanges':[],'passed':False}

def check(label,ok,evidence):
    report['checks'].append({'check':label,'passed':bool(ok),'evidence':evidence})
    print(('PASS ' if ok else 'FAIL ')+label,flush=True)
    if not ok: raise AssertionError(label+': '+str(evidence))

def exchange(command,prefix,timeout=10):
    p.reset_input_buffer()
    payload=command.encode() if isinstance(command,str) else command
    p.write(payload+b'\n')
    end=time.monotonic()+timeout; buf=bytearray(); lines=[]
    while time.monotonic()<end:
        buf.extend(p.read(p.in_waiting or 1))
        while b'\n' in buf:
            raw,_,rest=buf.partition(b'\n'); buf=bytearray(rest)
            line=raw.decode('ascii','backslashreplace').strip()
            if not line: continue
            lines.append(line)
            if line.startswith(prefix) or line.startswith(('ROBOT ERROR ','ERROR ')):
                report['exchanges'].append({'command':payload.decode('ascii','backslashreplace'),'lines':lines})
                return line
    raise RuntimeError(str(command)+' timeout: '+repr(lines))

def fields(line):
    return dict(re.findall(r'([A-Z0-9_]+)=([^\s]+)',line))

p=serial.Serial(port=None,baudrate=115200,timeout=.05,write_timeout=1)
p.port=args.pico; p.dtr=True; p.rts=False
try:
    p.open(); time.sleep(.3)
    r=exchange('PING','PONG ')
    check('Desk Pico USB firmware identity',r=='PONG PICO_DESK_BRIDGE_V2',r)
    r=exchange('STATUS','STATUS BOARD=')
    s=fields(r)
    check('Desk role and running indicator',s.get('ROLE')=='LAPTOP_BRIDGE' and s.get('LED')=='ON' and s.get('READ_ONLY')=='1',r)
    deadline=time.monotonic()+35
    while time.monotonic()<deadline:
        r=exchange('STATUS','STATUS BOARD='); s=fields(r)
        if all(s.get(k)=='UP' for k in ('WIFI','ESP_LINK','MSP_LINK')): break
        time.sleep(.5)
    check('Private Wi-Fi, ESP and MSP links UP',all(s.get(k)=='UP' for k in ('WIFI','ESP_LINK','MSP_LINK')),r)
    r=exchange('ROBOT PING','ROBOT PONG ')
    check('USB -> Pico Wi-Fi -> ESP HTTP round trip',r=='ROBOT PONG ESP32_DIRECT_WIFI_V1',r)
    r=exchange('ROBOT STATE','ROBOT STATE ')
    state=json.loads(r.removeprefix('ROBOT STATE '))
    check('ESP confirms fresh MSP UART telemetry',state.get('firmware')=='DIRECT_WIFI_V1' and state.get('main_controller')=='MSP430F5529' and state.get('fresh') is True and state.get('msp_link')=='UP',state)
    r=exchange('ROBOT MSP STATUS','ROBOT MSP STATUS '); baseline=fields(r)
    check('MSP supervisor identity through complete bridge',baseline.get('BOARD')=='MSP430F5529' and baseline.get('FW')=='SUPERVISOR_V2' and baseline.get('BRIDGE')=='ESP_UART_V1',r)
    check('Uno linked and stopped',baseline.get('LINK')=='READY' and baseline.get('RUN')=='0' and not(int(baseline.get('FLAGS','255'))&8),r)
    samples=[]
    for _ in range(20):
        time.sleep(.15)
        sample=fields(exchange('ROBOT MSP STATUS','ROBOT MSP STATUS ')); samples.append(sample)
        if sample.get('BOARD')!='MSP430F5529': break
    check('20 full-path status round trips',len(samples)==20 and all(s.get('BOARD')=='MSP430F5529' and s.get('LINK')=='READY' and s.get('RUN')=='0' for s in samples),samples)
    check('MSP/Uno error counters stable',all(all(s.get(k)==baseline.get(k) for k in ('UART_ERRORS','RX_DROPS','BAD_FRAMES')) for s in samples),samples)
    for cmd in ('F','START','SPRAY','W','B','C','ROBOT MSP START','ROBOT MSP STOP'):
        r=exchange(cmd,'ERROR ')
        check('Read-only bridge rejects '+cmd,r=='ERROR unsupported command; read-only bridge',r)
    r=exchange(b'X'*100+b'ROBOT MSP STATUS','ERROR ')
    check('Oversized line rejected',r=='ERROR invalid or oversized USB line',r)
    r=exchange(b'ROBOT\x00 MSP STATUS','ERROR ')
    check('Binary line rejected',r=='ERROR invalid or oversized USB line',r)
    r=exchange('ROBOT STATE','ROBOT STATE ')
    state=json.loads(r.removeprefix('ROBOT STATE '))
    check('Remote status recovers after rejected input',state.get('fresh') is True and state.get('msp_link')=='UP',state)
    report['passed']=True
except Exception as exc:
    report['error']=str(exc); print('ERROR '+str(exc),flush=True)
finally:
    p.close()
    path=ROOT/'Laptop/Artifacts/verification'/f'desk-wifi-{stamp:%Y-%m-%d-%H%M%S}.json'
    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('REPORT '+str(path),flush=True)
sys.exit(0 if report['passed'] else 1)
