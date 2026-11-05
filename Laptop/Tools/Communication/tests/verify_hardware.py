"""Exercise only the two bench firmwares. Never opens the Uno or MSP430."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tmp/pico-tools-python"))
import serial
from serial.tools import list_ports

parser = argparse.ArgumentParser()
parser.add_argument("--esp", required=True)
parser.add_argument("--pico", required=True)
parser.add_argument("--reset-test", action="store_true", help="Also reset the ESP32 to test recovery")
parser.add_argument("--report", type=Path, help="Optional report destination; default is a timestamped verification file")
parser.add_argument("--round-trips", type=int, default=30, help="Number of repeated radio PING checks")
parser.add_argument("--bridge-unwired", action="store_true", help="BRIDGE2 firmware with MSP I2C wires disconnected")
args = parser.parse_args()
if not 1 <= args.round_trips <= 300:
    parser.error("--round-trips must be between 1 and 300")
ports = {p.device: p for p in list_ports.comports()}
for name, identity in ((args.esp, (0x1A86, 0x7523)), (args.pico, (0x2E8A, 0x000A))):
    p = ports.get(name)
    if not p or (p.vid, p.pid) != identity:
        raise SystemExit(f"Unexpected USB identity on {name}; no device opened")

checks = []
def check(name, passed, evidence):
    checks.append({"check": name, "passed": bool(passed), "evidence": evidence})
    print(("PASS " if passed else "FAIL ") + name, flush=True)
    if not passed:
        raise AssertionError(f"{name}: {evidence}")

def open_port(name):
    port = serial.Serial()
    port.port, port.baudrate, port.timeout = name, 115200, 0.1
    port.dtr = False
    port.rts = False
    port.open()
    return port

def exchange(port, command, needle, timeout=4):
    port.reset_input_buffer()
    data = command.encode("ascii") if isinstance(command, str) else command
    port.write(data + b"\n")
    deadline = time.monotonic() + timeout
    seen = []
    while time.monotonic() < deadline:
        line = port.readline().decode("ascii", errors="replace").strip()
        if line:
            seen.append(line)
            if needle in line:
                return line
            if line.startswith("BUSY "):
                time.sleep(0.15)
                port.write(data + b"\n")
    return " | ".join(seen)

def wait_up(esp, timeout=35):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = exchange(esp, "STATUS", "STATUS BOARD=ESP32", 1)
        if "PICO_LINK=UP" in result:
            return result
        time.sleep(0.5)
    return result

esp = pico = None
try:
    esp, pico = open_port(args.esp), open_port(args.pico)
    # Pico SDK USB stdio requires host DTR. ESP32 uses a separate UART bridge;
    # keep its DTR low to avoid driving the ESP32 boot strap.
    pico.dtr = True
    time.sleep(1)
    result = exchange(esp, "PING", "PONG ESP32_GATEWAY")
    check("ESP32 USB firmware identity", "PONG ESP32_GATEWAY" in result, result)
    result = exchange(pico, "PING", "PONG PICO_W_USB")
    check("Pico USB firmware identity", "PONG PICO_W_USB" in result, result)
    result = wait_up(esp)
    check("Wireless handshake", "PICO_LINK=UP" in result, result)
    check("MSP link truthfully absent", "MSP_LINK=NOT_CONNECTED" in result, result)
    result = exchange(esp, "ROBOT PING", "ROBOT PONG PICO_W")
    check("USB to Wi-Fi round trip", "ROBOT PONG PICO_W" in result, result)
    result = exchange(esp, "ROBOT STATUS", "ROBOT STATUS BOARD=PICO_W")
    check("Pico status returned over Wi-Fi", "MSP_LINK=NOT_CONNECTED" in result, result)
    if args.bridge_unwired:
        check("Pico runs BRIDGE2", "FW=BRIDGE2" in result, result)
        result = exchange(esp, "ROBOT MSP STATUS", "ROBOT MSP ERROR NOT_CONNECTED")
        check("Missing physical MSP link reported", "ROBOT MSP ERROR NOT_CONNECTED" in result, result)
        result = exchange(esp, "ROBOT MSP START", "ERROR unsupported robot command")
        check("Remote movement start is unavailable", "ERROR unsupported robot command" in result, result)
        result = exchange(esp, "ROBOT PING", "ROBOT PONG PICO_W")
        check("Radio remains responsive after absent I2C peer", "ROBOT PONG PICO_W" in result, result)
    for state in ("ON", "OFF"):
        result = exchange(esp, f"ROBOT LED {state}", f"ROBOT LED={state}")
        check(f"Wireless LED {state} acknowledgement", f"ROBOT LED={state}" in result, result)
        result = exchange(pico, "STATUS", "STATUS BOARD=PICO_W")
        check(f"Independent Pico USB confirms LED {state}", f"LED={state}" in result, result)
    result = exchange(esp, "ROBOT SPRAY", "ERROR unsupported robot command")
    check("Actuator command rejected", "ERROR unsupported robot command" in result, result)
    result = exchange(esp, b"X" * 200 + b"PING", "ERROR invalid or oversized USB line")
    check("Oversized USB line rejected", "ERROR invalid or oversized USB line" in result, result)
    result = exchange(esp, b"PI\x00NG", "ERROR invalid or oversized USB line")
    check("Binary USB line rejected", "ERROR invalid or oversized USB line" in result, result)
    result = exchange(esp, b"PING\r", "PONG ESP32_GATEWAY")
    check("CRLF and recovery after invalid input", "PONG ESP32_GATEWAY" in result, result)
    repeated = []
    for _ in range(args.round_trips):
        result = exchange(esp, "ROBOT PING", "ROBOT PONG PICO_W")
        repeated.append(result)
        if "ROBOT PONG PICO_W" not in result:
            break
    check(f"{args.round_trips} repeated Wi-Fi round trips",
          len(repeated) == args.round_trips and all("ROBOT PONG PICO_W" in r for r in repeated),
          repeated)
    if args.reset_test:
        result = exchange(esp, "ROBOT LED ON", "ROBOT LED=ON")
        check("Precondition for disconnect test", "ROBOT LED=ON" in result, result)
        esp.dtr = False
        esp.rts = True
        time.sleep(0.2)
        esp.rts = False
        result = wait_up(esp, 45)
        check("Reconnect after ESP32 reset", "PICO_LINK=UP" in result, result)
        result = exchange(pico, "STATUS", "STATUS BOARD=PICO_W")
        check("LED cleared; old ON not replayed", "LED=OFF" in result, result)
        result = exchange(esp, "ROBOT PING", "ROBOT PONG PICO_W")
        check("Fresh command after reconnect", "ROBOT PONG PICO_W" in result, result)
finally:
    if esp:
        try:
            exchange(esp, "ROBOT LED OFF", "ROBOT LED=OFF", 2)
        except serial.SerialException:
            pass
        esp.close()
    if pico:
        pico.close()
    tested_at = datetime.now(timezone(timedelta(hours=8)))
    report = args.report or ROOT / "Laptop/Artifacts/verification" / f"wireless-bench-{tested_at:%Y-%m-%d-%H%M%S}.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"tested_at": tested_at.isoformat(),
                                 "scope": "USB/Wi-Fi/onboard LED only; no MSP, sensor or actuator integration",
                                 "ports": {"esp32": args.esp, "pico": args.pico},
                                 "checks": checks}, indent=2) + "\n", encoding="utf-8")
    print(f"Report: {report}")
