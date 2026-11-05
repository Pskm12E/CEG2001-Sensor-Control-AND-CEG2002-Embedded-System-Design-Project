"""Read-only desk Pico USB -> ESP Wi-Fi -> main MSP430 telemetry."""
from collections import deque
from datetime import datetime, timezone
import json
import queue
import re
import threading
import time

from camera_usb import serial, list_ports
from camera_radio import RadioCamera, UsbMultiplexer

ALLOWED_COMMANDS = frozenset({"PING", "STATUS"})
STATUS_PATTERN = re.compile(
    r"STATUS BOARD=MSP430F5529 FW=SUPERVISOR_V2 LINK=(READY|SYNCING) RUN=([01]) "
    r"CAL=(NEEDED|SAMPLING|READY) L2=(NC|BLACK|WHITE|UNSTABLE|UNKNOWN) "
    r"R4=(NC|BLACK|WHITE|UNSTABLE|UNKNOWN) LED2=(ON|OFF) "
    r"FLAGS=(\d{1,3}) RESULT=(\d{1,3}) PENDING=(\d{1,3}) "
    r"UART_ERRORS=(\d{1,10}) RX_DROPS=(\d{1,10}) BAD_FRAMES=(\d{1,10}) BRIDGE=ESP_UART_V1"
)
PICO_PATTERN = re.compile(
    r"STATUS BOARD=PICO_W ROLE=LAPTOP_BRIDGE FW=DESK_BRIDGE_V2 LED=ON "
    r"WIFI=(UP|DOWN) ESP_LINK=(UP|DOWN) MSP_LINK=(UP|STALE|NOT_CONNECTED) READ_ONLY=1"
)


class TelemetryError(RuntimeError):
    """Reject robot status without tearing down the independent camera relay."""


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def parse_status(line):
    if not isinstance(line, str):
        return None
    match = STATUS_PATTERN.fullmatch(line)
    if not match:
        return None
    values = match.groups()
    keys = ("uno_link", "run", "calibration", "left", "right", "led2", "flags", "result",
            "pending", "uart_errors", "rx_drops", "bad_frames")
    result = dict(zip(keys, values))
    for key in ("run", "flags", "result", "pending", "uart_errors", "rx_drops", "bad_frames"):
        result[key] = int(result[key])
    if any(result[k] > 255 for k in ("flags", "result", "pending")):
        return None
    return dict(result, board="MSP430F5529", firmware="SUPERVISOR_V2")


def available_ports():
    return [{"device": p.device, "description": "Desk Pico W USB", "suggested": True}
            for p in sorted(list_ports.comports(), key=lambda p: p.device)
            if (p.vid, p.pid) == (0x2E8A, 0x000A)]


