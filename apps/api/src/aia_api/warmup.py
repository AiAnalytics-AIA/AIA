"""The object map's kernels compiled in the background after the API starts.

The signed-off Sociomap methodology (aia-sociomap-5) runs numba kernels, compiled on their first
call in a process whose kernel cache is empty. A container's cache is empty on every start (the
image is read only; NUMBA_CACHE_DIR is /tmp, python.Dockerfile), so the first Metodika comparison
after a deploy paid the whole compile -- measured at 47.6 s against 8 s warm -- and the page sat on
"Porovnávám metodiky…" past the browser journey's 30 s.

With ``AIA_SOCIOMAP_WARMUP_ENABLED`` the API starts, after it is up, a separate process at a lower
priority that computes the code's preset map on the check panels once and exits; numba writes the
compiled kernels to the shared cache directory, and the API's own first comparison loads them. A
separate process, not a thread: numba compiles holding the GIL, and in a thread the API's health
p95 went from 8 ms to 60 ms (max 624 ms) for the minute it took. A thread only waits for it, to
log how long it took or why it failed; a failure changes nothing.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import time
from collections.abc import Sequence

_log = logging.getLogger("aia.warmup")

#: What the warm-up process runs: the domain's warm_object_maps, in a fresh interpreter.
WARM_COMMAND: tuple[str, ...] = (
    sys.executable,
    "-c",
    "from aia_core.domain.methodology.sociomap_check import warm_object_maps;"
    "print(warm_object_maps())",
)


def start_object_map_warmup(command: Sequence[str] = WARM_COMMAND) -> threading.Thread:
    """Run ``command`` as a child process at a lower priority; a daemon thread waits for it and
    logs "sociomap kernels warm" with the seconds it took, or why it failed. Returns the thread."""

    def run() -> None:
        started = time.perf_counter()
        try:
            child = subprocess.Popen(
                list(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            # Below the API's own requests; set from here, since a preexec_fn is not safe in a
            # process that runs threads.
            os.setpriority(os.PRIO_PROCESS, child.pid, 10)
            try:
                out, err = child.communicate(timeout=600)
            except subprocess.TimeoutExpired:
                child.kill()
                child.communicate()
                raise
        except (OSError, subprocess.SubprocessError):
            _log.warning("sociomap warm-up failed", exc_info=True)
            return
        seconds = round(time.perf_counter() - started, 1)
        if child.returncode != 0:
            _log.warning(
                "sociomap warm-up failed",
                extra={"context": {"seconds": seconds, "stderr": err[-2000:]}},
            )
            return
        _log.info(
            "sociomap kernels warm",
            extra={"context": {"panels": out.strip(), "seconds": seconds}},
        )

    thread = threading.Thread(target=run, name="aia-sociomap-warmup", daemon=True)
    thread.start()
    return thread
