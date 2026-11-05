"""Read-only integration check against real desk Pico and XIAO USB camera."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import zlib

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument("--port", required=True, help="Desk Pico USB port")
parser.add_argument("--camera", default="PICO_WIFI", choices=["PICO_WIFI"], help="Wireless camera through desk Pico")
parser.add_argument("--url", default="http://127.0.0.1:8765")
parser.add_argument("--keep-connected", action="store_true")
parser.add_argument("--observe-camera", action="store_true", help="Read the running preview without requesting captures")
args=parser.parse_args()
root=Path(__file__).resolve().parents[3]
report={"tested_at":datetime.now().astimezone().isoformat(), "checks":[], "passed":False, "actuators_tested":False}

def api(path, body=None):
    request=Request(args.url+path,data=json.dumps(body).encode() if body is not None else None, headers={"Content-Type":"application/json"})
    with urlopen(request,timeout=12) as response: return json.load(response)

def check(label,ok):
    report["checks"].append({"check":label,"passed":bool(ok)})
    print(("PASS " if ok else "FAIL ")+label,flush=True)
    if not ok: raise AssertionError(label)

try:
    ports=api("/api/ports")["ports"]
    check("Only Pico candidates in robot USB selector",all("Pico" in p["description"] for p in ports) and args.port in [p["device"] for p in ports])
    api("/api/connect",{"port":args.port})
    deadline=time.monotonic()+40
    while time.monotonic()<deadline:
        state=api("/api/state")
        if state["connection"]["fresh"]: break
        time.sleep(.3)
    check("Fresh real MSP430 status through desk Pico Wi-Fi",state["connection"]["fresh"] and state["telemetry"]["board"]=="MSP430F5529")
    check("Uno acknowledged and stopped",state["telemetry"]["uno_link"]=="READY" and state["telemetry"]["run"]==0)
    report["robot_state"]=state
    baseline=state["telemetry"]
    samples=[]; observed=[]; previous=state["connection"]["last_seen"]
    deadline=time.monotonic()+25
    while len(samples)<4 and time.monotonic()<deadline:
        time.sleep(.3); sample=api("/api/state"); observed.append(sample)
        if sample["connection"]["fresh"] and sample["connection"]["last_seen"]!=previous:
            samples.append(sample);previous=sample["connection"]["last_seen"]
    report["poll_observations"]=observed
    report["stale_poll_count"]=sum(not s["connection"]["fresh"] for s in observed)
    check("Four distinct fresh dashboard updates within 25 seconds",len(samples)==4)
    check("Robot error counters unchanged",all(all(s["telemetry"][k]==baseline[k] for k in ("uart_errors","rx_drops","bad_frames")) for s in samples))
    for command in ("START","STOP","SPRAY","ON","W","B"):
        try: api("/api/command",{"command":command})
        except HTTPError as error: check("API rejects "+command,error.code==400)
        else: check("API rejects "+command,False)
    camera=api("/api/state")["camera"]
    if not camera["connected"]:
        api("/api/camera/connect",{"port":args.camera})
    else:
        check("Expected camera USB port",camera["port"]==args.camera)
    frames=[]
    deadline=time.monotonic()+20
    previous=-1
    while len(frames)<3 and time.monotonic()<deadline:
        metadata=api("/api/state")["camera"]
        if metadata["streaming"] and metadata["sequence"]>previous:
            frames.append(metadata);previous=metadata["sequence"]
        time.sleep(.5)
    check("Wireless live frames advance",len(frames)==3 and all(b["sequence"]>a["sequence"] for a,b in zip(frames,frames[1:])))
    check("Camera transport is Wi-Fi through Pico",all(f["transport"]=="WIFI_VIA_PICO" for f in frames))
    check("No corrupt video frames",all(f["corrupt_frames"]==0 for f in frames))
    report["camera_frames"]=frames
    report["passed"]=True
except Exception as exc:
    report["error"]=str(exc);print("ERROR "+str(exc),flush=True)
finally:
    if not args.keep_connected:
        api("/api/camera/disconnect",{});api("/api/disconnect",{})
    path=root/"Laptop/Artifacts/verification"/f"local-dashboard-v2-{datetime.now():%Y-%m-%d-%H%M%S}.json"
    path.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8");print(path,flush=True)
raise SystemExit(0 if report["passed"] else 1)
