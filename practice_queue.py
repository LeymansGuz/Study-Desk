"""Per-user serialization for indexing, export, and explanation work."""
from __future__ import annotations
import asyncio
import weakref
from contextlib import asynccontextmanager
_LOCKS = weakref.WeakKeyDictionary()

@asynccontextmanager
async def request_slot(user_id):
    loop = asyncio.get_running_loop()
    locks = _LOCKS.setdefault(loop, {})
    entry = locks.setdefault(user_id, [asyncio.Lock(), 0])
    entry[1] += 1
    try:
        async with entry[0]:
            yield
    finally:
        entry[1] -= 1
        if entry[1] == 0:
            locks.pop(user_id, None)
