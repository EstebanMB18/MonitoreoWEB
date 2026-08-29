from __future__ import annotations

from threading import Lock, RLock
from contextlib import contextmanager


class MonitorLockedError(RuntimeError):
    pass


class MonitorLockManager:
    def __init__(self) -> None:
        self._guard = RLock()
        self._locks: dict[str, Lock] = {}
        self._owners: dict[str, str] = {}

    def _get_lock(self, monitor: str) -> Lock:
        monitor = monitor.upper()

        with self._guard:
            if monitor not in self._locks:
                self._locks[monitor] = Lock()

            return self._locks[monitor]

    def acquire(
        self,
        monitor: str,
        run_id: str,
        blocking: bool = False,
    ) -> bool:
        monitor = monitor.upper()
        lock = self._get_lock(monitor)

        acquired = lock.acquire(blocking=blocking)

        if acquired:
            with self._guard:
                self._owners[monitor] = run_id

        return acquired

    def release(self, monitor: str, run_id: str | None = None) -> None:
        monitor = monitor.upper()

        with self._guard:
            lock = self._locks.get(monitor)
            owner = self._owners.get(monitor)

            if not lock:
                return

            if run_id is not None and owner != run_id:
                raise MonitorLockedError(
                    f"{monitor} pertenece al run {owner}, no a {run_id}"
                )

            if not lock.locked():
                self._owners.pop(monitor, None)
                return

            self._owners.pop(monitor, None)

        lock.release()

    def is_locked(self, monitor: str) -> bool:
        monitor = monitor.upper()
        lock = self._get_lock(monitor)
        return lock.locked()

    def owner(self, monitor: str) -> str | None:
        monitor = monitor.upper()

        with self._guard:
            return self._owners.get(monitor)

    def status(self) -> dict[str, dict]:
        with self._guard:
            monitors = set(self._locks) | set(self._owners)

            return {
                monitor: {
                    "locked": self._locks[monitor].locked(),
                    "run_id": self._owners.get(monitor),
                }
                for monitor in sorted(monitors)
            }

    @contextmanager
    def hold(self, monitor: str, run_id: str):
        if not self.acquire(monitor, run_id, blocking=False):
            owner = self.owner(monitor)

            raise MonitorLockedError(
                f"{monitor} ya está en ejecución por {owner}"
            )

        try:
            yield
        finally:
            self.release(monitor, run_id)
