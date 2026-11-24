"use strict";
const el = id => document.getElementById(id);
const set = (id, value) => { el(id).textContent = value ?? "—"; };
const image = el("camera-image");
let source = "";
let paused = false;
let pending = false;
let scheduled;
function showStream(path) {
  if (path === source) return;
  source = path;
  image.hidden = !path;
  el("camera-empty").hidden = Boolean(path);
  if (path) image.src = path + "?t=" + Date.now();
  else image.removeAttribute("src");
}
image.onerror = () => showStream("");
function render(s) {
  el("offline").hidden = Boolean(s);
  const c = s?.camera;
  const d = s?.detection;
  const live = Boolean(c?.streaming);
  el("snapshot").disabled = !live || paused;
  showStream(live ? (d?.enabled && d.fresh ? "/video/target" : "/video/camera") : "");
  set("camera-status", live ? "Live video" : "Waiting for video");
  el("camera-status").className = live ? "badge good" : "badge";
  set("video-detail", live ? c.width + " × " + c.height + " · " + c.fps + " fps at camera" : "");
  set("detection", !s ? "—" : !d?.enabled ? "Off" : !d.fresh ? "Waiting for video" :
    ({DETECTED: "Blue target detected", CHECKING: "Checking target", SEARCHING: "Searching"}[d.status] || "Waiting"));
  const t = s?.telemetry;
  set("robot-status", t ? "Connected" : "Waiting for robot");
  el("robot-status").className = t ? "badge good" : "badge warning";
  const raw = t?.water_raw;
  const level = s?.tank_percent;
  set("level", Number.isInteger(level) ? level + "%" : null);
  el("water-meter").hidden = !Number.isInteger(level);
  if (Number.isInteger(level)) el("water-meter").value = level;
  set("water", Number.isInteger(raw) ? raw + " / 4095" : null);
  set("pump", t?.driver_ready === 0 ? "Pump disabled" : t?.pump === 1 ? "Pump commanded on" : t?.pump === 0 ? "Pump off" : "Pump status unavailable");
  set("run", t ? (t.run ? (t.flags & 2 ? "Reversing" : "Running") : "Stopped") : null);
  set("cal", {READY:"Ready", NEEDED:"Needed", SAMPLING:"Sampling"}[t?.calibration]);
  set("uart", t?.uart_errors); set("drops", t?.rx_drops);
  set("updated", t && s.last_seen ? new Date(s.last_seen).toLocaleTimeString() : "No fresh reading");
  for (const id of ["pico", "wifi", "esp", "msp", "uno"]) set(id, s?.links?.[id]);
}
async function poll() {
  clearTimeout(scheduled);
  if (paused || pending) return;
  pending = true;
  el("refresh").disabled = true;
  try {
    const response = await fetch("/api/state", {cache:"no-store", signal:AbortSignal.timeout(5000)});
    const data = response.ok ? await response.json() : null;
    if (!paused) render(data);
  } catch { if (!paused) render(null); }
  finally {
    pending = false;
    el("refresh").disabled = paused;
    if (!paused) scheduled = setTimeout(poll, 1000);
  }
}
el("refresh").addEventListener("click", poll);
el("pause").addEventListener("click", () => {
  paused = !paused;
  el("pause").setAttribute("aria-pressed", String(paused));
  set("pause", paused ? "Resume my view" : "Pause my view");
  clearTimeout(scheduled);
  if (paused) {
    showStream("");
    set("camera-status", "Paused");
    set("camera-empty", "Your view is paused");
    set("robot-status", "Updates paused");
    el("snapshot").disabled = el("refresh").disabled = true;
  } else {
    set("camera-empty", "Waiting for camera");
    poll();
  }
});
el("snapshot").addEventListener("click", () => {
  if (!image.naturalWidth || !source || paused) {
    set("snapshot-message", "Wait for a live frame and try again.");
    return;
  }
  const canvas = document.createElement("canvas");
  canvas.width = image.naturalWidth;
  canvas.height = image.naturalHeight;
  canvas.getContext("2d").drawImage(image, 0, 0);
  canvas.toBlob(blob => {
    if (!blob) { set("snapshot-message", "Could not save this frame."); return; }
    const link = document.createElement("a");
    const url = URL.createObjectURL(blob);
    link.href = url; link.download = "robot-camera-" + Date.now() + ".jpg";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 3000);
    set("snapshot-message", "Image saved.");
  }, "image/jpeg", .95);
});
poll();
