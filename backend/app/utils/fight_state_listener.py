import asyncio
import json
import os
import select
import threading
from typing import Set

import psycopg2

_loop: asyncio.AbstractEventLoop | None = None
_thread: threading.Thread | None = None
_stop_event = threading.Event()
_queues: Set[asyncio.Queue] = set()
_lock = threading.Lock()


def register_queue(q: asyncio.Queue) -> None:
    with _lock:
        _queues.add(q)


def unregister_queue(q: asyncio.Queue) -> None:
    with _lock:
        _queues.discard(q)


def _fan_out(payload: str) -> None:
    with _lock:
        for q in _queues:
            _loop.call_soon_threadsafe(q.put_nowait, payload)


def _listener_loop() -> None:
    dsn = os.getenv("DATABASE_URL")
    while not _stop_event.is_set():
        conn = None
        try:
            conn = psycopg2.connect(dsn)
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute("LISTEN fight_state")

            while not _stop_event.is_set():
                if select.select([conn], [], [], 1.0) == ([], [], []):
                    continue
                conn.poll()
                while conn.notifies:
                    notify = conn.notifies.pop(0)
                    _fan_out(notify.payload)
        except Exception:
            import traceback
            traceback.print_exc()
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
        if not _stop_event.is_set():
            _stop_event.wait(2.0)


def start(loop: asyncio.AbstractEventLoop) -> None:
    global _loop, _thread
    _loop = loop
    _stop_event.clear()
    _thread = threading.Thread(target=_listener_loop, daemon=True)
    _thread.start()


def stop() -> None:
    _stop_event.set()
    if _thread is not None:
        _thread.join(timeout=5)
