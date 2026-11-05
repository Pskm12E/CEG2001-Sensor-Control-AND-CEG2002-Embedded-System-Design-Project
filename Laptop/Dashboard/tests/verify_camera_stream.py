"""Measure the real continuous MJPEG relay; does not save images or command motors."""
from datetime import datetime
import json
from pathlib import Path
import statistics
import time
from urllib.request import urlopen
import zlib

ROOT=Path(__file__).resolve().parents[3]
URL='http://127.0.0.1:8765'
report={'tested_at':datetime.now().astimezone().isoformat(),'passed':False,
        'transport':'XIAO Wi-Fi -> ESP32 private AP -> desk Pico USB -> one local MJPEG response',
        'images_saved':False,'actuator_commands_sent':False}
frames=[]
try:
    with urlopen(URL+'/api/camera/stream',timeout=5) as response:
        assert response.headers['Content-Type']=='multipart/x-mixed-replace; boundary=robot-frame'
        start=time.monotonic()
        for _ in range(200):
            assert response.readline()==b'--robot-frame\r\n'
            headers={}
            while True:
                line=response.readline()
                if line==b'\r\n':break
                name,value=line.decode('ascii').split(':',1);headers[name.lower()]=value.strip()
            size=int(headers['content-length']);assert 4<=size<=512*1024
            jpeg=response.read(size)
            assert response.read(2)==b'\r\n'
            assert jpeg[:2]==b'\xff\xd8' and jpeg[-2:]==b'\xff\xd9'
            assert f'{zlib.crc32(jpeg):08X}'==headers['x-crc32']
            frames.append({'sequence':int(headers['x-sequence']),'time':time.monotonic(),
                           'relay_age_ms':(time.time()-float(headers['x-received-at']))*1000,
                           'bytes':size})
    fps=(len(frames)-1)/(frames[-1]['time']-frames[0]['time'])
    ages=[f['relay_age_ms'] for f in frames]
    assert fps>=8,f'Expected at least 8 fps; measured {fps:.2f}'
    assert all(b['sequence']>a['sequence'] for a,b in zip(frames,frames[1:]))
    report.update(passed=True,frames=len(frames),fps=round(fps,2),
                  median_relay_age_ms=round(statistics.median(ages),2),
                  max_relay_age_ms=round(max(ages),2),seconds=round(time.monotonic()-start,2),
                  scope='Relay age is laptop USB receive to HTTP client, not lens-to-display latency.')
    with urlopen(URL+'/api/state',timeout=3) as response:
        state=json.load(response)
        report['camera_state']=state['camera'];report['robot_connection']=state['connection']
        assert state['camera']['transport']=='WIFI_VIA_PICO'
        assert state['camera']['corrupt_frames']==0
except Exception as exc:
    report['error']=str(exc)
finally:
    path=ROOT/'Laptop/Artifacts/verification'/f'camera-live-stream-{datetime.now():%Y-%m-%d-%H%M%S}.json'
    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2));print(path)
raise SystemExit(0 if report['passed'] else 1)
