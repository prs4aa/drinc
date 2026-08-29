from typing import Set
from fastapi import WebSocket

audio_clients: Set[WebSocket] = set()


def add_audio_client(ws: WebSocket) -> None:
    audio_clients.add(ws)


def remove_audio_client(ws: WebSocket) -> None:
    audio_clients.discard(ws)


async def broadcast_audio(chunk: bytes) -> None:
    dead = set()
    for ws in list(audio_clients):
        try:
            await ws.send_bytes(chunk)
        except Exception:
            dead.add(ws)
    audio_clients.difference_update(dead)
