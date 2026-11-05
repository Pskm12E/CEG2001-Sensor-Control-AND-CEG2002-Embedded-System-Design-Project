"""Create a private bench network, without using the user's home/lab Wi-Fi."""
import json
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parent
settings_path = ROOT / "local-network.json"
if settings_path.exists():
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
else:
    settings = {"ssid": "PlantRobot-" + secrets.token_hex(3),
                "password": secrets.token_urlsafe(18)}
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
if not (1 <= len(settings["ssid"]) <= 32 and 8 <= len(settings["password"]) <= 63):
    raise SystemExit("Invalid network-name or password length in local-network.json")
header = ROOT / "libraries/RobotBench/src/NetworkConfig.h"
header.write_text(
    "// Generated locally by configure.py. Keep this file private.\n#pragma once\n"
    f"#define BENCH_SSID {json.dumps(settings['ssid'])}\n"
    f"#define BENCH_PASSWORD {json.dumps(settings['password'])}\n",
    encoding="ascii",
)
print("Bench network configuration ready for both builds. Password not printed.")
