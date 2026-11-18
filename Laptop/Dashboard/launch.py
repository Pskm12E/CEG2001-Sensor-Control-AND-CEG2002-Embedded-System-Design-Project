"""Start the local dashboard, desk Pico connection and wireless camera."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener
import webbrowser

ROOT = Path(__file__).resolve().parent


class LaunchError(RuntimeError):
    pass


class LocalDashboard:
    def __init__(self, port):
        self.url = f"http://127.0.0.1:{port}"
        self.http = build_opener(ProxyHandler({}))

    def request(self, path, body=None):
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = Request(self.url + path, data=data,
                      headers={"Content-Type": "application/json"} if data else {})
        try:
            with self.http.open(req, timeout=2) as response:
                return json.load(response)
        except HTTPError as exc:
            try:
                detail = json.load(exc).get("error", str(exc))
            except (ValueError, AttributeError):
                detail = str(exc)
            raise LaunchError(detail) from exc
        except (OSError, URLError, ValueError) as exc:
            raise LaunchError(f"Cannot reach the local dashboard: {exc}") from exc

    def is_running(self):
        try:
            health = self.request("/api/health")
        except LaunchError:
            return False
        if health.get("app") != "robot-bench-dashboard" or health.get("version") != 2:
            raise LaunchError(f"Another application is using {self.url}. Choose --http-port 8766.")
        return True

    def local_state(self):
        state = self.request("/api/state")
        if state.get("mode") != "local" or not (state.get("read_only") is True or state.get("target_jobs") is True):
            raise LaunchError("This launcher requires the local robot dashboard.")
        return state


def ensure_server(client, port, emit=print):
    if client.is_running():
        emit("[1/4] Reusing the running dashboard; no second server is started.")
        return None
    emit("[1/4] Starting the local dashboard...")
    # Shares the launcher's console; creates no extra helper window.
    child = subprocess.Popen([sys.executable, "-u", str(ROOT / "server.py"),
                              "--port", str(port)], cwd=ROOT)
    deadline = time.monotonic() + 10
    try:
        while time.monotonic() < deadline:
            if client.is_running():
                # Another launcher may have won the bind race.
                return child if child.poll() is None else None
            if child.poll() is not None:
                raise LaunchError("Dashboard exited during startup. Check the message above and Python dependencies.")
            time.sleep(0.2)
        raise LaunchError("The dashboard did not start within 10 seconds.")
    except BaseException:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=3)
        raise


def configure_hardware(client, *, pico_port=None, wait=30, camera=True,
                       detect=False, emit=print):
    """Use only the dashboard's verified Pico port list and monitoring APIs."""
    deadline = time.monotonic() + wait
    opened = False
    emit("[2/4] Finding the desk Pico and checking its firmware...")
    while True:
        state = client.local_state()
        connection = state["connection"]
        if connection["connected"]:
            if pico_port and connection["port"].upper() != pico_port.upper():
                raise LaunchError(f"Dashboard is already connected to {connection['port']}. Disconnect it before selecting {pico_port}.")
            if state["links"]["pico"] == "UP":
                emit(f"      Desk Pico verified on {connection['port']}.")
                break
        elif opened:
            raise LaunchError(connection.get("error") or "Pico disconnected during its firmware check. Close other serial consoles and retry.")
        else:
            ports = client.request("/api/ports")["ports"]
            if pico_port:
                ports = [p for p in ports if p["device"].upper() == pico_port.upper()]
            if len(ports) > 1:
                names = ", ".join(p["device"] for p in ports)
                raise LaunchError(f"More than one Pico found ({names}). Run Start Robot.cmd --pico-port COM11 with the correct port.")
            if ports:
                client.request("/api/connect", {"port": ports[0]["device"]})
                opened = True
                continue
        if time.monotonic() >= deadline:
            detail = connection.get("error") if connection["connected"] else "No desk Pico USB port found. Plug the desk Pico into the laptop using a data cable."
            raise LaunchError(detail or "Pico firmware verification timed out. Use DESK_BRIDGE_V2 and close other serial consoles.")
        time.sleep(0.25)

    if camera:
        emit("[3/4] Starting XIAO live video over the existing private Wi-Fi...")
        if not state["camera"]["connected"]:
            client.request("/api/camera/connect", {"port": "PICO_WIFI"})
        while True:
            state = client.local_state()
            if state["camera"]["streaming"]:
                emit(f"      Live frames received ({state['camera']['fps']} fps).")
                break
            if not state["connection"]["connected"] or state["camera"].get("error"):
                raise LaunchError(state["camera"].get("error") or "Desk Pico disconnected while starting video.")
            if time.monotonic() >= deadline:
                raise LaunchError("No live camera frames yet. Check power to the XIAO camera and car ESP32. The dashboard stays available; video will resume when the link recovers.")
            time.sleep(0.25)
    else:
        emit("[3/4] Camera startup skipped (--no-camera).")

    if detect and not state["detection"]["enabled"]:
        client.request("/api/detection/start", {})
        emit("      Blue-square practice detection enabled; this is not insect recognition.")
    emit("[4/4] Monitoring ready. No movement, calibration or spray commands were sent.")
    links = state["links"]
    emit(f"      Wi-Fi: {links['wifi']} | ESP32: {links['esp']} | MSP430: {links['msp']} | Uno: {links['uno']}")
    if not state["connection"]["fresh"] or links["uno"] != "READY":
        emit("      Robot telemetry is not fully linked yet. Check board power and UART wiring in the dashboard.")


