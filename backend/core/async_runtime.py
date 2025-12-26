import asyncio
import threading
from typing import Any, Coroutine

_loop = None
_thread = None

def start_background_loop() -> asyncio.AbstractEventLoop:
    global _loop, _thread
    if _loop is not None:
        return _loop

    def _run():
        global _loop
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
        _loop.run_forever()

    _thread = threading.Thread(target=_run, name="async-runtime-loop", daemon=True)
    _thread.start()

    while _loop is None:
        pass

    return _loop

def run_async(coro: Coroutine[Any, Any, Any]) -> Any:
    """
    Submit coroutine to the background loop and wait for result (sync -> async bridge).
    """
    loop = start_background_loop()
    fut = asyncio.run_coroutine_threadsafe(coro, loop)
    return fut.result()