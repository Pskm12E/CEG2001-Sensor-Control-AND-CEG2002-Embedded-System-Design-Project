"""Check ESP -> Pico -> MSP I2C and MSP -> Uno stop/status, with motors unpowered.

No start, calibration, reset, flash or supply-switching commands are sent.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'tmp/pico-tools-python'))
import serial
from serial.tools import list_ports

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--esp', required=True)
ap.add_argument('--msp', required=True)
args = ap.parse_args()
ports = {p.device: p for p in list_ports.comports()}
for name, identity in ((args.esp, (0x1A86, 0x7523)), (args.msp, (0x2047, 0x0013))):
    p = ports.get(name)
    if not p or (p.vid, p.pid) != identity:
        raise SystemExit(f'Unexpected USB device at {name}; nothing opened')
if 'Application' not in ports[args.msp].description:
    raise SystemExit('Use MSP Application UART, not Debug Interface')

stamp = datetime.now(timezone(timedelta(hours=8)))
report = {'tested_at': stamp.isoformat(), 'scope': __doc__,
          'ports': {'esp': args.esp, 'msp': args.msp},
          'checks': [], 'transcript': [], 'passed': False}

def check(label, ok, evidence):
    report['checks'].append({'check': label, 'passed': bool(ok), 'evidence': evidence})
    print(('PASS ' if ok else 'FAIL ') + label, flush=True)
    if not ok:
        raise AssertionError(f'{label}: {evidence}')

def open_port(name, baud):
    p = serial.Serial(port=None, baudrate=baud, timeout=.05, write_timeout=1)
    p.port = name
    p.dtr = p.rts = False
    p.open()
    return p

def exchange(p, command, prefix, timeout=3):
    p.reset_input_buffer()
    p.write((command + '\n').encode('ascii'))
    end = time.monotonic() + timeout
    seen = []
    buffered = bytearray()
    while time.monotonic() < end:
        buffered.extend(p.read(p.in_waiting or 1))
        if b'\n' not in buffered:
            continue
        raw, _, rest = buffered.partition(b'\n')
        buffered = bytearray(rest)
        line = raw.decode('ascii', 'backslashreplace').strip()
        if not line:
            continue
        seen.append(line)
        if line.startswith(prefix) or line.startswith(('ERROR ', 'ROBOT MSP ERROR')):
            break
        if line.startswith('BUSY '):
            # Explicit rejection means this command was NOT dispatched.
            time.sleep(.15)
            p.write((command + '\n').encode('ascii'))
    if buffered.strip():
        seen.append('[partial] ' + buffered.decode('ascii', 'backslashreplace').strip())
    report['transcript'].append({'port': p.port, 'command': command, 'lines': seen})
    return next((s for s in reversed(seen) if s.startswith(prefix)), ' | '.join(seen))

def fields(line):
    return dict(re.findall(r'([A-Z0-9_]+)=([^\s]+)', line))

def stopped(s):
    return s.get('LINK') == 'READY' and s.get('RUN') == '0' and not (int(s.get('FLAGS', '255')) & 8)

esp = msp = None
try:
    esp = open_port(args.esp, 115200)
    msp = open_port(args.msp, 9600)
    time.sleep(.3)
    r = exchange(msp, 'PING', 'PONG MSP430')
    check('MSP USB identity', r == 'PONG MSP430 SUPERVISOR_V2', r)
    direct = fields(exchange(msp, 'STATUS', 'STATUS BOARD='))
    check('MSP I2C firmware loaded', direct.get('BRIDGE') == 'I2C_V1', direct)
    r = exchange(esp, 'PING', 'PONG ESP32')
    check('ESP USB identity', r == 'PONG ESP32_GATEWAY', r)
    r = exchange(esp, 'STATUS', 'STATUS BOARD=')
    check('Pico Wi-Fi connection', fields(r).get('PICO_LINK') == 'UP', r)
    r = exchange(esp, 'ROBOT PING', 'ROBOT PONG')
    check('Pico radio reply', r == 'ROBOT PONG PICO_W', r)
    r = exchange(esp, 'ROBOT MSP STATUS', 'ROBOT MSP STATUS')
    remote = fields(r)
    check('Fresh physical I2C MSP response', remote.get('BOARD') == 'MSP430F5529' and
          remote.get('FW') == 'SUPERVISOR_V2' and 'TICKS' in remote, r)
    check('USB and radio state agree', all(remote.get(k) == direct.get(k) for k in
          ('LINK', 'RUN', 'FLAGS', 'UART_ERRORS', 'RX_DROPS', 'BAD_FRAMES')), {'usb': direct, 'radio': remote})
    r = exchange(esp, 'STATUS', 'STATUS BOARD=')
    check('Gateway reports fresh MSP link', fields(r).get('MSP_LINK') == 'UP', r)
    r = exchange(esp, 'ROBOT MSP STOP', 'ROBOT MSP STOP=REQUESTED')
    check('MSP accepted radio stop request', r.startswith('ROBOT MSP STOP=REQUESTED BOARD=MSP430F5529'), r)
    # Await the existing UART handshake; no local stop command is substituted.
    history = []
    for _ in range(10):
        time.sleep(.3)
        r = exchange(esp, 'ROBOT MSP STATUS', 'ROBOT MSP STATUS')
        s = fields(r)
        history.append(s)
        if stopped(s):
            break
    check('Uno reports stopped after radio request', stopped(history[-1]), history)
    direct = fields(exchange(msp, 'STATUS', 'STATUS BOARD='))
    check('Independent MSP USB confirms stopped', stopped(direct), direct)
    samples = []
    for _ in range(20):
        time.sleep(.15)
        s = fields(exchange(esp, 'ROBOT MSP STATUS', 'ROBOT MSP STATUS'))
        samples.append(s)
        if s.get('BOARD') != 'MSP430F5529':
            break
    check('20 repeated wired status round trips', len(samples) == 20 and
          all(s.get('BOARD') == 'MSP430F5529' and stopped(s) for s in samples), samples)
    check('MSP clock advances in fresh replies', len({s.get('TICKS') for s in samples}) > 1, samples)
    check('UART error counters stable during bridge test', all(all(s.get(k) == direct.get(k)
          for k in ('UART_ERRORS', 'RX_DROPS', 'BAD_FRAMES')) for s in samples), samples)
    time.sleep(1.8)
    r = exchange(esp, 'STATUS', 'STATUS BOARD=')
    check('Old MSP telemetry marked stale', fields(r).get('MSP_LINK') == 'STALE', r)
    r = exchange(esp, 'ROBOT MSP STATUS', 'ROBOT MSP STATUS')
    check('Fresh read restores MSP response', fields(r).get('BOARD') == 'MSP430F5529', r)
    r = exchange(esp, 'STATUS', 'STATUS BOARD=')
    check('MSP freshness restored', fields(r).get('MSP_LINK') == 'UP', r)
    report['passed'] = True
except Exception as exc:
    report['error'] = str(exc)
    print('ERROR ' + str(exc), flush=True)
finally:
    for p in (esp, msp):
        if p:
            p.close()
    path = ROOT / 'Laptop/Artifacts/verification' / f'wired-bridge-{stamp:%Y-%m-%d-%H%M%S}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('REPORT ' + str(path), flush=True)
sys.exit(0 if report['passed'] else 1)