def close_owned_server(client, child):
    # Never stop a server which was already running before this launcher.
    if child is None:
        return
    if child.poll() is None:
        for path in ("/api/detection/stop", "/api/camera/disconnect", "/api/disconnect"):
            try:
                client.request(path, {})
            except LaunchError:
                pass
        child.terminate()
        child.wait(timeout=3)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pico-port", help="Choose a specific desk Pico, for example COM11")
    parser.add_argument("--http-port", type=int, choices=range(1, 65536), default=8765, metavar="PORT")
    parser.add_argument("--wait", type=int, choices=range(1, 61), default=30, metavar="SECONDS",
                        help="Hardware startup budget, 1-60 seconds (default 30)")
    parser.add_argument("--detect", action="store_true", help="Also enable the OpenCV blue-square practice detector")
    parser.add_argument("--no-camera", action="store_true", help="Connect the Pico for telemetry only")
    parser.add_argument("--dashboard-only", action="store_true", help="Open the dashboard without connecting hardware")
    parser.add_argument("--no-browser", action="store_true", help="Do not open another browser tab")
    args = parser.parse_args(argv)
    if args.detect and (args.no_camera or args.dashboard_only):
        parser.error("--detect requires automatic camera startup")
    client = LocalDashboard(args.http_port)
    child = None
    result = 0
    try:
        child = ensure_server(client, args.http_port)
        client.local_state()
        print(f"\nDashboard: {client.url}", flush=True)
        if not args.no_browser and not webbrowser.open(client.url):
            print("Open the dashboard URL above in your browser.", flush=True)
        if not args.dashboard_only:
            try:
                configure_hardware(client, pico_port=args.pico_port, wait=args.wait,
                                   camera=not args.no_camera, detect=args.detect)
            except LaunchError as exc:
                result = 2
                print(f"\nSETUP INCOMPLETE: {exc}\nFix the connection and rerun this file, or use the dashboard buttons.", flush=True)
        if child is not None:
            print("\nKeep this window open. Press Ctrl+C to close this dashboard server.", flush=True)
            code = child.wait()
            if code:
                raise LaunchError(f"Dashboard server exited with code {code}.")
        else:
            print("The existing dashboard remains running. This launcher can close.", flush=True)
        return result
    except KeyboardInterrupt:
        print("\nClosing the launcher.", flush=True)
        return 0
    except (LaunchError, OSError) as exc:
        print(f"\nSTARTUP ERROR: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        close_owned_server(client, child)


if __name__ == "__main__":
    raise SystemExit(main())
