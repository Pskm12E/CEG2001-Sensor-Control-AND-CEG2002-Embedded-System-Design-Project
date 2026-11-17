"""Launcher checks use fake hardware; no USB device is opened."""
from copy import deepcopy
from io import StringIO
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import launch
import server


class FakeDashboard:
    def __init__(self):
        self.posts = []
        self.ports = [{"device": "COM11"}]
        self.auto_stream = True
        self.value = {
            "connection": {"connected": False, "port": None, "fresh": True, "error": None},
            "links": {"pico": "DOWN", "wifi": "UP", "esp": "UP", "msp": "UP", "uno": "READY"},
            "camera": {"connected": False, "streaming": False, "fps": 15, "error": None},
            "detection": {"enabled": False},
        }

    def local_state(self):
        return deepcopy(self.value)

    def request(self, path, body=None):
        if path == "/api/ports":
            return {"ports": self.ports}
        self.posts.append((path, body))
        if path == "/api/connect":
            self.value["connection"].update(connected=True, port=body["port"])
            self.value["links"]["pico"] = "UP"
        elif path == "/api/camera/connect":
            self.value["camera"].update(connected=True, streaming=self.auto_stream)
        elif path == "/api/detection/start":
            self.value["detection"]["enabled"] = True
        else:
            raise AssertionError(f"Unexpected mutation: {path}")
        return {"ok": True}


class StartupSequenceTests(unittest.TestCase):
    def test_connect_then_video_without_actuator_requests(self):
        client = FakeDashboard()
        launch.configure_hardware(client, emit=lambda _: None)
        self.assertEqual(client.posts, [
            ("/api/connect", {"port": "COM11"}),
            ("/api/camera/connect", {"port": "PICO_WIFI"}),
        ])

    def test_repeat_launch_keeps_existing_usb_and_video_connections(self):
        client = FakeDashboard()
        launch.configure_hardware(client, emit=lambda _: None)
        client.posts.clear()
        launch.configure_hardware(client, emit=lambda _: None)
        self.assertEqual(client.posts, [])

    def test_multiple_picos_require_selection(self):
        client = FakeDashboard()
        client.ports.append({"device": "COM20"})
        with self.assertRaisesRegex(launch.LaunchError, "More than one Pico"):
            launch.configure_hardware(client, emit=lambda _: None)
        self.assertEqual(client.posts, [])
        launch.configure_hardware(client, pico_port="com20", camera=False, emit=lambda _: None)
        self.assertEqual(client.posts, [("/api/connect", {"port": "COM20"})])

    def test_no_pico_keeps_dashboard_and_reports_missing_usb(self):
        client = FakeDashboard()
        client.ports.clear()
        with self.assertRaisesRegex(launch.LaunchError, "No desk Pico USB port"):
            launch.configure_hardware(client, wait=0, emit=lambda _: None)
        self.assertEqual(client.posts, [])

    def test_open_port_does_not_count_as_firmware_verification(self):
        client = FakeDashboard()
        client.value["connection"].update(connected=True, port="COM11")
        with self.assertRaisesRegex(launch.LaunchError, "firmware verification timed out"):
            launch.configure_hardware(client, wait=0, emit=lambda _: None)
        self.assertEqual(client.posts, [])

    def test_open_failure_does_not_trigger_camera(self):
        client = FakeDashboard()
        original = client.request
        def busy(path, body=None):
            if path == "/api/connect":
                raise launch.LaunchError("Close the Pico console")
            return original(path, body)
        client.request = busy
        with self.assertRaisesRegex(launch.LaunchError, "Close the Pico console"):
            launch.configure_hardware(client, emit=lambda _: None)
        self.assertEqual(client.posts, [])

    def test_camera_needs_live_frames_before_success(self):
        client = FakeDashboard()
        client.auto_stream = False
        messages = []
        with self.assertRaisesRegex(launch.LaunchError, "No live camera frames"):
            launch.configure_hardware(client, wait=0, emit=messages.append)
        self.assertFalse(any("Monitoring ready" in line for line in messages))

    def test_camera_can_work_without_robot_telemetry(self):
        client = FakeDashboard()
        client.value["connection"]["fresh"] = False
        client.value["links"].update(msp="STALE", uno="UNKNOWN")
        messages = []
        launch.configure_hardware(client, emit=messages.append)
        self.assertTrue(client.value["camera"]["streaming"])
        self.assertTrue(any("not fully linked" in line for line in messages))

    def test_practice_detection_is_explicit_and_after_live_frames(self):
        client = FakeDashboard()
        launch.configure_hardware(client, detect=True, emit=lambda _: None)
        self.assertEqual(client.posts[-1], ("/api/detection/start", {}))
        self.assertTrue(client.value["detection"]["enabled"])

    def test_running_other_pico_is_not_disconnected(self):
        client = FakeDashboard()
        client.value["connection"].update(connected=True, port="COM11")
        with self.assertRaisesRegex(launch.LaunchError, "already connected"):
            launch.configure_hardware(client, pico_port="COM20", emit=lambda _: None)
        self.assertEqual(client.posts, [])


class LauncherLifecycleTests(unittest.TestCase):
    def test_existing_server_does_not_spawn_a_duplicate(self):
        client = Mock()
        client.is_running.return_value = True
        with patch.object(launch.subprocess, "Popen") as spawn:
            self.assertIsNone(launch.ensure_server(client, 8765, emit=lambda _: None))
        spawn.assert_not_called()

    def test_dashboard_only_does_not_connect_hardware(self):
        with patch.object(launch, "ensure_server", return_value=None), \
             patch.object(launch.LocalDashboard, "local_state", return_value={}), \
             patch.object(launch, "configure_hardware") as configure, \
             patch.object(launch.webbrowser, "open") as browser, \
             patch("sys.stdout", new_callable=StringIO):
            self.assertEqual(launch.main(["--dashboard-only", "--no-browser"]), 0)
        configure.assert_not_called()
        browser.assert_not_called()

    def test_reused_server_is_not_stopped(self):
        client = Mock()
        launch.close_owned_server(client, None)
        client.request.assert_not_called()


class LauncherHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = server.Bridge()
        cls.http = server.DashboardServer(("127.0.0.1", 0), cls.bridge)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()
        cls.client = launch.LocalDashboard(cls.http.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join()

    def test_health_and_state_use_real_local_api(self):
        self.assertTrue(self.client.is_running())
        self.assertFalse(self.client.local_state()["connection"]["connected"])

    def test_real_http_refusals_have_actionable_errors(self):
        with self.assertRaisesRegex(launch.LaunchError, "Connect the desk Pico first"):
            self.client.request("/api/camera/connect", {"port": "PICO_WIFI"})
        with self.assertRaisesRegex(launch.LaunchError, "Only read-only"):
            self.client.request("/api/command", {"command": "F"})
        self.assertTrue(self.bridge.pending.empty())

    def test_wrong_application_and_hosted_mode_rejected(self):
        with patch.object(self.client, "request", return_value={"app": "other", "version": 2}):
            with self.assertRaisesRegex(launch.LaunchError, "Another application"):
                self.client.is_running()
        with patch.object(self.client, "request", return_value={"mode": "hosted", "read_only": True}):
            with self.assertRaisesRegex(launch.LaunchError, "local read-only"):
                self.client.local_state()


if __name__ == "__main__":
    unittest.main(verbosity=2)
