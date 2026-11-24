"""Share read-only views of selected data from the running local robot dashboard."""
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import queue
import re
import secrets
import shutil
import socket
import subprocess
import threading
import time
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
DASH = HERE.parent
FILES = {
    "/": (HERE / "viewer.html", "text/html; charset=utf-8"),
    "/styles.css": (DASH / "static" / "styles.css", "text/css; charset=utf-8"),
    "/viewer.js": (HERE / "viewer.js", "text/javascript; charset=utf-8"),
}
STREAMS = {"/video/camera": "/api/camera/stream", "/video/target": "/api/detection/stream"}

def fields(data, names):
    return {key: data[key] for key in names.split() if key in data}

def read_live_state(port, empty, full):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    try:
        connection.request("GET", "/api/state")
        response = connection.getresponse()
        if response.status != 200:
            raise OSError("Local dashboard unavailable")
        data = json.loads(response.read(512 * 1024))
    finally:
        connection.close()
    link = data["connection"]
    telemetry = data.get("telemetry") if link.get("connected") and link.get("fresh") else None
    raw = (telemetry or {}).get("water_raw")
    percent = None
    if type(raw) is int and empty is not None:
        percent = min(100, max(0, int((raw-empty)*100/(full-empty)+0.5)))
    return {
        "last_seen": link.get("last_seen") if telemetry else None,
        "tank_percent": percent,
        "telemetry": fields(telemetry, "run flags calibration uart_errors rx_drops pump driver_ready water_raw") if telemetry else None,
        "links": fields(data.get("links", {}), "pico wifi esp msp uno"),
        "camera": fields(data.get("camera", {}), "streaming sequence width height fps"),
        "detection": fields(data.get("detection", {}), "enabled fresh status"),
    }

class ShareServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False
    def server_bind(self):
        if os.name == "nt":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

class Viewer(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def headers_for(self, code, content_type):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store, no-transform")
        self.send_header("X-Robots-Tag", "noindex, nofollow, noarchive")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=()")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")

    def reply(self, code, content_type, body):
        self.headers_for(code, content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def stream(self, path):
        if not self.server.slots.acquire(blocking=False):
            return self.reply(503, "text/plain", b"Viewer limit reached")
        upstream = http.client.HTTPConnection("127.0.0.1", self.server.dashboard_port, timeout=5)
        started = False
        try:
            upstream.request("GET", STREAMS[path])
            response = upstream.getresponse()
            if response.status != 200 or not response.getheader("Content-Type", "").startswith("multipart/x-mixed-replace"):
                return self.reply(503, "text/plain", b"Waiting for camera")
            self.headers_for(200, "multipart/x-mixed-replace; boundary=robot-frame")
            self.end_headers()
            started = True
            self.connection.settimeout(5)
            while block := response.read1(16384):
                self.wfile.write(block)
        except (OSError, http.client.HTTPException):
            if not started:
                self.reply(503, "text/plain", b"Camera unavailable")
        finally:
            upstream.close()
            self.server.slots.release()

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in FILES:
            asset, mime = FILES[path]
            return self.reply(200, mime, asset.read_bytes())
        if path == "/api/view":
            return self.reply(200, "text/plain", self.server.view_id)
        if path == "/api/state":
            try:
                state = read_live_state(self.server.dashboard_port, self.server.empty, self.server.full)
            except (OSError, http.client.HTTPException, ValueError, KeyError):
                return self.reply(503, "application/json", b'{"error":"Laptop offline"}')
            return self.reply(200, "application/json", json.dumps(state).encode())
        if path in STREAMS and self.command == "GET":
            return self.stream(path)
        self.reply(404, "text/plain", b"Not found")

    do_HEAD = do_GET
    def do_POST(self):
        self.reply(405, "text/plain", b"View only")

def water_scale(folder):
    try:
        saved = json.loads((folder / "tank.json").read_text(encoding="utf-8-sig"))
        low, high = saved["empty"], saved["full"]
        if type(low) is int and type(high) is int and 0 <= low < high <= 4095:
            return low, high
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None, None

def share_dashboard(port, dashboard_process=None):
    """Run an outbound tunnel to the view-only server until Ctrl+C or process exit."""
    folder = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "PlantRobotShare"
    folder.mkdir(parents=True, exist_ok=True)
    cloudflared = shutil.which("cloudflared") or folder / "cloudflared.exe"
    if not Path(cloudflared).is_file():
        raise OSError("Install cloudflared on this laptop (winget install --id Cloudflare.cloudflared), then reopen Start Robot.")
    with ShareServer(("127.0.0.1", 0), Viewer) as server:
        server.dashboard_port = port
        server.empty, server.full = water_scale(folder)
        server.view_id = secrets.token_hex(16).encode("ascii")
        server.slots = threading.BoundedSemaphore(16)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        print("Connecting the public camera and readings viewer...", flush=True)
        with subprocess.Popen([str(cloudflared), "tunnel", "--no-autoupdate", "--protocol", "http2",
                               "--url", f"http://127.0.0.1:{server.server_port}"],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                              encoding="utf-8", errors="replace") as tunnel:
            addresses = queue.SimpleQueue()
            registered = threading.Event()
            def read_tunnel():
                for line in tunnel.stdout:
                    if "Registered tunnel connection" in line:
                        registered.set()
                    match = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com\b", line)
                    if match:
                        addresses.put(match[0])
                    elif " ERR " in line:
                        print(line.strip(), flush=True)
            threading.Thread(target=read_tunnel, daemon=True).start()
            try:
                deadline = time.monotonic() + 55
                url = None
                while time.monotonic() < deadline:
                    if tunnel.poll() is not None:
                        raise OSError(f"Public tunnel exited with code {tunnel.returncode}.")
                    if not url:
                        try:
                            url = addresses.get(timeout=0.5)
                        except queue.Empty:
                            continue
                    if registered.wait(.5):
                        break
                else:
                    raise OSError("The tunnel did not establish a public connection in time.")
                # A registered tunnel can precede DNS availability on the operator's Wi-Fi.
                # Keep the tunnel running while waiting for this exact viewer to answer.
                print(f"Waiting for public DNS and HTTPS. You can watch locally at http://127.0.0.1:{port}/", flush=True)
                next_notice = time.monotonic() + 45
                while True:
                    if tunnel.poll() is not None:
                        raise OSError("The tunnel closed before the public address was ready.")
                    if dashboard_process is not None and dashboard_process.poll() is not None:
                        raise OSError("The local dashboard closed.")
                    try:
                        with urlopen(url + "/api/view", timeout=3) as response:
                            if response.read(64) == server.view_id:
                                break
                    except (OSError, URLError, http.client.HTTPException):
                        pass
                    if time.monotonic() >= next_notice:
                        print("Still waiting for this Wi-Fi to reach the new public address. Keep this window open.", flush=True)
                        next_notice = time.monotonic() + 60
                    time.sleep(3)
                if tunnel.poll() is not None:
                    raise OSError("The tunnel closed before sharing was ready.")
                print(f"\nPublic view-only link: {url}\nKeep this window open. Press Ctrl+C here to end sharing.", flush=True)
                while tunnel.poll() is None:
                    if dashboard_process is not None and dashboard_process.poll() is not None:
                        raise OSError("The local dashboard closed.")
                    time.sleep(.3)
                raise OSError(f"Public tunnel closed (code {tunnel.returncode}).")
            finally:
                if tunnel.poll() is None:
                    tunnel.terminate()
                server.shutdown()
