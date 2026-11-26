"""Coordinate the station's USB visit with the car supervisor's stop acknowledgement."""
import math
import re
import secrets
import threading
import time

from camera_usb import serial, list_ports
from tank_scale import departure_raw


PHASE_RECORD = re.compile(r"DOCK1 (\d{1,5}) (BOOT|CLEAR|ARRIVAL|SETTLE|FILL|DONE|FAULT)")
HALL_RECORD = re.compile(r"HALL1 ([01?]) PUMP=([01])")
DEPARTURE_PAUSE_SECONDS = 3


class DockRelay:
    def __init__(self, bridge):
        self.bridge = bridge
        self.port = None
        self.worker = None
        self.stop = threading.Event()
        self.phase = "DISCONNECTED"
        self.armed = False
        self.visit = self.token = 0
        self.acknowledged = self.departing = False
        self.last_request = 0
        self.next_clear = 0
        self.sensor = None
        self.release_raw = None
        self.depart_at = None

    def snapshot(self, now):
        sample = self.sensor
        fresh = bool(sample and now - sample[0] < 3 and self.phase != "DISCONNECTED")
        depart_at = self.depart_at
        wait = max(0, math.ceil(depart_at - now)) if fresh and depart_at is not None else None
        return {"port": self.port, "phase": self.phase, "departure_wait_s": wait,
                "docked": sample[1] if fresh else None, "pump": sample[2] if fresh else None,
                "sensor_fresh": fresh}

    def connect(self, port):
        if self.worker and self.worker.is_alive():
            if self.port == port or port == "AUTO":
                return
            raise ValueError("Disconnect the station before choosing another port.")
        if not self.bridge.connected or not self.bridge.identity:
            raise ValueError("Connect the desk Pico first.")
        if port != "AUTO" and (port == self.bridge.port or not isinstance(port, str)
                               or not re.fullmatch(r"COM[1-9]\d*", port, re.I)):
            raise ValueError("Choose the station's application UART COM port.")
        self.sensor = None
        self.next_clear = 0
        self.armed = self.acknowledged = self.departing = False
        self.visit = self.token = 0
        self.release_raw = None
        self.depart_at = None
        self.stop.clear()
        if port == "AUTO":
            self.port, self.phase = None, "SEARCHING"
            self.worker = threading.Thread(target=self._discover, daemon=True)
            self.worker.start()
            return
        try:
            device = serial.Serial(port, 9600, timeout=.15, write_timeout=.25)
            device.reset_input_buffer()
        except (serial.SerialException, OSError) as exc:
            raise RuntimeError(f"Cannot open station USB on {port}. Close its serial terminal.") from exc
        self.port = port
        self.phase = "WAITING_FOR_STATION"
        self.worker = threading.Thread(target=self._run, args=(device,), daemon=True)
        self.worker.start()

    def _discover(self):
        # Car and station LaunchPads have identical USB IDs. Listen for the
        # station protocol before sending anything, and leave debug ports alone.
        try:
            for port in list_ports.comports():
                if (port.vid, port.pid) != (0x2047, 0x0013) or "application" not in (port.description or "").lower():
                    continue
                try:
                    with serial.Serial(port.device, 9600, timeout=.15, write_timeout=.25) as device:
                        device.reset_input_buffer()
                        deadline = time.monotonic() + 1.5
                        while not self.stop.is_set() and time.monotonic() < deadline:
                            line = device.read_until(b"\n", 128).decode("ascii", "replace").strip()
                            if PHASE_RECORD.fullmatch(line):
                                self.port, self.phase = port.device, "WAITING_FOR_STATION"
                                self._run(device)
                                return
                except (OSError, serial.SerialException):
                    continue
                if self.stop.is_set():
                    break
        finally:
            self.phase = "DISCONNECTED"

    def close(self):
        self.stop.set()
        if self.worker:
            self.worker.join(timeout=1)

    def _cancel(self):
        if self.token:
            self.bridge.dock_command("ROBOT STOP")
        self.armed = False
        self.visit = self.token = 0
        self.acknowledged = self.departing = False
        self.release_raw = None
        self.depart_at = None

    def sample(self, line, device, now):
        hall = HALL_RECORD.fullmatch(line)
        if hall:
            if hall[1] != "1" or hall[2] != "0":
                self.depart_at = None
            self.sensor = (now, {"0": False, "1": True, "?": None}[hall[1]], hall[2] == "1")
            return False  # Only DOCK1 counts as a control heartbeat.
        match = PHASE_RECORD.fullmatch(line)
        if not match or int(match[1]) > 65535:
            return False
        visit, phase = int(match[1]), match[2]
        if phase != self.phase:
            self.bridge.event("dock", f"Station {phase.lower()} on visit {visit}.")
        self.phase = phase
        if phase != "DONE" or visit != self.visit:
            self.depart_at = None
        if phase in {"BOOT", "FAULT", "CLEAR"}:
            if self.departing and phase != "BOOT":
                self.token = 0  # A departing car normally removes the magnet.
            self._cancel()
            self.armed = phase == "CLEAR"
            if self.armed and now >= self.next_clear:
                self.bridge.dock_command("ROBOT APPROACH")
                self.next_clear = now + 1.25
            return True
        if phase == "ARRIVAL" and self.armed and visit:
            self.armed = False
            self.visit = visit
            self.token = secrets.randbelow(0xffffffff) + 1
            self.last_request = now
            self.bridge.dock_command(f"ROBOT DOCK {self.token}")
        if not self.token or self.visit != visit:
            return True
        state = self.bridge.state()
        car = state["telemetry"] or {}
        held = (state["connection"]["fresh"] and car.get("dock_visit") == self.token
                and car.get("uno_link") == "READY" and car.get("run") == 0
                and car.get("calibration") == "READY" and car.get("pump") == 0)
        if held:
            self.acknowledged = True
            station = self.snapshot(now)
            if self.release_raw is None:
                self.release_raw = departure_raw(state.get("tank_calibration"))
            if station["docked"] is not True or self.release_raw is None:
                self.depart_at = None
                return True
            raw = car.get("water_raw")
            enough = car.get("wet") == 1 and type(raw) is int and self.release_raw <= raw <= 4095
            if phase in {"ARRIVAL", "SETTLE", "FILL"}:
                device.write(f"HOLD {visit}\n".encode("ascii"))
                if enough and phase in {"SETTLE", "FILL"}:
                    device.write(f"FULL {visit}\n".encode("ascii"))
            elif phase == "DONE" and station["pump"] is False and enough:
                if self.depart_at is None:
                    self.depart_at = now + DEPARTURE_PAUSE_SECONDS
                elif now >= self.depart_at and now - self.last_request >= 1.5:
                    self.bridge.dock_command(f"ROBOT DEPART {self.token}")
                    self.departing = True
                    self.last_request = now
            else:
                self.depart_at = None
        elif self.departing and state["connection"]["fresh"] and car.get("run"):
            self.token = 0
            self.depart_at = None
        elif self.acknowledged and not self.departing:
            self._cancel()  # Lost the stopped-car acknowledgement during service.
        elif not self.acknowledged and phase == "ARRIVAL" and now-self.last_request >= 1.5:
            self.bridge.dock_command(f"ROBOT DOCK {self.token}")
            self.last_request = now
        return True

    def _run(self, device):
        last = time.monotonic()
        try:
            with device:
                while not self.stop.is_set():
                    line = device.read_until(b"\n", 128)
                    now = time.monotonic()
                    if now-last > 3 or device.in_waiting > 256:
                        raise RuntimeError("Station heartbeat missing. Check the station firmware and USB port.")
                    if line.endswith(b"\n") and self.sample(line.decode("ascii", "replace").strip(), device, now):
                        last = now
        except (RuntimeError, OSError, serial.SerialException) as exc:
            self.bridge.event("error", str(exc))
        finally:
            if self.armed:
                self.bridge.dock_command("ROBOT STOP")
            self._cancel()
            self.phase = "DISCONNECTED"
            self.sensor = None
