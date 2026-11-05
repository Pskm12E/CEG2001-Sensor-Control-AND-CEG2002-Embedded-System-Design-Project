"""Local blue-square practice detector. Observations only; no robot commands.

The camera remains a continuous wireless stream. A separate worker processes the
newest JPEG without blocking the Pico USB reader or queuing old video frames.
This is HSV/shape detection, not an insect model or a calibrated probability.
"""
from collections import deque
from pathlib import Path
import sys
import threading
import time
import zlib

try:
    import cv2
    import numpy as np
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tmp/vision-python"))
    try:
        import cv2
        import numpy as np
    except ImportError:
        cv2 = np = None

FRESH_SECONDS = 0.75
REQUIRED_FRAMES = 3


def overlap(a, b):
    """Intersection-over-union for [x,y,width,height] boxes."""
    if a is None or b is None:
        return 0
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[0]+a[2], b[0]+b[2]), min(a[1]+a[3], b[1]+b[3])
    intersection = max(0, x2-x1) * max(0, y2-y1)
    return intersection / max(1, a[2]*a[3] + b[2]*b[3] - intersection)


class BlueSquare:
    """Find one blue quadrilateral and confirm it over distinct nearby frames."""
    def __init__(self):
        self.previous = None
        self.streak = 0
        self.last_time = None

    def reset(self):
        self.previous = None
        self.streak = 0
        self.last_time = None

    def process(self, jpeg, now=None):
        now = time.monotonic() if now is None else now
        image = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None or max(image.shape[:2]) > 4096:
            self.reset()
            raise ValueError("Camera image could not be decoded.")
        height, width = image.shape[:2]
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        # OpenCV hue is 0..179. Broad enough for this blue sample under indoor light.
        mask = cv2.inRange(hsv, (90, 85, 45), (135, 255, 255))
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if not max(75, width*height*0.001) <= area <= width*height*0.65:
                continue
            (_, _), (rw, rh), _ = cv2.minAreaRect(contour)
            if min(rw, rh) < 8 or min(rw, rh)/max(rw, rh) < 0.65:
                continue
            if area / max(1, rw*rh) < 0.78:
                continue
            polygon = cv2.approxPolyDP(contour, 0.035*cv2.arcLength(contour, True), True)
            if len(polygon) != 4 or not cv2.isContourConvex(polygon):
                continue
            candidates.append((area, list(cv2.boundingRect(contour))))
        # Prefer the same candidate if several blue squares are visible.
        matching = [c for c in candidates if overlap(c[1], self.previous) >= 0.2]
        candidate = max(matching or candidates, default=None, key=lambda c: c[0])
        box = candidate[1] if candidate else None
        contiguous = self.last_time is not None and 0 <= now-self.last_time <= 0.4
        if box is not None:
            self.streak = min(REQUIRED_FRAMES, self.streak+1) if contiguous and overlap(box, self.previous) >= 0.2 else 1
        else:
            self.streak = 0
        self.previous, self.last_time = box, now
        detected = self.streak >= REQUIRED_FRAMES
        status = "DETECTED" if detected else "CHECKING" if box else "SEARCHING"
        if box:
            x, y, w, h = box
            colour = (80, 240, 130) if detected else (0, 215, 255)
            cv2.rectangle(image, (x, y), (x+w, y+h), colour, 2)
            label = "BLUE TARGET" if detected else f"CHECKING {self.streak}/{REQUIRED_FRAMES}"
            tx, ty = min(x, max(0, width-145)), max(17, y-6)
            cv2.putText(image, label, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(image, label, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.42, colour, 1, cv2.LINE_AA)
        ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            raise ValueError("Detection video could not be encoded.")
        return encoded.tobytes(), dict(status=status, detected=detected, box=box,
                                      centre=[box[0]+box[2]//2, box[1]+box[3]//2] if box else None,
                                      streak=self.streak, required_frames=REQUIRED_FRAMES,
                                      width=width, height=height)


class DetectionVideo:
    """One newest annotated frame, shared by all dashboard viewers."""
    def __init__(self, camera):
        self.camera = camera
        self.condition = threading.Condition()
        self.enabled = False
        self.generation = 0
        self.sequence = 0
        self.jpeg = None
        self.result = None
        self.metadata = None
        self.received = None
        self.times = deque(maxlen=120)
        self.stop_event = None
        self.thread = None
        self.error = None

    def state(self):
        camera = self.camera.state()
        with self.condition:
            now = time.monotonic()
            age = (now-self.received)*1000 if self.received is not None else None
            fresh = bool(self.enabled and camera["streaming"] and age is not None and age < FRESH_SECONDS*1000
                         and self.metadata and camera["generation"] == self.metadata["source_generation"])
            recent = [t for t in self.times if now-t < 2]
            fps = (len(recent)-1)/(recent[-1]-recent[0]) if len(recent)>1 and recent[-1]>recent[0] else 0
            result = self.result if fresh and self.result else {}
            status = "OFF" if not self.enabled else "ERROR" if self.error else result.get("status", "WAITING")
            return dict(available=cv2 is not None, enabled=self.enabled, connected=self.enabled and camera["connected"],
                        generation=self.generation, sequence=self.sequence, fresh=fresh, status=status,
                        detected=bool(result.get("detected", False)), box=result.get("box"), centre=result.get("centre"),
                        streak=result.get("streak", 0), required_frames=REQUIRED_FRAMES,
                        width=result.get("width", camera["width"]), height=result.get("height", camera["height"]),
                        frame_age_ms=round(age) if age is not None else None, fps=round(fps, 1),
                        processing_ms=self.metadata.get("processing_ms") if fresh else None,
                        error=self.error, method="OPENCV_BLUE_SQUARE", source="PICO_WIFI", actuator_control=False)

    def start(self):
        if cv2 is None:
            raise RuntimeError("Blue-target detection is unavailable. Install the dashboard requirements and restart it.")
        if not self.camera.state()["connected"]:
            raise RuntimeError("Start the XIAO camera before enabling detection.")
        with self.condition:
            if self.enabled:
                return
            self.enabled = True
            self.generation += 1
            self.sequence = 0
            self.jpeg = self.result = self.metadata = self.received = None
            self.error = None
            self.times.clear()
            self.stop_event = threading.Event()
            self.thread = threading.Thread(target=self._run, args=(self.generation, self.stop_event), daemon=True)
            self.thread.start()

    def stop(self):
        with self.condition:
            self.enabled = False
            if self.stop_event:
                self.stop_event.set()
            thread = self.thread
            self.jpeg = self.result = self.metadata = self.received = None
            self.error = None
            self.condition.notify_all()
        if thread and thread is not threading.current_thread():
            thread.join(timeout=1)

    def _run(self, generation, stop):
        detector = BlueSquare()
        after, source_generation, last_source_id = 0, None, None
        while not stop.is_set():
            source = self.camera.state()
            if not source["connected"]:
                self.stop()
                return
            if source["generation"] != source_generation:
                after, source_generation = 0, source["generation"]
                last_source_id = None
                detector.reset()
            frame = self.camera.wait_frame(after, source_generation, timeout=0.2)
            if frame is None:
                continue
            jpeg, metadata = frame
            after = metadata["sequence"]
            source_id = metadata["source_sequence"]
            if source_id == last_source_id:
                continue  # Duplicate camera sequence is not another vote.
            if last_source_id is not None and source_id < last_source_id:
                detector.reset()  # Camera restarted or sequence wrapped.
            last_source_id = source_id
            # Do not confirm a target using a stale or repeated frame.
            if not self.camera.state()["streaming"]:
                detector.reset()
                continue
            started = time.perf_counter()
            try:
                annotated, result = detector.process(jpeg)
            except (ValueError, cv2.error):
                detector.reset()
                with self.condition:
                    if generation == self.generation:
                        self.error = "Frame processing failed. Check the camera feed or restart detection."
                        self.result = self.jpeg = None
                continue
            with self.condition:
                if stop.is_set() or generation != self.generation:
                    return
                self.sequence += 1
                self.jpeg, self.result = annotated, result
                self.received = time.monotonic()
                self.times.append(self.received)
                self.error = None
                self.metadata = dict(sequence=self.sequence, source_sequence=after,
                                     source_generation=source_generation, captured_at=metadata["captured_at"],
                                     crc32=f"{zlib.crc32(annotated):08X}", processing_ms=round((time.perf_counter()-started)*1000, 1))
                self.condition.notify_all()

    def wait_frame(self, after, generation, timeout=5):
        with self.condition:
            self.condition.wait_for(lambda: self.sequence > after or not self.enabled or generation != self.generation, timeout)
            if not self.enabled or generation != self.generation or self.sequence <= after or self.jpeg is None:
                return None
            if self.received is None or time.monotonic()-self.received >= FRESH_SECONDS:
                return None
            return self.jpeg, dict(self.metadata)