class Bridge:
    def __init__(self, hosted=False):
        self.hosted = hosted
        self.lock = threading.RLock()
        self.lifecycle = threading.Lock()
        self.events = deque(maxlen=100)
        self.sequence = 0
        self.connected = False
        self.port = None
        self.error = None
        self.telemetry = None
        self.pico = None
        self.remote = None
        self.identity = False
        self.pico_seen = None
        self.last_seen = None
        self.last_seen_monotonic = None
        self.worker = None
        self.stop = threading.Event()
        self.pending = queue.Queue(maxsize=8)
        self.video=RadioCamera(self)
        self.usb=UsbMultiplexer(self.video.publish,self.video.reject)
        self.event("info", "Hosted preview. Robot hardware is not linked." if hosted else
                   "Connect the desk Pico to read robot status. Wireless camera video also arrives through the Pico.")

    def event(self, kind, message):
        with self.lock:
            self.sequence += 1
            self.events.append({"id": self.sequence, "time": timestamp(), "kind": kind, "message": message})

    def state(self):
        with self.lock:
            now = time.monotonic()
            pico_fresh = self.connected and self.identity and self.pico_seen is not None and now - self.pico_seen < 12
            remote_age = self.remote.get("age_ms") if self.remote else None
            fresh = bool(pico_fresh and self.last_seen_monotonic is not None
                         and type(remote_age) is int
                         and remote_age + (now - self.last_seen_monotonic) * 1000 < 3500)
            links = {"pico": "UP" if pico_fresh else "DOWN", "wifi": "UNKNOWN", "esp": "UNKNOWN",
                     "msp": "UP" if fresh else "STALE", "uno": self.telemetry["uno_link"] if fresh else "UNKNOWN"}
            if pico_fresh and self.pico:
                links.update(wifi=self.pico["wifi"], esp=self.pico["esp"])
            error = self.error
            if self.connected and not fresh and not error:
                error = "Waiting for fresh robot status through the Pico. Check power to the ESP32, MSP430 and Uno."
            return {"mode": "hosted" if self.hosted else "local", "read_only": True,
                    "connection": {"connected": self.connected, "port": self.port, "baud": 115200,
                                   "error": error, "fresh": fresh, "last_seen": self.last_seen},
                    "links": links, "telemetry": dict(self.telemetry) if self.telemetry else None,
                    "events": list(self.events)}

    def connect(self, port):
        if self.hosted:
            raise RuntimeError("Hardware connections are available only in the local dashboard.")
        with self.lifecycle:
            if not isinstance(port, str) or port not in {p["device"] for p in available_ports()}:
                raise ValueError("Select the desk Pico USB port. Uno and MSP430 USB ports are excluded.")
            if self.connected:
                if self.port == port:
                    return
                raise ValueError("Disconnect the current Pico before choosing another port.")
            if self.worker:
                self.stop.set()
                self.worker.join(timeout=2)
                if self.worker.is_alive():
                    raise RuntimeError("The last USB connection is closing. Try again.")
            device = serial.Serial(port=None, baudrate=115200, timeout=.05, write_timeout=.5)
            device.port = port
            device.dtr = True
            device.rts = False
            try:
                device.open()
            except (serial.SerialException, OSError) as exc:
                raise RuntimeError(f"Cannot open {port}. Close the Pico console or other serial monitor and retry.") from exc
            with self.lock:
                self.port, self.connected, self.error = port, True, None
                self.telemetry = self.pico = self.remote = None
                self.last_seen = self.last_seen_monotonic = self.pico_seen = None
                self.identity = False
                self.stop = threading.Event()
                self.pending = queue.Queue(maxsize=8)
                self.usb=UsbMultiplexer(self.video.publish,self.video.reject)
            self.event("connection", f"Opened desk Pico on {port}; verifying firmware.")
            self.worker = threading.Thread(target=self._run, args=(device,), daemon=True)
            self.worker.start()

    def disconnect(self):
        with self.lifecycle:
            was_connected = self.connected
            self.stop.set()
            if self.worker:
                self.worker.join(timeout=2)
                if self.worker.is_alive():
                    raise RuntimeError("The USB connection is closing. Try again.")
            with self.lock:
                self.connected = False
                self.error = None
            if was_connected:
                self.event("connection", "Desk Pico disconnected. Robot readings are no longer live.")

    def command(self, command):
        if not isinstance(command, str) or command not in ALLOWED_COMMANDS:
            raise ValueError("Only read-only PING and STATUS checks are available.")
        with self.lifecycle:
            if not self.connected or not self.identity:
                raise RuntimeError("Connect the desk Pico and wait for its identity check first.")
            try:
                self.pending.put_nowait(command)
            except queue.Full as exc:
                raise RuntimeError("Checks are still pending. Wait for a reply.") from exc
            self.event("command", "Queued " + command)

    def _receive(self, line):
        if line.startswith("STATUS BOARD=PICO_W"):
            match = PICO_PATTERN.fullmatch(line)
            if not match:
                raise RuntimeError("Unexpected Pico status. Use the desk bridge firmware.")
            with self.lock:
                self.pico = dict(zip(("wifi", "esp", "msp"), match.groups()))
                self.pico_seen = time.monotonic()
            return
        if not line.startswith("ROBOT STATE "):
            if line:
                self.event("board", line)
            return
        try:
            remote = json.loads(line[len("ROBOT STATE "):])
            if not isinstance(remote, dict) or remote.get("board") != "ESP32_FIREBEETLE" or remote.get("firmware") != "DIRECT_WIFI_V1" or remote.get("main_controller") != "MSP430F5529":
                raise ValueError("identity")
            age = remote.get("age_ms")
            status = parse_status(remote.get("telemetry", ""))
            valid = (remote.get("fresh") is True and remote.get("msp_link") == "UP"
                     and remote.get("ap_ready") is True and type(age) is int and 0 <= age <= 2500 and status is not None)
        except (ValueError, TypeError) as exc:
            raise TelemetryError("Robot status is unavailable or invalid. Waiting for a fresh reply; video remains connected.") from exc
        with self.lock:
            if not valid:
                self.last_seen_monotonic = None
                self.error = "Robot status is unavailable or stale. Check the ESP32â€“MSP430 UART connection and board power."
                return
            first = self.telemetry is None
            self.telemetry, self.remote = status, remote
            self.last_seen = timestamp()
            self.last_seen_monotonic = time.monotonic()
            self.error = None
        if first:
            self.event("connection", "Fresh MSP430 supervisor status received through Pico Wi-Fi and ESP32 UART.")

    def camera_command(self,command):
        if command not in ('VIDEO ON','VIDEO OFF') or not self.connected or not self.identity:
            raise RuntimeError('Connect the desk Pico before starting wireless video.')
        try:self.pending.put_nowait(command)
        except queue.Full as exc:raise RuntimeError('Pico checks are pending. Try again shortly.') from exc

    def _poll_input(self,device):
        data=device.read(max(1,min(device.in_waiting,8192)))
        if data:self.usb.feed(data)

    def _exchange(self,device,command,prefix,timeout=10):
        # Never flush USB while video is running: text and binary share the same reader.
        device.write((command+'\n').encode('ascii'))
        deadline=time.monotonic()+timeout
        while not self.stop.is_set() and time.monotonic()<deadline:
            while self.usb.lines:
                line=self.usb.lines.popleft()
                if line.startswith((prefix,'ERROR ','ROBOT ERROR ')):return line
                self._receive(line)
            self._poll_input(device)
        if self.stop.is_set():return ''
        raise TimeoutError('No Pico reply. Check its USB cable and robot power, then retry.')

    def _run(self, device):
        try:
            reply = self._exchange(device, "PING", "PONG ", 3)
            if self.stop.is_set():
                return
            if reply != "PONG PICO_DESK_BRIDGE_V2":
                raise RuntimeError("This Pico is not running DESK_BRIDGE_V2. No robot requests were sent.")
            with self.lock:
                self.identity = True
            self.event("board", reply)
            while not self.stop.is_set():
                try:
                    try:
                        command = self.pending.get_nowait()
                    except queue.Empty:
                        command = None
                    if command in ("VIDEO ON","VIDEO OFF"):
                        self.event("camera",self._exchange(device,command,"VIDEO OK",3))
                    elif command == "PING":
                        self.event("board", self._exchange(device, "PING", "PONG ", 3))
                    self._receive(self._exchange(device, "STATUS", "STATUS ", 3))
                    reply = self._exchange(device, "ROBOT STATE", "ROBOT STATE ")
                    if reply.startswith(("ERROR ", "ROBOT ERROR ")):
                        with self.lock:
                            self.last_seen_monotonic = None
                            self.error = "Robot link unavailable: " + reply
                    else:
                        self._receive(reply)
                except (TimeoutError, TelemetryError) as exc:
                    with self.lock:
                        self.error = str(exc)
                        self.last_seen_monotonic = None
                idle_until=time.monotonic()+.5
                while not self.stop.is_set() and time.monotonic()<idle_until:
                    self._poll_input(device)
                    while self.usb.lines:self._receive(self.usb.lines.popleft())
        except (serial.SerialException, OSError, RuntimeError, UnicodeError) as exc:
            with self.lock:
                self.error = str(exc)
            self.event("error", "Desk Pico connection ended: " + str(exc))
        finally:
            try:
                if device.is_open: device.write(b"VIDEO OFF\n")
            except (serial.SerialException,OSError): pass
            device.close()
            self.video.link_down()
            with self.lock:
                self.connected = self.identity = False
