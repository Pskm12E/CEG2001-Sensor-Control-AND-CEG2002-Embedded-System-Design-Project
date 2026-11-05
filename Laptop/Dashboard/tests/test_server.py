"""Software-only checks: no serial device is opened by this suite."""
import json
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server

VALID = "STATUS BOARD=MSP430F5529 FW=SUPERVISOR_V2 LINK=READY RUN=0 CAL=NEEDED L2=NC R4=NC LED2=OFF FLAGS=96 RESULT=0 PENDING=0 UART_ERRORS=1 RX_DROPS=0 BAD_FRAMES=0 BRIDGE=ESP_UART_V1"

def remote_line(**changes):
    value = {"board": "ESP32_FIREBEETLE", "firmware": "DIRECT_WIFI_V1", "main_controller": "MSP430F5529", "ap_ready": True, "fresh": True, "msp_link": "UP", "age_ms": 100, "telemetry": VALID}
    value.update(changes)
    return "ROBOT STATE " + json.dumps(value)

def fresh_bridge():
    bridge = server.Bridge()
    bridge.connected = bridge.identity = True
    bridge.pico_seen = time.monotonic()
    bridge._receive(remote_line())
    return bridge

class BridgeTests(unittest.TestCase):
    def test_parse_supervisor_status(self):
        value = server.parse_status(VALID)
        self.assertEqual(value["uno_link"], "READY")
        self.assertEqual(value["calibration"], "NEEDED")
        self.assertEqual(value["run"], 0)
        self.assertEqual(value["uart_errors"], 1)

    def test_reject_incomplete_or_foreign_firmware(self):
        for value in [VALID.replace(" BRIDGE=ESP_UART_V1", ""), VALID + " trailing", VALID.replace("OFF", "MAYBE"), VALID.replace("MSP430F5529", "ARDUINO"), "PONG MSP430", VALID.replace("FLAGS=96", "FLAGS=999")]:
            with self.subTest(value=value): self.assertIsNone(server.parse_status(value))

    def test_freshness_expires_and_disconnect_keeps_last_known(self):
        bridge = fresh_bridge()
        self.assertTrue(bridge.state()["connection"]["fresh"])
        bridge.last_seen_monotonic = time.monotonic() - 5
        self.assertFalse(bridge.state()["connection"]["fresh"])
        self.assertEqual(bridge.state()["telemetry"]["run"], 0)
        bridge.connected = False
        self.assertFalse(bridge.state()["connection"]["fresh"])

    def test_nonstatus_reply_never_marks_live(self):
        bridge = server.Bridge()
        bridge.connected = True
        bridge._receive("PONG PICO_DESK_BRIDGE_V1")
        self.assertFalse(bridge.state()["connection"]["fresh"])
        self.assertIsNone(bridge.state()["telemetry"])

    def test_reject_remote_stale_bool_age_and_foreign_identity(self):
        for changes in [{"fresh": False}, {"age_ms": True}, {"age_ms": 2501}, {"telemetry": "wrong"}]:
            bridge = fresh_bridge()
            bridge._receive(remote_line(**changes))
            self.assertFalse(bridge.state()["connection"]["fresh"])
        with self.assertRaises(RuntimeError):
            fresh_bridge()._receive(remote_line(board="OTHER"))

    def test_unavailable_robot_status_does_not_disconnect_wireless_video(self):
        bridge=fresh_bridge()
        bridge.video.enabled=True
        bridge.video.value['connected']=True
        bridge._receive(remote_line(telemetry=None,age_ms=None,fresh=False,msp_link='NOT_CONNECTED'))
        self.assertFalse(bridge.state()['connection']['fresh'])
        self.assertTrue(bridge.connected)
        self.assertTrue(bridge.video.enabled)
        self.assertTrue(bridge.video.state()['connected'])
        self.assertIsNone(server.parse_status(None))

    def test_no_actuator_or_multiline_commands(self):
        bridge = fresh_bridge()
        for command in ["F", "SPRAY", "ON", "OFF", "LOOPBACK", "START", "STOP", "W", "B", "ON\nOFF", None, ["PING"], "ping"]:
            with self.subTest(command=command), self.assertRaises(ValueError): bridge.command(command)
        self.assertTrue(bridge.pending.empty())
        bridge.command("PING")
        self.assertEqual(bridge.pending.get_nowait(), "PING")

    def test_disconnected_blocks_checks(self):
        with self.assertRaises(RuntimeError): server.Bridge().command("PING")

    def test_only_pico_port_listed(self):
        ports = [SimpleNamespace(device="COM13", description="MSP Application UART1", vid=0x2047, pid=0x0013), SimpleNamespace(device="COM14", description="MSP Debug Interface", vid=0x2047, pid=0x0013), SimpleNamespace(device="COM12", description="Arduino Uno", vid=0x2341, pid=0x0043), SimpleNamespace(device="COM11", description="Pico USB", vid=0x2e8a, pid=0x000a)]
        with patch.object(server.list_ports, "comports", return_value=ports):
            self.assertEqual([p["device"] for p in server.available_ports()], ["COM11"])
            with self.assertRaises(ValueError), patch.object(server.serial, "Serial") as open_port:
                server.Bridge().connect("COM12")
            open_port.assert_not_called()

    def test_event_log_bounded(self):
        bridge = server.Bridge()
        for n in range(110): bridge.event("board", f"test {n}")
        self.assertEqual(len(bridge.state()["events"]), 100)


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = server.Bridge()
        cls.http = server.DashboardServer(("127.0.0.1", 0), cls.bridge)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.http.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join()

    def request(self, path, body=None, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        request_headers = {"Content-Type": "application/json"} if data else {}
        request_headers.update(headers or {})
        try:
            with urlopen(Request(self.url + path, data=data, headers=request_headers), timeout=3) as response:
                return response.status, response.headers, response.read()
        except HTTPError as response:
            return response.code, response.headers, response.read()

    def test_initial_state_is_disconnected_without_fabricated_telemetry(self):
        code, _, body = self.request("/api/state")
        self.assertEqual(code, 200)
        data = json.loads(body)
        self.assertFalse(data["connection"]["connected"])
        self.assertIsNone(data["telemetry"])

    def test_second_server_cannot_bind_same_port(self):
        with self.assertRaises(OSError):
            server.DashboardServer(("127.0.0.1", self.http.server_port), server.Bridge())

    def test_unrelated_hosts_and_origins_rejected(self):
        self.assertEqual(self.request("/api/state", headers={"Host": "attacker.example"})[0], 403)
        self.assertEqual(self.request("/api/command", {"command": "ON"}, {"Origin": "https://attacker.example"})[0], 403)

    def test_json_only_commands(self):
        self.assertEqual(self.request("/api/command", {"command": "ON"}, {"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.request("/api/command", ["ON"])[0], 400)
        self.assertEqual(self.request("/api/command", {"command": "SPRAY"})[0], 400)

    def test_cannot_serve_project_files(self):
        for path in ["/server.py", "/../work/project-context.md", "/api/spray"]:
            self.assertEqual(self.request(path)[0], 404)

    def test_stream_needs_camera_and_snapshot_polling_is_removed(self):
        self.assertEqual(self.request('/api/camera/stream')[0],409)
        self.assertEqual(self.request('/api/camera/capture',{})[0],405)

    def test_detection_requires_camera_and_stays_observation_only(self):
        self.assertEqual(self.request('/api/detection/start',{})[0],409)
        self.assertEqual(self.request('/api/detection/stream')[0],409)
        self.assertEqual(self.request('/api/detection/stop',{})[0],200)
        _, _, body = self.request('/api/state')
        detection=json.loads(body)['detection']
        self.assertFalse(detection['enabled'])
        self.assertFalse(detection['detected'])
        self.assertFalse(detection['actuator_control'])
        self.assertTrue(self.bridge.pending.empty())

    def test_response_limits_camera_and_frames(self):
        _, headers, _ = self.request("/api/state")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertEqual(headers["Permissions-Policy"], "camera=(self), microphone=()")


class HostedHttpTests(unittest.TestCase):
    def test_hosted_preview_is_read_only_and_host_restricted(self):
        bridge = server.Bridge(hosted=True)
        http = server.DashboardServer(("127.0.0.1", 0), bridge, "https://pest.4bytedigi.com")
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{http.server_port}"

        def request(path, body=None, host="pest.4bytedigi.com"):
            data = json.dumps(body).encode() if body is not None else None
            req = Request(url + path, data=data,
                          headers={"Host": host, "Content-Type": "application/json"})
            try:
                return urlopen(req, timeout=3)
            except HTTPError as response:
                return response

        try:
            with patch.object(server, "available_ports") as ports, patch.object(bridge, "connect") as connect:
                for path in ("/", "/styles.css", "/app.js", "/api/health"):
                    with self.subTest(path=path), request(path) as response:
                        self.assertEqual(response.status, 200)
                with request("/api/state") as response:
                    state = json.load(response)
                    self.assertEqual(state["mode"], "hosted")
                    self.assertFalse(state["connection"]["connected"])
                    self.assertIsNone(state["telemetry"])
                with request("/api/ports") as response:
                    self.assertEqual(json.load(response)["ports"], [])
                for path, body in (("/api/connect", {"port": "COM13"}),
                                   ("/api/command", {"command": "ON"}), ("/api/disconnect", {}),
                                   ("/api/camera/connect", {"port": "COM17"}),
                                   ("/api/camera/capture", {}), ("/api/camera/disconnect", {}),
                                   ("/api/detection/start", {}), ("/api/detection/stop", {})):
                    with self.subTest(path=path), request(path, body) as response:
                        self.assertEqual(response.status, 403)
                with request("/api/camera/frame") as response:
                    self.assertEqual(response.status, 403)
                with request("/api/camera/stream") as response:
                    self.assertEqual(response.status, 403)
                with request("/api/detection/stream") as response:
                    self.assertEqual(response.status, 403)
                ports.assert_not_called()
                connect.assert_not_called()
                for host in ("attacker.example", "pest.4bytedigi.com.attacker.example"):
                    with self.subTest(host=host), request("/api/state", host=host) as response:
                        self.assertEqual(response.status, 403)
                with urlopen(url + "/api/health", timeout=3) as response:
                    self.assertEqual(response.status, 200)
        finally:
            http.shutdown()
            http.server_close()
            thread.join()

    def test_public_host_cannot_enable_usb_bridge(self):
        with self.assertRaises(ValueError):
            server.DashboardServer(("127.0.0.1", 0), server.Bridge(), "https://pest.4bytedigi.com")


if __name__ == "__main__":
    unittest.main(verbosity=2)
