"""Interactive read-only console for the desk Pico W USB bridge."""
from pathlib import Path
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tmp/pico-tools-python'))
import serial
from serial.tools import list_ports

ports=[p for p in list_ports.comports() if (p.vid,p.pid)==(0x2e8a,0x000a)]
if len(ports)!=1:
    raise SystemExit('Connect one Pico W to laptop USB, then run this console again.')
p=serial.Serial(port=None,baudrate=115200,timeout=.1,write_timeout=1)
p.port=ports[0].device; p.dtr=True; p.rts=False
closed=threading.Event()

def receive():
    buf=bytearray()
    try:
        while not closed.is_set():
            buf.extend(p.read(p.in_waiting or 1))
            while b'\n' in buf:
                raw,_,rest=buf.partition(b'\n');buf=bytearray(rest)
                line=raw.decode('ascii','backslashreplace').strip()
                if line: print(line,flush=True)
    except (serial.SerialException,OSError) as exc:
        if not closed.is_set(): print('USB disconnected: '+str(exc),flush=True)
        closed.set()

try:
    p.open(); time.sleep(.2)
    p.reset_input_buffer(); p.write(b'PING\n')
    end=time.monotonic()+2; identity=bytearray()
    while time.monotonic()<end and b'PONG PICO_DESK_BRIDGE_V2\n' not in identity.replace(b'\r',b''):
        identity.extend(p.read(p.in_waiting or 1))
    if b'PONG PICO_DESK_BRIDGE_V2\n' not in identity.replace(b'\r',b''):
        raise SystemExit('This Pico is not running the desk bridge. No further commands sent.')
    print('Desk Pico connected on '+p.port+' at 115200 baud.')
    print('Type STATUS or ROBOT MSP STATUS, then Enter. Type Q to close.')
    print('Read-only: motor, spray, STOP and calibration commands are unavailable.')
    reader=threading.Thread(target=receive,daemon=True);reader.start()
    p.write(b'STATUS\n')
    while not closed.is_set():
        command=input().strip().upper()
        if command in ('Q','QUIT','EXIT'): break
        if command not in ('PING','STATUS','ROBOT PING','ROBOT STATE','ROBOT MSP STATUS','HELP','DIAG'):
            print('Use STATUS, ROBOT MSP STATUS, ROBOT STATE, PING, ROBOT PING, HELP, DIAG or Q.')
            continue
        p.write((command+'\n').encode('ascii'))
except (KeyboardInterrupt,EOFError):
    pass
except (serial.SerialException,OSError) as exc:
    print('Cannot open Pico USB. Close other serial monitors and try again. '+str(exc))
finally:
    closed.set()
    if p.is_open: p.close()
