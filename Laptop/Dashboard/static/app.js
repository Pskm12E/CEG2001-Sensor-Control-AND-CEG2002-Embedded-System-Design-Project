"use strict";
const $ = (id) => document.getElementById(id);
let state = null, serverAvailable = false, paused = false, connectionBusy = false, portBusy = false;
let commandBusy = false, pollBusy = false, eventFingerprint = "";
let stream = null, cameraActive = false, cameraBusy = false, cameraToken = 0, cameraTimer = null;
let imageUrl = null, imageBlob = null;
let detectionBusy = false, relayDetection = null;
let dockBusy = false, tankBusy = false;
const timeFormat = new Intl.DateTimeFormat(undefined, {hour: "2-digit", minute: "2-digit", second: "2-digit"});
const text = (id, value) => { if ($(id).textContent !== String(value)) $(id).textContent = value; };
const message = (id, value) => { text(id, value || ""); $(id).hidden = !value; };
const formatTime = (value) => timeFormat.format(new Date(value));
const maxWaterReading = 4095;
// Median P6.0 readings from this probe's dry and wet bench samples.
const probeReference = {dry: 15, wet: 1208};
const waterKey = "plant-robot.water-calibration.v1";
const waterButtons = document.querySelectorAll("[data-water-point]");
const validWaterReading = (value) => Number.isInteger(value) && value >= 0 && value <= maxWaterReading;
let waterCalibration = {};
try {
  const saved = JSON.parse(localStorage.getItem(waterKey));
  if (validWaterReading(saved?.empty)) waterCalibration.empty = saved.empty;
  if (validWaterReading(saved?.full)) waterCalibration.full = saved.full;
} catch { /* The readings remain available if storage is blocked or unavailable. */ }

function liveTelemetry() {
  return serverAvailable && !paused && state?.connection?.connected && state.connection.fresh ? state.telemetry : null;
}

function renderWater(data) {
  const raw = data?.water_raw;
  const available = validWaterReading(raw);
  const {empty, full} = waterCalibration;
  const calibrated = validWaterReading(empty) && validWaterReading(full) && full > empty;
  const low = calibrated ? empty : probeReference.dry;
  const high = calibrated ? full : probeReference.wet;
  const level = available ? Math.round(100 * Math.max(0, Math.min(1, (raw - low) / (high - low)))) : null;
  text("water-level-label", calibrated ? "Estimated tank level" : "Probe wetness");
  text("water-raw", available ? `${raw} / ${maxWaterReading}` : "—");
  text("water-level", level !== null ? `${level}%` : "—");
  $("water-meter").hidden = level === null;
  if (level !== null) $("water-meter").value = level;
  const desired = calibrated ? empty + Math.floor(3 * (full - empty) / 5) + 1 : 4096;
  const actual = data?.refill_min_raw;
  let refillInfo = "";
  if (Number.isInteger(actual)) {
    refillInfo = actual === 4096 ? "Automatic refill restart is disabled." :
      `Refill restart above 60% · car threshold ${actual} / 4095 · 3-second wait.`;
    if (actual !== desired) refillInfo += " Saved calibration is waiting to sync to the car.";
  } else if (data && calibrated) {
    refillInfo = `Refill restart needs the updated car firmware. Saved 60% setting starts at ${desired} / 4095.`;
  }
  message("water-departure", refillInfo);
  text("water-points", `Empty ${empty ?? "—"} · Full ${full ?? "—"}`);
  for (const button of waterButtons) button.disabled = tankBusy || !available || data.run !== 0 || data.pump !== 0;
  $("water-reset").disabled = tankBusy || (empty === undefined && full === undefined);

  let pumpStatus = "Pump status unavailable", tone = "";
  if (data?.driver_ready === 0) { pumpStatus = "Pump disabled"; tone = " warning"; }
  else if (data?.pump === 1) { pumpStatus = "Pump commanded on"; tone = " good"; }
  else if (data?.pump === 0) pumpStatus = "Pump off";
  text("pump-status", pumpStatus);
  $("pump-status").className = `badge${tone}`;
}

