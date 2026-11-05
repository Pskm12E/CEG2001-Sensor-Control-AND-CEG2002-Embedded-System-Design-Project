"""Opt-in dashboard UI smoke checks; no board commands or physical camera access.

Run manually with Python + Playwright against an already-running local server.
Camera/serial transport is tested separately by verify_live.py.
"""
from datetime import datetime
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"tmp/website-test-python"))
from playwright.sync_api import sync_playwright, expect

checks=[]
out=ROOT/"Laptop/Artifacts/camera-private";out.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,channel="msedge")
    page=browser.new_page(viewport={"width":1440,"height":1000})
    errors=[];page.on("pageerror",lambda error:errors.append(str(error)))
    page.goto("http://127.0.0.1:8765")
    page.wait_for_load_state("networkidle")
    expect(page.get_by_role("heading",name="Robot workspace")).to_be_visible()
    expect(page.locator("#camera-badge")).to_have_text("Off")
    assert page.locator("[data-command]").evaluate_all("nodes => nodes.map(n => n.dataset.command)")==["PING","STATUS"]
    checks.append("Read-only controls and camera-off initial state")
    page.keyboard.press("Tab");expect(page.locator(".skip-link")).to_be_focused()
    page.keyboard.press("Enter");expect(page.locator("#workspace")).to_be_focused()
    checks.append("Keyboard skip link")
    page.get_by_role("button",name="Pause updates",exact=True).click()
    expect(page.locator("#run-state")).to_have_text("—")
    expect(page.locator("#bench-controls")).to_be_disabled()
    page.get_by_role("button",name="Resume updates",exact=True).click()
    checks.append("Pause blanks live readings and disables checks")
    for width in [1440,768,390,320]:
        page.set_viewport_size({"width":width,"height":900})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"),width
        expect(page.locator("#camera-start")).to_be_visible()
    checks.append("No horizontal overflow at desktop/tablet/390px/320px")
    page.screenshot(path=str(out/"dashboard-ui-smoke.png"),full_page=True)
    assert not errors,errors
    checks.append("No uncaught browser errors")
    browser.close()
report=ROOT/"Laptop/Artifacts/verification"/f"dashboard-ui-{datetime.now():%Y-%m-%d-%H%M%S}.json"
report.write_text(json.dumps({"checks":checks,"passed":True,"physical_camera_accessed":False,"robot_commands_sent":False},indent=2)+"\n",encoding="utf-8")
print(report)
