from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import IO

from app.core.config import PROJECT_ROOT

try:  # POSIX only; Windows falls back to "always run" (single-worker documented constraint).
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

logger = logging.getLogger("marketscope")


class TickerLeaderLock:
    """Advisory file lock so only one worker process runs the synthetic market ticker.

    With several uvicorn workers every process would otherwise apply its own random-walk
    step, multiplying price movement. The first process to take the lock is the leader.
    """

    def __init__(self, path: Path | None = None) -> None:
        data_dir = PROJECT_ROOT / "data"
        base = data_dir if data_dir.is_dir() else Path(tempfile.gettempdir())
        self.path = path or base / ".market-ticker.lock"
        self._handle: IO[str] | None = None

    def acquire(self) -> bool:
        if fcntl is None:  # pragma: no cover
            return True
        handle = open(self.path, "w")  # noqa: SIM115 - held for the process lifetime
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            logger.info("market ticker already running in another worker; this worker will not tick")
            return False
        self._handle = handle
        return True

    def release(self) -> None:
        if self._handle is not None and fcntl is not None:
            try:
                fcntl.flock(self._handle, fcntl.LOCK_UN)
            finally:
                self._handle.close()
                self._handle = None
