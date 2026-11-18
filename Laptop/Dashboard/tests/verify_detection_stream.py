"""Check the detector worker on live video with its robot callback disconnected.

Start the camera first. This script makes only GET requests, holds no serial
port and never enables the dashboard target-job path. Other active clients keep
their existing settings; the private test worker has no robot callback.
"""
from datetime import datetime
import json
from pathlib import Path
import statistics
import sys
import time
from urllib.request import urlopen
from types import SimpleNamespace
import zlib

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'Laptop/Dashboard'))
from blue_detector import DetectionVideo, cv2, np
from camera_radio import RadioCamera

report = dict(tested_at=datetime.now().astimezone().isoformat(), passed=False,
              images_saved=False, actuator_commands_sent=False, method='OPENCV_BLUE_SQUARE')
frames, robot_updates, processing = [], set(), []
confirmed = 0
camera = RadioCamera(SimpleNamespace())
camera.enabled = camera.value['connected'] = True
camera.generation = 1
detector = DetectionVideo(camera)  # No on_observation callback: cannot send jobs.


def live_state():
    with urlopen('http://127.0.0.1:8765/api/state', timeout=3) as response:
        value = json.load(response)
    return value


try:
    state = live_state()
    assert state['camera']['streaming'], 'Start the XIAO camera first.'
    detector.start()
    after = 0
    with urlopen('http://127.0.0.1:8765/api/camera/stream', timeout=5) as response:
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
            source = int(headers['x-sequence'])
            camera.publish(jpeg, source, headers['x-crc32'])
            frame = detector.wait_frame(after, detector.generation, timeout=1)
            assert frame is not None, 'Detector worker did not produce a fresh image.'
            annotated, metadata = frame
            assert f'{zlib.crc32(annotated):08X}' == metadata['crc32']
            image = cv2.imdecode(np.frombuffer(annotated, np.uint8), cv2.IMREAD_COLOR)
            assert image is not None and image.shape[:2] == (240,320)
            after = metadata['sequence']
            frames.append((source, time.monotonic()))
            processing.append(metadata['processing_ms'])
            confirmed += detector.state()['detected']
            if index % 25 == 0:
                state = live_state()
                if state['connection']['fresh']:
                    robot_updates.add(state['connection']['last_seen'])
    assert all(b[0] > a[0] for a,b in zip(frames,frames[1:]))
    fps = (len(frames)-1)/(frames[-1][1]-frames[0][1])
    assert fps >= 8, f'Only {fps:.2f} fps'
    state = live_state()
    assert detector.state()['fresh']
    assert not detector.state()['actuator_control']
    assert len(robot_updates) >= 2, 'No independent fresh robot status updates during video'
    report.update(passed=True,frames=len(frames),fps=round(fps,2),
                  distinct_robot_updates=len(robot_updates),detection=detector.state(),
                  confirmed_frames=confirmed,processing_ms_median=round(statistics.median(processing),2),
                  callback_disconnected=True,dashboard_detection_enabled=state['detection']['enabled'],
                  camera=state['camera'],robot_connection=state['connection'])
except Exception as exc:
    report['error'] = str(exc)
finally:
    detector.stop()
path=ROOT/'Laptop/Artifacts/verification'/f'blue-detection-stream-{datetime.now():%Y-%m-%d-%H%M%S}.json'
path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
print(path)
raise SystemExit(0 if report['passed'] else 1)
