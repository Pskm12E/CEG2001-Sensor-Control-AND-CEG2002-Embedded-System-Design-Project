"""Exercise the real MSP430 USB console; no Arduino or motor access."""
from pathlib import Path
import argparse
import datetime
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tmp" / "pico-tools-python"))
import serial

parser = argparse.ArgumentParser()
parser.add_argument("--port", default="COM13")
args = parser.parse_args()
results = []


def read_until(port, expected, timeout=3.0):
    response = bytearray()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response.extend(port.read(port.in_waiting or 1))
        if expected in response:
            return bytes(response)
    raise AssertionError(f"Missing {expected!r}; received {bytes(response)!r}")


with serial.Serial(args.port, 9600, timeout=0.05, write_timeout=1) as port:
    def check(name, payload, expected):
        port.reset_input_buffer()
        port.write(payload)
        response = read_until(port, expected)
        results.append({"check": name, "response": response.decode("ascii", "backslashreplace")})
        print(f"PASS {name}: {response.decode('ascii', 'backslashreplace').strip()}", flush=True)
        return response

    check("USB request/reply", b"PING\n", b"PONG MSP430\r\n")
    check("help", b"HELP\n", b"No motor or pump commands.\r\n")
    check("initial status", b"STATUS\n", b"BENCH_ONLY\r\n")
    check("LED2 on", b"ON\n", b"OK LED2 ON\r\n")
    response = check("LED2 on status", b"STATUS\n", b"BENCH_ONLY\r\n")
    assert b"LED2=ON" in response
    check("LED2 off", b"OFF\n", b"OK LED2 OFF\r\n")
    check("unknown command rejected", b"FORWARD\n", b"ERR UNKNOWN COMMAND\r\n")
    check("oversized command rejected", b"ON" + b"X" * 60 + b"\n", b"ERR INVALID LINE\r\n")
    check("invalid byte rejected", b"ON\x00\n", b"ERR INVALID LINE\r\n")
    response = check("rejected inputs kept LED2 off", b"STATUS\n", b"BENCH_ONLY\r\n")
    assert b"LED2=OFF" in response
    check("lowercase and CRLF", b"ping\r\n", b"PONG MSP430\r\n")

    port.reset_input_buffer()
    port.write(b"PI")
    time.sleep(0.08)
    port.write(b"NG\n")
    response = read_until(port, b"PONG MSP430\r\n")
    results.append({"check": "fragmented command", "response": response.decode("ascii")})
    print("PASS fragmented command", flush=True)

    for attempt in range(1, 6):
        check(f"internal UART0 loopback {attempt}", b"LOOPBACK\n",
              b"LOOPBACK PASS: 12 bytes, internal UART0 only\r\n")
    check("missing Arduino times out", b"LINK PING\n",
          b"LINK TIMEOUT: no confirmed Arduino reply\r\n")
    response = check("timeout recovery and final status", b"STATUS\n", b"BENCH_ONLY\r\n")
    assert b"UART0=IDLE" in response and b"LED2=OFF" in response
    assert b"UART_ERRORS=0" in response and b"RX_DROPS=0" in response

report = ROOT / "output" / "verification" / "msp430-usb-console-2026-10-29.json"
report.parent.mkdir(parents=True, exist_ok=True)
report.write_text(json.dumps({
    "time": datetime.datetime.now().astimezone().isoformat(),
    "port": args.port, "baud": 9600, "checks_passed": len(results),
    "physical_interboard_link_tested": False, "results": results,
}, indent=2), encoding="utf-8")
print(f"All {len(results)} checks passed. Report: {report}")
