"""Check repository links and active entrypoints without opening hardware."""
from pathlib import Path
import re
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parents[2]
EXCLUDED={'build','Debug','Debug_wifi','Release','.git','tmp','work','__pycache__','.venv'}
errors=[]
for folder in ('Car','Laptop','Docking_Station'):
    if not (ROOT/folder/'README.md').exists():
        errors.append(f'Missing {folder}/README.md')
for relative in (
    'Car/MSP430/robot_supervisor/main.c',
    'Car/Arduino_Uno/msp_line_follow/msp_line_follow.ino',
    'Car/ESP32_Gateway/robot_wifi_gateway/robot_wifi_gateway.ino',
    'Car/XIAO_ESP32S3_Camera/xiao_camera_wifi/xiao_camera_wifi.ino',
    'Laptop/Pico_W/laptop_wifi_bridge/main.cpp',
    'Laptop/Pico_W/cmake/pico_sdk_import.cmake',
    'Laptop/Dashboard/server.py',
    'Laptop/Dashboard/Start Dashboard.cmd',
    'Laptop/YOLO_Model/README.md',
):
    if not (ROOT/relative).is_file():
        errors.append('Missing '+relative)
links=0
for path in ROOT.rglob('*.md'):
    if any(part in EXCLUDED or part.startswith(('board_backup_','build-')) for part in path.relative_to(ROOT).parts):
        continue
    for target in re.findall(r'\]\(([^)]+)\)',path.read_text(encoding='utf-8-sig')):
        target=unquote(target.strip('<>').split('#',1)[0])
        if not target or target.startswith(('https:','http:','mailto:','/')):
            continue
        links+=1
        if not (path.parent/target).exists():
            errors.append(f'{path.relative_to(ROOT)}: {target}')
if errors:
    raise SystemExit('\n'.join(errors))
print(f'PASS: three device groups, active entrypoints, and {links} local documentation links.')
