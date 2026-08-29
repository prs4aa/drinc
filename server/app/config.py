import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    tcp_host: str = os.getenv("DRINK_TCP_HOST", os.getenv("TCP_HOST", "0.0.0.0"))
    tcp_port: int = int(os.getenv("DRINK_TCP_PORT", os.getenv("TCP_PORT", "33110")))
    web_host: str = os.getenv("DRINK_WEB_HOST", os.getenv("WEB_HOST", "0.0.0.0"))
    web_port: int = int(os.getenv("DRINK_WEB_PORT", os.getenv("WEB_PORT", "3000")))
    enable_camera: bool = (
        os.getenv("DRINK_ENABLE_CAMERA", "false").lower() in ("true", "1")
    )
    storage_dir: Path = Path(
        os.getenv(
            "DRINK_STORAGE_DIR",
            os.getenv(
                "STORAGE_DIR",
                str(
                    Path.home() / "Desktop"
                    if (Path.home() / "Desktop").exists()
                    else Path.home() / "drink_storage"
                ),
            ),
        )
    )


settings = Settings()
