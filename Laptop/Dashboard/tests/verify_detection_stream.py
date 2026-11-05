"""Live annotated-video check. No images saved and no actuator commands sent."""
from datetime import datetime
import json
from pathlib import Path
import statistics
import sys
import time
from urllib.request import urlopen
import zlib

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'Laptop/Dashboard'))
from blue_detector import cv2, np

report = dict(tested_at=datetime.now().astimezone().isoformat(), passed=False,
              images_saved=False, actuator_commands_sent=False, method='OPENCV_BLUE_SQUARE')
frames, robot_updates = [], set()
try:
    with urlopen('http://127.0.0.1:8765/api/detection/stream', timeout=5) as response:
        assert response.headers['Content-Type'].startswith('multipart/x-mixed-replace')
        for index in range(150):
            assert response.readline() == b'--robot-frame\r\n'
            headers = {}
            while True:
                line = response.readline()
                if line == b'\r\n':
                    break
                key, value = line.decode('ascii').split(':', 1)
                headers[key.lower()] = value.strip()
            size = int(headers['content-length'])
            assert 4 <= size <= 512*1024
            jpeg = response.read(size)
            assert response.read(2) == b'\r\n'
            assert f'{zlib.crc32(jpeg):08X}' == headers['x-crc32']
            image = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
            assert image is not None and image.shape[:2] == (240,320)
            frames.append((int(headers['x-sequence']), time.monotonic()))
            if index % 25 == 0:
                with urlopen('http://127.0.0.1:8765/api/state',timeout=3) as state_response:
                    state = json.load(state_response)
                if state['connection']['fresh']:
                    robot_updates.add(state['connection']['last_seen'])
    assert all(b[0] > a[0] for a,b in zip(frames,frames[1:]))
    fps = (len(frames)-1)/(frames[-1][1]-frames[0][1])
    assert fps >= 8, f'Only {fps:.2f} fps'
    with urlopen('http://127.0.0.1:8765/api/state',timeout=3) as response:
        state = json.load(response)
    assert state['detection']['enabled'] and state['detection']['fresh']
    assert not state['detection']['actuator_control']
    assert len(robot_updates) >= 2, 'No independent fresh robot status updates during video'
    report.update(passed=True,frames=len(frames),fps=round(fps,2),
                  distinct_robot_updates=len(robot_updates),detection=state['detection'],
                  camera=state['camera'],robot_connection=state['connection'])
except Exception as exc:
    report['error'] = str(exc)
path=ROOT/'Laptop/Artifacts/verification'/f'blue-detection-stream-{datetime.now():%Y-%m-%d-%H%M%S}.json'
path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
print(path)
raise SystemExit(0 if report['passed'] else 1)
