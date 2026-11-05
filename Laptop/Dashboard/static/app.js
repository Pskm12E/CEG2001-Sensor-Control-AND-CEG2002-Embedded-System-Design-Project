"use strict";
const $ = (id) => document.getElementById(id);
let state = null, serverAvailable = false, paused = false, connectionBusy = false, portBusy = false;
let commandBusy = false, pollBusy = false, eventFingerprint = "";
let stream = null, cameraActive = false, cameraBusy = false, cameraToken = 0, cameraTimer = null;
let imageUrl = null, imageBlob = null;
let detectionBusy = false, relayDetection = null;
const timeFormat = new Intl.DateTimeFormat(undefined, {hour: "2-digit", minute: "2-digit", second: "2-digit"});
const text = (id, value) => { if ($(id).textContent !== String(value)) $(id).textContent = value; };
const message = (id, value) => { text(id, value || ""); $(id).hidden = !value; };
const formatTime = (value) => timeFormat.format(new Date(value));

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
  const hosted = state?.mode === "hosted", connected = Boolean(state?.connection?.connected && serverAvailable);
  $("connect").disabled = hosted || connected || connectionBusy || portBusy || !$("port-select").value || !serverAvailable;
  $("disconnect").disabled = !connected || connectionBusy;
  $("port-select").disabled = connected || connectionBusy || portBusy;
  $("refresh-ports").disabled = hosted || connectionBusy || portBusy;
  $("bench-controls").disabled = hosted || !connected || paused || commandBusy || connectionBusy;
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
  const hosted = state?.mode === "hosted", connection = state?.connection || {};
  const connected = connection.connected && serverAvailable, fresh = connected && connection.fresh && !paused;
  text("deployment-mode", hosted ? "Hosted preview" : "Local laptop");
  $("connect-form").hidden = hosted; $("bench-controls").hidden = hosted; $("command-message").hidden = hosted;
  text("connection-badge", !serverAvailable ? "Offline" : hosted ? "Not linked" : paused ? "Updates paused" : fresh ? "Connected" : connected ? "Waiting for robot" : "Disconnected");
  $("connection-badge").className = `badge${fresh ? " good" : connected ? " warning" : ""}`;
  text("reading-age", paused ? "Readings paused" : connection.last_seen ? `${fresh ? "Updated" : "Last reading"} ${formatTime(connection.last_seen)}` : "No reading yet");
  text("connection-message", hosted ? "Robot USB is available in the laptop dashboard." : connected ? `${connection.port} at 115200 baud. Pico relays status over private Wi-Fi.` : "Choose the desk Pico USB port. Close the Pico console before connecting.");
  message("connection-error", connection.error || "");
  const data = fresh ? state.telemetry : null, links = serverAvailable && !paused ? state?.links || {} : {};
  text("board-name", data?.board || "—");
  text("run-state", data ? (data.run ? "Running" : "Stopped") : "—");
  text("calibration", data ? ({NEEDED: "Needed", READY: "Ready", SAMPLING: "Sampling"}[data.calibration] || data.calibration) : "—");
  text("uart-errors", data?.uart_errors ?? "—"); text("rx-drops", data?.rx_drops ?? "—");
  for (const key of ["pico", "wifi", "esp", "msp", "uno"]) text(`${key}-link`, links[key] || "—");
  text("pico-summary", links.pico === "UP" ? "Connected" : "Not linked");
  const sensorName = (value) => value === "NC" ? "Not calibrated" : value;
  text("line-sensors", data ? `L: ${sensorName(data.left)} / R: ${sensorName(data.right)}` : "Not linked");
  renderEvents(); renderCameraState(); renderDetection(); controls();
}
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
    if (!ports.length) $("port-select").add(new Option(result.mode === "hosted" ? "Available on the laptop" : "No desk Pico found", ""));
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
  $("detection-panel").hidden = state?.mode === "hosted";
  $("detection-toggle").disabled = detectionBusy || cameraBusy || !serverAvailable ||
    (!running && (paused || !cameraActive || $("camera-source").value !== "xiao" || !state?.detection?.available));
  text("detection-toggle", detectionBusy ? "Updating…" : running ? "Stop detection" : "Start detection");
  $("detection-toggle").setAttribute("aria-pressed", String(running));
}

function renderDetection() {
  const detector = state?.detection;
  const live = serverAvailable && !paused && cameraActive && detector?.enabled && detector.fresh;
  const names = {SEARCHING: "Searching", CHECKING: "Checking target", DETECTED: "Blue target detected"};
  const status = !serverAvailable ? "Offline" : paused ? "Updates paused" : !detector?.enabled ? "Off" : live ? names[detector.status] || "Waiting for video" : "Waiting for video";
  text("detection-badge", status);
  $("detection-badge").className = `badge${live && detector.detected ? " good" : live && detector.status === "CHECKING" ? " warning" : ""}`;
  text("detection-position", live && detector.centre ? `Centre: ${detector.centre[0]}, ${detector.centre[1]} px · ${detector.fps} fps` : "");
  const prompt = !detector?.available ? "Detection is unavailable. Install the dashboard requirements and restart it." :
    $("camera-source").value !== "xiao" ? "Choose the XIAO camera for the blue-square test." :
    !detector?.enabled ? "Start the XIAO camera, then show the blue square. Detection only; no movement or spraying." :
    paused ? "Preview and readings are paused. No robot commands are sent." :
    live && detector.detected ? "Blue square confirmed across 3 frames. No robot commands are sent." :
    live && detector.status === "CHECKING" ? `Checking ${detector.streak} of ${detector.required_frames} frames. Hold the square face-on.` :
    live ? "Show the blue square face-on. Other similar blue shapes can also match." : "Waiting for fresh camera frames. Check camera power.";
  text("detection-message", prompt);
  message("detection-error", detector?.error || "");
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
  if (!cameraActive || $("camera-source").value!=="xiao") return;
  const camera=state?.camera;
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
  if (state?.mode === "hosted") {
    $("camera-source").value = "webcam"; $("camera-source").querySelector('[value="xiao"]').disabled = true;
    $("camera-empty").querySelector("p").textContent = "Choose a webcam, then start the preview.";
  }
  await Promise.all([refreshPorts(), cameraList()]); poll();
})();
