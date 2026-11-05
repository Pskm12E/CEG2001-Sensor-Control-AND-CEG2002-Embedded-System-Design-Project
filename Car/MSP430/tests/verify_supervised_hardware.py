"""USB-powered integration checks; keep the motor battery disconnected.
Never calibrates sensors, never sends a permitted START. F is tested only
after asserting the fresh firmware reports CAL=NEEDED and no calibrated flag.
"""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import argparse
import json
import re
import sys
import time
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tmp/pico-tools-python'))
import serial

ap=argparse.ArgumentParser()
ap.add_argument('--msp',default='COM13'); ap.add_argument('--uno',default='COM12')
args=ap.parse_args()
stamp=datetime.now(timezone(timedelta(hours=8)))
report={'time':stamp.isoformat(),'scope':'supervisor V2 integration, motors unpowered',
        'physical_line_following_tested':False,'physical_lease_stop_while_moving_tested':False,
        'results':[],'passed':False}
ports=[]
def connect(name,baud):
    p=serial.Serial(port=None,baudrate=baud,timeout=.05,write_timeout=1)
    p.port=name; p.dtr=False; p.rts=False; p.open(); ports.append(p); return p
def command(p,text,duration=.5):
    p.reset_input_buffer(); p.write(text.encode()+b'\n')
    end=time.monotonic()+duration; buf=bytearray()
    while time.monotonic()<end: buf.extend(p.read(p.in_waiting or 1))
    return buf.decode('ascii','backslashreplace')
def check(label,condition,evidence):
    report['results'].append({'check':label,'passed':bool(condition),'evidence':evidence})
    print(('PASS ' if condition else 'FAIL ')+label+': '+str(evidence).strip(),flush=True)
    if not condition: raise AssertionError(label)
def status(p):
    text=command(p,'STATUS')
    lines=[s for s in text.splitlines() if s.startswith('STATUS BOARD=')]
    if not lines: raise AssertionError('No MSP status: '+repr(text))
    fields=dict(re.findall(r'([A-Z0-9_]+)=([^\s]+)',lines[-1]))
    return fields,lines[-1]
def wait_ready(msp):
    end=time.monotonic()+5
    while time.monotonic()<end:
        fields,text=status(msp)
        if fields.get('LINK')=='READY': return fields,text
    raise AssertionError('MSP link did not become READY: '+text)

try:
    msp=connect(args.msp,9600); uno=connect(args.uno,115200); time.sleep(2)
    command(msp,''); command(uno,'')
    text=command(msp,'PING'); check('MSP V2 identity','PONG MSP430 SUPERVISOR_V2' in text,text)
    baseline,text=wait_ready(msp)
    check('Linked and stopped',baseline.get('RUN')=='0' and not(int(baseline['FLAGS'])&8),text)
    check('Calibration required',baseline.get('CAL')=='NEEDED' and not(int(baseline['FLAGS'])&1),text)
    text=command(uno,'STATUS'); check('Uno V2 stopped','UNO V2' in text and 'DRIVE=0' in text,text)
    text=command(msp,'F',.9); check('Uncalibrated start refused','START REFUSED; RESULT=NOT_CALIBRATED' in text,text)
    fields,text=status(msp); check('Refusal kept stopped',fields['RUN']=='0' and not(int(fields['FLAGS'])&8),text)
    text=command(msp,'S',1.2); check('MSP stop acknowledged','STOP CONFIRMED' in text,text)
    fields,text=wait_ready(msp); check('Stop resynchronised without start',fields['RUN']=='0',text)
    text=command(msp,'H',.8); check('Manual resynchronisation','LINK READY; STOPPED' in text,text)
    text=command(msp,'LINK ON'); check('Old bench command rejected','ERR UNKNOWN COMMAND' in text,text)
    text=command(uno,'F'); check('Uno USB cannot start','DRIVE=0' in text,text)
    command(uno,'S'); time.sleep(.9)
    fields,text=wait_ready(msp); check('Uno local stop recovered stopped',fields['RUN']=='0' and not(int(fields['FLAGS'])&8),text)
    for n in range(1,4):
        uno.dtr=True; time.sleep(.1); uno.dtr=False; time.sleep(2)
        fields,text=wait_ready(msp)
        check('Uno reset recovery '+str(n),fields['RUN']=='0' and fields['CAL']=='NEEDED',text)
    for n in range(1,6):
        fields,text=status(msp)
        check('Continuing wired status '+str(n),fields['LINK']=='READY' and fields['RUN']=='0',text)
    check('No new framing errors',fields['BAD_FRAMES']==baseline['BAD_FRAMES'],text)
    # Reset transitions can electrically disturb UART; report counters explicitly.
    report['initial_status']=baseline; report['final_status']=fields
    text=command(uno,'STATUS'); check('Final Uno outputs stopped','DRIVE=0' in text,text)
    report['passed']=True
except Exception as exc:
    report['error']=str(exc); print('ERROR: '+str(exc),flush=True)
finally:
    for p in ports:
        try: p.write(b'S\n'); time.sleep(.1)
        except Exception: pass
        p.close()
    out=ROOT/'Laptop/Artifacts/verification'/('supervised-link-'+stamp.strftime('%Y-%m-%d-%H%M%S')+'.json')
    out.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('REPORT: '+str(out),flush=True)
sys.exit(0 if report['passed'] else 1)
