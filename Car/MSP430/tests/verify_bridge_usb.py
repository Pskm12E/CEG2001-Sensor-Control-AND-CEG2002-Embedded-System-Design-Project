"""Verify the flashed I2C-capable supervisor via USB; never starts/calibrates.
The Uno and physical I2C links are reported separately from USB test results.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tmp/pico-tools-python'))
import serial
from serial.tools import list_ports

ap=argparse.ArgumentParser()
ap.add_argument('--msp',default='COM13')
args=ap.parse_args()
device=next((p for p in list_ports.comports() if p.device==args.msp),None)
if not device or (device.vid,device.pid)!=(0x2047,0x0013) or 'Application' not in device.description:
    raise SystemExit('Expected MSP Application UART; no port opened')

stamp=datetime.now(timezone(timedelta(hours=8)))
report={'time':stamp.isoformat(),'scope':'MSP USB after I2C endpoint upload; no movement/calibration',
        'physical_i2c_tested':False,'checks':[],'statuses':[],'usb_passed':False}
def check(label,ok,evidence):
    report['checks'].append({'check':label,'passed':bool(ok),'evidence':evidence})
    print(('PASS ' if ok else 'FAIL ')+label,flush=True)
    if not ok: raise AssertionError(label+': '+evidence)
def exchange(p,command,duration=.55):
    p.reset_input_buffer();p.write((command+'\n').encode('ascii'))
    end=time.monotonic()+duration;buf=bytearray()
    while time.monotonic()<end:buf.extend(p.read(p.in_waiting or 1))
    return buf.decode('ascii','backslashreplace')

p=serial.Serial(port=None,baudrate=9600,timeout=.05,write_timeout=1)
p.port=args.msp;p.dtr=False;p.rts=False
try:
    p.open();exchange(p,'',.2)
    text=exchange(p,'PING')
    check('Supervisor identity','PONG MSP430 SUPERVISOR_V2' in text,text)
    text=exchange(p,'S',1.2)
    check('Local stop command accepted','STOP REQUESTED' in text,text)
    report['uno_stop_ack_observed']='STOP CONFIRMED' in text
    for n in range(5):
        text=exchange(p,'STATUS')
        lines=[line for line in text.splitlines() if line.startswith('STATUS BOARD=')]
        check(f'USB status reply {n+1}',bool(lines),text)
        fields=dict(re.findall(r'([A-Z0-9_]+)=([^\s]+)',lines[-1]))
        check(f'I2C firmware identity and stopped {n+1}',
              fields.get('BRIDGE')=='I2C_V1' and fields.get('RUN')=='0',lines[-1])
        report['statuses'].append(fields)
    report['uno_link_stable_ready']=all(s.get('LINK')=='READY' for s in report['statuses'])
    report['usb_passed']=True
    print('UNO_LINK_STABLE_READY='+str(report['uno_link_stable_ready']),flush=True)
    print('FINAL '+json.dumps(report['statuses'][-1]),flush=True)
except Exception as exc:
    report['error']=str(exc);print('ERROR '+str(exc),flush=True)
finally:
    p.close()
    path=ROOT/'Laptop/Artifacts/verification'/f'msp-bridge-usb-{stamp:%Y-%m-%d-%H%M%S}.json'
    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('REPORT '+str(path),flush=True)
sys.exit(0 if report['usb_passed'] else 1)
