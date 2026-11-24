from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dock_relay import DockRelay


class DockVisitTests(unittest.TestCase):
    def setUp(self):
        self.bridge, self.usb = Mock(), Mock()
        self.state = {"connection": {"fresh": True}, "telemetry": {}}
        self.bridge.state.return_value = self.state
        self.relay = DockRelay(self.bridge)

    def sample(self, phase, now):
        visit = 0 if phase == "CLEAR" else 1
        self.assertTrue(self.relay.sample(f"DOCK1 {visit} {phase}", self.usb, now))

    def arrive(self):
        self.sample("CLEAR", 1)
        self.sample("ARRIVAL", 1.1)
        self.bridge.dock_command.assert_called_with(f"ROBOT DOCK {self.relay.token}")
        self.state["telemetry"] = dict(dock_visit=self.relay.token, uno_link="READY",
                                       run=0, pump=0, calibration="READY", wet=1)

    def test_wet_car_waits_for_dock_cutoff(self):
        self.arrive()
        self.usb.write.assert_not_called()
        for time, phase in enumerate(("ARRIVAL", "SETTLE", "FILL"), 2):
            self.sample(phase, time)
            self.usb.write.assert_called_with(b"HOLD 1\n")
            self.bridge.dock_command.assert_called_with(f"ROBOT DOCK {self.relay.token}")
        self.state["telemetry"]["wet"] = 0
        self.sample("DONE", 12)
        self.bridge.dock_command.assert_called_with(f"ROBOT DOCK {self.relay.token}")
        self.state["telemetry"]["wet"] = 1
        self.sample("DONE", 13)
        self.bridge.dock_command.assert_called_with(f"ROBOT DEPART {self.relay.token}")

    def test_stale_ack_and_fault_cancel(self):
        self.arrive()
        self.sample("ARRIVAL", 2)
        self.state["connection"]["fresh"] = False
        self.sample("FILL", 4)
        self.bridge.dock_command.assert_called_with("ROBOT STOP")
        self.assertEqual(self.usb.write.call_count, 1)
        self.state["connection"]["fresh"] = True
        self.sample("FAULT", 5)
        self.sample("DONE", 6)
        self.assertEqual(self.usb.write.call_count, 1)
        self.assertEqual(self.relay.token, 0)

    def test_reconnect_with_occupied_dock_requires_clear(self):
        for time, phase in enumerate(("BOOT", "ARRIVAL", "SETTLE", "DONE"), 1):
            self.sample(phase, time)
        self.bridge.dock_command.assert_not_called()
        self.usb.write.assert_not_called()
