import asyncio
import struct


async def send_frame(writer: asyncio.StreamWriter, payload: bytes) -> None:
    header = struct.pack(">I", len(payload))
    writer.write(header + payload)
    await writer.drain()


async def recv_frame(reader: asyncio.StreamReader) -> bytes:
    raw_len = await reader.readexactly(4)
    length = struct.unpack(">I", raw_len)[0]
    return await reader.readexactly(length)
