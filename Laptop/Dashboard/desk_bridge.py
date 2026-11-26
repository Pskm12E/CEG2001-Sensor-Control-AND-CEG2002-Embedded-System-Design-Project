"""Desk Pico video/status relay and bounded MSP-owned target jobs."""
from collections import deque
from datetime import datetime, timezone
import json
import queue
import re
import threading
import time

from camera_usb import serial, list_ports
from camera_radio import RadioCamera, UsbMultiplexer
from dock_relay import DockRelay
import tank_scale

ALLOWED_COMMANDS = frozenset({"PING", "STATUS"})
STATUS_PATTERN = re.compile(
    r"STATUS BOARD=MSP430F5529 FW=SUPERVISOR_V2 LINK=(READY|SYNCING) RUN=([01]) "
    r"CAL=(NEEDED|SAMPLING|READY) L2=(NC|BLACK|WHITE|UNSTABLE|UNKNOWN) "
    r"R4=(NC|BLACK|WHITE|UNSTABLE|UNKNOWN) LED2=(ON|OFF) "
    r"FLAGS=(\d{1,3}) RESULT=(\d{1,3}) PENDING=(\d{1,3}) "
    r"UART_ERRORS=(\d{1,10}) RX_DROPS=(\d{1,10}) BAD_FRAMES=(\d{1,10}) BRIDGE=ESP_UART_V1"
)
ZUMO_STATUS_PATTERN = re.compile(
    r"STATUS BOARD=MSP430F5529 FW=SUPERVISOR_V2 LINK=(READY|SYNCING) RUN=([01]) "
    r"CAL=(NEEDED|SAMPLING|READY) BASE=ZUMO LINE=BLACK LED2=(ON|OFF) "
    r"FLAGS=(\d{1,3}) RESULT=(\d{1,3}) PENDING=(\d{1,3}) "
    r"UART_ERRORS=(\d{1,10}) RX_DROPS=(\d{1,10}) BAD_FRAMES=(\d{1,10})"
    r"(?: JOB=(\d) JOB_ID=(\d{1,10}) PUMP=([01]) READY=([01]) WATER=(\d{1,4})"
    r"(?: DOCK=(\d{1,10}) WET=([01]) DCLEAR=([01])(?: RFMIN=(\d{1,4}))?)?)? BRIDGE=ESP_UART_V1"
)
PICO_PATTERN = re.compile(
    r"STATUS BOARD=PICO_W ROLE=LAPTOP_BRIDGE FW=DESK_BRIDGE_V2 LED=ON "
    r"WIFI=(UP|DOWN) ESP_LINK=(UP|DOWN) MSP_LINK=(UP|STALE|NOT_CONNECTED) READ_ONLY=1"
)
PICO_JOB_PATTERN = re.compile(
    r"STATUS BOARD=PICO_W ROLE=LAPTOP_BRIDGE FW=DESK_BRIDGE_V3 LED=ON "
    r"WIFI=(UP|DOWN) ESP_LINK=(UP|DOWN) MSP_LINK=(UP|STALE|NOT_CONNECTED) READ_ONLY=0 TARGET_JOBS=1"
)


class ActionPriority(Exception):
    """Interrupt a telemetry read to dispatch a fresh target request."""


