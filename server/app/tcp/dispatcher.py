import asyncio
from typing import Any, Dict, Optional

pending_futures: Dict[str, asyncio.Future] = {}


def _make_key(key: str, client_id: Optional[str] = None) -> str:
    if client_id:
        return f"{client_id}:{key}"
    return key


def register_pending(key: str, client_id: Optional[str] = None) -> asyncio.Future:
    loop = asyncio.get_running_loop()
    full_key = _make_key(key, client_id)
    old_fut = pending_futures.pop(full_key, None)
    if old_fut and not old_fut.done():
        try:
            old_fut.cancel()
        except (asyncio.InvalidStateError, asyncio.CancelledError):
            pass
    fut = loop.create_future()
    pending_futures[full_key] = fut
    return fut


def resolve_pending(key: str, result: Any, client_id: Optional[str] = None) -> None:
    if client_id:
        full_key = _make_key(key, client_id)
        fut = pending_futures.pop(full_key, None)
        if fut and not fut.done():
            try:
                fut.set_result(result)
            except (asyncio.InvalidStateError, asyncio.CancelledError):
                pass
            return
    fut = pending_futures.pop(key, None)
    if fut and not fut.done():
        try:
            fut.set_result(result)
        except (asyncio.InvalidStateError, asyncio.CancelledError):
            pass


def fail_pending(key: str, error: Exception, client_id: Optional[str] = None) -> None:
    if client_id:
        full_key = _make_key(key, client_id)
        fut = pending_futures.pop(full_key, None)
        if fut and not fut.done():
            try:
                fut.set_exception(error)
            except (asyncio.InvalidStateError, asyncio.CancelledError):
                pass
            return
    fut = pending_futures.pop(key, None)
    if fut and not fut.done():
        try:
            fut.set_exception(error)
        except (asyncio.InvalidStateError, asyncio.CancelledError):
            pass


def fail_all_pending(error: Exception, client_id: Optional[str] = None) -> None:
    if client_id:
        prefix = f"{client_id}:"
        matching_keys = [k for k in pending_futures.keys() if k.startswith(prefix)]
        for k in matching_keys:
            fut = pending_futures.pop(k, None)
            if fut and not fut.done():
                try:
                    fut.set_exception(error)
                except (asyncio.InvalidStateError, asyncio.CancelledError):
                    pass
        return

    keys = list(pending_futures.keys())
    for key in keys:
        fut = pending_futures.pop(key, None)
        if fut and not fut.done():
            try:
                fut.set_exception(error)
            except (asyncio.InvalidStateError, asyncio.CancelledError):
                pass
