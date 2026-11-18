"""Target-to-job tests use simulated camera/USB/robot data only."""
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from desk_bridge import Bridge, ActionPriority, parse_status
from test_server import ZUMO, remote_line

CONFIRMED = {"detected": True, "box": [20, 30, 40, 40]}
ABSENT = {"detected": False, "box": None}


def telemetry(phase=0, token=0, pump=0, ready=1, running=True):
    value = ZUMO.replace("RUN=0", f"RUN={int(running)}").replace("FLAGS=96", f"FLAGS={9 if running else 1}")
    return value.replace(" BRIDGE=", f" JOB={phase} JOB_ID={token} PUMP={pump} READY={ready} WATER=987 BRIDGE=")


def receive(bridge, phase=0, token=0, pump=0, ready=1, running=True, **changes):
    bridge._receive(remote_line(firmware="DIRECT_WIFI_V2", telemetry=telemetry(phase, token, pump, ready, running),
                                target_id=token, target_state="REQUEST_ACCEPTED", **changes))


def linked():
    b = Bridge()
    b.connected = b.identity = b.target_supported = True
    b.pico_seen = time.monotonic()
    b.video.enabled = True
    b.video.value["connected"] = True
    b.video.received = time.monotonic()
    receive(b)
    return b


class TargetJobTests(unittest.TestCase):
    def test_new_status_fields_and_invalid_ranges(self):
        self.assertEqual(parse_status(telemetry())["water_raw"], 987)
        for text in (telemetry().replace("JOB=0", "JOB=9"), telemetry().replace("WATER=987", "WATER=4096"),
                     telemetry().replace("JOB_ID=0", "JOB_ID=4294967296")):
            self.assertIsNone(parse_status(text))

    def test_once_per_continuously_visible_target(self):
        b = linked()
        for _ in range(20): b.observe_target(CONFIRMED)
        self.assertTrue(b.action_pending.is_set())
        self.assertEqual(len([e for e in b.events if e["kind"] == "target"]), 1)
        with patch.object(b, "_exchange", return_value="ROBOT TARGET SENT ID=42") as send:
            b._send_target(None)
        self.assertEqual(send.call_count, 1)
        self.assertEqual(b.target_action["request_id"], 42)
        receive(b, 6, 42)
        b.observe_target(CONFIRMED)
        self.assertFalse(b.action_pending.is_set())

    def test_fresh_absence_rearms_but_one_missing_frame_does_not(self):
        b = linked(); b.observe_target(CONFIRMED); b.action_pending.clear()
        b.target_action["state"] = "COMPLETE"
        tick = time.monotonic()
        with patch("desk_bridge.time.monotonic", return_value=tick): b.observe_target(ABSENT)
        b.observe_target(CONFIRMED)
        self.assertFalse(b.action_pending.is_set())
        with patch("desk_bridge.time.monotonic", return_value=tick): b.observe_target(ABSENT)
        with patch("desk_bridge.time.monotonic", return_value=tick+1.1): b.observe_target(ABSENT)
        b.observe_target(CONFIRMED)
        self.assertTrue(b.action_pending.is_set())

    def test_stale_foreign_or_old_firmware_never_queues_a_job(self):
        for kind in ("stale", "old-pico", "old-esp", "hosted", "not-driving"):
            b = linked()
            if kind == "stale": b.last_seen_monotonic -= 5
            elif kind == "old-pico": b.target_supported = False
            elif kind == "old-esp": b.remote["firmware"] = "DIRECT_WIFI_V1"
            elif kind == "hosted": b.hosted = True
            else: receive(b, running=False)
            b.observe_target(CONFIRMED)
            self.assertFalse(b.action_pending.is_set(), kind)

    def test_expired_or_failed_request_is_not_replayed(self):
        b = linked(); b.observe_target(CONFIRMED); b.action_at -= 1
        with patch.object(b, "_exchange") as send: b._send_target(None)
        send.assert_not_called()
        self.assertEqual(b.target_action["state"], "EXPIRED")
        b.observe_target(CONFIRMED); self.assertFalse(b.action_pending.is_set())
        b = linked(); b.observe_target(CONFIRMED)
        with patch.object(b, "_exchange", side_effect=TimeoutError("lost")): b._send_target(None)
        self.assertEqual(b.target_action["state"], "UNKNOWN")
        b.observe_target(CONFIRMED); self.assertFalse(b.action_pending.is_set())

    def test_resume_needs_matching_job_pump_off_and_fresh_camera(self):
        for failure in ("none", "wrong-token", "stale-camera", "driver-disabled", "pump-on"):
            b = linked(); b.observe_target(CONFIRMED)
            with patch.object(b, "_exchange", return_value="ROBOT TARGET SENT ID=42"): b._send_target(None)
            if failure == "stale-camera": b.last_observation -= 1
            receive(b, phase=5, token=99 if failure == "wrong-token" else 42,
                    ready=0 if failure == "driver-disabled" else 1, pump=int(failure == "pump-on"), running=False)
            self.assertEqual(b.action_pending.is_set(), failure == "none", failure)
            if failure == "none":
                self.assertEqual(b.action_command, "ROBOT RESUME 42")
                with patch.object(b, "_exchange", return_value="ROBOT RESUME SENT ID=43"): b._send_target(None)
                receive(b, 5, 42, running=False)
                self.assertFalse(b.action_pending.is_set())

    def test_stop_detection_cancels_pending_and_inflight_cycles(self):
        b = linked(); b.observe_target(CONFIRMED); b.cancel_target()
        self.assertFalse(b.action_pending.is_set())
        self.assertEqual(b.target_action["state"], "CANCELLED")
        b = linked(); b.observe_target(CONFIRMED)
        with patch.object(b, "_exchange", return_value="ROBOT TARGET SENT ID=42"): b._send_target(None)
        b.cancel_target()
        self.assertEqual(b.action_command, "ROBOT STOP")
        receive(b, 5, 42, running=False)
        self.assertEqual(b.action_command, "ROBOT STOP")

    def test_request_preempts_a_slow_telemetry_read(self):
        b = linked(); b.observe_target(CONFIRMED)
        class Device:
            def write(self, data): pass
        with self.assertRaises(ActionPriority): b._exchange(Device(), "ROBOT STATE", "ROBOT STATE ")

    def test_disabled_driver_is_visible_and_never_resumes(self):
        b = linked(); b.observe_target(CONFIRMED)
        with patch.object(b, "_exchange", return_value="ROBOT TARGET SENT ID=42"): b._send_target(None)
        receive(b, 8, 42, ready=0, running=False)
        self.assertEqual(b.target_action["state"], "DRIVER_DISABLED")
        self.assertFalse(b.action_pending.is_set())
        self.assertIn("disabled", b.target_action["error"])


if __name__ == "__main__": unittest.main()