class TelemetryError(RuntimeError):
    """Reject robot status without tearing down the independent camera relay."""


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def parse_status(line):
    if not isinstance(line, str):
        return None
    match = STATUS_PATTERN.fullmatch(line)
    keys = ("uno_link", "run", "calibration", "left", "right", "led2", "flags", "result",
            "pending", "uart_errors", "rx_drops", "bad_frames")
    if match:
        result = dict(zip(keys, match.groups()))
    else:
        match = ZUMO_STATUS_PATTERN.fullmatch(line)
        if not match:
            return None
        keys = ("uno_link", "run", "calibration", "led2", "flags", "result",
                "pending", "uart_errors", "rx_drops", "bad_frames")
        result = dict(zip(keys, match.groups()[:10]), base="ZUMO", line="BLACK", left=None, right=None)
        job = match.groups()[10:15]
        if job and job[0] is not None:
            values = list(map(int, job))
            if values[0] > 8 or values[1] > 4294967295 or values[4] > 4095:
                return None
            result.update(zip(("job", "job_id", "pump", "driver_ready", "water_raw"), values))
            visit, wet, clear, minimum = match.groups()[15:]
            if visit is not None:
                if int(visit) > 0xffffffff:
                    return None
                result.update(dock_visit=int(visit), wet=int(wet), dock_clear=int(clear))
            if minimum is not None:
                if not 1 <= int(minimum) <= 4096:
                    return None
                result["refill_min_raw"] = int(minimum)
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
    def __init__(self):
        self.tank_calibration = tank_scale.load()
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
        self.target_supported = False
        self.action_pending = threading.Event()
        self.target_action = {"state": "IDLE", "error": None, "request_id": None}
        self.action_at = 0
        self.target_latched = False
        self.target_absent_since = None
        self.last_observation = None
        self.resume_requested = False
        self.action_command = "ROBOT TARGET"
        self.pico_seen = None
        self.last_seen = None
        self.last_seen_monotonic = None
        self.worker = None
        self.stop = threading.Event()
        self.pending = queue.Queue(maxsize=8)
        self.dock = DockRelay(self)
        self.dock_pending = None
        self.next_tank_sync = 0
        self.dock_stop_sent = threading.Event()
        self.dock_stop_sent.set()
        self.video=RadioCamera(self)
        self.usb=UsbMultiplexer(self.video.publish,self.video.reject)
        self.event("info", "Connect the desk Pico to read robot status. Wireless camera video also arrives through the Pico.")

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
            return {"mode": "local", "read_only": not self.target_supported,
                    "target_jobs": self.target_supported,
                    "target_action": dict(self.target_action),
                    "connection": {"connected": self.connected, "port": self.port, "baud": 115200,
                                   "error": error, "fresh": fresh, "last_seen": self.last_seen},
                    "tank_calibration": self.tank_calibration, "dock": self.dock.snapshot(now),
                    "links": links, "telemetry": dict(self.telemetry) if self.telemetry else None,
                    "events": list(self.events)}

    def set_tank_calibration(self, points):
        with self.lock:
            if self.dock.token and self.dock.release_raw is not None:
                raise ValueError("Wait until the current docking visit ends to change tank calibration.")
            try:
                tank_scale.save(points)
            except OSError as exc:
                raise RuntimeError("Could not save tank calibration on this laptop.") from exc
            self.tank_calibration = dict(points)

    def connect(self, port):
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
                self.target_supported = False
                self.action_pending.clear()
                self.target_action = {"state": "IDLE", "error": None, "request_id": None}
                self.target_latched = False
                self.target_absent_since = None
                self.last_observation = None
                self.resume_requested = False
                self.action_command = "ROBOT TARGET"
                self.stop = threading.Event()
                self.pending = queue.Queue(maxsize=8)
                self.usb=UsbMultiplexer(self.video.publish,self.video.reject)
            self.event("connection", f"Opened desk Pico on {port}; verifying firmware.")
            self.worker = threading.Thread(target=self._run, args=(device,), daemon=True)
            self.worker.start()

    def disconnect(self):
        with self.lifecycle:
            self.dock.close()
            if self.worker and self.worker.is_alive():
                self.dock_stop_sent.wait(timeout=1)
            was_connected = self.connected
            if self.worker and self.worker.is_alive() and self.action_command == "ROBOT STOP":
                deadline = time.monotonic()+2
                while time.monotonic()<deadline and self.target_action["state"] not in {"CANCELLED", "ABORTED", "UNKNOWN"}:
                    time.sleep(.02)
            self.stop.set()
            self.action_pending.clear()
            if self.worker:
                self.worker.join(timeout=2)
                if self.worker.is_alive():
                    raise RuntimeError("The USB connection is closing. Try again.")
            with self.lock:
                self.connected = False
                self.dock_pending = None
                self.target_supported = False
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
            match = PICO_PATTERN.fullmatch(line) or PICO_JOB_PATTERN.fullmatch(line)
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
            if not isinstance(remote, dict) or remote.get("board") != "ESP32_FIREBEETLE" or remote.get("firmware") not in {"DIRECT_WIFI_V1", "DIRECT_WIFI_V2"} or remote.get("main_controller") != "MSP430F5529":
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
            action_id = self.target_action.get("request_id")
            if action_id and remote.get("target_id") == action_id and type(remote.get("target_id")) is int:
                if remote.get("target_state") == "REFUSED":
                    self.target_action.update(state="REFUSED", error="MSP refused the target job; pump not started.")
                elif remote.get("target_state") == "REQUEST_ACCEPTED" and status.get("job_id") == action_id:
                    names = {1: "STOPPING", 2: "STOPPING", 3: "SETTLING", 4: "SPRAYING",
                             5: "RESUMING", 6: "COMPLETE", 7: "ABORTED", 8: "DRIVER_DISABLED"}
                    phase = names.get(status.get("job"))
                    if phase:
                        detail = ("Pump driver is disabled; robot stays stopped." if phase == "DRIVER_DISABLED"
                                  else "Cycle cancelled; use the Zumo button after checking the robot." if phase == "ABORTED" else None)
                        self.target_action.update(state=phase, error=detail)
                        if (phase == "RESUMING" and not self.resume_requested
                                and self.last_observation is not None
                                and time.monotonic()-self.last_observation < .75 and age < 750
                                and self.video.state()["streaming"]
                                and status["pump"] == 0 and status["driver_ready"] == 1):
                            self.resume_requested = True
                            self.action_command = f"ROBOT RESUME {action_id}"
                            self.action_at = time.monotonic()
                            self.action_pending.set()
            stop_id = self.target_action.get("stop_request_id")
            if (stop_id and type(remote.get("stop_id")) is int and remote.get("stop_id") == stop_id
                    and remote.get("stop_state") == "REQUEST_ACCEPTED"
                    and not status["run"] and not (status["flags"] & 8)):
                self.target_action.update(state="CANCELLED", error=None)
        if first:
            self.event("connection", "Fresh MSP430 supervisor status received through Pico Wi-Fi and ESP32 UART.")

    def observe_target(self, observation):
        """One job per target appearance; require one second of fresh absence to rearm."""
        now = time.monotonic()
        with self.lock:
            self.last_observation = now
            if not observation.get("detected"):
                if observation.get("box") is None:
                    if self.target_absent_since is None:
                        self.target_absent_since = now
                    elif now-self.target_absent_since >= 1:
                        self.target_latched = False
                else:
                    self.target_absent_since = None
                return
            self.target_absent_since = None
            if self.target_latched or self.action_pending.is_set():
                return
            active = {"SENT", "STOPPING", "SETTLING", "SPRAYING", "RESUMING"}
            if self.target_action["state"] in active and now-self.action_at < 10:
                return
            live = self.state()
            if (not self.target_supported or not self.identity or not live["connection"]["fresh"]
                    or not self.remote or self.remote.get("firmware") != "DIRECT_WIFI_V2"
                    or not self.telemetry or "job" not in self.telemetry):
                self.target_action.update(state="UNAVAILABLE", error="Target control needs updated Pico, ESP32 and MSP firmware with a live robot link.")
                return
            if self.telemetry.get("base") != "ZUMO" or not self.telemetry["run"]:
                self.target_action.update(state="WAIT_DRIVING", error=None)
                return
            self.target_latched = True
            self.action_at = now
            self.action_command = "ROBOT TARGET"
            self.resume_requested = False
            self.target_action = {"state": "QUEUED", "error": None, "request_id": None}
            self.action_pending.set()
        self.event("target", "Blue target confirmed; requesting MSP stop/spray/resume cycle.")

    def _send_target(self, device):
        with self.lock:
            self.action_pending.clear()
            command = self.action_command
            if command != "ROBOT STOP" and time.monotonic()-self.action_at >= .75:
                self.target_action.update(state="EXPIRED", error="Target request expired before dispatch; nothing replayed.")
                return
        try:
            prefix = " ".join(command.split()[:2])
            reply = self._exchange(device, command, prefix + " ", 9)
            match = re.fullmatch(re.escape(prefix) + r" SENT ID=([1-9]\d{0,9})", reply)
            if not match or int(match[1]) > 4294967295:
                raise RuntimeError("Target request not confirmed: " + reply)
            with self.lock:
                if command == "ROBOT TARGET":
                    self.target_action.update(state="SENT", request_id=int(match[1]), error=None)
                elif command == "ROBOT STOP":
                    self.target_action.update(state="CANCELLING", stop_request_id=int(match[1]), error=None)
                else:
                    self.target_action.update(state="RESUMING", resume_request_id=int(match[1]), error=None)
        except (RuntimeError, TimeoutError) as exc:
            with self.lock:
                self.target_action.update(state="UNKNOWN", error=str(exc) + " No automatic replay.")
            self.event("error", self.target_action["error"])

    def cancel_target(self):
        with self.lock:
            self.last_observation = None
            if not self.connected or not self.target_supported:
                return
            if self.target_action["state"] in {"IDLE", "WAIT_DRIVING", "COMPLETE", "ABORTED", "DRIVER_DISABLED", "CANCELLED", "UNAVAILABLE"}:
                return
            if self.target_action["state"] == "QUEUED":
                self.action_pending.clear()
                self.target_action.update(state="CANCELLED", error=None)
                return
            self.action_at = time.monotonic()
            self.action_command = "ROBOT STOP"
            self.target_action.update(state="CANCELLING", error=None)
            self.action_pending.set()

    def camera_command(self,command):
        if command not in ('VIDEO ON','VIDEO OFF') or not self.connected or not self.identity:
            raise RuntimeError('Connect the desk Pico before starting wireless video.')
        try:self.pending.put_nowait(command)
        except queue.Full as exc:raise RuntimeError('Pico checks are pending. Try again shortly.') from exc

    def dock_command(self, command):
        with self.lock:
            if not self.connected or not self.identity:
                return
            if self.dock_pending and self.dock_pending[0] == "ROBOT STOP":
                return
            if command == "ROBOT STOP":
                self.dock_stop_sent.clear()
            self.dock_pending = (command, time.monotonic())

    def _send_dock(self, device):
        with self.lock:
            request, self.dock_pending = self.dock_pending, None
        if not request:
            return
        command, created = request
        if command != "ROBOT STOP" and time.monotonic()-created > .75:
            return
        prefix = " ".join(command.split()[:2]) + " "
        try:
            reply = self._exchange(device, command, prefix, 1)
            if " SENT ID=" not in reply:
                self.event("error", reply)
        finally:
            if command == "ROBOT STOP":
                self.dock_stop_sent.set()

    def _poll_input(self,device):
        data=device.read(max(1,min(device.in_waiting,8192)))
        if data:self.usb.feed(data)

    def _sync_tank(self, device):
        with self.lock:
            car = self.telemetry or {}
            desired = tank_scale.departure_raw(self.tank_calibration) or 4096
            now = time.monotonic()
            if (not self.target_supported or not self.state()["connection"]["fresh"]
                    or car.get("refill_min_raw") in (None, desired) or car.get("run") != 0
                    or car.get("pump") != 0 or self.dock.token or self.dock_pending
                    or self.action_pending.is_set() or now < self.next_tank_sync):
                return
            self.next_tank_sync = now + 8
        # The next MSP status echoes the installed cutoff. Older radio firmware
        # can reject this optional setting while continuing normal telemetry.
        try:
            self._exchange(device, f"ROBOT RFMIN {desired}", "ROBOT RFMIN ", 1)
        except TimeoutError:
            pass  # Keep fresh robot telemetry while waiting for the next retry.

    def _exchange(self,device,command,prefix,timeout=10):
        # Never flush USB while video is running: text and binary share the same reader.
        device.write((command+'\n').encode('ascii'))
        deadline=time.monotonic()+timeout
        while not self.stop.is_set() and time.monotonic()<deadline:
            is_action = command.startswith(("ROBOT TARGET", "ROBOT STOP", "ROBOT RESUME ", "ROBOT DOCK ", "ROBOT DEPART ", "ROBOT APPROACH"))
            dock_request = self.dock_pending
            if dock_request and (not is_action or
                    (dock_request[0].startswith(("ROBOT DOCK ", "ROBOT STOP")) and
                     command != "ROBOT STOP" and command != dock_request[0])):
                raise ActionPriority()
            if self.action_pending.is_set() and command != self.action_command and not command.startswith(("ROBOT DOCK ", "ROBOT STOP")):
                raise ActionPriority()
            while self.usb.lines:
                line=self.usb.lines.popleft()
                if line.startswith(prefix):return line
                if not is_action and line.startswith(('ERROR ','ROBOT ERROR ')):return line
                self._receive(line)
            self._poll_input(device)
        if self.stop.is_set():return ''
        raise TimeoutError('No Pico reply. Check its USB cable and robot power, then retry.')

    def _run(self, device):
        try:
            reply = self._exchange(device, "PING", "PONG ", 3)
            if self.stop.is_set():
                return
            if reply not in {"PONG PICO_DESK_BRIDGE_V2", "PONG PICO_DESK_BRIDGE_V3"}:
                raise RuntimeError("This Pico is not running desk bridge firmware. No robot requests were sent.")
            with self.lock:
                self.identity = True
                self.target_supported = reply == "PONG PICO_DESK_BRIDGE_V3"
            self.event("board", reply)
            while not self.stop.is_set():
                try:
                    if self.dock_pending:
                        self._send_dock(device)
                    if self.action_pending.is_set():
                        self._send_target(device)
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
                        self._sync_tank(device)
                except ActionPriority:
                    continue
                except (TimeoutError, TelemetryError) as exc:
                    with self.lock:
                        self.error = str(exc)
                        self.last_seen_monotonic = None
                idle_until=time.monotonic()+.5
                while not self.stop.is_set() and time.monotonic()<idle_until:
                    if self.action_pending.is_set() or self.dock_pending:break
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
