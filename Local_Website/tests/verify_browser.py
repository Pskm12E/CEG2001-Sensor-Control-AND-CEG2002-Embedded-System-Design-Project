"""Opt-in UI verification against the local server and connected robot MSP430.

Uses a synthetic camera, never the user's physical camera. LED tests are real.
"""
import json
from pathlib import Path
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tmp" / "website-test-python"))
from playwright.sync_api import sync_playwright, expect

URL = "http://127.0.0.1:8765"
OUT = ROOT / "output" / "verification"
checks = []


def passed(message):
    checks.append(message)
    print("PASS", message, flush=True)


def state():
    with urlopen(URL + "/api/state", timeout=3) as response:
        return json.load(response)


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, channel="msedge",
                               args=["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"])
    context = browser.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(URL)
    page.wait_for_load_state("networkidle")
    expect(page.locator("#connection-badge")).to_have_text("Disconnected")
    expect(page.locator("#camera-badge")).to_have_text("Off")
    assert page.locator("#camera-video").evaluate("video => video.srcObject === null")
    passed("page starts disconnected with camera off")

    page.get_by_role("button", name="Connect", exact=True).click()
    expect(page.locator("#connection-badge")).to_have_text("Connected", timeout=7000)
    expect(page.locator("#board-name")).to_have_text("MSP430F5529")
    expect(page.locator("#connection-error")).to_be_hidden()
    passed("USB connect renders verified hardware identity without lingering error")
    last_id = max(event["id"] for event in state()["events"])
    page.get_by_role("button", name="Ping board", exact=True).click()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if any(e["id"] > last_id and e["message"] == "PONG MSP430" for e in state()["events"]):
            break
        time.sleep(0.1)
    else:
        raise AssertionError("No fresh board PONG")
    passed("Ping button receives a new real board reply")

    page.get_by_role("button", name="LED2 on", exact=True).click()
    expect(page.locator("#led2")).to_have_text("ON", timeout=5000)
    page.get_by_role("button", name="LED2 off", exact=True).click()
    expect(page.locator("#led2")).to_have_text("OFF", timeout=5000)
    passed("LED on/off controls update confirmed telemetry")
    page.get_by_role("button", name="Pause updates", exact=True).click()
    expect(page.locator("#led2")).to_have_text("—")
    expect(page.get_by_role("button", name="LED2 on", exact=True)).to_be_disabled()
    page.get_by_role("button", name="Resume updates", exact=True).click()
    expect(page.locator("#connection-badge")).to_have_text("Connected")
    passed("paused readings are not labelled live and bench controls pause")
    page.screenshot(path=str(OUT / "dashboard-live.png"), full_page=True)

    with page.expect_download() as download_info:
        page.get_by_role("button", name="Save log", exact=True).click()
    data = json.loads(Path(download_info.value.path()).read_text())
    assert any(e["message"] == "PONG MSP430" for e in data["events"])
    passed("activity export contains real board replies")
    page.get_by_role("button", name="Disconnect", exact=True).click()
    expect(page.locator("#connection-badge")).to_have_text("Disconnected")
    expect(page.locator("#led2")).to_have_text("—")
    expect(page.get_by_role("button", name="LED2 on", exact=True)).to_be_disabled()
    passed("disconnect clears live readings and disables commands")

    stale = state()
    stale["connection"].update({"connected": True, "fresh": False, "error": "Waiting for a current MSP430 bench status reply."})
    page.route("**/api/state", lambda route: route.fulfill(json=stale))
    expect(page.locator("#connection-badge")).to_have_text("Waiting for reply", timeout=4000)
    expect(page.locator("#led2")).to_have_text("—")
    expect(page.get_by_role("button", name="LED2 on", exact=True)).to_be_disabled()
    page.unroute("**/api/state")
    expect(page.locator("#connection-badge")).to_have_text("Disconnected", timeout=4000)
    passed("stale telemetry is blanked and controls remain disabled (mocked stale response)")

    page.route("**/api/ports", lambda route: route.fulfill(json={"ports": []}))
    page.get_by_role("button", name="Refresh ports", exact=True).click()
    expect(page.locator("#port-select")).to_contain_text("No MSP430 Application UART found")
    expect(page.get_by_role("button", name="Connect", exact=True)).to_be_disabled()
    page.unroute("**/api/ports")
    page.get_by_role("button", name="Refresh ports", exact=True).click()
    passed("missing-port state gives an actionable empty state (mocked port list)")

    page.get_by_role("button", name="Start camera", exact=True).click()
    expect(page.locator("#camera-badge")).to_have_text("Preview live", timeout=8000)
    assert page.locator("#camera-video").evaluate("v => v.srcObject.getAudioTracks().length === 0")
    with page.expect_download() as snapshot_info:
        page.get_by_role("button", name="Save image", exact=True).click()
    assert Path(snapshot_info.value.path()).read_bytes().startswith(b"\x89PNG")
    passed("synthetic video preview and PNG capture work without microphone")
    page.get_by_role("button", name="Stop camera", exact=True).click()
    expect(page.locator("#camera-badge")).to_have_text("Off")
    assert page.locator("#camera-video").evaluate("video => video.srcObject === null")
    passed("Stop camera releases the preview")

    page.evaluate("() => { navigator.mediaDevices.getUserMedia = async () => { throw new DOMException('Denied for test', 'NotAllowedError'); }; }")
    page.get_by_role("button", name="Start camera", exact=True).click()
    expect(page.locator("#camera-error")).to_contain_text("Camera permission was blocked")
    expect(page.get_by_role("button", name="Start camera", exact=True)).to_be_enabled()
    passed("camera permission refusal provides a retry path (mocked denial)")

    page.reload()
    page.wait_for_load_state("networkidle")
    page.keyboard.press("Tab")
    expect(page.locator(".skip-link")).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator("#workspace")).to_be_focused()
    passed("keyboard skip link reaches main workspace")
    for width in [1440, 768, 375]:
        page.set_viewport_size({"width": width, "height": 900})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width
        assert page.evaluate("document.body.scrollWidth <= innerWidth"), width
        assert page.locator("#camera-start").is_visible()
    page.locator("h1").click()
    page.screenshot(path=str(OUT / "dashboard-mobile.png"), full_page=True)
    passed("desktop, tablet and mobile layouts have no horizontal overflow")
    assert not errors, errors
    passed("no uncaught browser JavaScript errors")
    context.close()
    browser.close()

report = OUT / "local-dashboard-2026-10-29.json"
data = json.loads(report.read_text()) if report.exists() else {}
data.update({"browser_checks": checks, "camera_test_source": "Chromium synthetic video only",
             "camera_hardware_tested": False, "browser": "Microsoft Edge headless", "browser_js_errors": errors})
report.write_text(json.dumps(data, indent=2), encoding="utf-8")
