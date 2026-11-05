"""Bounded, CRC-checked USB JPEG transport for the XIAO Sense camera.

Standalone stream check: python camera_usb.py --port COM17 --seconds 10
No network, robot commands, continuous recording or automatic disk writes.
"""
from __future__ import annotations

import argparse
import json
from collections import deque
from pathlib import Path
import re
import sys
import threading
import time
import zlib

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tmp/pico-tools-python"))
    import serial
    from serial.tools import list_ports

MAX_FRAME = 512 * 1024
HEADER = re.compile(rb"FRAME TYPE=JPEG BYTES=(\d{1,6}) CRC32=([0-9A-F]{8}) WIDTH=(\d{1,4}) HEIGHT=(\d{1,4})")
INFO = re.compile(r"INFO BOARD=XIAO_ESP32S3 FW=CAMERA_USB_V2 CAMERA_READY=([01]) SENSOR=(OV2640|OV3660|OV5640|OTHER) PID=0x([0-9A-F]{4}) PSRAM_BYTES=(\d+) FRAME=QVGA WIFI=OFF STREAM=(ON|OFF) ERROR=0x([0-9A-F]+)")


def available_camera_ports():
    # USB identities are candidates only. PING + INFO must confirm our firmware.
    return [{"device": p.device, "description": "XIAO camera USB (verify on connect)"}
            for p in sorted(list_ports.comports(), key=lambda p: p.device)
            if (p.vid, p.pid) in {(0x303A, 0x1001), (0x2886, 0x0056)}]


class StreamStopped(RuntimeError):
    pass


def read_line(device, deadline, stop=None):
    data = bytearray()
    while time.monotonic() < deadline:
        if stop is not None and stop.is_set():
            raise StreamStopped()
        char = device.read(1)
        if char == b"\n":
            return bytes(data).rstrip(b"\r")
        if char:
            data.extend(char)
            if len(data) > 512:
                raise RuntimeError("Camera reply is too long. Stop and reconnect the camera.")
    raise RuntimeError("Camera USB reply timed out. Check the cable and reconnect.")


def receive_frame(device, deadline, stop=None):
    """Reject partial/oversized/corrupt frames before exposing any image."""
    for _ in range(20):
        line = read_line(device, deadline, stop)
        if line.startswith(b"ERROR"):
            raise RuntimeError("Camera reported " + line.decode("ascii", "replace"))
        match = HEADER.fullmatch(line)
        if match:
            break
    else:
        raise RuntimeError("No valid camera frame header. Stop and reconnect the camera.")
    length, checksum, width, height = match.groups()
    length, width, height = int(length), int(width), int(height)
    if not 4 <= length <= MAX_FRAME or (width, height) != (320, 240):
        raise RuntimeError("Camera frame size is invalid. Reconnect the camera.")
    data = bytearray()
    while len(data) < length and time.monotonic() < deadline:
        if stop is not None and stop.is_set():
            raise StreamStopped()
        data.extend(device.read(min(4096, length - len(data))))
    if len(data) != length:
        raise RuntimeError("Camera image was incomplete. Reconnect and try again.")
    if zlib.crc32(data) != int(checksum, 16):
        raise RuntimeError("Camera image checksum failed. Check the USB cable and retry.")
    if not data.startswith(b"\xff\xd8") or not data.endswith(b"\xff\xd9"):
        raise RuntimeError("Camera did not return a valid JPEG. Reconnect and retry.")
    if read_line(device, deadline, stop) != b"" or read_line(device, deadline, stop) != b"END FRAME":
        raise RuntimeError("Camera image footer is missing. Reconnect and retry.")
    return bytes(data), {"width": width, "height": height, "bytes": length,
                         "crc32": checksum.decode("ascii")}


