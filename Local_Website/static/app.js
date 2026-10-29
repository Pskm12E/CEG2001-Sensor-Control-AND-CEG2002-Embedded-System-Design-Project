"use strict";

const $ = (id) => document.getElementById(id);
const ui = Object.fromEntries([
  "pause-updates", "server-message", "camera-video", "camera-empty", "camera-empty-title", "camera-badge",
  "camera-select", "camera-start", "camera-stop", "snapshot", "camera-message", "camera-error",
  "connect-form", "port-select", "connect", "refresh-ports", "disconnect", "connection-badge",
  "connection-message", "connection-error", "reading-age", "led2", "s2-presses", "uart-errors", "rx-drops",
  "board-name", "uart-state", "bench-controls", "command-message", "observe-status", "events-empty", "events", "export-events"
].map((id) => [id, $(id)]));

let state = null;
let serverAvailable = false;
let paused = false;
let connectionBusy = false;
let commandBusy = false;
let portBusy = false;
let stream = null;
let cameraBusy = false;
let cameraRequest = 0;
let pollInFlight = false;
let eventFingerprint = "";
const timeFormat = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" });

function text(id, value) { if (ui[id].textContent !== String(value)) ui[id].textContent = value; }
function message(id, value) { text(id, value || ""); ui[id].hidden = !value; }
function formattedTime(value) { const date = new Date(value); return Number.isNaN(date.valueOf()) ? "—" : timeFormat.format(date); }

async function api(path, body) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 6000);
  try {
    const options = { signal: controller.signal, cache: "no-store", credentials: "same-origin" };
    if (body !== undefined) Object.assign(options, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const response = await fetch(path, options);
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `Request failed (${response.status}). Try again.`);
    return result;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("The local server did not respond. Check that the website launcher is running, then try again.");
    if (error instanceof TypeError) throw new Error("Cannot reach the local server. Start the website launcher, then refresh this page.");
    throw error;
  } finally { window.clearTimeout(timeout); }
}

function updateControls() {
  const connected = Boolean(state?.connection?.connected && serverAvailable);
  const fresh = Boolean(state?.connection?.fresh);
  ui.connect.disabled = connected || connectionBusy || portBusy || !ui["port-select"].value || !serverAvailable;
  ui.disconnect.disabled = !connected || connectionBusy;
  ui["port-select"].disabled = connected || connectionBusy || portBusy;
  ui["refresh-ports"].disabled = portBusy || connectionBusy;
  ui["bench-controls"].disabled = !connected || !fresh || paused || commandBusy || connectionBusy;
  ui["export-events"].disabled = !(state?.events?.length);
}

function renderState() {
  const connection = state?.connection || {};
  const connected = Boolean(connection.connected && serverAvailable);
  const fresh = connected && connection.fresh && !paused;
  text("connection-badge", !serverAvailable ? "Offline" : paused ? "Updates paused" : fresh ? "Connected" : connected ? "Waiting for reply" : "Disconnected");
  ui["connection-badge"].className = `badge${fresh ? " good" : connected ? " warning" : ""}`;
  const lastSeen = connection.last_seen ? formattedTime(connection.last_seen) : null;
  text("reading-age", paused ? "Paused; readings may be old" : fresh && lastSeen ? `Updated ${lastSeen}` : lastSeen ? `Last reading ${lastSeen}` : "No reading yet");
  text("connection-message", connected ? `${connection.port} at 9600 baud. Close this connection before using another serial terminal.` : "Choose the MSP430 Application UART port, usually COM13. Close any terminal using it first.");
  if (connection.error) message("connection-error", connection.error);
  else if (fresh) message("connection-error", "");
  const telemetry = fresh ? state.telemetry : null;
  const fields = { "led2": "led2", "s2-presses": "s2_presses", "uart-errors": "uart_errors", "rx-drops": "rx_drops", "board-name": "board", "uart-state": "uart0" };
  for (const [element, key] of Object.entries(fields)) text(element, telemetry?.[key] ?? "—");
  renderEvents();
  updateControls();
}