async function saveWaterCalibration(calibration, feedback) {
  tankBusy = true; renderWater(liveTelemetry());
  try {
    await api("/api/tank/calibration", calibration);
    waterCalibration = calibration;
    try { localStorage.removeItem(waterKey); } catch { /* Storage can be disabled. */ }
    text("water-calibration-message", feedback);
  } catch (error) { text("water-calibration-message", error.message); }
  finally { tankBusy = false; renderWater(liveTelemetry()); }
}

for (const button of waterButtons) button.addEventListener("click", () => {
  const data = liveTelemetry();
  if (!validWaterReading(data?.water_raw) || data.run !== 0 || data.pump !== 0) return;
  const point = button.dataset.waterPoint;
  const next = {...waterCalibration, [point]: data.water_raw};
  if (next.full <= next.empty) {
    text("water-calibration-message", "Full must read higher than empty. Check the probe and try again.");
    return;
  }
  saveWaterCalibration(next, point === "empty" ? "Empty reading saved." : "Full reading saved.");
});
$("water-reset").addEventListener("click", () => saveWaterCalibration({}, "Calibration cleared."));

async function api(path, body) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 12000);
  try {
    const options = {signal: controller.signal, cache: "no-store", credentials: "same-origin"};
    if (body !== undefined) Object.assign(options, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
    const response = await fetch(path, options);
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Request failed. Try again.");
    return result;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("The local server did not reply. Check its terminal and try again.");
    if (error instanceof TypeError) throw new Error("Cannot reach the local server. Start Dashboard, then refresh this page.");
    throw error;
  } finally { clearTimeout(timer); }
}

function controls() {
  const connected = Boolean(state?.connection?.connected && serverAvailable);
  $("connect").disabled = connected || connectionBusy || portBusy || !$("port-select").value || !serverAvailable;
  $("disconnect").disabled = !connected || connectionBusy;
  $("port-select").disabled = connected || connectionBusy || portBusy;
  $("refresh-ports").disabled = connectionBusy || portBusy;
  $("bench-controls").disabled = !connected || paused || commandBusy || connectionBusy;
  $("export-events").disabled = !state?.events?.length;
}
function renderEvents() {
  const events = (state?.events || []).slice(-50).reverse();
  const fingerprint = JSON.stringify(events);
  if (fingerprint === eventFingerprint) return;
  eventFingerprint = fingerprint;
  $("events-empty").hidden = events.length > 0;
  const fragment = document.createDocumentFragment();
  for (const event of events) {
    const item = document.createElement("li"), time = document.createElement("time"), content = document.createElement("div");
    time.textContent = formatTime(event.time); time.dateTime = event.time;
    const detail = document.createElement("span"), kind = document.createElement("span");
    detail.className = "event-message"; detail.textContent = event.message;
    kind.className = "event-kind"; kind.textContent = event.kind;
    content.append(detail, kind); item.append(time, content); fragment.append(item);
  }
  $("events").replaceChildren(fragment);
}
function render() {
  const connection = state?.connection || {};
  const connected = connection.connected && serverAvailable, fresh = connected && connection.fresh && !paused;
  text("connection-badge", !serverAvailable ? "Offline" : paused ? "Updates paused" : fresh ? "Connected" : connected ? "Waiting for robot" : "Disconnected");
  $("connection-badge").className = `badge${fresh ? " good" : connected ? " warning" : ""}`;
  text("reading-age", paused ? "Readings paused" : connection.last_seen ? `${fresh ? "Updated" : "Last reading"} ${formatTime(connection.last_seen)}` : "No reading yet");
  text("connection-message", connected ? `${connection.port} at 115200 baud. Pico relays status over private Wi-Fi.` : "Choose the desk Pico USB port. Close the Pico console before connecting.");
  message("connection-error", connection.error || "");
  const data = liveTelemetry(), links = serverAvailable && !paused ? state?.links || {} : {};
  text("board-name", data?.board || "—");
  const reversing = data?.base === "ZUMO" && Boolean(data.flags & 2);
  text("run-state", data ? (data.run ? (reversing ? "Reversing" : "Running") : "Stopped") : "—");
  text("calibration", data ? ({NEEDED: "Needed", READY: "Ready", SAMPLING: "Sampling"}[data.calibration] || data.calibration) : "—");
  text("uart-errors", data?.uart_errors ?? "—"); text("rx-drops", data?.rx_drops ?? "—");
  for (const key of ["pico", "wifi", "esp", "msp", "uno"]) text(`${key}-link`, links[key] || "—");
  text("pico-summary", links.pico === "UP" ? "Connected" : "Not linked");
  const sensorName = (value) => value === "NC" ? "Not calibrated" : value;
  text("line-sensor-pins", data && data.base !== "ZUMO" ? "D4 left / D2 right" : "Zumo array");
  text("line-sensors", data ? (data.base === "ZUMO" ? "Black line on white" : `L: ${sensorName(data.left)} / R: ${sensorName(data.right)}`) : "Not linked");
  if (state?.tank_calibration && !tankBusy) waterCalibration = state.tank_calibration;
  renderWater(data); renderDock(); renderEvents(); renderCameraState(); renderDetection(); controls();
}

