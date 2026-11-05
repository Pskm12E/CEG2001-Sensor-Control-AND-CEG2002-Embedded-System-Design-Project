"""Verify direct ESP firmware over USB; optionally check UART and Wi-Fi HTTP.
Never sends start, calibration, reset, flash or spray commands.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import time
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tmp/pico-tools-python'))
import serial
from serial.tools import list_ports

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--esp',default='COM15')
ap.add_argument('--allow-unwired',action='store_true')
ap.add_argument('--http',action='store_true',help='Laptop must already have joined the robot private Wi-Fi')
args=ap.parse_args()
device=next((p for p in list_ports.comports() if p.device==args.esp),None)
if not device or (device.vid,device.pid)!=(0x1a86,0x7523):
    raise SystemExit('Expected FireBeetle CH340 port; nothing opened')
stamp=datetime.now(timezone(timedelta(hours=8)))
report={'tested_at':stamp.isoformat(),'scope':__doc__,'checks':[],'exchanges':[],
        'uart_wired_passed':False,'wifi_http_passed':False,'usb_passed':False}

def check(label,ok,evidence):
    report['checks'].append({'check':label,'passed':bool(ok),'evidence':evidence})
    print(('PASS ' if ok else 'FAIL ')+label,flush=True)
    if not ok: raise AssertionError(label+': '+str(evidence))

def exchange(p,command,prefix,timeout=3):
    p.reset_input_buffer(); p.write((command+'\n').encode())
    end=time.monotonic()+timeout; buf=bytearray(); lines=[]
    while time.monotonic()<end:
        buf.extend(p.read(p.in_waiting or 1))
        while b'\n' in buf:
            raw,_,rest=buf.partition(b'\n'); buf=bytearray(rest)
            line=raw.decode('ascii','backslashreplace').strip()
            if not line: continue
            lines.append(line)
            if line.startswith(prefix):
                report['exchanges'].append({'command':command,'lines':lines})
                return line
    raise RuntimeError(command+' timeout: '+repr(lines))

p=serial.Serial(port=None,baudrate=115200,timeout=.05,write_timeout=1)
p.port=args.esp; p.dtr=p.rts=False
try:
    p.open(); time.sleep(.3)
    r=exchange(p,'PING','PONG ')
    check('New ESP direct Wi-Fi identity',r=='PONG ESP32_DIRECT_WIFI_V1',r)
    r=exchange(p,'STATUS','STATUS BOARD=')
    check('Private AP and new UART pins configured',all(v in r for v in
          ('FW=DIRECT_WIFI_V1','AP=READY','MSP_UART_RX=16','MSP_UART_TX=17','IP=192.168.4.1')),r)
    for cmd in ('F','START','SPRAY','W','B','C','ROBOT MSP START'):
        check('Reject '+cmd,exchange(p,cmd,'ERROR ')=='ERROR unsupported command',cmd)
    s=json.loads(exchange(p,'STATE','{'))
    check('JSON identifies MSP as main controller',s.get('main_controller')=='MSP430F5529',s)
    if args.allow_unwired:
        check('Unwired MSP is truthfully unavailable',s.get('msp_link')=='NOT_CONNECTED' and not s.get('fresh'),s)
        check('Unwired STOP is not queued',exchange(p,'MSP STOP','ERROR ')==
              'ERROR MSP unavailable or busy; request not queued','MSP STOP')
    else:
        check('Fresh physical MSP UART response',s.get('fresh') and s.get('msp_link')=='UP' and
              'BRIDGE=ESP_UART_V1' in (s.get('telemetry') or ''),s)
        check('Uno linked and stopped',all(v in s['telemetry'] for v in ('LINK=READY','RUN=0')),s['telemetry'])
        report['uart_wired_passed']=True
    report['usb_passed']=True
    if args.http:
        with urlopen('http://192.168.4.1/api/state',timeout=4) as response:
            state=json.load(response)
        check('Laptop Wi-Fi HTTP reaches direct ESP',state.get('firmware')=='DIRECT_WIFI_V1',state)
        report['wifi_http_passed']=True
except Exception as exc:
    report['error']=str(exc); print('ERROR '+str(exc),flush=True)
finally:
    p.close()
    path=ROOT/'Laptop/Artifacts/verification'/f'direct-wifi-{stamp:%Y-%m-%d-%H%M%S}.json'
    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('REPORT '+str(path),flush=True)
sys.exit(0 if report['usb_passed'] and 'error' not in report else 1)