class Camera:
    """One continuous USB reader; consumers get the newest frame, never a backlog."""
    def __init__(self):
        self.lifecycle = threading.Lock()
        self.condition = threading.Condition()
        self.device = None
        self.worker = None
        self.stop = threading.Event()
        self.jpeg = None
        self.times = deque(maxlen=120)
        self.received_monotonic = None
        self.generation = 0
        self.value = {"connected": False, "port": None, "sensor": None, "error": None,
                      "sequence": 0, "captured_at": None, "transport": "USB_MJPEG"}

    def state(self):
        with self.condition:
            now = time.monotonic()
            age = (now-self.received_monotonic)*1000 if self.received_monotonic is not None else None
            recent = [t for t in self.times if now-t < 2]
            fps = (len(recent)-1)/(recent[-1]-recent[0]) if len(recent)>1 and recent[-1]>recent[0] else 0
            return dict(self.value, streaming=bool(self.value["connected"] and age is not None and age<2000),
                        fps=round(fps, 1), frame_age_ms=round(age) if age is not None else None,
                        generation=self.generation)

    def connect(self, port):
        with self.lifecycle:
            if not isinstance(port,str) or port not in {p["device"] for p in available_camera_ports()}:
                raise ValueError("Select the XIAO camera USB port. Other boards are excluded.")
            if self.value["connected"]:
                raise RuntimeError("Stop the current camera before connecting again.")
            if self.worker:
                self.stop.set(); self.worker.join(timeout=2)
                if self.worker.is_alive():
                    raise RuntimeError("The previous camera stream is closing. Try again.")
            device=serial.Serial(port=None,baudrate=115200,timeout=.05,write_timeout=.5)
            device.port=port;device.dtr=True;device.rts=False
            try:
                device.open()
                # Quiesce an earlier reader before identity checks, including after a crash.
                device.write(b"STREAM_STOP\n");time.sleep(.2)
                deadline=time.monotonic()+.5
                while device.in_waiting and time.monotonic()<deadline:
                    device.read(min(device.in_waiting,4096))
                device.reset_input_buffer();device.write(b"PING\n")
                deadline=time.monotonic()+3
                for _ in range(20):
                    if read_line(device,deadline)==b"PONG XIAO_CAMERA_USB_V2":break
                else: raise RuntimeError("Use CAMERA_USB_V2 live-stream firmware on the XIAO.")
                device.write(b"INFO\n")
                reply=read_line(device,time.monotonic()+3).decode("ascii","replace")
                match=INFO.fullmatch(reply)
                if not match or match[1]!="1":
                    raise RuntimeError("Camera did not initialise. Check the Sense attachment with power off. "+reply[:220])
                self.device=device;self.stop=threading.Event()
                with self.condition:
                    self.generation+=1;self.jpeg=None;self.times.clear();self.received_monotonic=None
                    self.value.update(connected=True,port=port,sensor=match[2],error=None,sequence=0,captured_at=None,info=reply)
                device.write(b"STREAM_START\n")
                self.worker=threading.Thread(target=self._run,args=(device,),daemon=True)
                self.worker.start()
            except (serial.SerialException,OSError,RuntimeError) as exc:
                device.close()
                with self.condition:
                    self.value.update(connected=False,error=str(exc));self.condition.notify_all()
                raise RuntimeError("Cannot start camera stream: "+str(exc)) from exc

    def _run(self,device):
        try:
            while not self.stop.is_set():
                jpeg,metadata=receive_frame(device,time.monotonic()+3,self.stop)
                now=time.monotonic()
                with self.condition:
                    self.jpeg=jpeg;self.received_monotonic=now;self.times.append(now)
                    self.value.update(metadata,sequence=self.value["sequence"]+1,captured_at=time.time(),error=None)
                    self.condition.notify_all()
        except StreamStopped:
            pass
        except (serial.SerialException,OSError,RuntimeError) as exc:
            if not self.stop.is_set():
                with self.condition:
                    self.value["error"]=str(exc)
        finally:
            try:
                if device.is_open:device.write(b"STREAM_STOP\n")
            except (serial.SerialException,OSError):pass
            device.close()
            with self.condition:
                self.value["connected"]=False;self.condition.notify_all()

    def wait_frame(self,after,generation,timeout=2):
        """A slow browser skips old frames; only one immutable JPEG is retained."""
        with self.condition:
            self.condition.wait_for(lambda: self.value["sequence"]>after or not self.value["connected"] or self.generation!=generation,timeout)
            if not self.value["connected"] or self.generation!=generation or self.value["sequence"]<=after:
                return None
            if self.received_monotonic is None or time.monotonic()-self.received_monotonic>2:
                return None
            return self.jpeg,dict(self.value)

    def image(self):
        with self.condition:
            return self.jpeg if self.value["connected"] else None

    def disconnect(self):
        with self.lifecycle:
            self.stop.set()
            if self.worker:
                self.worker.join(timeout=2)
                if self.worker.is_alive():
                    raise RuntimeError("Camera reader is still closing. Try again.")
            if self.device and self.device.is_open:self.device.close()
            self.device=None
            with self.condition:
                self.jpeg=None;self.received_monotonic=None;self.times.clear()
                self.value.update(connected=False,captured_at=None,error=None)
                self.condition.notify_all()


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port",required=True)
    parser.add_argument("--seconds",type=float,default=10)
    args=parser.parse_args();camera=Camera()
    try:
        camera.connect(args.port);generation=camera.state()["generation"]
        if not camera.wait_frame(0,generation,5):raise SystemExit("No video frames received")
        start=time.monotonic();first=camera.state()["sequence"]
        time.sleep(args.seconds)
        state=camera.state();elapsed=time.monotonic()-start
        print(json.dumps(dict(state,measured_fps=round((state["sequence"]-first)/elapsed,2),measured_seconds=round(elapsed,2)),indent=2))
    finally:camera.disconnect()
