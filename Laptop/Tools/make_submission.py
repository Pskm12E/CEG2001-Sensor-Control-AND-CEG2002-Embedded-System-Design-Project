"""Collect the final robot sources and linked project documents in a portable ZIP."""
from pathlib import Path
import argparse
import os
import re
from tempfile import NamedTemporaryFile
from urllib.parse import unquote, urlsplit
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[2]
# Include by role. Generated Wi-Fi headers, captures, saved settings and
# firmware binaries never enter the archive, even after a local build.
GROUPS = {
    ".": ("README.md", "Start Robot.cmd"),
    "Car/Arduino_Uno": ("build_zumo.ps1", "README.md"),
    "Car/Arduino_Uno/zumo_line_follow": ("*.ino", "*.h", "README.md"),
    "Car/Arduino_Uno/tests": ("check_zumo.py",),
    "Car/MSP430": ("build_robot_supervisor.ps1",),
    "Car/MSP430/robot_supervisor": ("main.c", "*.h", "*.cmd", ".project", ".cproject",
                                    ".ccsproject", "targetConfigs/*.ccxml", ".settings/*.prefs",
                                    "README.md", "PUMP_SETUP.md", "ULTRASONIC_SETUP.md"),
    "Car/MSP430/tests": ("check_supervisor_logic.py", "check_ultrasonic.py",
                         "check_console_tx_interrupt.py", "check_spray_job.py", "fixtures/legacy_peer.h"),
    "Car/ESP32_Gateway": ("README.md",),
    "Car/ESP32_Gateway/robot_wifi_gateway": ("*.ino", "direct_protocol.h"),
    "Car/XIAO_ESP32S3_Camera": ("build_camera_wifi.ps1", "xiao_camera_wifi/*.ino", "README.md"),
    "Laptop/Pico_W": ("README.md", "laptop_wifi_bridge/*.cpp", "laptop_wifi_bridge/*.h", "laptop_wifi_bridge/CMakeLists.txt",
                      "cmake/pico_sdk_import.cmake"),
    "Laptop/Dashboard": ("*.py", "requirements.txt", "Start Dashboard.cmd", "README.md",
                         "static/index.html", "static/styles.css", "static/app.js", "tests/test_*.py"),
    "Laptop/Tools": ("check_layout.py", "make_submission.py"),
    "Laptop/Tools/Communication": ("configure.py", "build_env.ps1", "build_desk_pico.ps1", "build_direct.ps1",
                                  "upload_esp32.ps1", "upload_pico.ps1", "desk_console.py", "Open Pico Console.cmd",
                                  "libraries/RobotBench/library.properties", "libraries/RobotBench/src/RobotBench.h",
                                  "libraries/RobotBench/src/SupervisorBridge.h", "tests/protocol_tests.cpp",
                                  "tests/check_direct.py", "tests/check_desk_actions.py", "tests/check_desk_pico.py",
                                  "tests/check_video_receiver.py", "tests/verify_desk_wifi.py", "tests/verify_direct_wifi.py",
                                  "README.md", "board-placement.md", "desk-pico-setup.md", "direct-wifi-wiring.md"),
    "Docking_Station": ("README.md", "Booster_Board/README.md", "MSP430/README.md",
                       "MSP430/build_station.ps1", "tests/check_dock.py"),
    "Laptop/Presentation": ("Robot presenter notes - 17 slides.md", "Robot and refill station - hardware block diagram.pdf"),
    "output/pdf": ("CEG2001_Report_P2-2.pdf",),
}
STATION_FILES = ("main.c", "lcd16.c", "lcd16.h", "lnk_msp430f5529.cmd", ".project", ".cproject",
                 ".ccsproject", ".settings/*.prefs", "targetConfigs/MSP430F5529.ccxml")
CANVA = "https://www.canva.com/d/4f2vKg5oXtSbtI9"
LINK = re.compile(r"\]\((?:<([^>]+)>|([^\s)]+))\)")
PRIVATE = {"local-network.json", "networkconfig.h", ".env", ".git", "tmp", "work",
           "camera-private", "build", "debug", "node_modules", "__pycache__", ".venv"}


def files_to_include():
    """Start from final board files and follow local documentation links."""
    files = set()
    groups = dict(GROUPS)
    for variant in ("standalone", "waterlevel"):
        groups[f"Docking_Station/MSP430/{variant}"] = STATION_FILES
    for folder, patterns in groups.items():
        for pattern in patterns:
            matches = [p for p in (ROOT / folder).glob(pattern) if p.is_file()]
            if not matches and "*" not in pattern:
                raise ValueError(f"Missing submission file: {folder}/{pattern}")
            files.update(matches)
    pending = list(files)
    while pending:
        path = pending.pop()
        if path.suffix.lower() != ".md":
            continue
        body = path.read_text(encoding="utf-8-sig")
        for angle, plain in LINK.findall(body):
            target = angle or plain
            url = urlsplit(target)
            if url.hostname and ("canva.com" in url.hostname or "canva.link" in url.hostname) and target != CANVA:
                raise ValueError(f"Unexpected presentation link in {path.name}")
            if url.scheme or url.netloc or not url.path:
                continue
            linked = (path.parent / unquote(url.path)).resolve()
            if not linked.is_relative_to(ROOT) or not linked.exists():
                raise ValueError(f"Broken submission link in {path.relative_to(ROOT)}: {target}")
            if linked.is_dir():
                if any(p.is_relative_to(linked) for p in files):
                    continue
                linked = linked / "README.md"
                if not linked.is_file():
                    raise ValueError(f"Linked folder has no packaged file: {target}")
            if linked not in files:
                files.add(linked)
                pending.append(linked)
    for file in files:
        rel = file.relative_to(ROOT)
        if any(part.lower() in PRIVATE or part.startswith(("board_backup_", "Debug", ".env")) for part in rel.parts):
            raise ValueError(f"Private or generated file: {rel}")
        if file.suffix.lower() in {".out", ".hex", ".bin", ".uf2", ".zip", ".pptx", ".key", ".pem", ".log"}:
            raise ValueError(f"Unexpected binary or draft: {rel}")
    return sorted(files)


def main():
    """Build in a temporary file, test its integrity and atomically publish the archive."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "output/submission/CEG2001_CEG2002_P2-2_Source.zip")
    args = parser.parse_args()
    if args.output.suffix.lower() != ".zip":
        parser.error("Choose a .zip file for the submission archive.")
    files = files_to_include()
    if args.output.resolve() in files:
        parser.error("The output must be separate from the submission sources.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=args.output.parent, suffix=".zip", delete=False) as temporary:
        name = Path(temporary.name)
    try:
        with ZipFile(name, "w", compression=ZIP_DEFLATED) as archive:
            for file in files:
                archive.write(file, file.relative_to(ROOT).as_posix())
        with ZipFile(name) as archive:
            if archive.testzip():
                raise ValueError("ZIP integrity check failed.")
        os.replace(name, args.output)
    finally:
        name.unlink(missing_ok=True)
    print(f"Packaged {len(files)} files into {args.output}")


if __name__ == "__main__":
    main()
