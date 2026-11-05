"""Laptop-only robot telemetry and XIAO camera dashboard; optional hosted preview."""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import sys
from urllib.parse import urlsplit
from urllib.request import urlopen
import webbrowser

from desk_bridge import Bridge, ALLOWED_COMMANDS, parse_status, available_ports, timestamp, serial, list_ports
from camera_usb import Camera, available_camera_ports
from blue_detector import DetectionVideo

ROOT = Path(__file__).resolve().parent


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def server_bind(self):
        # Windows SO_REUSEADDR can allow a second HTTP server on the same port.
        if sys.platform == "win32":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def __init__(self, address, bridge, public_origin=None):
        self.bridge = bridge
        self.public_origin = public_origin
        self.camera = bridge.video
        self.detector = DetectionVideo(self.camera)
        if public_origin and not bridge.hosted:
            raise ValueError("Public hosting requires a read-only bridge.")
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    server_version = "RobotBench/1.0"

    def _camera_stream(self, detection=False):
        if self.server.public_origin:
            return self._reply(403, {"error": "Wireless camera relay is available only in the local dashboard."})
        camera = self.server.detector if detection else self.server.camera
        state = camera.state()
        if not state["connected"]:
            return self._reply(409, {"error": "Start blue-target detection first." if detection else "Start the XIAO camera first."})
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=robot-frame")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Connection", "close")
        self.end_headers()
        # Bound a slow client's socket; do not queue every captured frame for it.
        self.connection.settimeout(3)
        self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 16384)
        sequence = 0
        try:
            while True:
                frame = camera.wait_frame(sequence, state["generation"])
                if frame is None:
                    current = camera.state()
                    if current["connected"] and current["generation"] == state["generation"]:
                        continue  # Keep one live response while the radio reconnects.
                    break
                jpeg, metadata = frame
                sequence = metadata["sequence"]
                header = ("--robot-frame\r\nContent-Type: image/jpeg\r\n"
                          f"Content-Length: {len(jpeg)}\r\nX-Sequence: {sequence}\r\n"
                          f"X-CRC32: {metadata['crc32']}\r\n"
                          f"X-Received-At: {metadata['captured_at']}\r\n\r\n").encode("ascii")
                self.wfile.write(header)
                self.wfile.write(jpeg)
                self.wfile.write(b"\r\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionError, OSError):
            pass  # Browser stopped/paused the stream; USB reader stays independent.

    def _local_request(self):
        allowed = {f"localhost:{self.server.server_port}", f"127.0.0.1:{self.server.server_port}"}
        if self.server.public_origin:
            host = urlsplit(self.server.public_origin).netloc
            allowed.update({host, f"{host}:443"})
        return self.headers.get("Host", "").lower() in allowed

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
            state = self.server.bridge.state()
            state["camera"] = self.server.camera.state()
            state["detection"] = self.server.detector.state()
            return self._reply(200, state)
        if path == "/api/ports":
            return self._reply(200, {"ports": [] if self.server.public_origin else available_ports(),
                                     "mode": "hosted" if self.server.public_origin else "local"})
        if path == "/api/camera/ports":
            return self._reply(200, {"ports": [] if self.server.public_origin else [{"device": "PICO_WIFI", "description": "XIAO over private Wi-Fi via desk Pico"}]})
        if path == "/api/camera/stream":
            return self._camera_stream()
        if path == "/api/detection/stream":
            return self._camera_stream(detection=True)
        if path == "/api/camera/frame":
            if self.server.public_origin:
                return self._reply(403, {"error": "Wireless camera relay is available only in the local dashboard."})
            frame = self.server.camera.image()
            if not frame:
                return self._reply(409, {"error": "Start the XIAO camera and capture an image first."})
            return self._reply(200, frame, "image/jpeg")
        if path == "/api/health":
            return self._reply(200, {"app": "robot-bench-dashboard", "version": 2})
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
        if self.server.public_origin:
            expected.add(self.server.public_origin)
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
        # Consume the bounded request body before refusing hosted commands, so
        # closing the socket cannot discard unread data and reset the response.
        if self.server.public_origin:
            return self._reply(403, {"error": "USB controls are available only in the laptop dashboard."})
        try:
            path = urlsplit(self.path).path
            if path == "/api/connect":
                self.server.bridge.connect(body.get("port"))
            elif path == "/api/disconnect":
                self.server.detector.stop()
                self.server.bridge.disconnect()
            elif path == "/api/command":
                self.server.bridge.command(body.get("command"))
            elif path == "/api/camera/connect":
                self.server.camera.connect(body.get("port"))
            elif path == "/api/camera/capture":
                return self._reply(405, {"error": "Snapshot polling was replaced by the live stream."})
            elif path == "/api/camera/disconnect":
                self.server.detector.stop()
                self.server.camera.disconnect()
            elif path == "/api/detection/start":
                self.server.detector.start()
            elif path == "/api/detection/stop":
                self.server.detector.stop()
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
    parser.add_argument("--host", choices=("127.0.0.1", "0.0.0.0"), default="127.0.0.1")
    parser.add_argument("--public-origin", help="HTTPS origin for a read-only hosted preview")
    parser.add_argument("--open", action="store_true", help="Open the local page in the default browser")
    args = parser.parse_args()
    if args.public_origin:
        origin = urlsplit(args.public_origin)
        if (origin.scheme != "https" or not origin.hostname or origin.username or origin.password
                or origin.port is not None or origin.path or origin.query or origin.fragment):
            parser.error("--public-origin must be an HTTPS origin such as https://pest.4bytedigi.com")
        args.public_origin = args.public_origin.lower()
    if args.host != "127.0.0.1" and not args.public_origin:
        parser.error("Non-loopback hosting requires --public-origin and runs read-only.")
    if args.open and args.public_origin:
        parser.error("Use --open only for the local laptop dashboard.")
    bridge = Bridge(hosted=bool(args.public_origin))
    try:
        server = DashboardServer((args.host, args.port), bridge, args.public_origin)
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
    url = args.public_origin or f"http://127.0.0.1:{args.port}"
    mode = "Read-only hosted preview." if args.public_origin else "Local computer only."
    print(f"Robot dashboard: {url}\n{mode} Ctrl+C closes the server.", flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.detector.stop()
        bridge.disconnect()
        server.camera.disconnect()
        server.server_close()


if __name__ == "__main__":
    main()
