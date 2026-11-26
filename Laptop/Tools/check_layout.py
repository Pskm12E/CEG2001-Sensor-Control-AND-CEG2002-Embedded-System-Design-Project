"""Check active board entry points and relative Markdown links without using hardware."""
from pathlib import Path
import os
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
ENTRY_POINTS = (
    "Start Robot.cmd",
    "Car/MSP430/robot_supervisor/main.c",
    "Car/Arduino_Uno/zumo_line_follow/zumo_line_follow.ino",
    "Car/Arduino_Uno/zumo_line_follow/robot_link.h",
    "Car/ESP32_Gateway/robot_wifi_gateway/robot_wifi_gateway.ino",
    "Car/XIAO_ESP32S3_Camera/xiao_camera_wifi/xiao_camera_wifi.ino",
    "Laptop/Pico_W/laptop_wifi_bridge/main.cpp",
    "Laptop/Pico_W/cmake/pico_sdk_import.cmake",
    "Laptop/Dashboard/launch.py",
    "Laptop/Dashboard/server.py",
    "Laptop/Dashboard/Start Dashboard.cmd",
    "Docking_Station/MSP430/build_station.ps1",
    "output/pdf/CEG2001_Report_P2-2.pdf",
)
STATION_FILES = ("main.c", "lcd16.c", "lcd16.h", ".project", ".cproject", ".ccsproject",
                 "lnk_msp430f5529.cmd", "targetConfigs/MSP430F5529.ccxml")
EXCLUDE = {".git", ".venv", ".vscode", "work", "tmp", "node_modules", "__pycache__",
           "build", "Release", ".metadata", "camera-private"}
LINK = re.compile(r"\]\((?:<([^>]+)>|([^\s)]+))\)")


def markdown_files():
    """Prune build products and private folders before descending into the tree."""
    for directory, children, filenames in os.walk(ROOT):
        children[:] = [name for name in children if name not in EXCLUDE
                       and not name.startswith(("board_backup_", "build-", "Debug", ".ccs"))]
        for name in filenames:
            if name.lower().endswith(".md"):
                yield Path(directory) / name


def main():
    required = [ROOT / entry for entry in ENTRY_POINTS]
    for variant in ("standalone", "waterlevel"):
        required.extend(ROOT / "Docking_Station/MSP430" / variant / name for name in STATION_FILES)
    errors = [f"Missing {path.relative_to(ROOT)}" for path in required if not path.is_file()]
    checked = 0
    for path in markdown_files():
        for angle, plain in LINK.findall(path.read_text(encoding="utf-8-sig")):
            url = urlsplit(angle or plain)
            if url.scheme or url.netloc or not url.path:
                continue
            target = path.parent / unquote(url.path)
            checked += 1
            if not target.exists():
                errors.append(f"{path.relative_to(ROOT)} -> {url.path}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"PASS: active board sources, both station CCS projects and {checked} local links.")


if __name__ == "__main__":
    main()
