"""Small helpers shared by the FastAPI tool apps.

install_idle_shutdown(app): make a login-node dev server exit on its own after a stretch
with no HTTP requests. The prep tools run as personal uvicorn servers on SHARED Great Lakes
login nodes, reached from the laptop via an SSH/VS Code port-forward. Because each login node
is a separate host and `ssh greatlakes` round-robins, it is easy to leave a server running on
gl-login5, hop to gl-login4 tomorrow, and forget the old one — it keeps holding a port and a
sliver of the (2-core / 4 GB) login budget. An idle timeout means a forgotten server cleans
itself up; an actively-used one never dies mid-session (every click resets the clock).

Idle = no request whatsoever for VOCAB_IDLE_MIN minutes (default 180; set 0 to disable). The
apps only talk to the server on user actions, so "idle" genuinely means "nobody is using it".
"""
from __future__ import annotations

import asyncio
import os
import signal
import time


def install_idle_shutdown(app, env_var: str = "PREP_IDLE_MIN", default_min: float = 180.0):
    """Attach last-request tracking + a watchdog that SIGTERMs this process once idle.

    Returns the timeout in seconds (0 = disabled), mostly so callers/tests can assert it.
    """
    try:
        idle_min = float(os.environ.get(env_var, default_min))
    except ValueError:
        idle_min = default_min
    idle_sec = max(0.0, idle_min * 60)

    state = {"last": time.monotonic()}

    @app.middleware("http")
    async def _mark_active(request, call_next):
        state["last"] = time.monotonic()
        return await call_next(request)

    if idle_sec <= 0:
        return 0.0  # disabled: keep the activity marker (harmless) but never shut down

    async def _watchdog():
        # check a few times per timeout window so shutdown lands within ~1/10 of it
        step = min(60.0, max(5.0, idle_sec / 10))
        while True:
            await asyncio.sleep(step)
            if time.monotonic() - state["last"] >= idle_sec:
                # graceful: uvicorn traps SIGTERM and unwinds the server cleanly
                os.kill(os.getpid(), signal.SIGTERM)
                return

    @app.on_event("startup")
    async def _start_watchdog():
        asyncio.create_task(_watchdog())

    return idle_sec
