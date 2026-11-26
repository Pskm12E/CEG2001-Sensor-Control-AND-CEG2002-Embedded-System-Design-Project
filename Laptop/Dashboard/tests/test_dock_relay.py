from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dock_relay import DockRelay
import tank_scale


class DockVisitTests(unittest.TestCase):
    def setUp(self):
        self.bridge, self.usb = Mock(), Mock()
        self.state = {"connection": {"fresh": True}, "telemetry": {},
                      "tank_calibration": {"empty": 1836, "full": 2281}}
        self.bridge.state.return_value = self.state
        self.relay = DockRelay(self.bridge)

    def sample(self, phase, now, *, hall=None, pump=None):
        visit = 0 if phase == "CLEAR" else 1
        hall = int(phase != "CLEAR") if hall is None else hall
        pump = int(phase == "FILL") if pump is None else pump
        self.relay.sample(f"HALL1 {hall} PUMP={pump}", self.usb, now)
        self.assertTrue(self.relay.sample(f"DOCK1 {visit} {phase}", self.usb, now))

    def arrive(self):
        self.sample("CLEAR", 1)
        self.sample("ARRIVAL", 1.1)
        self.bridge.dock_command.assert_called_with(f"ROBOT DOCK {self.relay.token}")
        self.state["telemetry"] = dict(dock_visit=self.relay.token, uno_link="READY",
                                       run=0, pump=0, calibration="READY", wet=1, water_raw=2103)

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
        self.sample("DONE", 13)  # 2103 is exactly 60% on this tank.
        self.bridge.dock_command.assert_called_with(f"ROBOT DOCK {self.relay.token}")
        self.state["telemetry"]["water_raw"] = 2104
        self.sample("DONE", 14)
        self.sample("DONE", 16.9)
        self.bridge.dock_command.assert_called_with(f"ROBOT DOCK {self.relay.token}")
        self.sample("DONE", 17)
        self.bridge.dock_command.assert_called_with(f"ROBOT DEPART {self.relay.token}")

    def test_refilled_car_requests_cutoff_before_departing(self):
        self.arrive()
        self.state["telemetry"]["water_raw"] = 2104
        self.sample("FILL", 4)
        self.usb.write.assert_called_with(b"FULL 1\n")
        for phase, hall, pump in (("FILL", 1, 1), ("DONE", 1, 1), ("DONE", "?", 0), ("DONE", 0, 0)):
            self.sample(phase, 5, hall=hall, pump=pump)
            self.bridge.dock_command.assert_called_with(f"ROBOT DOCK {self.relay.token}")
        self.sample("DONE", 6)
        self.assertEqual(self.relay.snapshot(6)["departure_wait_s"], 3)
        self.sample("DONE", 8.9)
        self.bridge.dock_command.assert_called_with(f"ROBOT DOCK {self.relay.token}")
        self.sample("DONE", 9)
        self.bridge.dock_command.assert_called_with(f"ROBOT DEPART {self.relay.token}")

    def test_departure_pause_restarts_if_level_dips_or_pump_turns_on(self):
        self.arrive()
        car = self.state["telemetry"]
        car["water_raw"] = 2104
        self.sample("DONE", 3)
        car["water_raw"] = 2103
        self.sample("DONE", 5)
        self.assertIsNone(self.relay.snapshot(5)["departure_wait_s"])
        car["water_raw"] = 2104
        self.sample("DONE", 6)
        self.sample("DONE", 8, pump=1)
        self.sample("DONE", 9)
        self.sample("DONE", 11.9)
        self.bridge.dock_command.assert_called_with(f"ROBOT DOCK {self.relay.token}")
        self.sample("DONE", 12)
        self.bridge.dock_command.assert_called_with(f"ROBOT DEPART {self.relay.token}")

    def test_boot_magnet_reports_without_starting_a_visit_and_expires(self):
        self.sample("BOOT", 1)
        self.assertTrue(self.relay.snapshot(1)["docked"])
        self.assertIsNone(self.relay.snapshot(4)["docked"])
        self.sample("CLEAR", 5)
        self.assertIs(self.relay.snapshot(5)["docked"], False)
        self.usb.write.assert_not_called()

    def test_uncalibrated_or_older_station_cannot_release_car(self):
        self.arrive()
        self.state["tank_calibration"] = {}
        self.sample("FILL", 4)
        self.usb.write.assert_not_called()
        self.state["tank_calibration"] = {"empty": 10, "full": 100}
        self.relay.sample("DOCK1 1 DONE", self.usb, 10)
        self.bridge.dock_command.assert_called_with(f"ROBOT DOCK {self.relay.token}")

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

    def test_discovery_listens_to_application_ports_and_recognizes_only_station(self):
        def port(device, label):
            return SimpleNamespace(vid=0x2047, pid=0x0013, device=device, description=label)
        ports = [port("COM1", "MSP Debug"), port("COM2", "MSP Application UART"),
                 port("COM3", "MSP Application UART")]
        car, station = MagicMock(), MagicMock()
        for device in (car, station):
            device.__enter__.return_value = device
        car.read_until.return_value = b"MSP STATUS\n"
        station.read_until.return_value = b"DOCK1 1 BOOT\n"
        with (patch("dock_relay.list_ports.comports", return_value=ports),
              patch("dock_relay.serial.Serial", side_effect=[car, station]) as opened,
              patch("dock_relay.time.monotonic", side_effect=[0, 1, 2, 3, 4]),
              patch.object(self.relay, "_run") as run):
            self.relay._discover()
        self.assertEqual([call.args[0] for call in opened.call_args_list], ["COM2", "COM3"])
        run.assert_called_once_with(station)
        car.write.assert_not_called()
        station.write.assert_not_called()

    def test_tank_calibration_survives_restart_and_preserves_previous_points_on_error(self):
        with TemporaryDirectory() as folder, patch.object(tank_scale, "path", return_value=Path(folder) / "tank.json"):
            tank_scale.save({"empty": 1836})
            self.assertIsNone(tank_scale.departure_raw(tank_scale.load()))
            tank_scale.save(self.state["tank_calibration"])
            with self.assertRaises(ValueError):
                tank_scale.save({"empty": 2281, "full": 1836})
            self.assertEqual(tank_scale.departure_raw(tank_scale.load()), 2104)
            tank_scale.save({})
            self.assertIsNone(tank_scale.departure_raw(tank_scale.load()))
