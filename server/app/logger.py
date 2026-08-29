import time
from collections import deque
from typing import List

logs = deque(maxlen=200)


def log_event(msg: str, level: str = "INFO") -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{ts}] [{level.upper()}] {msg}"
    logs.append(formatted)


def log_info(msg: str) -> None:
    log_event(msg, "INFO")


def log_warn(msg: str) -> None:
    log_event(msg, "WARN")


def log_error(msg: str) -> None:
    log_event(msg, "ERROR")


def get_logs() -> List[str]:
    return list(logs)


def clear_logs() -> None:
    logs.clear()
