"""Explicit hardware check through the website API; only onboard LED diagnostics."""
import argparse
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--port", required=True, help="MSP Application UART, for example COM13")
parser.add_argument("--url", default="http://127.0.0.1:8765")
args = parser.parse_args()
results = []


def api(path, data=None):
    request = Request(args.url + path,
                      data=json.dumps(data).encode() if data is not None else None,
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=4) as response:
        return json.load(response)


def wait_for(label, predicate):
    end = time.monotonic() + 6
    while time.monotonic() < end:
        state = api("/api/state")
        if predicate(state):
            results.append(label)
            print("PASS", label, flush=True)
            return state
        time.sleep(0.15)
    raise AssertionError(label)


api("/api/connect", {"port": args.port})
try:
    wait_for("real MSP430 status received", lambda s: s["connection"]["fresh"] and s["telemetry"]["board"] == "MSP430F5529")
    for command, reply in [("PING", "PONG MSP430"), ("ON", "OK LED2 ON"),
                           ("OFF", "OK LED2 OFF"), ("LOOPBACK", "LOOPBACK PASS: 12 bytes")]:
        start_id = max(e["id"] for e in api("/api/state")["events"])
        api("/api/command", {"command": command})
        wait_for(f"{command} acknowledged by board", lambda s: any(e["id"] > start_id and reply in e["message"] for e in s["events"]))
    final = wait_for("final LED off and UART idle", lambda s: s["telemetry"]["led2"] == "OFF" and s["telemetry"]["uart0"] == "IDLE")
finally:
    api("/api/disconnect", {})
wait_for("disconnect marks last readings not live", lambda s: not s["connection"]["connected"] and not s["connection"]["fresh"])

report_path = Path(__file__).resolve().parents[2] / "output" / "verification" / "local-dashboard-2026-10-29.json"
# parents[2] is Local_Website's parent, the project root.
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text(json.dumps({"software_tests_passed": 14, "live_hardware_checks": results,
    "final_telemetry": final["telemetry"], "actuators_tested": False,
    "camera_hardware_tested": False}, indent=2), encoding="utf-8")
print(report_path)
