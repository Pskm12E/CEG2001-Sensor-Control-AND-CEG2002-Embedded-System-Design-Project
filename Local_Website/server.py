"""Loopback-only robot bench dashboard. No motion or spray API exists."""
from __future__ import annotations

import argparse
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import queue
import re
import socket
import sys
import threading
import time
from urllib.parse import urlsplit
from urllib.request import urlopen
import webbrowser

ROOT = Path(__file__).resolve().parent
try:
    import serial
    from serial.tools import list_ports
except ImportError:
    # Reuse the already installed project tools; a normal venv takes precedence.
    sys.path.insert(0, str(ROOT.parent / "tmp" / "pico-tools-python"))
    try:
        import serial
        from serial.tools import list_ports
    except ImportError:
        raise SystemExit("Install dependencies first: python -m pip install -r requirements.txt")

ALLOWED_COMMANDS = frozenset({"PING", "STATUS", "ON", "OFF", "LOOPBACK"})
STATUS_PATTERN = re.compile(
    r"STATUS BOARD=MSP430F5529 LED2=(ON|OFF) S2_PRESSES=(\d{1,10}) "
    r"UART0=(IDLE|LOOPBACK|WAIT_REPLY) UART_ERRORS=(\d{1,10}) "
    r"RX_DROPS=(\d{1,10}) BENCH_ONLY"
)


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def parse_status(line):
    match = STATUS_PATTERN.fullmatch(line)
    if not match:
        return None
    led, presses, uart, errors, drops = match.groups()
    return {"board": "MSP430F5529", "led2": led, "s2_presses": int(presses),
            "uart0": uart, "uart_errors": int(errors), "rx_drops": int(drops)}


def available_ports():
    # Never open the Uno (which resets on opening USB) or the TI debug interface.
    return [{"device": p.device, "description": p.description, "suggested": True}
            for p in sorted(list_ports.comports(), key=lambda p: p.device)
            if p.vid == 0x2047 and p.pid == 0x0013
            and "application uart" in (p.description or "").lower()]


