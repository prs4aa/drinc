import asyncio
from typing import Any, Dict

pending_futures: Dict[str, asyncio.Future] = {}


def register_pending(key: str) -> asyncio.Future:
    loop = asyncio.get_running_loop()
    old_fut = pending_futures.pop(key, None)
    if old_fut and not old_fut.done():
        try:
            old_fut.cancel()
        except (asyncio.InvalidStateError, asyncio.CancelledError):
            pass
    fut = loop.create_future()
    pending_futures[key] = fut
    return fut


def resolve_pending(key: str, result: Any) -> None:
    fut = pending_futures.pop(key, None)
    if fut and not fut.done():
        try:
            fut.set_result(result)
        except (asyncio.InvalidStateError, asyncio.CancelledError):
            pass


def fail_pending(key: str, error: Exception) -> None:
    fut = pending_futures.pop(key, None)
    if fut and not fut.done():
        try:
            fut.set_exception(error)
        except (asyncio.InvalidStateError, asyncio.CancelledError):
            pass


def fail_all_pending(error: Exception) -> None:
    keys = list(pending_futures.keys())
    for key in keys:
        fut = pending_futures.pop(key, None)
        if fut and not fut.done():
            try:
                fut.set_exception(error)
            except (asyncio.InvalidStateError, asyncio.CancelledError):
                pass
