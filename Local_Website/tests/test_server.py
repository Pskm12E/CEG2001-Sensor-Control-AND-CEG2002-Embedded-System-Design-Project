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

VALID = "STATUS BOARD=MSP430F5529 LED2=OFF S2_PRESSES=7 UART0=IDLE UART_ERRORS=0 RX_DROPS=2 BENCH_ONLY"


class BridgeTests(unittest.TestCase):
    def test_parse_full_status(self):
        value = server.parse_status(VALID)
        self.assertEqual(value["s2_presses"], 7)
        self.assertEqual(value["rx_drops"], 2)
        self.assertEqual(value["led2"], "OFF")

    def test_reject_incomplete_or_foreign_firmware(self):
        for value in [VALID.replace(" BENCH_ONLY", ""), VALID + " trailing", VALID.replace("OFF", "MAYBE"),
                      VALID.replace("MSP430F5529", "ARDUINO"), "PONG MSP430", VALID.replace("7", "-1")]:
            with self.subTest(value=value):
                self.assertIsNone(server.parse_status(value))

    def test_freshness_expires_and_disconnect_keeps_last_known(self):
        bridge = server.Bridge()
        bridge.connected = True
        bridge._receive(VALID)
        self.assertTrue(bridge.state()["connection"]["fresh"])
        bridge.last_seen_monotonic = time.monotonic() - 5
        self.assertFalse(bridge.state()["connection"]["fresh"])
        self.assertEqual(bridge.state()["telemetry"]["s2_presses"], 7)
        bridge.connected = False
        self.assertFalse(bridge.state()["connection"]["fresh"])

    def test_nonstatus_reply_never_marks_live(self):
        bridge = server.Bridge()
        bridge.connected = True
        bridge._receive("PONG MSP430")
        self.assertFalse(bridge.state()["connection"]["fresh"])
        self.assertIsNone(bridge.state()["telemetry"])

    def test_no_actuator_or_multiline_commands(self):
        bridge = server.Bridge()
        bridge.connected = True
        bridge._receive(VALID)
        for command in ["F", "SPRAY", "LINK ON", "ON\nOFF", None, ["ON"], "on"]:
            with self.subTest(command=command), self.assertRaises(ValueError):
                bridge.command(command)
        self.assertTrue(bridge.pending.empty())

    def test_stale_reading_blocks_new_commands(self):
        bridge = server.Bridge()
        with self.assertRaises(RuntimeError):
            bridge.command("ON")
        self.assertTrue(bridge.pending.empty())

    def test_only_ti_application_port_listed(self):
        ports = [SimpleNamespace(device="COM13", description="MSP Application UART1", vid=0x2047, pid=0x0013),
                 SimpleNamespace(device="COM14", description="MSP Debug Interface", vid=0x2047, pid=0x0013),
                 SimpleNamespace(device="COM12", description="Arduino Uno", vid=0x2341, pid=0x0043)]
        with patch.object(server.list_ports, "comports", return_value=ports):
            self.assertEqual([p["device"] for p in server.available_ports()], ["COM13"])
            with self.assertRaises(ValueError), patch.object(server.serial, "Serial") as open_port:
                server.Bridge().connect("COM12")
            open_port.assert_not_called()

    def test_event_log_bounded(self):
        bridge = server.Bridge()
        for n in range(110):
            bridge.event("board", f"test {n}")
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

    def test_response_limits_camera_and_frames(self):
        _, headers, _ = self.request("/api/state")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertEqual(headers["Permissions-Policy"], "camera=(self), microphone=()")


if __name__ == "__main__":
    unittest.main(verbosity=2)