class Bridge:
    def __init__(self):
        self.lock = threading.RLock()
        self.lifecycle = threading.Lock()
        self.events = deque(maxlen=100)
        self.sequence = 0
        self.connected = False
        self.port = None
        self.error = None
        self.telemetry = None
        self.last_seen = None
        self.last_seen_monotonic = None
        self.worker = None
        self.stop = threading.Event()
        self.pending = queue.Queue(maxsize=8)
        self.event("info", "Dashboard ready. Connect the robot MSP430 to read its bench status.")

    def event(self, kind, message):
        with self.lock:
            self.sequence += 1
            self.events.append({"id": self.sequence, "time": timestamp(),
                                "kind": kind, "message": message})

    def state(self):
        with self.lock:
            fresh = (self.connected and self.last_seen_monotonic is not None
                     and time.monotonic() - self.last_seen_monotonic < 4)
            error = self.error
            if self.connected and not fresh:
                error = "Waiting for a current MSP430 bench status reply."
            return {"mode": "bench", "connection": {
                "connected": self.connected, "port": self.port, "baud": 9600,
                "error": error, "fresh": bool(fresh), "last_seen": self.last_seen},
                "telemetry": dict(self.telemetry) if self.telemetry else None,
                "events": list(self.events)}

    def connect(self, port):
        with self.lifecycle:
            if not isinstance(port, str) or port not in {p["device"] for p in available_ports()}:
                raise ValueError("Select the MSP Application UART port. The Uno and debug port are excluded.")
            with self.lock:
                if self.connected:
                    if self.port == port:
                        return
                    raise ValueError("Disconnect the current board before selecting another port.")
            if self.worker:
                self.stop.set()
                self.worker.join(timeout=2)
                if self.worker.is_alive():
                    raise RuntimeError("The previous connection is still closing. Try again.")
            try:
                device = serial.Serial(port, 9600, timeout=0.1, write_timeout=0.5,
                                       xonxoff=False, rtscts=False, dsrdtr=False)
            except (serial.SerialException, OSError) as exc:
                self.error = f"Cannot open {port}. Close other serial terminals and check the USB cable."
                self.event("error", self.error)
                raise RuntimeError(self.error) from exc
            with self.lock:
                self.port = port
                self.connected = True
                self.error = None
                self.telemetry = None
                self.last_seen = self.last_seen_monotonic = None
                self.stop = threading.Event()
                self.pending = queue.Queue(maxsize=8)
            self.event("connection", f"Opened {port} at 9600 baud; waiting for MSP430 status.")
            self.worker = threading.Thread(target=self._run, args=(device,), daemon=True)
            self.worker.start()

    def disconnect(self):
        with self.lifecycle:
            was_connected = self.connected
            self.stop.set()
            if self.worker:
                self.worker.join(timeout=2)
                if self.worker.is_alive():
                    raise RuntimeError("The serial connection is still closing. Try again.")
            with self.lock:
                self.connected = False
                self.error = None
            if was_connected:
                self.event("connection", "Disconnected. Last readings are no longer live.")

    def command(self, command):
        if not isinstance(command, str) or command not in ALLOWED_COMMANDS:
            raise ValueError("Only PING, STATUS, ON, OFF and LOOPBACK bench commands are available.")
        with self.lifecycle:
            if not self.state()["connection"]["fresh"]:
                raise RuntimeError("Connect to the MSP430 and wait for fresh bench status first.")
            try:
                self.pending.put_nowait(command)
            except queue.Full:
                raise RuntimeError("Commands are still pending. Wait for a board reply.")
            self.event("command", f"Queued {command}")

    def _receive(self, line):
        telemetry = parse_status(line)
        if telemetry:
            with self.lock:
                first = self.last_seen is None
                self.telemetry = telemetry
                self.last_seen = timestamp()
                self.last_seen_monotonic = time.monotonic()
                self.error = None
            if first:
                self.event("connection", "MSP430F5529 bench firmware confirmed. Live status received.")
        elif line:
            self.event("error" if line.startswith("ERR") or "FAIL" in line else "board", line)

    def _run(self, device):
        buffer = bytearray()
        discard = False
        next_status = 0.0
        next_command = 0.0
        try:
            while not self.stop.is_set():
                now = time.monotonic()
                if now >= next_command:
                    # Commands queued by the operator are separated by 250 ms.
                    try:
                        command = self.pending.get_nowait()
                    except queue.Empty:
                        command = "STATUS" if now >= next_status else None
                    if command:
                        device.write((command + "\n").encode("ascii"))
                        next_command = now + 0.25
                        if command == "STATUS":
                            next_status = now + 1.0
                for char in device.read(max(1, min(device.in_waiting, 256))):
                    if char == 10:
                        if not discard:
                            self._receive(buffer.decode("ascii", errors="replace"))
                        buffer.clear()
                        discard = False
                    elif char != 13 and not discard:
                        if len(buffer) >= 512:
                            buffer.clear()
                            discard = True
                            self.event("error", "Discarded an overlong serial line.")
                        else:
                            buffer.append(char)
        except (serial.SerialException, OSError) as exc:
            with self.lock:
                self.error = "MSP430 USB connection lost. Check the cable, then reconnect."
            self.event("error", self.error)
        finally:
            device.close()
            with self.lock:
                self.connected = False


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def server_bind(self):
        # Windows SO_REUSEADDR can allow a second HTTP server on the same port.
        if sys.platform == "win32":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def __init__(self, address, bridge):
        self.bridge = bridge
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    server_version = "RobotBench/1.0"

    def _local_request(self):
        allowed = {f"localhost:{self.server.server_port}", f"127.0.0.1:{self.server.server_port}"}
        return self.headers.get("Host") in allowed

    def _reply(self, code, data, content_type="application/json; charset=utf-8"):
        if not isinstance(data, bytes):
            data = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(self), microphone=()")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self._local_request():
            return self._reply(403, {"error": "This dashboard only accepts local requests."})
        path = urlsplit(self.path).path
        if path == "/api/state":
            return self._reply(200, self.server.bridge.state())
        if path == "/api/ports":
            return self._reply(200, {"ports": available_ports()})
        if path == "/api/health":
            return self._reply(200, {"app": "robot-bench-dashboard", "version": 1})
        files = {"/": ("index.html", "text/html; charset=utf-8"),
                 "/index.html": ("index.html", "text/html; charset=utf-8"),
                 "/styles.css": ("styles.css", "text/css; charset=utf-8"),
                 "/app.js": ("app.js", "text/javascript; charset=utf-8")}
        if path not in files:
            return self._reply(404, {"error": "Not found"})
        name, mime = files[path]
        try:
            data = (ROOT / "static" / name).read_bytes()
        except FileNotFoundError:
            return self._reply(503, {"error": "Dashboard files are missing."})
        self._reply(200, data, mime)

    def do_POST(self):
        if not self._local_request():
            return self._reply(403, {"error": "This dashboard only accepts local requests."})
        origin = self.headers.get("Origin")
        expected = {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}
        if origin is not None and origin not in expected:
            return self._reply(403, {"error": "Cross-site commands are not allowed."})
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self._reply(415, {"error": "Send application/json."})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 1024:
                raise ValueError("Invalid request size")
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError("Expected a JSON object")
        except (ValueError, UnicodeDecodeError):
            return self._reply(400, {"error": "Invalid JSON request."})
        try:
            path = urlsplit(self.path).path
            if path == "/api/connect":
                self.server.bridge.connect(body.get("port"))
            elif path == "/api/disconnect":
                self.server.bridge.disconnect()
            elif path == "/api/command":
                self.server.bridge.command(body.get("command"))
            else:
                return self._reply(404, {"error": "Not found"})
            self._reply(200, {"ok": True})
        except ValueError as exc:
            self._reply(400, {"error": str(exc)})
        except RuntimeError as exc:
            self._reply(409, {"error": str(exc)})

    def log_message(self, format, *args):
        # Polling stays quiet; startup and exceptional replies still have logs.
        if len(args) > 1 and str(args[1]) not in {"200", "304"}:
            super().log_message(format, *args)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true", help="Open the local page in the default browser")
    args = parser.parse_args()
    bridge = Bridge()
    try:
        server = DashboardServer(("127.0.0.1", args.port), bridge)
    except OSError:
        if args.open:
            try:
                with urlopen(f"http://127.0.0.1:{args.port}/api/health", timeout=2) as response:
                    if json.load(response).get("app") == "robot-bench-dashboard":
                        webbrowser.open(f"http://127.0.0.1:{args.port}")
                        print("Opened the dashboard that is already running.", flush=True)
                        return
            except (OSError, ValueError):
                pass
        raise SystemExit(f"Port {args.port} is in use. Open the existing dashboard or choose --port 8766.")
    url = f"http://127.0.0.1:{args.port}"
    print(f"Robot dashboard: {url}\nLocal computer only. Ctrl+C closes the server.", flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        bridge.disconnect()
        server.server_close()


if __name__ == "__main__":
    main()