function renderDock() {
  const dock = serverAvailable && !paused ? state?.dock : null;
  const label = !dock ? "Unavailable" : !dock.sensor_fresh ? "Waiting for station" :
    dock.docked === null ? "Checking magnet" : dock.docked ? "Docked" : "Undocked";
  text("dock-status", label);
  $("dock-status").className = dock?.docked === true ? "badge good" : "badge";
  text("dock-pump", dock?.pump === true ? "On" : dock?.pump === false ? "Off" : "—");
  const phases = {BOOT:"Waiting for first undock", CLEAR:"Ready for arrival", ARRIVAL:"Waiting for stop",
    SETTLE:"Settling", FILL:"Refilling", DONE:"Refill ended", FAULT:"Interrupted"};
  const wait = dock?.departure_wait_s;
  text("dock-phase", Number.isInteger(wait)
    ? (wait > 0 ? `Departure check in ${wait} s` : "Waiting for departure")
    : phases[dock?.phase] || "—");
  $("dock-find").hidden = Boolean(dock && dock.phase !== "DISCONNECTED");
  $("dock-find").disabled = dockBusy || !serverAvailable || paused || state?.links?.pico !== "UP";
  let hint = "";
  if (dock?.phase === "DISCONNECTED") hint = "Connect the station MSP430 to laptop USB.";
  else if (dock?.phase === "SEARCHING") hint = "Checking station USB…";
  else if (dock && phases[dock.phase] && !dock.sensor_fresh) hint = "Waiting for a Hall reading. Check the station firmware.";
  else if (dock?.sensor_fresh && liveTelemetry() && !Number.isInteger(liveTelemetry().dock_visit))
    hint = "The car needs the docking supervisor firmware for automatic refill and departure.";
  else if (dock?.sensor_fresh && (!Number.isInteger(waterCalibration.empty) || !Number.isInteger(waterCalibration.full)))
    hint = "Record empty and full tank readings to enable automatic departure.";
  else if (dock?.sensor_fresh) {
    const firstAbove = waterCalibration.empty + Math.floor(3 * (waterCalibration.full - waterCalibration.empty) / 5) + 1;
    hint = `Above 60% (sensor reading ${firstAbove} or higher), the Zumo waits 3 seconds with the refill pump off before leaving.`;
  }
  message("dock-message", hint);
}
$("dock-find").addEventListener("click", async () => {
  dockBusy = true; renderDock();
  try { await api("/api/dock/connect", {port:"AUTO"}); await refreshState(); }
  catch (error) { message("dock-message", error.message); }
  finally { dockBusy = false; $("dock-find").disabled = state?.links?.pico !== "UP"; }
});
async function refreshState() {
  if (paused || pollBusy) return;
  pollBusy = true;
  try { state = await api("/api/state"); serverAvailable = true; message("server-message", ""); }
  catch (error) { serverAvailable = false; message("server-message", error.message); }
  finally { pollBusy = false; render(); }
}
async function poll() {
  if (!document.hidden) await refreshState();
  setTimeout(poll, 1000);
}
async function refreshPorts() {
  portBusy = true; controls();
  const previous = $("port-select").value;
  try {
    const result = await api("/api/ports"), ports = result.ports || [];
    $("port-select").replaceChildren();
    if (!ports.length) $("port-select").add(new Option("No desk Pico found", ""));
    for (const port of ports) $("port-select").add(new Option(`${port.device} — ${port.description}`, port.device));
    if (ports.some(p => p.device === previous)) $("port-select").value = previous;
  } catch (error) { message("connection-error", error.message); }
  finally { portBusy = false; controls(); }
}
$("connect-form").addEventListener("submit", async (event) => {
  event.preventDefault(); if (connectionBusy || $("connect").disabled) return;
  connectionBusy = true; controls(); text("connect", "Connecting…");
  try { await api("/api/connect", {port: $("port-select").value}); await refreshState(); }
  catch (error) { message("connection-error", error.message); }
  finally { connectionBusy = false; text("connect", "Connect"); controls(); }
});
$("disconnect").addEventListener("click", async () => {
  connectionBusy = true; controls();
  try { await api("/api/disconnect", {}); state = await api("/api/state"); render(); }
  catch (error) { message("connection-error", error.message); }
  finally { connectionBusy = false; controls(); }
});
$("refresh-ports").addEventListener("click", () => { refreshPorts(); cameraList(); });
$("port-select").addEventListener("change", controls);
$("pause-updates").addEventListener("click", async () => {
  paused = !paused; text("pause-updates", paused ? "Resume updates" : "Pause updates");
  $("pause-updates").setAttribute("aria-pressed", String(paused));
  if (!paused) await refreshState();
  if (cameraActive && $("camera-source").value === "xiao") attachLiveRelay();
  if (stream) { if (paused) $("camera-video").pause(); else $("camera-video").play().catch(() => {}); }
  render();
});
for (const button of document.querySelectorAll("[data-command]")) button.addEventListener("click", async () => {
  if (commandBusy || $("bench-controls").disabled) return;
  commandBusy = true; controls(); text("command-message", "Requesting status…");
  try { await api("/api/command", {command: button.dataset.command}); text("command-message", "Check queued. Replies appear in Activity."); }
  catch (error) { text("command-message", error.message); }
  finally { commandBusy = false; controls(); }
});
function download(blob, name) {
  const url = URL.createObjectURL(blob), link = document.createElement("a");
  link.href = url; link.download = name; document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
$("export-events").addEventListener("click", () => download(new Blob([JSON.stringify({exported_at: new Date().toISOString(), events: state?.events || []}, null, 2)], {type: "application/json"}), `robot-log-${Date.now()}.json`));

function cameraControls() {
  $("camera-start").disabled = cameraBusy || cameraActive || ($("camera-source").value === "xiao" && !$("camera-select").value);
  $("camera-stop").disabled = !cameraBusy && !cameraActive && !state?.camera?.connected;
  $("camera-select").disabled = cameraBusy || cameraActive;
  $("camera-source").disabled = cameraBusy || cameraActive;
  $("snapshot").disabled = cameraBusy || (!cameraActive && !stream);
  text("camera-start", cameraBusy ? "Starting…" : "Start camera");
  detectionControls();
}

function detectionControls() {
  const running = Boolean(state?.detection?.enabled);
  $("detection-toggle").disabled = detectionBusy || cameraBusy || !serverAvailable ||
    (!running && (paused || !cameraActive || $("camera-source").value !== "xiao" || !state?.detection?.available));
  text("detection-toggle", detectionBusy ? "Updating…" : running ? "Stop detection" : "Start detection");
  $("detection-toggle").setAttribute("aria-pressed", String(running));
}

function renderDetection() {
  const detector = state?.detection;
  const action = state?.target_action;
  const robot = liveTelemetry();
  const pumpDisabled = robot?.driver_ready === 0;
  text("target-mode", pumpDisabled ? "Pump disabled: target detection stops the robot. Spraying and automatic continuation are disabled." :
    robot?.driver_ready === 1 ? "Target cycle: stop, spray for 3 seconds, then continue." : "Waiting for pump status.");
  const live = serverAvailable && !paused && cameraActive && detector?.enabled && detector.fresh;
  const names = {SEARCHING: "Searching", CHECKING: "Checking target", DETECTED: "Blue target detected"};
  const status = !serverAvailable ? "Offline" : paused ? "Updates paused" : !detector?.enabled ? "Off" : live ? names[detector.status] || "Waiting for video" : "Waiting for video";
  text("detection-badge", status);
  $("detection-badge").className = `badge${live && detector.detected ? " good" : live && detector.status === "CHECKING" ? " warning" : ""}`;
  text("detection-position", live && detector.centre ? `Centre: ${detector.centre[0]}, ${detector.centre[1]} px · ${detector.fps} fps` : "");
  const prompt = !detector?.available ? "Detection is unavailable. Install the dashboard requirements and restart it." :
    $("camera-source").value !== "xiao" ? "Choose the XIAO camera for the blue-square test." :
    !detector?.enabled ? "Start detection to test the blue target." :
    robot && !robot.run && (action?.state === "DRIVER_DISABLED" || robot.job === 8) ? "Target stop complete. Pump disabled; robot remains stopped." :
    robot && action?.state === "SPRAYING" ? "Robot stopped. Pump commanded on." :
    action?.state === "SETTLING" || action?.state === "STOPPING" ? "Target confirmed. Stopping before spraying." :
    action?.state === "RESUMING" ? "Spray finished. Resuming line following." :
    action?.state === "COMPLETE" ? (state?.connection?.fresh && state?.telemetry?.run ? "Spray cycle finished. Following the line." : "Spray cycle finished.") :
    action?.state === "WAIT_DRIVING" ? "Target visible. Start line following with the Zumo button." :
    paused ? "Preview paused; detection continues on the laptop." :
    live && detector.detected ? "Blue target confirmed. Requesting the MSP cycle." :
    live && detector.status === "CHECKING" ? `Checking ${detector.streak} of ${detector.required_frames} frames. Hold the square face-on.` :
    live ? "Show the blue square face-on. Other similar blue shapes can also match." : "Waiting for fresh camera frames. Check camera power.";
  text("detection-message", prompt);
  message("detection-error", action?.error || detector?.error || "");
  if (live) text("observe-status", detector.detected ? "Blue test target detected" : "Blue-target test running");
  if (cameraActive && $("camera-source").value === "xiao" && relayDetection !== Boolean(detector?.enabled)) attachLiveRelay();
  detectionControls();
}

$("detection-toggle").addEventListener("click", async () => {
  if (detectionBusy || $("detection-toggle").disabled) return;
  detectionBusy = true; detectionControls(); message("detection-error", "");
  try {
    await api(state?.detection?.enabled ? "/api/detection/stop" : "/api/detection/start", {});
    await refreshState();
  } catch (error) { message("detection-error", error.message); }
  finally { detectionBusy = false; detectionControls(); }
});
async function cameraList() {
  if (cameraBusy || cameraActive) return;
  const previous = $("camera-select").value;
  try {
    $("camera-select").replaceChildren();
    if ($("camera-source").value === "xiao") {
      const {ports} = await api("/api/camera/ports");
      if (!ports.length) $("camera-select").add(new Option("Connect the desk Pico for wireless video", ""));
      for (const port of ports) $("camera-select").add(new Option(port.description || "XIAO over Pico Wi-Fi", port.device));
      if (ports.some(p => p.device === previous)) $("camera-select").value = previous;
    } else {
      const devices = navigator.mediaDevices?.enumerateDevices ? (await navigator.mediaDevices.enumerateDevices()).filter(d => d.kind === "videoinput") : [];
      $("camera-select").add(new Option("Default webcam", ""));
      devices.forEach((d, i) => $("camera-select").add(new Option(d.label || `Webcam ${i + 1}`, d.deviceId)));
      if (devices.some(d => d.deviceId === previous)) $("camera-select").value = previous;
    }
  } catch (error) { message("camera-error", error.message); }
  cameraControls();
}
function clearCameraView() {
  if (stream) stream.getTracks().forEach(track => track.stop());
  stream = null; $("camera-video").srcObject = null; $("camera-video").hidden = true;
  $("camera-image").hidden = true; $("camera-image").removeAttribute("src");
  if (imageUrl) URL.revokeObjectURL(imageUrl);
  imageUrl = null; imageBlob = null;
  relayDetection = null;
  $("camera-empty").hidden = false;
}
async function stopCamera() {
  ++cameraToken; clearTimeout(cameraTimer); cameraActive = false; cameraBusy = true; cameraControls();
  clearCameraView();
  try { if ($("camera-source").value === "xiao") await api("/api/camera/disconnect", {}); }
  catch (error) { message("camera-error", error.message); }
  finally {
    cameraBusy = false; if (state?.camera) state.camera.connected = false;
    if (state?.detection) state.detection.enabled = false;
    text("camera-badge", "Off"); $("camera-badge").className = "badge";
    text("observe-status", "Preview available"); text("camera-message", "Camera stopped. Images stay on this laptop."); cameraControls();
  }
}
function attachLiveRelay() {
  const image=$("camera-image");
  if (!cameraActive || paused || document.hidden) { image.removeAttribute("src"); return; }
  relayDetection = Boolean(state?.detection?.enabled);
  image.src=`${relayDetection ? "/api/detection/stream" : "/api/camera/stream"}?session=${Date.now()}`;
  image.hidden=false; $("camera-empty").hidden=true;
}
function renderCameraState() {
  if ($("camera-source").value!=="xiao") return;
  const camera=state?.camera;
  // The CMD launcher may start the stream before this browser opens.
  if (!cameraActive && !cameraBusy && serverAvailable && camera?.connected && !camera.error) {
    clearCameraView(); cameraActive=true; message("camera-error", "");
    if (![...$("camera-select").options].some(option => option.value === "PICO_WIFI")) {
      $("camera-select").replaceChildren(new Option("XIAO over private Wi-Fi via desk Pico", "PICO_WIFI"));
    }
    $("camera-select").value="PICO_WIFI";
    attachLiveRelay(); cameraControls();
  }
  if (!cameraActive) return;
  if (!camera?.connected || camera.error) {
    cameraActive=false;$("camera-image").removeAttribute("src");$("camera-image").hidden=true;
    $("camera-empty").hidden=false;text("camera-badge","Stream stopped");
    $("camera-badge").className="badge warning";
    message("camera-error",camera?.error || "Camera disconnected. Check camera power and start it again.");
    cameraControls();return;
  }
  text("camera-badge",paused?"Updates paused":camera.streaming?"Live video":"Connecting…");
  $("camera-badge").className=`badge${camera.streaming && !paused?" good":""}`;
  text("camera-message",`${camera.sensor} live Wi-Fi video via Pico, 320 × 240, ${camera.fps || 0} fps.`);
  text("observe-status",paused?"Preview paused":"Live video; detection pending");
}
async function startCamera() {
  if (cameraBusy || cameraActive) return;
  clearCameraView(); const token = ++cameraToken; cameraBusy = true; cameraControls(); message("camera-error", "");
  try {
    if ($("camera-source").value === "xiao") {
      const latest = await api("/api/state");
      if (latest.camera.connected && latest.camera.port !== $("camera-select").value) throw new Error("Stop the current camera before switching.");
      if (!latest.camera.connected) await api("/api/camera/connect", {port: $("camera-select").value});
      if (token !== cameraToken) { await api("/api/camera/disconnect", {}); return; }
      cameraActive = true; cameraBusy = false;
      state=await api("/api/state"); attachLiveRelay(); renderCameraState(); renderDetection();
    } else {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error("Webcam access is unavailable. Use Chrome or Edge on this laptop.");
      text("camera-message", "Allow webcam access in your browser, or select Stop camera.");
      const deviceId = $("camera-select").value;
      const next = await navigator.mediaDevices.getUserMedia({audio: false, video: {...(deviceId ? {deviceId: {exact: deviceId}} : {}), width: {ideal: 1280}, height: {ideal: 720}}});
      if (token !== cameraToken) { next.getTracks().forEach(track => track.stop()); return; }
      stream = next; $("camera-video").srcObject = next; await $("camera-video").play();
      $("camera-video").hidden = false; $("camera-empty").hidden = true; cameraActive = true;
      next.getVideoTracks()[0].addEventListener("ended", () => { if (token === cameraToken) stopCamera(); });
      text("camera-badge", "Webcam live"); $("camera-badge").className = "badge good";
      text("camera-message", "Webcam preview stays in this browser. Pest detection pending."); text("observe-status", "Preview on; detection pending");
    }
  } catch (error) {
    if (token !== cameraToken) return;
    cameraActive = false;
    const errors = {NotAllowedError: "Webcam permission was blocked. Allow camera access in site settings and retry.", NotFoundError: "No webcam found. Connect it to laptop USB and retry.", NotReadableError: "Webcam is busy. Close other camera apps and retry."};
    message("camera-error", errors[error.name] || error.message);
  } finally { if (token === cameraToken) { cameraBusy = false; cameraControls(); } }
}
$("camera-start").addEventListener("click", startCamera);
$("camera-stop").addEventListener("click", stopCamera);
$("camera-source").addEventListener("change", () => { clearCameraView(); cameraList(); });
$("camera-select").addEventListener("change", cameraControls);
$("snapshot").addEventListener("click", async () => {
  if (cameraActive && $("camera-source").value === "xiao") {
    try {
      const response=await fetch("/api/camera/frame",{cache:"no-store",signal:AbortSignal.timeout(3000)});
      if(!response.ok) throw new Error("No current video frame. Check the camera and retry.");
      download(await response.blob(),`xiao-frame-${Date.now()}.jpg`);
    } catch(error) { message("camera-error",error.message); }
    return;
  }
  const video = $("camera-video"); if (!stream || !video.videoWidth) return;
  const canvas = document.createElement("canvas"); canvas.width = video.videoWidth; canvas.height = video.videoHeight;
  canvas.getContext("2d").drawImage(video, 0, 0); canvas.toBlob(blob => { if (blob) download(blob, `webcam-${Date.now()}.png`); }, "image/png");
});
navigator.mediaDevices?.addEventListener?.("devicechange", cameraList);
window.addEventListener("pagehide", () => { ++cameraToken; cameraActive=false; $("camera-image").removeAttribute("src"); if (stream) stream.getTracks().forEach(track => track.stop()); });
document.addEventListener("visibilitychange", () => {
  if(cameraActive && $("camera-source").value === "xiao") attachLiveRelay();
  if (!document.hidden) refreshState();
});
(async () => {
  await refreshState();
  if (state?.mode === "local" && state.tank_calibration === null && Object.keys(waterCalibration).length)
    await saveWaterCalibration(waterCalibration, "Existing tank calibration saved on this laptop.");
  await Promise.all([refreshPorts(), cameraList()]); poll();
})();
