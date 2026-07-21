// Remote User client — Phase 1: render the stream, tap = move + left click.

"use strict";

const canvas = document.getElementById("screen");
const ctx = canvas.getContext("2d");
const statusEl = document.getElementById("status");

const token = new URLSearchParams(location.search).get("token");

// Where the last frame was drawn on the canvas (letterboxed) — needed to map
// a tap back to 0-1 coordinates within the remote monitor.
let drawRect = { x: 0, y: 0, w: 1, h: 1 };
let frameSize = { w: 0, h: 0 };
let ws = null;

function setStatus(cls, text) {
  statusEl.className = cls;
  statusEl.textContent = text;
}

function resizeCanvas() {
  canvas.width = window.innerWidth * devicePixelRatio;
  canvas.height = window.innerHeight * devicePixelRatio;
}
window.addEventListener("resize", resizeCanvas);
resizeCanvas();

async function drawFrame(blob) {
  const bitmap = await createImageBitmap(blob);
  frameSize = { w: bitmap.width, h: bitmap.height };

  const scale = Math.min(canvas.width / bitmap.width, canvas.height / bitmap.height);
  const w = bitmap.width * scale;
  const h = bitmap.height * scale;
  const x = (canvas.width - w) / 2;
  const y = (canvas.height - h) / 2;
  drawRect = { x, y, w, h };

  ctx.fillStyle = "#0f172a";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(bitmap, x, y, w, h);
  bitmap.close();
}

// Maps a client tap to 0-1 coordinates within the remote monitor, or null
// when the tap lands on the letterbox padding.
function toRemote(clientX, clientY) {
  const px = clientX * devicePixelRatio;
  const py = clientY * devicePixelRatio;
  const x = (px - drawRect.x) / drawRect.w;
  const y = (py - drawRect.y) / drawRect.h;
  if (x < 0 || x > 1 || y < 0 || y > 1) return null;
  return { x, y };
}

function send(msg) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
}

canvas.addEventListener("pointerdown", (e) => {
  const pos = toRemote(e.clientX, e.clientY);
  if (pos) send({ type: "pointer_down", x: pos.x, y: pos.y, button: "left" });
});

canvas.addEventListener("pointerup", (e) => {
  const pos = toRemote(e.clientX, e.clientY);
  if (pos) send({ type: "pointer_up", x: pos.x, y: pos.y, button: "left" });
});

function connect() {
  setStatus("connecting", "Connecting…");
  ws = new WebSocket(`ws://${location.host}/ws`);
  ws.binaryType = "blob";

  ws.onopen = () => {
    ws.send(JSON.stringify({ type: "auth", token }));
    setStatus("connected", "Connected");
  };

  ws.onmessage = (e) => {
    if (e.data instanceof Blob) drawFrame(e.data);
  };

  ws.onclose = () => {
    setStatus("disconnected", "Disconnected — retrying…");
    setTimeout(connect, 2000);
  };
}

connect();