function renderEvents() {
  const events = state?.events || [];
  ui["events-empty"].hidden = events.length > 0;
  const visible = events.slice(-50).reverse();
  const fingerprint = JSON.stringify(visible);
  if (fingerprint === eventFingerprint) return;
  eventFingerprint = fingerprint;
  const fragment = document.createDocumentFragment();
  for (const event of visible) {
    const item = document.createElement("li");
    const timestamp = document.createElement("time");
    timestamp.textContent = formattedTime(event.time);
    if (event.time) timestamp.dateTime = event.time;
    const content = document.createElement("div");
    const detail = document.createElement("span");
    detail.className = "event-message";
    detail.textContent = event.message;
    const kind = document.createElement("span");
    kind.className = "event-kind";
    kind.textContent = event.kind;
    content.append(detail, kind);
    item.append(timestamp, content);
    fragment.append(item);
  }
  ui.events.replaceChildren(fragment);
}

async function refreshState() {
  if (paused || pollInFlight) return;
  pollInFlight = true;
  try {
    state = await api("/api/state");
    serverAvailable = true;
    message("server-message", "");
  } catch (error) {
    serverAvailable = false;
    message("server-message", error.message);
  } finally { pollInFlight = false; renderState(); }
}

async function poll() {
  if (!document.hidden) await refreshState();
  window.setTimeout(poll, 1000);
}

async function refreshPorts() {
  portBusy = true;
  updateControls();
  const previous = ui["port-select"].value;
  try {
    const result = await api("/api/ports");
    ui["port-select"].replaceChildren();
    const ports = Array.isArray(result.ports) ? result.ports : [];
    if (!ports.length) ui["port-select"].add(new Option("No MSP430 Application UART found", ""));
    for (const port of ports) ui["port-select"].add(new Option(`${port.device} — ${port.description}`, port.device));
    const chosen = ports.find((port) => port.device === previous) || ports.find((port) => port.suggested) || ports[0];
    if (chosen) ui["port-select"].value = chosen.device;
    message("connection-error", "");
  } catch (error) { message("connection-error", error.message); }
  finally { portBusy = false; updateControls(); }
}

ui["connect-form"].addEventListener("submit", async (event) => {
  event.preventDefault();
  if (connectionBusy || ui.connect.disabled) return;
  connectionBusy = true;
  text("connect", "Connecting…");
  message("connection-error", "");
  updateControls();
  try {
    await api("/api/connect", { port: ui["port-select"].value });
    if (paused) { state = await api("/api/state"); renderState(); } else await refreshState();
  }
  catch (error) { message("connection-error", error.message); }
  finally { connectionBusy = false; text("connect", "Connect"); updateControls(); }
});
ui.disconnect.addEventListener("click", async () => {
  connectionBusy = true; updateControls();
  try { await api("/api/disconnect", {}); message("connection-error", ""); if (paused) { state = await api("/api/state"); renderState(); } else await refreshState(); }
  catch (error) { message("connection-error", error.message); }
  finally { connectionBusy = false; updateControls(); }
});
ui["port-select"].addEventListener("change", updateControls);
ui["refresh-ports"].addEventListener("click", refreshPorts);
ui["pause-updates"].addEventListener("click", async () => {
  paused = !paused;
  text("pause-updates", paused ? "Resume updates" : "Pause updates");
  ui["pause-updates"].setAttribute("aria-pressed", String(paused));
  if (!paused) await refreshState();
  renderState();
});
for (const button of document.querySelectorAll("[data-command]")) button.addEventListener("click", async () => {
  if (commandBusy || ui["bench-controls"].disabled) return;
  commandBusy = true; updateControls();
  text("command-message", "Sending bench check…");
  try {
    await api("/api/command", { command: button.dataset.command });
    text("command-message", "Command sent. The board’s reply appears in Activity.");
    await refreshState();
  } catch (error) { text("command-message", error.message); }
  finally { commandBusy = false; updateControls(); }
});

function downloadBlob(blob, name) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url; link.download = name;
  document.body.append(link); link.click(); link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
ui["export-events"].addEventListener("click", () => {
  downloadBlob(new Blob([JSON.stringify({ exported_at: new Date().toISOString(), events: state?.events || [] }, null, 2)], { type: "application/json" }), `robot-log-${Date.now()}.json`);
});

function cameraControls() {
  ui["camera-start"].disabled = cameraBusy || Boolean(stream);
  ui["camera-stop"].disabled = !cameraBusy && !stream;
  ui["camera-select"].disabled = cameraBusy;
  ui.snapshot.disabled = !stream || cameraBusy || !ui["camera-video"].videoWidth;
  text("camera-start", cameraBusy ? "Starting…" : "Start camera");
}

