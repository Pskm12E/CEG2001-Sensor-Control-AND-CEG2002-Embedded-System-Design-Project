"""Coordinate the station's USB visit with the car supervisor's stop acknowledgement."""
import re
import secrets
import threading
import time

from camera_usb import serial


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

    def connect(self, port):
        if self.worker and self.worker.is_alive():
            if self.port == port:
                return
            raise ValueError("Disconnect the station before choosing another port.")
        if self.bridge.hosted or not self.bridge.connected or not self.bridge.identity:
            raise ValueError("Connect the desk Pico first.")
        if port == self.bridge.port or not isinstance(port, str) or not re.fullmatch(r"COM[1-9]\d*", port, re.I):
            raise ValueError("Choose the station's application UART COM port.")
        try:
            device = serial.Serial(port, 9600, timeout=.15, write_timeout=.25)
            device.reset_input_buffer()
        except (serial.SerialException, OSError) as exc:
            raise RuntimeError(f"Cannot open station USB on {port}. Close its serial terminal.") from exc
        self.port = port
        self.phase = "WAITING_FOR_STATION"
        self.next_clear = 0
        self.armed = False
        self.visit = self.token = 0
        self.stop.clear()
        self.worker = threading.Thread(target=self._run, args=(device,), daemon=True)
        self.worker.start()

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

    def sample(self, line, device, now):
        match = re.fullmatch(r"DOCK1 (\d{1,5}) (BOOT|CLEAR|ARRIVAL|SETTLE|FILL|DONE|FAULT)", line)
        if not match or int(match[1]) > 65535:
            return False
        visit, phase = int(match[1]), match[2]
        if phase != self.phase:
            self.bridge.event("dock", f"Station {phase.lower()} on visit {visit}.")
        self.phase = phase
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
            if phase in {"ARRIVAL", "SETTLE", "FILL"}:
                device.write(f"HOLD {visit}\n".encode("ascii"))
            elif phase == "DONE" and car.get("wet") and now-self.last_request >= 1.5:
                self.bridge.dock_command(f"ROBOT DEPART {self.token}")
                self.departing = True
                self.last_request = now
        elif self.departing and state["connection"]["fresh"] and car.get("run"):
            self.token = 0
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