function stopCamera(note = "Camera stopped. Preview and images stay on this laptop.") {
  cameraRequest += 1;
  if (stream) { for (const track of stream.getTracks()) track.stop(); stream = null; }
  ui["camera-video"].srcObject = null;
  ui["camera-video"].hidden = true;
  ui["camera-empty"].hidden = false;
  cameraBusy = false;
  text("camera-badge", "Off"); ui["camera-badge"].className = "badge";
  text("camera-empty-title", "Camera is off");
  text("observe-status", "Preview available");
  text("camera-message", note);
  cameraControls();
}

async function cameraList() {
  if (!navigator.mediaDevices?.enumerateDevices) return;
  const selected = ui["camera-select"].value;
  try {
    const devices = (await navigator.mediaDevices.enumerateDevices()).filter((device) => device.kind === "videoinput");
    ui["camera-select"].replaceChildren(new Option("Default camera", ""));
    devices.forEach((device, index) => ui["camera-select"].add(new Option(device.label || `Camera ${index + 1}`, device.deviceId)));
    const active = stream?.getVideoTracks()[0]?.getSettings().deviceId || selected;
    if (devices.some((device) => device.deviceId === active)) ui["camera-select"].value = active;
  } catch { /* The browser may hide camera names until permission is granted. */ }
}

async function startCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    message("camera-error", "Camera access is unavailable here. Open this local website in Chrome or Edge on the laptop."); return;
  }
  stopCamera("");
  const request = ++cameraRequest;
  cameraBusy = true;
  cameraControls();
  message("camera-error", "");
  text("camera-message", "Allow camera access in the browser. You can cancel with Stop camera.");
  const deviceId = ui["camera-select"].value;
  try {
    const next = await navigator.mediaDevices.getUserMedia({ audio: false, video: { ...(deviceId ? { deviceId: { exact: deviceId } } : {}), width: { ideal: 1920 }, height: { ideal: 1080 } } });
    if (request !== cameraRequest) { next.getTracks().forEach((track) => track.stop()); return; }
    stream = next;
    ui["camera-video"].srcObject = stream;
    ui["camera-video"].hidden = false;
    ui["camera-empty"].hidden = true;
    await ui["camera-video"].play();
    if (request !== cameraRequest) return;
    const track = stream.getVideoTracks()[0];
    track.addEventListener("ended", () => { if (request === cameraRequest) stopCamera("Camera disconnected. Reconnect it, choose the camera, and start again."); });
    const settings = track.getSettings();
    text("camera-badge", "Preview live"); ui["camera-badge"].className = "badge good";
    text("observe-status", "Preview live; detection pending");
    text("camera-message", `${track.label || "Camera"}${settings.width && settings.height ? ` (${settings.width} × ${settings.height})` : ""}. Preview only; pest detection is not connected.`);
    await cameraList();
  } catch (error) {
    if (request !== cameraRequest) return;
    stopCamera();
    const errors = {
      NotAllowedError: "Camera permission was blocked. Allow camera access in the browser’s site settings, then start again.",
      NotFoundError: "No camera was found. Plug the USB webcam into the laptop, then start again.",
      NotReadableError: "The camera is busy or unavailable. Close other camera apps, then start again.",
      OverconstrainedError: "The selected camera is unavailable. Choose another camera, then start again."
    };
    message("camera-error", errors[error.name] || "The camera could not start. Check its USB connection and browser permission, then try again.");
  } finally { if (request === cameraRequest) { cameraBusy = false; cameraControls(); } }
}
ui["camera-start"].addEventListener("click", startCamera);
ui["camera-stop"].addEventListener("click", () => stopCamera());
ui["camera-select"].addEventListener("change", () => { if (stream) startCamera(); });
ui["camera-video"].addEventListener("loadedmetadata", cameraControls);
ui.snapshot.addEventListener("click", () => {
  const video = ui["camera-video"];
  if (!stream || !video.videoWidth) return;
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth; canvas.height = video.videoHeight;
  canvas.getContext("2d").drawImage(video, 0, 0);
  canvas.toBlob((blob) => {
    if (blob) { downloadBlob(blob, `test-plot-${Date.now()}.png`); text("camera-message", "Image download started. This image has not been analysed for pests."); }
  }, "image/png");
});
navigator.mediaDevices?.addEventListener?.("devicechange", cameraList);
window.addEventListener("pagehide", () => stopCamera());
document.addEventListener("visibilitychange", () => { if (!document.hidden) refreshState(); });
cameraList();
refreshPorts();
poll();
